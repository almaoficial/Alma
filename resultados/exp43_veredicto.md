# EXP43 — Veredicto: FAIL (hipótesis refutada, confirmación pre-registrada)

**Fecha:** 2026-09-27 · **Modo:** mock, replay puro, US$0 · **Duración:** ~1s
**Pre-registro:** `resultados/exp43-20260927/preregistro.json` (escrito antes de correr;
con una enmienda documentada post-ejecución, ver honestidad incómoda)
**Código:** `run_experiment43.py`
**Datos:** los mismos de EXP42 (`data_exp42/W{1,3,4,5,6}.json`, Coinbase público)

## Diseño
EXP42 dio PASS técnico pero su diagnóstico post-hoc lo refutó: el PASS vivía
en la asignación retroactiva de las 5h de probe por bloque (artefacto heredado
de EXP36). EXP43 pre-registra la contabilidad honesta **antes** de correr:
durante las horas de probe (q=0,1,2 y q=12,13) la posición es flat — el probe
solo mide (actualiza bandit + rep), no puntúa. La lógica de elección y los
sorteos Thompson son idénticos. Diseño pareado: se reutiliza el namespace de
semilla de EXP42 (`exp42-{w}-r{r}`), así que la diferencia honesto-vs-retroactivo
por (ventana, réplica) es efecto-contable puro.

## Criterio pre-registrado
Hipótesis a refutar: "regla36 con probe honesto le gana a buyhold".
PASS iff media_w(efecto) > 0 y (media − 1×desvío) > −0.02,
con efecto(w) = media de 4 réplicas (P&L_honesto − P&L_buyhold).
Resultado esperado: FAIL.

## Números

Efecto honesto vs buyhold por ventana (media de 4 réplicas):

| ventana | honesto | retroactivo (recomputado) | oficial EXP42 | artefacto |
|---|---|---|---|---|
| W1 BTC ago-sep | −11.04% | −3.92% | −3.92% | +7.12pp |
| W3 BTC ene-feb | +20.80% | +48.11% | +48.11% | +27.31pp |
| W4 ETH ago-sep | −12.17% | +22.94% | +22.94% | +35.11pp |
| W5 ETH abr-may | +0.09% | +28.84% | +28.84% | +28.75pp |
| W6 SOL ago-sep | −19.68% | +19.82% | +19.82% | +39.50pp |
| **media** | **−4.40%** | **+23.16%** | **+23.16%** | **+27.56pp** |

Resumen honesto: media_w = −4.40%, desvío = 15.76%, media−1sd = −20.15%.
Media < 0 → **FAIL de la hipótesis (refutación pre-registrada confirmada).**
Vara intacta.

## Validación interna (pre-registrada)
- Retroactivo recomputado vs oficial EXP42: max|dif| = 4.50e-07 → OK
  (dentro del redondeo a 6 decimales del report oficial).
- Honesto vs tabla post-hoc del veredicto EXP42: max|dif| = 3.74e-05 → OK
  (dentro del redondeo a 2 decimales de la tabla publicada).
- Dos replicaciones independientes coinciden al nivel de redondeo: la
  implementación está validada; la diferencia honesto-vs-retroactivo es
  con certeza efecto-contable puro, no bug.

## Implicancia para la serie 36–42: cuánto del P&L era artefacto contable
El mecanismo: las horas de probe se puntuaban con el P&L del brazo ganador
**elegido con los datos de esas mismas horas** (`pnl[elegido][h]` para
q en PROBE_Q1/Q2). Verificado por inspección de código que el patrón existe en:
- `run_experiment36.py` (líneas ~145, ~170: `pnl_alma_h[h] = pnl[elegido1][h]`)
- `run_experiment37.py`, `run_experiment38.py`, `run_experiment39.py`
  (las tres reglas), `run_experiment40.py`, `run_experiment42.py`
  (`fijar(PROBE_Q*, elegido...)`)
- `run_experiment41.py`: **no afectado** (política de régimen sin probe
  quarters; posiciones de bloque completo).

Cuantificación pareada (5 ventanas, mismas semillas): el artefacto infló el
efecto vs buyhold entre **+7.1pp (W1) y +39.5pp (W6)**, media **+27.6pp**.
Lectura por experimento:
- **EXP36** (dif −0.046%, "casi empate"): con contabilidad honesta el dif
  cae ~7pp (orden de magnitud medido en W1) → el empate era ficticio.
- **EXP37/38/39**: los FAILs se mantienen (ya eran negativos); las
  comparaciones *entre* reglas con probe están menos afectadas porque el
  artefacto inflaba a todas por igual, pero sus P&L absolutos vs buyhold
  estaban inflados.
- **EXP40**: usaba probe quarters → su −10.73% era optimista; el FAIL se
  mantiene. Su conclusión sobre el clasificador Hurst (48.3% de acierto)
  **no** depende del artefacto (es clasificación pura).
- **EXP42**: PASS técnico → refutado; la conclusión sustantiva ("ninguna
  adaptación generaliza") ahora está confirmada con vara pre-registrada.
- Lo que **sobrevive intacto**: el hallazgo de ruido de semilla (EXP38/39,
  sobre azar Thompson, independiente de la puntuación), la muerte del Hurst
  (EXP40/41, clasificación), y todos los veredictos FAIL (eran negativos
  aun con la inflación).

Estándar del laboratorio desde ahora: **toda política con probe pre-registra
contabilidad honesta (el probe cuesta) antes de correr.** Sin eso, cualquier
PASS futuro es sospechoso por construcción.

## Honestidad incómoda
1. **Enmienda al pre-registro (declarada):** la tolerancia de validación se
   corrigió de 1e-9 a 1e-6 post-ejecución porque los oficiales están
   redondeados a 6 decimales (1e-9 era más estricto que la precisión de los
   datos). Motivo mecánico, independiente del resultado: el test de hipótesis
   da FAIL con ambas tolerancias. Quedó registrado en `preregistro.json`
   como `enmienda_post_ejecucion`, no en silencio.
2. **Semillas reutilizadas de EXP42:** el test de hipótesis no usa azar
   fresco — pero nunca fue un test de suerte de semilla sino una comparación
   contable pareada; las 4 réplicas × 5 ventanas igual alimentan el criterio.
3. **K=5, todo cripto, todo 2026**, ventanas elegidas por el worker de EXP42:
   el sesgo de selección de períodos sigue vigente.
4. **La contabilidad "honesta" sigue siendo ligeramente optimista:** no cobra
   los costos de cambio flat→brazo en h=3 y h=14 (1bp por transición). Aplica
   igual a ambas versiones, así que no afecta la diferencia pareada ni la
   dirección del veredicto — solo haría el honesto un poco peor.
5. **W3 (crash −32.5%):** hasta el probe honesto le gana a buyhold (+20.8%),
   pero pierde contra flat (+32.5%). En crashes gana no estar, no el probe.
6. `regimen_adx` y `flat` no se re-corrieron (deterministas, idénticos a
   EXP42); no afectan a la hipótesis.

## Conclusión
La refutación de EXP42 queda confirmada con vara pre-registrada: con
contabilidad honesta del probe, **regla36 no le gana a buyhold en media a
través de ventanas (−4.40%, media−1sd −20.15%)**. El PASS de EXP42 era 100%
artefacto contable (+27.6pp de inflación media). La serie 36–43 cierra con
una lección metodológica más valiosa que cualquier PASS: siete experimentos
midieron un artefacto heredado sin verlo, y el laboratorio ahora tiene el
estándar para no repetirlo.

## Próxima pregunta servida (no lanzada — la decide el usuario)
La pregunta abierta ya no es *qué regla* ni *cómo puntuar el probe*: es
*dónde* hay señal para la selección adaptativa. Candidatas: escala diaria/
semanal en lugar de horaria; los 4 regímenes macro del informe cripto
(meses, no horas); o el dominio original de ALMA (elegir estrategia de
razonamiento por problema, con oráculo). Cualquiera de las tres merece
diseño explícito antes de correr.
