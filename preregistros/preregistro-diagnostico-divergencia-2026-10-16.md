# Pre-registro — Diagnóstico de la divergencia train → held-out (revisión §9)

**Fecha:** 2026-10-16 · **Autorización:** Alejandro, «Sigamos» —
sobre la mesa que dejó el §9 del pre-registro del crossover ·
**Estado al abrir:** el meta-loop está **DETENIDO** (freno de
estancamiento **3/3 ACTIVO**, evento `metaloop_freno_estancamiento`,
ledger de 42 eventos con cadena íntegra, último hash
`6323c3c06616…`). **Presupuesto: US$0** — simulador determinista
local, ningún LLM en ningún paso.

## 1. Qué es este documento — y qué no es

Esto es un **paquete de diagnóstico**, no una corrida del loop.
No desbloquea el freno, no propone candidatos, no adopta nada, no
toca `gate.py`, ni el panel cableado en `metaloop.py`, ni el
validador congelado, ni el split E3, ni el panel de confirmación
[5000..5017]/[5100..5111] (que sigue virgen y fuera de alcance).
Las particiones de D1 son **de análisis**, no un panel nuevo de
puerta: ningún número de este paquete alimenta una decisión de
adopción, hoy ni nunca, por esta vía.

Su único producto es una **respuesta medida** a la pregunta que
el §9 del pre-registro del crossover dejó escrita para la
revisión humana, más las palancas siguientes declaradas como
opciones (papel y costo de cada una) en el documento de revisión
— **ninguna se ejecuta en este paquete**.

## 2. La pregunta

**¿Por qué todo candidato positivo en train se revierte en
held-out?** Tres búsquedas, tres métodos distintos, el mismo
patrón al llegar a la puerta:

| búsqueda | mejor marca en train | en held-out |
|---|---|---|
| RSO (mutación puntual) | ninguna positiva (8/8 ≤ 0) | — |
| Generador LLM (nemo) | finalista P5: Δ_in **+0,0556** (1,0% del piso) | Δ_ho **−0,7500** |
| Crossover | 6/24 positivos; finalista hijo 9: Δ_in **+1,4444** (26,4% del piso) | Δ_ho **−3,0833** |

Las lecturas en danza son dos, y este diagnóstico existe para
discriminarlas con números, no para elegir la más cómoda:

- **(E) El espacio de scaffold está agotado**: la base es un
  óptimo local robusto de las 324 configuraciones (60 con
  medición train asentada al cierre del crossover; 89 contando
  tandas y screening) y los «positivos» de train son la cola de
  ruido que cualquier búsqueda termina encontrando.
- **(P) La estructura de paneles no deja ver la mejora**: el
  Δ de train no generaliza entre paneles del mismo simulador —
  por ruido de subpanel dentro de train, por promedios cargados
  por pocas réplicas, o por una relación train→held-out débil
  en la región de los ganadores — y la selección por train
  elige exactamente ese ruido (maldición del ganador).

D1 mira **dentro** de train; D2 mira **dentro del promedio** de
los dos finalistas; D3 mide, por primera vez y con gasto
declarado, la **relación entre paneles** en la región que
importa.

## 3. Conjuntos, convenciones y anclas de validez

**Evaluador.** El de siempre, sin tocar: `MetaLoop._evaluar`
corre `e56.correr_replica_param` con el stream y las tasas de
`e47` (validador congelado) y devuelve el `reg_pol` por
réplica. Este paquete usa esa misma maquinaria y guarda el
`reg_pol` **por réplica** de cada configuración medida.

**Convención de Δ.** La de todos los papeles de hoy:
Δ(config, réplicas) = media_base − media_config sobre el
conjunto de réplicas, en totales por réplica. Positivo = la
configuración rinde mejor que la base (menos regret). Base:
{decay 0,5 · gate_margin 0,0 · n0 4 · umbral_base 1 ·
umbral_divisor 3}. Panel train [400..417] (18 réplicas), media
de la base **85,2222**; panel held-out [600..611] (12),
media de la base **80,6667**.

**Conjunto de configuraciones (cerrado, 35):**

- **X1–X24** — los 24 hijos del crossover, con la configuración
  y el Δ_train oficial de
  `data_crossover_2026-10-16/mediciones.json`. El **hijo 9
  (X9)** es el finalista del crossover.
- **P1–P11** — los 11 válidos de la tanda del generador, en el
  orden de `tanda_generador_1792192469.json`. **Marco
  declarado:** en su corrida, P1–P5 se midieron contra la base
  y P6–P11 contra P5 retenido (evaluación voraz); **este
  diagnóstico recalcula las 11 independientes contra la base**
  y esos números — no los de la corrida — son los del
  diagnóstico. **P5** es el finalista del generador.

**Anclas de validez (fail-closed).** Antes de interpretar nada,
la recomputación debe reproducir: (a) el Δ_train oficial de
X1–X24 (tolerancia 5·10⁻⁵; los valores asentados están
redondeados a 4 decimales); (b) el Δ_train independiente de
P1–P5 del informe del generador (−4,3333 · −3,7222 · −0,4444
· −3,8889 · +0,0556; misma tolerancia); (c) las medias de la
base, 85,2222 en train y 80,6667 en held-out (misma
tolerancia). **Si una sola ancla falla, el paquete se detiene:
no se interpreta nada y se reporta la discrepancia.**

## 4. D1 — Consistencia interna de train (split-half)

**Partición primaria, declarada antes de medir:** las 18
réplicas de train en dos mitades de 9 **por paridad de índice**
en la lista ordenada [400..417]: mitad **A** = posiciones
pares → {400, 402, 404, 406, 408, 410, 412, 414, 416}; mitad
**B** = posiciones impares → {401, 403, 405, 407, 409, 411,
413, 415, 417}. **Robustez secundaria (declarada, solo
descriptiva):** partición contigua, primera mitad {400..408}
contra segunda {409..417}, con las mismas estadísticas.

**Por configuración (las 35):** Δ_A, Δ_B y Δ_completo.
**Estadísticas del conjunto:** acuerdo de signo entre mitades
(categorías +, 0, −; se reporta también el acuerdo ignorando
los ceros exactos), correlación de Pearson r(Δ_A, Δ_B) y
Spearman ρ. **En el subconjunto que importa** — las 7
configuraciones con Δ_completo > 0 (X4, X7, X9, X10, X13, X17
y P5, si la recomputación confirma los signos) —: cuántas son
positivas **en ambas mitades**.

**Reglas de lectura (escritas antes de los números):**

- Si **r < 0,3** en la partición primaria, **o** de las 7
  positivas a lo sumo **3** lo son en ambas mitades → el
  «positivo de train» es en gran parte **ruido de subpanel**: el
  signo no es estable ni dentro del panel donde se seleccionó.
- Si **r ≥ 0,6** **y** al menos **6 de 7** positivas lo son en
  ambas mitades → la señal de train es **internamente
  estable**; la divergencia vive **entre paneles** (y la
  palabra pasa a D3).
- Cualquier resultado intermedio se declara **mixto**, con los
  dos números sobre la mesa. No hay lectura intermedia
  disfrazada de concluyente.

## 5. D2 — Jackknife por réplica de los dos finalistas

**Objeto:** X9 (finalista del crossover, Δ_train +1,4444) y
P5 (finalista del generador, Δ_train +0,0556). Para cada uno,
el **vector Δ_r** = reg_base(r) − reg_config(r) sobre las 18
réplicas de train, completo y asentado en los datos crudos.

**Medidas declaradas:**

- Conteo de réplicas con Δ_r > 0, = 0 y < 0; **masa positiva**
  (Σ Δ_r sobre las positivas) y **masa negativa** (Σ |Δ_r|
  sobre las negativas); fracción de masa positiva sobre la
  masa total |Δ|.
- **Dejar-una-fuera (LOO):** las 18 medias sin cada réplica —
  mínimo, máximo, y **cuántas remociones individuales cambian
  el signo** del promedio.
- **Número portador de signo k\***: la menor cantidad de
  réplicas — retirando siempre la de mayor Δ_r positivo
  primero (voraz descendente, declarado) — cuya remoción lleva
  el promedio a ≤ 0. Es la respuesta a «¿cuántas réplicas
  cargan el promedio?».
- Error estándar jackknife del promedio (solo descriptivo).

**Reglas de lectura:**

- Si **k\* ≤ 3**, o **alguna remoción individual** cambia el
  signo → el promedio lo cargan **pocas réplicas**: efecto
  frágil, compatible con interacción configuración×stream en
  un puñado de réplicas, no con una mejora repartida.
- Si **k\* ≥ 7** y **ninguna** remoción individual cambia el
  signo → el promedio es **de base ancha** dentro de train.
- Intermedio → fragilidad parcial, declarada como tal.

## 6. D3 — Gasto declarado y acotado de held-out como diagnóstico

**Medición:** Δ sobre held-out [600..611] de exactamente
**7 configuraciones**: los 6 hijos del crossover con
Δ_train > 0 (X4, X7, X9, X10, X13, X17) y el finalista del
generador (P5). Nada más se mide en held-out en este paquete;
el E3 **no se toca**; el panel de confirmación **no se toca**.

**Declaraciones previas (parte del pre-registro, no una
aclaración posterior):**

- **(a) Sin vía de adopción, jamás.** Estas mediciones son
  diagnóstico puro. **Ninguna de las 7 configuraciones puede
  ser adoptada apoyándose en este paquete**, ni hoy ni en el
  futuro: si alguna volviera a ser candidata, deberá recorrer
  el camino normal completo (propuesta → puerta → splits
  ciegos), y su ganancia oficial, si la hubiera, seguirá
  siendo la del **panel de confirmación**, como manda la
  adenda 1 del generador.
- **(b) Costo de ceguera acotado y asentado.** El gasto es
  exactamente este: el signo y la magnitud de Δ_ho de estas 7
  configuraciones dejan de ser ciegos para quien lea el
  informe. Nada más del panel held-out se revela (ninguna otra
  configuración, ningún dato por réplica que no sea el de las
  7). El costo queda asentado aquí y en el evento de
  auditoría del cierre.
- **(c) El estimando es la relación, no un ganador.** Se
  reportan los 7 pares (Δ_train, Δ_ho), el acuerdo de signo,
  la correlación de Pearson y la recta de regresión
  Δ_ho ~ Δ_train (pendiente e intercepto) **como descripción
  de la región de los ganadores de train**. Salvedad escrita
  antes: las 7 fueron **seleccionadas** por Δ_train > 0 — la
  restricción de rango atenúa r y la pendiente, y la maldición
  del ganador sesga Δ_ho a la baja respecto del efecto «real»
  de cada configuración; por eso la lectura primaria es el
  **signo**, que la selección no fabrica.

**Anclas específicas (fail-closed):** la recomputación debe
reproducir los dos Δ_ho que el camino normal ya asentó — X9:
**−3,0833** y P5: **−0,7500** (tolerancia 5·10⁻⁵). Si no
reproducen, el paquete se detiene igual que en §3.

**Reglas de lectura:**

- Si **≥ 5 de 7** revierten el signo y **r ≤ 0** → en la
  región de los ganadores, la generalización train→held-out
  está **ausente**: seleccionar por train elige ruido propio
  del panel train.
- Si la mayoría **conserva el signo** con **0 < pendiente
  < 1** → hay señal real con **contracción** (maldición del
  ganador cuantificada): el problema sería de magnitud y de
  piso, no de dirección.
- Patrón sin mayoría clara → se declara **indeterminado en
  esta región** y se dice qué medición lo resolvería.

## 7. Regla de síntesis — cómo se responde la pregunta §9

La respuesta del documento de revisión se construye
**mapeando el patrón observado a través de esta tabla**,
declarada antes de medir. No se admiten interpretaciones
fuera de la tabla sin declararlas como tales.

| patrón observado | respuesta §9 |
|---|---|
| D1 inestable (ruido de subpanel) y/o D2 frágil en ambos finalistas | **Ni (E) ni (P) probadas por separado: manda el ruido de medición/selección.** Con 18 réplicas y la varianza entre réplicas medida en la recalibración v3 (sd ≈ 8,6–9,0 por réplica), los Δ de 0,05–1,44 que las búsquedas persiguen están por debajo de la resolución con que train puede certificarlos: el «positivo de train» era, en lo medible, ruido seleccionado. El cuello de botella es la **relación señal/ruido del panel de selección** — un hecho sobre la medición, anterior a cualquier juicio sobre el espacio. |
| D1 estable, D2 de base ancha, D3 con reversión ≥ 5/7 y r ≤ 0 | **(P) estructura de paneles.** La señal existe y es estable *dentro* de train, pero es propiedad del panel (interacción configuración×stream repartida), no de la configuración sola: el cuello de botella es **qué mide la búsqueda** (train solo) y con qué paneles se confirma. |
| D1 estable, D2 de base ancha, D3 conserva signo con contracción | **(E) gana apoyo medido.** Hay señal que generaliza en dirección pero no alcanza el piso: la base queda como óptimo local robusto *a esta resolución*, y la lectura «espacio agotado» pasa a ser la explicación parsimoniosa de las tres búsquedas. |
| Cualquier otra combinación | **Mixta o indeterminada**, declarada como tal, con la medición faltante nombrada. Prohibido forzar un veredicto. |

En todos los casos, la revisión debe además reportar el dato
duro de resolución: el error estándar apareado de un Δ sobre
18 réplicas (de los propios vectores Δ_r de D2 y de la
dispersión entre réplicas ya medida en la recalibración v3)
contra el tamaño de los efectos perseguidos (0,05–1,44) y
contra el piso de la puerta (5,4781).

## 8. Cierre y entregables

1. **Datos crudos** en `data_diagnostico_divergencia_2026-10-16/`:
   `reg_por_replica.json` (reg_pol por réplica: base y las 35
   configuraciones en train; base y las 7 de D3 en held-out),
   `analisis.json` (todas las estadísticas de D1/D2/D3) y el
   script `run_diagnostico.py` que los produce.
2. **Documento de revisión** `revision-seccion9-2026-10-16.md`:
   resultados de D1/D2/D3 con tablas, el patrón observado
   mapeado por la tabla de §7, la respuesta a la pregunta §9
   (espacio vs paneles, con la evidencia) y las **palancas
   siguientes como opciones** — cada una con su papel nuevo y
   su costo — **sin ejecutar ninguna**.
3. **Ledger:** al cierre se asienta **un** evento de auditoría
   de tipo `diagnostico_divergencia` (con el resumen de
   hallazgos y el gasto de ceguera de D3 declarado). Ningún
   evento de corrida, de propuesta ni de adopción. Cadena
   recomputada e íntegra al cierre.
4. **Estado final declarado:** freno **activo 3/3** (este
   paquete no lo toca), scaffold vigente = la base, adopciones
   históricas **0**, panel de confirmación **virgen**, E3 sin
   tocar.
5. **Suites** de gobernanza en verde y **commits locales**
   separados: este pre-registro primero (antes de medir);
   el diagnóstico y la revisión después.

*Fin del pre-registro.*
