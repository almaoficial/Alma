# ALMA-EXP59 — Pre-registro (mock, US$0)

**Fecha:** 2026-09-27 ~16:05 EDT · **Serie:** "ideas orientales" (cuarta idea; la serie RSO quedó archivada en EXP58)
**Modo:** mock (US$0,00 — ninguna API key se toca)

## Hipótesis (una frase)

En los bloques con probe, someter el veredicto de Q1 a un segundo rol verificador — el runner-up recibe 1 item focalizado de verificación y un verifier decide entre ganador-Q1 y challenger con la evidencia combinada — reduce el regret frente al probe de Q1 solo, porque la re-pregunta focalizada compra identificación donde Q1 fue ruidoso.

## Idea oriental testeada

SPELL (idea 3 del catálogo oriental, Alibaba Tongyi Lab + Sun Yat-sen University, ICLR 2026): un solo modelo asume los roles de questioner, responder y verifier, mejorándose por self-play multi-rol sin etiquetas. Aquí, los tres roles operan sobre el mismo probe de un bloque: Q1 propone (questioner), el runner-up recibe evidencia extra (challenger) y una regla explícita decide (verifier). Lo testeado es la *estructura multi-rol del probe*, no un verifier aprendido — no confundir con el SPELL real.

## Diseño

- **Mundo:** stream de 24 bloques bit-idéntico al de la serie (`run_experiment47.construir_stream`, seeds 45/47, namespace de RNG del oráculo `exp45-...`).
- **Control:** el scaffold evolucionado validado (EXP56/57, dos seeds): `SC_EVO = {n0:4, umbral_base:1, umbral_divisor:3, gate_margin:0.0, decay:0.5}` vía `run_experiment56.correr_replica_param` importado verbatim (sin copiar). Es el default actual del servicio (`alma_service/scaffold.py`).
- **Tratamiento ("spell"):** el control + UN moving part (el probe multi-rol). Todo lo demás — skip con umbral endurecido, gate Q1, Thompson, `probe_obs`, conteo de victorias de la skill — idéntico por construcción.

### Los tres roles (reglas exactas)

Bloque con probe (no saltado). Q1 (items 0,1,2) idéntico al control: se miden los 4 brazos, se juega `fav` (favorito del prior).

1. **Questioner (Q1 propone):** `mean_q1[a]` = media del brazo `a` en los 3 items de Q1. Orden de brazos por `(-mean_q1[a], -prior_mean[a], nombre)` — desempate determinista. `winner_q1` = primero, `runner_up` = segundo. (Generaliza a los 4 brazos la comparación que el gate ya hace para el brazo de la skill.)
2. **Challenger (re-pregunta focalizada):** el primer item Thompson post-Q1 (q=3) se sacrifica: en vez de la jugada de Thompson se juega el `runner_up`. Todos los brazos se miden igual que en `medir` (scoring honesto, mismo namespace de RNG por (b,q,a)); el reward jugado es el del challenger. El bandit, `rep_hist`, `rew_fija` y el clasificador se actualizan como en cualquier jugada medida.
3. **Verifier (decide con evidencia combinada):**
   - `r3_w`, `r3_c` = rewards medidos de `winner_q1` y `runner_up` en el item del challenger (full-information: `medir` mide todos los brazos).
   - `q1_wins_w` = cantidad de items de Q1 donde `rs_q1[q][winner_q1] > rs_q1[q][runner_up]` (estricto).
   - **Regla pre-registrada:** `chosen = runner_up` ssi `(r3_c > r3_w)` **y** `(q1_wins_w <= 1)`; en cualquier otro caso `chosen = winner_q1`. Es decir: el challenger gana ssi gana el item extra **y** Q1 no lo contradijo fuerte ("evidencia fuerte en contra" = el ganador de Q1 ganó ≥2 de los 3 items).
4. **Consecuencia (única):** en el camino sin gate, los items del re-probe Q2 (6,7) se juegan con `chosen` en vez de `fav`. En el camino con gate (Q2 saltado → Thompson en 6,7) el verifier se computa y se registra pero no tiene consecuencia de juego — documentado, no es un segundo moving part.

### RNG y determinismo

Mismos namespaces que el control (`exp45-r{rep}-b{b}-q{q}-{a}`). El item del challenger no consume el sorteo `-sel` de Thompson (no hay selección); las divergencias posteriores del Thompson son efecto legítimo del tratamiento (el estado del bandit difiere por la observación del challenger).

### Réplicas

5 pareadas (0–4), mismo RNG que el control por réplica.

## Criterio PRE-REGISTRADO

- **efecto** = media sobre réplicas pareadas de `regret(spell) − regret(control-EVO)`.
- **PASS ssi efecto < 0** (misma vara de refutación que toda la línea).
- Se reporta además (no cambia el veredicto): distancia a la mejor fija `d_trat` vs `d_ctrl`; **tasa de cambio del verifier** = bloques con probe donde `chosen == runner_up` / bloques con probe; **acierto del verifier** = entre bloques no-gate con cambio, fracción donde el challenger fue estrictamente mejor que `winner_q1` en los items Q2 (medidos full-information; se informan empates aparte); baseline Q1 = fracción de bloques no-gate donde `winner_q1` fue estrictamente mejor que el `runner_up` en Q2 (cuánto acertaba Q1 solo).

## Chequeos de reproducibilidad (pre-registrados)

1. El tratamiento con el módulo SPELL desactivado (`spell_on=False`) debe ser **bit-idéntico** a `e56.correr_replica_param(SC_EVO)` en las 5 réplicas. Si no coincide, el puerto no es fiel y el experimento no se interpreta.
2. Magnitudes: los regrets del control por réplica deben estar en el rango ~70–95 (consistente con EXP57: train V3 81,33, held-out [84, 81]).

## Nota de refutación

Riesgos pre-registrados: (1) 1 item extra es ruidoso (el mundo tiene ~2/10 de ruido por bloque) → el verifier puede coronar al challenger equivocado con una sola observación; (2) la regla "evidencia fuerte" puede hacer que el verifier casi nunca cambie (Q1 con 3 items binarios suele dar 2-1) → tasa de cambio ~0 y efecto nulo por construcción; (3) aun si el verifier acierta, solo mueve 2 items (Q2) por bloque → el techo del efecto es bajo. Si el efecto ≥ 0, el probe multi-rol no compra nada en este mundo.

## Qué se concluye si el verifier no supera al Q1 solo (pre-registrado)

- **Tasa de cambio < 10% o acierto ≤ 55%** → el veredicto de Q1 ya es la restricción vinculante: una re-pregunta focalizada no compra identificación en este mundo. Se archiva SPELL-para-probe; el valor del probe vive en la interacción gate↔skip (EXP51/52), no en afinar la adjudicación de Q1.
- **Acierto > 60% pero efecto ≥ 0** → el verifier identifica bien pero el efecto no alcanza: el problema está downstream (2 items de Q2 no pagan el costo del item sacrificado, o el gate/skip domina el regret).
- **PASS** → el probe multi-rol entra al scaffold como candidato, pendiente de replicación con otro seed antes de tocar el servicio real.

## Qué sigue según el resultado (pre-registrado)

- **Si PASS:** EXP60 = replicación con seed distinto del stream (o, si el acierto del verifier es alto pero el efecto es chico, variante con 2 items de verificación en vez de 1).
- **Si FAIL:** no se insiste con variantes del verifier. La serie "ideas orientales" pasa a la siguiente idea (candidatas restantes del catálogo: CodeAct, Infra Agent, destilación — las dos últimas son de sistema real, no de mock).

## Relación con la serie

EXP53 refutó SkillRL (+5,20). EXP54 dio PASS frágil a TTRL (−2,20, cargado por una réplica) y EXP55 lo diseccionó (FAIL+FAIL: el PASS fue fragilidad entre réplicas). EXP56/57 validaron el loop RSO como tuning (n0=4, umbral_base=1 load-bearing) y EXP58 refutó el proponente heurístico → serie RSO archivada. EXP59 testea la cuarta idea oriental (SPELL) sobre el scaffold ya evolucionado. La fase 1 real (FAIL) mostró que las skills como instrucciones no mueven al modelo: el probe sigue siendo donde vive el valor.
