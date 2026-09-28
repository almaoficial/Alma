# EXP70 — Piloto de medición de Claude para el registry (pre-registro)

Fecha: 2026-09-28. Pedido del usuario ("Hagamos"): medir a Claude sobre los
problemas del EXP67 para sembrar el registry de proveedores con datos medidos
(tercer proveedor junto a DeepSeek y OpenAI).

## Pregunta
¿Se puede medir limpiamente reward por brazo por slice + costo por llamada de
Claude (haiku) con el mismo diseño de los pilotos EXP67/69?

## Diseño
- Subset `pilot` del manifiesto: PRIMEROS 8 problemas de cada slice en el
  orden pre-registrado del manifiesto (8 gsm8k / 8 mmlu / 8 mbpp, sin
  cherry-picking) × 3 brazos (single/cot/reflexion, prompting disciplina
  EXP1-9) × 1 intento = **72 llamadas**.
- Modelo: `claude-haiku-4-5-20251001` (snapshot pineado, descubierto vía
  GET /v1/models el 2026-09-28; el alias `claude-haiku-4-5` no figuraba en el
  listado). max_tokens por brazo 256/1024/2048 (presupuestos EXP62/EXP69).
- Métrica de reward: `puntuar()` binario 0/1 — idéntica a oráculo y pilotos
  EXP67/69 (éxito del verificador numero/letra/codigo).
- Costo por llamada: medido de `usage` (input/output tokens) × precios
  oficiales verificados en vivo el 2026-09-28
  (docs.anthropic.com/en/docs/about-claude/pricing): haiku-4-5 = $1/$5 por MTok.
- Auth: solo surrogate del vault (`custom.anthropic`); la key nunca toca disco.
- Idempotencia: pulls keyed por (fase="exp70-claude", pid, arm, intento);
  resume limpio; freno aborta con parcial sin resumen ni veredicto.

## Desviaciones honestas vs el pedido literal
1. El pedido mencionaba "los 180 problemas del oráculo" (180×3×2 = 1080
   llamadas). Con pricing verificado, 1080 llamadas en haiku costarían
   ~US$1,20 — 12× el freno aprobado de US$0,10. Se mide el subset pilot
   (espejo exacto del diseño EXP69) en versión reducida por presupuesto.
   La réplica completa del oráculo en Claude queda como follow-up con
   presupuesto propio (~US$1,20), NO recomendada sin aprobación separada.
2. N_INTENTOS=1 (no 2): mismo motivo de presupuesto.
3. Estimado del padre (US$0,03–0,06): con costos medidos del piloto OpenAI
   (US$0,000153/llamada) × ratio de precios verificado (~7,3×), 72 llamadas
   proyectan ~US$0,065–0,081 — dentro del freno US$0,10 con margen para
   reintentos, apenas por encima del estimado. La diferencia se explica:
   haiku cuesta ~7× gpt-4o-mini por token.
4. Sonnet diferido: con haiku en ~US$0,08 no queda margen útil para sonnet
   ($2/$10 = 2× haiku) dentro del freno. Follow-up con presupuesto propio.

## Criterio de éxito (vara pre-registrada — medición, NO comparativa)
MEDICIÓN COMPLETA si TODAS:
1. 72/72 pulls completados sin 401/403 (la key anda: verificada 2026-09-28
   con 1 llamada mínima + GET /v1/models).
2. Scorers verificados en dry-run antes de gastar.
3. `claude_summary.json` generado con reward/arm/slice + costo medido por
   llamada, en formato apto para sembrar el registry.
NO hay veredicto comparativo: la comparación contra DeepSeek/OpenAI (y la
decisión del router) viene después, con estos datos como insumo.

## Presupuesto
Freno duro US$0,10 (default del script). Monitoreo: si el run-rate proyecta
> US$0,095, se para antes del freno. Aborto limpio → parcial sin resumen.
Verificación de key: 1 llamada mínima (~US$0,000035, ya gastada).
Tiempo estimado: 4–8 min en segundo plano.

## Gobernanza
Claude es el tercer proveedor del registry: solo IDs + estadísticas medidas,
nunca secretos. Este piloto no toca el servicio vivo ni promociona nada.
