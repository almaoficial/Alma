# EXP70 — Veredicto de medición: MEDICIÓN PARCIAL

Fecha: 2026-09-28. Pre-registro en `preregistro.md` (vara sagrada, escrita
antes de correr).

## Veredicto
**MEDICIÓN PARCIAL** — el freno duro cortó la corrida en 63/72 pulls (87,5%).
No se declara MEDICIÓN COMPLETA. No hay veredicto comparativo (la comparación
vs DeepSeek/OpenAI queda pendiente de datos completos).

## Ejecución
- Modelo: `claude-haiku-4-5-20251001` (descubierto vía GET /v1/models).
- Key: verificada (1 llamada mínima + /v1/models, cero 401/403 en 64 llamadas).
- Dry-run de scorers: VERDE antes de gastar.
- Duración: ~3,5 min. 0 truncadas por max_tokens reportadas como error
  (el backend cuenta `stop_reason=max_tokens`; ver pulls).

## Presupuesto: overshoot admitido
- **Gastado: US$0,1028 vs freno duro US$0,10 → +US$0,0028 (+2,8%).**
- Causa: el freno se chequea antes de cada pull (diseño heredado de
  pilot.py); un pull caro puede pasarlo. El pre-registro incluía regla de
  parada por proyección (parar si el run-rate proyectaba > US$0,095) que NO
  se aplicó durante la corrida en background — miss de ejecución, no de
  diseño. Consta para no repetirlo.
- La llamada mínima de verificación (~US$0,000035) está incluida en el total.

## Medición por celda (parcial — n indicado)

| celda | n | reward medio | costo medio/llamada | in medio | out medio |
|---|---|---|---|---|---|
| gsm8k/cot | 8 | 1,000 | US$0,001475 | 126 | 270 |
| gsm8k/reflexion | 8 | 1,000 | US$0,002150 | 164 | 397 |
| gsm8k/single | 8 | 0,375 | US$0,000178 | 111 | 13 |
| mmlu/cot | 8 | 1,000 | US$0,002055 | 135 | 384 |
| mmlu/reflexion | 8 | 1,000 | US$0,002794 | 173 | 524 |
| mmlu/single | 8 | 1,000 | US$0,000245 | 120 | 25 |
| mbpp/cot | 5 | 0,000 | US$0,002331 | 67 | 453 |
| mbpp/reflexion | 5 | 0,000 | US$0,003356 | 86 | 654 |
| mbpp/single | 5 | 0,000 | US$0,000637 | 55 | 116 |

Costo global medido: **US$0,001632/llamada** (63 llamadas).

## Pricing: verificado, sin diferencias
Precios oficiales leídos en vivo el 2026-09-28
(docs.anthropic.com/en/docs/about-claude/pricing): haiku-4-5 = **$1/$5 por
MTok**, igual que el estimado. La diferencia de costo efectivo (~10,7×
gpt-4o-mini por llamada, vs ~7× estimado por ratio de precios) viene de
**verbosidad**: Claude genera más tokens de salida que gpt-4o-mini en los
brazos cot/reflexion (out medio 270–654 vs ~130–170 estimados).

## Lecturas honestas (no veredicto)
1. En gsm8k y mmlu (celdas completas, n=8), el patrón replica a los otros
   proveedores: cot/reflexion perfectos, single flojo en gsm8k (0,375) y
   perfecto en mmlu (1,000).
2. En mbpp (n=5, parcial), **0,000 en los 3 brazos**: la hipótesis "Claude
   programa mejor y puede dar vuelta el slice de código" NO se sostiene en
   este subset — la debilidad en código parece independiente del modelo.
   Con n=5 es evidencia débil, no refutación.
3. Para el registry: las celdas gsm8k/mmlu (n=8) son medición limpia y
   semillable con caveat de n; las celdas mbpp (n=5) quedan como parciales.

## Follow-ups
- Completar los 9 pulls faltantes (3 problemas mbpp × 3 brazos): ~US$0,02,
  resume idempotente desde `claude_pulls.jsonl`. Requiere aprobación.
- Réplica completa del oráculo (1080 llamadas): ~US$1,20 en haiku — no
  recomendada sin aprobación separada.
- Sonnet: diferido (sin margen en el freno).
- `claude_summary.json` NO generado (el pre-registro lo prohíbe ante aborto
  por freno); los datos crudos semillables están en `claude_pulls.jsonl`.
