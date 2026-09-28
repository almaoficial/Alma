# EXP67-Claude-Full — Pre-registro: réplica del oráculo EXP67 con Claude

**Fecha:** 2026-09-28 (escrito ANTES de gastar el primer centavo de esta corrida).
**Estado:** DISEÑO COMPLETO, experimento NO ejecutado.
**Aprobación de gasto:** el usuario aprobó FRENO DURO US$1,50 para este frente
de medición (tarea del 2026-09-28). La key va solo por surrogate del vault
(`custom.anthropic`); nunca toca disco ni logs.

## Pregunta

¿Se puede medir el oráculo completo del EXP67 (180 problemas reales × 3 brazos
× 2 intentos) con `claude-haiku-4-5-20251001` para sembrar el registry con el
tercer proveedor (reward por celda + costo por llamada medidos)?

## Hallazgo previo a correr (verificación del 2026-09-28, sin gasto)

Los 63 pulls crudos del EXP70 (`exp70-claude-pilot-20260928/claude_pulls.jsonl`)
están en problemas de la **sección pilot** del manifiesto, DISJUNTOS de los 180
problemas de la sección stream del oráculo (overlap verificado = 0). Por lo
tanto **no rellenan celdas del oráculo** y los 1080 pulls se miden frescos sobre
los problemas del stream. Los 63 pulls se conservan como campaña complementaria
(`exp70-piloto`) para el registry. No se re-gasta nada ya medido.

## Diseño

- **Problemas:** los 180 de la sección `stream` del manifiesto EXP67
  (`stream_manifest.json`, seed 67), en su orden pre-registrado
  (9 bloques × 20: gsm8k → mmlu → mbpp → mmlu → gsm8k → mbpp → gsm8k → mmlu → mbpp).
  Correr en este orden hace que un corte por freno deje bloques completos.
- **Brazos:** {single, cot, reflexion} — mismos prompts que el oráculo
  (vía `ejecutar()` de run_exp62, disciplina EXP1-9), mismos max_tokens por
  brazo (256/1024/2048), temperature 0.2.
- **Modelo:** `claude-haiku-4-5-20251001` (snapshot pineado, mismo que EXP70).
- **Intentos:** 2 por celda (problema × brazo), igual que el oráculo EXP67.
  Total: 180 × 3 × 2 = **1080 pulls**.
- **Métrica:** `puntuar()` binaria 0/1 idéntica al EXP67 (exact-match numérico
  gsm8k, letra mmlu, tests en sandbox mbpp). Misma reward, mismos problemas que
  el oráculo DeepSeek → comparación directa válida.
- **Idempotencia:** pulls keyed por (pid, brazo, intento) en
  `claude_oracle_pulls.jsonl`; resume limpio ante crashes.
- **Auth check:** `GET /v1/models` gratuito antes del primer pull con gasto.

## Criterio (vara pre-registrada — frente de MEDICIÓN, no de hipótesis)

- **MEDICIÓN COMPLETA** si TODAS: 1080/1080 pulls sin 401/403;
  `claude_oracle_summary.json` generado con reward/costo por celda.
- **MEDICIÓN PARCIAL** si el freno o la proyección cortan la corrida: se
  conservan los pulls, se reporta por celda lo medido, SIN veredicto
  comparativo (misma regla que el EXP70).
- No hay PASS/FAIL de hipótesis: la comparación vs DeepSeek/OpenAI es
  **descriptiva** (formato pre-registrado abajo), insumo para el registry
  y el router — no un veredicto sobre ALMA.

## Comparación pre-registrada (formato, no resultado)

Tabla por (slice, brazo) con: reward medio Claude (n real) vs DeepSeek-oráculo
(n=120, mismos 180 problemas) vs OpenAI-piloto (n=20, otros 30 problemas —
caveat de comparabilidad); costo medio por llamada de cada proveedor;
reward/USD por proveedor y brazo. Cálculo fáctico adicional: qué
(proveedor, brazo) gana cada slice por reward/USD con la regla EXP69 verbatim.
Sin test de hipótesis, sin vara: es medición.

## Presupuesto (freno duro US$1,50)

**Proyección honesta con costos MEDIDOS del EXP70** (63 pulls, medias por celda
gsm8k/mmlu n=8, mbpp n=5):

| celda | costo/pull medido | ×120 |
|---|---|---|
| gsm8k/single | US$0,000178 | US$0,021 |
| gsm8k/cot | US$0,001475 | US$0,177 |
| gsm8k/reflexion | US$0,002150 | US$0,258 |
| mmlu/single | US$0,000245 | US$0,029 |
| mmlu/cot | US$0,002055 | US$0,247 |
| mmlu/reflexion | US$0,002794 | US$0,335 |
| mbpp/single | US$0,000637 | US$0,076 |
| mbpp/cot | US$0,002331 | US$0,280 |
| mbpp/reflexion | US$0,003356 | US$0,403 |
| **Total 1080** | | **≈ US$1,83** |

**La proyección medida (≈ US$1,83) supera el freno (US$1,50).** El estimado
previo (~US$1,20) usaba la heurística de ratio de precios; el piloto ya mostró
que la verbosidad de Claude lo encarece ~35–50% por encima de esa heurística.
Se corre igual bajo el freno porque (a) la tarea lo pide con la regla de
parcial explícita, (b) un parcial de ~840–900 pulls deja gsm8k completo y
mmlu/mbpp con n≈80 por celda — útil para el registry. **Resultado esperado:
MEDICIÓN PARCIAL.**

**Regla operativa anti-overshoot (la que el EXP70 no aplicó — miss +2,8%):**
antes de CADA pull se estima su costo (media observada de la celda si n≥5,
si no el prior medido de la tabla) y **no se arranca el pull si
gastado + estimado + US$0,01 (slack) > US$1,50** → parada limpia con parcial.
Además el chequeo duro gastado ≥ US$1,50 aborta (exit 2). El total proyectado
(gastado + Σ celdas restantes × estimado) se loguea cada 60 pulls para el
reporte honesto del veredicto.

**Tiempo estimado:** 45–60 min en background (throughput medido EXP70
~18 pulls/min; reintentos pueden variar). Marcado como estimación, no promesa.

## Sonnet (condicional pre-registrado)

Subset con sonnet **si y solo si** se completan los 1080 pulls con
gastado ≤ US$1,20 (margen real ≥ US$0,30): entonces 24 problemas del subset
pilot × 3 brazos × 1 intento = 72 pulls con el snapshot pineado de la familia
sonnet descubierto vía `GET /v1/models` al momento (registrado en el veredicto),
con proyección propia y parada si amenaza el remanente. Si no se cumple la
condición → diferido a presupuesto propio, sin improvisar. Escenario esperado
con la proyección actual: NO sonnet.

## Registry

Al cierre (completa o parcial): nueva entrada `anthropic` en
`alma_service/proveedores.yaml` (connector `custom.anthropic`, modelo pineado,
hosts `api.anthropic.com`, ping `https://api.anthropic.com/v1/models`) con dos
campañas: `exp70-piloto` (63 pulls, n=8/8/5 por celda, caveat de n) y
`exp67-claude-full` (esta corrida, n real por celda, caveat si parcial).
Edición por texto (preserva comentarios y procedencia), validada con
`registro.py::validar_documento` + `test_registro.py` en verde. Solo IDs y
estadísticas medidas — cero secretos por construcción.

## Gobernanza

No toca el servicio vivo (puerto 8471). No toca el núcleo (topes de gasto,
obligación de notificar). Si el freno amenaza: PARAR y reportar parcial,
sin improvisar (sin recortar max_tokens, sin cambiar de modelo, sin bajar
intentos a mitad de corrida).
