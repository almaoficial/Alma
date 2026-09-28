# EXP39 — Veredicto: FAIL

**Fecha:** 2026-09-27 · **Modo:** mock, replay puro, US$0 · **Duración:** <1s
**Pre-registro:** `resultados/exp39-20260927/preregistro.json` (escrito antes de correr)
**Código:** `run_experiment39.py` · **Datos:** idénticos a EXP36/37/38 (Kraken XBTUSD 1h, 720 velas, 719 retornos)
**Réplicas:** 6 · **Reglas:** 3 (EXP36 original, EXP37 penal+flat, EXP38 desempate calibrado)

## Diseño
Common random numbers: dentro de cada réplica, las tres reglas usan el
mismo namespace de semilla de Thompson (`exp39-r{r}-{b}-{h}`). El
probe/spy es determinista, así que la diferencia intra-réplica entre
reglas es efecto-regla puro (más la divergencia de estado del bandit que
cada regla induce, que es parte de la regla). Réplicas distintas usan
semillas distintas.

**Fidelidad verificada antes de correr:** con los namespaces originales
(`exp36-`, `exp37-`, `exp38-`), las tres funciones replican los números
oficiales a 4 decimales (+8,4578% / +0,7001% / −2,5157%).

## Criterio pre-registrado
efecto = P&L_regla(réplica) − P&L_buyhold. PASS si alguna regla tiene
media(efecto) > 0 y media(efecto) − 1×desvío(efecto) > −0,01. Sin mover la vara.

## Tabla regla × réplica (P&L total; buyhold fijo +8,5041%)

| Réplica | regla36 (EXP36) | regla37 (EXP37) | regla38 (EXP38) |
|---|---|---|---|
| r0 | −0,828% | −1,694% | −3,049% |
| r1 | −2,036% | +1,757% | −5,905% |
| r2 | −2,998% | +1,016% | −4,553% |
| r3 | +22,040% | +8,427% | +18,944% |
| r4 | +9,511% | +2,777% | +7,781% |
| r5 | +12,473% | +5,952% | +8,695% |
| **media(efecto)** | **−2,144%** | **−5,465%** | **−4,852%** |
| **desvío** | ±10,029% | ±3,625% | ±9,797% |
| **media − 1sd** | −12,173% | −9,090% | −14,649% |

**→ FAIL.** Ninguna regla cumple media > 0.

## Hallazgos (esto sí es medición, no lotería)

1. **El CRN funcionó: el ranking intra-réplica es consistente.**
   regla38 < regla36 en **6/6** réplicas; regla37 < regla36 en **5/6**.
   Las dos "correcciones" pierden contra la regla original casi siempre,
   con el mismo camino aleatorio. El diagnóstico de EXP37 ("el remedio fue
   peor que la enfermedad") **sobrevive** al CRN; la sospecha de EXP38 de
   que ese diagnóstico era artefacto de semilla **queda refutada**.
2. **La semilla sigue dominando.** Desvío entre réplicas de ±10 puntos
   para regla36/38 con la regla fija. El efecto-regla neto (diferencias de
   2–3 puntos entre reglas) vive dentro del ruido de semilla.
3. **El outlier r3 es suerte de camino, no de regla.** En r3, regla36 hizo
   +15,35% en la mitad en tendencia (buyhold: +8,99%): el sorteo montó la
   tendencia con meanrev/momentum. Misma regla, otra semilla (r0): −7,17%
   en la mitad lateral.
4. **Ninguna variante de ALMA le gana a no hacer nada en promedio.**
   buyhold (+8,50%) supera la media de las tres reglas en las 6 réplicas.
   En este stream, con este horizonte, la adaptación activa destruye valor
   en promedio aunque a veces ligue la tendencia.

## Honestidad incómoda

1. **El CRN arregla la semilla, no el sample.** Sigue siendo UNA historia
   realizada de 30 días que driftó +8,55%. Todo el ranking vive adentro de
   esa ventana. Seis réplicas del camino aleatorio no son seis mundos.
2. **El CRN no es un control perfecto.** En regla37 Thompson a veces no
   corre (bloques en flat), así que los estados del bandit divergen entre
   reglas; la comparación intra-réplica incluye esa divergencia. Es parte
   de la regla, pero "misma semilla" no significa "mismo experimento".
3. **6 réplicas es poco para ±10 puntos de desvío.** Las medias son
   ruidosas; lo sólido es el ranking intra-réplica (6/6 y 5/6), no los
   valores puntuales.
4. **La vara era exigente y aun así no hubo pelea.** El umbral
   (media−1sd > −1%) no importó: las tres medias son negativas de movida.
   No hay "casi pasa" que lamentar.
5. **Pregunta de fondo intacta:** como anticipó EXP38, sin un test de
   régimen previo al probe no hay qué decidir; EXP39 confirma que ninguna
   variante del desempate cambia esa conclusión. El próximo paso honesto
   es el test de régimen, no otra variante del desempate.

## Archivos
- Reporte JSON + pre-registro: `~/workspace/alma-prototype/resultados/exp39-20260927/`
- Código: `~/workspace/alma-prototype/run_experiment39.py`
