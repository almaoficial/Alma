# ALMA-EXP17 — veredictos (26/9/2026)

Re-verificación multi-seed (seeds pre-registradas 1721, 1722, 1723, 1724) de
EXP12–EXP15 en modo mock (US$0, sin llamadas a la API). Oráculo fijo: las 720
mediciones api de EXP12. Stream fijo: idéntico a EXP12 (assert en scripts).

**Corrección al registro:** el brief de EXP17 decía que EXP12–15 "dieron PASS".
Falso: los cuatro `report.json` registran `"pasa": false`. La pregunta honesta
fue si los FAIL de una sola seed se sostienen multi-seed.

## Resultados por experimento

| Exp | Criterio pre-registrado | api 1 seed | mock 4 seeds (pasa) | Rango regret | Veredicto EXP17 |
|-----|------------------------|------------|---------------------|--------------|-----------------|
| 12 | alma < mejor fija (4,12) | FAIL (8,615) | PASS ×4 (v1: −5,24/−10,20/−4,64/−0,75) | 9,45 | **NO CONFIABLE** |
| 13 | v2 < v1 y v2 < mejor fija | FAIL (4,615) | FAIL, FAIL, PASS, PASS | 5,28 | **NO CONFIABLE** |
| 14 | sueño < control | FAIL (7,525 vs 7,075) | PASS, FAIL, FAIL, PASS (diffs −5,5/+1,41/+0,63/−1,12) | 5,21 | **NO CONFIABLE** |
| 15 | eps ≤ v2 + 0,5 (refutación) | FAIL refut. (diff 4,04) | FAIL refut. ×4 (diffs 9,6/15,76/7,95/10,61) | 4,74 (eps) | **SOSTIENE** |

## Lectura honesta

- **EXP12:** el mock y el api cuentan historias opuestas (mock: v1 le gana a la
  fija en las 4 seeds; api: pierde por 4,5). La diferencia no es solo la seed:
  es el régimen de rewards — sintéticos bien calibrados (el probe estima bien)
  vs ruido real de LLM. El número no es firme en ningún modo. NO CONFIABLE.
- **EXP13:** el veredicto cambia con la seed (2 FAIL / 2 PASS). Ni la dirección
  es estable. NO CONFIABLE.
- **EXP14:** la "fase sueño" a veces ayuda mucho (−5,5) y a veces empeora
  (+1,41): el signo del efecto depende de la seed. Puro ruido. NO CONFIABLE.
  (La hipótesis del sueño ya estaba refutada en api; el mock no la resucita.)
- **EXP15:** el único veredicto estable. La refutación (un epsilon-greedy tonto
  empata a ALMA v2) fracasa en api y en las 4 seeds mock, siempre por amplio
  margen (mínimo 7,95 vs margen de equivalencia 0,5). **"La complejidad paga"
  sobrevive multi-seed.** El número exacto no es firme (rango 4,74), pero la
  dirección del veredicto sí.

## Conclusión

De los cuatro experimentos, solo EXP15 tiene un veredicto que se sostiene.
EXP12–14 son ruido de seed: sus FAIL api no se pueden leer como conclusiones,
pero tampoco sus versiones mock como reversiones. Lo único firme es el mapa
de incertidumbre, no los números.

Archivos: `preregistro.json`, `reporte-exp17.json`,
`seed{1721,1722,1723,1724}/{exp13,exp14,exp15}/` (report.json + experiencias).
Costo real: US$0 (mock).
