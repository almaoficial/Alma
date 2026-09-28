# Fase 2.3 — Freno humano (2026-09-27)

**Estado:** construida, tests en verde, servicio reiniciado sano (puerto 8471, pid 10868).
**Costo:** US$0. Sin API keys. **Cambio de contrato deliberado** (decisión del usuario, 27/9):
el meta-loop **deja de auto-adoptar**.

## Qué cambió

**Nuevo: `alma_service/promotor.py`** — pipeline de promoción con freno humano:
- `proponer()`: un PASS de la puerta de dos splits entra a **staging** (tabla
  `staging_promociones`). Solo **una** promoción en espera por vez.
- `pendiente()` / `inspeccionar(id)`: la promoción en espera es totalmente
  inspeccionable — **qué cambia** (diff `{parámetro: [antes, después]}`),
  **qué Δ medido la justifica** (delta_in, delta_ho, motivo de la puerta),
  **en qué splits pasó** (evidencia: seed, rondas, preregistro, keeps,
  train/heldout antes/después).
- `aprobar(id, aprobador)`: solo un aprobador de la allowlist `("humano",)`
  (espeja el fix A3b de politicas.py). Solo entonces se ejecuta el commit.
- `rechazar(id, motivo, aprobador)`: exige motivo; archiva la promoción; el
  sistema sigue con el scaffold vigente — el rechazo no rompe nada.

**`metaloop.py`**: el bloque de auto-adopción se reemplazó por staging. El
commit real vive en `_aplicar_promocion()`, invocado **solo** desde
`Promotor.aprobar()` con aprobador autorizado. `event_log` se propaga al
promotor vía property setter (server.py no cambió su línea
`metaloop.event_log = event_log`).

**`server.py`** — endpoints nuevos:
- `GET /fase2/promocion/pendiente` → staging inspeccionable + allowlist.
- `POST /fase2/promocion/aprobar` → `{"id", "aprobador"}` (default "humano").
- `POST /fase2/promocion/rechazar` → `{"id", "motivo", "aprobador"}`.
- `/fase2/estado` suma la sección `fase23`.

**Trazabilidad (event log 2.2):** `promocion_staging` (actor=promotor),
`promocion_aprobada` / `promocion_rechazada` (actor=aprobador, con ts) +
ledger del meta-loop con hash encadenado.

## Cómo se ve en la práctica

1. El meta-loop corre (semanal o a pedido). Si la puerta da FAIL, nada pasa
   (como antes, queda en el ledger).
2. Si da PASS, aparece en `GET /fase2/promocion/pendiente`: el diff, los
   deltas, la evidencia. **El scaffold vigente no se tocó.**
3. Él aprueba (`POST .../aprobar {"id": N}`) → commit con lineage, o rechaza
   (`POST .../rechazar {"id": N, "motivo": "..."}`) → archivado con motivo.
4. Sin su "sí" no hay commit. Nunca. El loop no puede auto-aprobarse: ni
   siquiera el label "loop"/"metaloop" pasa la allowlist.

## Verificación

- Nuevo `test_fase23_freno_humano.py`: **31/31 en verde** (staging sin commit,
  allowlist, doble aprobación bloqueada, rechazo con motivo, integración
  MetaLoop PASS→staging sin auto-adopción, FAIL→sin staging, trazabilidad).
- Suite completa existente en verde (incluida bit-identidad fase 0 y
  `test_fase2_metaloop.py` 12/12 con el nuevo contrato).
- En vivo: corrida real del meta-loop (seed 23, rondas 2) → puerta FAIL
  honesto, sin staging, scaffold intacto (n0=4). Endpoints validados:
  400 sin id/motivo, rechazo de aprobador no autorizado.

## Líneas rojas intactas

Anti-auto-edición (el loop propone parámetros del espacio acotado, nunca
código); validador congelado; enforcement determinístico fuera del modelo;
fases 0/1/2.1/2.2 sin cambios de comportamiento; rollback manual sigue
siendo acción humana directa.
