# EXP66 — Fase A: minería de firmas de fallo (US$0)

**Fuente**: `exp62_deepseek/oraculo.json` (1080 celdas reales deepseek-flash) +
`exp62_deepseek/experiencias.jsonl` (1743 filas). Minero: `alma_service/debilidades.py`
(coincidencia exacta, describe — no prescribe).

## 1. Firmas del ORÁCULO: casi no hay

Solo 3/120 celdas con ganador ≠ single. Inspección celda por celda:

| celda | bloque (clase) | ganador | detalle |
|---|---|---|---|
| 6 | 0 (puzzles) | cot | single [0.2,0.2,0.2], cot **[0.19, 0.94, 0.19]**, reflexion [0.05,0.05,0.05] |
| 29 | 2 (depuracion) | cot | single [0.2,0.2,0.2], cot **[0.94,0.94,0.94]**, reflexion [0.8,0.8,0.8] |
| 91 | 7 (calculo) | cot | single [0.2,0.2,0.2], cot **[0.94,0.19,0.19]**, reflexion [0.05,0.8,0.05] |

**Firma descriptiva**: 2 de las 3 "victorias" de cot son un ÚNICO intento
afortunado (0.94) entre 3 — el argmax sobre 3 intentos premia outliers.
Solo la celda 29 (depuración) es una victoria consistente de cot.
La "heterogeneidad" del oráculo es en 2/3 ruido de medición, no señal.

## 2. Firmas de DECISIÓN de la política (las accionables)

`alma-full` (90 pulls): elige single 40, cot 35, reflexion 15.
Casi todos los no-single son fallos (oráculo: single 117/120).

Top firmas de fallo de `alma-full` — (clase, elegido, tramo de costo):

- (logica, cot, barato) ×6 · (conocimiento, cot, barato) ×5 ·
  (puzzles, cot, barato) ×4 · (traduccion, cot, barato) ×4 ·
  (codigo, cot, barato) ×4 · (depuracion, cot, barato) ×3 ·
  (depuracion, reflexion, barato) ×3 · (resumen, reflexion, barato) ×3 ·
  (resumen, cot, barato) ×3 · (herramientas, cot, barato) ×2 ·
  (calculo, cot, barato) ×2 · (logica, reflexion, barato) ×2

**Firma dominante (colapsada por clase)**: `(alma-full, *, cot|reflexion, fallo)` —
Thompson elige el brazo caro cuando el oráculo dice single. Soporte: ~50/90
pulls. El costo por fallo es chico ("barato": <0.3), pero la frecuencia lo
vuelve load-bearing: regret total alma-full 4.82.

**Firma de mecanismo** (del código, no del minero): el probe eligió single
10/10, pero `correr_alma_full` NUNCA usa `elegido` para condicionar el bandit —
solo le suma 3 rewards por brazo. El warm-start (n0=2, medias
0.758/0.696/0.552) deja las posteriores solapadas y Thompson explora.
**El probe acierta y nadie lo escucha.**

Regret por bloque (alma-full): b1 (qa_multihop) 1.16 y b7 (calculo) 1.17
los peores — donde Thompson más exploró.

## 3. Paquete de evidencia

La firma más fuerte y accionable: **Thompson-con-warm-start ignora al probe
y explora cot/reflexion contra un oráculo single 117/120**.
Edición propuesta (una sola): anclar el prior de Thompson al ganador del
probe — ver `preregistro.md`.
