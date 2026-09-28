# EXP64-skip — Pre-registro: ablación del skip, follow-up con más réplicas

**Fecha**: 2026-09-28. **Costo**: US$0 (mock). **Escrito ANTES de correr.**

## Motivación

EXP64 (2026-09-27) ablacionó el scaffold con n=5 réplicas. El skip del
probe mostró efecto +6,00 (quitarlo empeora en media) con
IC95 [−2,60, +14,60] y peor en 3/5 réplicas → **no load-bearing** por
falta de potencia, no por evidencia de inutilidad. El veredicto lo dejó
explícito: "El skip (+6,00, CI [−2,60, +14,60]) es el candidato para un
follow-up con más réplicas."

Este experimento es ese follow-up.

## Pregunta

¿El skip del probe (EXP52) carga peso de verdad en el regret, o es
decoración? Medido con n=20 réplicas held-out.

## Diseño

Implementación: se reutiliza `correr_replica_ablacion` de
`../exp64-ablacion-20260927/run_exp64.py` SIN modificarla (el control
con flags apagados es bit-idéntico a `e56.correr_replica_param`,
sanidad ya probada en EXP64). Estructura espejada del EXP67: probe por
bloque (Q1/Q2), Thompson por bloque/régimen, skip del EXP52 vía
`soporte_param`, prior condicionado a la firma del régimen.

Tratamientos (pareados por rep_id — mismo RNG en ambos):
- **control**: flags `{}` (con skip).
- **sin_skip**: flags `{"sin_skip": True}` (se mide todo, nunca se salta).

Réplicas: `100..119` (20 réplicas **held-out**: EXP64 usó 0..4; estos
IDs nunca se usaron — streams RNG frescos).

## Métrica

Regret total por réplica. Efecto del skip:
`d_r = reg_sin_skip(r) − reg_control(r)`, r = 100..119.
Efecto medio `d̄` con IC95 t-pareado (**t=2,093, gl=19**).
d̄ > 0 = quitar el skip empeora (el skip cargaba peso).

## Criterio pre-registrado (vara sagrada)

El skip es **load-bearing** ssi se cumplen las tres:
1. d̄ > 0,
2. el IC95 de d̄ NO cruza el 0,
3. d_r > 0 en ≥14/20 réplicas (70%).

El skip es **nocivo** (se poda) ssi se cumple el espejo:
1. d̄ < 0,
2. el IC95 de d̄ NO cruza el 0,
3. d_r < 0 en ≥14/20 réplicas.

Si no se cumple ninguno: **sin efecto detectable con n=20** — no se
poda, no se declara útil; se reporta el IC tal cual (incluido su ancho)
y se dice sin anestesia.

## Sanidades pre-registradas

1. Determinismo: dos corridas del control en la misma réplica dan el
   mismo número.
2. Bit-identidad: flags apagados == `correr_replica_param` en las
   réplicas nuevas (chequeo en 3 de ellas; ya probado en 0..4).

## Veredicto

`veredicto.md`: PASS/FAIL del skip con números, diagnóstico honesto y
decisión (conservar / podar / sin evidencia).
