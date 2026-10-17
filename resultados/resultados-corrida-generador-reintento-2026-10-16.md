# Resultados — REINTENTO de la corrida del generador (mismo pre-registro + adenda)

**Fecha:** 2026-10-16 (segundo intento del día, ~40 minutos después
del primero). **Documentos rectores:**
`preregistro-generador-sakana-2026-10-16.md` +
`adenda-preregistro-generador-2026-10-16.md` (commit `79208b6`),
sin cambios — el reintento corre bajo el mismo papel, como el
precedente El Probador 002b (fecha nueva, mismo protocolo).
**Informe del intento anterior:**
`resultados-corrida-generador-2026-10-16.md`.
**Autorización:** Alejandro, 16/10/2026 («Hagamos los puntos 2 y
3» — el punto 3 es este reintento).

## Veredicto en una línea

**La corrida NO se realizó por segunda vez: bloqueo de
plataforma (HTTP 429 del tier gratuito sobre el modelo
designado), según §7 del pre-registro — «bloqueada por la
plataforma, no desaprobada».** El catálogo de hoy designó al
mismo modelo que en el intento anterior y la plataforma respondió
con el mismo 429 en el intento real y en las dos sondas del
protocolo. Freno de estancamiento **sin cambios: 1/3** (no hubo
corrida evaluada). Costo total: **US$0**.

---

## 1. Verificación de catálogo y modelo designado (hoy)

Catálogo OpenRouter consultado sin costo a las ~22:36 UTC
(467 modelos; snapshot y crudo en
`data_corrida_generador_reintento_2026-10-16/`). El tier gratuito
**no rotó** desde el intento anterior: los mismos 16 modelos
`:free`, en el mismo orden. Aplicada la regla de reemplazo del §4
del pre-registro, en su orden:

- Paso (1)–(2): el primario declarado
  `inclusionai/ling-3.1-flash:free` **sigue sin figurar** (solo
  existe su versión paga `inclusionai/ling-3.1-flash`).
- Paso (2): **ningún** `deepseek/*:free` en el catálogo.
- Paso (3): el primer `*:free` de chat no-reasoning del catálogo,
  en su orden, es de nuevo **`xingchen-agi/xing4.0-29b-a4b:free`**
  (índice 0, text→text; mismo criterio de clasificación asentado
  en el snapshot: «reasoning» por diseño según id/nombre/
  descripción; excluido por no-chat el guardrail
  `nemotron-3.5-content-safety`).

Ese es el modelo designado del reintento. La regla se agotó en su
paso (3) antes de generar, igual que en el intento anterior: no
hay paso siguiente que improvisar.

## 2. Generación — tres 429 consecutivos (bloqueo sostenido)

Evidencia completa en
`data_corrida_generador_reintento_2026-10-16/evidencia_429.txt`
(con `generar.log`, `sonda1.txt` y `sonda2.txt` en la misma
carpeta), con el mismo protocolo de sondas del intento anterior:

1. **Intento real de generación** (~22:37 UTC):
   `correr_generador.py --generar --modelo
   "xingchen-agi/xing4.0-29b-a4b:free"` murió en el primer
   llamado: `or_chat` salió con error y stderr vacío (reporta el
   error como JSON en stdout, la misma firma de falla del intento
   anterior). Sin tanda escrita, sin candidatos, sin evaluación.
2. **Sonda inmediata** (~22:38 UTC), prompt mínimo al mismo
   modelo: **HTTP 429 Too Many Requests**.
3. **Sonda espaciada** (+4 minutos, 22:42 UTC), prompt mínimo:
   **HTTP 429** otra vez.

**Veredicto:** §7 del pre-registro, «bloqueo de plataforma» — la
corrida **no se realizó**, por segunda vez en el día y con el
mismo modelo designado. No se sustituyó el modelo por fuera de la
regla declarada (tras el 429, cambiar de modelo sería improvisar
otra ruta: la regla ya estaba agotada en su paso 3) y no se pagó
ninguna ruta. La tanda nunca existió: no hay candidatos que
reportar, ni Δ por candidato, ni veredicto de adopción — cualquier
número ahí sería inventado.

El screening factorial de la adenda **no se repitió**: ya corrió
en el intento anterior y su veredicto (sin interacciones
detectables; único efecto detectable `umbral_base` +3,2569) quedó
asentado en `resultados-corrida-generador-2026-10-16.md` §2. El
reintento es solo de la corrida, como manda el precedente 002b.

---

## 3. Estado tras el bloqueo (verificado en disco y en la DB)

- **Freno de estancamiento: 1/3, inactivo — sin cambios**
  (`freno_estancamiento`: racha_planas 1, freno_activo 0; el
  freno cuenta corridas evaluadas y no hubo ninguna).
- **Ledger: 23 eventos, cadena de hashes recomputada e íntegra**,
  último hash `91c8e0ddc518` — idéntico al estado previo a
  ambos intentos. La generación fallida no asentó nada.
- **Scaffold vigente: sin cambios** — la base de siempre
  ({decay 0.5, gate_margin 0.0, n0 4, umbral_base 1,
  umbral_divisor 3}, `scaffold_activo` id 1).
- **Panel de confirmación: declarado y SIN consumir** —
  confirmación-train [5000..5017] y confirmación-held-out
  [5100..5111] siguen vírgenes; nadie los evaluó en ninguno de
  los dos intentos.
- **Piso, panel de puerta y validador: intocados** (5,4781
  totales; train [400..417] / held-out [600..611] / E3 [500,501];
  esta tarea no tocó `metaloop.py` ni `gate.py`).

## 4. Suites de gobernanza al cierre

- **Runner completo sobre el árbol: 46/46 PASS · 0 FAIL ·
  0 BLOCKED** (resumen en
  `data_corrida_generador_reintento_2026-10-16/test-results-reintento.json`).
  Son 46 y no las 45 del cierre anterior porque durante esta
  tarea aterrizó en el árbol la suite nueva de la tarea paralela
  (`test_gobernanza_freno_rollback.py`, el arreglo del
  freno/rollback): el runner la descubrió y también pasa.
- **Suite del generador, corrida directa: 77/77 checks en
  verde** (incluye la sección 2b del cortafuegos y la frontera
  por hashes).
- **Costo: US$0.** Duración del reintento: ~15 minutos de reloj,
  incluida la espera declarada de 4 minutos entre sondas y la
  corrida completa de suites.

## 5. Lo que queda listo

El bloqueo ya no es un evento de minutos: el mismo modelo
designado devolvió 429 en dos intentos separados por ~40
minutos, con dos sondas cada uno. Todo lo demás sigue armado
bajo el mismo papel — pre-registro + adenda vigentes, generador
con cortafuegos probado (77/77), panel de confirmación declarado
y virgen, screening asentado. Un próximo reintento no necesita
rehacer nada de este documento: verificar el catálogo de ese día
(el tier rota: si el primario vuelve o aparece un
`deepseek/*:free`, la misma regla designa otro modelo), generar,
congelar la tanda y correr. Si el tier gratuito sigue sin
responder, el desenlace se asienta igual que este: no realizada,
no desaprobada, freno quieto.
