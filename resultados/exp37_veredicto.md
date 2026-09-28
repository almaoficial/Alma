# EXP37 — Veredicto: FAIL

**Fecha:** 2026-09-27 · **Modo:** mock, replay puro, US$0 · **Duración:** <1s
**Pre-registro:** `resultados/exp37-20260927/preregistro.json` (escrito antes de correr)
**Código:** `run_experiment37.py` · **Datos:** idénticos a EXP36 (Kraken XBTUSD 1h, 720 velas, 719 retornos)

## Cambios pre-registrados vs EXP36
- (a) Desempate del probe hacia `flat` si la brecha (mejor − 2.º mejor, medias ajustadas) < **UMBRAL_SENAL = 0.02**.
- (b) **CAMBIO_PENAL = 0.01** a todo brazo distinto del brazo final del bloque anterior; sin brecha clara → bloque completo en `flat` (sin Thompson, sin exploración), re-evaluable en el re-probe.

## Criterio pre-registrado
P&L neto total(ALMA37) > P&L neto total(mejor fija). Sin mover la vara.

## Números
| Política | P&L total | 1ra mitad (lateral −0,89%) | 2da mitad (tendencia +9,35%) |
|---|---|---|---|
| **ALMA37** | **+0,700%** | −2,144% | +2,844% |
| ALMA (EXP36) | +8,458% | −4,213% | +12,671% |
| buyhold (mejor fija) | **+8,504%** | −0,481% | +8,985% |
| meanrev | +2,954% | −3,769% | +6,723% |
| flat | +0,000% | +0,000% | +0,000% |
| momentum | −18,534% | −3,811% | −14,723% |

**Diff ALMA37 − mejor fija: −7,804%. → FAIL.**

**Criterio secundario:** recorta sangrado = **SÍ** (−2,14% vs −4,21% de EXP36); no pierde tendencia = **NO** (+2,84% vs +12,67% de EXP36).

## Diagnóstico
- **Mitad 1 (lateral): el mecanismo funcionó.** 12/15 bloques terminaron en `flat`; el sangrado se recortó a la mitad (−2,14% vs −4,21%). El desempate a flat hace lo que prometía donde no hay señal.
- **Mitad 2 (tendencia): el mecanismo la mató.** 14/15 bloques en `flat`. Las brechas del probe en la mitad en tendencia fueron 0.000–0.019 (solo un bloque llegó a 0.091): **un probe de 3–5 horas no distingue una tendencia de +0,026%/h del ruido**. El umbral 0.02, heredado del MARGEN de EXP36 sin calibrar, quedó inalcanzable.
- **Trampa de histéresis (culpa del cambio b):** una vez en `flat`, la penalización por cambio (−0.01 a todo lo que no sea flat) hizo que flat se auto-perpetúe. El costo de exploración, en vez de disciplinar la exploración, la prohibió justo cuando el probe sí empezaba a ver algo (bloques con brecha 0.013–0.019 quedaron en flat por el penal).
- Re-probe cambió la decisión en 4/30 bloques (vs 7/30 en EXP36): con flat-trap, el re-probe casi no tiene nada que corregir.

## Honestidad incómoda
1. **n=1.** Una historia realizada de 30 días. Test de existencia, no prueba.
2. **El umbral no se calibró:** se heredó 0.02 del MARGEN de EXP36, que medía otra cosa (desempate entre brazos, no "hay señal o no"). Un umbral de detección necesita su propia calibración contra el ruido del probe — no la tuvo.
3. **Los dos cambios no se separaron:** (a) y (b) corrieron juntos, así que el FAIL no dice cuál de los dos rompió la mitad 2. El diagnóstico apunta a la interacción (umbral alto + penal que traba la salida de flat), pero es inferencia, no medición.
4. **buyhold ganó de arriba otra vez:** la ventana driftó +8,55%. El ranking depende del sample, igual que en EXP36.
5. **El remedio fue peor que la enfermedad en total:** EXP36 perdía por 0,05%; EXP37 pierde por 7,8%. Endurecer la regla sin calibrar el detector destruyó exactamente la capacidad que EXP36 tenía (capturar tendencia).

## Próxima idea servida
EXP38: separar los cambios y calibrar el detector — (1) correr (a) solo, sin penalización por cambio, para aislar el efecto; (2) calibrar el umbral de "hay señal" contra el ruido del propio probe (p. ej. brecha mínima = k × error estándar de las medias del probe, pre-registrado) en vez de un número heredado. Si ni así el probe de 3–5h detecta la tendencia, la conclusión es la que EXP36 anticipó: el probe necesita un test de régimen previo (p. ej. filtro de volatilidad/tendencia realizada) antes de elegir brazo.
