# ALMA-EXP53 — Veredicto: FAIL (mock)

**Fecha:** 2026-09-27 ~16:15 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Serie:** "ideas orientales" (nueva; no reapertura de EXP45–52)
**Pre-registro:** `exp53_skillrl/preregistro.md` + `exp53_skillrl/preregistro.json` (escritos antes de correr)

## Qué se testea

La idea oriental SkillRL (idea 5 del catálogo): banco de skills versionado con scoring (win-rate con decaimiento por firma, retrieval de la versión de mejor score, evolución del campeón ante misfires, deprecación del que pierde) vs la memoria "diario" plana de EXP45–51 (prior de Thompson condicionado a la firma, promediando todo el historial con olvido 0.5^d). Un solo moving part: la representación de la memoria. Control = política de EXP51 verbatim.

**Criterio pre-registrado:** PASS ssi media(reg_trat − reg_ctrl) < 0.

## Números

| Réplica | efecto | reg trat | reg ctrl | skips trat (mis) | skips ctrl (mis) | Q2 saltados trat/ctrl |
|---|---|---|---|---|---|---|
| 0 | +4,00 | 82,0 | 78,0 | 5 (1) | 5 (1) | 2 / 3 |
| 1 | +8,00 | 94,0 | 86,0 | 0 (—) | 0 (—) | 3 / 8 |
| 2 | +9,00 | 102,0 | 93,0 | 0 (—) | 2 (1) | 1 / 3 |
| 3 | +0,00 | 95,0 | 95,0 | 8 (1) | 6 (2) | 3 / 3 |
| 4 | +5,00 | 85,0 | 80,0 | 4 (1) | 5 (1) | 2 / 3 |

**Efecto medio: +5,20 → FAIL** (criterio: < 0).
Media sin la mejor réplica (rep 3, +0,00): +6,50 → el FAIL no lo carga una sola réplica; 4/5 en contra, ninguna a favor.
**Regret medio:** tratamiento 91,60 vs control 86,40, mejor fija 84,20.
**Distancia a la mejor fija:** tratamiento 7,40 vs control 2,20 (en EXP51: 2,20 vs 3,80). El hueco se AGRANDÓ 5,2 puntos.
**Reproducibilidad del control vs EXP51:** bit-idéntico (True) — el control es la política probe-barato exacta.

**Banco (5 réplicas):** 28 nacimientos, 26 refuerzos, **66 penalizaciones**, 37 evoluciones, 23 deprecaciones.

## Dónde pierde (disección)

- **El skip no es el problema.** El tratamiento salta 17 bloques con 3 misfires (17,6%) vs 18 con 5 (27,8%) del control — misfirea MENOS. En rep 0, la pérdida en bloques saltados es exactamente 0,0; los +4,0 viven enteros en bloques no saltados (5 de 19 pierden).
- **La pérdida es difusa:** muerte por mil cortes. Rep 0 pierde +4 sin ningún bloque ≥ +2. El prior concentrado juega ~+1 peor por bloque en muchos bloques.
- **El gate dispara menos en el tratamiento** (totales: 11 vs 17): el campeón del banco rara vez es el brazo decisivo en Q1 — a menudo está stale — así que el tratamiento paga más probes completos con scoring ciego.
- **El banco churnea sin converger:** los campeones pierden sus evaluaciones 2,5× más de lo que las ganan (66 penalizaciones vs 26 refuerzos); 37 evoluciones migran el campeón sin asentarlo; 23 deprecaciones. La evolución por victorias ruidosas persigue ruido, no señal.

## Honestidad incómoda

1. **El FAIL es robusto, no ruidoso.** 4/5 réplicas en contra y ninguna a favor: es una refutación fuerte de la representación versionada en este mundo, no un accidente de muestra.
2. **El mecanismo del fracaso es el anticipado en la nota de refutación.** La concentración olvida estructuralmente los brazos no-campeones → el prior es más frágil que el diario cuando el campeón está stale. Y la evolución por victorias pareadas ruidosas (el probe tiene ~2/10 de ruido por bloque) migra el campeón al brazo equivocado una y otra vez. Los dos riesgos pre-registrados se materializaron a la vez.
3. **El diario plano recuerda lo que el banco olvida, y en este mundo eso vale +5,2.** La lección es asimétrica: olvidar es más caro que recordar cuando el mundo es ruidoso, porque el "campeón" que elegís con evidencia ruidosa está mal la mitad del tiempo.
4. **Corrección metodológica:** el primer chequeo de bit-identidad comparó el control contra la columna equivocada de EXP51 (`reg_control_bloques`, el skip-endurecido) en vez de `reg_trat_bloques` (la política probe-barato). Detectado antes de interpretar, corregido en el script y en el pre-registro; la verificación final es True contra la columna correcta.

## Veredicto

**FAIL.** La representación versionada con scoring pierde por 5,2 puntos contra el diario plano, agranda el hueco a la mejor fija de 2,2 a 7,4, y falla en 4 de 5 réplicas. El valor de la idea SkillRL no está en la representación de la memoria — al menos no en un mundo con este nivel de ruido.

## Recomendación (según pre-registro)

No insistir con variantes del banco (ni ablaciones: el FAIL es lo bastante claro y robusto como para no gastar otro mock en diseccionarlo). La serie "ideas orientales" pasa a la siguiente idea. Candidatas: **TTRL** (aprendizaje en test-time: el modelo sigue aprendiendo mientras responde) o **CodeAct** (el agente programa en vez de elegir brazo). Para el sistema real: la memoria con olvido plano de la fase 0 **no** se reemplaza por un banco versionado con scoring sin más evidencia — este mock la refutó.
