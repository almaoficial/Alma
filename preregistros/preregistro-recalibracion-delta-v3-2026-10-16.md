# Pre-registro: recalibración del piso de ruido δ — VERSIÓN 3

**Fecha:** 2026-10-16 · **Estado:** redactado el 16/10/2026 a pedido de
Alejandro («Hacelo», tras el archivo de la v2 el mismo día), US$0, sin
código, sin corridas — este documento no autoriza por sí solo ninguna
corrida: como la v1 y la v2, su ejecución exige el «corré» explícito
**Predecesoras:** `preregistro-recalibracion-delta-2026-10-16.md` (v1),
ejecutada y **archivada por su propia cláusula de rareza**
(resultados en `resultados-recalibracion-delta-2026-10-16.md`), y
`preregistro-recalibracion-delta-v2-2026-10-16.md` (v2), ejecutada y
**archivada por la caída de su validación H4** (resultados en
`resultados-recalibracion-delta-v2-2026-10-16.md` y
`data_recalibracion_delta_v2/`). Esta v3 hereda de la v2 todo lo que
la v2 no demostró erróneo, y corrige **una sola cosa**: la
especificación de la validación del estimador (§2). No «corrige» la
v2 después de verla para rescatar un número: declara la regla nueva
antes de correr, con su justificación escrita, y cualquier corrida
futura se juzga solo contra este documento.
**Regla que se toca (solo el número y el panel, no la forma):**
`alma_service/gate.py` — `PISO_RUIDO_DELTA = 0.53`; auto-adopción solo
si `Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(Δ_in, Δ_ho) > δ` (la puerta pura `> 0` y
el E3 quedan intactos)

---

## 1. Qué midieron la v1 y la v2 (los hechos que esta v3 hereda)

Con recibo en `resultados-recalibracion-delta-2026-10-16.md` (v1) y
`resultados-recalibracion-delta-v2-2026-10-16.md` (v2):

1. **Determinismo total, dos veces.** En ambas corridas, 10/10
   evaluaciones idénticas del scaffold base (diferencia máxima 0,0).
   Varianza de medición repetida = 0; varianza «del juez» en el
   camino del Δ = 0 por construcción (no hay LLM en este camino: el
   Δ lo produce el simulador determinista del validador congelado).
2. **La fuente dominante del ruido es la varianza ENTRE réplicas**
   del `reg_pol`: panel histórico (5 réplicas) var 47,70 / sd 6,91;
   pool fresco v1 (20 réplicas) var 81,74 / sd **9,04**; pool fresco
   v2 (30 réplicas) var 54,30 / sd **7,3688**. La variación de σ̂
   entre pools de n=20–30 es muestreo ordinario (error relativo
   típico ~13% a n=30, §10.4 de la v2), no un cambio de régimen.
3. **El nulo pareado entre paneles NO bajó el piso con el panel
   actual** (v1): piso A (método original) = 0,5320 — reprodujo el
   0,5331 vigente (desvío 0,0011), y volvió a reproducirlo en la v2
   con el mismo desvío (0,5320); nulo A/A pareado con panel 3/2 =
   **0,5623** (≥ A → rareza, archivo de la v1); nulo A/A con panel
   6/4 = **0,3922** (−26%): ayuda, pero queda sobre 0,30 y sobre el
   efecto mínimo de interés de §3.
4. **El modelo del nulo de la v2 quedó validado en todo menos en su
   propia puerta** (v2, Paso 3): el estimador paramétrico con
   σ_usado = 9,04 reprodujo el piso empírico del pool de la v1
   (0,5591 vs 0,5623; desvío 0,0032), y reescalado al σ̂ del pool
   nuevo predijo su piso empírico casi exacto (0,4557 vs 0,4569;
   desvío 0,0012), con los sd por split dentro de ~1%. Lo que cayó
   no fue el modelo: fue la comparación tal como estaba
   especificada (§2).
5. **El defecto de escalas de la v1 ya está corregido desde la v2:**
   §2 de la v2 (heredado como §3 acá) declara una sola escala y toda
   magnitud lleva su conversión escrita. Verificado además en
   código: `metaloop._evaluar` promedia `reg_pol` (totales por
   réplica, escala 0–240) y `gate.decidir_auto_adopcion` compara
   esos Δ en totales contra la constante 0,53, calibrada en la otra
   escala — la comparación mixta queda registrada como el defecto a
   no repetir, no como un detalle a heredar en silencio.
6. **Costo de paneles grandes en este instrumento: despreciable.**
   Una evaluación completa (5 réplicas × 240 ítems) ≈ 0,09–0,097 s;
   los protocolos v1 y v2 enteros tardaron 2,35 s y 2,30 s. Una
   réplica ≈ 0,02 s.

## 2. La única corrección de la v3: validación y adopción son dos comparaciones distintas

### 2.1 Qué estaba mal especificado en la v2

La validación H4 de la v2 mandaba comparar, dentro de ±0,10:

- (a) el piso **empírico** A/A por sorteo de paneles desde el pool
  fresco de la corrida — que mide la varianza **de ese pool**
  (su σ̂ salió 7,3688), contra
- (b) el piso **paramétrico** δ_P(3/2) calculado con
  **σ_usado = max(σ̂, 9,04) = 9,04** — la varianza **del pool de la
  v1**, impuesta por la regla de conservadurismo.

Las dos reglas, cada una razonable por separado, hacían la
comparación imposible por construcción: (a) y (b) difieren
sistemáticamente por el factor σ_usado/σ̂ del pool (9,04/7,3688 ≈
1,23 en sd, ≈ 0,10 en el piso a panel 3/2) antes de que intervenga
ningún error del modelo. La diferencia medida fue 0,1022 contra una
tolerancia de 0,10 — la puerta cayó por 0,0022 sobre una comparación
que mezclaba dos varianzas distintas. El diagnóstico completo, con
los tres chequeos que muestran que el modelo sí describe al pool
que lo alimenta, está asentado en
`resultados-recalibracion-delta-v2-2026-10-16.md`.

### 2.2 La regla de la v3 (declarada antes de correr, sin ambigüedad)

**Validación y adopción son dos comparaciones distintas, cada una
con su σ declarado:**

1. **Validación del estimador (pregunta sobre el MODELO):** el piso
   paramétrico a panel 3/2 se calcula con **σ̂_pool, el σ̂ del pool
   fresco de ESTA corrida** (sin regla max, sin ningún σ heredado),
   y se compara contra el piso **empírico** A/A por sorteo de
   paneles desde **ese mismo pool**, con la misma tolerancia de la
   v2: **±0,10 (escala δ)**. Mismo pool, mismo σ, misma mecánica de
   sorteo empírico de la v1/v2. Si no valida → se detiene todo,
   como en la v2: el diseño P no queda validado y no se adopta nada
   por esta vía.
2. **Piso de adopción (pregunta sobre la PUERTA):** el piso que se
   adopta — δ_P al panel de la puerta, primario o escalón — se
   calcula con **σ_usado = max(σ̂_pool, 9,04)**. La regla de
   conservadurismo de la v2 se mantiene intacta, pero se aplica
   **solo al número que se adopta, nunca a la validación**: ningún
   piso adoptado baja porque el pool nuevo haya salido más quieto
   que el medido por la v1.

Y una referencia cruzada **informativa, no una puerta**: se reporta
también δ_P(3/2) calculado con σ_usado contra el 0,5623 que midió la
v1 (la v2 lo reportó: 0,5591, desvío 0,0032). Es un dato de
continuidad entre corridas; **no** valida ni invalida nada en esta
v3, y queda escrito así para que nadie lo use como segunda
validación encubierta con σ mezclado — eso fue exactamente el
defecto de la v2.

### 2.3 Por qué esto no es mover el arco

- La regla se fija **antes** de correr la v3, en este documento; la
  corrida se juzga solo contra ella. Nadie ajusta σ ni tolerancias
  después de ver un número de esta corrida — lo que §8 prohíbe,
  igual que en la v1 y la v2.
- La validación y la adopción responden **preguntas distintas**, y
  cada σ es el que esa pregunta exige: la validación pregunta si el
  modelo paramétrico describe al pool que se está midiendo — si se
  le impusiera el σ de otro pool, mediría la diferencia entre pools
  y no al modelo (es lo que hizo caer a la v2); la adopción pregunta
  qué piso protege la puerta — y ahí el colchón conservador
  (σ_usado = max(σ̂, 9,04)) sigue vigente y sin tocar.
- La tolerancia de validación no se ensancha: sigue en ±0,10, la de
  la v2. Lo único que cambia es que ambos lados de la comparación
  miden el mismo pool, que es lo que una validación de un estimador
  significa.

## 3. La escala única (heredada de la v2, sin cambios)

**Escala δ** — la escala de este documento para pisos, umbrales y
efectos: **media por bloque**, es decir, puntos de regret total
divididos por los 24 bloques de la réplica. Es la escala en la que
δ = 0,5331 fue calibrado (EXP-piso-ruido, 30/9/2026) y cableado como
`PISO_RUIDO_DELTA`.

- Todo piso, umbral y efecto de este documento se expresa en
  escala δ. Ningún número aparece sin su escala.
- Los cálculos internos del nulo A/A nacen en **totales** (medias de
  panel de `reg_pol`): su conversión a escala δ es **÷ 24**, escrita
  junto a cada resultado (así: δ_B v1 = 13,4947 totales = 0,5623
  escala δ).
- El congelamiento (§8) fija δ_nuevo **en escala δ y en su
  equivalente en totales (δ × 24)**, para que el recableado en
  `gate.py` compare magnitudes de la misma escala.

## 4. Efecto mínimo de interés (heredado de la v2, sin cambios)

**EMI = 0,3636** (escala δ) — el Δ_down de EXP76
(`data_exp76/resultados_exp76.json`: Δ_down = +0,3636, Δ_ref =
+0,3807), el efecto real más grande que el sistema produjo y adoptó
en una de sus puertas.

**Justificación, escrita en la v2 antes de calcular paneles:** un
piso que no puede detectar el mejor efecto que el sistema ya
produjo no sirve para el destino declarado — la primera adopción
medida del meta-loop. Hoy δ = 0,5331 supera al EMI; incluso el piso
del panel 6/4 de la v1 (0,3922) lo supera: con cualquiera de los dos,
un EXP76 futuro sería invisible para la auto-adopción. El piso
recalibrado debe quedar **por debajo** del EMI con margen declarado:
ese margen es el objetivo de diseño de §5 (piso esperado ≤ 0,25,
margen ≥ 0,1136 bajo el EMI).

La procedencia cruzada de este EMI (EXP76 es la puerta de admisión
de skills, con su propia métrica) se declara sin maquillar en
§11.2: 0,3636 se adopta como EMI **por decisión de diseño** — la
vara que el piso debe poder ver —, no como una medición en unidades
idénticas a las del Δ del meta-loop.

## 5. Cálculo de potencia y elección del panel (heredado de la v2; cambian el pool y los ids, §5.5)

### 5.1 El modelo del nulo (validado contra las mediciones de la v1)

Bajo el nulo A/A (el mismo sistema en dos paneles disjuntos de
réplicas), con σ = sd entre réplicas del `reg_pol` (totales):

    sd(Δ_split) = σ · √(2/n_split)

con σ = **9,04** (pool fresco de la v1, var 81,74 — base
conservadora; el panel histórico da 6,91 y no se usa). El modelo
reproduce los cuatro sd por split medidos por la v1 dentro del 2%:

| split | predicho (σ=9,04) | medido v1 | desvío |
|---|---|---|---|
| Δ_in, n=3 | 7,38 | 7,31 | +0,9% |
| Δ_ho, n=2 | 9,04 | 9,07 | −0,4% |
| Δ_in, n=6 | 5,22 | 5,20 | +0,3% |
| Δ_ho, n=4 | 6,39 | 6,27 | +1,9% |

### 5.2 Pisos esperados por panel (declarados ANTES de correr)

Con `s = max(Δ_in, Δ_ho)`, `δ = 2,0 · sd(s)` (el estadístico y el
criterio de la v1, sin cambio — §5.4), sorteos normales
independientes con los sd de §5.1, Monte Carlo de alta precisión a
σ = 9,04, expresados en escala δ (totales ÷ 24):

| panel (train/held-out, por lado) | δ esperado (escala δ) | referencia |
|---|---|---|
| 3/2 (actual) | 0,568 | v1 midió 0,5623 (modelo: +0,9%) |
| 6/4 | 0,401 | v1 midió 0,3922 (modelo: +2,3%) |
| 9/6 | 0,328 | — |
| 12/8 | 0,284 | — |
| 15/10 | 0,254 | no alcanza (≤ 0,25) |
| **18/12** | **0,232** | **primer panel 3:2 que cumple** |
| 24/16 | 0,201 | escalón pre-declarado (§5.5) |
| 30/20 | 0,180 | — |

### 5.3 Por qué NO se fuerza el panel con el diseño de la v1

Con la mecánica de la v1 (sortear paneles disjuntos desde un pool de
réplicas vírgenes), el panel 18/12 exige **60 réplicas vírgenes por
sorteo** (dos paneles de 30) y por tanto un pool ≥ 60.

**Criterio de desproporción, declarado:** un diseño de calibración
que exija **> 40 réplicas vírgenes totales** (o una duración estimada
> 1 h) es desproporcionado para este instrumento. El panel sorteado
lo supera (60 > 40); la duración no es el problema (≈ 0,02 s por
réplica). **No se fuerza**: la v3 adopta el estadístico alternativo
de §5.4, que mide el mismo piso con un pool de 30 réplicas (≤ 40).

### 5.4 El estadístico (diseño P: bootstrap paramétrico del Δ pareado)

- **Qué se mide no cambia:** el piso del nulo A/A — cuánto se mueve
  `s = max(Δ_in, Δ_ho)` cuando el mismo sistema se compara contra sí
  mismo en paneles independientes — y el criterio no cambia:
  **δ = z · sd(s), z = 2,0, B = 5000, semilla 12345** (los de la v1).
- **Qué cambia, y por qué (justificación escrita):** solo la
  generación de los sorteos del nulo. En vez de sortear paneles
  desde un pool finito (que desperdicia réplicas — un pool de 60
  apenas produce pares de paneles distintos — y suma error de
  composición del pool al error de Monte Carlo), los sorteos se
  generan del modelo de §5.1: Δ_in ~ N(0, 2σ²/n_in),
  Δ_ho ~ N(0, 2σ²/n_ho), independientes (los paneles del A/A son
  disjuntos). El modelo no es un supuesto nuevo: reproduce los
  cuatro sd medidos por la v1 dentro del 2% y sus dos pisos dentro
  de +0,9% / +2,3% (§5.2). Y σ se estima con **todas** las réplicas
  del pool (el contraste con todas las réplicas), no con las que
  toca un sorteo.
- **σ de la corrida:** pool fresco de **30 réplicas vírgenes, ids
  [4000..4029]** (virginidad según el procedimiento de §5.6;
  [1000..1019] ya los quemó la v1 y [2000..2029] la v2).
  σ̂_pool = sd de los 30 `reg_pol`, estimado **una sola vez**, en el
  Paso 1 (§7), y alimenta las dos comparaciones de §2.2 — no se
  re-estima entre pasos. **Regla de conservadurismo, declarada
  antes de correr:** σ_usado = max(σ̂_pool, 9,04) — se aplica solo
  al piso de adopción (§2.2, punto 2); la validación del Paso 3
  usa σ̂_pool, sin max (§2.2, punto 1).
- **Piso esperado del diseño P, declarado antes de correr:** con
  σ_usado = 9,04, δ_P(18/12) = **0,232** (escala δ; 5,57 en totales).
  Si σ̂_pool > 9,04, el piso esperado escala linealmente:
  δ_P ≈ 0,232 · (σ_usado / 9,04). El número que manda es el medido
  en la corrida con el σ_usado que resulte, no esta expectativa.

### 5.5 El panel de la puerta que esta v3 propone

- **Panel primario: train 18 / held-out 12** (razón 3:2, como
  siempre). Piso esperado 0,232 ≤ 0,25, margen 0,1316 bajo el EMI.
  Ids declarados (vírgenes según §5.6, disjuntos de todo lo usado:
  histórico [0..4], E3 [500,501], pools [1000..1019] y [2000..2029]):
  train **[400..417]**, held-out **[600..611]**. El E3 no se toca:
  sigue en [500,501].
- **Escalón pre-declarado: train 24 / held-out 16** (piso esperado
  0,201; ids train [400..423], held-out [600..615]). Solo se evalúa
  dentro de la misma corrida, con el mismo σ_usado, y solo si el
  piso del panel primario cae en la zona inconclusa de §8. Nunca se
  sube el escalón para «mejorar» un piso que ya alcanzó adopción, ni
  desde la zona de archivo.
- Los ids que la v2 había declarado para este mismo panel
  (train [200..223], held-out [300..315]) **quedan descartados** por
  el incidente de §5.7, aunque la corrida de la v2 nunca los usó.
- Adoptar un panel significa adoptar el paquete completo
  (δ_nuevo + panel + ids): antes de evaluar cualquier candidato con
  el panel nuevo, el scaffold base debe ser evaluado sobre ese panel
  (parte del recableado, fuera de esta calibración).

### 5.6 Procedimiento de virginidad (alcance explícito) y reverificación

**El criterio, declarado con su alcance:** un id es virgen si no
aparece en **ninguna posición estructural de id de réplica** en
**ningún** archivo JSON/JSONL del árbol completo de
`~/workspace/alma-prototype`: listas de enteros bajo claves tipo
`replicas`/`seeds`/`panel`/`ids`/`train`/`held`/`split` y escalares
bajo esas claves, claves de dict que parsean como entero con valores
numéricos (dicts id → regret), y cualquier secuencia de ≥2 enteros
en cualquier posición (estas últimas se clasifican por contexto:
una aparición como índice de ítem de un dataset — p. ej.
`/gsm8k/indices_originales` — es maquinaria ajena, no uso como
réplica, y se declara por transparencia en vez de contarse como
uso). Virginidad significa exactamente eso: ausencia en ese
barrido, con ese alcance.

**Este documento ordena repetir ese barrido — el amplio, sobre el
árbol completo, no el acotado de la v1/v2 — inmediatamente antes de
correr, sobre el workspace tal como esté ese día** (Paso 1, §7).
Si el barrido previo encuentra algún id declarado (pool o panel)
usado en posición de réplica, se reemplaza por el rango virgen
verificado más cercano y se asienta el reemplazo en el documento de
resultados **antes** de evaluar nada (§9).

**Reverificación al redactar esta v3 (16/10/2026), con recibo:**
barrido estructural sobre los 375 archivos JSON/JSONL del árbol
(373 parseados; los 2 no parseables —
`resultados/exp35-20260927/report.json`, cuyos seeds son
[3521..3528], y `producto/router-puro/mvp/shadow/mediciones.jsonl`,
sin claves de id — se inspeccionaron en texto, sin ids candidatos).
El barrido detectó todos los controles conocidos (pool v1
[1000..1019], pool v2 [2000..2029], EXP64b en [200..219], seeds de
exp30 en [3021..3028]) y declara:

- train [400..417] y [400..423]: **vírgenes** como ids de réplica.
  Únicos hits, de maquinaria ajena y declarados: 402, 404 y 421 en
  `data_exp11/seleccion.json` y 409, 411 y 414 en
  `data_exp12/seleccion.json`, todos en `/gsm8k/indices_originales`.
- held-out [600..611] y [600..615]: **vírgenes** como ids de
  réplica. Hits ajenos declarados: 602 y 609 (`data_exp11`), 604 y
  614 (`data_exp12`), mismo contexto GSM8K.
- pool [4000..4029]: **virgen, sin hits de ninguna categoría.**

### 5.7 El incidente de virginidad de la v2 (asentado)

La v2 declaró vírgenes los ids de panel [200..223] / [300..315] a
partir de un barrido de 256 archivos que **omitió el directorio
`integracion_fase21/`**. El barrido amplio posterior encontró que
**EXP64b (28/9/2026,
`integracion_fase21/resultados/exp64b-ablacion-probe-thompson-20260928/report.json`)
ya había usado las réplicas [200..219]** en su clave `/replicas`,
sobre la misma maquinaria de regret. La corrida de la v2 **nunca
evaluó esos ids** — se detuvo en su Paso 3 por la caída de H4, y los
ids de panel solo existían como declaración — así que **ninguna
medición quedó contaminada**: es un **defecto de alcance de la
auditoría de la v2, no un defecto de su ejecución**, y la frase de
sus resultados «esos ids quedan vírgenes» queda corregida por este
asiento en lo que toca a [200..219]. Los [300..315] salieron
vírgenes bajo el criterio estructural (único hit: 306, índice de
ítem GSM8K en `data_exp11/seleccion.json`, declarado por
transparencia), pero se movieron igual, para no arrastrar un bloque
cuya otra mitad cayó. El rango de pool [3000..3029] que se había
propuesto para esta v3 se descartó con motivo escrito: 3021–3028 ya
aparecen como `/seeds` en `resultados/exp30-20260927/report.json`
(exp30, 27/9/2026). De este incidente salen el procedimiento de
§5.6 y su repetición obligatoria antes de correr.

## 6. Hipótesis (escritas antes de correr)

- **H1′ (el panel manda):** con el diseño P y σ = 9,04, el piso A/A
  del panel 18/12 es ≤ 0,25 (esperado 0,232). La reducción frente a
  0,5331 viene del tamaño de panel (√n), no de aparear la medición —
  la v1 ya demostró que el apareamiento entre paneles, con el panel
  actual, no reduce nada (0,5623 ≥ 0,5320).
- **H2 (determinismo):** la varianza de medición repetida vuelve a
  ser exactamente 0 (Paso 0). Si falla, todo se detiene.
- **H3 (el held-out sigue mandando el ruido):** en todo panel 3:2,
  sd(Δ_ho) > sd(Δ_in), porque n_ho < n_in.
- **H4 (validez del estimador paramétrico, especificación de la
  v3):** el piso paramétrico a panel 3/2 calculado con **σ̂_pool**
  (el σ̂ del pool fresco de esta corrida, sin regla max) y el piso
  empírico por sorteo de paneles desde **ese mismo pool** coinciden
  dentro de ±0,10 (escala δ). Es la H4 de la v2 con la comparación
  corregida según §2.2: mismo pool, mismo σ. Si H4 cae, el diseño P
  no queda validado y no se adopta nada por esta vía.

## 7. Protocolo (todo mock, local, US$0; no se toca el validador, el stream, las tasas ni `gate.py` durante la calibración)

**Paso 0 — Auditoría de determinismo.** Como la v1: evaluar el
scaffold base sobre [0,1,2] + [3,4], 10 veces sin caché; esperado:
identidad exacta. Cualquier diferencia detiene el protocolo. Se
asienta la duración medida (referencia v1: evaluación completa =
0,097 s; estimado total de esta corrida: decenas de segundos; el
umbral de 1 h de la v1 sigue vigente para reducir B, asentando el
cambio).

**Paso 1 — Descomposición de fuentes y σ̂_pool.** Antes de evaluar:
repetir el **barrido amplio de virginidad de §5.6** sobre el árbol
completo, tal como esté el workspace ese día, y verificar el pool
[4000..4029] y los ids de panel de §5.5 (reemplazos según §9 si
hicieran falta, asentados antes de seguir). Con el pool verificado:
reportar varianza entre bloques dentro de réplica, varianza entre
réplicas del `reg_pol` (σ̂_pool y su var), varianza de medición
repetida (Paso 0) y varianza del juez en el camino del Δ (0 por
construcción, se declara). **σ̂_pool se estima una sola vez, en este
paso**, y alimenta las dos comparaciones de §2.2; re-estimarlo
entre pasos reintroduciría la mezcla que la v3 corrige.
**Cláusula de régimen:** si σ̂_pool > 11,30 (= 1,25 × 9,04), el
generador/stream cambió de régimen respecto a lo medido por la v1:
se investiga antes de adoptar cualquier número, sea cual sea el
piso resultante.

**Paso 2 — Control A (validez interna).** Método original de
EXP-piso-ruido, panel 3/2, B = 5000, z = 2,0, semilla 12345. Debe
reproducir δ_A = 0,5331 con |δ_A − 0,5331| ≤ 0,02 (escala δ). Si no
reproduce, el pipeline cambió: se detiene todo y se investiga antes
de mirar cualquier otro piso.

**Paso 3 — Validación del estimador (H4, especificación §2.2).**
Desde el pool del Paso 1: (a) piso empírico A/A por sorteo de
paneles disjuntos a panel 3/2, con la mecánica declarada de la v1
(mismo RNG y partición); (b) δ_P(3/2) paramétrico con **σ̂_pool**
(sin regla max). Deben coincidir dentro de ±0,10 (escala δ). Se
reporta además, como referencia **informativa y no como puerta**,
δ_P(3/2) con σ_usado contra el 0,5623 que midió la v1. Si la
validación cae → rareza (§8): no se adopta nada.

**Paso 4 — El piso del panel elegido.** δ_P(18/12) con **σ_usado**,
B = 5000, semilla 12345 (totales ÷ 24 → escala δ; se reportan ambas
escalas y los sd por split). Solo si δ_P(18/12) cae en (0,25 ; 0,30]:
δ_P(24/16) con el mismo σ_usado y la misma mecánica.

## 8. Reglas de decisión y congelamiento (fijadas antes de correr)

- **δ_P(18/12) ≤ 0,25** → **δ_nuevo = δ_P(18/12)**, panel 18/12
  (ids §5.5). El escalón no se evalúa.
- **δ_P(18/12) ∈ (0,25 ; 0,30]** → se evalúa el escalón:
  δ_P(24/16) ≤ 0,25 → **δ_nuevo = δ_P(24/16)**, panel 24/16;
  δ_P(24/16) > 0,25 → **INCONCLUSO**: no se adopta ningún número;
  δ vigente queda; este documento no autoriza más escalones.
- **δ_P(18/12) > 0,30** → **ARCHIVADO por estructural**: ningún
  escalón se evalúa; el diagnóstico completo se asienta y no se
  buscan adopciones hasta rediseñar la medición (con otro
  pre-registro).
- **Qué contaría como raro** (no se adopta; se investiga y se
  archiva el intento con el diagnóstico):
  - δ_P del panel que se fuera a adoptar ≥ δ_A de esta corrida (el
    nulo recalibrado no mejora al piso original en su propia
    escala);
  - cualquier piso < 0,05 (sospecha de bug de medición: paneles no
    independientes, RNG compartido entre ids, o σ̂ ≈ 0);
  - σ̂_pool en régimen (§7, Paso 1) o validación H4 caída en su
    especificación de esta v3 (§7, Paso 3).
- **Congelamiento:** producido el resultado, δ_nuevo queda asentado
  en el documento de resultados y en el commit correspondiente
  **antes de que se evalúe cualquier candidato nuevo del meta-loop**,
  expresado en las dos escalas: δ_nuevo (escala δ) y su equivalente
  en totales (δ_nuevo × 24), junto con el panel y sus ids. Entre el
  congelamiento y el recableado no se corre el meta-loop con fines
  de adopción, y **dentro de la corrida de recalibración no se evalúa
  ningún candidato** contra δ nuevo ni viejo. La **forma** de la
  regla no cambia: `Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(Δ_in, Δ_ho) > δ`,
  puerta pura y E3 intactos; el recableado compara en una sola
  escala (la declarada en el congelamiento). Cualquier cambio
  posterior de δ, del panel o de sus ids exige **otro pre-registro**.
  Recalibrar después de ver candidatos es mover el arco y está
  prohibido por este documento.

## 9. Qué invalida la recalibración o archiva el intento

- Paso 0 con cualquier diferencia entre repeticiones → invalidada
  hasta explicar el no-determinismo.
- δ_A fuera de la tolerancia de reproducción (±0,02) → invalidada
  hasta explicar qué cambió en el pipeline desde el 30/9.
- El barrido amplio previo (§5.6, Paso 1) encuentra algún id
  declarado (pool o panel) usado en posición de réplica → se
  reemplaza por el rango virgen verificado más cercano y se asienta
  el reemplazo en el documento de resultados **antes** de evaluar
  nada: es el procedimiento de §5.6 funcionando, no una
  invalidación.
- Contaminación del pool [4000..4029] descubierta **después** de
  usado (algún id ya había sido usado por otra corrida sin que el
  barrido lo viera) → los Pasos 1/3 quedan invalidados y se rehacen
  con ids verificados como vírgenes, asentando el error y el hueco
  del barrido que lo dejó pasar.
- Validación H4 caída (especificación §2.2), σ̂_pool en régimen, o
  cualquier rareza de §8 → no se adopta; intento archivado con
  diagnóstico (no se «arregla» el método hasta que dé el número
  deseado).
- δ_P(18/12) > 0,30 → archivado por estructural (§8).
- Si algún paso exigiera tocar el validador congelado, el stream o
  las tasas → fuera de alcance: se detiene y se registra.

## 10. Presupuesto y alcance

- **US$0.** Todo mock/local sobre el validador congelado; sin keys,
  sin juez LLM, sin servicio.
- **Duración estimada:** decenas de segundos (≈ 30 réplicas del pool
  + control A + sorteos; referencias medidas en la v1). Si la
  duración medida superara 1 h, se asienta y se reduce B antes de
  seguir — reducir B es cambio de resolución, no de criterio, y
  queda asentado en resultados.
- Si el protocolo exigiera gasto con key en cualquier punto, queda
  **fuera** de este pre-registro y requiere otro, con presupuesto y
  «sí» explícito con costo y tiempo.

## 11. Limitaciones y supuestos declarados (sin maquillar)

1. **Sin holdout independiente para el juez barato:** la batería de
   selección del juez (n=30) es el mismo conjunto con el que se
   eligió a mistral-nemo y con el que se cita su 28/30; no existe un
   set holdout independiente para ese número. (El juez no entra en
   esta recalibración; es la limitación viva del sistema de medición
   y se registra igual que en la v1 y la v2.)
2. **El EMI viene de otra puerta.** EXP76 es la puerta de admisión
   de skills y su Δ se midió en la métrica de esa puerta (scores de
   interfaz), no en puntos de regret del validador. El EMI = 0,3636
   de §4 es una **decisión de diseño** (la vara que el piso debe
   poder detectar), declarada como tal — no una resta entre unidades
   idénticas. Si un día el meta-loop produce su propio efecto
   histórico grande en su escala, el EMI debería re-declararse en un
   pre-registro futuro con ese número.
3. **El piso vale solo para este validador y esta batería:** δ se
   calibra sobre el mismo stream congelado de 240 ítems que después
   juzga a los candidatos; no hay holdout de ítems posible sin
   descongelar el validador. δ_nuevo no se exporta a otro validador,
   otra batería ni otra escala.
4. **σ̂_pool se estima con 30 réplicas:** su error relativo típico es
   ~13% (n=30, normal). Se mitiga con la regla max(σ̂_pool, 9,04)
   para el piso de adopción y con la cláusula de régimen, pero el
   piso resultante hereda esa incertidumbre: δ_P es una estimación,
   no una constante física. B = 5000 reduce solo el error de Monte
   Carlo de los sorteos. La validación de §2.2, en cambio, compara
   a igual σ̂_pool a propósito: su objeto es el modelo, no el piso.
5. **El diseño P supone** réplicas con ids distintos =
   realizaciones independientes del mismo generador, y `reg_pol`
   aproximadamente normal entre réplicas (media de 24 bloques; el
   modelo reprodujo las mediciones de la v1, §5.1). La validación
   empírica del Paso 3 es el control declarado de este supuesto.
6. **Advertencia de costo futuro — el truco del panel cuesta plata
   fuera de este simulador.** Acá, bajar el piso con más réplicas es
   casi gratis porque el «juez» es un simulador determinista
   (0,02 s por réplica). Si el validador fuera el juez LLM actual
   (mistral-nemo), cada réplica son 240 juicios: el panel 18/12
   serían **7.200 juicios por evaluación de candidato (×6 frente a
   los 1.200 del panel 3/2 actual)** y el escalón 24/16,
   **9.600 (×8)**; una corrida de 8 rondas a panel 18/12 rondaría
   los 57.600 juicios. Los archivos no registran un precio por juicio
   utilizable para proyectar en dólares (la batería de EXP-JUEZ-001
   asienta `costo_usd = 0,0`), así que la proyección honesta es la
   fórmula — juicios × precio por juicio vigente — y la obligación
   de pre-registrar ese costo **antes** de exportar este panel a
   cualquier validador con juez real. Este piso no se exporta a ese
   futuro sin ese papel.
7. **Supuestos nuevos de la v3, declarados:**
   - **Criterio de virginidad con alcance explícito:** «virgen» es
     una afirmación sobre el barrido estructural de §5.6 (árbol
     completo de JSON/JSONL; posiciones de id de réplica; hits de
     maquinaria ajena clasificados por contexto y declarados, no
     contados como uso). Su punto débil conocido es el alcance —
     el incidente de §5.7 nació de un barrido que no miró todo el
     árbol — y por eso el protocolo ordena repetir *ese* barrido,
     ya no el acotado de la v1/v2, inmediatamente antes de correr,
     sobre el workspace tal como esté ese día.
   - **σ̂_pool se estima una sola vez** (Paso 1, §7) y alimenta
     validación y adopción; re-estimarlo entre pasos reintroduciría
     la mezcla que §2 corrige.
   - **El incidente de virginidad queda clasificado** como defecto
     de alcance de auditoría de la v2, no de ejecución (§5.7): la
     v2 corrió lo que su barrido declaró; el error estaba en lo que
     el barrido no miró.

## 12. Entregables (cuando se corra, con otro «sí»)

- Documento de resultados junto a este pre-registro: resultado del
  barrido amplio de virginidad previo (pool y panel verificados, o
  los reemplazos asentados), Paso 0 (10/10 idénticas o el hallazgo),
  descomposición de fuentes con σ̂_pool y σ_usado, δ_A con su desvío,
  validación H4 en la especificación de §2.2 (empírico vs paramétrico
  a 3/2, ambos con el σ̂ del pool) más la referencia informativa con
  σ_usado contra 0,5623, δ_P(18/12) (y δ_P(24/16) solo si el escalón
  se disparó), veredicto según §8, y δ_nuevo congelado con su panel,
  sus ids y su equivalente en totales — o el archivo del intento con
  su diagnóstico.
- Asiento en el ledger del meta-loop del evento «recalibración de δ
  v3» con el número viejo, el nuevo (o «sin cambio») y la referencia
  a este documento.

---

*Fuentes de cada dato: `resultados-recalibracion-delta-2026-10-16.md`
y `data_recalibracion_delta/resultados.json` (corrida v1: pisos,
descomposición, pool [1000..1019], duraciones);
`resultados-recalibracion-delta-v2-2026-10-16.md` y
`data_recalibracion_delta_v2/resultados.json` (corrida v2: σ̂ del pool
[2000..2029] = 7,3688, caída de H4 = 0,1022, reescalado 0,4557 vs
0,4569); `preregistro-recalibracion-delta-2026-10-16.md` (v1) y
`preregistro-recalibracion-delta-v2-2026-10-16.md` (v2: protocolo,
tabla de decisión, limitaciones que esta v3 hereda);
`alma_service/gate.py` (PISO_RUIDO_DELTA = 0,53 y la regla de
auto-adopción); `alma_service/metaloop.py` (`_evaluar`: media de
`reg_pol` por panel; splits [0,1,2]/[3,4]; E3 vía `puerta_e3.py` en
[500,501]); `data_exppisorruido/` (calibración original, δ = 0,5331);
`data_exp76/resultados_exp76.json` (Δ_down = +0,3636, Δ_ref =
+0,3807); `alma_service/exp_juez_001_resultados.json` (juez nemo
28/30, costo asentado 0,0);
`integracion_fase21/resultados/exp64b-ablacion-probe-thompson-20260928/report.json`
(EXP64b, 28/9/2026: `/replicas` = [200..219] — el incidente de §5.7);
`resultados/exp30-20260927/report.json` (exp30, 27/9/2026:
`/seeds` = 3021–3028 — el descarte de §5.7); `data_exp11/seleccion.json`
y `data_exp12/seleccion.json` (`/gsm8k/indices_originales`: los hits
ajenos declarados en §5.6). Los pisos esperados de §5.2 se calcularon
para la v2 con Monte Carlo de 400.000 sorteos normales a σ = 9,04
(semilla 12345) y esta v3 los hereda sin recalcular; la corrida, si
se autoriza, usará B = 5000 como declara §5.4.*
