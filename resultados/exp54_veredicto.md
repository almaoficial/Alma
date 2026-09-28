# ALMA-EXP54 — Veredicto: PASS frágil (mock)

**Fecha:** 2026-09-27 ~16:10 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Serie:** "ideas orientales" (nueva; no reapertura de EXP45–52)
**Pre-registro:** `exp54_ttrl/preregistro.md` + `resultados/exp54-20260927/preregistro.json` (escritos antes de correr)

## Qué se testea

La idea oriental TTRL (idea 6 del catálogo): test-time learning — adaptación online intra-bloque. Tratamiento = política de EXP51 verbatim + UN moving part: en bloques con probe, los items 3,4,5 se juegan como rollouts de consenso round-robin (c1,c2,c1) entre los dos brazos con mayor media del bandit post-probe; el ganador del voto (media estrictamente mayor; empate → fallback) se juega greedy en los items Thompson restantes (gate: 6,7,8,9; sin gate: 8,9). Q1, Q2, gate, skip y probe_obs: idénticos al control por construcción. Bloques saltados: idénticos.

**Criterio pre-registrado:** PASS ssi media(reg_trat − reg_ctrl) < 0.

## Números

| Réplica | efecto | reg trat | reg ctrl | mejor fija | commits (acierto ex-post) | Q2 trat/ctrl | skips trat/ctrl |
|---|---|---|---|---|---|---|---|
| 0 | −10,00 | 68,0 | 78,0 | 84,0 | 11 (7) | 4 / 3 | 5 / 5 |
| 1 | +10,00 | 96,0 | 86,0 | 89,0 | 18 (7) | 6 / 8 | 0 / 0 |
| 2 | −1,00 | 92,0 | 93,0 | 88,0 | 18 (4) | 3 / 3 | 0 / 2 |
| 3 | −12,00 | 83,0 | 95,0 | 80,0 | 13 (9) | 3 / 3 | 7 / 6 |
| 4 | +2,00 | 82,0 | 80,0 | 80,0 | 18 (11) | 4 / 3 | 5 / 5 |

**Efecto medio: −2,20 → PASS** (criterio: < 0).
Media sin la mejor réplica (rep 3, −12,00): **+0,25** → el PASS lo carga una sola réplica; 2/5 en contra.
**Regret medio:** tratamiento 84,20 vs control 86,40, mejor fija 84,20.
**Distancia a la mejor fija:** tratamiento 0,00 vs control 2,20 — el tratamiento **empata** a la mejor fija en la media (primera vez en toda la línea).
**Reproducibilidad del control vs tratamiento de EXP51:** bit-idéntico (True).

**TTRL (5 réplicas):** consenso en 103 bloques con probe; commits 78 (tasa 75,7%), fallbacks a Thompson 25. Ganador del consenso = mejor brazo ex-post en los items de commit: **38/78 (48,7%)**.

## Disección

- **El voto es una moneda.** El consenso acierta el mejor brazo ex-post el 48,7% de las veces — indistinguible de azar. Con 3 rollouts en un mundo con ~2/10 de ruido por bloque, el voto no identifica nada.
- **Pero la accuracy del voto no predice el efecto.** Rep 4: 11/18 aciertos (61%) y pierde (+2,0). Rep 2: 4/18 aciertos (22%) y gana (−1,0). El mecanismo no es "el consenso elige bien".
- **Hay efecto downstream real.** El tratamiento cambia Q2-saltados (rep 0: 4/3, rep 1: 6/8) y skips (rep 2: 0/2) respecto al control: las jugadas de consenso/commit alteran `rep_hist` → cambian `skill_arm_actual`, el soporte del skip y el disparo del gate en bloques posteriores. Parte del efecto vive en esa interacción, como pasó en EXP51 con el gate.
- **La lectura más parsimoniosa:** el valor —donde lo hay— parece estar en el **commit greedy** (ahorrar el costo de exploración de Thompson en 2–4 items), no en la identificación del voto. Pero con el voto al 48,7%, el greedy también amplifica errores (rep 1: +10,0 con 7/18 aciertos).

## Honestidad incómoda

1. **El PASS es frágil por construcción del criterio.** Sin la rep 3 el efecto es +0,25 (FAIL). Dos réplicas en contra (+10, +2), una casi neutra (−1). La media −2,2 no describe a "la política típica": describe un promedio tironeado por un extremo.
2. **El empate con la mejor fija (0,00) es el titular más lindo y el menos confiable.** Primera vez que una política no pierde contra la mejor fija — pero viene del mismo promedio cargado por la rep 3. No es un techo roto; es varianza.
3. **El diagnóstico pre-registrado quedó a medio responder.** La pregunta era: ¿falla por explotación (greedy peor que Thompson) o por identificación (voto ruidoso)? El voto ES ruidoso (48,7%), pero la accuracy no explica el signo del efecto por réplica. El mecanismo real incluye el downstream sobre skills/gate, que este mock no aísla.
4. **No hay evidencia de que "aprender en test-time" funcione aquí.** Lo que se testeó fue un voto de 3 rollouts + commit greedy, no aprendizaje de pesos (el TTRL real). El nombre de la serie no debe confundirse con el mecanismo testeado.

## Veredicto

**PASS por el criterio pre-registrado (−2,20 < 0), con el asterisco grande de que lo carga una sola réplica y el voto es una moneda (48,7%).** No es una validación de TTRL: es una señal ruidosa de que el commit greedy post-consenso a veces ahorra más exploración de la que cuesta.

## Recomendación (según pre-registro)

La ablación pre-registrada (EXP55) es ahora obligatoria antes de cualquier conclusión: ¿el valor está en el voto o en el greedy? Variante A: consenso + Thompson en los items restantes (solo identificación, sin commit). Variante B: commit greedy al top-2 del bandit SIN rollouts (solo explotación). Una variante por mock. Si ninguna variante mueve el perfil, la adaptación intra-bloque se archiva como la SkillRL: idea interesante, mundo que no la compra.
