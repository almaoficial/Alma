# ARENA ALMA-trading — Tabla de posiciones (papel)

Campeón defensor inicial: **reversión fija** (+265,9% en 2021–2026).
**Campeón actual: ALMA v3**

Protocolo: `ARENA_PREREGISTRO.md` (pre-registrado, sin mover). 5 ventanas no solapadas; cada retador calibra solo con datos anteriores a la ventana. Período efectivo por ventana: inicio+126 días hábiles → fin.

| Competidor | 2016–2017 (ret / dd) | 2018–2019 (ret / dd) | 2020–2021 (ret / dd) | 2022–2023 (ret / dd) | 2024–2026 (ret / dd) | Ret medio | DD medio |
|---|---|---|---|---|---|---|---|
| ALMA v1 | +27.4% / 0.24 | +16.5% / 0.64 | +121.9% / 0.51 | -3.7% / 0.61 | +45.8% / 1.00 | +41.6% | 0.60 |
| ALMA v2 | +27.4% / 0.24 | +16.5% / 0.64 | +129.7% / 0.51 | -3.7% / 0.61 | +81.4% / 1.00 | +50.3% | 0.60 |
| ALMA v3 👑 | +27.6% / 0.05 | +17.5% / 0.11 | +66.7% / 0.59 | +15.0% / 0.24 | +5.9% / 0.31 | +26.5% | 0.26 |
| fijo_hold | +27.6% / 0.05 | +18.2% / 0.25 | +49.9% / 0.10 | +22.8% / 0.21 | +36.3% / 0.24 | +30.9% | 0.17 |
| fijo_momentum | +52.5% / 0.24 | -2.8% / 1.08 | +190.1% / 0.59 | +21.7% / 0.36 | +16.2% / 1.15 | +55.5% | 0.69 |
| fijo_reversion | +18.5% / 0.21 | -39.3% / 1.48 | +57.7% / 0.37 | +5.1% / 1.88 | +103.1% / 0.32 | +29.0% | 0.85 |
| fijo_cash | +0.0% / 0.00 | +0.0% / 0.00 | +0.0% / 0.00 | +0.0% / 0.00 | +0.0% / 0.00 | +0.0% | 0.00 |

## Asaltos por el título

- **ALMA v1** vs reversion: 2/5 ventanas → no destrona.
  - 2016-01-01→2017-12-31: ✓ (ret +27.4% vs +18.5%, dd 0.24 vs 0.21)
  - 2018-01-01→2019-12-31: ✓ (ret +16.5% vs -39.3%, dd 0.64 vs 1.48)
  - 2020-01-01→2021-12-31: ✗ (ret +121.9% vs +57.7%, dd 0.51 vs 0.37)
  - 2022-01-01→2023-12-31: ✗ (ret -3.7% vs +5.1%, dd 0.61 vs 1.88)
  - 2024-01-01→2026-09-25: ✗ (ret +45.8% vs +103.1%, dd 1.00 vs 0.32)
- **ALMA v2** vs reversion: 2/5 ventanas → no destrona.
  - 2016-01-01→2017-12-31: ✓ (ret +27.4% vs +18.5%, dd 0.24 vs 0.21)
  - 2018-01-01→2019-12-31: ✓ (ret +16.5% vs -39.3%, dd 0.64 vs 1.48)
  - 2020-01-01→2021-12-31: ✗ (ret +129.7% vs +57.7%, dd 0.51 vs 0.37)
  - 2022-01-01→2023-12-31: ✗ (ret -3.7% vs +5.1%, dd 0.61 vs 1.88)
  - 2024-01-01→2026-09-25: ✗ (ret +81.4% vs +103.1%, dd 1.00 vs 0.32)
- **ALMA v3** vs reversion: 3/5 ventanas → 🏆 TOMA EL TÍTULO.
  - 2016-01-01→2017-12-31: ✓ (ret +27.6% vs +18.5%, dd 0.05 vs 0.21)
  - 2018-01-01→2019-12-31: ✓ (ret +17.5% vs -39.3%, dd 0.11 vs 1.48)
  - 2020-01-01→2021-12-31: ✗ (ret +66.7% vs +57.7%, dd 0.59 vs 0.37)
  - 2022-01-01→2023-12-31: ✓ (ret +15.0% vs +5.1%, dd 0.24 vs 1.88)
  - 2024-01-01→2026-09-25: ✗ (ret +5.9% vs +103.1%, dd 0.31 vs 0.32)

## Cómo entra un retador nuevo (v3, v4, ...)

1. Agregar una entrada a `RETADORES` en `arena.py` con `factory` (firma `f(precios, fechas, **params) -> (banco, decisiones)`) y `grilla` de calibración.
2. Correr `python3 arena.py`. La tabla se regenera sola; el nuevo retador reta al campeón vigente en último lugar.

_Papel: ningún resultado autoriza dinero real._
