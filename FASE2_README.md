# ALMA — Fase 2: servicio persistente 24/7

Núcleo del sistema real. Construido 2026-09-27 sobre `servicio/` (motor,
server en puerto 8471, store SQLite) y `alma_service/` (scaffold validado,
memoria con olvido, skills, Curator, detector de recurrencia, resolver).

**Lo que la evidencia permite** (EXP45–61, fase 1): ningún LLM genera
skills útiles — ni en prosa (fase 1: diferencia conductual 0,000) ni en
parámetros (EXP61: +0,40 vs oráculo perfecto). Lo validado es el loop RSO
que tunea hiperparámetros del scaffold (EXP56/57) y el scaffold fijo
evolucionado. Por eso **no hay proveedor generativo en fase 2**: el
sistema conserva scaffold fijo evolucionado + memoria con olvido 0.5^d +
detector de recurrencia + Curator.

## Qué corre

| Componente | Módulo | Estado |
|---|---|---|
| Presupuesto con topes duros | `alma_service/presupuesto.py` | Activo |
| Meta-loop RSO (proponente de scaffold) | `alma_service/metaloop.py` | Activo, en background |
| Benchmark propio (puerta de calidad) | `alma_service/benchmark.py` | Activo, a pedido + semanal |
| Revisión de background (heurística) | `alma_service/revision.py` | Activa, cada 50 interacciones |
| Curator determinista | `alma_service/curator.py` | Activo (barrido semanal) |
| Schedule semanal | cron `alma-fase2-semanal` | Domingos ~04:23 EDT |

### 1. Presupuesto (`presupuesto.py`)
Buckets: `servicio_diario` (70%), `metaloop` (20%), `curator` (5%),
`revision_bg` (5%) del tope mensual `ALMA_PRESUPUESTO_MENSUAL` (USD).
**Sin tope configurado (default 0.0) todo corre en modo barato**: la key
arranca APAGADA. `autorizar()` nunca corta con excepción: si el bucket no
alcanza, el componente se degrada a demo/mock. El gasto se persiste en la
tabla `gasto_mensual` (aditiva, por mes).

El motor gatea cada resolución: `_backend_efectivo()` usa el backend real
solo si el bucket `servicio_diario` autoriza el costo estimado
(`ALMA_COSTO_ESTIMADO_RESOLUCION`, default US$0,005); si no, usa demo para
esa resolución. El backend configurado (vault, exigido por el watchdog) se
conserva: queda cableado pero sin gastar. La respuesta incluye
`backend_efectivo` para auditarlo.

### 2. Meta-loop (`metaloop.py`)
El RSO de `exp56_rso/` como proponente de los 5 hiperparámetros del
scaffold, con **validador congelado**: importa el oráculo, el stream, el
cómputo de regret y los splits train [0,1,2] / held-out [3,4] de
e47/e56 sin tocarlos. Protocolo: pre-registro en disco antes de la
primera réplica → mutación greedy 1/ronda → keep/revert estricto →
adopción solo con mejora estricta en held-out → ledger con hash
encadenado + rollback (`/fase2/metaloop/revertir`). Corre en hilo
separado, nunca en el camino crítico; 8 rondas por corrida semanal
(EXP56 usó 24 en laboratorio). El scaffold vigente vive en la tabla
`scaffold_activo` (arranca en `DEFAULT_SCAFFOLD`: n0=4, umbral_base=1,
validados en EXP56/57).

### 3. Benchmark propio (`benchmark.py`)
El hueco que el estudio marcó en todos los agentes: nadie mide si el loop
mejora con el tiempo. Este benchmark fijo (mock US$0, mundo congelado,
5 réplicas pareadas) compara el scaffold vigente contra el baseline
`DEFAULT_SCAFFOLD` y guarda cada corrida en `benchmark_corridas`.
`mejora > 0` = el vigente gana. Si el meta-loop adopta algo peor, la
próxima corrida lo muestra.

### 4. Revisión de background (`revision.py`)
Cada `ALMA_REVISION_CADA` interacciones (default 50) se bifurca una
revisión heurística (US$0, sin LLM) en un hilo separado: detecta clases
con feedbacks negativos repetidos y propone notas de memoria. Las
propuestas quedan en `revisiones_pendientes` y **solo se aplican con
aprobación explícita** (`/fase2/revision/aprobar|rechazar`). Nada se
escribe solo.

### 5. Curator (`curator.py`)
Barrido determinista active→stale (14 días)→archived (30 días), ledger
append-only, nunca borra, solo skills `created_by=agent`. La
**consolidación LLM está implementada pero OPT-IN APAGADA por default**:
`consolidar_llm()` corta con `ConsolidacionNoHabilitada` salvo
`ALMA_CURATOR_LLM=1` explícito + aprobación del usuario.

## Endpoints nuevos (puerto 8471)

- `GET /fase2/estado` — presupuesto, scaffold vigente, metaloop, benchmark, revisión, curator.
- `POST /fase2/metaloop/correr` `{"seed"?, "rondas"?}` — a pedido, background.
- `POST /fase2/metaloop/revertir` — rollback al scaffold anterior.
- `POST /fase2/benchmark/correr` — benchmark a pedido.
- `POST /fase2/revision/aprobar|rechazar` `{"id"}` — gate de aprobación.
- `GET /fase2/revision/pendientes`
- `POST /fase2/curator/ciclo` — barrido determinista.

## Qué está APAGADO esperando aprobación del usuario

1. **Toda la key**: `ALMA_PRESUPUESTO_MENSUAL=0` → modo barato. Para gastar: fijar el tope mensual (decisión del usuario) y reiniciar el servicio.
2. **Consolidación LLM del Curator**: requiere `ALMA_CURATOR_LLM=1` + aprobación caso por caso.
3. **Revisión con LLM**: cableada como idea, no implementada; la revisión actual es heurística US$0.

## Decisiones del usuario que faltan

- **Ámbito**: ¿sobre qué dominio corre el servicio (inglés, como se habló)?
- **Presupuesto mensual**: tope en USD para `ALMA_PRESUPUESTO_MENSUAL`.
- **Dónde corre 24/7**: hoy corre en esta VM (el watchdog `alma-servicio-watchdog` lo vigila por cron horario y lo arranca con `ALMA_BACKEND=vault`); un despliegue permanente necesita decidirse.

## Tests

`test_fase2_presupuesto.py` (18), `test_fase2_metaloop.py` (12),
`test_fase2_revision.py` (10), `test_fase2_benchmark.py` (7),
`test_fase2_curator_optin.py` (3). Suites fase 0 y fase 1 intactas y en
verde. Correr: `python3 test_fase2_*.py` (convención del repo: scripts
planos, sin pytest).

## Notas de diseño

- El meta-loop muta solo hiperparámetros del registry existente; no inventa arquitecturas (lección EXP58: una heurística mal atribuida es peor que el azar).
- El presupuesto nunca rompe una resolución ni el /estado: todo gate está envuelto en try/except que degrada.
- Tablas nuevas (aditivas, `IF NOT EXISTS`): `gasto_mensual`, `scaffold_activo`, `revisiones_pendientes`, `benchmark_corridas`. Ninguna tabla existente fue tocada.
- Bug atrapado durante el build: deadlock join-dentro-del-lock en `MetaLoop.correr(bloqueante=True)` — el join va fuera del lock.
