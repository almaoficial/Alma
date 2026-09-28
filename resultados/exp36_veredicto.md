# EXP36 — Veredicto: FAIL

**Fecha:** 2026-09-27 · **Modo:** mock, replay puro, US$0 · **Duración:** <1s
**Pre-registro:** `resultados/exp36-20260927/preregistro.json` (escrito antes de correr)
**Código:** `run_experiment36.py` · **Datos:** Kraken público XBTUSD 1h, 720 velas (2026-08-28 → 2026-09-27)

## Criterio pre-registrado
P&L neto total(ALMA) > P&L neto total(mejor estrategia fija). Sin mover la vara.

## Números
| Política | P&L total | 1ra mitad (lateral −0,89%) | 2da mitad (tendencia +9,35%) |
|---|---|---|---|
| **ALMA** (probe continuo + re-probe + olvido) | **+8,458%** | −4,213% | **+12,671%** |
| buyhold (mejor fija) | **+8,504%** | −0,481% | +8,985% |
| meanrev | +2,954% | −3,769% | +6,723% |
| flat | +0,000% | +0,000% | +0,000% |
| momentum | −18,534% | −3,811% | −14,723% |

**Diff ALMA − mejor fija: −0,046%. → FAIL.**

## Diagnóstico
- **Mitad 2 (tendencia): ALMA ganó.** +12,67% vs +8,99% de buyhold. El probe + olvido concentró la elección (7 meanrev, 4 buyhold, 3 momentum en 15 bloques) y capturó el régimen. La adaptación funciona cuando hay señal.
- **Mitad 1 (lateral): ALMA sangró.** −4,21% vs −0,48% de buyhold y 0% de flat. Sin señal, el probe no encontró ganador (6 momentum, 5 meanrev, 3 buyhold, 1 flat) y Thompson siguió explorando perdedores. El brazo `flat` existía pero la maquinaria casi nunca lo eligió.
- **Falla de diseño honesta:** el desempate de la regla del probe ("si no hay brecha, quedate con el favorito del prior") defaulteó a orden de lista (`momentum` primero) en vez de al brazo seguro (`flat`). En régimen sin señal, explorar cuesta.
- Re-probe cambió la decisión en 7/30 bloques (2 en mitad 1, 5 en mitad 2): el re-probe trabajó más donde había régimen que detectar.

## Honestidad incómoda
1. **n=1.** Una historia realizada de 30 días. Sin poder estadístico: es test de existencia, no prueba.
2. **buyhold ganó de arriba:** la ventana elegida driftó +8,55%. En 30 días bajistas, la "mejor fija" sería `flat` y el ranking cambiaría. El veredicto depende del sample.
3. **El momentum horario en BTC tiene reversión a la media a 1h** (microestructura): −18,5% no es mala suerte, es esperable. El experimento lo redescubrió solo.
4. **ALMA ≈ buyhold en total (−0,05%) pero por caminos opuestos:** buyhold no hizo nada y ligó el drift; ALMA trabajó, ganó la mitad 2 y perdió la mitad 1 explorando. Adaptarse tiene costo cuando no hay nada que adaptarse.

## Próxima idea servida
EXP37: mismo stream, dos cambios pre-registrados — (a) desempate del probe hacia `flat` cuando no hay brecha (hipótesis: recorta el sangrado en lateral sin tocar la mitad en tendencia); (b) costo de exploración explícito en la regla. Si (a) no mueve la mitad 1, la conclusión es que el probe necesita un test de "hay señal o no" antes de elegir.
