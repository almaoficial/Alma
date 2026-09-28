# ALMA-EXP53 — Pre-registro (mock, US$0)

**Fecha:** 2026-09-27 ~16:05 EDT · **Serie:** "ideas orientales" (nueva serie; NO es reapertura de EXP45–52)
**Modo:** mock (US$0,00 — ninguna API key se toca)

## Hipótesis (una frase)

Un banco de skills versionado con scoring (win-rate con decaimiento por firma de régimen, retrieval de la versión de mejor score, evolución del campeón ante misfires y deprecación del que pierde) reduce el regret frente al prior plano de EXP51, porque concentra la memoria en el brazo que gana y olvida estructuralmente el que pierde, en vez de promediar toda la historia con olvido uniforme.

## Idea oriental testeada

SkillRL (idea 5 del catálogo oriental): banco de skills jerárquico y versionado que co-evoluciona, vs la memoria "diario" plana de EXP45–51 (prior de Thompson condicionado a la firma, promediando todo el historial con olvido 0.5^d).

## Diseño

- **Mundo:** stream de 24 bloques bit-idéntico al de EXP47/49/51 (`run_experiment47.construir_stream`, seeds 45/47, namespace de RNG del oráculo `exp45-...`).
- **Control:** la política de EXP51 VERBATIM (`run_experiment51.correr_replica_probe_barato`, importada sin copiar): skip con umbral endurecido 2+floor(K/3) + probe adaptativo con gate Q1.
- **Tratamiento ("skill-bank"):** COPIA VERBATIM del control, salvo UN moving part: la representación de la memoria. El diario plano se reemplaza por un banco versionado:

  Por firma de régimen, el banco guarda versiones `{brazo, v, score, media}` donde `score` = win-rate con decaimiento exponencial (D=0.5 por bloque, igual que el olvido de la línea) y `media` = accuracy con decaimiento del brazo.
  - **Retrieval:** la versión NO deprecada de mayor score (desempate: menor nº de versión, determinista). Si no hay versiones o todas están deprecadas → no hay skill (camino idéntico al control sin skill: prior ciego).
  - **Nacimiento:** al completar un bloque con probe sin skill previa, nace v1 con el brazo ganador de la comparación pareada (regla estricta idéntica a la de victorias del soporte; desempate primer máximo como el control), score inicial 1.0.
  - **Evolución:** al final de cada bloque se evalúa la versión recuperada. Victoria (pareada estricta en probe, o mejor ex post en bloque saltado) → **se versiona reforzada** (nueva versión, mismo brazo, score con continuidad). Derrota → **se penaliza** (score baja en el lugar); si otro brazo ganó el bloque estrictamente → **nace una versión con ese brazo** (el campeón migra). Score < 0.25 con masa decaída ≥ 1.5 → **deprecada** (excluida del retrieval).
  - **Prior de Thompson con skill:** concentrado en el campeón — el brazo de la versión recuperada recibe `(1+N0·m, 1+N0·(1−m))` con `m` = su media con decaimiento (N0=2, igual que el control); los demás brazos reciben prior uniforme `(1+N0·0.5, 1+N0·0.5)`. El banco **olvida estructuralmente** los brazos no-campeones: esa es la diferencia representacional vs el diario, que los recuerda a todos.
  - **Soporte del skip y gate Q1:** reglas IDÉNTICAS al control (`soporte_endurecido`, `q1_decisivo`), aplicadas al campeón del banco en vez del argmax del diario.
  - **Sin skill:** fallback idéntico al control (prior ciego del historial).

- **RNG:** mismos namespaces que el control. Los sorteos del oráculo son bit-idénticos; las jugadas de Thompson divergen legítimamente porque los priors difieren (efecto downstream, como en EXP51).
- **Réplicas:** 5 pareadas (mismo RNG que el control por réplica).

## Criterio PRE-REGISTRADO

- **efecto** = media sobre réplicas pareadas de `regret(skill-bank) − regret(control-EXP51)`.
- **PASS ssi efecto < 0** (misma vara de refutación que toda la línea).
- Se reporta además (no cambia el veredicto): distancia a la mejor fija `d_trat` vs `d_ctrl` (en EXP51: 2.20 vs 3.80), tasa de misfires de skips, efecto sin la mejor réplica, y estadísticas del banco (versiones nacidas, evoluciones, deprecaciones).

## Chequeo de reproducibilidad (pre-registrado)

El control debe ser bit-idéntico a la política probe-barato de EXP51, es decir, al **tratamiento** de EXP51 (no a su control skip-endurecido): `reg_trat_bloques` por réplica == `resultados/exp51-20260927/report.json` (`[78.0, 86.0, 93.0, 95.0, 80.0]`). Si no coincide, el experimento no es válido y no se interpreta.

## Nota de refutación

El riesgo principal es la concentración: al olvidar los brazos no-campeones, el prior del tratamiento es MÁS frágil que el del control cuando el campeón está stale — el diario recuerda que el otro brazo era malo/bueno, el banco no. Segundo riesgo: la evolución por victorias ruidosas puede migrar el campeón al brazo equivocado (el probe tiene ~2/10 de ruido por bloque). Si el efecto no aparece o es positivo, la representación versionada no supera al diario plano en este mundo: el valor de SkillRL no está en la representación sino en otro lado (o en ningún lado, en este mundo).

## Qué sigue según el resultado (pre-registrado)

- **Si PASS:** EXP54 = ablación del banco: ¿el valor está en la evolución (migración del campeón) o en la concentración (olvidar no-campeones)? Un mock con banco SIN evolución (campeón fijo = primer ganador) vs banco SIN concentración (recuerda todos los brazos) lo dirime. Un solo moving part por mock.
- **Si FAIL:** no se insiste con variantes del banco. La serie "ideas orientales" pasa a la siguiente idea (candidatas: TTRL —aprendizaje en test-time— o CodeAct —el agente programa en vez de elegir brazo—). El FAIL también informa al diseño del sistema real: la memoria con olvido plano (fase 0) no se reemplaza por un banco versionado sin más evidencia.

## Relación con el cierre de EXP52

EXP52 cerró la línea EXP45–52 (mecanismo skip/probe: techo estructural del mundo). EXP53 abre una SERIE NUEVA con hipótesis distinta (representación de la memoria, idea oriental SkillRL). El control es EXP51 verbatim precisamente para que la comparación sea limpia y no se mueva el arco: la vara de PASS es la misma.
