# ALMA-TRADING v2 — Preregistro de evaluación (papel)

**Escrito antes de la primera corrida v2. No se mueve.**

## Pregunta
¿Los tres cambios v2 (penalidad por churn en el EVI, prior con decaimiento,
universo sin sesgo de supervivencia) reparan el FAIL de la corrida 1
(ALMA −66% vs hold +97%, out-of-sample 2021–2026)?

## Cambios v2 (fijados antes de correr)
1. **Penalidad por churn en el EVI:** cambiar de brazo solo si
   `ganancia_probe > costo_cambio × umbral_evi + penalidad_churn`.
   La corrida 1 hizo 43 cambios de brazo (whipsaw: compraba el mejor de la
   ventana reciente, que en mercados laterales es el peor hacia adelante).
   La penalidad se calibra en in-sample junto a los otros parámetros.
2. **Prior con decaimiento (lección EXP9):** reemplaza al mapless "mejor
   global desde el día 0", que ancló en campeones del bull antes del bear
   2022. Decaimiento exponencial con vida media **fijada en 252 días
   hábiles (~1 año), NO calibrada** — un grado de libertad menos, por
   principio: lo reciente pesa más que lo viejo.
3. **Universo sin sesgo de supervivencia:** se agregan **XLE** (ETF energía:
   perdedor 2015–2020, ganador 2021–2022 — flip de régimen) y **GE**
   (colapso 2017–2018, recuperación parcial — perdedor sostenido).
   Elección estructural, no por su efecto en el veredicto (que no existe
   al escribir esto): son nombres grandes, líquidos y conocidos — no
   penny stocks oscuras elegidas para hacer fallar a ALMA (eso sería
   cherry-picking inverso). El sesgo residual declarado: sigue siendo
   large-cap USA líquido.

## Universo (fijado antes de correr)
SPY, QQQ, AAPL, MSFT, TSLA, XLE, GE — precios diarios ajustados
(Yahoo Finance, gratuitos, cacheados en `trading/data/`).
Período total: 2015-01-02 → 2026-09-25.

## Split temporal (sin mirar el futuro, idéntico a v1)
- **In-sample:** 2015-01-02 → 2020-12-31. Solo para calibrar 4 parámetros.
- **Out-of-sample:** 2021-01-01 → 2026-09-25. Solo para el veredicto.

## Brazos (una línea cada uno; ahora operan sobre 7 tickers)
- `hold`: buy & hold SPY (línea base, sin cambios).
- `momentum`: la de mejor retorno 63d entre los 7; si todas caen, efectivo.
- `reversion`: la perdedora de 21d entre los 7.
- `cash`: efectivo.

## Costos (iguales para todos, sin excepciones)
0,10% por pata operada sobre el nocional. Sin apalancamiento, sin cortos.

## Calibración (solo in-sample)
Grilla: ventana_probe ∈ {42, 63}, umbral_evi ∈ {2, 3, 5},
umbral_cd ∈ {1.5, 2.0, 2.5}, penalidad_churn ∈ {0.0, 0.005, 0.01}.
Se elige la combinación con mayor retorno neto in-sample. 54 combinaciones
(más que las 18 de v1: riesgo de sobreajuste mayor, declarado abajo).
Luego se congelan. La vida media del prior (252d) NO se calibra.

## Métricas del veredicto (out-of-sample)
Retorno neto total, Sharpe anualizado (rf=0), máximo drawdown
(definición v1: pico/p − 1, comparable entre versiones).
Capital inicial US$10.000 en papel para todos.

## Criterio de veredicto (numérico, pre-registrado, IDÉNTICO a v1)
**PASS** si y solo si, en out-of-sample:
1. retorno_neto(ALMA) > retorno_neto(hold), **y**
2. max_drawdown(ALMA) ≤ 1.2 × max_drawdown(hold).

Si no: **FAIL**. La vara no se mueve entre versiones: cambiar el criterio
después de un FAIL sería mover el arco. v2 tiene que ganar con la misma vara.

## Riesgos de sobreajuste (declarados antes)
1. 4 parámetros / 54 combinaciones en 6 años in-sample: más riesgo que v1.
   Mitigado por grillas chicas por parámetro, vida media fijada (no
   calibrada) y out-of-sample de 5,7 años.
2. El universo sigue siendo large-cap USA líquido; no es "la bolsa".
3. `hold` de SPY en 2021–2026 fue un gran mercado alcista: la vara es alta.
4. Costos de 10bps optimistas para retail chico; el veredicto es techo.
5. Papel: sin impacto de mercado, impuestos ni emociones.
   Ningún PASS acá autoriza dinero real. El guardián de `banco_papel.py`
   sigue vigente y su auto-chequeo debe pasar antes de correr.

## Nota de comparabilidad
v1 y v2 difieren en universo (5→7 tickers) y mecanismo (prior, EVI).
El veredicto v2 se lee contra la vara v1, no como "mejora probada sobre v1":
son experimentos distintos con el mismo criterio.
