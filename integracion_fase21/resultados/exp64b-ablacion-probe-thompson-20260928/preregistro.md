# EXP64b — Pre-registro: ablación probe-vs-Thompson

**Fecha**: 2026-09-28. **Costo**: US$0 (mock, cero llamadas API).
**Escrito ANTES de correr.** No toca el servicio vivo (puerto 8471).

## Motivación

EXP64 (n=5, 2026-09-27) ablacionó el scaffold componente por componente:
`sin_probe` midió efecto **+9,8**, IC95 [+2,59, +17,01], peor en 5/5 →
load-bearing ya con n=5. EXP64-skip (n=20 held-out, 2026-09-28) confirmó
el skip como load-bearing: **+6,55**, IC95 [+2,19, +10,92], 14/20.

Quedan sin aislar con potencia los otros dos componentes del loop:
el **probe** (medición al inicio de cada bloque) y el **Thompson
sampling** (exploración posterior en los slots no-probe). Este
experimento los mide a ambos con n=20 réplicas held-out.

## Pregunta

¿Qué parte del loop hace la fuerza: el probe, el Thompson, o ambos?
Medido como efecto sobre el regret al quitar cada componente por
separado, con n=20 réplicas held-out.

## Diseño

Mismo harness mock que EXP64/EXP64-skip (stream de
`run_experiment47.construir_stream`, tasas de `tasas.json`,
`DEFAULT_SCAFFOLD`, pareo por rep_id). `run_exp64.py` **NO se modifica**:
la lógica existente se reutiliza verbatim.

Tratamientos (pareados por rep_id — mismo RNG en los tres):
- **(a) control**: `e56.correr_replica_param` (implementación de
  referencia).
- **(b) sin_probe**: `r64.correr_replica_ablacion` con
  `{"sin_probe": True}` — flag EXISTENTE: Thompson pelado en los 10
  items del bloque, sin medición previa.
- **(c) sin_thompson**: flag NUEVO `{"sin_thompson": True}`,
  implementado en una copia verbatim de `correr_replica_ablacion`
  dentro de `run_exp64b.py` (este experimento). Semántica
  pre-registrada:
  - El probe queda INTACTO: Q1 siempre se mide; Q2 se mide ssi el gate
    lo pide (mismas decisiones de medición que el control); el camino
    de skip no cambia; los rewards de política en items medidos siguen
    siendo los del favorito del prior (`fav`).
  - Único cambio: en los slots donde el control corre Thompson
    sampling, se EXPLOTA al ganador del probe — el brazo con mayor
    reward medio observado en las mediciones del probe de ESTE bloque
    hasta ese punto (Q1 para los slots 3,4,5 y para Q2 cuando el gate
    lo declara decisivo; Q1+Q2 para los slots 8,9 cuando Q2 se midió).
  - Desempate determinista por orden de brazos. `rep_hist` se actualiza
    para el ganador (alimenta skills y prior de régimen en bloques
    futuros, igual que el control). El bandit no se consulta para
    seleccionar (maquinaria Thompson totalmente apagada).
  - Justificación: una sola cosa por vez — el gate y el skip quedan
    intactos para no confundir la ablación. Esto aísla el valor de la
    EXPLORACIÓN por muestreo posterior, manteniendo idéntica la
    información del probe.

Réplicas: `200..219` (20 **held-out**: EXP64 usó 0..4, EXP64-skip usó
100..119; estos IDs nunca se usaron — streams RNG frescos).

## Métrica

Regret total por réplica. Efecto de quitar el componente X:
`d_r = reg_sin_X(r) − reg_control(r)`, r = 200..219.
Efecto medio `d̄` con IC95 t-pareado (**t=2,093, gl=19**).
d̄ > 0 = quitar el componente empeora (el componente cargaba peso).

## Criterio pre-registrado (vara sagrada, por componente)

El componente es **load-bearing** ssi se cumplen las tres:
1. d̄ > 0,
2. el IC95 de d̄ NO cruza el 0,
3. d_r > 0 en ≥14/20 réplicas (70%).

El componente es **nocivo** (se poda) ssi se cumple el espejo:
1. d̄ < 0,
2. el IC95 de d̄ NO cruza el 0,
3. d_r < 0 en ≥14/20 réplicas.

Si no se cumple ninguno: **sin efecto detectable con n=20** — no se
poda, no se declara útil; se reporta el IC tal cual (incluido su ancho)
y se dice sin anestesia.

## Expectativas honestas (no son criterios)

- `sin_probe`: se espera que REPLIQUE el load-bearing de EXP64
  (prior: +9,8, IC95 [+2,59, +17,01], 5/5). Si no replica, el veredicto
  lo dice sin anestesia.
- `sin_thompson`: pregunta ABIERTA, sin compromiso direccional.
  Hipótesis A: en un mundo mock de regímenes limpios el probe ya
  identifica al ganador y la exploración de Thompson es puro costo
  (cf. lección EXP44) → quitarlo mejora o no cambia. Hipótesis B: el
  probe es ruidoso y Thompson aporta en bloques inciertos → quitarlo
  empeora. El criterio simétrico decide.

## Sanidades pre-registradas

1. Determinismo: dos corridas del control en la misma réplica dan el
   mismo número.
2. Bit-identidad: la copia extendida con flags apagados ==
   `r64.correr_replica_ablacion` con flags apagados en 3 réplicas
   nuevas (200/207/219). Si falla, no se corre nada.

## Caveats pre-registrados

- Mundo mock con regímenes sintéticos limpios: mide la maquinaria,
  no garantiza el mismo orden de magnitud con modelos reales.
- Dos ablaciones, un criterio por componente (misma convención que
  EXP64). Comparación entre componentes (quién hace más fuerza) es
  descriptiva sobre los efectos medidos, no un tercer test.

## Veredicto

`veredicto.md`: PASS/FAIL por componente con números (efecto, IC95,
conteo), diagnóstico honesto, ranking de qué parte del loop hace la
fuerza (probe vs Thompson vs skip +6,55 de EXP64-skip), y decisión
(conservar / podar / sin evidencia) por componente.
