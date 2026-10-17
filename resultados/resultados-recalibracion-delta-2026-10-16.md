# Resultados: recalibración del piso de ruido δ

**Fecha:** 2026-10-16 · **Pre-registro rector:** `preregistro-recalibracion-delta-2026-10-16.md` (ejecutado con el «Corre» de Alejandro, 16/10/2026) · **Presupuesto:** US$0, todo mock/local · **Script:** `data_recalibracion_delta/run_recalibracion_delta.py` · **Datos crudos:** `data_recalibracion_delta/resultados.json`

**Veredicto: RARO — no se adopta ningún número. El intento se archiva
con este diagnóstico (§5 «qué contaría como raro» + §6).**
δ vigente queda como estaba: **0,5331** (0,53 cableado en `gate.py`,
que **no se tocó**). No se evaluó ningún candidato; no se corrió el
meta-loop.

---

## Paso 0 — Auditoría de determinismo: PASA (H2 verificada)

- 10 evaluaciones idénticas del scaffold base sobre [0,1,2] + [3,4],
  sin caché: **10/10 idénticas** — los 5 `reg_pol` y los 120
  `reg_pol_bloques` coinciden exactamente (diferencia máxima = 0,0).
- `reg_pol` del scaffold base: réplica 0 = 71,0 · 1 = 83,0 · 2 = 90,0
  · 3 = 84,0 · 4 = 81,0.
- **Duraciones medidas (el dato «a fijar» del pre-registro, §6/§7):**
  una evaluación completa (5 réplicas × 240 ítems) = **0,097 s**;
  Paso 0 completo = 0,97 s; protocolo entero estimado en el Paso 0 =
  6,4 s; duración real total de la corrida = **2,35 s**. Muy por
  debajo del umbral de 1 h → B se mantuvo en 5000, sin reducción.

## Paso 1 — Descomposición de fuentes (cada una por separado)

| Fuente | Valor medido |
|---|---|
| Varianza entre bloques dentro de réplica | por réplica: 3,52 / 3,13 / 2,98 / 2,87 / 3,11 (media **3,12**; sd típica por bloque **1,77**) |
| Varianza entre réplicas del `reg_pol` | panel histórico (5): var **47,70**, sd **6,91**, media 81,8 · pool fresco (20): var **81,74**, sd **9,04**, media 81,5 |
| Varianza de medición repetida | **0** (Paso 0: 10/10 idénticas) |
| Varianza «del juez» en el camino del Δ | **0 por construcción** (no hay LLM en este camino; se declara, no se estima) |

Lectura: la varianza vive **entre réplicas** (sd ≈ 7–9 puntos de
regret), no dentro de la medición ni dentro de los bloques.

**Contaminación del pool:** antes de correr se verificó que ningún id
de [1000..1019] aparece como réplica evaluada en
`metaloop_ledger.jsonl`, `metaloop_archivo.jsonl` ni en los resultados
de experimentos archivados (búsqueda sin resultados). Pool virgen,
como exige §4-B.

## Paso 2 — Los tres pisos (B = 5000, z = 2,0, semilla 12345, s = max(Δ_in, Δ_ho))

| Piso | δ | sd(s*) | sd(Δ_in*) | sd(Δ_ho*) |
|---|---|---|---|---|
| **A** — método original, panel 3/2 | **0,5320** | 0,2660 | 0,2918 | 0,3470 |
| **B** — A/A pareado entre paneles, panel 3/2 | **13,4947** | 6,7474 | 7,3122 | 9,0749 |
| **C** — A/A pareado entre paneles, panel 6/4 | **9,4125** | 4,7063 | 5,2045 | 6,2735 |

**Control A: REPRODUCE.** |δ_A − 0,5331| = 0,0011 ≤ 0,02 (tolerancia
de Monte Carlo declarada). El pipeline no cambió desde el 30/9; la
validez interna del procedimiento quedó confirmada antes de mirar
B y C, como manda §4-A.

Mecánica de sorteo B/C (declarada para reproducibilidad): RNG
`numpy.default_rng(12345)` por diseño; B: `choice(20, 10, replace=
False)`, panel P = idx[0:5] (train 0:3, held-out 3:5), panel Q =
idx[5:10] (train 5:8, held-out 8:10); C: permutación completa
`choice(20, 20, replace=False)`, P = idx[0:10] (train 0:6, ho 6:10),
Q = idx[10:20] (train 10:16, ho 16:20). Paneles siempre disjuntos.

## Qué disparó la tabla de decisión (§5)

**δ_B ≥ δ_A → raro.** 13,4947 ≥ 0,5320. La regla dice: no se adopta
ningún número hasta entender por qué, y §6 agrega: el intento se
archiva con el diagnóstico. Ninguna otra rama se alcanzó: δ_B y δ_C
también están muy por encima de 0,30 (zona de archivo estructural) y
ningún piso cayó bajo 0,05.

## El diagnóstico (el «por qué» que la cláusula de rareza exige)

**Los tres pisos no comparten unidades, y el documento no lo
declaraba.** δ_A hereda la estadística de la calibración original:
diferencias de **medias por bloque** (promedios de los 24 bloques
remuestreados dentro de cada réplica) — su escala es 1/24 de la del
Δ de la puerta. δ_B y δ_C siguen la fórmula de §4 al pie de la
letra — medias de panel de `reg_pol` (regret **total** por réplica,
escala 0–240), que son las unidades en que la puerta compara de
verdad. El factor entre ambas escalas es exactamente 24 (bloques
por réplica): δ_A en puntos totales = 0,5320 × 24 = **12,77**;
δ_B en media-por-bloque = **0,5623**; δ_C = **0,3922**.

**La conclusión no depende de la lectura que se elija:**

- En unidades comunes, δ_B (0,5623) ≥ δ_A (0,5320) **igual**: el nulo
  pareado entre paneles con el panel actual **no reduce el piso** —
  lo sube levemente. La sospecha del pre-registro (§1, hecho 2) de
  que el nulo independiente «cuenta dos veces una varianza que el
  diseño real cancela» resulta no describir el término dominante: el
  bootstrap de bloques original **nunca vio** la varianza entre
  réplicas, que es la fuente grande (sd ≈ 9 puntos en el pool), y el
  A/A entre paneles la expone entera.
- El panel ampliado sí ayuda: δ_C es ~30% menor que δ_B y ~26% menor
  que δ_A en unidades comunes (0,3922 vs 0,5320) — pero queda por
  encima de 0,30 en la escala de A, y a años luz de 0,20 en la
  escala literal de la tabla. No alcanza ninguna zona de adopción.
- Por tanto **no hay lectura coherente del documento que produzca
  un δ_nuevo**: literal → rareza δ_B ≥ δ_A; en unidades comunes →
  rareza igual, y además todos los pisos comparables quedan > 0,30.
  Corregir las unidades «a mano» dentro de esta corrida para forzar
  la rama de C sería rediseñar el protocolo después de ver los
  resultados — mover el arco, prohibido por el propio pre-registro
  (§5/§6). Lo que corresponde es lo que el documento manda:
  **archivar con diagnóstico**.

## Hipótesis (§3)

- **H1 (dominancia del diseño, reducción ≥ 50%): NO confirmada.**
  La mayor reducción observada es la de C: ~26–30% según la
  comparación, lejos del 50%.
- **H2 (varianza de medición repetida = 0): CONFIRMADA.** Paso 0,
  10/10 idénticas.
- **H3 (el held-out manda el ruido): CONFIRMADA.** sd(Δ_ho*) >
  sd(Δ_in*) en los tres diseños (A: 0,347 > 0,292 · B: 9,07 > 7,31 ·
  C: 6,27 > 5,20), y la brecha se achica al ampliar el panel
  (B: 1,7627 → C: 1,0690), como predecía.

## Estado final

- **δ_nuevo: ninguno.** δ vigente: **0,5331** (cableado 0,53 en
  `gate.py` — archivo no modificado en esta corrida; la separación
  congelamiento/recableado de §5 queda sin objeto porque no hay
  número nuevo).
- Panel de evaluación: sin cambio (3/2, E3 [500,501]).
- Asiento en `metaloop_ledger.jsonl`: evento `recalibracion_delta`
  con δ viejo, δ nuevo (= sin cambio) y referencia a este documento.
- **Qué haría falta para un próximo intento (fuera de esta corrida,
  exige pre-registro nuevo):** definir los pisos B/C y los umbrales
  de decisión en **una sola escala declarada** (la del Δ de la
  puerta: puntos de regret total), o expresar el A/A en la escala
  del estadístico original y re-derivar los umbrales 0,20/0,30 en
  esa escala antes de correr — nunca después. El dato que ese
  pre-registro ya tiene gratis: con panel 6/4 el piso A/A baja ~30%
  y la brecha held-out/train se achica; el término dominante a
  atacar es la varianza entre réplicas del stream, no la medición.

---

*Corrida: 2026-10-16, duración total 2,35 s, costo US$0. Nada se
subió a GitHub. Ningún candidato fue evaluado contra δ nuevo ni
viejo en esta corrida; el meta-loop no se corrió con fines de
adopción; el validador congelado no se tocó.*
