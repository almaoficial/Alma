# ALMA-EXP58 — Pre-registro (mock, US$0)

**Fecha:** 2026-09-27 ~16:05 EDT · **Serie:** "ideas orientales" (RSO; continúa EXP56/57)
**Modo:** mock (US$0,00 — ninguna API key se toca)

## Hipótesis (una frase)

Un proponente que analiza atribución de fallos por bloque (en vez de proponer al
azar) encuentra en 24 rondas un scaffold mejor que el encontrado por propuestas
aleatorias (EXP56: held-out 83.00), partiendo del mismo scaffold inicial y con el
mismo protocolo keep/revert.

## Qué cambia vs EXP56/57

**Solo el proponente.** Mismo espacio de 5 hiperparámetros, mismos valores
iniciales (SC_INIT = EXP51 manual), mismo stream bit-idéntico (24 bloques de
EXP47/49/51), mismos splits (train [0,1,2] para keep/revert Y para el análisis;
held-out [3,4] que el loop nunca ve), misma regla keep-estricto en train, misma
regla de oro (el loop nunca edita al validador: oráculo, stream, cómputo de
regret, evaluador y código del loop congelados). La instrumentación añade
diagnósticos por bloque al retorno de la réplica; el cómputo de la política y del
regret no cambia (chequeo de sanidad bit-idéntica pre-registrado, mismos totales
de EXP51: [78.0, 86.0, 93.0, 95.0, 80.0]).

## La heurística del proponente (explícita y documentada)

Después de cada ronda, el proponente evalúa el scaffold ACTUAL en train [0,1,2]
con diagnósticos por bloque y computa, agregado sobre 72 observaciones
bloque×réplica. Referencias por bloque (todas computables porque cada item se
evalúa en todos los brazos): `reg_pol` (regret de la política), `reg_skill`
(regret jugando el brazo de la skill en todo el bloque), `reg_best` (regret del
mejor brazo fijo del bloque), `fav` (brazo favorito del prior no condicionado al
inicio del bloque).

**Señales** (unidades: regret):
1. `misfire_cost` — en bloques SALTADOS con skill: Σ (reg_skill − reg_best)
   donde el skip perdió contra la mejor fija del bloque. Mide "saltar de más".
2. `oportunidad` — en bloques NO saltados con skill: Σ max(0, reg_pol − reg_skill).
   Mide "saltar de menos".
3. `probe_cost` — en bloques NO saltados: Σ max(0, reg_pol − reg_best). Mide
   errores del probe/prior/Thompson.
4. `prior_bien` / `prior_mal` — descomposición de probe_cost según si `fav`
   coincidió con el mejor brazo del bloque. Mide si el prior sabía y el probe
   desperdició (domina prior_bien) o si el prior engañó (domina prior_mal).

**Reglas** (una mutación por ronda, un paso en el espacio ordenado; prioridad en
orden; dentro de cada regla se intenta la dimensión preferida y luego la
alternativa):
- **R1 — skip demasiado agresivo:** si `misfire_cost > oportunidad` y
  `misfire_cost > 2.0` → endurecer el skip: `umbral_base` +1 paso si < 3;
  si no, `umbral_divisor` −1 paso si > 2; si no, abstener.
- **R2 — skip demasiado tímido:** si `oportunidad > misfire_cost` y
  `oportunidad > 2.0` → ablandar el skip: `umbral_base` −1 paso si > 1;
  si no, `umbral_divisor` +1 paso si < 6; si no, abstener.
- **R3 — el probe es el problema:** si `probe_cost > (misfire_cost + oportunidad)`
  y `probe_cost > 4.0` → ajustar el prior: si `prior_bien ≥ prior_mal`,
  `n0` +1 paso si < 4 (el prior sabía: darle más fuerza); si no, `n0` −1 paso
  si > 1 (el prior engañaba: debilitarlo); si no, abstener.
- Si ninguna regla dispara → **la ronda se abstiene** (se registra "sin
  propuesta"; el scaffold no cambia).

**Memoria tabú:** una mutación rechazada no se re-propone en las 3 rondas
siguientes (se intenta la alternativa de la regla; si ambas están vetadas, la
ronda se abstiene). El tabú se limpia cuando hay un keep (el scaffold cambió, la
evaluación vieja ya no vale).

**Dimensiones sin señal atribuible:** `gate_margin` (EXP56 mostró que el gate es
binario en este mundo: ningún margen mueve decisiones) y `decay` (sin regla
direccional honesta derivable de estas señales) — el proponente nunca las propone.
El espacio de mutación es el mismo que EXP56; la diferencia es solo qué propone
el proponente.

## Criterio final PRE-REGISTRADO

- **PASS** ssi `media_heldout(scaffold_EXP58) < 83.00` = media held-out del
  scaffold evolucionado de EXP56 en el mismo held-out [3,4].
- Secundario (no cambia el veredicto): vs INIT 87.50, vs EXP57-B 84.50;
  eficiencia (keeps/ronda, abstenciones, ronda de convergencia); trayectoria
  completa con regla disparada y señales por ronda.

## Interpretación pre-registrada (vinculante)

- **PASS** → el proponente con análisis de fallos supera en 24 rondas al de
  propuestas aleatorias: evidencia (en mock) de que la inteligencia del
  proponente aporta sobre el keep/revert pelado.
- **FAIL con held-out < 87.50** → el loop con proponente inteligente iguala el
  vecindario del aleatorio pero no lo supera: no hay evidencia de que el análisis
  de fallos ayude en este espacio/régimen (o la heurística es mala, o 24 rondas no
  alcanzan, o el espacio ya está agotado tras EXP56/57).
- **FAIL con held-out ≥ 87.50** → el proponente ni siquiera supera el tuning
  manual: la heurística dirige mal.

## Notas de honestidad pre-registradas

1. La heurística se diseñó CON conocimiento de los hallazgos de EXP45–57 (p. ej.,
   que n0↑ ayuda y que el gate es binario). Testea "proponente con reglas
   diseñadas por analista", no "descubrimiento desde cero" — como el de MiniMax,
   que también trae priors.
2. Los umbrales ε (2.0 / 4.0) son juicio del analista, no derivados.
3. El held-out [3,4] es n=2 y ya se usó en los veredictos de EXP56/57
   (comparación múltiple leve; el loop no lo ve, así que la medición es válida).
4. Mutaciones de un paso (el azar de EXP56 a veces saltaba varios pasos):
   granularidad comparable, documentada.

## Qué sigue según el resultado (pre-registrado)

- **PASS** → EXP59: ablación del scaffold del proponente inteligente (¿qué regla
  aportó?) y/o escalar a proponente LLM real sobre el sistema real (requiere key:
  decisión del usuario).
- **FAIL** → la serie RSO se archiva en este espacio: el keep/revert queda como
  mecanismo de tuning validado (EXP56/57) y se pasa a la siguiente idea oriental
  (SPELL para el probe).
