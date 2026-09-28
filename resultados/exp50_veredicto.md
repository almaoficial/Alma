# ALMA-EXP50 — Veredicto: CONTINÚA (mock dirimente)

**Fecha:** 2026-09-27 ~15:25 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Pre-registro:** `resultados/exp50-20260927/preregistro.json` (escrito antes de correr)

## Qué se testea

La pregunta abierta de EXP49: la baja de misfires (2/14 vs 14/38) vino de
SALTAR MUCHO MENOS, no de saltar mejor. ¿El efecto medio (−1,80) viene de
elegir bien los saltos (la skill aporta) o simplemente de saltar menos?

- **Tratamiento:** skip-endurecido de EXP49 importado verbatim.
- **Control ("skip-aleatorio"):** salta la MISMA cantidad de bloques por
  réplica que el tratamiento (N_t(r) matcheado: 4, 0, 0, 5, 5), pero
  eligiendo QUÉ bloques al azar entre los elegibles (21 bloques donde la
  skill existe). En los bloques saltados juega el brazo de la skill con la
  misma contabilidad honesta; el azar decide QUÉ bloques, no QUÉ brazo.
  Un solo moving part: la regla de selección.

**Criterio pre-registrado** (efecto = reg_trat − reg_azar; umbral 1,0 ≈ 1 SE
del ruido entre réplicas de EXP49, fijado antes de correr):
- |media| < 1,0 → EMPATE → CIERRE (el valor estaba en saltar menos)
- media ≤ −1,0 → GANA SKILL → CONTINÚA (la selectividad aporta valor real)
- media ≥ +1,0 → GANA AZAR → CIERRE (la selectividad es contraproducente)

## Números

| Réplica | efecto | reg trat | reg azar | skips trat (mis) | skips azar (mis) |
|---|---|---|---|---|---|
| 0 | −13,00 | 81,0 | 94,0 | 4 (1) | 4 (2) |
| 1 | +0,00 | 88,0 | 88,0 | 0 (—) | 0 (—) |
| 2 | +0,00 | 92,0 | 92,0 | 0 (—) | 0 (—) |
| 3 | −9,00 | 97,0 | 106,0 | 5 (0) | 5 (3) |
| 4 | −12,00 | 82,0 | 94,0 | 5 (1) | 5 (5) |

**Efecto medio: −6,80 → GANA SKILL** (−6,80 ≤ −1,0, con margen amplio).
**Misfires:** tratamiento 2/14 (0,143) vs skip-aleatorio 10/14 (0,714).
Tasa de saltos matcheada por réplica (verificación): (4,4), (0,0), (0,0),
(5,5), (5,5). **Reproducibilidad del tratamiento vs EXP49: True.**
Regret medio: tratamiento 88,00 · skip-aleatorio 94,80 · mejor fija 84,20.
Media del efecto sin la mejor réplica: −5,25 (no cargado por una sola).

Detalle de saltos y diagnóstico por bloque (rep 0):
`resultados/exp50-20260927/report.json`.

## Honestidad incómoda

1. **El −6,8 está inflado por un baseline débil.** El efecto es mucho más
   grande que el −1,8 de EXP49, pero la mayor parte no viene de que la skill
   sea excelente: viene de que el control aleatorio es pésimo (94,8 vs 84,2
   de la mejor fija — 10 puntos peor). El dirimente mide "cuánto peor es
   saltar al azar" tanto como "cuánto mejor es la skill". La respuesta a la
   pregunta sigue siendo "elegir bien", pero el tamaño del número no es
   mérito puro de la skill.
2. **La tasa base es brutal y la skill la navega bien.** Entre los bloques
   elegibles, el brazo de la skill es el mejor ex post solo ~29% de las
   veces (el azar misfirea 71%). La skill, con su umbral de soporte,
   encuentra esos bloques con 86% de precisión (misfire 14%). La
   selectividad es real y grande en términos relativos: 14% vs 71%.
3. **El efecto vive en 3 de 5 réplicas.** En las réplicas 1 y 2 el
   mecanismo no saltó ni una vez (efecto 0, abstención total). Sin la mejor
   réplica (−13,00) la media sigue en −5,25 — distribuido, pero con el 40%
   de las réplicas en cero.
4. **El diagnóstico estructural no se mueve.** Tratamiento 88,0 vs mejor
   fija 84,2: 3,8 puntos abajo. Sexta marca seguida de la línea en el mismo
   rango (~4–7 puntos bajo la mejor fija). La skill elige bien *entre los
   bloques donde salta*, pero el costo del probe residual y la exploración
   siguen ahí.
5. **Condición de alcance intacta:** todo ocurre en el mundo construido con
   recurrencia garantizada. En el feed real (rotación 8/8) el mecanismo
   seguiría sin activarse ni una vez.

## Veredicto

**CONTINÚA.** Las regiones pre-registradas son exhaustivas y mutuamente
excluyentes; caímos en GANA SKILL con margen amplio (−6,80 ≤ −1,0). La
pregunta dirimente tiene respuesta: **el valor está en elegir bien, no en
saltar menos.** Con la misma tasa de abstención, la selectividad de la
skill vale 6,8 puntos sobre elegir los bloques al azar, y el azar misfirea
5 veces más (71% vs 14%).

**Dictamen: LA LÍNEA DE SKILLS SIGUE ABIERTA** (regla pre-registrada,
sin ambigüedad).

## Recomendación

La pregunta de la selectividad quedó dirimida; no más mocks sobre *qué*
bloques saltear. El próximo mock debería atacar lo que la línea nunca
movió: la distancia a la mejor fija (~4 puntos). El residuo está en el
probe de los bloques no saltados y en la exploración — ahí vive el
regret que ninguna variante de skip tocó en seis experimentos.
