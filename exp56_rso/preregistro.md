# ALMA-EXP56 — Pre-registro (mock, US$0)

**Fecha:** 2026-09-27 ~16:10 EDT · **Serie:** "ideas orientales" (EXP53 SkillRL refutado, EXP54/55 TTRL archivado)
**Modo:** mock (US$0,00 — ninguna API key se toca)

## Hipótesis (una frase)

Un loop greedy de auto-optimización recursiva del scaffold estilo MiniMax (linaje único: proponer UNA mutación de hiperparámetros por ronda → evaluar en benchmark fijo → keep si mejora, revert si no) encuentra un scaffold de la política de probe mejor que el tunning manual de EXP51, medido en réplicas held-out que el loop nunca vio.

## Idea oriental testeada

RSO estilo MiniMax M2.7 (idea 1 del catálogo oriental): el modelo optimizó su propio scaffold de coding en 100+ rondas con 30% de mejora — el loop evoluciona CÓDIGO del scaffold, no pesos. Aquí se testea la maquinaria keep/revert en miniatura: el "scaffold" = los hiperparámetros de la política de probe de EXP51.

## El scaffold y el espacio de mutación (explícito y acotado)

El scaffold a evolucionar es la política probe-barato de EXP51 con 5 hiperparámetros:

| # | Parámetro | Valor inicial (EXP51) | Espacio de mutación | Qué controla |
|---|-----------|----------------------|---------------------|--------------|
| 1 | `umbral_base` | 2 | {1, 2, 3} | base del umbral de skip: umbral(K) = base + floor(K/div) |
| 2 | `umbral_divisor` | 3 | {2, 3, 4, 6} | velocidad de endurecimiento con el horizonte K |
| 3 | `gate_margin` | 0.0 | {0.0, 0.05, 0.10} | margen exigido en q1_decisivo: m_s > m_a + margin ∀a≠s |
| 4 | `n0` | 2 | {1, 2, 4} | fuerza del prior warm de Thompson |
| 5 | `decay` | 0.5 | {0.25, 0.5, 0.75} | olvido del prior: decay^d |

Total: 3×4×3×3×3 = 324 combinaciones. Todo lo demás (stream, oráculo, posiciones de probe Q1=(0,1,2)/Q2=(6,7), Thompson, firma, skill_arm) queda congelado.

## El loop (greedy, linaje único, como MiniMax)

- **N = 24 rondas.**
- Ronda r: se propone UNA mutación = elegir un parámetro al azar y cambiarlo a otro valor aleatorio de su espacio (distinto del actual). RNG de propuestas dedicado `random.Random(56)`, independiente del RNG de evaluación → el experimento es reproducible bit a bit.
- **Evaluación:** regret medio del scaffold mutante en el split de entrenamiento (réplicas [0,1,2]). La evaluación es determinista (mismo scaffold + mismas réplicas = mismo número), así que la regla keep/revert es limpia.
- **Keep** ssi métrica(mutante) < métrica(actual) estricto. Si no, revert (se descarta la mutación).
- El scaffold inicial es el de EXP51.

## Benchmark y splits (anti-Goodhart)

- **Mundo:** stream de 24 bloques bit-idéntico al de EXP47/49/51 (`run_experiment47.construir_stream`, seeds 45/47, namespace de RNG del oráculo `exp45-...`).
- **Split train (lo ve el loop):** réplicas [0, 1, 2] — keep/revert se decide acá.
- **Split held-out (el loop NUNCA lo ve):** réplicas [3, 4] — solo medición final. Mismo mundo, distinto ruido del oráculo (el namespace incluye el id de réplica).

## REGLA DE ORO (del estudio MiniMax, vinculante)

**El loop NUNCA edita al validador.** Congelados fuera del espacio de mutación: el oráculo mock (`tasas.json`), el stream (`construir_stream`), el cómputo de regret, las réplicas held-out [3,4], el código del evaluador y el código del propio loop de evolución (una sola capa de recursión, como corresponde a un mock). Las mutaciones tocan SOLO los 5 hiperparámetros de la política.

## Chequeo de sanidad (pre-registrado, antes del loop)

El puerto parametrizado de EXP51 con parámetros iniciales debe reproducir **bit-idéntico** el tratamiento de EXP51: `reg_tratamiento` por réplica == [78.0, 86.0, 93.0, 95.0, 80.0] (de `resultados/exp51-20260927/report.json`). Si no coincide, el experimento no es válido y no se corre el loop.

## Criterio final PRE-REGISTRADO

- **PASS** ssi `media_heldout(evolucionado) < media_heldout(inicial)`, donde media_heldout = regret medio en réplicas [3,4].
- Se reporta además (no cambia el veredicto): trayectoria completa de rondas (ronda, mutación, keep/revert, métrica), mejora en train (esperada por construcción), scaffold final vs inicial, per-réplica en held-out, y el chequeo Goodhart: ¿la mejora en train se transfiere a held-out?

## Interpretación pre-registrada (vinculante)

- **PASS** → el loop RSO encontró un scaffold mejor en datos no vistos durante la evolución: evidencia (en mock) de que la auto-optimización recursiva aporta sobre el tuning manual. Siguiente: ablación de qué dimensión aportó, y escalar N / llevar el loop al sistema real.
- **FAIL con mejora en train pero no en held-out** → Goodhart confirmado: el loop sobreajustó al split de entrenamiento. Lección: RSO necesita validación held-out real y/o más réplicas; el keep/revert es vulnerable al ruido del benchmark.
- **FAIL sin mejora ni en train** → el espacio no contiene mejoras alcanzables en 24 rondas greedy, o el scaffold EXP51 ya está en un óptimo local de este espacio.

## Nota de refutación / honestidad pre-registrada

MiniMax usa un LLM que **analiza fallos y propone cambios de código**; este mock usa **propuestas aleatorias sobre 5 hiperparámetros**. Lo testeado es la maquinaria keep/revert + la pregunta "¿hay mejores hiperparámetros que los manuales?", NO la inteligencia del proponente. Consecuencias:
- Si el loop con propuestas aleatorias NO mejora → no refuta al RSO real (que propone con análisis de fallos). Solo dice que 24 rondas aleatorias no bastaron.
- Si mejora → sugiere que el espacio tenía margen que el tuning manual dejó en la mesa; no prueba que un proponente inteligente mejore más.
- El split held-out es delgado (2 réplicas): un PASS/FAIL por <1 punto es ruido, no señal. El veredicto debe leerse con el margen.

## Qué sigue según el resultado (pre-registrado)

- **Si PASS:** EXP57 = ablación del scaffold evolucionado (¿qué dimensión aportó? ¿el resto es lastre?) + repetir la evolución con otro seed de propuestas para ver si converge al mismo scaffold.
- **Si FAIL (Goodhart):** EXP57 = RSO con validación cruzada interna (keep/revert sobre 4 réplicas, 1 de validación rotante) para ver si el guardrail repara el sobreajuste.
- **Si FAIL (sin mejora):** la serie oriental pasa a la siguiente idea (SPELL para el probe). El RSO queda archivado en este espacio/régimen.
