# ALMA-TRADING — Preregistro de evaluación (papel)

**Escrito antes de la primera corrida. No se mueve.**

## Pregunta
¿El loop ALMA (probe con costo + detección de cambios + transferencia mapless)
aplicado a trading en papel supera al buy-and-hold en datos que nunca vio?

## Universo (fijado antes de correr)
SPY, QQQ, AAPL, MSFT, TSLA — precios diarios ajustados (Yahoo Finance, gratuitos).
Período total: 2015-01-02 → 2026-09-25.

## Split temporal (sin mirar el futuro)
- **In-sample:** 2015-01-02 → 2020-12-31. Solo para calibrar 3 parámetros.
- **Out-of-sample:** 2021-01-01 → 2026-09-25. Solo para el veredicto. La corrida
  de evaluación usa historia desde 2015 (pasado real al momento de decidir),
  pero las métricas del veredicto se calculan únicamente sobre out-of-sample.

## Brazos (estrategias de una línea)
- `hold`: buy & hold SPY (línea base).
- `momentum`: tener la de mejor retorno 63d; si todas caen, efectivo.
- `reversion`: comprar la perdedora de 21d.
- `cash`: efectivo.

## Costos (iguales para todos, sin excepciones)
0,10% por pata operada sobre el nocional. Sin apalancamiento, sin cortos.

## Calibración (solo in-sample)
Grilla: ventana_probe ∈ {42, 63}, umbral_evi ∈ {2, 3, 5}, umbral_cd ∈ {1.5, 2.0, 2.5}.
Se elige la combinación con mayor retorno neto in-sample. Grilla chica a propósito:
3 parámetros, 18 combinaciones. Luego se congelan.

## Métricas del veredicto (out-of-sample)
Retorno neto total, Sharpe anualizado (rf=0), máximo drawdown. Capital inicial
US$10.000 en papel para todos.

## Criterio de veredicto (numérico, pre-registrado)
**PASS** si y solo si, en out-of-sample:
1. retorno_neto(ALMA) > retorno_neto(hold), **y**
2. max_drawdown(ALMA) ≤ 1.2 × max_drawdown(hold) (no ganar asumiendo locuras).

Si no: **FAIL**. Sin grises, sin mover la vara.

## Riesgos de sobreajuste (declarados antes)
1. El universo tiene sesgo de supervivencia (5 ganadores conocidos a posteriori).
   El veredicto vale *condicionado* a este universo; no es "la bolsa".
2. 3 parámetros calibrados en 6 años in-sample: riesgo moderado, mitigado por
   la grilla chica y el out-of-sample de 5.7 años (~68 decisiones mensuales).
3. `hold` de SPY en 2021-2026 fue un gran mercado alcista: la vara es alta.
4. Costos de 10bps son optimistas para retail chico; el veredicto es techo, no piso.
5. Esto es papel: sin impacto de mercado, sin impuestos, sin emociones.
   Ningún PASS acá autoriza dinero real.
