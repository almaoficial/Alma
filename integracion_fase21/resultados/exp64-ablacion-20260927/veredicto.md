# EXP64 — Veredicto: ablación del scaffold estilo Cherny

**Fecha**: 2026-09-27. **Costo**: US$0 (mock). **Sanidades**: bit-identidad
OK (ablación con flags apagados == referencia en 5/5), determinismo OK.

## Resultados (efecto de QUITAR vs control; + = quitar empeora)

Control medio: 81,80.

| Ablación | Efecto medio | IC95 | Peor en | Veredicto |
|---|---|---|---|---|
| (b) sin prior condicionado | +3,40 | [−2,91, +9,71] | 3/5 | NO load-bearing |
| (c) sin skip del probe | +6,00 | [−2,60, +14,60] | 3/5 | NO load-bearing |
| (d) sin gate adaptativo | +1,40 | [−0,86, +3,66] | 4/5 | NO load-bearing |
| (e) sin probe (Thompson pelado) | +9,80 | [+2,59, +17,01] | 5/5 | **LOAD-BEARING** |
| (f) mínimo total (prior uniforme) | +31,40 | [+24,24, +38,56] | 5/5 | **LOAD-BEARING** |

Criterio pre-registrado: load-bearing ssi media>0, IC95 sin cruzar el 0,
y peor en ≥4/5 réplicas.

## Diagnóstico honesto

1. **Ninguna pieza individual del probe carga el peso sola.** El prior
   condicionado, el skip y el gate no pasan el criterio — pero la
   maquinaria del probe **en conjunto** sí (+9,80, IC95 sin cruzar el 0,
   5/5). El valor está en la **interacción**, tal como pre-registraba el
   criterio para este caso.
2. **El prior con memoria es el componente más valioso.**
   Contraste post-hoc (f−e, mismos datos pareados): quitar la historia
   con decaimiento (n0=4) y dejar prior uniforme cuesta +21,60
   (IC95 [+12,12, +31,08], 5/5). Más del doble que todo el probe junto.
   Post-hoc pero aritméticamente limpio: (e) y (f) difieren solo en el prior.
3. **Cherny refutado en lo grande, escuchado en lo chico.** Pelar TODO al
   mínimo pierde por +31,40 con el IC más ajustado del experimento —
   el scaffold no es decoración. Pero tenía razón en el espíritu:
   ninguna pieza individual justifica su existencia por sí sola.
4. **Matices por réplica**: el prior condicionado no cambió NI UNA
   decisión en 2/5 réplicas (diffs 0,0); el skip salvó +15 en una réplica
   y costó −1 en otra — alta varianza, n=5 no da para más.

## Qué se conserva y qué se poda

- **Se conserva todo el scaffold.** El piso pierde por +31,40; no hay
  nada que podar sin pagar.
- **No se poda (b)/(c)/(d) todavía.** "No load-bearing con n=5" no es
  "inútil": los IC son anchos y el test no tiene potencia para piezas
  individuales. El skip (+6,00, CI [−2,60, +14,60]) es el candidato para
  un follow-up con más réplicas.
- **Lección de diseño**: el próximo esfuerzo de tuning va al prior
  (memoria con decaimiento), no al probe — ahí viven +21,6 puntos.
