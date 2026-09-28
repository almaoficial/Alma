# Fase 2.2 — Trazas unificadas (2026-09-27)

**Estado:** construida, tests en verde, servicio reiniciado sano (puerto 8471).
**Costo:** US$0. Sin API keys. Sin cambios de contrato: el meta-loop sigue
auto-adoptando como antes (el freno humano es fase 2.3); ninguna promoción
cambia de comportamiento; el loop no toca código (línea roja intacta).

## Qué se construyó

**Nuevo: `alma_service/trazas.py`** — `EventLog`, el event log estructurado
único del servicio (SQLite + WAL, hilo-seguro), en
`~/workspace/alma-prototype/alma_eventos.db` (mismo directorio que las demás
DBs, nombre distinto al observador del asistente `trazas.db` — semánticas
distintas, no se mezclan por diseño §5):

- `eventos_decision`: el contrato §4.1 — `(ts, firma_regimen,
  veredicto_probe, brazo_elegido, reward, costo_usd, latencia_ms,
  scaffold_version)` + modo, backend_efectivo, extras JSON.
- `eventos_ciclo`: propuestas del meta-loop, veredictos de la puerta de dos
  splits, adopciones/rollbacks, transiciones del Curator,
  propuestas/aprobaciones/rechazos de la revisión.
- `rotar()`: retención determinista (90 días decisiones, 180 ciclo).
- `paquete_debilidades()`: evidencia descriptiva lista para el minero.

**Puente minero (`debilidades.py`, aditivo):** `firma_decision()` +
`minar_decisiones()` — agrupan por firma exacta
`(firma_regimen, brazo_elegido, tramo_reward)` solo sobre eventos con reward
medido. Describen, no prescriben.

## Qué se instrumentó (todo fail-safe: el log nunca rompe el camino crítico)

| Módulo | Eventos |
|---|---|
| `servicio/motor.py` (`_resolver_locked`) | 1 decisión por resolución: firma=clase, veredicto del probe (modo probe), brazo, reward, costo, latencia, hash del scaffold vigente |
| `servicio/motor.py` (`feedback`) | completa el `reward` del evento cuando llega feedback explícito |
| `alma_service/metaloop.py` | corrida_iniciada, propuesta (por ronda), veredicto de la puerta, rollback |
| `alma_service/curator.py` | transiciones active→stale→archived + ablación por evidencia |
| `alma_service/revision.py` | propuesta, aprobación, rechazo |
| `servicio/server.py` | cableado + sección `fase22` en `/fase2/estado` |

## Ejemplo de traza real (servicio en vivo, 27/9)

```json
{"id": 1, "firma_regimen": "aritmetica", "veredicto_probe": null,
 "brazo_elegido": "cot", "reward": 0.9, "costo_usd": 8.7e-06,
 "latencia_ms": 23.5, "scaffold_version": "78d5e686a83d",
 "modo": "thompson", "backend_efectivo": "demo_forzado_modo_barato"}
```

El `reward: 0.9` llegó por `/feedback` posterior a la decisión — el mapa
experiencia→evento lo completa a posteriori, que es exactamente lo que el
minero necesita (§4.2: solo eventos con reward medido).

## Tests

- Nuevo `test_fase22_trazas.py`: **31/31 en verde** (contrato §4.1,
  reward a posteriori, puente minero, retención, instrumentación del Motor
  con y sin trazas, emisores de ciclo).
- Suite completa existente: todo en verde (26 archivos `test_*.py` +
  6 en `tests/`), incluida la bit-identidad del resolver de fase 0.

## Lo que sigue (fase 2.3)

El minero ya puede leer operación real vía
`event_log.paquete_debilidades()`; el cableado del ciclo completo
(proponente → validador → puerta → staging → aprobación humana → commit)
es la próxima fase, con el cambio de contrato deliberado: el meta-loop
deja de auto-adoptar.
