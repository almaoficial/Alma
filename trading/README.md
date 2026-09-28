# ALMA-trading (papel)

Paper trading con el loop ALMA sobre datos históricos reales. **Solo papel:**
`banco_papel.py` se niega a operar con dinero real (`DineroRealProhibido`).

## Estructura
- `datos.py` — carga CSVs cacheados (Yahoo Finance) de SPY, QQQ, AAPL, MSFT, TSLA 2015→2026.
- `estrategias.py` — 4 brazos de una línea: hold, momentum, reversion, cash.
- `banco_papel.py` — portafolio en papel + costos 10bps/pata + guardián anti-dinero-real.
- `alma_trading.py` — el loop: probe en ventana reciente → EVI (cambiar solo si la
  ganancia supera el costo x umbral) → detección de cambios (re-probe forzado si
  z < -umbral) → prior mapless (mejor global hasta hoy) → olvido (solo ventanas).
- `evaluar.py` — protocolo pre-registrado: calibra 3 parámetros en 2015-2020,
  congela, veredicto en 2021-2026 contra buy-and-hold SPY.
- `PREREGISTRO.md` — protocolo y criterio, escrito antes de la primera corrida.

## Correr
```
cd ~/workspace/alma-prototype/trading
python3 evaluar.py
```
US$0: cómputo local + datos gratuitos ya descargados. Sin API keys.

## Veredicto corrida 1 (2026-09-27)
**FAIL.** Out-of-sample 2021-2026, parámetros congelados (vp=63, evi=5.0, cd=2.0):

| Sistema | Retorno neto | Sharpe | MaxDD |
|---|---|---|---|
| ALMA | -66% | -0.25 | 4.51 |
| hold (SPY) | +97% | +0.79 | 0.35 |
| momentum | -14% | +0.12 | 1.26 |
| reversion | +181% | +0.63 | 1.38 |
| cash | 0% | 0.00 | 0.00 |

Criterio pre-registrado: ret(ALMA)>ret(hold) y maxDD(ALMA)≤1.2×maxDD(hold).
Ambas condiciones fallan. No se movió la vara.

## Diagnóstico honesto
1. **Whipsaw:** 29 cambios de brazo en 69 decisiones (42%). El probe compra el
   mejor brazo de los últimos 63 días, que en mercados laterales suele ser el
   peor hacia adelante: comprar techos y vender pisos, entre estrategias.
   El brazo `reversion` solo hizo +181%; ALMA lo eligió 66 veces y terminó -66%.
   El switching destruyó el valor.
2. **Sobreajuste de régimen:** calibrado en 2015-2020 (bull histórico, TSLA x10).
   La grilla de calibración salió casi plana (28.39–28.59 en los 18 combos):
   no discriminó nada, los parámetros "congelados" son arbitrarios.
3. **El prior mapless muerde en flips grandes:** empezar por "lo que mejor
   funcionó en general" ancló en los campeones del bull justo antes del bear
   2022 — el mecanismo "creencia confiadamente equivocada" de EXP32, ahora con
   datos reales de mercado.
4. Universo con sesgo de supervivencia; costos de 10bps optimistas; papel ≠ real
   (sin impacto de mercado, sin impuestos, sin emociones).

## Qué seguiría (no hecho)
- Penalizar el churn en el EVI (el costo de cambiar subestima el whipsaw).
- Prior mapless con decaimiento (EXP9) en vez de mejor-global-histórico.
- Más brazos descorrelacionados y universo sin sesgo de supervivencia.
- Nada de esto autoriza dinero real: primero PASS en papel, después se habla.
