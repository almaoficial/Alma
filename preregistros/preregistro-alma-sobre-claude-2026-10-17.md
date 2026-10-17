# Pre-registro — ALMA sobre Muse: la gobernanza del meta-loop sobre la configuración del asistente

**Fecha:** 2026-10-17 · **Autorización:** Alejandro, 17/10/2026 03:59–04:01 EDT
(«Lo hagamos ahora»; «Usa ALMA y hacé más pruebas que nadie — te vas a dar
cuenta si mejorás, y qué podemos hacer con eso»; precisión de alcance: «Ya
sabemos que anda — usá todo lo de ALMA en vos»). **Costo autorizado:** US$0.
**Estado al firmar:** SOLO PAPEL. Este documento no corre ninguna batería sobre
la vida de Alejandro ni cambia ninguna configuración vigente; la única medición
que habilita esta misma noche es la línea de base de pantalla de la Fase 2
(§14), que mide la configuración que ya existe y no toca su vida.

## 1. Objeto y lugar en la historia — el papel nuevo que el acta de L1 exige

El 16/10/2026 el ciclo L1 cerró la búsqueda sobre el scaffold del laboratorio
con un **nulo certificado a resolución 72/48/24** (resultados-L1-2026-10-16.md
§7). La cláusula de salida ejecutada prohíbe reabrir ese espacio «sin papel
nuevo que cambie el marco (otro espacio o superficie, otra tarea u otro
validador, u otro instrumento)», y declara a la vez lo que NO cierra: «otros
scaffolds, tareas y validadores futuros».

**Este documento es ese papel nuevo.** El marco cambia en los tres ejes:

| Eje | Laboratorio (cerrado) | Este programa |
|---|---|---|
| Tarea | Simulador determinista de regret | El trabajo diario real de Muse para Alejandro |
| Superficie | Scaffold de 5 parámetros (espacio EXP56, 324 configs) | La capa de configuración comportamental del asistente (§2) |
| Instrumento | Regret por réplica, paneles de réplicas | Baterías offline sobre corpus reales + resultados de su vida (§4) |

La gobernanza **no** cambia: se traslada **entera**, sin subconjunto (§3). Lo
que el laboratorio probó — pre-registrar antes de medir, calibrar el piso
contra el ruido, no adoptar por debajo del piso, frenar y esperar al humano —
pasa a gobernar cómo Muse cambia su propia forma de trabajar. La frase de
Alejandro que funda el programa queda asentada como su hipótesis de trabajo:
*«te vas a dar cuenta si mejorás»* — el programa existe para que esa frase sea
medible, no declamada.

## 2. El scaffold nuevo: la configuración comportamental de Muse

La superficie versionable de este programa es la **capa de configuración
comportamental** del asistente en su trabajo diario: las políticas escritas
que rodean al modelo y determinan cómo se comporta. Inventario de la
superficie (cada política es versionable, comparable y reversible):

1. **Estructura del plan matutino** (07:30): formato, orden y contenido del
   plan de 3 puntos que abre su día.
2. **Selección del digest**: qué noticias entra, con qué criterio de corte.
3. **Profundidad de delegación y verificación antes de afirmar**: cuánto se
   verifica en disco/fuente antes de presentar algo como hecho.
4. **Diseño del chequeo nocturno** (23:23): qué se pregunta, en qué orden,
   en qué formato («Los 3»).
5. **Criterios del barrido del Despegue**: la puerta que filtra roles antes
   de presentarlos.
6. **Política de memoria**: qué se asienta, cuándo, con qué vara de evidencia.
7. **Umbrales de proactividad**: cuándo Muse habla sin ser preguntado y
   cuándo calla.

**Lo que NO es superficie:** el modelo. No es versionable por nosotros, como
en el laboratorio el validador no era la superficie sino el instrumento. Toda
afirmación de este programa es sobre la **configuración**, jamás sobre el
modelo (§15). Las superficies se escalonan (la primera se declara en §6; el
resto es roadmap en §6.4). La gobernanza, en cambio, rige completa desde el
primer ciclo: no hay «versión tímida» de la gobernanza (§3).

## 3. Gobernanza completa desde el día uno — mapeo 1:1 desde el laboratorio

Por precisión expresa de Alejandro (04:01), la gobernanza se traslada
**entera**. Ninguna pieza queda como roadmap; lo único escalonado son las
superficies (§6.4). Mapeo:

| Pieza del laboratorio | En este programa (vigente desde el ciclo 1) |
|---|---|
| Pre-registro antes de correr | **Pre-registro antes de cada ciclo**: superficie, UN cambio candidato, métricas, δ, panel y veredictos escritos antes de medir. Este documento es el pre-registro fundacional; cada ciclo posterior lleva el suyo. |
| Validador congelado | **Baterías y rúbricas congeladas por ciclo**: el validador de pantalla de un ciclo no se toca a mitad de ciclo; cambiarlo es un ciclo nuevo con su papel. |
| Piso de ruido δ calibrado | **δ análogo derivado** (§8): margen mínimo de adopción calculado de la varianza de la propia batería según fórmula fijada en este papel, congelado antes de medir la variante. |
| Paneles ciegos / cortafuegos | **Dos arenas con cortafuegos** (§4): la variante se selecciona en pantalla; la confirmación en vivo no alimenta la selección. |
| Panel de confirmación fresco por adopción | Tras cada adopción-en-pantalla, la confirmación corre sobre una **ventana viva nueva** (los 14 días siguientes), nunca sobre días ya usados para seleccionar. |
| Ledger con cadena de hashes | **Ledger propio del programa**: `alma-sobre-claude-ledger.jsonl` en esta misma carpeta del prototipo; cada evento lleva el hash del anterior; todo evento del programa (pre-registro, corpus, congelamiento, línea de base, veredicto, adopción, reversión, informe) se asienta ahí. |
| Freno de estancamiento (3 corridas) | **Freno de 3 ciclos**: tres ciclos sin adopción → el programa se detiene y espera revisión de Alejandro. No se baja la vara, no se extiende la ventana, no se redefine la métrica (§10). |
| Token humano / veto | **Token y veto de Alejandro intactos**: él puede frenar el programa entero en cualquier momento con una palabra; ningún cambio de configuración se adopta «en su vida» sin evento en el ledger y aviso a él (§13). |
| Informes con recibo | **Informe de auto-evaluación por ciclo** (§12), asentado en el ledger con la misma vara que mide a las variantes. |
| Corrección en el acto | Toda desviación detectada durante un ciclo se detiene, se verifica contra evidencia y se asienta — como la falsa alarma del 0,3923 en L1 — antes de seguir. |

**Regla heredada sin excepción:** recalibrar o ajustar después de ver el
resultado es mover el arco. Está prohibido en este programa igual que en el
laboratorio: los intentos que no adoptan se archivan con su diagnóstico, no
se tunean en silencio.

## 4. Las dos arenas

El diagnóstico §9 (revision-seccion9-2026-10-16.md) dejó la lección central:
con un panel de selección chico, el «ganador» es la cola favorable del ruido,
y esa cola es la que peor generaliza. El laboratorio no pudo tener paneles
grandes de confirmación. **Este programa sí puede tener panel grande donde
importa: en la pantalla.** La arquitectura es de dos arenas, como recomendó
el diagnóstico:

### 4.1 Arena de pantalla (selección)

- Baterías **offline de alto volumen** sobre corpus de tareas reales de su
  mundo (§5), reconstruidos desde los registros del workspace con procedencia
  ítem por ítem.
- **Validador congelado por ciclo**, con puntaje **determinista** (script,
  no juez LLM) siempre que la superficie lo permita; donde no lo permita, la
  rúbrica y su límite quedan declarados en el pre-registro del ciclo.
- Acá se hacen **«más pruebas que nadie»**: decenas de instancias por
  variante sobre el mismo corpus, panel dimensionado por el efecto mínimo
  de interés (§8), no por costumbre. La pantalla es barata (US$0) y
  repetible: es el panel de 72 del laboratorio, pero sobre tareas reales.
- La pantalla **selecciona**: ninguna variante pasa a su vida sin superar el
  δ de pantalla. La pantalla **no adopta sola** (§4.3).

### 4.2 Arena de confirmación (su vida, en vivo)

- Las métricas que **ya se recolectan** sin este programa: su **bit diario
  1/0** («¿el día fue bueno?»), el **veredicto planificado/improvisado** del
  cierre, el **cumplimiento de rutina** del chequeo, y las **respuestas del
  Despegue** (embudo del ledger de aplicaciones).
- Son **chicas y preciosas**, como el panel de confirmación del laboratorio:
  jamás se usan para seleccionar variantes, tunear prompts ni elegir el
  próximo ciclo. Solo confirman o vetan lo que la pantalla aprobó.
- Ventana de confirmación: los **14 días vivos siguientes** a una adopción
  en pantalla, contra la línea de base viva declarada en el pre-registro del
  ciclo (con su n y su procedencia escritos).

### 4.3 Higiene entre arenas (el cortafuegos)

1. La variante candidata se diseña y se mide **sin ver** la confirmación en
   curso; los datos vivos posteriores a la firma del pre-registro del ciclo
   no alimentan ningún ajuste de ese ciclo.
2. **Adopción en dos llaves**: pantalla ≥ δ (selección) ∧ confirmación sin
   caída (§9) → adopción plena. Pantalla ≥ δ ∧ confirmación con caída →
   **reversión** a la configuración anterior, asentada con su motivo.
3. Lo que la confirmación mide no se reusa como pantalla: los días vivos de
   una ventana de confirmación no entran a ningún corpus de selección de
   ciclos posteriores sin declararlo como gasto de ceguera en el papel del
   ciclo (la regla del D3 del laboratorio, heredada).
4. Los resultados de pantalla se **nombran como pantalla** en todo informe
   (§11): «en la batería» no es «en su vida».

## 5. Inventario de corpus — qué existe hoy, verificado en el workspace

Inventario corrido el 17/10/2026 sobre los archivos reales. «Sirve» = puede
alimentar una batería de pantalla con verdad de terreno defendible **hoy**.

| # | Corpus | Contenido verificado | Verdad de terreno | Estado |
|---|---|---|---|---|
| 1 | **Días con plan real + veredicto + bit** | `goals/d-as-mejor-organizados/hidden_files/loop-diario.md`: planes matutinos reales del 2/10 al 16/10 (**15 días**) con cierres y veredictos (11 planificados, 2 improvisados, resto pendiente); `goals/rutina-semanal-23-27-9/loop-rutina/estado.jsonl`: **11 bits** (30/9–14/10, 10×1 y 1×0) con brazo y gasto | El día real: qué lo ató (compromiso, vencimiento, turno), registrado el mismo día en el cierre y en el log diario | **SIRVE — es la base de la batería del ciclo 1** (§7) |
| 2 | **Logs diarios** `~/memory/2026-09-23.md … 2026-10-17.md` (**25 días**) | Rutina, SUEÑO (horas/energía), CHISPA 1–5 (serie 1–12/10 asentada), gastos, hechos con etiqueta (fuente · fecha) | El registro del día, con huecos declarados: hay campos «pendiente» o «?» (noches sin respuesta); solo se usan los campos completos | **SIRVE** como fuente de contexto y de verdad de terreno del corpus 1 |
| 3 | **Scorecard «fallas que parecen éxitos»** (`your_files/fallas-que-parecen-exitos-scorecard.md`) | 1 corrida asentada (11/10): 35 éxitos declarados auditados contra archivos, **0 % de fallas**, con su regla de cadencia | Los archivos y registros reales contra los que se auditó cada afirmación | **SIRVE como semilla** para la superficie 3 (verificación antes de afirmar) cuando haya ≥3 corridas mensuales; hoy n=1 corrida: **no** es batería todavía |
| 4 | **Ledger de afirmaciones** (`alma-prototype/ledger-afirmaciones.md`, 32 líneas) | Afirmaciones hechas en informes con su etiqueta (fuente · fecha) y su estado de verificación | La fuente citada en cada fila | **SIRVE como semilla** de la misma superficie 3; n chico hoy |
| 5 | **Despegue: ledger + barridos** (`despegue-constructor/`) | 7 aplicaciones con estado y su «sí» fechado (3 enviadas, 42 roles vistos el 16/10, 1 que pasa la puerta, 2 avisos muertos el mismo día) | El desenlace de cada aplicación (enviada / muerta / descartada, con motivo) | **PARCIAL**: sirve cuando el embudo acumule ≥30 decisiones con desenlace conocido; hoy los desenlaces de respuesta están abiertos (0 respuestas al 16/10) — **no** es batería del ciclo 1 |
| 6 | **Gastos del día + conciliación** | Gasto diario en `estado.jsonl` (10 de 11 días con monto, 1 null) y en los logs; conciliación banco vs reporte practicada con recibos en los logs (p. ej. un pago asentado con dos versiones — la del aviso y la posteada — etiquetadas por separado cuando difieren) | El banco (posteado) contra lo reportado, con las dos versiones etiquetadas cuando difieren | **PARCIAL**: la práctica y los recibos existen; la extracción ítem-por-ítem banco↔reporte como corpus **no está construida** — no se inventa; superficie futura (§6.4) |
| 7 | **Digest / feed** (`~/workspace/feed`) | Pipeline y corridas del digest diario | No hay registro ítem-por-ítem de qué se seleccionó contra qué valía | **NO SIRVE hoy**: sin verdad de terreno de selección asentada; construirla es trabajo de un ciclo futuro, declarado antes |

**Regla del inventario:** ningún corpus entra a una batería sin fila en esta
tabla (o en la del pre-registro de su ciclo) con procedencia y verdad de
terreno declaradas. Dato que no se puede rastrear a su fuente, no se usa.

## 6. Primera superficie y primer ciclo

### 6.1 Superficie elegida: la estructura del plan matutino (07:30)

Criterio de elección, declarado: **el mejor corpus disponible hoy** (el #1
del §5: 15 días con plan real, contexto, veredicto y bit), el artefacto más
frecuente del sistema (un plan por día, todos los días), y una superficie
cuyo validador de pantalla puede ser **enteramente determinista** (§7.2).
Las demás superficies tienen corpus parcial o nulo hoy (§5); elegirlas
primero sería medir sobre arena.

### 6.2 La configuración vigente (v0), codificada

La línea de base se mide sobre la política vigente **tal como se aplica
hoy**, reconstruida de los 15 planes reales del corpus y del formato
instalado. Su texto — este texto ES la configuración v0 a efectos del
programa:

> **Política del plan matutino v0.** A las ~07:30, un plan de **exactamente
> 3 puntos numerados** y nada más que el plan. **Punto 1:** la acción o
> compromiso que manda el día, con su dato duro etiquetado (fuente · fecha)
> cuando lo hay. **Punto 2:** el ancla de rutina factible del día o el
> frente de trabajo en curso. **Punto 3:** la guarda del día — plata si hay
> un hecho crítico (vencimiento, disponible bajo, reserva), y si no, el
> siguiente paso del frente abierto. Tono directo, voseo, criollo. **El plan
> decide, no consulta:** no lleva preguntas; las decisiones que son de
> Alejandro se le presentan como tales, no disfrazadas de puntos del plan.

### 6.3 La variante candidata del ciclo 1 (v1): UN solo cambio

**v1 = v0 + ranuras fijas con horario obligatorio.** El único cambio: el
punto 1 debe nombrar el compromiso que manda el día **con su ventana horaria
escrita** (la hora o el rango: «a las 10:00», «17–23», «antes de las 14»),
el punto 2 es **siempre** el ancla de rutina factible (nunca un frente de
trabajo), y el punto 3 es **siempre** la guarda de plata si hay hecho
crítico, o la **condición de cierre del día** si no lo hay. Todo lo demás —
3 puntos, tono, etiquetas, «decide, no consulta» — idéntico a v0.
Hipótesis del ciclo 1, escrita antes de medir: *fijar las ranuras y obligar
el horario del compromiso principal sube la cobertura medida del plan (el
plan nombra lo que ata el día, con su hora) sin costo en invenciones.*

### 6.4 Roadmap de superficies (escalonadas; la gobernanza no)

2. **Profundidad de verificación antes de afirmar** — cuando el scorecard
   (§5.3) tenga ≥3 corridas mensuales asentadas.
3. **Criterios del barrido del Despegue** — cuando el embudo tenga ≥30
   decisiones con desenlace conocido.
4. **Diseño del chequeo nocturno** — corpus: las noches con y sin respuesta
   de los logs (la tasa de cierre del chequeo es su métrica natural).
5. **Selección del digest** — tras construir su verdad de terreno (§5.7).
6. **Política de memoria** y 7. **umbrales de proactividad** — requieren
   instrumento nuevo; su papel se escribe cuando 1–3 hayan corrido.

## 7. La batería de pantalla del ciclo 1

### 7.1 Corpus de días (congelado)

Los **15 días del corpus #1** (2026-10-02 → 2026-10-16). Por cada día, un
registro en `alma_sobre_claude/corpus_planes.jsonl` con procedencia ítem
por ítem:

- **Paquete de entrada** (lo único que la generación puede ver): el contexto
  disponible a las 07:30 de ese día — cierre del día anterior, hechos con
  fecha conocida de antemano y reglas permanentes (turnos, rutina). **Corte
  temporal estricto:** nada del propio día ni posterior entra al paquete; la
  fuga de contexto invalida el ítem y se asienta.
- **Verdad de terreno** (lo único que el validador puede ver, además del
  plan): el compromiso que ató el día (texto, palabras clave, horario si
  lo tuvo), si la plata era crítica ese día, los montos permitidos (los que
  estaban en el paquete), las anclas de rutina factibles e infactibles del
  día. Cada campo con su fuente (archivo y pasaje).

### 7.2 El validador (congelado, determinista, sin juez LLM)

Script versionado (`alma_sobre_claude/validador_plan.py`, v1, hash asentado
en el ledger al congelarlo). Puntúa cada plan generado con 7 chequeos
binarios; el puntaje del plan es **chequeos pasados / chequeos aplicables**:

| # | Chequeo | Qué verifica |
|---|---|---|
| C1 | Formato | Exactamente 3 puntos numerados, sin preguntas al usuario |
| C2 | Cobertura | El plan nombra el compromiso que ata el día (≥1 palabra clave de la verdad de terreno) |
| C3 | Horario | Si el compromiso tuvo horario, el plan lo escribe (N/A si no tuvo) |
| C4 | Ancla factible | Nombra ≥1 ancla de rutina factible del día y ninguna infactible (p. ej. fútbol un día que no es martes; gym un día declarado sin gym) |
| C5 | Sin invenciones de plata | Todo monto US$ del plan figura en el paquete (ningún número inventado) |
| C6 | Guarda de plata | Si la plata era crítica, el plan trae la guarda (reserva/disponible/no gastar); N/A si no era crítica |
| C7 | Liderazgo | El punto 1 es el compromiso que ata el día (no un frente secundario) |

### 7.3 Generación y panel

Cada variante (v0, v1) se aplica al paquete de cada día **4 veces**
(aplicaciones independientes de la política escrita, por el propio
asistente, en orden mezclado entre días y repeticiones). Panel por
variante: **15 días × 4 = 60 instancias**. Ancla de validez: los **15
planes reales históricos** se puntúan con el mismo validador y se reportan
aparte (n=15, no integran la línea de base): si la v0 generada difiriera
groseramente de la v0 vivida, la batería estaría midiendo otra cosa y el
ciclo lo declara antes de interpretar.

## 8. El δ análogo: margen mínimo que vale adoptar

Fórmula **fijada en este papel** (el número se computa de la línea de base
de la Fase 2 y queda congelado en su informe **antes** de generar v1):

- **Efecto mínimo de interés: +0,10** de puntaje (10 puntos del checklist).
  Menos que eso no cambia su día de manera que valga gobernar un cambio.
- **δ = max(0,10 ; 2 × SE_dif)**, con SE_dif = s₀ × √(2/60) y s₀ = desvío
  estándar por instancia de la línea de base v0 medida en la Fase 2.
- Dimensionado con la lección §9: con s₀ ≈ 0,20 (esperado), SE_dif ≈ 0,037
  y δ = 0,10 ≈ 2,7 SE — el panel de 60 por variante está dimensionado por
  el efecto mínimo de interés, no por costumbre. Si s₀ saliera mucho mayor,
  δ crece por la fórmula y el ciclo puede quedar sin poder adoptar: eso se
  asienta como resultado, no se «arregla» bajando δ.

## 9. Confirmación en vivo (segunda llave)

**Línea de base viva (pre-programa, con su n):** bit diario 10/11 = **0,909**
(`estado.jsonl`, 30/9–14/10); días con veredicto: **11 planificados / 13 con
veredicto = 0,846** (`loop-diario.md`, 1/10–16/10). Es la v0 vivida. Su n es
chico y queda declarado: la confirmación es un **veto contra daño**, no una
prueba fina.

Si el ciclo 1 (o cualquier ciclo) adopta en pantalla:

1. La variante pasa a ser la configuración vigente y se asienta el evento
   `adopcion_pantalla` en el ledger, con aviso a Alejandro el mismo día.
2. Corre la **ventana de confirmación: 14 días vivos nuevos** con la nueva
   configuración. Métricas: tasa de bit y tasa de días planificados de la
   ventana, contra la línea de base viva.
3. **Ratifica** si ninguna de las dos tasas cae más de **0,15** respecto de
   la línea de base viva → evento `adopcion_confirmada`. **Revierte** si
   alguna cae más de 0,15 → se vuelve a la configuración anterior, evento
   `reversion` con el motivo y los números. Sin término medio: la ventana
   no se extiende «para ver si repunta».
4. Los días de la ventana no se usan para seleccionar nada (§4.3.3).

## 10. Veredictos pre-declarados y freno

Por ciclo, el veredicto es uno de estos tres, con su nombre asentado:

| Veredicto | Condición | Qué afirma / qué no |
|---|---|---|
| **ADOPCIÓN** (en pantalla) | media(v1) − media(v0) ≥ δ, con el mismo validador y panel | La variante supera el piso en la batería; pasa a confirmación (§9). No afirma todavía nada sobre su vida |
| **SEÑAL PARCIAL** | 0 < media(v1) − media(v0) < δ | Hay dirección sin resolución: se asienta, no se adopta, no se «casi» |
| **NULO** | media(v1) − media(v0) ≤ 0 | La variante no mejora la batería; v0 sigue. El nulo se asienta y se reporta con el mismo rango que una adopción |

**Freno del programa:** tres ciclos consecutivos sin adopción →
**el programa se detiene** y espera la revisión de Alejandro (el análogo
del 3/3 del laboratorio, que funcionó). Reanudar exige su palabra, como el
token del laboratorio. Ningún ciclo mueve δ, el panel, el validador ni la
ventana después de ver resultados: hacerlo es, por definición de este
papel, salir del programa.

## 11. Límites de inferencia — escritos sin anestesia

Esto es lo que separa al programa del enamoramiento, y queda firmado antes
de medir nada:

1. **La vida no es un simulador determinista.** No hay replay ni números
   aleatorios comunes: un día no se puede correr dos veces con dos
   configuraciones. Toda comparación en vivo es entre días distintos.
2. **Los días no son intercambiables.** Día de semana, turno (17–23, finde
   6:45–14, martes sin turno), sueño previo, energía, clima y frentes
   abiertos se mezclan con cualquier efecto de la configuración. La arena
   de confirmación **no puede atribuir** con la limpieza del laboratorio;
   por eso su única función declarada es vetar daño grueso (§9).
3. **El validador de su vida es él.** El bit y el veredicto los pone
   Alejandro: subjetivos **por diseño y declarado así** — es su día el que
   se mide. Eso los hace la métrica correcta para «¿el día fue bueno?» y
   una métrica inválida para cualquier afirmación sobre terceros.
4. **Muse no es ciego.** El asistente sabe qué variante corre en vivo (la
   aplica él), y en la pantalla las instancias las genera el propio
   asistente aplicando la política escrita: la batería mide **la política
   tal como este generador la aplica**, con correlación residual entre
   repeticiones. Se declara; no se disimula con la palabra «ciego».
5. **Afirmaciones PROHIBIDAS con estos datos** (en informes, en su
   vidriera, en entrevistas):
   - «Muse mejora» sin adopción **confirmada en vivo** asentada (§9). La
     pantalla sola habilita solo: «la variante X superó el piso en la
     batería Y».
   - Cualquier número de pantalla presentado como resultado de su vida.
   - Cualquier generalización a otros usuarios, otros asistentes u otros
     modelos (§15).
   - La palabra «óptimo» para una configuración con n vivo de un dígito.

## 12. Auto-medición — «te vas a dar cuenta si mejorás»

Al cierre de **cada ciclo**, Muse produce y asienta en el ledger un
**informe de auto-evaluación** con esta estructura fija:

1. Qué se midió (superficie, variante, panel, validador y su hash).
2. El número central y su dispersión (pantalla), contra el δ congelado.
3. El veredicto con su nombre (§10) y, si hubo adopción, el estado de su
   confirmación.
4. **Qué es ruido**: qué parte del resultado no debe leerse como señal,
   dicho por el propio informe antes de que lo lea otro.
5. Estado de la serie: adopciones / nulos / reversiones acumuladas del
   programa hasta hoy.

La **acumulación de estos informes es el activo**: la primera serie medida,
con vara congelada y registro con hashes, de si un asistente mejora su
configuración trabajando — y de cuánto, y de cuántas veces no. Su cadencia
es la de los ciclos; no hay informe sin ciclo ni ciclo sin informe.

## 13. Privacidad, veto y token

- El ledger del programa y los corpus viven **locales** en el workspace.
  Contienen su vida (rutina, plata, días): **no se publican**. Hacia afuera
  solo salen agregados y método, pieza por pieza con el «sí» de Alejandro,
  como rige para todo lo suyo.
- **Veto total:** Alejandro puede frenar el programa entero en cualquier
  momento, sin motivo y sin apelación del sistema. Ningún ciclo corre con
  un veto vigente.
- Ningún cambio de configuración adoptado rige en su vida sin **evento en
  el ledger y aviso a él el mismo día**. No hay adopciones silenciosas: es
  la regla «mejora a sus espaldas solo con aviso» del 27/9/2026, heredada.

## 14. Costos, arranque y la Fase 2 de esta noche

- **Costo: US$0.** Toda excepción paga futura exige pre-registro propio con
  presupuesto y su «sí» con costo y tiempo (regla mock-first, heredada).
- **Arranque:** la revisión de este papel es de Alejandro. **Nada arranca
  en vivo el 17/10**: hoy tiene turno de trabajo y un compromiso laboral
  inamovible por la tarde. El ciclo 1 (generar v1, medir, veredicto) corre solo tras
  su revisión y su palabra.
- **Fase 2 habilitada esta misma noche** (por su precisión de las 04:01):
  construir la batería de la §7 y **correr la línea de base de v0** — la
  medición de la configuración que ya existe, sobre corpus histórico. No
  cambia ninguna configuración, no adopta nada, no toca su vida: mide el
  punto de partida, como la base del laboratorio se evaluó antes que
  cualquier candidato. Sus resultados se asientan en el ledger del programa
  y en un informe de línea de base verificado en disco. Si el corpus no
  alcanzara, la batería queda especificada y el informe declara qué falta
  — **sin inventar datos** (§5, regla del inventario).

## 15. Qué NO prueba este programa

- No prueba que **el modelo** mejora: mejora, cuando adopta, la
  **configuración** que lo rodea. El modelo es el mismo al principio y al
  final de cada ciclo.
- No generaliza a otros usuarios: el validador de la confirmación es
  Alejandro, el corpus es su mundo, la configuración es la de su asistente.
- No es un producto ni una promesa: es un instrumento de medición sobre un
  caso — el suyo. Su valor público, si lo tiene, es el **método** y la serie
  de informes (§12), no un resultado transferible.
- Una adopción en pantalla no prueba mejora en su vida hasta que la
  confirmación la ratifique (§9); una confirmación ratificada no prueba
  que la configuración sea «la mejor»: prueba que superó el piso en la
  batería y no hizo daño medible en 14 días. Nada más — y ese «nada más»
  es exactamente el punto.

---

*Firmado como pre-registro fundacional del programa «ALMA sobre Muse»,
2026-10-17, antes de construir la batería y de medir la línea de base de
la Fase 2. La gobernanza de este papel rige desde esta firma; las
configuraciones vigentes no cambian por este documento.*
