# EXP38 — Veredicto: FAIL

**Fecha:** 2026-09-27 · **Modo:** mock, replay puro, US$0 · **Duración:** <1s
**Pre-registro:** `resultados/exp38-20260927/preregistro.json` (escrito antes de correr)
**Código:** `run_experiment38.py` · **Datos:** idénticos a EXP36/37 (Kraken XBTUSD 1h, 720 velas, 719 retornos)

## Cambios pre-registrados vs EXP36
- Solo (a): desempate del probe hacia `flat` cuando no hay brecha clara. **Sin** penal por cambio (b): la estructura del bloque es la de EXP36 (probe → Thompson → re-probe → Thompson).
- Umbral calibrado contra el ruido del propio probe: señal clara iff `gap > K_SENAL × se_gap`, con `K_SENAL = 1.0` pre-registrado; `se_gap` estimado de las observaciones del probe de cada decisión (3 obs/brazo en q1, 5 en el re-probe).

## Criterio pre-registrado
P&L neto total(ALMA38) > P&L neto total(mejor fija). Sin mover la vara.

## Números (corrida pre-registrada)
| Política | P&L total | 1ra mitad (lateral −0,89%) | 2da mitad (tendencia +9,35%) |
|---|---|---|---|
| **ALMA38** | **−2,516%** | +5,263% | −7,778% |
| buyhold (mejor fija) | **+8,504%** | −0,481% | +8,985% |
| meanrev | +2,954% | −3,769% | +6,723% |
| flat | +0,000% | +0,000% | +0,000% |
| momentum | −18,534% | −3,811% | −14,723% |

**Diff ALMA38 − mejor fija: −11,020%. → FAIL.**

**Criterio secundario:** recorta sangrado = **SÍ** (+5,26% vs −4,21% de EXP36); retiene tendencia = **NO** (−7,78% vs +12,67% de EXP36). **Pero ver honestidad incómoda §3: estas mitades no miden la regla.**

## Diagnóstico del detector calibrado
- El detector hizo lo que se le pidió: 24/30 bloques con señal débil (probe en flat), gap medio 0,016 vs umbral medio 0,029. Un probe de 3–5 horas **genuinamente no distingue** una tendencia de +0,026%/h del ruido: la calibración confirma el diagnóstico de EXP37 en vez de refutarlo.
- Re-probe cambió la decisión en 4/30 bloques.
- El único bloque con señal fuerte (b18, gap 0,1006 > umbral 0,0561) eligió `meanrev`.

## Hallazgo real de EXP38 (no es sobre la regla)
Al aislar (a) apareció el verdadero cuello de botella: **el camino aleatorio de Thompson domina el resultado, no la regla del probe.** Misma regla, mismos datos, solo cambia la semilla del Thompson:

| Regla \ semilla | exp36 | exp37 | exp38 | seedX |
|---|---|---|---|---|
| EXP36 (a+b de EXP36) | **+8,458%** (oficial) | — | — | — |
| EXP37 (a+b endurecido) | +5,665% | **+0,700%** (oficial) | +8,039% | +7,923% |
| EXP38 (solo a, calibrado) | +5,336% | −6,593% | **−2,516%** (oficial) | +8,207% |

buyhold fijo: +8,504% en todos los casos.

Lectura: la regla mueve ±1–2 puntos; la semilla mueve **±7 puntos**. La regla nunca fue la restricción activa.

## Honestidad incómoda
1. **n=1, y encima lotería de semilla.** Una historia realizada de 30 días × un camino aleatorio de Thompson. El FAIL pre-registrado se sostiene (las 4 semillas quedan bajo buyhold), pero **ninguna** comparación entre reglas de la serie 36/37/38 es válida: cada experimento usó un namespace de semilla distinto (`exp36-`, `exp37-`, `exp38-`), así que las diferencias EXP36 vs EXP37 vs EXP38 mezclan efecto-regla con efecto-semilla.
2. **El diagnóstico de EXP37 probablemente sea artefacto de semilla.** Con la semilla `exp38`, la regla de EXP37 (la "que mató la tendencia") da +8,04%, a 0,5 puntos de buyhold. El "14/15 bloques en flat mató la mitad 2" se escribió mirando un solo camino aleatorio.
3. **El secundario de EXP38 no mide nada.** El "recorta sangrado SÍ / retiene tendencia NO" se invierte con otra semilla (seedX: H1 +2,98%, H2 +5,23%). Lo reporto porque estaba pre-registrado; no lo creo.
4. **El detector calibrado funciona y no alcanza.** Incluso bien calibrado (k=1 contra el propio ruido), el probe de 3–5h casi nunca ve señal. La conclusión de EXP37 se mantiene: sin un test de régimen previo, el probe no tiene qué decidir.
5. **buyhold ganó de arriba otra vez:** la ventana driftó +8,55%. El ranking depende del sample, igual que en EXP36/37.
6. Con seedX, ALMA38 llega a +8,21% (lo más cerca que estuvo ALMA de buyhold). No lo festejo: es suerte de semilla y el criterio pre-registrado no era ese.

## Próxima idea servida
EXP39: **arreglar la medición antes de tocar otra regla.** Re-correr las tres reglas (EXP36, EXP37, EXP38) bajo *common random numbers* — mismo namespace de semilla de Thompson para las tres — y reportar el efecto-regla neto de la varianza de semilla, con 4+ semillas. Sin eso, cualquier veredicto sobre reglas del probe es ruido con formato de número. Recién después tiene sentido volver a la pregunta de fondo (test de régimen previo al probe).
