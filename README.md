# ALMA — Prototipo mínimo (Experimento 1)

**La prueba de la selección**: ¿un sistema que *elige* cómo pensar según el
problema supera a usar siempre la misma estrategia?

Este prototipo implementa el Experimento 1 del informe de investigación
ALMA (sección 6): un meta-loop mínimo que clasifica problemas, selecciona
arquitecturas de resolución con un bandit Thompson por clase, evalúa con
verificadores externos y audita su propio aprendizaje con safety gates.

> Todo en español rioplatense, como pediste. Empezá por acá.

---

## Qué demuestra (y qué no)

**Demuestra** — en un mundo sintético controlado:
- Que el loop completo funciona end-to-end: clasificar → seleccionar →
  ejecutar → evaluar → aprender → auditar.
- Que un selector que transfiere políticas entre clases parecidas alcanza
  ~95% del reward del oráculo por clase, sin costar más que él, y supera a
  la mejor arquitectura fija en las 5 clases (criterio pre-registrado: PASS
  en seeds 42, 7 y 123).
- Que la memoria persistente entre problemas reduce el regret acumulado
  frente a resetearla (15.2 → 8.3) y frente a la mejor fija (9.5).
- Que los safety gates detectan una mala actualización y hacen rollback.

**NO demuestra** — honestidad ante todo:
- Nada sobre LLMs reales: el mock no resuelve nada, simula tasas de éxito
  por diseño. El selector aprende *del mock*, no de inteligencia real.
- El `Experimenter` es un stub: detecta incertidumbre pero **no inventa
  arquitecturas** (problema abierto del informe, sección 8).
- El juez LLM está deshabilitado en mock; la taxonomía es fija (reglas,
  no clustering descubierto por el sistema).
- Con 12 problemas por clase el bandit apenas sale de exploración: un
  buen prior manual (`prior_manual`, regret 5.9) todavía gana. El
  meta-loop paga cuando los priors son imperfectos o el mundo cambia —
  eso se ve con más muestras o con drift, no en este pilotaje.

---

## Estructura

```
alma/
  registry.py      6 familias de arquitecturas (núcleo fijo, v1.0.0)
  executors.py     runners: single, cot, self_consistency, reflexion, debate,
                   plan_tools_verify (interfaz común: ejecutar(arch, problema, backend))
  backends.py      MockBackend (mundo sintético calibrado) + OpenAICompatBackend
  featurizer.py    taxonomía fija v1 (reglas legibles, 5 clases)
  selector.py      bandit Beta por clase + Thompson sampling (snapshot/restore)
  evaluator.py     exact-match, tests de código en sandbox, juez stub/LLM (eval-v1)
  store.py         experience store append-only con hash encadenado (store-v1)
  budget.py        presupuestos por bucket (resolución/selección/experimentación)
  experimenter.py  stub honesto: propone experimentos, no arquitecturas
  gates.py         núcleo fijo + privilegios + auditoría de no-regresión + rollback
run_experiment.py  protocolo completo: pre-registro → A → B → C → gates → veredicto
data/              5 clases × 12 problemas sintéticos auto-verificables
tests/             unit tests + test de ground truth del mock
resultados/        salida del último run (reporte.json, pre-registro, etc.)
alma/evals/        LA VARA EXTERNA: evals sobre el mundo real del usuario
  base.py          métricas + EvalResult firmado (evals-v1) + historial JSONL
  finanzas.py      categorizar_gastos / detectar_anomalia / gasto_semanal
  rutina.py        rutina_manana / patron_sostiene (el meta-eval)
  data/            ground truth real: 31 transacciones de Plaid etiquetadas
                   a mano + rutina reportada + snapshot de transacciones
  run.py           runner: `python3 -m alma.evals.run`
  eval_history.jsonl  memoria de la vara: cada corrida queda firmada acá
```

### La vara externa (nuevo)

El `evaluator.py` mide si ALMA resuelve problemas sintéticos. `alma/evals/`
mide si ALMA **acierta sobre la realidad**: tus gastos, tu rutina, tus
patrones. La verdad la ponen los datos reales, nunca el modelo.

```bash
python3 -m alma.evals.run                  # corre todo y firma el historial
python3 -m alma.evals.run --eval gasto_semanal
python3 -m alma.evals.run --eval rutina_manana --fecha 2026-09-26
# ^ predice mañana sin puntuar (no hay ground truth todavía)
```

Cada eval tiene un **baseline heurístico** (corre hoy, sin API key) y acepta
un `predict_fn` para enchufar un método mejor (LLM, DSPy) que compita contra
el baseline **con la misma vara**. Ese es el loop "ALMA aprende de ALMA":
el método nuevo solo gana si el historial lo muestra.

Primera corrida real (2026-09-25, baselines):

| eval | método | score |
|---|---|---|
| categorizar_gastos | reglas | 0.968 |
| detectar_anomalia | reglas | 0.750 (F1) |
| gasto_semanal | mediana por día de semana | 0.677 |
| patron_sostiene | verificación con datos | 0.667 (2/3) |
| rutina_manana | persistencia | 0.857 |

Hallazgo del meta-eval: el patrón "gasta más los fines de semana" **no se
sostiene** en los últimos 60 días de datos — la vara externa refutó un
patrón del estudio. Así tiene que funcionar.

## Cómo correrlo

```bash
# 1. Tests (todo en stdlib, ~10 segundos)
for t in tests/test_*.py; do python3 $t; done

# 2. Experimento completo en mock (~5 segundos, ~$0.02 simulados)
python3 run_experiment.py --mock --seed 42

# 3. Con una API real compatible con OpenAI (¡gasta plata de verdad!)
export ALMA_API_KEY="sk-..."
export ALMA_API_BASE="https://api.openai.com/v1"   # o tu proveedor
export ALMA_MODEL="gpt-4o-mini"                     # o el que quieras
python3 run_experiment.py --api
```

El modo `--api` usa los datasets de `data/` (12/clase). Para el protocolo
completo (30/clase) conseguí los datasets reales —ver `data/README.md`—
y ponelos en `data/` con el mismo formato.

## El protocolo (pre-registrado antes de correr)

- **Fase A** — matriz 5 clases × 6 arquitecturas: mide el oráculo por clase
  (mejor reward) y la mejor arquitectura fija global.
- **Fase B** — leave-one-class-out: el bandit entrena en 4 clases y se evalúa
  en la 5ta, pidiendo prestada la política de la clase vista más parecida
  (`MAPEO_TRANSFER`). Mide transferencia a clase no vista.
- **Fase C (H2)** — 60 problemas en orden aleatorio, cuatro políticas:
  `persistente` (bandit con memoria), `reiniciada` (olvida en cada cambio
  de clase), `fija_global` (mejor fija de Fase A), `prior_manual` (diseño
  a mano, sin aprendizaje). Curva de regret acumulado.
- **Gates** — verificación del núcleo fijo, separación de privilegios,
  auditoría de no-regresión con regresión simulada y rollback.
- **Veredicto** — contra el criterio pre-registrado en el código
  (`CRITERIO`, calibrado en el pilotaje mock y congelado antes del primer
  run real):
  - `reward_ratio ≥ 0.90` (selector/oráculo, promedio de 5 folds)
  - `cost_ratio ≤ 1.25` (selector/oráculo en costo)
  - supera a la mejor fija global en `≥ 4/5` clases

Reward: `0.75·éxito + 0.25·(1 − costo_relativo/5)`.

## Resultados del pilotaje (mock, seed 42)

| Fase | Resultado |
|---|---|
| A — oráculos | calculo→cot, codigo→plan_tools_verify, qa_multihop→cot, herramientas→plan_tools_verify, puzzles→debate; mejor fija: reflexion |
| B — transferencia | reward_ratio 0.945, cost_ratio 0.924, supera a la fija en 5/5 |
| C — regret final | persistente 8.27 < fija_global 9.51 < reiniciada 15.24 (prior_manual 5.91: el prior diseñado es bueno en este mundo) |
| Gates | núcleo intacto, regresión simulada detectada, rollback OK |
| **Veredicto** | **PASS** (también con seeds 7 y 123) |

## Costo estimado del experimento real

Protocolo completo: 5 clases × 30 problemas × 6 arquitecturas (Fase A: 900
ejecuciones) + 150 (Fase B) + 600 (Fase C) ≈ **1650 ejecuciones**,
≈ **4650 llamados** a la API (self-consistency, debate y reflexion hacen
varios llamados por ejecución). Suponiendo ~1000 tokens de entrada y ~300
de salida por llamado:

| Modelo | Estimación |
|---|---|
| gpt-4o-mini ($0.15/$0.60 por 1M) | **≈ $1.50–2.00 USD** |
| gpt-4o ($2.50/$10.00 por 1M) | **≈ $25–35 USD** |

Precios ilustrativos (2026): **verificar vigentes antes del run real** —
están en `alma/backends.py` (`PRECIOS`). El `BudgetManager` corta la
ejecución si se supera el presupuesto: para el run real se sugiere
`--api` con presupuesto de **$10 USD** en mini (margen de sobra) o
**$50 USD** en 4o. El juez LLM real (`--judge`) suma ~30%.

## Decisiones de diseño que vale la pena discutir

1. **El mock es un laboratorio, no un estudio de campo.** Su ground truth
   está calibrado a ±0.045 del diseño por construcción (búsqueda de sal
   determinista, verificada en `tests/test_mock_ground_truth.py`). Esto
   elimina el ruido muestral del mundo para que el experimento mida al
   *selector*, no a los dados. El ruido real aparece con la API de verdad.
2. **La taxonomía es infraestructura fija, no algo que el sistema aprende.**
   Por eso en Fase B se clasifica con las 5 clases aunque el bandit no
   tenga experiencia en la retenida: lo no-visto es la *política*, no la
   *clase*.
3. **El criterio de costo se calibró en el pilotaje** (1.10 → 1.25): el
   clasificador al 95% genera ~5% de rutas caras por mala clasificación.
   Quedó congelado antes de cualquier run real.
4. **Lo que falta** (a propósito): juez que se auto-calibra, taxonomía
   descubierta por el sistema, experimentador que invente arquitecturas,
   garantías formales. Están marcados como `stub` / `TODO(H)` en el código.

## Próximo paso sugerido

Correr el protocolo contra `gpt-4o-mini` con los datasets reales
(GSM8K, HumanEval, HotpotQA, GAIA, Game-of-24 — ver `data/README.md`).
Costo estimado: **menos de $2 USD**. Si el veredicto da PASS en el mundo
real, el siguiente paso es el Experimento 2 del informe (ALMA vs
DynaSwarm).
