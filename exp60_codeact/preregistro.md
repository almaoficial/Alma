# ALMA-EXP60 — Pre-registro (mock, US$0)

**Fecha:** 2026-09-27 ~16:10 EDT · **Serie:** "ideas orientales" (quinta y última idea mockable; la serie RSO quedó archivada en EXP58)
**Modo:** mock (US$0,00 — ninguna API key se toca)

## Hipótesis (una frase)

En bloques con probe donde el prior no es decisivo, componer un schedule que reparte los 5 slots comprometidos del bloque (Q1=0,1,2 y Q2=6,7) entre los dos mejores brazos del prior — en vez de jugar el favorito en los 5 — reduce el regret, porque el favorito del prior es ruidoso y la composición compra cobertura donde el compromiso único apuesta todo a una moneda.

## Idea oriental testeada

CodeAct (idea 10 del catálogo oriental, Manus/Butterfly Effect, China): en vez de elegir una acción fija de un catálogo, el agente compone programáticamente su curso de acción. Aquí, la "composición" se instancia como: por bloque, elegir una plantilla (secuencia corta de brazos) con una regla explícita sobre la evidencia del prior. Lo testeado es la *estructura componer-vs-elegir sobre slots comprometidos*, no un agente que escribe código — no confundir con el CodeAct real.

## Diseño

- **Mundo:** stream de 24 bloques bit-idéntico al de la serie (`run_experiment47.construir_stream`, seeds 45/47, namespace de RNG del oráculo `exp45-...`).
- **Control:** el scaffold evolucionado validado (EXP56/57, dos seeds): `SC_EVO = {n0:4, umbral_base:1, umbral_divisor:3, gate_margin:0.0, decay:0.5}` vía `run_experiment56.correr_replica_param` importado verbatim (sin copiar). Es el default actual del servicio (`alma_service/scaffold.py`).
- **Tratamiento ("codeact"):** el control + UN moving part (composición por plantillas). Todo lo demás — skip con umbral endurecido, camino de probe saltado, gate Q1, Thompson en sus slots, `medir` con scoring full-information, `probe_obs`, conteo de victorias de la skill — idéntico por construcción. La medición alimenta al bandit con todos los brazos igual que en el control; lo único que cambia es **qué brazo se juega** en cada slot comprometido.

### Plantillas (pre-registradas)

Slots comprometidos en orden: (0,1,2,6,7). `W` = favorito del prior (skill-free, el mismo `fav` del control), `R` = runner-up del prior (desempate determinista por nombre).

| id | nombre | schedule |
|---|---|---|
| T0 | solo | [W,W,W,W,W] |
| T1 | confianza | [W,W,W,W,R] |
| T2 | mixta | [W,W,R,W,R] |
| T3 | duelo | [W,R,W,R,W] |

### Regla de elección (pre-registrada)

`gap` = mean_prior(W) − mean_prior(R). Umbrales **calibrados sobre la distribución de gaps del control** (sanity run con `codeact_on=False`, bit-idéntico al control; no se observó ningún resultado del tratamiento — solo cuántos bloques caerían en cada plantilla):

- `gap ≥ 0.15` → T0 (con este umbral, el bloque es bit-idéntico al control)
- `0.08 ≤ gap < 0.15` → T1
- `0.03 ≤ gap < 0.08` → T2
- `gap < 0.03` → T3

Uso esperado sobre los 46 bloques con probe del control: T0=8, T1=10, T2=12, T3=16.

En el camino con gate, los slots Q1 usan la plantilla y Q2 se juega con Thompson (idéntico al control) — la plantilla no toca el gate.

## Criterio PRE-REGISTRADO

- **efecto** = media sobre réplicas pareadas de `regret(codeact) − regret(control-EVO)`.
- **PASS ssi efecto < 0** (misma vara de refutación que toda la línea).
- Se reporta además (no cambia el veredicto): distancia a la mejor fija `d_trat` vs `d_ctrl`; **frecuencia de uso de cada plantilla** en bloques con probe; efecto condicionado a bloques con mezcla (T1/T2/T3) como diagnóstico.

## Chequeos de reproducibilidad (pre-registrados)

1. El tratamiento con el módulo desactivado (`codeact_on=False`, plantilla forzada a `[fav]*5`) debe ser **bit-idéntico** a `e56.correr_replica_param(SC_EVO)` en las 5 réplicas. Si no coincide, el puerto no es fiel y el experimento no se interpreta. (Ya verificado en la calibración: OK en 5/5.)
2. Magnitudes: los regrets del control por réplica deben estar en el rango ~70–95 (consistente con EXP57/59).

## Nota de refutación

Riesgos pre-registrados: (1) el gap del prior es ruidoso — la plantilla "mixta" puede repartir slots hacia un R que es peor que W de verdad, comprando cobertura que no existe; (2) si el prior suele ser decisivo, T0 domina y el tratamiento ≈ control → efecto ~0 por construcción (test vacuo); (3) el techo del efecto es bajo: solo cambian los slots comprometidos de bloques con probe no-decisivos. Si el efecto ≥ 0, componer no compra nada frente a elegir en este mundo.

## Qué se concluye según el resultado (pre-registrado)

- **PASS** → la composición por plantillas entra al scaffold como candidata, pendiente de replicación con otro seed antes de tocar el servicio real.
- **FAIL** → se archiva CodeAct-para-probe. **La serie mock de ideas orientales se cierra acá**: era la quinta y última idea mockable del catálogo. Las restantes (Infra Agent, destilación/post-training scaling, MoE de baja activación, observabilidad, co-diseño) son decisiones de sistema real, no de mock de probe — y CodeAct-real (agente que programa) es arquitectura del servicio, no un parámetro del probe.

## Relación con la serie

EXP53 refutó SkillRL-banco (+5,20). EXP54 dio PASS frágil a TTRL y EXP55 lo diseccionó (FAIL+FAIL: fragilidad entre réplicas). EXP56/57 validaron el loop RSO como tuning (n0=4, umbral_base=1 load-bearing, integrados al servicio) y EXP58 refutó el proponente heurístico → serie RSO archivada. EXP59 archivó SPELL-para-probe (FAIL +5,80; el verifier casi nunca dispara y cuando lo hace no identifica). EXP60 testea la última idea mockable: CodeAct.
