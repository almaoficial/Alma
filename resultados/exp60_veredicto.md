# ALMA-EXP60 — Veredicto: FAIL (mock)

**Fecha:** 2026-09-27 ~16:12 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Serie:** "ideas orientales" (quinta y última idea mockable; la serie RSO quedó archivada en EXP58)
**Pre-registro:** `exp60_codeact/preregistro.md` (escrito antes de correr; umbrales de gap calibrados sobre la distribución de gaps del control, sin observar resultados del tratamiento)

## Qué se testea

La idea oriental CodeAct (idea 10 del catálogo, Manus/Butterfly Effect, China): componer programáticamente el curso de acción en vez de elegir una acción fija. Tratamiento = scaffold evolucionado (SC_EVO: n0=4, umbral_base=1, umbral_divisor=3, gate_margin=0.0, decay=0.5 — defaults validados EXP56/57) + UN moving part: en bloques con probe, los 5 slots comprometidos (Q1=0,1,2 y Q2=6,7) se juegan con una plantilla elegida por regla explícita sobre el gap del prior (T0 solo / T1 confianza / T2 mixta / T3 duelo, umbrales 0.15/0.08/0.03), en vez de jugar el favorito en los 5. Control = `run_experiment56.correr_replica_param(SC_EVO)` importado verbatim. La medición es full-information en ambos: el estado de información (bandit, rep_hist, probe_obs) evoluciona idéntico; lo único que cambia es qué brazo se juega por slot.

**Criterio pre-registrado:** PASS ssi media(reg_trat − reg_ctrl) < 0.

## Números

| Réplica | efecto | reg trat | reg ctrl | mejor fija |
|---|---|---|---|---|
| 0 | +2,00 | 73,0 | 71,0 | 84,0 |
| 1 | −1,00 | 82,0 | 83,0 | 89,0 |
| 2 | −2,00 | 88,0 | 90,0 | 88,0 |
| 3 | +1,00 | 85,0 | 84,0 | 80,0 |
| 4 | +4,00 | 85,0 | 81,0 | 80,0 |

**Efecto medio: +0,80 → FAIL** (criterio: < 0). 3/5 réplicas en contra, 2/5 a favor.
**Regret medio:** tratamiento 82,60 vs control 81,80, mejor fija 84,20.
**Distancia a la mejor fija:** control −2,40 (el scaffold evolucionado sigue ganándole a la mejor fija); tratamiento −1,60.
**Reproducibilidad del control:** el puerto con `codeact_on=False` es bit-idéntico a `e56.correr_replica_param(SC_EVO)` en las 5 réplicas (chequeo pre-registrado OK).

**Uso de plantillas** (46 bloques con probe, idéntico a la calibración — determinista dado el control): T3_duelo 16, T2_mixta 12, T1_confianza 10, T0_solo 8. En 38/46 bloques (83%) el schedule difirió del compromiso único del control: el test no fue vacuo.

## Dónde pierde (disección)

- **El efecto es ruido alrededor de cero con leve sesgo en contra.** +0,80 sobre un regret de ~82 es ~1%. Ninguna réplica domina: 2 a favor (−1, −2), 3 en contra (+1, +2, +4). No hay mecanismo visible, solo la moneda cargada apenas en contra.
- **El riesgo (1) del pre-registro se materializó:** el gap del prior es ruidoso — repartir slots hacia R cuando el prior está "peleado" compra cobertura sobre un runner-up que, en este mundo, suele ser genuinamente peor que W. El favorito del prior, aun con gap chico, acierta lo suficiente como para que diversificar cueste más de lo que ahorra.
- **Diseño limpio, veredicto limpio.** Como la medición es full-information en ambos brazos del experimento, el estado de información evoluciona bit-idéntico entre control y tratamiento: el +0,80 mide *puro* el valor de componer-vs-elegir, sin divergencia de información que lo contamine. Es la comparación más limpia de toda la serie, y dice que no hay nada que cosechar.

## Honestidad incómoda

1. **Lo testeado fue "plantillas sobre 2 brazos con regla de gap", no CodeAct real.** Igual que EXP54 no testeó el TTRL real ni EXP59 el SPELL real, esto no testea un agente que escribe código: testea si componer schedules supera a comprometer un brazo. El nombre de la serie no debe confundirse con el mecanismo.
2. **El FAIL es chico pero no es frágil en el sentido de EXP54.** No lo carga una réplica ni depende de un umbral: 3/5 en contra, y la magnitud (~1%) está por debajo de cualquier umbral de relevancia práctica. Un PASS con este tamaño de efecto tampoco habría justificado integrar nada.
3. **El control sigue siendo lo mejor que tenemos.** Scaffold evolucionado −2,40 vs mejor fija en la media de 5 réplicas, reproducido en EXP57 (dos seeds), EXP59 y ahora EXP60. El probe Q1 + gate + Thompson con n0=4 y umbral_base=1 es un punto fijo robusto de esta línea.
4. **La serie mock oriental termina 1–4** (un PASS frágil diseccionado como varianza en EXP55, cuatro FAILs). El loop RSO como *tuning* (EXP56/57) fue lo único que sobrevivió, y ya está integrado al servicio real.

## Veredicto

**FAIL.** Efecto +0,80 (3/5 en contra, magnitud ~1% = ruido). Se activa la cláusula pre-registrada: **la serie mock de ideas orientales se cierra acá**. CodeAct-para-probe se archiva sin variantes.

## Qué queda del catálogo oriental (no mockable)

Las ideas restantes son decisiones de sistema real, no parámetros del probe: Infra Agent (telemetría + auto-optimización del stack), destilación / post-training scaling sobre open-weights (tesis: nunca pre-entrenar), MoE de baja activación como base, observabilidad/auditabilidad por diseño, co-diseño modelo-producto-infra, y CodeAct-real como arquitectura del agente del servicio (intérprete Python en vez de catálogo de tools). Ninguna se testea con este harness.
