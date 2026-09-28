# ALMA EXP24 — Veredicto: **NO CONFIABLE** (con hallazgos de mecanismo)

**Pregunta:** ¿el probe consciente de ruido de ALMA v2 repara la transferencia
donde el probe ciego de v1 falló?
**Respuesta:** no de forma confiable. El antídoto funciona como diseñado, pero
la rotura se movió de lugar.

## Diseño ejecutado (pre-registrado antes de correr)
Trampa idéntica a EXP21 (5 clases, C1 a d=0.04 de N con mejor brazo distinto),
120 pulls por estrategia, 4 seeds nuevas [2421–2424], umbral 0.15
(`motor.py UMBRAL_RUIDO_DEFAULT`). Tres brazos pre-registrados + 1 diagnóstico:
- **(a) probe v1**: réplica exacta EXP21 — 8×3 probe, compromiso duro ×96.
- **(b) probe v2**: mismo probe; gap=m1−m2; si gap>0.15 compromiso duro;
  si no, Thompson adaptativo con priors del probe + re-probe cada 24 pulls.
- **(c) vecino manual**: single (trampa) ×120.
- **(d) desde cero** (diagnóstico, fuera del criterio): Thompson ×120.
100% mock, US$0, cero llamadas a API.

## Números
| Estrategia | Regret medio (4 seeds) |
|---|---|
| (b) probe v2 noise-aware | **8,1** |
| (a) probe v1 duro | 8,5 |
| (d) desde cero (diag.) | 5,0 |
| (c) vecino manual | 17,75 |

Diffs v2−v1 por seed: **−2,0 / −7,0 / +4,2 / +3,2** → cambio de signo →
**NO CONFIABLE** (regla pre-registrada). Diffs v2−vecino: −16,0 / 0,0 / −14,8 / −7,8
(sin cambio de signo: v2 le gana al vecino en las 4).
Compromisos v2: duro, duro, adaptativo, adaptativo.

## Lectura honesta: la rotura se movió
1. **El mecanismo disparó exactamente donde debía.** En las seeds 2423/2424 el
   gap fue 0,125 (el valor exacto del fallo de EXP21) y v2 fue a adaptativo en
   ambas, evitando el compromiso ciego. El antídoto funciona como diseñado.
2. **Pero la adaptatividad es un seguro con prima.** En esas mismas seeds el
   probe había acertado (cot), y el compromiso ciego de v1 —con suerte en la
   explotación (regret −1,0 en 2423)— le ganó a la exploración cuidadosa de v2
   (3,2 y 8,2). Evitar la catástrofe cuesta exploración cuando no hay catástrofe.
3. **El umbral no atrapa al probe seguro-pero-equivocado.** Seed 2422: el probe
   midió gap 0,25 a favor de single (el brazo trampa) y v2 se comprometió igual
   que v1. Con 8 pulls, un evento de cola cruza cualquier umbral razonable:
   ningún umbral distingue "suerte-equivocada" de "confianza-correcta". Ruido
   irreducible — eco de EXP6.
4. **Sub-hallazgo confiable:** v2 ≤ vecino en las 4 seeds. La transferencia por
   vecino es reliably mala (la trampa funcionó 4/4) y v2 la evita siempre. Lo que
   no se establece es si v2 supera a v1.
5. **Desde cero sigue competitivo** (5,0, diagnóstico): Thompson sin memoria le
   gana a ambos probes en la media. La exploración adaptativa sin compromiso
   previo sigue siendo el rival a batir — mismo mensaje que EXP21.

## Comparación explícita vs EXP21
| | EXP21 (seeds 2121–24) | EXP24 (seeds 2421–24) |
|---|---|---|
| probe v1 media | 10,0 | 8,5 |
| vecino media | 13,5 | 17,75 |
| desde cero media | 7,5 | 5,0 |
| probe v2 media | — | 8,1 |
| veredicto | NO CONFIABLE | **NO CONFIABLE** |

Comparación cualitativa (seeds distintas, no pareada): el patrón rima — el ruido
del probe domina, desde-cero compite. Lo nuevo: v2 desplaza el modo de fallo
(compromiso marginal → exploración con prima; pero no cubre cola segura-
equivocada) sin resolverlo de forma confiable. **La transferencia sigue siendo
la herida abierta de ALMA.**

## Archivos
- `preregistro.json` — hipótesis, umbral documentado, criterio (escrito antes de correr)
- `report.json` — tabla numérica por seed + comparación EXP21
- `veredictos-exp24.md` — este archivo
- Script re-ejecutable: `~/workspace/alma-prototype/run_experiment24.py`
