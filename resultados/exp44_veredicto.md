# ALMA-EXP44 — Veredicto: FAIL (fase mock)

**Fecha:** 2026-09-27 ~15:05 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Pre-registro:** `resultados/exp44-20260927/preregistro.json` (escrito antes de correr)
**Stream:** 94 unidades reales del feed de Muse (2026-09-22 → 2026-09-27), 30 categorías;
se usan los 90 más antiguos (9 bloques completos de 10 items; los 4 del 27/9 quedan fuera).
**Oráculo:** la categoría publicada por el feed (verdad barata y real).
**Brazos mock:** titular / contexto / mayoria / estable — estrategias SIMULADAS con tasas
por categoría; lo que se testea es la maquinaria de selección sobre un stream real no
estacionario, no la clasificación en sí.

## Primera corrida: oráculo degenerado (descartada, documentada)

La primera corrida usó un `tasas.json` cuyas 30 categorías reales caían todas en
`por_defecto` (titular=contexto=0,6 idénticos en todo). El veredicto (FAIL, +5,4) no era
informativo: con un oráculo plano, la "mejor fija" es ruido. Se calibró el oráculo a las
30 categorías reales con diferenciales genuinos entre brazos (titular fuerte en
tech/deportes, contexto fuerte en dinero/negocios, siguiendo las descripciones de los
brazos) y se re-corrió con pre-registro nuevo. La vara no se movió.

## Números (corrida calibrada)

| Réplica | efecto (reg_alma − reg_mejor_fija) | mejor fija |
|---|---|---|
| 1 | +7,00 | titular |
| 2 | +11,00 | contexto |
| 3 | +7,00 | contexto |
| 4 | +5,00 | titular |
| 5 | +4,00 | contexto |

**Efecto medio: +6,80 → FAIL** (vara: media(efecto) < 0).

## Diagnóstico estructural (datos reales, no mock)

Categoría dominante por bloque:
`ai research → ai industry → auto-mejora de ia → finanzas → inteligencia artificial →
ingresos con ia → inglés → inteligencia artificial → agentes ia`
— **la dominante cambia en 8/8 transiciones**. El feed rota sus intereses en cada
bloque de 10 items: el mundo se mueve más rápido de lo que cualquier maquinaria con
probe puede seguir.

La mejor fija varía por réplica (titular ×2, contexto ×3) porque titular y contexto
empatan en el total: titular gana los bloques tech/deportes, contexto los de
dinero/negocios, y la rotación decide. ALMA paga probe en cada bloque y nunca se
asienta: con 10 items por bloque y un ganador que rota cada bloque, la exploración es
puro costo.

## Honestidad incómoda

El FAIL no dice que la maquinaria esté rota: dice que **el problema está mal
planteado para una bandida con bloques de 10**. El stream real tiene 30 categorías y
una rotación de intereses total por bloque. Ninguna política de selección —ALMA o no—
puede extraer ventaja ahí: el mejor fijo ya empata y ALMA paga el costo de aprender.

## Veredicto

**FAIL.** La pregunta 1 de la agenda ("¿rinde cuando el mundo se mueve?") recibe otra
respuesta incómoda: cuando el mundo se mueve *tan rápido*, la respuesta es no — y no
hay maquinaria que lo arregle sin cambiar el problema (bloques más largos, menos
categorías, o brazos que difieran dentro del bloque).

## Consecuencia para EXP44b (fase con key)

El spec de la fase con modelos reales (`resultados/exp44b-20260927/SPEC_FASE_KEY.md`,
~US$0,02, 5–10 min) sigue válido técnicamente, pero el mock calibrado sugiere que el
diseño actual produciría un FAIL caro: mediría con plata real lo que el mock ya
diagnosticó gratis. **Recomendación: no aprobar EXP44b con este diseño.** Si se quiere
el run real, hay que rediseñar primero (p. ej. bloques de 30 items / 3 bloques, o
colapsar a ~8 categorías gruesas) con pre-registro propio.
