# EXP65 — Pre-registro: tuning del prior con memoria (no del probe)

**Fecha**: 2026-09-27. **Costo**: US$0 (mock). **Escrito ANTES de correr.**

## Motivación

EXP64 (ablación estilo Cherny): el prior con memoria vale +21,60 (f−e,
IC95 [+12,12, +31,08], 5/5) — más del doble que toda la maquinaria del
probe junta (+9,80). Ninguna pieza individual del probe es load-bearing.
Conclusión pre-registrada de EXP64: *el próximo tuning va al prior con
memoria, no al probe.* Este experimento es esa aplicación directa.

## Pregunta

¿Hay rendimiento sin exprimir en los hiperparámetros del prior con
memoria, con el resto del scaffold fijo en los valores validados?

## Genoma (solo hiperparámetros del prior)

- `n0`: fuerza del prior Beta — [2, 4, 6, 8] (actual: 4, validado EXP57)
- `decay`: base del olvido `decay^(b−1−blk)` — [0.3, 0.5, 0.7, 0.9, 1.0]
  (actual: 0.5; 1.0 = sin decaimiento)
- `cond`: granularidad del condicionamiento a la firma del régimen —
  ["completa", "gruesa", "ninguna"]
  - `completa`: comportamiento actual — solo historia de bloques con la
    misma firma exacta; fallback a prior ciego si no hay.
  - `gruesa`: pooling jerárquico — toda la historia pasada participa;
    peso 1.0 si misma firma, 0.3 si firma distinta (factor fijo,
    pre-registrado, no tunable).
  - `ninguna`: prior siempre ciego con historia decaída
    (equivale al tratamiento (b) de EXP64).

El probe, el skip, el gate adaptativo, `umbral_base`, `umbral_divisor`
y `gate_margin` quedan FIJOS en los valores validados (EXP56/57).
No se tocan.

## Loop

RSO estilo EXP56: greedy keep/revert de linaje único, máximo 24 rondas,
seed de propuestas 65. En cada ronda se propone UNA mutación (un
hiperparámetro → otro valor de su espacio).

**Puerta de dos splits** (`alma_service/gate.py`): cada candidato se
evalúa en held-in (réplicas [0,1,2]) y held-out (réplicas [3,4]),
5 réplicas pareadas por evaluación (mismo RNG por rep_id). Se adopta
ssi `Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(Δ_in, Δ_ho) > 0` (Δ = mejora en regret,
menor es mejor). Los trade-offs entre splits se rechazan.

**Caveat honesto**: el held-out participa en la puerta, así que hay
presión de selección sobre el gate a lo largo de las rondas (el propio
`gate.py` lo documenta). Es la disciplina nueva ejercitándose; el
informe independiente queda en `benchmark.py` (mundo congelado).

## Sanidades (pre-registradas, bloqueantes)

1. Con genoma inicial (`n0=4, decay=0.5, cond=completa`) el driver de
   EXP65 debe ser bit-idéntico a `correr_replica_param` con
   `DEFAULT_SCAFFOLD` en las 5 réplicas. Si no, no se corre el loop.
2. Determinismo: dos corridas del mismo genoma dan números idénticos.

## Métrica y criterio

Efecto final por réplica: `d_r = reg_final(r) − reg_init(r)`, r = 0..4.
Efecto medio `d̄` con IC95 t-pareado (t=2.776, gl=4).

**PASS** ssi `d̄ < 0` (menos regret) Y el IC95 no cruza el 0.
**FAIL** en cualquier otro caso — incluyendo el caso honesto de que
ninguna variante pase la puerta: el prior actual ya está en su óptimo
local.

## Veredicto

`veredicto.md`: qué hiperparámetros se movieron (trayectoria),
efecto con IC95, y la lectura — si el peso estaba donde no mirábamos,
¿cuánto había para exprimir?
