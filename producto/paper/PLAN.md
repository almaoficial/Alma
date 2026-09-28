# ALMA — Plan del paper PÚBLICO

> **ESTADO: PLAN — NO PUBLICAR**
> Este documento es planificación interna. No es un borrador del paper, no se publica,
> no se comparte con terceros, no se cita. Existe para que decidas con información
> completa antes de que exista cualquier versión pública.
> Fecha: 2026-09-28 · Costo de elaboración: US$0 · Contacto con terceros: ninguno

---

## 1. Qué es este documento (y qué no es)

**Es:** el plan de la *versión pública y adaptada* del trabajo de ALMA — qué se puede
contar, qué no, con qué estructura, dónde conviene publicarlo y qué decisiones
necesitan tu "sí" explícito antes de mover un dedo hacia afuera.

**No es:**
- Una duplicación del informe técnico v2 (ese sigue su curso en otra tanda, con todo
  el detalle interno; este plan lo usa como fuente de números, no lo repite).
- El informe original de 11 páginas (EXP1–EXP4, interno).
- Un borrador del paper. Cuando apruebes el plan, el borrador se escribe aparte.

**La tesis editorial del paper público, en una línea:** un loop chico y embebible
(Thompson sampling + probe + skip + memoria con olvido) que aprende *qué modo usar
según el tipo de problema*, validado con experimentos pre-registrados — incluyendo
los que salieron mal — y una metodología de refutación primero que es parte del
aporte, no un adorno.

---

## 2. Qué SÍ se puede contar en público

Todo lo de esta sección es publicable sin riesgo para tu seguridad, tu privacidad
o el proyecto. Son tres capas: el diseño en alto nivel, los números, y la metodología.

### 2.1. Diseño en alto nivel (conceptos, no implementación)

- La arquitectura conceptual del loop: **Thompson sampling con prior condicionado
  a la firma del régimen + probe por bloque + skip del probe + memoria con olvido
  (0,5^días) + puerta de dos splits + auto-adopción gobernada.**
- Qué hace cada pieza *en palabras*: el probe testea qué brazo anda mejor por tipo
  de problema; el skip evita re-testear cuando el sistema ya sabe; la memoria con
  olvido pesa más lo reciente; la puerta de dos splits valida que una mejora mida
  mejor en datos no vistos antes de adoptarla.
- El detector de heterogeneidad (EXP68) como concepto: si el probe es unánime,
  se achica la exploración.
- El router por eficiencia (reward/USD, EXP69) como concepto: elegir proveedor por
  rendimiento medido por dólar, no por precio del token.
- La gobernanza como *idea de diseño*: el sistema solo se auto-mejora ante mejora
  medida, avisa cada cambio, y hay un núcleo intocable (topes de gasto, reglas de
  validación, obligación de notificar). Contar la regla, no el mecanismo interno
  que la enforcea.

### 2.2. Números publicables (todos salen de veredictos en disco)

| Experimento | Resultado publicable |
|---|---|
| EXP67 (benchmark real, deepseek-flash, 180 problemas frescos GSM8K/MMLU/MBPP) | **PASS** — loop 3,445 vs mejor política fija 10,945 vs aprendiz global 10,995. Primera evidencia fuera del mundo sintético. |
| EXP62 (réplica con deepseek-flash, mundo homogéneo) | **FAIL** — loop 4,82 vs fija −0,03. La ventaja es condicional a la heterogeneidad del mundo, no intrínseca del loop. |
| EXP68 (detector de heterogeneidad, mock) | **PASS** — +6,00 en mundo homogéneo (IC95 [+2,17,+9,83]), 0 regresión en heterogéneo. |
| EXP69 (router por reward/USD) | **PASS** — elige al ganador ex post 3/3 slices; generaliza en held-out nunca visto. |
| EXP64-skip (ablación, n=20) | **Load-bearing** — quitar el skip: +6,55 (IC95 [+2,19,+10,92]); pasa por el umbral justo (14/20). |
| EXP18 (4 seeds, API real) | **FAIL global** — 9/10 bloques correctos pero el costo del probe supera el beneficio. |
| EXP20 (errores correlacionados) | **PASS** — la ventaja de la selección sobrevive a rho=0,5 con margen idéntico. |
| EXP11b | **FAIL de diseño** — el flip no existía a resolución del probe; pregunta incontestable con esos brazos. |

También publicable: los perfiles de debilidad medidos del oráculo (p. ej., gsm8k:
cot 0,967 / single 0,633; mmlu: single 0,917; mbpp: single 0,108) y los costos
agregados por experimento (p. ej., EXP67 ~US$0,69 total), porque son parte de la
honestidad del reporte. Los FAILs entran sí o sí: son la mitad del valor del paper
y lo que lo diferencia de un publirreportaje.

### 2.3. Metodología (parte del aporte)

- **Pre-registro antes de gastar:** la vara se escribe antes de correr; los FAILs se
  aceptan sin moverla.
- **Regla mock-first:** ningún gasto en una pregunta que el simulador gratis ya
  respondió (caso EXP66: US$0,08 aprobados, US$0,00 gastados).
- **Replay con oráculo medido + RNG pareado** como estándar de comparación honesta.
- **Refutación primero:** la serie está diseñada para intentar romper la tesis
  (EXP62, EXP66, EXP20, EXP11b), no para confirmarla.

### 2.4. Contexto publicable del proyecto

- Que es investigación independiente (no afiliada a ninguna empresa ni universidad),
  iniciada en julio de 2025, con serie experimental intensiva en septiembre de 2026.
- Que el loop está implementado como servicio en operación (sin detalles: no puerto,
  no infraestructura, no dónde corre).
- La distinción entre laboratorio (evidencia) y producto (el router como pieza
  usable). Sin nombrar el producto comercial en el paper científico — ver §6,
  decisión 6.

---

## 3. Qué NO se publica (lista dura)

Nada de lo siguiente aparece en el paper, sus apéndices, su repo público (si lo
hubiera), ni en comunicaciones sobre el paper. El motivo va entre paréntesis.

1. **Keys, credenciales y cómo se gestionan** (seguridad operativa: el paper no
   explica dónde viven las keys, el vault, ni los conectores).
2. **Prompts internos** del sistema, del meta-loop, del minero o del evaluador
   (son la implementación; el paper describe *qué* decide cada pieza, no *cómo
   está instada* a decidirlo).
3. **Arquitectura de seguridad interna**: defensas contra skills maliciosas,
   provenance tracking, detalles del `NucleoProtegidoError`, allowlists del executor
   (publicar defensas en detalle es regalar el mapa del ataque).
4. **Código fuente del servicio vivo** tal cual está (puede liberarse una versión
   limpia y auditada *si* lo aprobás — ver §6, decisión 7 — nunca el repo de trabajo).
5. **Trazas de operación real, bases de datos, event logs** (contienen tu actividad).
6. **Tus datos personales y financieros**: nada de deudas, ingresos, banco, Zelle,
   alquiler, ni ninguna cifra de tu vida. El paper no sabe que existís como persona.
7. **Tu diario, tus conversaciones, tus vínculos**: nada de familia, amigos,
   roommates, fútbol, Orilla, ni el material de julio de 2025 más allá de la fecha
   de inicio del proyecto. La historia personal del proyecto no se publica.
8. **Detalles del feed personal** (las 94 noticias, categorías, el ~18% fabricado):
   si se menciona EXP44, es como "stream de noticias no estacionario", sin decir
   de dónde sale ni de quién es.
9. **La app de Mercado Libre / el conector**: nada de Client ID, estado de la
   validación de identidad, ni el respondedor como producto, salvo que lo apruebes
   explícitamente (§6, decisión 6). En el paper científico, los proveedores se
   nombran por práctica estándar del campo (ver §7, nota sobre marcas) o se
   anonimizan como Proveedor A/B/C — a tu elección.
10. **Misses operativos finos** que no aportan a la ciencia (el overshoot de 2,8% del
    freno en EXP70, el bug del `report.json`, la llamada de smoke perdida): van en
    los veredictos internos, no en el paper. La honestidad pública es sobre los
    resultados, no sobre cada tropiezo de ejecución.
11. **Dónde corre el servicio y con qué presupuesto** (infraestructura y topes
    mensuales: dato operativo sensible).
12. **El informe v2 técnico completo y el de 11 páginas**: son documentos internos.
    El paper público los reemplaza hacia afuera; si algún día se liberan, es
    decisión separada tuya.

**Regla de oro para la redacción:** si un párrafo sirve para *reproducir el sistema
tal cual* en vez de *entender la idea y los resultados*, va para adentro, no para
afuera. El paper enseña el qué y el cuánto; el cómo detallado queda en el laboratorio.

---

## 4. Estructura propuesta del paper público

Extensión objetivo: equivalente a 8–12 páginas (versión blog: 3.000–4.500 palabras;
versión arXiv: formato estándar). Registro: técnico pero llano — la versión "en
criollo" que pedís para lo técnico, con los números igual de duros. Todo en español
(salvo que apruebes versión en inglés, §6 decisión 3).

1. **Título + resumen.** Título de trabajo: *"ALMA: un loop adaptativo chico que
   aprende qué modo usar — evidencia a favor y en contra"*. El resumen promete los
   dos veredictos (PASS en heterogeneidad, FAIL en homogeneidad) en 150–200 palabras.
2. **Introducción.** El problema: elegir bien entre modos de un modelo según el tipo
   de tarea, sin pagar de más por averiguarlo. La tesis en una línea (ver §1). Mapa
   del paper.
3. **Trabajo relacionado.** Bandits contextuales, Thompson sampling, meta-learning,
   agentes auto-mejorados (posición honesta: el loop no inventa los componentes; la
   novedad es la combinación embebible + la disciplina de validación). Acá entra el
   estudio de self-improving agents como respaldo, sin sus detalles internos.
4. **Método (alto nivel).** Las seis piezas en palabras (§2.1), con un diagrama
   conceptual. Nada de código, nada de prompts.
5. **Diseño experimental.** Pre-registro, mock-first, oráculo medido + replay con
   RNG pareado, puerta de dos splits, criterio de vara. Esta sección es parte del
   aporte: otros pueden copiar la disciplina sin copiar el sistema.
6. **Resultados.** Una subsección por experimento clave (EXP67, EXP62, EXP68, EXP69,
   EXP64-skip, EXP18, EXP20, EXP11b), cada una con: pregunta, vara pre-registrada,
   números, veredicto, una línea de lectura honesta. Los FAILs con el mismo peso
   visual que los PASS.
7. **Discusión: lo que la serie refutó.** El techo de EXP62 (la ventaja es
   condicional al mundo), el costo del probe (EXP18/EXP44: explorar es caro cuando
   la ventaja entre brazos es chica), la pregunta abierta de los mundos
   heterogéneos para modelos fuertes. Sin anestesia: si el paper no deja incómodo
   al autor en al menos un párrafo, está endulzado.
8. **Gobernanza de la auto-mejora.** La regla "mejora a mis espaldas y avísame, pero
   no peor": solo se adopta ante mejora medida, todo cambio se notifica, el núcleo
   (topes, validación, notificación) es intocable. Planteado como propuesta de
   diseño para sistemas que se modifican solos, no como producto terminado.
9. **Trabajo futuro.** Las refutaciones pendientes (§16 del informe v2): mundos
   heterogéneos para modelos fuertes, E3 con datos frescos, validación del detector
   en trazas reales.
10. **Reproducibilidad y límites.** Qué datos son públicos (benchmarks estándar),
    qué código se libera (solo si lo aprobás), y la declaración explícita de lo que
    el paper *no* afirma (no es SOTA general, no es evidencia de producción).

**Lo que NO lleva el paper público:** apéndices con código, prompts, logs de
ejecución, ni el detalle de la infraestructura. Si un revisor los pide, la respuesta
es "están en el informe técnico interno, no publicado", no improvisar una
liberación.

---

## 5. Plan de publicación: opciones con pros y contras

Ninguna opción se ejecuta sin tu "sí" (§6). El orden sugerido es secuencial:
primero lo rápido y en tu idioma, después lo académico si te interesa.

### Opción A — Blog propio / Substack personal (recomendada como primera salida)

- **Pros:** sale en días; control total del texto y del momento; en español, tu
  idioma y tu audiencia; marca prioridad pública con fecha; costo US$0.
- **Contras:** cero validación externa; peso académico nulo; alcance limitado a tu
  red y a quien lo encuentre; no es citable en el sentido formal.
- **Timing:** 1–2 semanas después de aprobado el plan (una semana de redacción del
  borrador + tu revisión).

### Opción B — arXiv (cs.AI o cs.LG)

- **Pros:** timestamp de prioridad reconocido; citable (DOI vía arXiv); alcance
  global en ML; gratis; no requiere peer review para salir.
- **Contras:** necesitás *endorsement* (primera publicación en la categoría: alguien
  con historial te avala — hay que conseguirlo, no es automático); la audiencia
  espera inglés (se puede publicar en español pero el alcance cae fuerte);
  exposición a crítica pública sin filtro; formato LaTeX y sus tiempos.
- **Timing:** +2–4 semanas tras el borrador (endorsement + formato + eventual
  versión en inglés).
- **Prerrequisito:** decidir idioma (§6.3) y firma (§6.2) antes de subir nada.

### Opción C — Workshop de conferencia (NeurIPS / ICML workshops, ej. agentes adaptativos)

- **Pros:** feedback de pares de verdad; prestigio si aceptan; networking.
- **Contras:** meses de espera (deadlines semestrales); casi obligado en inglés;
  aceptación competitiva (un paper honesto con FAILs puede gustar o puede caer por
  "resultados negativos"); formato académico completo con related work pesado.
- **Timing:** 3–6 meses mínimo. Solo tiene sentido si la vía arXiv previa validó
  que el trabajo interesa.

### Opción D — Medium / HackerNoon / prensa tech en español

- **Pros:** rápido, audiencia general.
- **Contras:** peso nulo en la comunidad técnica; riesgo de titular sensacionalista
  ("el argentino que creó la IA que se mejora sola") que después hay que desmentir;
  poco control sobre cómo se recorta.
- **Veredicto del plan:** no como vía primaria. Como amplificación del blog, quizás.

### Amplificación (después de la vía primaria, si querés)

Hacker News, r/MachineLearning, hilo en X: sirven para feedback y alcance, no como
publicación. Se hacen *después* de que el texto canónico exista en tu blog o arXiv,
nunca antes (si el debate arranca sobre un hilo, perdés el control de la versión
canónica).

### Secuencia propuesta

1. Aprobás este plan (con tus decisiones del §6).
2. Se redacta el borrador (blog, español) — ~1 semana.
3. Lo revisás vos, línea por línea contra la lista dura del §3.
4. Se publica en tu blog. Recién ahí existe algo público.
5. Si te interesa la vía académica: versión en inglés → arXiv (con endorsement).
6. Workshop solo si el paso 5 muestra tracción.

---

## 6. Decisiones que necesitan tu "sí" explícito

Nada de esta lista se asume. Cada punto espera tu decisión antes de avanzar al
siguiente paso del plan:

1. **¿Se publica?** Que exista un paper público es irreversible: una vez afuera,
   no se retira de internet. El "no publicar" también es una decisión válida y el
   plan muere acá sin costo.
2. **Firma.** ¿Nombre real, seudónimo o anónimo? (Anónimo en arXiv es raro y le
   quita fuerza a la prioridad; seudónimo en blog es viable.)
3. **Idioma.** ¿Solo español, o español + versión en inglés para arXiv? La versión
   en inglés duplica el trabajo de redacción y revisión.
4. **Dónde.** ¿Solo blog, o la secuencia blog → arXiv? ¿Algún workshop en el radar?
5. **Alcance de resultados.** ¿Entran todos los experimentos del §2.2, incluidos
   los FAILs? (El plan recomienda que sí: sin los FAILs el paper pierde su
   diferencial honesto. Pero es tu decisión.)
6. **Mención comercial.** ¿El paper nombra a Mercado Libre / el respondedor como
   aplicación, o la capa producto queda 100% afuera del paper científico?
   (Recomendación del plan: afuera. El paper vende ciencia; el producto se anuncia
   por su propio canal cuando exista.)
7. **Código y datos.** ¿Se libera algún código? ¿Con qué licencia (MIT/Apache-2.0)?
   Si la respuesta es sí, hay que producir una versión limpia y auditada del repo
   — el repo de trabajo actual NO se publica bajo ningún concepto (puede contener
   restos de keys, paths y datos tuyos).
8. **Nombrar proveedores.** En el paper, ¿los modelos se nombran (práctica estándar
   en ML) o se anonimizan como Proveedor A/B/C?
9. **Timing.** ¿Hay alguna fecha que te importe (antes/después de algún hito del
   producto o del laboratorio)? Sin fecha tuya, el plan propone "cuando el borrador
   esté revisado, sin apuro".

---

## 7. Prerrequisitos antes de redactar el borrador

1. **Informe v2 técnico cerrado** (corre en otra tanda): el paper público cita sus
   números; no se redacta sobre serie abierta.
2. **Tus 9 decisiones del §6**, al menos las 1–5.
3. **Chequeo de marcas:** si se nombran proveedores o benchmarks, uso nominativo
   estándar del campo (como cualquier paper que evalúa GPT/Claude/DeepSeek). Si se
   nombra a Mercado Libre como aplicación, revisión aparte: es anuncio comercial,
   no cita académica.
4. **Auditoría del material fuente del borrador:** quien redacte trabaja solo con
   los veredictos en disco y este plan, nunca con el repo de trabajo ni con
   memoria personal. Checklist contra el §3 antes de que veas el borrador.
5. **Definir el canal del blog** (dominio propio, Substack, otro) si la vía A es la
   elegida — crear la cuenta no publica nada por sí misma.

---

## 8. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Alguien publica algo parecido antes | La secuencia blog → arXiv con fecha marca prioridad; no apurar por pánico igual la preserva. |
| Crítica dura a los FAILs ("no funciona") | Los FAILs están enmarcados como refutaciones diseñadas, con vara intacta — la honestidad es la defensa, no el punto débil. |
| Filtración accidental de un dato de la lista dura | Checklist del §3 aplicado al borrador por dos pasadas (redacción + tu revisión). Ningún apuro justifica saltearla. |
| El paper genera expectativas sobre el producto que aún no existe | Separación explícita: el paper no nombra el producto (§6.6); el paper no promete fechas. |
| Titulares sensacionalistas (vía D) | No usar la vía D como primaria; si se amplifica, con el texto canónico ya publicado como referencia. |
| Arrepentimiento post-publicación | Por eso la decisión 1 es explícita y previa a todo lo demás. |

---

## 9. Estimación honesta de esfuerzo (US$0)

- Redacción del borrador (blog, español): ~1 semana de trabajo por tandas.
- Tu revisión: 1–2 sesiones (la lista dura del §3 es tu checklist).
- Versión arXiv en inglés (si la aprobás): +1–2 semanas (traducción técnica +
  formato LaTeX + endorsement).
- Auditoría de repo limpio para liberar código (si la aprobás): trabajo separado,
  se presupuesta cuando toque — no está incluido en este plan.

Ningún paso gasta key, contacta terceros ni toca el servicio vivo. Todo el plan es
documento.

---

*Fin del plan. Siguiente paso: tus decisiones del §6 — con la 1 ("¿se publica?")
primero, porque todo lo demás cuelga de ella.*
