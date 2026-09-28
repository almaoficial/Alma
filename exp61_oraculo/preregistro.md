# ALMA-EXP61 — Pre-registro (mock, US$0)

**Fecha:** 2026-09-27 ~16:30 EDT · **Serie:** rediseño post-fase-1 ("skills como priors")
**Modo:** mock (US$0,00 — ninguna API key se toca)

## Por qué existe este experimento

Fase 1 FAIL (criterio 6): el proveedor real genera skills en prosa (SKILL.md),
se inyectan al prompt del modelo, y la diferencia conductual guiada−raw es
exactamente 0,000. La consecuencia pre-registrada: **rediseñar antes de fase 2
— skills como priors, no como instrucciones**.

El rediseño mueve el efecto de la skill del *modelo* (prompt) a la
*maquinaria* (números que el resolver consume): la skill deja de ser prosa
que el modelo lee y pasa a ser **parámetros del prior por firma** que el
Thompson usa. Los mocks EXP45–52 ya probaron que los priors condicionados a
la firma funcionan; lo que falta saber es si un **proveedor generativo** (que
abstrae parámetros por firma desde las experiencias) tiene techo sobre el
scaffold global fijo ya evolucionado.

## Hipótesis (una frase)

Un proveedor que genera parámetros del prior por firma con abstracción
PERFECTA (oráculo: conoce las medias verdaderas por grupo) reduce el regret
frente al scaffold global fijo evolucionado, porque adapta el prior a cada
régimen en vez de usar un único default global estimado con ruido.

## Diseño

- **Mundo:** stream de 24 bloques bit-idéntico al de la serie
  (`run_experiment47.construir_stream`, seed 45, namespace RNG del oráculo
  `exp45-...`).
- **Control:** el scaffold evolucionado validado (EXP56/57, dos seeds):
  `SC_EVO = {n0:4, umbral_base:1, umbral_divisor:3, gate_margin:0.0,
  decay:0.5}` vía `run_experiment56.correr_replica_param` importado verbatim.
  Es el default actual del servicio (`alma_service/scaffold.py`).
- **Tratamiento ("oráculo"):** el control + UN moving part. Cuando el
  camino con probe usa la skill (`usa_skill`), el prior condicionado a la
  firma NO se estima del historial con ruido: se fija en las **medias
  verdaderas por grupo** del oráculo, con el mismo peso n0=4. Todo lo demás
  — skip con umbral endurecido, camino de probe saltado, gate Q1, Thompson
  en sus slots, `medir` con scoring full-information, `probe_obs`, victorias
  de la skill, prior NO condicionado (fav) — idéntico por construcción. Se
  compara CALIDAD de información del prior, no su peso.

### Prior oráculo (pre-registrado)

Para firma `g` (grupo) y brazo `a`:
`m_a(g) = Σ_cat∈GRUPOS[g] w_cat · tasa(a, cat)`,
con `w_cat = freq[cat] / Σ_{c∈GRUPOS[g]} freq[c]` (freq del feed, como en
`construir_stream`) y `tasa` del `MockClasificador`. Para el brazo
"mayoria" (sin tasa en el oráculo): aproximación pre-registrada con la moda
global de categorías del stream —
`m_mayoria(g) = Σ_cat∈GRUPOS[g] w_cat · [cat == moda]`.
Formato idéntico al control: `(1 + n0·m, 1 + n0·(1−m))`.

El oráculo es el **techo informativo**: lo mejor que cualquier proveedor
podría generar. Un proveedor real (LLM) solo vería experiencias logueadas,
nunca las tasas verdaderas.

## Criterio PRE-REGISTRADO

- **efecto** = media sobre 5 réplicas pareadas de
  `regret(oráculo) − regret(control-EVO)`.
- **PASS ssi efecto < −1,0** (vara MÁS exigente que el <0 habitual: el
  oráculo es irrealmente fuerte; un LLM real capturaría solo una fracción
  del techo. Si ni el techo mueve >1 punto, no hay nada que un proveedor
  real pueda entregar).
- Se reporta además (no cambia el veredicto): efecto por réplica; efecto en
  bloques 0–11 (primeras ocurrencias, prior del control más ruidoso) vs
  12–23; distancia a la mejor fija `d_trat` vs `d_ctrl`; frecuencia de uso
  de la skill.

## Chequeos de reproducibilidad (pre-registrados)

1. El tratamiento con el módulo desactivado (`oraculo_on=False`) debe ser
   **bit-idéntico** a `e56.correr_replica_param(SC_EVO)` en las 5 réplicas.
   Si no coincide, el puerto no es fiel y el experimento no se interpreta.
2. Magnitudes: los regrets del control por réplica deben estar en el rango
   ~70–95 (consistente con EXP57/59/60).

## Qué se concluye según el resultado (pre-registrado)

- **PASS (efecto < −1,0):** hay techo para el proveedor generativo. Siguiente:
  diseñar **fase 1b** — proveedor REAL (LLM con key) que genera parámetros
  por firma desde experiencias logueadas, con pre-registro propio y su "sí"
  explícito con costo (~US$0,05–0,10) y tiempo. El PASS no prueba que el LLM
  alcance el techo: solo prueba que el techo existe.
- **FAIL (efecto ≥ −1,0):** ni la abstracción perfecta mueve la aguja. Se
  **archiva la vía del proveedor generativo**: el sistema real conserva el
  scaffold fijo evolucionado (n0=4, umbral_base=1), la memoria con olvido, el
  detector de recurrencia y el Curator; ningún LLM genera skills. El
  rediseño post-fase-1 queda respondido por la negativa con números.

## Nota de refutación

Riesgos pre-registrados: (1) el prior del control ya está condicionado a la
firma con olvido — la ventaja del oráculo vive solo en las primeras
ocurrencias y en el ruido de estimación; puede ser chica; (2) con n0=4 y 10
items por bloque, el prior se diluye rápido: el techo estructural del
mecanismo es bajo por construcción; (3) si el efecto ∈ (−1, 0): mejora
real pero sin techo útil — se clasifica como FAIL (la vara −1,0 ya lo
contempla).
