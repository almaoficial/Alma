# EXP19 — Veredicto: ¿la SELECCIÓN es lo que hace funcionar al enjambre?

**Veredicto: PASS** (criterio pre-registrado, sin mover el arco; sin cambio de signo entre seeds → confiable por la regla EXP16).

## Números (media de 4 seeds, mock puro, US$0)

| Brazo | F1 (calidad) | Llamadas | E = F1/1000 llamadas |
|---|---|---|---|
| Enjambre CON probe | 0,4807 | 232 | **0,0940** |
| Agente individual (azar) | 0,2770 | 120 | 0,0554 |
| Enjambre por voto (7×) | **0,5164** | 840 | 0,0148 |

E_probe > E_individual en las 4 seeds (diffs +0,045, +0,029, +0,035, +0,045 — siempre positivo). E_probe ≈ 6,4× E_voto.

## Lectura honesta

1. **La selección sí es lo que hace funcionar al enjambre — por unidad de costo.** El probe (16 etiquetados, 112 llamadas) compra un agente mejor que el azar de forma consistente, y a escala (M=5000) ese overhead se vuelve despreciable.
2. **Pero el probe es ruidoso: solo encontró al mejor agente (F) en 2/4 seeds** (las otras 2 eligió a D, el segundo mejor). La victoria no vino de la optimalidad sino de "mejor que el promedio". Esto replica la lección de EXP6: el probe decide con ruido.
3. **El enjambre ingenuo NO es inútil: tiene el mejor F1 crudo (0,5164).** En calidad pura, votar le gana al probe. Lo que lo mata es el costo 7×. La frase precisa: *escalar sin selección iguala en calidad pero quema cómputo; la selección es lo que lo vuelve eficiente.*
4. **Caveats:** agentes = tablas fijas de TPR/TNR, no LLMs (errores independientes; con LLMs reales los errores correlacionan y el voto rendiría menos). El mock no prueba agentes de verdad, prueba la lógica de selección.

## Conexión con las noticias del 26/9

El enjambre de ~950 agentes de Anthropic funciona porque hay filtrado/selección detrás, no por mero número. Y del lado oscuro (agentes de OpenAI actuando solos): un probe que evalúa y selecciona es también la forma más barata de *auditar* a qué agente le das el trabajo — la selección como control, no solo como optimización.
