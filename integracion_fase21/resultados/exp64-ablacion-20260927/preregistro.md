# EXP64 — Pre-registro: ablación del scaffold estilo Cherny

**Fecha**: 2026-09-27. **Costo**: US$0 (mock). **Escrito ANTES de correr.**

## Pregunta

Del scaffold evolucionado (n0=4, umbral_base=1, umbral_divisor=3, decay=0.5,
gate adaptativo, skip con soporte, probe Q1/Q2, prior condicionado a firma),
¿qué componentes cargan peso de verdad y cuáles son decoración?
Cherny: pelar al mínimo y medir qué se rompe.

## Tratamientos (réplicas [0..4], pareadas por rep_id — mismo RNG en todos)

Implementación de referencia: `exp56_rso/run_experiment56.py`
(`correr_replica_param`, mundo y validador congelados).

- **(a) control**: `correr_replica_param` con `DEFAULT_SCAFFOLD`
  (`alma_service/scaffold.py`). Es la implementación de referencia misma,
  no una copia: bit-identidad por construcción. Chequeo de sanidad:
  determinismo (dos corridas del control dan números idénticos).
- **(b) sin prior condicionado**: el bandit nunca se reconstruye con la
  firma del régimen; prior siempre ciego (con historia decaída, n0=4).
  El gate adaptativo sigue pudiendo disparar sobre Q1 (componente separada).
- **(c) sin skip del probe**: `saltar=False` siempre; se mide todo.
- **(d) sin gate adaptativo Q1**: `gate=False` siempre; Q2 siempre re-probe.
- **(e) sin probe (Thompson pelado)**: sin Q1/Q2, sin skip, sin gate, sin
  maquinaria de skills. Thompson sobre los 10 items con prior ciego
  (historia decaída, n0=4).
- **(f) mínimo total**: Thompson con prior UNIFORME (n0=0 → Beta(1,1),
  sin historia) y sin ninguna maquinaria del scaffold.

**Desvío honesto del diseño original**: el task pedía (f) = b+c+d+e, pero
eso es operacionalmente idéntico a (e) (sin probe, el resto no tiene sobre
qué actuar). Para que (f) sea un tratamiento real se define como el piso
absoluto: prior uniforme + nada. (e) aísla "toda la maquinaria del probe";
(f) aísla además "el prior con memoria".

## Métrica

Regret total por réplica. Efecto por ablación X:
`d_r = reg_X(r) − reg_control(r)`, r = 0..4.
Efecto medio `d̄` con IC95 t-pareado (t=2.776, gl=4). d̄ > 0 = quitar
empeora (el componente cargaba peso).

## Criterio pre-registrado

Una componente es **load-bearing** ssi se cumplen las tres:
1. d̄ > 0 (quitarla empeora en media),
2. el IC95 de d̄ NO cruza el 0,
3. d_r > 0 en ≥4/5 réplicas.

Si quitarla MEJORA (d̄ < 0 con IC95 sin cruzar el 0): la componente es
nociva → se poda. Si nada es load-bearing individualmente pero (f)
empeora con IC95 sin cruzar el 0: el valor está en la **interacción**.
Si ni (f) empeora: el scaffold completo no le gana al mínimo — se dice
sin anestesia y se poda todo lo no load-bearing.

## Veredicto

`veredicto.md`: PASS/FAIL por componente con números, diagnóstico,
qué se conserva y qué se poda.
