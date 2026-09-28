# ALMA-EXP54 — Pre-registro (mock, US$0)

**Fecha:** 2026-09-27 ~16:00 EDT · **Serie:** "ideas orientales" (nueva serie; NO es reapertura de EXP45–52)
**Modo:** mock (US$0,00 — ninguna API key se toca)

## Hipótesis (una frase)

En los bloques con probe, gastar los items 3,4,5 en rollouts de consenso round-robin entre los dos brazos con mayor media del bandit post-probe y jugar greedy el ganador del consenso en los items Thompson restantes reduce el regret frente al Thompson post-probe de EXP51, porque el consenso compra identificación barata a mitad de bloque.

## Idea oriental testeada

TTRL — test-time learning (idea 6 del catálogo oriental): el modelo sigue aprendiendo durante la inferencia. Aquí, adaptación online **intra-bloque**: después del probe, la política re-muestrea los brazos candidatos en los primeros items del bloque y puede cambiar de brazo a mitad de bloque por voto de consenso, en vez de comprometerse con Thompson desde el item 3.

## Diseño

- **Mundo:** stream de 24 bloques bit-idéntico al de EXP47/49/51/53 (`run_experiment47.construir_stream`, seeds 45/47, namespace de RNG del oráculo `exp45-...`).
- **Control:** la política de EXP51 VERBATIM (`run_experiment51.correr_replica_probe_barato`, importada sin copiar): skip con umbral endurecido 2+floor(K/3) + probe adaptativo con gate Q1 + Thompson post-probe.
- **Tratamiento ("ttrl"):** COPIA VERBATIM del control, salvo UN moving part: el juego post-probe en bloques CON probe (los bloques saltados son idénticos al control — sin probe no hay candidatos que consensuar):

  1. **Candidatos:** top-2 brazos por media del bandit en el estado post-probe (prior + Q1 + recondicionamiento por skill; en el camino sin gate, las mediciones Q2 llegan después, igual que en el control). Desempate determinista: menor índice de brazo.
  2. **Consenso (reemplaza al Thompson de los items 3,4,5):** round-robin determinista c1, c2, c1. Cada jugada observa solo el brazo jugado (update del bandit + `rep_hist`, igual que cualquier jugada); el accounting ex-post de todos los brazos (`rew_fija`) sigue la convención del control. Los sorteos del oráculo usan el mismo namespace por (b,q,a): pareados con el control.
  3. **Voto:** m_c1 = media de c1 en {3,5}, m_c2 = reward de c2 en {4}. Ganador = media estrictamente mayor; empate → sin ganador (fallback).
  4. **Commit (reemplaza al Thompson restante):** si hay ganador, se juega greedy en los items Thompson que quedan (camino con gate: 6,7,8,9; camino sin gate: 8,9 — el re-probe Q2 6,7 es idéntico al control). Si no hay ganador, Thompson idéntico al control.
  5. **probe_obs:** idéntico al control (NO incluye las jugadas de consenso: son explotación post-probe, no probe). Q1/Q2 bit-idénticos. La cuenta de victorias de la skill no cambia de construcción.

- **RNG:** mismos namespaces que el control. En fallback a Thompson se usa el namespace `-sel` por (b,q) igual que el control (los sorteos de selección son los mismos objetos; las decisiones divergen legítimamente porque el estado del bandit difiere por las observaciones del consenso).
- **Réplicas:** 5 pareadas (mismo RNG que el control por réplica).

## Criterio PRE-REGISTRADO

- **efecto** = media sobre réplicas pareadas de `regret(ttrl) − regret(control-EXP51)`.
- **PASS ssi efecto < 0** (misma vara de refutación que toda la línea).
- Se reporta además (no cambia el veredicto): distancia a la mejor fija `d_trat` vs `d_ctrl` (en EXP53: 7,40 vs 2,20; en EXP51: 2,20 vs 3,80), tasa de commit (bloques con ganador del consenso / bloques con probe), accuracy del ganador del consenso vs mejor brazo ex-post en los items de commit, efecto sin la mejor réplica.

## Chequeo de reproducibilidad (pre-registrado)

El control debe ser bit-idéntico a la política probe-barato de EXP51, es decir, a su **tratamiento** (`reg_trat_bloques` de `resultados/exp51-20260927/report.json`, NO la columna del control skip-endurecido — lección de EXP53). Si no coincide, el experimento no es válido y no se interpreta.

## Nota de refutación

El riesgo es doble y pre-registrado: (1) 3 rollouts son ruidosos (el mundo tiene ~2/10 de ruido por bloque) → el consenso puede coronar al brazo equivocado con una muestra mínima; (2) el commit greedy abandona la exploración de Thompson → si el consenso se equivoca, el error se amplifica en 2–4 items en vez de diluirse. Si el efecto ≥ 0, la adaptación intra-bloque no compra nada en este mundo. El diagnóstico auxiliar dirime el modo de falla: si el ganador del consenso suele ser el mejor ex-post pero el greedy pierde igual → el problema es la explotación (Thompson explora mejor); si el consenso elige mal → el voto con 3 rollouts es demasiado ruidoso.

## Qué sigue según el resultado (pre-registrado)

- **Si PASS:** EXP55 = ablación del módulo TTRL con un moving part: ¿el valor está en el voto (identificación) o en el greedy (explotación)? Variante A: consenso + Thompson en los items restantes (solo identificación, sin commit). Variante B: commit greedy al top-2 del bandit SIN rollouts de consenso (solo explotación). Una variante por mock.
- **Si FAIL:** no se insiste con variantes intra-bloque. La serie "ideas orientales" pasa a la siguiente idea (candidatas: RSO/Darwin-Gödel —evolución del scaffold— o CodeAct). Para el sistema real: la adaptación en test-time no se prioriza sin más evidencia.

## Relación con la serie

EXP53 refutó el banco de skills versionado (SkillRL): efecto +5,20, FAIL en 4/5 réplicas, hueco a la mejor fija agrandado de 2,20 a 7,40. EXP54 testea la segunda idea oriental (TTRL, idea 6). La línea EXP45–52 sigue cerrada; esto es serie nueva con hipótesis distinta (adaptación intra-bloque, no representación de la memoria).
