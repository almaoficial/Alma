# EXP41 — Veredicto: FAIL

**Fecha:** 2026-09-27 · **Modo:** mock, replay puro, US$0 · **Duración:** 0.2s
**Pre-registro:** `resultados/exp41-20260927/preregistro.json` (escrito antes de correr)
**Código:** `run_experiment41.py`
**Datos calibración:** Coinbase BTC-USD 1h público, 720 velas, 2026-07-29 17:00 UTC → 2026-08-28 16:00 UTC (`data_exp41/btc_h1_calib.json`)
**Datos test:** idénticos a EXP36–40 (Kraken XBTUSD 1h, 720 velas, 719 retornos)

## Diseño
EXP40 dejó el umbral sin calibrar (pecado declarado). EXP41 barre ventana
W ∈ {24, 72, 168} × umbral T ∈ {0.50…0.70} en un período DISTINTO,
elige por precisión balanceada (desempate: menor W, luego menor T),
congela (W*, T*) y testea la política condicional de EXP40 en el stream
original. Sin lookahead en ninguna etapa.

## Criterios pre-registrados
(a) acierto del clasificador en test (bloques 1..29) > 55%.
(b) P&L(EXP41) > P&L(buyhold). PASS iff (a) y (b).

## Números

Calibración (período distinto): **(W*=24, T*=0.68)**,
bal.acc=0.6753 (recall tendencia=0.71,
recall lateral=0.64); bloques-tendencia
verdaderos en calibración: 7/29.

Test (stream original):
- (a) clasificador: **14/29 = 48.3%** (umbral 55%) → **NO CUMPLE**
  (tendencia clasificada en 8, verdad ex-post 7, TP 0)
- (b) P&L: EXP41 **-13.5766%** vs buyhold **+8.5041%** → **NO CUMPLE**

**→ FAIL.** el Hurst calibrado fuera de muestra no discrimina régimen a esta escala (<= 55%): la conclusión pre-registrada es que no tiene señal explotable y hay que cambiar de familia de test.

## Diagnóstico
- La calibración mejoró la moneda
  en muestra distinta (bal.acc=0.675).
- La ganancia de calibración NO sobrevivió al cambio de período: el umbral calibrado no generaliza.

## Honestidad incómoda
1. **Fuente distinta en calibración** (Coinbase BTC-USD vs Kraken XBTUSD en
   test): ambos son BTC/USD spot horario y la microestructura es la misma
   familia, pero la calibración no es estrictamente "misma fuente".
2. **n=1 en test**: sigue siendo una ventana de 30 días con drift +8,55%
   que favorece a buyhold; el ranking vive dentro de ese sample.
3. **La verdad ex-post (|retorno| > 2%) es cruda**: mide utilidad, no verdad
   en sentido Hurst — un bloque puede ser persistente sin superar el 2%.
4. **33 combos en 29 bloques**: la calibración puede sobreajustar ruido;
   si (W*,T*) es un pico aislado en la tabla, desconfiar.
5. **Fidelidad verificada**: (W=72,T=0.55) reproduce EXP40
   (P&L=-10.7313%, hits=14/29); Hurst en RW sintético=0.595.

## Addendum post-hoc (no pre-registrado, diagnóstico)
Revisada la tabla de calibración: los 8 mejores combos son TODOS W=24
(la ventana más ruidosa: 23 retornos para estimar Hurst). No es un pico
aislado en T sino una columna entera elevada en muestra — patrón típico
de sobreajuste a ruido en 29 bloques, no de señal. En test esa misma
columna colapsó a TP=0. Refuerza la conclusión: a esta escala y con este
n, el R/S no deja señal que calibrar.
