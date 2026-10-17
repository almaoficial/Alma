# Revisión §9 — Diagnóstico de la divergencia train → held-out

**Fecha:** 2026-10-16 · **Pre-registro:**
`preregistro-diagnostico-divergencia-2026-10-16.md` (commit
`c71ea8a`, asentado **antes** de medir) · **Autorización:**
Alejandro, «Sigamos» · **Estado durante todo el paquete:** el
loop **detenido** — freno de estancamiento **3/3 ACTIVO**; esto
es análisis sobre mediciones ya hechas y mediciones
diagnósticas declaradas, no una corrida. **Costo: US$0.**
Medición completa: 13,8 s de simulador determinista.

## 1. La respuesta, primero

La pregunta del §9 era dónde está el cuello de botella: el
**espacio** de scaffold (E) o la **estructura de paneles** (P).
Aplicando la tabla de síntesis declarada en el §7 del
pre-registro al patrón observado, la respuesta es la **fila 1**:

> **Ni (E) ni (P) quedan probadas por separado: manda el ruido
> de medición/selección.** El panel de selección (train, 18
> réplicas) **no tiene resolución** para los efectos que las
> tres búsquedas persiguieron (0,05–1,44 totales): el error
> estándar apareado de un Δ sobre ese panel es **0,57–1,37**
> según la configuración. El «positivo de train» que cada
> búsqueda terminó seleccionando era, en lo medible, **ruido
> seleccionado** — inestable entre mitades del propio panel
> (D1), cargado por 1–2 réplicas (D2) — y en la región de los
> ganadores la relación con held-out no es cero: es
> **negativa** (7/7 reversiones, r = −0,65; D3).

Esto no absuelve ni condena al espacio: dice que **con esta
resolución no se puede saber** si entre las 324 configuraciones
hay una mejor que la base. Lo que sí se puede saber — y quedó
medido — es que seguir buscando con la métrica y el panel
actuales seguiría produciendo el mismo patrón, porque el
patrón lo genera la etapa de selección, no el método de
búsqueda. Tres métodos distintos (mutación, LLM, recombinación)
ya lo demostraron por triplicado.

## 2. Anclas de validez — todas reproducidas

Antes de interpretar, la recomputación con la maquinaria
congelada reprodujo **exactamente** (tolerancia 5·10⁻⁵): los
24 Δ_train oficiales del crossover; los Δ_train independientes
de P1–P5 del informe del generador; las medias de la base
(85,2222 train · 80,6667 held-out); y los dos Δ_ho que el
camino normal ya había asentado (X9: −3,0833 · P5: −0,7500).
Las anclas pasaron, así que los números que siguen son del
mismo evaluador que produjo las tres corridas — no hay una
discrepancia de instrumento escondida en el diagnóstico.

## 3. D1 — Dentro de train, el signo de los ganadores no es estable

Partición primaria declarada: mitades por paridad de índice —
A = {400, 402, …, 416}, B = {401, 403, …, 417}. Sobre las 35
configuraciones: **r(Δ_A, Δ_B) = 0,6174** (Spearman ρ =
0,6535); acuerdo de signo **21/35**. La correlación global
supera el umbral de 0,6 del papel — pero la regla declarada
exige **además** que al menos 6 de las 7 positivas lo sean en
ambas mitades, y ahí está el resultado:

| config | Δ completo | Δ_A | Δ_B | ¿positiva en ambas? |
|---|---|---|---|---|
| X4 | +0,6667 | +1,3333 | 0,0000 | no (cero en B) |
| X7 | +0,7222 | +0,4444 | +1,0000 | **sí** |
| X9 | +1,4444 | +1,2222 | +1,6667 | **sí** |
| X10 | +0,0556 | +0,5556 | −0,4444 | no (revierte) |
| X13 | +0,6111 | +0,8889 | +0,3333 | **sí** |
| X17 | +0,6667 | +1,3333 | 0,0000 | no (cero en B) |
| P5 | +0,0556 | +0,8889 | −0,7778 | no (revierte) |

**3 de 7.** Por la letra del pre-registro (la cláusula «a lo
sumo 3 de 7» dispara la lectura de ruido de subpanel; la
lectura de estabilidad exige ≥ 6/7), **D1 cae del lado del
ruido en la región que importa**. La partición secundaria
(contigua 400–408 vs 409–417, solo descriptiva) cuenta lo
mismo con otros números: r = 0,7859 y 4 de 7 en ambas mitades.

La correlación global de 0,62 no contradice esto: la cargan
las configuraciones **muy** negativas, que son negativas en
todas partes. Dato descriptivo (corte posterior, declarado
como tal, no una prueba del papel): el acuerdo estricto de
signo entre mitades por banda de |Δ| es **15/15** para
|Δ| ≥ 2, **6/13** para 0,5 ≤ |Δ| < 2 y **0/7** para |Δ| < 0,5.
El panel certifica sin dudar los efectos grandes — todos los
«muy malos» son muy malos en cualquier mitad — y es una moneda
al aire exactamente en la banda donde viven todos los
ganadores jamás seleccionados (0,05–1,44). *(Nota de
transparencia: X4 y X17, que difieren solo en gate_margin
0,05 vs 0,10, produjeron vectores de regret idénticos en
ambos paneles — sobre estos streams son la misma
configuración en comportamiento.)*

## 4. D2 — Los dos promedios finalistas los cargan 1–2 réplicas

**X9 — Δ_train +1,4444** (vector Δ_r completo en los datos
crudos). Réplicas: 9 positivas, 1 cero, 8 negativas; masa
positiva 44 contra masa negativa 18. Pero el promedio neto es
+26 puntos-réplica, y **una sola réplica — la 403, con
Δ_r = +21 — aporta el 48% de toda la masa positiva**; la
segunda portadora es la 412 (+8). **k\* = 2**: retirando esas
dos, el promedio cae a ≤ 0. Ninguna remoción individual lo da
vuelta (LOO mínimo +0,2941) — pero la regla declarada dice
k\* ≤ 3 → **frágil**, y k\* = 2 lo es. Su propio error
estándar apareado es **1,3677** (jackknife = clásico, como
debía ser para una media): el +1,4444 del finalista del
crossover es **1,06 errores estándar** sobre cero.

**P5 — Δ_train +0,0556.** 9 positivas, 2 cero, 7 negativas;
masa positiva 19 contra negativa 18: el neto es **+1
punto-réplica sobre 18**. **k\* = 1** (basta retirar su mejor
réplica, la 412 con +4) y **9 de las 18 remociones LOO
cambian el signo** del promedio. Error estándar **0,5744**:
el efecto que el generador «encontró» es **0,10 errores
estándar** — indistinguible de cero por un orden de magnitud.

**Lectura según el papel: D2 frágil en ambos finalistas.**
Ninguno de los dos promedios es una mejora repartida sobre el
panel; son la suma de un puñado de interacciones
configuración×réplica. Que la réplica 403 le regale +21 a X9
dice algo de X9 *sobre esa réplica*, no de X9 sobre el mundo
del simulador.

## 5. D3 — La relación train→held-out en la región de ganadores: negativa

Gasto declarado en el pre-registro (§6): Δ_ho de exactamente
las 7 configuraciones positivas, **solo como diagnóstico** —
ninguna puede ser adoptada por esta vía, jamás (declaración
(a) del papel; si alguna volviera, recorre el camino normal y
su ganancia oficial seguiría siendo el panel de
confirmación). El costo de ceguera queda asentado aquí y en el
evento de auditoría del ledger: el signo y la magnitud de
estas 7, nada más.

| config | Δ_train | Δ_ho | signo |
|---|---|---|---|
| X4 | +0,6667 | −0,5000 | revierte |
| X7 | +0,7222 | −3,0000 | revierte |
| X9 | +1,4444 | −3,0833 | revierte |
| X10 | +0,0556 | −0,9167 | revierte |
| X13 | +0,6111 | −0,8333 | revierte |
| X17 | +0,6667 | −0,5000 | revierte |
| P5 | +0,0556 | −0,7500 | revierte |

**7 de 7 reversiones.** Correlación de Pearson **−0,6471**;
regresión Δ_ho ~ Δ_train: pendiente **−1,5855**, intercepto
−0,4127. La magnitud media no se contrae: **crece** —
|Δ| medio 0,6032 en train contra 1,3690 en held-out (2,3×).
Por la regla declarada (≥ 5/7 reversiones y r ≤ 0): **en la
región de los ganadores de train, la generalización a
held-out está ausente — y lo medido es más fuerte que
«ausente»: dentro de esta región, ganar más en train se
asoció a perder más en held-out.** La salvedad del papel se
mantiene escrita: son 7 configuraciones **seleccionadas** por
Δ_train > 0; la selección atenúa correlaciones y sesga
magnitudes, y por eso la lectura primaria es el signo (7/7),
que la selección no fabrica. La pendiente se reporta como
descripción de la región, no como ley del simulador.

## 6. Respuesta a la pregunta §9

La tabla de síntesis del pre-registro (§7) asigna la **fila
1** cuando «D1 inestable y/o D2 frágil en ambos finalistas».
Acá se cumplen **las dos** condiciones, no una: D1 falla la
barra de estabilidad exactamente en la región de los
ganadores (3/7 contra ≥ 6/7 exigidos) y D2 es frágil en los
dos finalistas (k\* = 2 y k\* = 1). La fila 2 — la que habría
declarado ganadora a la lectura (P) — exigía D1 estable **y**
D2 de base ancha: no se cumple, aunque el patrón de D3
(7/7, r < 0) es el que esa fila esperaba. Se reporta la
tensión tal cual: **la evidencia de D3 es compatible con una
estructura de paneles anti-generalizante, pero por la tabla
declarada la atribución primaria es el ruido de
medición/selección**, porque los dos diagnósticos que miran
*dentro* de train muestran que ahí ya no había una señal
sólida que pudiera generalizar o dejar de generalizar.

El dato de resolución que el papel manda reportar, en una
línea: con sd(Δ_r) ≈ 5,8 (la del finalista X9), certificar un
efecto de +1,4444 a 2 errores estándar exige **~65 réplicas**;
el panel de selección tiene **18**. Y el piso de la puerta
**no** es el problema de resolución: 5,4781 equivale a
**4,0 errores estándar** del Δ de X9 (9,5 del de P5) — un
candidato que de verdad estuviera en el piso sería detectable
con el panel actual. El cuello de botella medido es anterior
a la puerta: **la búsqueda optimiza una métrica cuya banda de
ruido (±1,4 a 1 SE) se traga todos los efectos que cualquier
método encontró hasta hoy**, y selecciona sistemáticamente la
cola favorable de ese ruido — que es, por construcción, la
que peor generaliza.

Qué queda de las dos lecturas originales, dicho con
precisión: **(E) espacio agotado — no probada ni refutada.**
Es consistente con todo lo medido (y D1 muestra que las
configuraciones malas de verdad son malas en todas partes),
pero «no encontramos nada mejor con una regla que no puede
ver efectos menores a ~±1,4» no equivale a «no existe nada
mejor entre las 324». Hay 264 configuraciones sin medición
train asentada (60 medidas al cierre del crossover: 36 previas
+ los 24 hijos). **(P) estructura de paneles — reformulada por
la evidencia:** el problema no es solo que held-out difiera
de train; es que el propio train, a 18 réplicas, no distingue
señal de ruido en la banda de interés, y la selección sobre
él produce ganadores que anti-predicen fuera. Las palancas
que siguen atacan eso, en este orden lógico.

## 7. Palancas siguientes — opciones, ninguna ejecutada

Cada una exige **papel nuevo y autorización de Alejandro**;
con el freno activo, ninguna corrida futura arranca sin su
revisión y su token. Costos en plata: todas US$0 (simulador
local); el costo real es de diseño y de paneles.

- **L1 — Panel de selección con resolución.** Agrandar el
  panel de selección a ~66–72 réplicas vírgenes (SE ≈ 0,68 a
  sd 5,8 — la mitad del efecto de X9) o selección en dos
  etapas: pantalla en 18, confirmación de finalistas en panel
  fresco grande **antes** de la puerta. Papel: recalibración
  de panel estilo v3 (δ_P depende de n: el piso se recalcula,
  no se hereda). Es la palanca que el diagnóstico señala
  primero: cambia la resolución, no el método de búsqueda.
- **L2 — Métrica de selección con acuerdo interno.** Que un
  candidato solo avance si sus dos mitades de train acuerdan
  en signo (filtro split-half, US$0 de ceguera externa), o
  selección por Δ penalizado por dispersión entre mitades.
  Papel: pre-registro de métrica. Habría filtrado a X10 y a
  P5 antes de gastar puerta; no habría salvado a X9 (acuerda
  en ambas mitades y aun así revirtió) — se declara su límite.
- **L3 — Paneles rotativos por búsqueda.** Cada búsqueda
  sortea su panel de selección de un pool grande y fresco, en
  vez de exprimir el mismo [400..417] que ya vieron tres
  búsquedas (higiene adaptativa; el estudio web externo lo
  recomendó hoy). Papel nuevo; interactúa con δ (recalibrar).
- **L4 — Espacio de scaffold más rico.** Otros parámetros u
  otra superficie editable. Papel grande de diseño. El
  diagnóstico le pone una condición de orden: **después** de
  L1 — con la resolución actual, un espacio nuevo tampoco
  podría medirse, y se repetiría el mismo patrón con
  configuraciones más caras.
- **L5 — Aceptar el óptimo y cerrar la búsqueda en este
  scaffold.** Declarar la base óptimo operativo por acta, con
  el registro completo como evidencia (324 puntos, 60 con
  medición train asentada, la divergencia medida en este
  documento),
  y redirigir el esfuerzo fuera del laboratorio. Papel: acta
  de cierre. El freno queda como está; desbloquearlo o no pasa
  a ser una decisión sobre un sistema cerrado, no sobre una
  búsqueda en curso.

## 8. Estado al cierre (verificado)

- **Freno de estancamiento: ACTIVO, 3/3 — sin cambios.** Este
  paquete no lo tocó, no corrió el loop, no propuso ni adoptó
  nada. El desbloqueo sigue exigiendo el token
  `ALMA_TOKEN_HUMANO` de Alejandro.
- **Ledger:** 43 eventos (42 previos + **un** evento de
  auditoría `diagnostico_divergencia`, hash `2a38287b0074…`),
  cadena **recomputada e íntegra**. Ningún evento de corrida,
  propuesta ni adopción lleva la fecha de este paquete.
- **Scaffold vigente:** la base {0,5 · 0,0 · 4 · 1 · 3}, sin
  cambios. **Adopciones históricas del meta-loop: 0.**
- **Panel de confirmación** [5000..5017]/[5100..5111]:
  **virgen, sin tocar**. **E3: sin tocar.** El único gasto de
  ceguera del paquete es el declarado en §5 (las 7
  configuraciones de D3), asentado en el pre-registro antes de
  medir y en el evento del ledger.
- **Suites:** batería de gobernanza completa **51/51 archivos
  PASS** (`data_diagnostico_divergencia_2026-10-16/suites.log`).
- **Evidencia:** `data_diagnostico_divergencia_2026-10-16/` —
  `run_diagnostico.py` (el procedimiento ejecutado),
  `reg_por_replica.json` (reg_pol por réplica: base y 35
  configuraciones en train; base y las 7 de D3 en held-out),
  `analisis.json` (anclas y todas las estadísticas de
  D1/D2/D3), `suites.log`.
- **Tiempos:** medición del diagnóstico 13,8 s; suites ~20 s;
  el paquete completo (papel, medición, revisión) dentro de
  la misma noche del 16/10. **Costo total: US$0.**

Lo que sigue no está en este documento porque no le
corresponde: la decisión entre L1–L5 es de Alejandro, con
esta revisión sobre la mesa — que es exactamente el estado
en el que el freno, por diseño, lo está esperando.

*Fin de la revisión §9.*
