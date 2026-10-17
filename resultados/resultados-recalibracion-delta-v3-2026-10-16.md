# Resultados: recalibración del piso de ruido δ — VERSIÓN 3

**Fecha:** 2026-10-16 · **Pre-registro rector:** `preregistro-recalibracion-delta-v3-2026-10-16.md` (md5 verificado antes de correr: `5d4d51875850c160fde4cf30d15f1239`, 33.281 bytes, 603 líneas, §1–§12; ejecutado con el «Corre» de Alejandro, 16/10/2026, reafirmado) · **Presupuesto:** US$0, todo mock/local · **Script:** `data_recalibracion_delta_v3/run_recalibracion_delta_v3.py` · **Datos crudos:** `data_recalibracion_delta_v3/resultados.json` · **Barrido de virginidad:** `data_recalibracion_delta_v3/barrido_virginidad.json`

**Veredicto: ADOPCIÓN PRIMARIA (§8). δ_P(18/12) = 0,2283 ≤ 0,25 →
δ_nuevo = 0,2283 (escala δ) = 5,4781 totales, con panel 18/12
(train [400..417], held-out [600..611], E3 [500,501] intacto),
CONGELADO en este documento, en el ledger y en el commit
correspondiente antes de que se evalúe cualquier candidato.**
Todas las puertas del protocolo pasaron: determinismo 10/10,
barrido de virginidad sin consumo no declarado, σ̂_pool fuera de
régimen, control A reproduce, y la validación H4 — en la
especificación corregida de la v3 (§2.2) — validó con una
diferencia de 0,0004 contra una tolerancia de ±0,10. El escalón
24/16 **no se evaluó**: el panel primario alcanzó adopción y §8
manda que el escalón no se evalúa en ese caso. Ningún candidato fue
evaluado contra δ nuevo ni viejo; el meta-loop no se corrió; el
validador congelado no se tocó. `gate.py` **no se tocó en esta
corrida** (`PISO_RUIDO_DELTA` sigue cableado en 0,53): por §7 la
calibración no toca `gate.py`, y por §8 el congelamiento (este
asiento) y el recableado son pasos separados — el recableado, que
compara en la escala declarada abajo y exige evaluar el scaffold
base sobre el panel nuevo antes de cualquier candidato (§5.5),
queda fuera de esta calibración.

---

## Barrido amplio de virginidad previo (§5.6, Paso 1): SIN CONSUMO NO DECLARADO

Repetido inmediatamente antes de correr, sobre el árbol completo
tal como estaba hoy: **375 archivos JSON/JSONL, 373 parseados**;
los 2 no parseables — los mismos declarados en §5.6 — se
inspeccionaron en texto (`resultados/exp35-20260927/report.json`:
ningún id candidato, solo 4975 y 4981 fuera de todo rango;
`producto/router-puro/mvp/shadow/mediciones.jsonl`: 0 apariciones
de ningún candidato, sin claves de id).

| Rango | Resultado |
|---|---|
| Pool [4000..4029] | **Virgen — 0 hits de ninguna categoría** |
| Train [400..417] y escalón [400..423] | **Vírgenes como réplica** — únicos hits: 402, 404, 421 (`data_exp11/seleccion.json`) y 409, 411, 414 (`data_exp12/seleccion.json`), todos en `/gsm8k/indices_originales`: índices de ítems GSM8K, maquinaria ajena ya declarada en §5.6 |
| Held-out [600..611] y escalón [600..615] | **Vírgenes como réplica** — únicos hits: 602, 609 (`data_exp11`) y 604, 614 (`data_exp12`), mismo contexto GSM8K declarado |
| E3 [500,501] | Aparecen en `metaloop_ledger.jsonl` (`/evento/config_e3/e3_reps`): son los ids del propio E3, en uso por diseño; la v3 los declara intactos, no requieren virginidad |

El barrido detectó además los controles esperados del propio
ledger, así que su alcance quedó verificado en el acto. **No hizo
falta reemplazo alguno**: §9 no se activó por esta vía. Los ids del
panel **no se evaluaron** en esta corrida (evaluar el scaffold base
sobre el panel nuevo es parte del recableado, §5.5).

## Paso 0 — Auditoría de determinismo: PASA (H2 verificada)

- 10 evaluaciones frescas del scaffold base sobre [0,1,2] + [3,4],
  sin caché: **10/10 idénticas** — diferencia máxima 0,0 en los 5
  `reg_pol` y los 120 `reg_pol_bloques`.
- `reg_pol` del scaffold base: 71,0 · 83,0 · 90,0 · 84,0 · 81,0
  (idénticos a los de la v1 y la v2).
- **Duraciones:** una evaluación completa = **0,0847 s**; Paso 0 =
  0,847 s; duración estimada del protocolo asentada en el Paso 0 =
  11,36 s; duración real de la corrida completa = **2,179 s**.
  Umbral de 1 h ni cerca → B se mantuvo en 5000, sin reducción.

## Paso 1 — Descomposición de fuentes y σ̂_pool (pool fresco [4000..4029])

| Fuente | Valor medido |
|---|---|
| Varianza entre bloques dentro de réplica (pool de 30) | media **2,6030**; sd típica por bloque **1,6134** |
| Varianza entre réplicas del `reg_pol` (pool de 30) | var **74,8057**, **σ̂_pool = 8,6490**, media 81,2333 |
| Varianza entre réplicas, panel histórico (5, referencia) | var 47,70, sd 6,9065, media 81,8 |
| Varianza de medición repetida | **0** (Paso 0: 10/10 idénticas) |
| Varianza «del juez» en el camino del Δ | **0 por construcción** (declarada, no estimada) |

- **σ̂_pool = 8,6490**, estimado una sola vez en este paso, como
  manda §5.4/§11.7. Salió más alto que el del pool de la v2
  (7,3688) y más bajo que el de la v1 (9,04): variación de muestreo
  ordinaria entre pools de n=30 (§11.4), en la dirección que la
  regla de conservadurismo existe para cubrir.
- **σ_usado = max(σ̂_pool, 9,04) = 9,04** — aplicado **solo** al
  piso de adopción (Paso 4); la validación del Paso 3 usó σ̂_pool
  sin max (§2.2).
- **Cláusula de régimen: NO se activó.** σ̂_pool = 8,6490 ≤ 11,30
  (= 1,25 × 9,04).

## Paso 2 — Control A: REPRODUCE

Método original de EXP-piso-ruido, panel 3/2, B = 5000, z = 2,0,
semilla 12345: **δ_A = 0,5320** (escala δ), sd(s) 0,2660,
sd(Δ_in) 0,2918, sd(Δ_ho) 0,3470. |δ_A − 0,5331| = **0,0011 ≤ 0,02**:
el pipeline no cambió desde el 30/9 y la validez interna quedó
confirmada antes de mirar cualquier otro piso, como manda §7.
(Tercera reproducción consecutiva con el mismo desvío: v1, v2, v3.)

## Paso 3 — Validación H4, especificación de la v3 (§2.2): VALIDA

| Piso a panel 3/2 | totales | escala δ | sd(Δ_in) totales | sd(Δ_ho) totales |
|---|---|---|---|---|
| (a) **Empírico** A/A por sorteo de paneles desde el pool fresco | 12,8467 | **0,5353** | 7,0161 | 8,5818 |
| (b) **Paramétrico** δ_P(3/2) con **σ̂_pool = 8,6490** (sin regla max) | 12,8383 | **0,5349** | 7,1542 | 8,6184 |

- |0,5353 − 0,5349| = **0,0004 ≤ 0,10** → **H4 VALIDA**: el
  estimador paramétrico describe al pool que lo alimenta cuando
  ambos lados de la comparación miden el mismo pool con el mismo
  σ — la corrección de §2.2 funcionó tal como fue declarada.
- Referencia **informativa, no puerta** (§2.2): δ_P(3/2) con
  σ_usado = 9,04 = **0,5591**, contra el 0,5623 que midió la v1:
  desvío **0,0032** (idéntico al de la v2, como corresponde al mismo
  σ_usado, la misma semilla y la misma mecánica). El empírico de
  este pool contra ese 0,5623 difiere 0,0270 — esperable: este pool
  salió con σ̂ = 8,6490, más cerca del de la v1 (9,04) que el de la
  v2 (7,3688), y su piso empírico quedó en consecuencia más alto
  que el de la v2 (0,5353 vs 0,4569).

## Paso 4 — El piso del panel elegido: δ_P(18/12) = 0,2283 → ADOPCIÓN

δ_P(18/12) con **σ_usado = 9,04**, B = 5000, semilla 12345:
**5,4781 totales = 0,2283 (escala δ)**. sd(Δ_in) medido 3,0527
totales (teórico 3,0133), sd(Δ_ho) medido 3,6775 (teórico 3,6906),
sd(s) 2,7391 totales.

- **0,2283 ≤ 0,25** → rama primaria de §8: **δ_nuevo = δ_P(18/12)**,
  panel 18/12. H1′ confirmada (esperado declarado antes de correr:
  0,232; medido: 0,2283 — la diferencia es resolución de Monte
  Carlo a B = 5000, y §5.4 manda que el número que vale es el
  medido). Margen bajo el EMI (§4, 0,3636): **0,1353**, por encima
  del margen objetivo de diseño (≥ 0,1136).
- **El escalón 24/16 no se evaluó** (§8: con adopción primaria, el
  escalón no se evalúa).
- **Rarezas de §8, todas despejadas:** el piso adoptado (0,2283) es
  menor que δ_A de esta corrida (0,5320) ✓; ningún piso computado
  cayó bajo 0,05 (el mínimo es el propio 0,2283) ✓; σ̂_pool fuera
  de régimen ✓; validación H4 válida en su especificación ✓.

## Congelamiento (§8)

Producido el resultado, queda congelado **antes de que se evalúe
cualquier candidato nuevo del meta-loop**, en las dos escalas y con
su panel:

- **δ_nuevo = 0,2283 (escala δ)** — valor exacto medido:
  5,4781 / 24 = 0,22825…; se asienta con los 4 decimales del
  sistema, como el δ vigente (0,5331).
- **Equivalente en totales: 5,4781** (medido directamente como
  2·sd(s) en el Paso 4). Nota de redondeo: δ × 24 sobre el valor
  redondeado da 5,4792; la diferencia de 0,0011 totales es puro
  redondeo a 4 decimales y queda declarada para que el recableado
  use el par asentado acá: **(0,2283 escala δ ; 5,4781 totales)**.
- **Panel: 18/12** — train **[400..417]**, held-out **[600..611]**,
  E3 **[500,501]** sin cambio.
- **La forma de la regla no cambia:** `Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧
  max(Δ_in, Δ_ho) > δ`, puerta pura y E3 intactos.
- Asentado en: este documento, el evento `recalibracion_delta_v3`
  del ledger del meta-loop (cadena de hash de `metaloop.py`) y el
  commit local de esta corrida. **Nada se subió a GitHub.**
- **Estado de `gate.py`: sin tocar.** `PISO_RUIDO_DELTA` sigue
  cableado en 0,53. Entre este congelamiento y el recableado no se
  corre el meta-loop con fines de adopción, y el recableado —
  escribir el número nuevo comparando en la escala declarada acá y
  evaluar el scaffold base sobre el panel nuevo antes de cualquier
  candidato (§5.5) — es un paso posterior, fuera del alcance de
  esta calibración (§7). Cualquier cambio posterior de δ, del
  panel o de sus ids exige otro pre-reg
...[truncated 5474 chars]