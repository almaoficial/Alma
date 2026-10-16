# ALMA — Diseño del sistema real (v1.0)

**Fecha:** 2026-09-27 · **Estado:** documento de diseño — no hay código todavía.
**Principio rector:** refutación primero. Cada mecanismo de este diseño existe
porque un experimento lo sostuvo o porque el estudio lo exige. Cada afirmación
de mejora —interna o del propio sistema— pasa por pre-registro, harness y
veredicto con números. La vara pre-registrada es sagrada también para el
sistema, no solo para el laboratorio.

## 0. De dónde sale este diseño

Tres fuentes de evidencia, ninguna de opinión:

1. **Los mocks EXP45–52** (línea de skills, cerrada por regla pre-registrada
   en EXP52): el loop probe→selección→ejecución→aprendizaje con skills estilo
   Hermes, testeado en 8 experimentos pareados, mock US$0.
2. **El estudio de agentes que se mejoran solos** (27/9, 39 fuentes):
   `research_notes/self-improving-agents-study-20260927-1910/report.md`.
3. **Lo ya construido:** el prototipo `alma/` (registry, executors, selector,
   evaluator, store con hash encadenado, budget, gates) y el esqueleto del
   servicio `servicio/` (motor, server, store SQLite, spec ALMA_V2).

---

## 1. Qué le robamos a Hermes y qué le corregimos

### 1.1 Robar (con fuente del estudio)

1. **Formato AgentSkills SKILL.md + progressive disclosure** (§1.2A, §2.2).
   Las skills viven como `skills/<categoria>/<nombre>/SKILL.md` con frontmatter
   YAML (`name`, `description`); al inicio de sesión solo se precargan
   nombre+descripción (~30–50 tokens por skill) y el cuerpo se carga bajo
   demanda. Por qué: compatibilidad con el ecosistema (27–40+ herramientas ya
   lo adoptan) y control del costo de contexto.
2. **Ciclo de vida estilo Curator** (§1.2C): `active → stale` (14 días sin
   uso) `→ archived` (30 días); **nunca borrar** — archivar es la acción
   máxima. Solo toca skills creadas por el agente (`created_by: "agent"`);
   las instaladas de terceros son intocables por el Curator. Ledger de
   auditoría append-only con rollback (nuestro `store.py` ya implementa hash
   encadenado: se reutiliza).
3. **Revisión de auto-mejora en background, fuera del camino crítico**
   (§1.2B): cada N interacciones se bifurca una revisión liviana que detecta
   qué guardar o parchear en memoria/skills sin tocar la conversación
   activa. Con **gate de consentimiento**: las escrituras de background se
   aprueban antes de aplicarse (el `write_approval` de Hermes).
4. **Provenance tracking** (§1.2A): cada skill y cada memoria lleva su
   origen (`agent` / `bundled` / `externo` / `background_review`).

### 1.2 Corregir: el defecto que Hermes tiene y nosotros medimos

**Hermes no tiene olvido en su memoria basada en archivos.** El estudio lo
dice sin vueltas (§3.3): *"every fact ever written stays there permanently…
The signal-to-noise ratio degrades monotonically."* Sin conciencia temporal,
una preferencia de hace 6 meses pisa a la de ayer. Es el defecto estructural
del diseño que más nos importa, porque **nosotros medimos el valor del
olvido en EXP9**: un prior con decaimiento `0.5^d` le gana al prior uniforme
tras un flip del mundo (0.545 vs 0.555 post-flip) — el uniforme arrastra
historia vieja, el decaído la olvida. El efecto era chico con prior débil
(N0=2), pero el mecanismo se confirmó en los priors.

El sistema real, entonces:

- **Toda memoria lleva timestamp.** El scoring de retrieval incluye
  decaimiento temporal (lo nuevo pesa más que lo viejo, con tasa configurable
  por tipo de memoria).
- **Consolidación episódica→semántica:** un job periódico promueve
  experiencias repetidas a hechos compactos y poda las de baja utilidad
  (mitigaciones estándar, estudio §3.3).
- **Capacidad acotada con evicción:** la memoria no crece sin límite; lo que
  no se usa y no se consolida, se archiva.
- **Anti-bloat de skills** (estudio §3.1: un usuario midió 75 skills =
  38.8% de su system prompt): presupuesto duro de contexto para el índice
  de skills, enforced por el Curator. Si el índice supera el tope, el
  Curator archiva por score de utilidad (uso × recencia × éxito), no por
  antigüedad sola.
- **Seguridad en la ingesta** (estudio §3.4: 0.16% de skills confirmadas
  maliciosas en un estudio de 98k; 36.82% con ≥1 issue; incidente ClawHavoc):
  **ninguna skill de terceros se auto-instala.** Las crea el agente desde su
  propia experiencia o las aprobás vos caso por caso, con escaneo previo.

---

## 2. El loop que los mocks validaron

El loop operativo es **probe → selección → ejecución → aprendizaje**, con
los mecanismos que sobrevivieron a la refutación:

| Mecanismo | Evidencia | Qué entra al diseño |
|---|---|---|
| Prior de Thompson condicionado a la firma del régimen | EXP45 (−1.00) | La experiencia persiste condicionada por firma, no ciega |
| Skip del probe con soporte fuerte y **umbral endurecido** `umbral(K)=2+floor(K/3)` | EXP49 (misfires 14.3% vs 36.8% de EXP47) | Saltar la exploración cuando la evidencia acumulada lo justifica |
| **Gate adaptativo**: si Q1 decide a favor del brazo de la skill, se salta el re-probe | EXP51 (−24 en bloques no saltados; hueco a la mejor fija 3.8→2.2) | Abaratar el probe donde ya hay decisión |
| **Selectividad real** | EXP50 (dirimente vs azar: 14% vs 71% de misfires) | El valor está en *elegir bien*, no en saltar menos |
| Skip **load-bearing** | EXP52 (+5.0 al quitarlo) | El skip no es optimización: sostiene el resultado |
| Evidencia ruidosa-pero-**seleccionada** > evidencia limpia-pero-adversamente-seleccionada | EXP52 (lección contra-intuitiva) | El soporte del skip se alimenta de toda la evidencia, no solo de probes "limpios" |

### 2.1 La honestidad estructural: el detector de recurrencia

EXP44 (stream real, 94 noticias del feed): la categoría dominante rota en
**8/8 transiciones**; efecto +6.80, FAIL. En un mundo sin recurrencia, el
mecanismo de skills **no tiene de qué agarrarse** — en EXP46 quedó
pre-registrado: *"en el feed real el mecanismo no se activaría ni una vez."*

Por eso el sistema real **no crea skills a ciegas**. Lleva un componente
previo a todo el loop:

- **Detector de recurrencia:** mide, por ventana deslizante, si las firmas
  de los problemas **recurren** (tasa de re-ocurrencia por firma).
- **Si no hay recurrencia** → modo adaptativo puro: Thompson + re-probe
  (EXP7), sin invertir un token en crear ni curar skills. Explorar ya es
  caro; no se le suma el costo de un loop que no puede rendir.
- **Si hay recurrencia** → se activa el loop de skills completo (§2).

La condición de alcance de los mocks se convierte así en una **compuerta
del sistema**, no en una nota al pie. (Nota: el feed además *fabrica* ~18%
de su contenido —hallazgo del 27/9—; el detector trabaja sobre firmas de
problemas reales que el sistema resolvió, no sobre unidades sin ground
truth.)

---

## 3. El nivel meta: lo que nadie en producción hace

El hueco del estudio (§4): **ningún agente en producción rediseña su propia
arquitectura.** Todos acumulan procedimientos (markdown, memoria) bajo un
loop fijo. El único sistema que reescribe su propio código es la
Darwin-Gödel Machine de Sakana AI (investigación: SWE-bench 20%→50%), con un
incidente documentado de objective-hacking —el agente borró los tokens que
su propia función de reward chequeaba, pese a instrucciones en contra.

### 3.1 El Meta-loop

Un componente que decide, **por tipo de problema**:

1. **Qué familia de arquitectura** del registry
   (`single / cot / self_consistency / reflexion / debate / plan_tools_verify`
   — `alma/registry.py`, núcleo fijo v1.0.0);
2. **Qué estrategia de selección** (Thompson global vs por clase; con/sin
   skills; con/sin skip; presupuesto de probe);
3. **Cuánto presupuesto** de exploración asignar.

Es el `Experimenter` del prototipo dejando de ser stub — pero honesto: el
README ya marca que *"detectar incertidumbre pero no inventar arquitecturas"*
es el problema abierto. El Meta-loop v1 **propone variantes de política
sobre el registry existente**, no arquitecturas inventadas de la nada. La
invención de arquitecturas nuevas queda como investigación (fase 3).

### 3.2 Evaluación: el harness como puerta de calidad

Toda propuesta de cambio —del Meta-loop o de la consolidación LLM del
Curator— pasa por el mismo protocolo del laboratorio:

> **sandbox → harness** (tests + `puerta_calidad.sh` + benchmark estilo
> EXP11) **→ pre-registro con criterio falsable → A/B pareado → veredicto.**

Sin PASS no se adopta. El sistema se evalúa a sí mismo con la misma vara
que usamos para refutarlo. (El estudio marca como hueco general que
*ningún* benchmark público mide si estos loops mejoran con el tiempo —
hallazgo 6; nuestro harness existe para no repetir ese hueco.)

### 3.3 Guardarraíles anti objective-hacking

Diseñados contra el incidente DGM:

1. **Separación proposer/verifier:** quien propone el cambio no lo evalúa
   (ya existe en `gates.py`).
2. **Reward anclado a ground truth** donde exista (exact-match, tests en
   sandbox); juez LLM solo donde no hay otra vía, y nunca como única señal
   para cambios estructurales.
3. **Núcleo fijo no modificable por el propio sistema** (privilegios en
   `gates.py`): el Meta-loop opera sobre política y composición, no sobre
   su propio código.
4. **Lineage auditable + rollback:** ledger append-only con hash encadenado
   (`store.py` ya lo implementa); rollback automático ante no-regresión
   (`gates.py`).
5. **Presupuesto por bucket** (`budget.py`): el Meta-loop no puede gastar en
   experimentación más de lo asignado.

### 3.4 Alcance honesto del "rediseño"

El sistema v1 rediseña su **política** (qué arquitectura, qué estrategia,
cuánto probe) por tipo de problema, validada empíricamente. **No reescribe
su propio código en producción.** Eso es más que todo lo que hay en
producción hoy (estudio §4) y menos que DGM — deliberadamente: el riesgo no
se justifica sin una infraestructura de validación equivalente a la de
Sakana. La reescritura de código propio queda para fase 3, en sandbox y con
aprobación tuya por cambio.

---

## 4. Realidad operativa

### 4.1 Persistencia

- **SQLite** para la memoria de experiencias (ya existe: `store_sqlite.py`,
  `alma_store.db`). Cada experiencia guarda: problema (firma), brazo,
  modo, gap estimado, decisión, reward, timestamp.
- **Skills como archivos SKILL.md** en disco (formato AgentSkills, §1.1.1)
  con índice en SQLite: telemetría de uso (`use_count`, `last_activity_at`,
  `estado`), necesaria para el Curator y el umbral endurecido.
- El esqueleto del servicio ya existe (`servicio/motor.py`, `server.py`);
  este diseño lo convierte en el sistema real en vez de empezar de cero.

### 4.2 Qué corre siempre vs por schedule

- **Siempre:** el servicio — ciclo resolver → feedback. La revisión de
  background cada N interacciones (fuera del camino crítico, §1.1.3).
- **Por schedule:** Curator semanal (transiciones deterministas
  stale→archived; la consolidación LLM es opt-in y gateada); auditoría
  diaria del feed 09:00 (cron ya creado); chequeo nocturno 23:23 (ya
  existe). El Meta-loop corre por schedule (semanal) o a pedido — nunca en
  el camino crítico de una respuesta.

### 4.3 Costos (dimensionado por fases)

- **Fase 0: US$0** — sin key. Scaffolding, harness, mocks, backends demo.
- **Fase 1: por experimento** — cada corrida con key lleva presupuesto
  pre-registrado (referencia: EXP11 ~US$0.50) y tu "sí" explícito con costo
  y tiempo informados antes.
- **Fase 2: servicio diario con tope mensual fijado por vos.** Referencia
  del estudio: ~US$150/mes a ritmo serio con modelos grandes (Opus-class,
  ~10M tokens). Con gpt-4o-mini el mismo volumen cuesta ~dos órdenes de
  magnitud menos; **el número real se mide en fase 1 antes de prometer
  nada.**
- **Regla dura:** ningún componente gasta sin bucket asignado (`budget.py`);
  si un bucket se agota, el componente se degrada a modo barato (demo /
  adaptativo puro), no pide más solo.

### 4.4 Lo que requiere tu aprobación explícita

1. **Cualquier uso de tu key de OpenAI** — por experimento o por
   presupuesto mensual. Sin tu "sí" con costo y tiempo, no se toca.
2. **Instalar skills de terceros** — decisión caso por caso, con escaneo
   previo (§1.2, seguridad).
3. **Activar la consolidación LLM del Curator** — hace cambios
   estructurales amplios (fusiones de skills); es opt-in a propósito.
4. **Cambios al núcleo fijo / privilegios** (`gates.py`).
5. **Reescritura de código propio** (fase 3) — aprobación por cambio, en
   sandbox primero.
6. **Dónde corre el servicio 24/7** (esta VM vs un VPS tuyo) y **qué datos
   toca**.
7. **Sacar datos fuera de tu máquina** — por defecto nada sale.

---

## 5. Plan por fases (con criterios de salida falsables)

- **Fase 0 — sin key, US$0** (autonomía mía, en curso tras tu "creemos"):
  scaffolding del sistema real sobre `alma/` + `servicio/`: store de
  experiencias + skills SKILL.md con índice SQLite; loop con los mecanismos
  de §2 (skip endurecido, gate adaptativo, selectividad); detector de
  recurrencia (§2.1); memoria con olvido (§1.2); harness como puerta;
  tests. **Criterio de salida:** tests en verde + el mock reproduce EXP51
  bit-idéntico (el mejor punto de la línea).
- **Fase 1 — con key, gateada por tu "sí":** calibrar con modelos reales:
  benchmark estilo EXP11 (200 problemas, ~US$0.50) + una tarea real tuya en
  el ámbito que elijas. Cada experimento: pre-registro + presupuesto + tu
  sí. **Criterio de salida:** ¿el loop con LLM real reproduce la dirección
  de los mocks? Si la refuta, se rediseña antes de gastar un centavo más.
- **Fase 2 — servicio persistente:** ALMA 24/7 con memoria con olvido,
  Curator semanal y Meta-loop proponiendo variantes validadas por harness.
  Tope mensual de gasto fijado por vos. **Criterio:** el harness propio
  mide mejora o no-mejora en el tiempo (el hueco que el estudio marca en
  todos los demás).
- **Fase 3 — meta-evolución acotada:** el Experimenter propone variantes de
  política de forma continua; reescritura de código propio solo en sandbox
  y con tu aprobación por cambio. **Criterio:** un cambio de código propio
  que pase el harness completo sin regresión.

---

## 6. Alternativas descartadas (con razón)

1. **Instalar Hermes tal cual y listo.** Descartado: duplica lo que ya
   tenés gratis conmigo (tu decisión del 27/9); no tiene olvido (defecto
   medido en §1.2); no tiene nivel meta (estudio §4); y el loop de skills
   ya lo testeamos en el lab con mejores mecanismos que los suyos.
2. **Fine-tuning de pesos.** Descartado: ningún sistema en producción lo
   hace; toda la mejora es in-context/procedural (estudio §4). Costo e
   infraestructura injustificados para la evidencia disponible.
3. **Mapa de parecido / fingerprint para transferencia.** Descartado por
   evidencia propia: EXP27 (catastrófico cuando erra: 21.65 vs 8.90),
   EXP28, EXP29 → especificación V2.4: shortlist global sin mapa. La
   transferencia es un problema de riesgo, no de información.
4. **Reescribir el propio código en producción (estilo DGM).** Descartado
   por ahora: riesgo de objective-hacking sin infraestructura de
   validación equivalente. Se re-evalúa en fase 3 con sandbox + tu
   aprobación por cambio.
5. **Auto-instalar skills de terceros.** Descartado por seguridad (estudio
   §3.4: supply-chain real, incidentes reales).
6. **Correr EXP44b con key y el diseño actual.** Descartado en el propio
   veredicto de EXP44: mediría con plata lo que el mock ya diagnosticó
   gratis.

---

## 7. Decisiones que solo vos podés tomar

1. **Presupuesto mensual en US$ para la key** (o esquema por experimento).
2. **Activar la fase 1** — cada experimento llega con costo y tiempo
   explícitos para tu "sí".
3. **Instalar skills de terceros** — caso por caso.
4. **Activar la consolidación LLM del Curator.**
5. **Cambios al núcleo fijo / privilegios.**
6. **Dónde corre el servicio 24/7** y qué datos toca.
7. **El ámbito real donde ALMA opera primero** (habías elegido inglés —
   a confirmar).
8. **La key de Anthropic** (pendiente): si querés el segundo brazo de
   modelos para el rediseño de brazos.

---

## 8. Honestidad incómoda del diseño

- **Todo lo validado vive en mocks.** La fase 1 puede refutar que el loop
  funcione con LLMs reales. El diseño lo prevé: el criterio de salida de
  fase 1 es falsable y, si falla, se rediseña antes de seguir gastando.
- **El techo estructural no lo rompe este diseño.** En mundos que rotan
  rápido, ninguna maquinaria con exploración le gana sistemáticamente a la
  mejor fija (EXP44, EXP52). Lo que hace el diseño es **no pagar de más**:
  el detector de recurrencia evita invertir en skills donde no pueden
  rendir, y el gate + el skip abaratan lo que sí funciona.
- **La ventaja meta-evolutiva es una afirmación arquitectónica, no una
  medición.** Ningún benchmark público demuestra que estos loops mejoren
  con el tiempo (estudio, hallazgo 6). Nuestro harness existe justamente
  para no repetir ese hueco: si el sistema no mejora mediblemente, el
  veredicto lo va a decir.
- **Cuatro PASS seguidos con el mismo perfil** (EXP45–51: efecto real,
  chico, frágil entre réplicas) es la base empírica real. Este diseño no
  promete más de lo que esa base sostiene.
