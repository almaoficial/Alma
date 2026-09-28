# ALMA EXP25 — Veredicto: hipótesis REFUTADA (con hallazgo estructural)

**Pregunta:** ¿cuántos pulls necesita el probe para que la transferencia sea confiable?
**Respuesta honesta:** la pregunta asumía que más medición → más confiabilidad. Los datos dicen lo contrario.

## La curva (4 seeds nuevas [2521–2524] por presupuesto, 100% mock, US$0)

| k | stream | probe v2 | vecino | cero (diag.) | veredicto |
|---|--------|----------|--------|--------------|-----------|
| 8 | 120 | 4,90 | 13,00 | 5,25 | **PASS** |
| 16 | 144 | 7,25 | 13,60 | 11,35 | NO CONFIABLE |
| 32 | 192 | 19,10 | 21,05 | 6,80 | NO CONFIABLE |
| 64 | 288 | 27,10 | 35,70 | 6,70 | NO CONFIABLE |

Diffs probe−vecino: k=8 [−2,8, −17,8, −3,8, −8,0] (sin cambio de signo);
k=16/32/64 todos con cambio de signo. Regla de confiabilidad pre-registrada aplicada por presupuesto.

## Por qué la hipótesis se refuta (mecánica verificada en los números)

1. **Medir cuesta linealmente.** Cada pull del probe en los dos brazos equivocados
   cuesta (0,90−0,78)=0,12 y (0,90−0,65)=0,25 → 0,37k de regret clavado por medir.
   En k=64 son ~23,7 de regret solo por la fase de medición. El regret por pull
   del probe EMPEORA con k: 0,041 → 0,050 → 0,100 → 0,094.
2. **El horizonte largo disuelve la transferencia.** El Thompson desde cero mejora
   con el horizonte (0,044 → 0,023 por pull); en k=64 le gana al probe 4×
   (6,7 vs 27,1). El horizonte que justificaría un probe grande es exactamente
   el horizonte donde ya no necesitás transferir: aprendés desde cero igual.
3. **El sweet spot es k chico + fallback adaptativo.** En k=8 el probe acertó el
   brazo 3/4 y en 3/4 fue a adaptativo (gaps 0,125); el fallback contuvo el daño
   del error. Transferencia sirve donde no te alcanza el horizonte para aprender.

## Calibración honesta del PASS en k=8

El PASS vale intra-set (regla pre-registrada cumplida), pero EXP24 con OTRAS
seeds dio NO CONFIABLE para el mismo mecanismo en k=8. El veredicto k=8 es
frágil entre sets de seeds. Lo estructuralmente robusto: (1) el costo lineal
de medir, (2) cero domina a horizonte largo, (3) el vecino es reliably malo
(probe ≤ vecino en 15/16 celdas).

## Lectura final (contradicción TRIZ)

Mejorar la medición (X) destruye el valor de lo medido (Y): cuanto más gastás
en decidir de quién pedir prestado, menos vale el préstamo — porque el
horizonte que lo justifica te habría alcanzado para aprender solo.
**La transferencia no se repara midiendo más. Se repara midiendo POCO y con
fallback adaptativo, o no se repara.** La herida sigue abierta, pero ahora con
diagnóstico económico, no solo estadístico.

## Archivos

- `preregistro.json` — hipótesis, presupuestos, criterio por presupuesto (escrito antes de correr)
- `report.json` — tabla presupuesto × seed con diffs, gaps, compromisos, aciertos
- Script re-ejecutable: `~/workspace/alma-prototype/run_experiment25.py`
