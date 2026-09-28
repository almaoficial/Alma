# ALMA-EXP67 — Pre-registro: benchmark del loop en tarea REAL

**Fecha:** 2026-09-27 (escrito ANTES de gastar el primer centavo).
**Estado:** DISEÑO COMPLETO, experimento NO ejecutado. Las llamadas reales con
la key del usuario requieren su "sí" explícito al costo y tiempo estimados aquí.
La key, si se usa, va solo vía variable de entorno transitoria; nunca en disco.

## Pregunta

¿El loop de ALMA le gana a los brazos fijos en un stream NO estacionario de
tareas REALES (no sintéticas), con el modelo real como motor?

## Hipótesis

`alma-full` (Thompson por régimen + probe + memoria con olvido + skip) logra
menor regret que el mejor brazo fijo y que el Thompson global, porque el
probe y la memoria seleccionan el brazo correcto por régimen. La hipótesis
asume un mundo donde distintos brazos ganan en distintos regímenes — la
puerta anti-colapso (§4 de `diseno_stream.md`) verifica esa propiedad con el
modelo real ANTES del oráculo.

## Diseño

- **Stream:** 9 bloques × 20 problemas = 180 problemas reales, orden de slices
  pre-registrado: gsm8k → mmlu → mbpp → mmlu → gsm8k → mbpp → gsm8k → mmlu → mbpp.
  Manifiesto con IDs exactos: `stream_manifest.json` (seed 67).
- **Brazos:** {single, cot, reflexion} con el mapeo de esfuerzo de EXP62
  (none/high/max; max_tokens 256/1024/2048). Detalle en `diseno_stream.md`.
- **Oráculo:** 2 intentos por celda (problema × brazo) — disciplina EXP8
  relajada por costo (3→2), documentado. 180×3×2 = 1080 llamadas.
  Ground truth automático: exact-match numérico (gsm8k), letra (mmlu),
  tests en sandbox con timeout (mbpp).
- **Piloto anti-colapso (pre-oráculo):** 10 problemas/slice × 3 brazos × 2
  intentos = 180 llamadas. Regla: el slice pasa si ningún brazo gana >80% de
  sus celdas; si colapsa → backup pre-registrado (HumanEval / ARC-Challenge),
  máx. 2 reemplazos; si persiste → diseño a 2 slices. El criterio PASS/FAIL
  no cambia (validación del mundo, no del arco).
- **Políticas:** alma-full (scaffold vigente n0=4, decay 0.5, umbral_base=1;
  probe 9/bloque; skip) vs fija-single / fija-cot / fija-reflexion vs
  thompson-global (1 bandit, prior uniforme). Evaluador idéntico al EXP62
  (reward = 0.75·éxito + 0.25·(1 − costo_rel/5)); RNG pareado por posición.
- **Idempotencia:** pulls idempotentes por (fase, problema, brazo, intento);
  resume limpio ante crashes (lección EXP62: 3 crashes sin pérdida de datos).

## Criterio de éxito (vara pre-registrada, sin mover después)

PASS necesita AMBAS:
- regret(alma-full) < regret(mejor brazo fijo entre los 3)
- regret(alma-full) < regret(thompson-global)

Diagnóstico: bloques donde alma-full le gana a la mejor fija; elecciones del
probe por bloque; firma del régimen que el loop aprendió.

## Presupuesto (freno duro US$1,00)

Estimación construida con costos por llamada MEDIDOS del EXP62
(`exp62_deepseek/gasto_por_llamada.jsonl`, medias: single US$0,000014,
cot US$0,000139, reflexion US$0,000278; n=101, muestra parcial — se usa la
media como estimación conservadora) + 50% de margen por reintentos
(la API de DeepSeek es inestable: EXP62 necesitó decenas de reintentos).

| Fase | Llamadas | Estimado |
|---|---|---|
| Smoke (1 problema × 3 brazos) | 3 | US$0,01 |
| Piloto anti-colapso (3 slices × 10 × 3 × 2) | 180 | US$0,026 |
| Oráculo (180 × 3 × 2) | 1080 | US$0,155 |
| Políticas (probe 81 + pulls 900) | 981 | US$0,128 |
| **Subtotal** | **2244** | **US$0,319** |
| **+50% margen reintentos** | | **US$0,48** |

**Estimado total con margen: US$0,48 (< US$0,50).** Freno duro US$1,00
(`BudgetExceeded` aborta limpio; si aborta antes de completar → parcial sin
veredicto). Orden de fases: smoke → piloto → oráculo → políticas
(si hay que abortar, el oráculo completo es el artefacto más valioso).

**Tiempo estimado: ~3 horas (±1 h).** Basado en throughput MEDIDO del EXP62
(~19 llamadas/min con inestabilidad y reintentos 3→6). Marcado como estimación,
no promesa. Todo corre en background.

## Veredictos posibles

- **PASS:** el loop le gana a las fijas y al Thompson global en tarea real →
  primera evidencia de que la ventaja no es un artefacto del mundo sintético.
- **FAIL:** no le gana → se reporta con números qué parte falló
  (¿probe? ¿memoria? ¿mundo single-dominante pese al piloto?).
- **ABORTO:** freno de US$1,00 o inestabilidad insalvable → parcial sin veredicto.

## Trazabilidad de decisiones

- N reducido a 180 problemas (9×20) para que el estimado con margen entre
  bajo US$0,50 — se achicó el diseño, no el margen (regla de la tarea).
- Intentos/celda 3→2 por costo; el piloto compensa con verificación del mundo.
- Motor: deepseek-flash (mismo que EXP62, permite comparar real-vs-sintético
  con el mismo modelo).
