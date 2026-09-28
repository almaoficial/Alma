# EXP42 — Veredicto: PASS

**Fecha:** 2026-09-27 · **Modo:** mock, replay puro, US$0 · **Duración:** 0.6s
**Pre-registro:** `resultados/exp42-20260927/preregistro.json` (escrito antes de correr)
**Código:** `run_experiment42.py`
**Datos:** Coinbase Exchange público (BTC-USD/ETH-USD/SOL-USD, 1h), 888 velas
por ventana (168 lookback + 720 stream), `data_exp42/W{1,3,4,5,6}.json`

## Diseño
La serie 36–41 corrió sobre una sola ventana (n=1). EXP42 evalúa políticas
congeladas en 5 ventanas efectivas (K planeado=6): W1 BTC 2026-08-28→09-27
(ancla = EXP36), W3 BTC 2026-01-15→02-14, W4 ETH 2026-08-28→09-27,
W5 ETH 2026-04-01→05-01, W6 SOL 2026-08-28→09-27. Políticas: buyhold
(referencia), flat, regla36 (probe EXP36, CRN por ventana, R=4 réplicas),
regimen_adx (ADX-14 Wilder sobre 168h previas, umbral 25: tendencia→momentum,
si no→flat; determinista, congelado). Costo 1bp. Sin lookahead.

## Criterio pre-registrado
PASS iff alguna política no-buyhold tiene media(efecto) > 0 y
media − 1×desvío > −0.02 a través de ventanas, con
efecto = P&L_política − P&L_buyhold por ventana (media de 4 réplicas).

## Números

Efecto vs buyhold por ventana (media de 4 réplicas):

| ventana | buyhold | flat | regla36 | regimen_adx |
|---|---|---|---|---|
| W1 BTC ago-sep | +8.49% | −8.49% | −3.92% | −19.77% |
| W3 BTC ene-feb | −32.50% | +32.50% | +48.11% | +28.91% |
| W4 ETH ago-sep | +7.75% | −7.75% | +22.94% | −11.29% |
| W5 ETH abr-may | +7.62% | −7.62% | +28.84% | −19.57% |
| W6 SOL ago-sep | +11.84% | −11.84% | +19.82% | −28.53% |

Resumen (media ± desvío a través de ventanas):
- flat: media −0.64%, sd 18.61% → media−1sd −19.25% → no pasa
- **regla36: media +23.16%, sd 18.70% → media−1sd +4.46% > −2% → PASA**
- regimen_adx: media −10.05%, sd 22.62% → media−1sd −32.67% → no pasa

**→ PASS** (criterio pre-registrado cumplido, vara intacta).

## Diagnóstico post-hoc (no pre-registrado, decisivo)
La política regla36 puntúa las 5h de probe de cada bloque con el brazo
ganador **elegido con los datos de esas mismas horas** (diseño heredado de
EXP36: `fijar(PROBE_Q1, elegido1)`). Diagnóstico: re-correr idéntico pero
puntuando las horas de probe con flat (el probe CUESTA, sin asignación
retroactiva):

| ventana | regla36 (efecto) | regla36 probe-honesto (efecto) |
|---|---|---|
| W1 | −3.92% | −11.04% |
| W3 | +48.11% | +20.80% |
| W4 | +22.94% | −12.17% |
| W5 | +28.84% | +0.09% |
| W6 | +19.82% | −19.68% |
| **media** | **+23.16%** | **−4.40%** |

El PASS entero vive en la asignación retroactiva del probe. Sin ella, la
media cae a −4.40%: **regla36 no generaliza; la "habilidad de selección"
medida es el artefacto, no la adaptación.** En W3 (crash −32.5%) hasta el
probe honesto gana (+20.8%), pero menos que flat (+32.5%): en crashes gana
no estar, no el probe.

## Honestidad incómoda
1. **El PASS es técnico, no sustantivo.** El criterio se cumplió al pie de
   la letra, pero el diagnóstico muestra que mide el artefacto del probe,
   no selección adaptativa. La hipótesis de generalización queda
   **refutada**, no confirmada.
2. **W3 infla la media** (+48.11% en el crash): sin W3 la media es +16.92%,
   todavía positiva — pero el diagnóstico la desarma igual (probe-honesto
   sin W3: −11.2%).
3. **K=5, todo cripto, todo 2026, ventanas elegidas por mí**: sesgo de
   selección de períodos; n chico; un solo asset-class.
4. **Ruido de semilla intacto**: réplicas de regla36 en W1 van de −10.25%
   a −0.05% (±5pp intra-ventana); el ancla W1 da −3.92% acá vs −0.05% en
   EXP36 — lotería de semillas, consistente con EXP39.
5. **regimen_adx, la única adaptativa sin probe** (determinista), pierde en
   4/5 ventanas (media −10.05%): sin el artefacto, ninguna adaptación le
   gana a buyhold en este dominio.
6. **Fuentes**: las 6 ventanas salieron de Coinbase (Kraken descartado:
   verificado que ignora `since` y devuelve solo ~720 velas recientes).
   W2 excluida por hueco real de 5h en Coinbase (2026-05-08 02:00–06:00
   UTC); K=5 pre-registrado. W1 re-alineada a 17:00 UTC para calzar con
   EXP36 (corr. de retornos 0.9992).

## Conclusión
El laboratorio tiene su respuesta a "dónde": en este dominio (cripto
horario, 2026), con contabilidad honesta del probe, **ninguna política
adaptativa le gana a buyhold de forma generalizable**. El próximo
experimento (EXP43) debe pre-registrar contabilidad honesta del probe
(probe = costo) antes de probar otra regla: sin eso, cualquier PASS futuro
es sospechoso por construcción.
