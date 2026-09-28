# EXP65 — Veredicto: tuning del prior con memoria

**Fecha**: 2026-09-27. **Costo**: US$0 (mock). **Veredicto: FAIL**
(pre-registrado: efecto medio < 0 con IC95 sin cruzar 0; ningún
candidato pasó la puerta).

## Resultado

24 rondas RSO, **0 keeps**. Genoma final = genoma inicial
(`n0=4, decay=0.5, cond=completa`). Efecto medio 0,0, IC95 [0,0].
Sanidades OK: puerto bit-idéntico a `correr_replica_param` en 5/5
réplicas, determinista. Media del control en 5 réplicas: 81,80 —
idéntica a la de EXP64 (consistencia entre experimentos).

## Trayectoria (lo propuesto y por qué murió)

Ninguna mutación pasó la puerta de dos splits. Los casos ilustrativos:

- `n0 4→6` (5 propuestas): `d_in=+0,00` exacto, `d_ho=−3,50` — empate
  en held-in, peor en held-out. Rechazada.
- `decay 0.5→0.9` (3 propuestas): `d_in=+0,00`, `d_ho=−3,00`.
  Rechazada.
- `decay 0.5→0.3` (r21): `d_in=+0,33`, `d_ho=−1,00` — **trade-off**:
  mejora en held-in, empeora en held-out. La puerta la rechaza por
  diseño. Nótese: con la regla vieja de EXP56 (keep si mejora en
  train), esta mutación SE HABRÍA ADOPTADO. La puerta nueva es
  estrictamente más conservadora y acá mostró para qué existe.
- `cond completa→gruesa` / `→ninguna`: `d_in` entre −3,67 y −4,00,
  `d_ho` entre −2,50 y −5,00 — peores en ambos splits. El pooling
  jerárquico y el prior ciego no aportan nada sobre el condicionado
  exacto.
- `decay 0.5→1.0` (sin olvido): `d_in=−0,67`, `d_ho=−1,00` — el olvido
  carga peso; quitarlo empeora.

## Lectura

El FAIL es informativo, no vacío:

1. **El prior está en su óptimo local** bajo esta disciplina: ningún
   movimiento individual en el espacio pre-registrado mejora ambos
   splits a la vez.
2. **El +21,60 de EXP64 era el valor de TENER el prior con memoria,
   no de seguir tuneándolo.** El peso estaba donde no mirábamos —
   y resulta que ya estaba bien calibrado. No había más para exprimir
   en estos tres knobs.
3. **La puerta de dos splits funcionó como diseñada**: rechazó
   trade-offs que el RSO viejo habría adoptado (r21). El costo de esa
   disciplina es conservadurismo: con n=5 réplicas y empates exactos
   en held-in (`+0,00`), la puerta casi no deja pasar nada.

## Caveats

- n=5 réplicas, linaje único greedy, 24 rondas con propuestas al azar
  (algunas dimensiones se propusieron 5 veces, otras 1).
- La puerta expone el held-out a presión de selección (documentado en
  el pre-registro); el informe independiente queda en `benchmark.py`.
- "Óptimo local" ≠ "óptimo global": el espacio cubre un knob a la vez;
  interacciones entre knobs (p. ej. n0×decay) no se exploraron.

## Decisión

Se conserva el genoma del prior (`n0=4, decay=0.5, cond=completa`).
No hay tuning que adoptar. La línea de tuning del prior queda
**cerrada por criterio pre-registrado**: el mecanismo ya rinde lo que
rinde; la próxima mejora, si existe, no está en estos hiperparámetros.
