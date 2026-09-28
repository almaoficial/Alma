# Veredicto: ALMA-EXP61 — techo del proveedor generativo (skills como priors)

**Fecha:** 2026-09-27 ~16:40 EDT · **Modo:** mock (US$0,00)
**Pre-registro:** `exp61_oraculo/preregistro.md` (criterio: PASS ssi efecto < −1,0)

## Qué se testeó

El rediseño post-fase-1: la skill deja de ser prosa inyectada al prompt
(fase 1 FAIL: diferencia conductual guiada−raw = 0,000) y pasa a ser
**parámetros del prior por firma** que el resolver consume numéricamente.
EXP61 midió el TECHO de esa vía: un proveedor oráculo con abstracción
perfecta (medias verdaderas por grupo) vs el scaffold global fijo
evolucionado (SC_EVO: n0=4, umbral_base=1, umbral_divisor=3, gate 0,0,
decay 0,5). Un solo moving part: el prior condicionado a la firma, mismo
peso n0=4 (se comparó CALIDAD de información, no peso).

## Números

- Réplicas pareadas: 5 (control = `e56.correr_replica_param` verbatim)
- Chequeo bit-identidad (oráculo off): OK 5/5
- Chequeo magnitudes control: [71, 83, 90, 84, 81] ✓ (rango 70–95)
- **Efecto medio: +0,40** (por réplica: +2, +2, +3, −2, −3; 3/5 en contra)
- Distancia a la mejor fija: trat −2,00 vs ctrl −2,40
- Diagnóstico early (bloques 0–11) vs late (12–23): el oráculo no gana ni
  siquiera en bloques tempranos, donde el prior del control es más ruidoso
  (early: 0, +2, 0, 0, −1)

## Veredicto

**FAIL** (criterio pre-registrado: efecto < −1,0; observado +0,40)

Ni la abstracción perfecta mueve la aguja. El prior condicionado a la firma
aprendido del historial con olvido ya es tan bueno como la información
perfecta: con n0=4 y 10 items por bloque, el prior se diluye rápido y el
trabajo real lo hacen el Thompson + el probe + el skip. El valor nunca
estuvo en la precisión del prior.

## Consecuencia (pre-registrada)

Se **archiva la vía del proveedor generativo**. El sistema real conserva:
scaffold fijo evolucionado (n0=4, umbral_base=1), memoria con olvido
0,5^d, detector de recurrencia, Curator. **Ningún LLM genera skills** —
ni en prosa (fase 1: 0,000) ni en parámetros (EXP61: +0,40).

El rediseño post-fase-1 queda respondido por la negativa con números, sin
gastar un centavo de key (regla mock-first): el mock respondió la pregunta
del techo, así que la fase 1b con proveedor real no se propone.

## Honestidad incómoda

El resultado es contraintuitivo: darle al sistema la verdad perfecta no lo
mejora. Eso habla bien del scaffold evolucionado (el prior aprendido ya
captura lo capturable) y clausura una intuición atractiva — "un LLM que
abstrae mejores priors" — que sin este test habría justificado gasto real.
El control sigue siendo el mejor punto de toda la línea (EXP57/59/60/61).
