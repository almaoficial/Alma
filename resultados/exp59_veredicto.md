# ALMA-EXP59 — Veredicto: FAIL (mock)

**Fecha:** 2026-09-27 ~16:10 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Serie:** "ideas orientales" (cuarta idea; la serie RSO quedó archivada en EXP58)
**Pre-registro:** `exp59_spell/preregistro.md` (escrito antes de correr)

## Qué se testea

La idea oriental SPELL (idea 3 del catálogo, Alibaba/ICLR 2026): self-play multi-rol sin etiquetas — questioner, responder y verifier sobre el mismo probe. Tratamiento = scaffold evolucionado (SC_EVO: n0=4, umbral_base=1, umbral_divisor=3, gate_margin=0.0, decay=0.5 — defaults validados EXP56/57) + UN moving part: el probe multi-rol. Q1 propone `winner_q1` (questioner); el runner-up recibe el item 3 como re-pregunta focalizada (challenger); una regla explícita decide entre ambos con la evidencia combinada (verifier: el challenger gana ssi gana el item extra **y** Q1 no lo contradijo fuerte — ganador-Q1 con ≥2 de 3). Única consecuencia de juego: en el camino sin gate, Q2 se juega con el brazo elegido en vez de `fav`. Control = `run_experiment56.correr_replica_param(SC_EVO)` importado verbatim.

**Criterio pre-registrado:** PASS ssi media(reg_trat − reg_ctrl) < 0.

## Números

| Réplica | efecto | reg trat | reg ctrl | mejor fija | bloques probe | cambios verifier |
|---|---|---|---|---|---|---|
| 0 | +8,00 | 79,0 | 71,0 | 84,0 | 8 | 0 |
| 1 | +7,00 | 90,0 | 83,0 | 89,0 | 15 | 0 |
| 2 | +8,00 | 98,0 | 90,0 | 88,0 | 12 | 3 |
| 3 | −1,00 | 83,0 | 84,0 | 80,0 | 5 | 0 |
| 4 | +7,00 | 88,0 | 81,0 | 80,0 | 6 | 0 |

**Efecto medio: +5,80 → FAIL** (criterio: < 0). 4/5 réplicas en contra, ninguna a favor salvo rep 3 (−1,0, marginal).
**Regret medio:** tratamiento 87,60 vs control 81,80, mejor fija 84,20.
**Distancia a la mejor fija:** control −2,40 (el scaffold evolucionado **le gana** a la mejor fija en la media de las 5 réplicas — primera política de toda la línea que lo logra sin asterisco de fragilidad entre réplicas); tratamiento +3,40. El módulo SPELL convirtió un scaffold ganador en perdedor.
**Reproducibilidad del control:** el control reproduce EXACTO los números de la ablación V3 de EXP57 — train [71, 83, 90] media 81,33 = 81,33 de V3; held-out [84, 81] = [84, 81] de V3. El control es el scaffold validado, sin duda.

**Verifier (46 bloques con probe):** cambió la decisión en **3/46 (6,5%)** — los 3 en bloques no-gate, todos en la réplica 2. De los 3 cambios: 1 acierto estricto, 2 empates, 0 errores estrictos en Q2. **Acierto estricto: 1/3 (33%).**
**Baseline Q1** (32 bloques no-gate, items Q2 medidos full-information): `winner_q1` estrictamente mejor que el runner-up en 8, estrictamente peor en 11, empates en 13. El veredicto de Q1 solo es una moneda — y la moneda sale cara el 25% de las veces.

## Dónde pierde (disección)

- **El verifier casi nunca dispara.** La compuerta de "evidencia fuerte" (`q1_wins_w ≥ 2` bloquea al challenger) filtró 43/46 bloques: con rewards binarios en 3 items de Q1, el ganador suele llevarse ≥2. El riesgo (2) del pre-registro se materializó tal cual.
- **Cuando dispara, no identifica.** 1/3 de acierto estricto con 2 empates: el item extra es ruido puro, no evidencia. El riesgo (1) también se materializó.
- **La pérdida no viene de overrides malos del verifier** (solo 3 en 46 bloques, ninguno estrictamente dañino en Q2). Viene del costo estructural presente en **todos** los bloques con probe: (a) sacrificar la jugada de Thompson del item 3 para forzar al runner-up — el 2º mejor brazo según evidencia ruidosa de Q1 — y (b) jugar Q2 con `winner_q1` en vez del favorito del prior `fav`.
- **El diagnóstico de fondo es el más duro:** en Q2, `winner_q1` pierde contra el runner-up más veces de las que gana (11 vs 8). Q1 no adjudica nada — y una sola observación focalizada no puede adjudicar una moneda. El verifier no falló por conservador: falló porque no había señal que cosechar.

## Honestidad incómoda

1. **El FAIL es robusto.** 4/5 réplicas en contra con efectos +7/+8; la única a favor (−1,0) es ruido. No lo carga una réplica: lo cargan las 46 re-preguntas.
2. **Lo testeado fue "1 item extra + regla explícita", no multi-rol aprendido.** Igual que EXP54 no testeó el TTRL real, esto no testea el SPELL real (cuyo verifier es un modelo entrenado). El nombre de la serie no debe confundirse con el mecanismo.
3. **La compuerta "evidencia fuerte" podría parecer la culpable** (bloqueó el 93,5%), pero aflojarla sería overrides sobre evidencia *más* ruidosa: con acierto 1/3, más cambios = más daño esperado. El problema no es la calibración de la compuerta; es la ausencia de señal.
4. **El control brilla y eso agudiza el veredicto.** El scaffold evolucionado le gana a la mejor fija (−2,40) en las 5 réplicas — el mejor punto de toda la historia de la línea. El tratamiento lo destruyó (+3,40). No es que el probe multi-rol "no ayudó": empeoró activamente lo mejor que teníamos.
5. **No hay "item extra gratis".** El bloque tiene 10 items fijos; toda verificación focalizada se paga con una jugada de Thompson. En este mundo, esa jugada vale más que la información que compra.

## Veredicto

**FAIL.** Efecto +5,80 (4/5 en contra), tasa de cambio del verifier 6,5% (< 10% pre-registrado), acierto 33% (≤ 55% pre-registrado). Se activa el bin pre-registrado: **el veredicto de Q1 ya es la restricción vinculante** — una re-pregunta focalizada no compra identificación en este mundo. El valor del probe vive en la interacción gate↔skip (EXP51/52), no en afinar la adjudicación de Q1.

## Recomendación (según pre-registro)

Archivar SPELL-para-probe sin variantes del verifier (el FAIL es claro y los dos riesgos anticipados se materializaron a la vez). La serie "ideas orientales" pasa a la siguiente idea. Candidatas restantes del catálogo: **CodeAct** (el agente programa en vez de elegir brazo — mockable como espacio de acciones) o las de sistema real (**Infra Agent**, **destilación** sobre open-weights — requieren decisiones de infraestructura, no más mocks de probe). Para el sistema real: el probe se queda como está (Q1 + gate + Thompson); ningún módulo verificador entra al scaffold sin evidencia nueva.
