# Resultados — La forma buscada: completación de la regla y generación ejecutada

**Fecha:** 2026-10-16 (tercer movimiento del día sobre esta
corrida). **Documentos rectores:**
`preregistro-generador-sakana-2026-10-16.md` +
`adenda-preregistro-generador-2026-10-16.md` (commit `79208b6`) +
`adenda2-preregistro-generador-2026-10-16.md` (commit `16f81c0`,
escrita y commiteada ANTES de generar, como la adenda manda).
**Informes previos:** `resultados-corrida-generador-2026-10-16.md`
y `resultados-corrida-generador-reintento-2026-10-16.md` (ambos:
NO REALIZADA por bloqueo de plataforma).
**Autorización:** Alejandro, 16/10/2026 («busquemos la forma»).

## Veredicto en una línea

**La forma funcionó para salir del bloqueo y la generación SE
EJECUTÓ — pero la tanda salió INSUFICIENTE y la corrida NO se
lanzó:** el modelo designado por completación de la regla
(`nvidia/nemotron-3.5-super-vl:free`) respondió a la sonda y a
los 3 llamados de generación, y las 3 respuestas fueron
**no parseables** (0 objetos JSON utilizables): válidos
**0/14**, bajo el mínimo declarado de 8. Es el desenlace «tanda
insuficiente» del §7 del pre-registro — **falla de generación
del tier gratuito, no bloqueo de plataforma y no corrida**.
Freno de estancamiento **sin cambios: 1/3** (§8: no hubo corrida
evaluada). Costo total: **US$0**.

---

## 1. La completación de la regla (adenda 2, previa a todo)

La regla de reemplazo del §4 se agotaba en su paso (3) con un
modelo sostenidamente bloqueado (429 en dos intentos, ~40 min
aparte, con sondas en ambos). La adenda 2 — escrita y commiteada
antes de generar (commit `16f81c0`) — agregó el **paso (6),
descenso por la tabla gratuita**: ante bloqueo sostenido del
designado, la designación desciende por los `*:free` de chat
no-reasoning **en orden del catálogo** (mismo criterio de
clasificación asentado en los snapshots previos), con una sonda
diagnóstica mínima por candidato; el primero que responde,
genera. Máximo 6 sondas; si ninguno responde, se frena sin pagar
ni sustituir por fuera. Todo lo demás del protocolo quedó sin
cambios (3 llamados, temperatura 0,7, cortafuegos, tanda 14/8,
puerta 5,4781, panel de confirmación, §8 del freno).

Declaración de procedencia de la tabla: el descenso se hizo
sobre el snapshot del catálogo consultado sin costo hoy a las
~22:47 UTC (467 modelos, los mismos 16 `:free` en el mismo
orden que en ambos intentos previos; snapshot en la carpeta de
evidencia). No se encontró en disco ninguna otra tabla de
ranking de modelos gratuitos; la ordenación usada es la del
catálogo, que es la que la propia regla del §4 usa en su paso
(3).

## 2. Sondas diagnósticas (evidencia: `data_corrida_generador_forma_2026-10-16/sondas.jsonl`)

| # | modelo | hora UTC | resultado |
|---|--------|----------|-----------|
| 1 | `nvidia/nemotron-3.5-super-vl:free` | 2026-10-16T22:48:45Z | **responde** (HTTP 200, texto devuelto en <1 s) |

Una sola sonda bastó: el descenso se detuvo en el primer
candidato, como la completación declara, y ese modelo quedó
designado. Su ficha (catálogo de hoy): multimodal MoE de NVIDIA
(texto+imagen+video → texto, 12B activos de 120B); la
descripción **no** lo presenta como modelo de razonamiento (no
clasifica «reasoning» bajo el criterio asentado) y soporta
`structured_outputs`/`response_format` — la ruta declarada
(`or_chat.py`) no los solicita, y usarlos sería un cambio de
procedimiento con su propio papel (no se hizo).

## 3. Generación — ejecutada; tanda insuficiente

Invocación declarada en la adenda 2:
`correr_generador.py --generar --modelo "nvidia/nemotron-3.5-super-vl:free"`
(~88 s de reloj). Resultado: **3 llamados, 3 descartes, 0
válidos**. Los 3 descartes con el mismo motivo:
`respuesta_no_parseable` («sin objeto JSON parseable»). La
tanda completa (los 3 prompts enviados + los descartes con
motivo) quedó congelada en `tanda_generador_1792191039.json`
antes de evaluar a nadie, como manda el §6.

**Por qué no se lanzó:** §7 del pre-registro — con válidos < 8
tras los 3 llamados, la corrida no se lanza; el script lo frenó
solo («OJO: bajo el mínimo declarado»). No es un bloqueo de
plataforma (el modelo respondió las 4 veces que se lo llamó
hoy) ni una corrida plana (nadie fue evaluado: no hay Δ por
candidato que reportar, y cualquier número ahí sería inventado).

**Por qué no se descendió más hoy:** la completación de la
adenda 2 declara el descenso ante *no-respuesta* (bloqueo). Este
modelo respondió; lo que falló fue el formato. Cambiar de
modelo después de ver ese resultado es exactamente lo que el
§6.3 del pre-registro prohíbe bajo este papel («prohibido
re-generar tras ver resultados, cambiar el modelo»), y ninguna
adenda escrita hoy lo habilita. El antecedente es el conocido:
EXP-JUEZ-001 ya midió que el tier gratuito puede no obedecer
formatos estrictos (0/30 veredictos utilizables como juez); hoy
el mismo modo de falla apareció en generación (0/3 respuestas
parseables).

**Lo que no se puede afirmar:** el texto crudo de las
respuestas no queda retenido por el módulo generador (la tanda
guarda prompts y motivos de descarte, no las respuestas), así
que el detalle interno del fallo — si el modelo respondió en
prosa, si su razonamiento visible consumió el presupuesto de
tokens, o si el JSON venía malformado — **no es observable** con
los artefactos de esta corrida y no se hizo ningún llamado
extra-protocolo para averiguarlo. Como contexto (inferencia,
no medición): la sonda diagnóstica a temperatura 0 con 16
tokens devolvió meta-razonamiento visible («The user wants me
to respond only with "OK"…») en lugar del token pedido, un
comportamiento compatible con que el presupuesto de salida se
gaste en texto previo al JSON.

## 4. Estado tras la generación (verificado en disco y en la DB)

- **Freno de estancamiento: 1/3, inactivo — sin cambios**
  (§8: la corrida no se lanzó; el freno cuenta corridas
  evaluadas).
- **Ledger: 23 eventos, cadena de hashes recomputada e íntegra**,
  último hash `91c8e0ddc518` — idéntico al estado previo a los
  tres movimientos del día. Nadie asentó nada.
- **Scaffold vigente: sin cambios** — la base de siempre
  ({decay 0.5, gate_margin 0.0, n0 4, umbral_base 1,
  umbral_divisor 3}).
- **Panel de confirmación: declarado y SIN consumir** —
  [5000..5017]/[5100..5111] siguen vírgenes.
- **Piso, panel de puerta y validador: intocados** (5,4781;
  18/12 + E3; esta tarea no tocó `gate.py`, `metaloop.py` ni el
  panel cableado).

## 5. Suites al cierre

- **Archivos de suite del árbol: 50/50 PASS · 0 FAIL** (raíz +
  `alma_service/`; el runner que contaba 46 en los informes
  previos cubría un subconjunto — el barrido de hoy incluye las
  suites de `alma_service/` y también pasan; resultados en
  `data_corrida_generador_forma_2026-10-16/test-results-forma.json`
  y `suites.log`).
- **Suite del generador, corrida directa: 77/77 checks en
  verde** (cortafuegos y frontera por hashes incluidos).
- **Costo: US$0.** Duración del movimiento completo: ~25 minutos
  de reloj (catálogo 22:47 UTC → cierre ~22:53 UTC, incluida la
  generación de 88 s y la corrida completa de suites).

## 6. Opciones que quedan para Alejandro (ninguna ejecutada)

La corrida sigue sin realizarse, pero el obstáculo cambió de
naturaleza y eso está medido: ya no es «la plataforma no
responde» — es «el único gratuito que responde hoy no sostiene
el formato». Las rutas, en orden de fidelidad al papel vigente:

- **(a) Esperar la rotación del tier.** El precedente 002b:
  mismo papel, fecha posterior. Si vuelve el primario
  (`ling-3.1-flash:free`) o aparece un `deepseek/*:free`, la
  regla original designa sin adenda nueva. Costo US$0; costo
  real: días.
- **(b) Tanda con mistral-nemo pago.** Es el modelo que este
  sistema ya midió obedeciendo formato (28/30 en su batería de
  juez). Precio de catálogo de hoy: US$0,029/millón de tokens de
  prompt y US$0,03/millón de salida. Con el prompt real de esta
  tanda (~793 tokens el mayor) y el tope declarado, el peor caso
  de los ≤3 llamados es **≈ US$0,0004** (tres décimas de centavo
  serían US$0,003; esto es diez veces menos). El monto es
  despreciable; lo que exige es papel nuevo: el pre-registro
  vigente prohíbe sustituir por un modelo pago, así que esta
  ruta requiere su «sí» explícito con costo declarado, como
  cualquier gasto real de la casa.
- **(c) Adenda 3: descenso también ante falla de formato.**
  Declarar — antes de ejecutar, como hoy — que «responde pero no
  genera en formato tras los 3 llamados» habilita descender al
  siguiente de la tabla con una tanda nueva. Es una extensión
  legítima de la completación de hoy, pero es papel nuevo con
  su autorización: hoy no se hizo porque hacerlo tras ver el
  resultado habría roto el §6.3. Quedan en la tabla, sin sondar
  todavía: `dots-3-note-preview`, `lfm-2.5-2.6b`,
  `nemotron-3.5-lightning`, `inkling-small`, `laguna-s-2.1`,
  `inkling`, `laguna-xs-2.1`, `north-mini-code`,
  `nemotron-3-ultra-550b`, `gemma-4-26b`, `gemma-4-31b` y
  `nemotron-3-super-120b` (todos `:free`).

## 7. Lo que queda listo

Tres papeles vigentes y encadenados (pre-registro + adenda +
adenda 2, commits `1ba3763`/`79208b6`/`16f81c0`), el bloqueo de
plataforma superado por completación declarada, y el modo de
falla ahora medido con nombre propio: **formato, no
plataforma**. La tanda que el generador necesita puede venir de
la rotación (a), de un gasto de fracciones de centavo con papel
nuevo (b), o de un descenso extendido con papel nuevo (c). La
decisión es de Alejandro; el laboratorio no se movió un
milímetro mientras tanto: freno 1/3, ledger íntegro, panel de
confirmación virgen, US$0.
