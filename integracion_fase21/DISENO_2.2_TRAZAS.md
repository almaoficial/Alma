# Fase 2.2 — Trazas unificadas: diseño del event log (as-built)

**Fecha:** 2026-09-28. **Estado:** diseñado e implementado en
`alma_service/trazas.py` (módulo nuevo, aditivo). **Costo:** US$0 (mock).
**Fuente:** `DISENO_PAQUETE_UNICO.md` §4–§5.

> En criollo: el servicio ahora anota cada decisión que toma en un diario
> propio y estructurado. Ese diario es lo que después va a leer el minero
> de debilidades para encontrar patrones de fallo en la operación real,
> no en experimentos.

## 1. Qué problema resuelve

Antes de 2.2 había dos mundos de trazas:

1. `servicio/trazas.py` + `trazas.db` — el **observador del asistente**:
   registra tarea → estrategia → resultado → feedback del *asistente*,
   con feedback del *usuario*.
2. Ledgers sueltos del servicio — `metaloop_ledger.jsonl`,
   `revisiones_pendientes`, etc.: decisiones del *servicio* dispersas
   en archivos con formatos distintos.

El minero de debilidades (`debilidades.py`) solo veía keeps/reverts del
metaloop, no la operación real. La fase 2.2 crea **UN** event log del
servicio: un formato, un lugar, un lector (el minero).

**Decisión de diseño (§5 del paquete único):** el observador del asistente
NO se mezcla con el event log. Señales distintas, semántica distinta:
el observador registra conducta con feedback subjetivo; el event log
registra decisiones con reward medido. Mezclarlos contaminaría al minero.
Viven en el mismo directorio con nombres distintos.

## 2. Dónde se escribe

- **Archivo:** `~/workspace/alma-prototype/alma_eventos.db`
  (SQLite, `PRAGMA journal_mode=WAL`, hilo-seguro con lock).
- **Módulo:** `alma_service/trazas.py`, clase `EventLog`.
- **Nombre deliberadamente distinto** de `trazas.db` (el observador).
- **Versión de esquema:** `schema_version = 1` en tabla `_meta`
  (permite migraciones futuras sin romper lectores viejos).

## 3. Esquema

### 3.1 `eventos_decision` — una fila por decisión del resolver

El contrato de `DISENO_PAQUETE_UNICO.md` §4.1, más campos operativos:

| Campo | Tipo | Contenido |
|---|---|---|
| `id` | INTEGER PK | autoincremental |
| `ts` | REAL | epoch del asentamiento |
| `firma_regimen` | TEXT | firma del régimen del problema (p. ej. `aritmetica`) |
| `veredicto_probe` | TEXT, NULL | brazo que ganó el probe; NULL si no hubo probe (modo thompson directo) o si aún no se midió |
| `brazo_elegido` | TEXT | brazo efectivamente usado (`cot`, `single`, `reflexion`, skill…) |
| `reward` | REAL, NULL | **NULL hasta que se mide.** Solo los eventos con reward medido son visibles para el minero. `feedback()` lo completa a posteriori vía `actualizar_reward()`. |
| `costo_usd` | REAL | costo medido de la decisión |
| `latencia_ms` | REAL, NULL | tiempo de resolución en ms |
| `scaffold_version` | TEXT | hash SHA-256 corto (12) del scaffold vigente — permite atribuir resultados a la versión que los produjo |
| `modo` | TEXT | `probe` / `thompson` (modo del resolver en ese momento) |
| `backend_efectivo` | TEXT | `demo`, `demo_forzado_modo_barato`, `vault`, `openai`… |
| `extras_json` | TEXT | JSON canónico (claves ordenadas): `gap`, `compromiso`, `transferencia`, `modo_agente`, `horizonte`. Extensible sin migraciones. |

**Semántica clave:** `reward NULL` ≠ `reward 0`. NULL significa "sin
medición todavía"; el minero (§4.2) solo lee `reward IS NOT NULL`. No
inventar señal donde no la hay.

### 3.2 `eventos_ciclo` — una fila por evento del ciclo de mejora

| Campo | Tipo | Contenido |
|---|---|---|
| `id` | INTEGER PK | autoincremental |
| `ts` | REAL | epoch |
| `tipo` | TEXT | taxonomía cerrada (ver §4) |
| `actor` | TEXT | emisor: `metaloop`, `promotor`, `curator`, `revision_background` |
| `detalle_json` | TEXT | JSON canónico con el payload del evento |

Índices: `idx_dec_ts`, `idx_dec_firma`, `idx_ciclo_tipo`.

## 4. Taxonomía de `eventos_ciclo` (inventario del código)

**Meta-loop** (`metaloop.py`, actor `metaloop`):
- `metaloop_corrida_iniciada` — el RSO semanal arrancó.
- `metaloop_propuesta` — candidato generado (qué parámetro mutó).
- `metaloop_puerta` — veredicto de la puerta de dos splits (Δ_in, Δ_ho).
- `metaloop_rollback` — reversión de una adopción.
- `metaloop_nucleo_bloqueado` — el loop intentó tocar el núcleo (bloqueado).

**Promotor** (`promotor.py`, actor `promotor` o el aprobador):
- `nucleo_bloqueado` — intento de tocar el núcleo.
- `auto_adopcion` / `auto_adopcion_rechazada` / `auto_adopcion_revertida`.
- `promocion_staging` — PASS de la puerta, versionado, queda en staging.
- `promocion_aprobada` / `promocion_rechazada` (actor = el aprobador humano).

**Curator** (`curator.py`, actor `curator`):
- `curator_transicion` — skill cambia de estado (active→stale→archived).

**Revisión de background** (`revision.py`, actor `revision_background`):
- `revision_propuesta` / `revision_aprobada` / `revision_rechazada`.

**Decisiones del resolver** (`servicio/motor.py`):
- `eventos_decision` vía `_asentar_traza()` (fail-safe interno).

## 5. Emisores y regla fail-safe

**El núcleo no sabe quién lo lee** (contrato §4.1): el resolver asienta y
sigue; nadie en el camino crítico espera al minero.

Regla dura de instrumentación, aplicada en los 5 emisores
(Motor, MetaLoop, Promotor, Curator, RevisionBackground):

1. `event_log` es **opcional** (`None` por defecto). Sin log, el
   comportamiento es idéntico al de antes (verificado en tests).
2. Cada emisión va envuelta en `try/except`: **el log nunca rompe el
   camino crítico**.
3. El mapeo experiencia→evento (`_exp_a_evento` en Motor, acotado a
   10.000 entradas) permite que `feedback()` complete el reward a
   posteriori sin buscar en disco.

## 6. Contrato con el minero (§4.2)

`EventLog.paquete_debilidades(minimo_soporte)`:

1. Lee **solo** `decisiones(con_reward=True)` — eventos con reward medido.
2. Agrupa por **firma exacta** `(firma_regimen, brazo_elegido, tramo)` con
   `tramo = "fallo"` si `reward < 0.5`, `"ok"` si ≥ 0.5.
3. Devuelve el paquete de evidencia **descriptivo**: clusters con soporte,
   sin prescripción (lección EXP58: el que atribuye y prescribe es peor
   que el azar).

Implementado en `debilidades.py`: `firma_decision()` + `minar_decisiones()`.
El minero describe; el proponente propone del espacio pre-registrado sin
usar la evidencia para dirigir mutaciones.

## 7. Retención

`EventLog.rotar()`: borra `eventos_decision` más viejos que
`RETENCION_DECISION_DIAS = 90` y `eventos_ciclo` más viejos que
`RETENCION_CICLO_DIAS = 180`. Determinista, sin LLM — mismo espíritu que
el olvido de la memoria (lo viejo pesa menos).

**Pendiente:** `rotar()` no está cableado a ningún schedule del servicio
(ver §9).

## 8. Lecturas de conveniencia

- `decisiones(firma_regimen, con_reward, desde, hasta, limite)` y
  `ciclo(tipo, desde, hasta, limite)` — filtros deterministas.
- `estado()` — conteos: decisiones, decisiones con reward, eventos de ciclo.
- `resumen_operacion(minimo_soporte)` — agregado por
  `(firma_regimen, brazo_elegido)`: n, n con reward, reward medio, costo
  medio. Determinista; insumo para el digest dominical y el minero.
- `servicio/server.py` expone `"trazas": event_log.estado()` en el
  endpoint de estado (solo lectura).

## 9. Qué falta para completar la 2.2

1. **Cablear `rotar()` a un mantenimiento periódico** — la retención está
   implementada y testeada, pero nadie la invoca. Opciones: el ciclo
   semanal del metaloop la corre antes de minar, o un cron del sistema.
   (No se tocó: el schedule vive en el servicio y la consigna prohíbe
   tocarlo en esta tarea.)
2. **Link `experiencia_id ↔ evento`** en `eventos_decision` — hoy el mapeo
   vive solo en memoria (`_exp_a_evento`). Persistirlo como columna
   nullable permitiría auditar decisión↔experiencia después de un restart.
3. **Ventanas de retención configurables** — hoy son constantes del
   módulo; podrían venir de configuración sin tocar código.
4. **El observador queda separado** — decisión de diseño permanente, no
   pendiente: `servicio/trazas.py` no alimenta al minero.

## 10. Lo que NO se tocó (líneas rojas respetadas)

- Servicio vivo del puerto 8471: no modificado (solo leído para verificar
  el cableado existente).
- Núcleo: topes de gasto (`presupuesto.py`), obligación de notificar
  (`promotor.py` notificaciones), validador congelado — intactos.
- Fase 0/1: la suite completa sigue en verde (ver reporte).
