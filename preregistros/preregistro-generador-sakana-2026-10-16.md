# Pre-registro — Corrida del generador de candidatos (proponente estilo Sakana)

**Fecha:** 2026-10-16 · **Estado:** construcción AUTORIZADA y hecha
(«Armalo y dejá el pre-registro listo»); **la corrida NO está
autorizada todavía** — requiere el «corré» de Alejandro sobre este
documento. **Presupuesto: US$0** (tier gratuito; sin excepciones).

## 1. Pregunta e hipótesis

¿Un proponente que propone con criterio — leyendo el historial
medido de fracasos y moviendo varios parámetros en conjunto —
encuentra candidatos que la mutación puntual no encontró?

**H1:** al menos un candidato de la tanda logra Δ_train > 0 (la
búsqueda coordinada ve algo que la simple no vio).
**H2 (la que importa):** al menos un candidato es AUTO-ADOPTADO por
la puerta vigente, sin tocar piso, panel ni validador.

## 2. Contexto medido (no opinado)

La primera corrida contra la puerta recableada (hoy, seed 87859,
8 rondas RSO estándar, US$0) dio **SIN ADOPCIÓN**: las 8 mutaciones
puntuales revirtieron en train. La tabla exacta, desde el ledger:

| # | cambio | Δ_train (totales) |
|---|--------|-------------------|
| 1 | umbral_base: 1 → 3 | −3,0556 |
| 2 | decay: 0.5 → 0.75 | −0,5000 |
| 3 | umbral_divisor: 3 → 4 | −0,3333 |
| 4 | decay: 0.5 → 0.75 | −0,5000 |
| 5 | gate_margin: 0.0 → 0.1 | 0,0000 |
| 6 | umbral_divisor: 3 → 2 | −2,7778 |
| 7 | umbral_base: 1 → 2 | −3,1667 |
| 8 | gate_margin: 0.0 → 0.05 | 0,0000 |

El candidato final fue la propia base (Δ 0,0/0,0): la puerta nueva
nunca recibió un candidato positivo. Puerta vigente: max(Δ) >
**5,4781 totales** (≡ δ 0,2283), panel **18/12** (train [400..417],
held-out [600..611], E3 [500,501]) — recalibración de δ v3 y
recableado de hoy, commits b834e3d y ddb2859. Freno de
estancamiento: **racha plana 1/3**. Adopciones históricas del
meta-loop: **0**.

Dos precedentes que este diseño respeta: (a) EXP-JUEZ-001 midió que
el tier gratuito puede no obedecer formatos estrictos (0/30
veredictos utilizables como juez) → la validación es mecánica, el
protocolo admite feedback y la tanda insuficiente es un resultado
declarado, no un error a tapar; (b) el tier gratuito ROTA modelos
(ling-3.0 salió del tier; entró ling-3.1-flash) → la regla de
reemplazo de §4 se decide acá, no durante la corrida.


## 3. La pieza construida (esta autorización)

- **`alma_service/generador_candidatos.py`** — el proponente. Lee la
  base y el historial del ledger (solo lectura), arma el prompt,
  parsea la respuesta, valida la forma y produce la tanda. Su única
  escritura posible es el archivo de tanda que se le pasa.
- **Frontera dura:** el módulo no importa gate, metaloop, puerta_e3
  ni el validador; no puede tocar piso, panel ni regla. La suite lo
  verifica con **hashes SHA-256 antes y después de importar y
  ejecutar el módulo con mocks** (gate.py, metaloop.py, puerta_e3.py,
  scaffold.py, run_experiment47.py, exp56_rso/run_experiment56.py,
  metaloop_ledger.jsonl, metaloop_archivo.jsonl: idénticos).
- **Ruta de modelos:** la existente — `or_chat.py` de la skill
  openrouter (la misma de `juez_barato.backend_openrouter`), sin
  claves en archivos. Durante la construcción NO se hizo ninguna
  llamada viva: todas las pruebas usan backends mock.
- **Integración (opt-in, el único toque a metaloop.py):**
  `correr(..., candidatos=None)`. Con tanda, la corrida la consume
  en orden (rondas = len(tanda)) por el camino normal — keep/revert
  en train, puerta de dos splits, E3, piso de ruido, archivo de
  variantes y freno, sin cambios — y la tanda queda declarada en el
  pre-registro máquina de la corrida. Sin tanda (default), la
  corrida RSO es byte a byte la de siempre (su pre-registro no gana
  campos). Diff completo en el commit de construcción.
- **Procedimiento ejecutable:** `correr_generador.py`
  (`--generar` congela la tanda; `--tanda` la corre).
- **Verificación de la construcción:** suite nueva
  `test_generador_candidatos.py`: **57/57 checks**. Gobernanza
  completa tras el cambio: **45/45 PASS** (las 44 preexistentes
  intactas + la nueva), contra 44/44 de base.

## 4. Parámetros declarados de la corrida

- **Tanda: objetivo 14 candidatos válidos, mínimo 8 para lanzar.**
  Justificación del 14: la corrida RSO que falló usó 8 propuestas;
  14 da casi el doble de tiros coordinados sin salir del orden de
  costo medido (la corrida de 8 tardó 2,9 s; la de 14 queda en
  segundos) y el espacio (3×4×3×3×3 = 324 configuraciones) admite
  14 candidatos a distancia ≥ 2 entre sí y de la base sin apretar
  el piso de diversidad. Si el último llamado trae más válidos que
  los que faltan, la tanda los conserva todos: recortar sería
  seleccionar a mano.
- **Modelo primario: `inclusionai/ling-3.1-flash:free`** — el del
  precedente del sistema (pre-registrado en EXP-JUEZ-001 como tier
  :free de OpenRouter). **Regla de reemplazo (decidida acá):**
  (1) antes de generar, se consulta el catálogo con `or_models.py`
  (llamada sin costo) y se registra el snapshot; (2) si el primario
  no figura en el tier free, se usa el primer modelo
  `deepseek/*:free` de chat (no reasoning) del catálogo — la
  familia que `ruteo.py` declara como tier barato natural —; (3) si
  tampoco hay, el primer `*:free` de chat no-reasoning del
  catálogo, en su orden; (4) el id efectivamente usado queda
  asentado en el archivo de tanda y en el informe; (5) si no hay
  ningún modelo free de chat, la generación NO se hace — bajo este
  pre-registro no se sustituye por un modelo pago.
- **Temperatura 0.7, max_tokens 4000.** La temperatura es del
  proponente, no del validador (determinista): la reproducibilidad
  de la corrida viene de la tanda congelada a disco, no del
  muestreo. Reasoning queda fuera por la lección de EXP-JUEZ-001
  (razonan en voz alta y rompen formatos estrictos).
- **Llamados: máximo 3.** El 1º pide la tanda completa; los
  siguientes reciben los motivos de descarte y los ya aceptados, y
  piden solo los que faltan. Sin más llamados ni reparaciones a
  mano bajo este pre-registro.
- **Entradas del prompt (exactas):** la config base vigente, el
  espacio SPACES completo, la **tabla medida de propuestas del
  ledger con su Δ_train exacto** (todas las corridas registradas,
  agrupadas por corrida — incluye la tabla de §2), las reglas
  duras y el formato de salida JSON.


## 5. Validación mecánica y piso de diversidad (lo que corre antes de evaluar)

Cada candidato crudo pasa, en orden: es objeto con `config` y
`justificacion` no vacía → config completa (los 5 parámetros, sin
extras) → tipos (bool no es número; enteros aceptan float integral)
→ rango = membresía en SPACES → **no idéntico a la base** →
**mueve ≥ 2 parámetros respecto de la base** (los movimientos de 1
parámetro ya están medidos: ninguno mejoró).

**Piso de diversidad de la tanda:** ningún par de candidatos
válidos puede ser idéntico (distancia 0 → `duplicado_en_tanda`) ni
diferir en un solo parámetro (distancia 1 →
`diversidad_insuficiente`). Se aplica en orden contra los ya
aceptados, incluidos los de llamados anteriores. Todo descarte
queda registrado con su motivo (`no_es_objeto`, `sin_config`,
`sin_justificacion`, `config_incompleta`, `parametro_desconocido`,
`tipo_invalido`, `fuera_de_rango`, `identico_a_base`,
`movimiento_simple`, `duplicado_en_tanda`,
`diversidad_insuficiente`, `respuesta_no_parseable`). La validación
es de FORMA: no usa el validador congelado ni la puerta, y no mide
a nadie.

## 6. Procedimiento de la corrida (cuando se autorice)

1. **Generar y congelar:** `correr_generador.py --generar` —
   verificación de catálogo y regla de reemplazo de §4, generación
   por el protocolo de llamados, validación mecánica, y la tanda
   COMPLETA (válidos + descartados con motivo + prompts) queda
   escrita en `tanda_generador_<ts>.json` **antes** de evaluar a
   nadie.
2. **Correr una sola vez:** `correr_generador.py --tanda <archivo>`
   → `MetaLoop.correr(candidatos=[configs válidas], bloqueante=True)`.
   Semántica declarada: greedy secuencial del camino normal — cada
   candidato se mide en train contra la config vigente de la
   corrida (que incluye los keeps anteriores de la tanda); el
   candidato final pasa la puerta de dos splits contra la base
   original, el E3 ciego y el piso de ruido, como siempre.
3. **Sin segunda tanda** bajo este pre-registro: prohibido
   re-generar tras ver resultados, ajustar la temperatura, cambiar
   el modelo ni «ayudar» con selección manual. Lo que salga, queda.

## 7. Criterios (declarados antes de correr)

- **ÉXITO (H2):** ≥ 1 auto-adopción por la puerta vigente. Se
  reporta con qué cambió, el efecto medido en ambos splits y el
  E3, y el alcance exacto: adopción dentro del validador congelado
  (simulador), no capacidad en el mundo real.
- **SEÑAL PARCIAL (H1 sin H2):** ≥ 1 candidato con Δ_train > 0 que
  no llega a adoptar (revertido después, o candidato final bajo el
  piso / vetado por E3 / en banda de «sí» explícito). La búsqueda
  coordinada vio algo; la puerta manda.
- **FRACASO INFORMATIVO:** 0 candidatos con Δ_train > 0 → la base
  es un óptimo local también para esta búsqueda, y eso queda
  MEDIDO (no opinado) sobre 14 candidatos coordinados.
- **TANDA INSUFICIENTE:** tras los 3 llamados, válidos < 8 → la
  corrida **no se lanza** (el script lo frena) y el resultado se
  reporta como falla de generación del tier gratuito, no como
  corrida plana.
- **BLOQUEO DE PLATAFORMA:** 429 o caída del tier free que impida
  generar → corrida no realizada (precedente: El Probador 002b,
  «bloqueada por la plataforma, no desaprobada»). Se reporta y se
  espera; no se paga ni se improvisa otra ruta.


## 8. Contabilidad del freno de estancamiento

La corrida de la tanda ES una corrida del meta-loop a efectos del
freno (`registrar_corrida` del camino normal): **sin adopción →
la racha pasa de 1/3 a 2/3**; con adopción → vuelve a 0. Si la
corrida no se lanza (tanda insuficiente o bloqueo de plataforma),
**no hubo corrida y la racha no se mueve** — el freno cuenta
corridas evaluadas, no intentos de generación.

## 9. Destino de la tanda

La tanda completa queda asentada en tres lugares: el archivo
`tanda_generador_<ts>.json` (crudos válidos y descartados, con
motivos y prompts), el ledger del meta-loop (audit records por
candidato vía el camino normal, con sus Δ medidos) y el archivo de
variantes (el candidato final evaluado por la puerta, como
siempre). **Adoptada o no, la tanda es la población inicial para un
futuro crossover** — que ya tiene su propio pre-registro
(`metaloop_preregistro_crossover.json`, 12/10/2026) y requerirá su
propia autorización: este documento no lo habilita.

## 10. Fronteras y limitaciones declaradas

- **Intocables en esta corrida:** piso (5,4781), panel (18/12 +
  E3), validador congelado (e47/e56), regla de la puerta y del
  auto-adoptar. El generador propone; la gobernanza decide.
- La calidad del proponente está **sin medir**: que un LLM proponga
  mejor que el azar en este espacio de 324 configuraciones es la
  hipótesis de §1, no un hecho. El fracaso informativo es un
  resultado válido y publicable tal cual.
- El tier gratuito ya falló por formato una vez (EXP-JUEZ-001) y
  por 429 otra (El Probador 002b): ambos desenlaces están
  contemplados en §7 como resultados, no como sorpresas.
- La semilla de la corrida no afecta las propuestas (vienen de la
  tanda congelada); queda asentada en el pre-registro máquina como
  siempre.
- Alcance del éxito, dicho antes: una adopción acá prueba el
  MECANISMO (proponer → medir → adoptar sobre el piso de ruido)
  dentro del simulador determinista. No prueba que el scaffold
  mejore en tareas reales, y el informe de la corrida no debe
  decirlo.
