# EXP68 — Pre-registro: detector de heterogeneidad

**Fecha:** 2026-09-27 ~19:30 EDT. **Costo:** mock, US$0, sin API keys.
**Estado:** escrito ANTES de correr la validación (réplicas 0–4). K/J/veredicto
congelados a partir de acá.

## 1. Hipótesis

Un detector que observa el veredicto del probe bloque a bloque y encoje la
exploración cuando el probe es unánime K bloques seguidos (con spot-checks
cada J bloques como red de seguridad ante flips, lección EXP9):

- **mejora** el regret en un mundo homogéneo single-dominante (estilo EXP62),
  donde la exploración es puro costo de verificación, **y**
- **no regresa** en un mundo heterogéneo con regímenes rotantes (estilo EXP5),
  donde la adaptación sí paga.

Si ayuda en A pero rompe B → FAIL, no se integra. La validación es a dos
puntas por diseño, no por accidente.

## 2. Motivación (lección EXP66)

El FAIL del EXP62 no tenía defecto aprendible: el mundo era single-dominante
y el costo de exploración fue el precio de verificar que no había nada que
descubrir. Este detector es la respuesta mecánica: el loop aprende **cuándo
no hay nada que descubrir** y deja de pagar el costo, sin romper la
adaptación donde sí hay algo que descubrir.

## 3. El detector (`alma_service/heterogeneidad.py`)

`DetectorHeterogeneidad(K, J)` — state machine pura (sin RNG, sin I/O, sin
LLM), aditiva: no toca el scaffold vigente.

- **Veredicto del bloque** = argmax **estricto** de las medias del probe
  (Q1+Q2, los items que la política efectivamente mide). Un bloque saltado
  por la skill **no** produce veredicto (reinicia la racha: sin medición no
  hay unanimidad que observar). Un empate (sin ganador estricto) reinicia.
- **Entrada:** K bloques consecutivos con el mismo veredicto → modo
  ENCOGIDO, compromete ese brazo, saltea probe+Thompson (juega el brazo
  en los 10 items, réplica exacta del camino de skip del scaffold).
- **Salida (histéresis):** cada J bloques encogidos, spot-check de 3 items
  (mide a todos los brazos, banca al comprometido). El comprometido se
  mantiene salvo que otro brazo lo supere por **≥2 items**
  (`MARGEN_SALIDA=2`): la contradicción estricta en 3 items ocurre ~24%
  por azar cuando el comprometido sigue siendo el mejor; el margen la baja
  a ~5% manteniendo la detección de flips reales.

### Por qué el veredicto es el probe y no el brazo comprometido (fav)

Decisión de diseño con evidencia de calibración (réplicas 10–19, nunca las
de validación):

1. El argmax crudo del probe en 5 items es ruidoso (P=0,59/bloque en A),
   pero el **brazo comprometido (fav del posterior)** es peor señal:
   con decay=0,5 el posterior lo dominan los bloques recientes → en A se
   enganchó al brazo **equivocado** (Δ=-34 en una réplica: bancó 18 bloques
   el brazo perdedor); en B el fav se computa siempre con el prior ciego
   (ciego a regímenes por construcción) → rachas falsas estructurales
   (5/5 réplicas con enganches).
2. Con veredicto=probe, los bloques saltados reinician la racha: en B el
   skip del scaffold opera y rompe cualquier racha espuria → **0 enganches
   en B** en calibración; en A (skip dormido por diseño) el probe manda.

Variante "probe_decisivo" (margen ≥1 item para que el veredicto cuente) se
probó y dio idéntico al probe crudo en calibración → se descarta por
simplicidad.

### K=3, J=3 (congelados)

- **K=3:** en calibración (20 réplicas 10–29), A engancha 18/20 siempre en
  el brazo correcto ('contexto'), Δ medio +5,05 (rango −2 a +13). K=4
  engancha más tarde y rinde menos (+2,60 en 5 réplicas). En B, K=3 dio
  1 enganche en 20 réplicas, **restaurado por el primer spot-check**
  (bloque 3→6) con Δ neto 0,00: la red de seguridad funciona.
- **J=3:** con el margen de salida, las falsas restauraciones en A son
  raras (1/5 en calibración, sin daño al Δ). J mayor detectaría flips más
  lento; J menor haría más spot-checks (más chances de falsa salida).

## 4. Mundos (congelados)

**Mundo A (homogéneo, estilo EXP62):** 24 bloques × 10 items, categoría única
`"tarea"`, tasas `contexto=0,75` vs `titular=estable=0,50`. Firmas de bloque
**únicas por bloque** → la skill/skip del scaffold queda dormida y el
detector es el único mecanismo de explotación. El brazo `mayoria` se excluye
(sería perfecto en categoría única); mismo recorte en baseline y tratamiento.

**Mundo B (heterogéneo, estilo EXP5):** stream e47 estándar (24 bloques,
firma = grupo mayoritario de Q1, con 2 items de ruido por bloque), tasas por
régimen: tech→titular, dinero→contexto, deportes→estable (0,75 vs 0,50).
El skip del scaffold opera normal.

## 5. Protocolo

- **Baseline:** `correr_replica_exp68(detector=None)` — bit-idéntico a
  `e56.correr_replica_param` (sanity check: 71/83/90/84/81 en el mundo
  default, réplicas 0–4).
- **Tratamiento:** mismo runner + `DetectorHeterogeneidad(K=3, J=3)`.
  Pareo por réplica con el **mismo namespace RNG** (`exp45-…`): los draws
  por celda son idénticos; la única diferencia es el detector.
- **Réplicas de validación:** 0–4 por mundo (las de calibración fueron
  10–29; no se tocan).
- **Scaffold:** `DEFAULT_SCAFFOLD` (n0=4, umbral_base=1, umbral_divisor=3,
  decay=0,5, gate_margin=0,0). No se toca.

## 6. Criterio pre-registrado (puerta de dos splits)

Sobre deltas puntuales pareados, Δ = regret(baseline) − regret(detector)
por réplica:

> **PASS ⟺ media(Δ_B) ≥ 0 ∧ media(Δ_A) > 0.**

Se reportan IC95 (t, df=4) por mundo como contexto, pero el veredicto usa
las medias puntuales, igual que `alma_service/gate.py`. Si Δ_A > 0 pero
Δ_B < 0 → FAIL (el detector rompe la adaptación: no se integra).

## 7. Compromisos

- K, J, margen de salida, definición de veredicto y mundos **no se tunean
  después de este pre-registro**. Lo que salga en 0–4 es el veredicto.
- El módulo es aditivo en `alma_service/`; el scaffold vigente no se toca.
- Mock US$0. Ninguna key. Ningún gasto real.
