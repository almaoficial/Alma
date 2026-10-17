# Resultados: recalibración del piso de ruido δ — VERSIÓN 2

**Fecha:** 2026-10-16 · **Pre-registro rector:** `preregistro-recalibracion-delta-v2-2026-10-16.md` (ejecutado con el «Corre» de Alejandro, 16/10/2026) · **Presupuesto:** US$0, todo mock/local · **Script:** `data_recalibracion_delta_v2/run_recalibracion_delta_v2.py` · **Datos crudos:** `data_recalibracion_delta_v2/resultados.json`

**Veredicto: RARO — la validación H4 cayó (§6 Paso 3, §7). No se
adopta ningún número; el intento se archiva con este diagnóstico.**
La corrida se detuvo en la puerta del Paso 3: el Paso 4 (δ_P(18/12)
y el escalón 24/16) **no se ejecutó** — el estimador paramétrico que
lo iba a producir no quedó validado, y el documento manda no adoptar
(y no seguir) por una vía no validada. δ vigente queda como estaba:
**0,5331** (0,53 cableado en `gate.py`, que **no se tocó**). Panel
sin cambio (3/2). No se evaluó ningún candidato; no se corrió el
meta-loop; el validador congelado no se tocó.

---

## Paso 0 — Auditoría de determinismo: PASA (H2 verificada)

- 10 evaluaciones frescas del scaffold base sobre [0,1,2] + [3,4],
  sin caché: **10/10 idénticas** — diferencia máxima 0,0 en los 5
  `reg_pol` y los 120 `reg_pol_bloques`.
- `reg_pol` del scaffold base: 71,0 · 83,0 · 90,0 · 84,0 · 81,0
  (idénticos a los de la v1).
- **Duraciones:** una evaluación completa = **0,0893 s**; Paso 0 =
  0,893 s; duración estimada del protocolo asentada en el Paso 0 =
  11,43 s; duración real de la corrida (hasta la detención en el
  Paso 3) = **2,30 s**. Umbral de 1 h ni cerca → B se mantuvo en
  5000, sin reducción.

## Paso 1 — Descomposición de fuentes y σ̂ (pool fresco [2000..2029])

Virginidad del pool verificada antes de correr: 0 apariciones como
réplica en `metaloop_ledger.jsonl`, `metaloop_archivo.jsonl` y 256
archivos de resultados archivados (`data_exp*`, `exp*`,
`resultados/`, ledgers). Los ids de panel declarados en §4.5
([200..223] / [300..315]) se verificaron con el mismo barrido: 0
apariciones — y al no haber adopción, quedan vírgenes y sin usar.

| Fuente | Valor medido |
|---|---|
| Varianza entre bloques dentro de réplica (pool de 30) | media **2,60**; sd típica por bloque **1,61** |
| Varianza entre réplicas del `reg_pol` (pool de 30) | var **54,30**, **σ̂ = 7,3688**, media 81,33 |
| Varianza entre réplicas, panel histórico (5, referencia) | var 47,70, sd 6,91, media 81,8 |
| Varianza de medición repetida | **0** (Paso 0: 10/10 idénticas) |
| Varianza «del juez» en el camino del Δ | **0 por construcción** (declarada, no estimada) |

- **σ_usado = max(σ̂, 9,04) = 9,04** — la regla de conservadurismo de
  §4.4 se aplicó tal cual: el pool nuevo salió más quieto que el de
  la v1 (7,3688 < 9,04) y el piso no baja por eso.
- **Cláusula de régimen: NO se activó.** σ̂ = 7,3688 ≤ 11,30
  (= 1,25 × 9,04). El generador/stream no cambió de régimen en el
  sentido de la cláusula (que solo vigila σ̂ hacia arriba).

## Paso 2 — Control A: REPRODUCE

Método original de EXP-piso-ruido, panel 3/2, B = 5000, z = 2,0,
semilla 12345: **δ_A = 0,5320** (escala δ), sd(s) 0,2660,
sd(Δ_in) 0,2918, sd(Δ_ho) 0,3470. |δ_A − 0,5331| = **0,0011 ≤ 0,02**:
el pipeline no cambió desde el 30/9 y la validez interna quedó
confirmada antes de mirar cualquier otro piso, como manda §6.

## Paso 3 — Validación H4: CAE (diferencia 0,1022 > ±0,10)

| Piso a panel 3/2 | totales | escala δ | sd(Δ_in) totales | sd(Δ_ho) totales |
|---|---|---|---|---|
| (a) **Empírico** A/A por sorteo de paneles desde el pool nuevo | 10,9644 | **0,4569** | 5,9434 | 7,3846 |
| (b) **Paramétrico** δ_P(3/2) con σ_usado = 9,04 | 13,4186 | **0,5591** | 7,4776 | 9,0080 |

- |0,4569 − 0,5591| = **0,1022 > 0,10** → H4 no valida → rareza (§7):
  no se adopta nada por la vía paramétrica y la corrida se detiene.
- Referencias cruzadas: el paramétrico contra el piso que la v1
  midió a panel 3/2 difiere apenas **0,0032** (0,5591 vs 0,5623); el
  empírico del pool nuevo contra ese mismo 0,5623 difiere 0,1054.

## Paso 4 — NO EJECUTADO

δ_P(18/12) y δ_P(24/16) **no se computaron**. La puerta del Paso 3
existe exactamente para esto: el número de adopción lo produce el
estimador paramétrico, y ese estimador no pasó su validación
declarada. Computarlo igual «para ver cuánto daba» habría sido
seguir corriendo tras una invalidación, contra §6/§8.

## El diagnóstico (el «por qué» que la cláusula de rareza exige)

**La comparación de H4 mezcla, por construcción de las propias
reglas declaradas, las varianzas de dos pools distintos.** El
paramétrico se computa con σ_usado = max(σ̂, 9,04) = **9,04** — la
varianza del pool de la v1 — mientras que el empírico mide el pool
nuevo, cuyo σ̂ salió **7,3688** (−18,5% frente a 9,04; variación de
muestreo ordinaria entre pools de n=30: el propio §10.4 declara un
error relativo típico de ~13% para σ̂, así que −18,5% ≈ 1,4 errores
típicos — nada anómalo).

Tres chequeos con los números de esta corrida muestran que el
modelo paramétrico, alimentado con el σ del pool que se está
midiendo, sí describe a ese pool:

1. Reescalando el paramétrico al σ̂ del pool nuevo:
   0,5591 × (7,3688 / 9,04) = **0,4557**, contra el empírico medido
   **0,4569** — diferencia 0,0012.
2. Los sd por split del empírico (5,9434 / 7,3846 en totales)
   contra los que el modelo predice con σ = 7,3688 (6,016 / 7,369):
   desvíos de ~1,2% y ~0,2%.
3. El paramétrico con σ_usado = 9,04 reproduce el piso empírico que
   la v1 midió con su pool (0,5591 vs 0,5623; desvío 0,0032): el
   estimador acierta sobre el pool cuya varianza lo alimenta.

Es decir: **lo que cayó no es el modelo — es la validación tal como
fue especificada** (paramétrico con σ forzado por la regla max
contra empírico de un pool nuevo, con tolerancia ±0,10 calibrada
sin margen para la variación de σ̂ entre pools). La tentación de
«corregir» la comparación en esta corrida — validar a igual σ̂, o
mover la tolerancia a ±0,11 — es exactamente mover el arco después
de ver el resultado, prohibido por §7/§8. Lo que corresponde es lo
que el documento manda: **archivar el intento con este
diagnóstico**. Un intento futuro exige pre-registro nuevo que
decida de antemano cómo conviven la regla de conservadurismo
max(σ̂, 9,04) y la validación (p. ej.: validar paramétrico contra
empírico al mismo σ̂ y aplicar el max solo al piso que se adopta;
o derivar la tolerancia H4 del error de muestreo de σ̂ en vez de
fijarla en 0,10).

Nota al margen, sin efecto en el veredicto: aun en su lectura más
favorable, el piso empírico a panel 3/2 del pool nuevo (0,4569)
sigue por encima del EMI (0,3636) y de la zona de adopción a ese
panel — coherente con H1′: sin panel grande no hay adopción, y el
panel grande quedó sin medir en esta corrida.

## Hipótesis (§5)

- **H1′ (el panel manda, δ_P(18/12) ≤ 0,25): NO PUESTA A PRUEBA.**
  El Paso 4 no corrió: la corrida se detuvo en la puerta del
  Paso 3. No es un rechazo de la hipótesis — es su medición
  abortada por la invalidación del estimador.
- **H2 (determinismo): CONFIRMADA.** Paso 0, 10/10 idénticas.
- **H3 (el held-out manda el ruido): CONFIRMADA** en todo diseño
  medido: control A (0,3470 > 0,2918), empírico 3/2 (7,3846 >
  5,9434), paramétrico 3/2 — medido 9,0080 > 7,4776 y teórico
  9,04 > 7,3811.
- **H4 (validez del estimador paramétrico, ±0,10): CAÍDA.**
  Diferencia medida 0,1022.

## Estado final

- **δ_nuevo: ninguno.** δ vigente: **0,5331** (`PISO_RUIDO_DELTA`
  en `gate.py` sigue 0,53 — archivo no modificado en esta corrida;
  la separación congelamiento/recableado de §7 queda sin objeto
  porque no hay número nuevo que congelar).
- Panel de evaluación: sin cambio (3/2, train [0,1,2] / held-out
  [3,4], E3 [500,501]). El paquete de §4.5 (δ + panel 18/12 + ids
  [200..217]/[300..311]) **no se adoptó**; esos ids no se usaron
  para evaluar nada y quedan vírgenes.
- Pool [2000..2029]: consumido como pool de calibración de la v2
  (sus 30 `reg_pol` quedan asentados en los datos crudos).
- Asiento en `metaloop_ledger.jsonl`: evento `recalibracion_delta_v2`
  con σ̂, σ_usado, δ_A, ambos pisos del Paso 3, la diferencia H4 y el
  veredicto, con la cadena de hash del propio `metaloop.py`.
- Commit local en `~/workspace/alma-prototype` con el pre-registro
  v2, este documento, los datos crudos, el script y el asiento del
  ledger. Nada se subió a GitHub.

---

*Corrida: 2026-10-16, duración total 2,30 s, costo US$0. Ningún
candidato fue evaluado contra δ nuevo ni viejo; el meta-loop no se
corrió con fines de adopción; el validador congelado, el stream,
las tasas y `gate.py` no se tocaron.*
