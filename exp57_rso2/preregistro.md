# ALMA-EXP57 — Pre-registro (mock, US$0)

**Fecha:** 2026-09-27 ~16:01 EDT · **Serie:** "ideas orientales" (RSO estilo MiniMax)
**Modo:** mock (US$0,00 — ninguna API key se toca)
**Predecesor:** EXP56 PASS — loop greedy (24 rondas, 1 mutación/ronda,
keep/revert estricto en train [0,1,2], RNG de propuestas seed 56) encontró el
scaffold `{umbral_base:1, umbral_divisor:2, gate_margin:0.0, n0:4, decay:0.5}`
con mejora held-out **+4.50** ([3,4]: 87.50 → 83.00; por réplica [95,80] →
[86,80]). Keeps: r06 n0 2→4, r10 umbral_base 2→1, r14 umbral_divisor 3→2.

## Hipótesis (una frase por parte)

- **A (ablación):** la mejora +4.50 no está concentrada en una sola dimensión;
  las tres mutaciones contribuyen y ninguna es lastre puro.
- **B (convergencia):** el efecto RSO replica con otro seed de propuestas
  (mejora held-out > 0), aunque el scaffold final puede ser un óptimo local
  distinto.

## Regla de oro (heredada de EXP56, vinculante)

El loop / la medición NUNCA editan al validador: oráculo, stream, cómputo de
regret, réplicas held-out [3,4] y evaluador congelados. Solo se evalúan
scaffolds (5 hiperparámetros) ya fijados.

## Parte A — ablación (medición, no optimización)

Variantes de un-solo-revert sobre el scaffold evolucionado EVO:

| Variante | Scaffold |
|---|---|
| EVO | {ub:1, ud:2, gm:0.0, n0:4, decay:0.5} |
| V1 (revert n0) | {ub:1, ud:2, gm:0.0, n0:**2**, decay:0.5} |
| V2 (revert umbral_base) | {ub:**2**, ud:2, gm:0.0, n0:4, decay:0.5} |
| V3 (revert umbral_divisor) | {ub:1, ud:**3**, gm:0.0, n0:4, decay:0.5} |

Se mide regret medio en train [0,1,2] y held-out [3,4] para INIT, EVO, V1, V2,
V3 (misma maquinaria `correr_replica_param` de EXP56, importada, no copiada).

- Contribución marginal de la dimensión d:
  Δ_d = mejora_heldout(EVO) − mejora_heldout(V_d)
      = media_ho(V_d) − media_ho(EVO),
  donde mejora_heldout(X) = media_ho(INIT) − media_ho(X). (mejora(EVO) = +4.50
  por EXP56; se re-mide igual como chequeo de consistencia.)
- **Interpretación vinculante:**
  - Si algún Δ_d ≥ 3.0 → esa dimensión es *load-bearing* (carga ≥ 2/3 de la
    mejora); el "RSO" se reduce en gran parte a "el tuning manual erró ese
    parámetro".
  - Si todos los Δ_d < 1.5 → mejora *distribuida/redundante* entre dimensiones.
  - En el medio → contribución parcial; se reporta el orden de Δ_d.
  - Si mejora_heldout(V_d) < 0 → el keep era activamente protector (sin él se
    queda *peor* que el scaffold manual).
- **Caveats pre-registrados:** (1) held-out n=2 es delgado — el orden estable se
  lee en train [0,1,2]; held-out confirma dirección. (2) La ablación mide el
  efecto marginal *condicional* a los otros dos keeps, no el efecto
  independiente de cada dimensión (el orden de los keeps en el loop greedy
  importa).

## Parte B — convergencia / replicación con otro seed

Repetir el loop RSO completo con el **mismo protocolo** (24 rondas, 1 mutación
propuesta por ronda, keep ssi mejora estricta en train [0,1,2], medición final
en held-out [3,4] que el loop nunca ve) pero **RNG de propuestas seed 57**
(distinto de 56). Implementación: reutilizar `proponer`/`evaluar` de EXP56 por
importación; el loop se reescribe en este experimento.

- **Chequeo de validez (pre-registrado, ANTES de interpretar B):** re-correr el
  loop con seed 56 debe reproducir la trayectoria de EXP56 **bit-idéntica**
  (3 keeps: r06 n0 2→4, r10 ub 2→1, r14 ud 3→2; scaffold final idéntico;
  train 79.33; held-out 83.00). Si no coincide, el harness de este experimento
  no es válido y B no se interpreta.
- **Criterio de replicación:** PASS_B ssi
  media_heldout(evo_B) < media_heldout(INIT) (= 87.50). Mismo criterio que
  EXP56.
- **Convergencia:** ¿scaffold_final_B == scaffold_EXP56? Se reportan scaffold
  final, keeps y trayectoria de B.
- **Interpretación vinculante:**
  - PASS_B + mismo scaffold (o vecino a 1 mutación) → el efecto replica y el
    óptimo es robusto al orden de propuestas.
  - PASS_B + scaffold distinto → el mecanismo replica pero es *path-dependent*
    (óptimos locales distintos); la dirección se confirma si los keeps de B
    van en la misma dirección ("más confianza en la skill, menos probe").
  - FAIL_B → el PASS de EXP56 fue *suerte de un seed* (path-luck); el RSO con
    propuestas aleatorias no replica. Consecuencia: EXP56 se rebaja a "un seed
    tuvo suerte"; la serie NO sigue con más seeds aleatorios — pasa a
    proponente con análisis de fallos (miniatura) o a N mayor con guardrail.
- **Caveat pre-registrado:** held-out [3,4] ya se usó para el veredicto de
  EXP56 (comparación múltiple leve). Para el loop de B sigue siendo no visto,
  así que la medición es válida, pero el umbral se lee con cautela.

## Qué sigue según el resultado (pre-registrado)

- Si A muestra una dimensión load-bearing **y** B replica → fijar esa dimensión
  como default en el sistema real; el "loop" aportó tuning, no emergencia.
- Si B no replica → archivar RSO-aleatorio; EXP58 = proponente que analiza
  fallos (aunque sea heurístico) o N=24→96 con el mismo seed 56 para ver si el
  óptimo local se mueve.
- Si B replica con scaffold distinto → EXP58 = intersección de scaffolds
  (¿qué dimensiones coinciden entre seeds?) o ensemble de scaffolds.

## Nota de honestidad pre-registrada

Lo testeado sigue siendo keep/revert con propuestas aleatorias, no el RSO real
de MiniMax (proponente LLM que analiza fallos y edita código). Un FAIL_B no
refuta al RSO real; solo dice que 24 rondas de propuestas aleatorias no
replican de forma estable. Un PASS_B no prueba que un proponente inteligente
replicaría mejor.
