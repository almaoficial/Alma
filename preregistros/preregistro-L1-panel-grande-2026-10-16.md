# Pre-registro — Ciclo L1: panel de selección grande + recalibración de δ + re-medición acotada

**Fecha:** 2026-10-16 · **Estado:** REDACTADO a pedido de Alejandro
(«L1: panel grande + recalibrar δ», 16/10/2026) — **este documento
es solo el papel**: no construye el panel, no recalibra, no
desbloquea el freno y no corre nada. Su ejecución es la semana
próxima y exige su «corré» sobre este documento (§13).
**Presupuesto: US$0** (simulador determinista local en todos los
pasos; ningún LLM participa — §11). **Regla que el ciclo tocaría,
solo si adopta:** `alma_service/gate.py` — `PISO_RUIDO_DELTA`
(hoy 5,4781 totales ≡ δ 0,2283, panel 18/12) y el panel cableado
en `metaloop.py`; el recableado es paso separado y posterior a la
recalibración (§6.3), como fue con la v3.

---

## 1. Objeto y lugar en la historia — este papel ES la revisión §9

El meta-loop está **detenido por diseño**: el freno de
estancamiento llegó a **3/3 ACTIVO** tras tres corridas evaluadas
sin adopción (mutación puntual RSO, generador LLM, crossover) y
`correr()` se niega a arrancar hasta la revisión humana. La
revisión que el freno esperaba se ejecutó como diagnóstico
pre-registrado (`preregistro-diagnostico-divergencia-2026-10-16.md`,
commit `c71ea8a`) y su documento de cierre,
`revision-seccion9-2026-10-16.md`, respondió la pregunta del §9
del pre-registro del crossover por la fila 1 de su tabla de
síntesis declarada: **manda el ruido de medición/selección** —
el panel de selección (train, 18 réplicas) no tiene resolución
para los efectos que las tres búsquedas persiguieron.

Este pre-registro es el **acta de esa revisión humana**: cita el
diagnóstico (§2), nombra la decisión de Alejandro — **L1**, la
primera palanca que la revisión señaló — y fija por escrito, antes
de ejecutar nada, el ciclo completo: panel nuevo con resolución,
recalibración de δ sobre ese panel con la metodología v3, y una
re-medición **acotada** de lo que las tres búsquedas ya
propusieron. Incluye además, como corazón de las condiciones de
la aprobación, la **cláusula de salida** (§9): si el ciclo no
produce adopción, la búsqueda sobre este scaffold se cierra por
esta misma acta.

**El desbloqueo del freno ocurre solo dentro de la ejecución de
este ciclo** (§7): con el token `ALMA_TOKEN_HUMANO` que Alejandro
defina en su entorno al momento de ejecutar. **Ningún valor de
token figura en este papel ni se genera en esta redacción.** Sin
token definido por él, el ciclo no puede arrancar — el freno
sigue activo y eso es el comportamiento correcto, no un bloqueo
a «resolver» por otra vía.

## 2. El diagnóstico que manda (los hechos, con recibo)

De `revision-seccion9-2026-10-16.md` (medición 13,8 s, US$0,
anclas fail-closed todas reproducidas):

1. **D1 — dentro de train, el signo de los ganadores no es
   estable.** Split-half por paridad sobre 35 configuraciones:
   de las 7 con Δ completo > 0, solo **3** son positivas en
   ambas mitades (la regla declarada exigía ≥ 6/7 para
   «estable»). El acuerdo de signo por banda: 15/15 para
   |Δ| ≥ 2, **0/7 para |Δ| < 0,5** — el panel certifica los
   efectos grandes y es moneda al aire en la banda 0,05–1,44
   donde vivieron todos los ganadores.
2. **D2 — los promedios finalistas los cargan 1–2 réplicas.**
   X9 (+1,4444): la réplica 403 aporta +21, el **48%** de su
   masa positiva; k\* = 2; su error estándar apareado es
   **1,3677** — el efecto es **1,06 SE**. P5 (+0,0556): neto de
   +1 punto-réplica sobre 18, k\* = 1, **0,10 SE**.
3. **D3 — en la región de ganadores, train anti-predice
   held-out.** Las 7 positivas medidas en held-out como
   diagnóstico: **7/7 reversiones de signo**, r = −0,6471,
   pendiente OLS −1,5855.
4. **El dato de resolución:** con sd(Δ_r) ≈ 5,8 (la del
   finalista X9), certificar un efecto de **+1,4444 a 2 SE
   exige ~65 réplicas**; el panel de selección tiene **18**. Y
   el piso de la puerta **no** es el problema: 5,4781 equivale a
   4,0 SE del Δ de X9 — un candidato realmente en el piso sería
   detectable hoy. El cuello de botella es **anterior** a la
   puerta: la etapa de selección.
5. **Lo que el diagnóstico NO resolvió:** (E) espacio agotado —
   no probada ni refutada (264 de 324 configuraciones sin
   medición train asentada; «no encontramos nada con una regla
   que no ve efectos < ~±1,4» ≠ «no existe nada mejor»).

## 3. El panel nuevo: tamaños derivados del diagnóstico

Los tamaños no se eligen por redondez: se derivan del efecto que
hay que poder certificar — **+1,4444 totales**, el mayor Δ_train
que cualquier búsqueda produjo (hijo 9 del crossover) — con la
dispersión medida de ese mismo efecto, sd(Δ_r) ≈ 5,8.

**Train = 72 réplicas.** Para que el promedio de un efecto
θ = 1,4444 supere 2 errores estándar:
SE = sd/√n ≤ θ/2 → n ≥ (2 · 5,8 / 1,4444)² = (8,03)² ≈ 64,5 →
**n ≥ 65**. Se adopta **72**: SE = 5,8/√72 = **0,6835**, el
efecto queda a **2,11 SE** (margen sobre el mínimo, no justo en
el borde), y 72 = 4 × 18 permite además mitades internas de
36/36 para cualquier control split-half futuro con el doble de
resolución que el D1 de hoy. Con 72, la banda de ruido de la
selección (±1 SE) baja de ±1,37 a **±0,68**: los efectos de la
banda histórica de ganadores (0,05–1,44) dejan de ser todos
indistinguibles de cero.

**Held-out = 48 réplicas.** Mantiene la proporción **3:2** de
todos los paneles de la historia del sistema (3/2 → 18/12 →
72/48), que es la razón sobre la que δ se calibró en cada
ocasión. Con σ = 9,04 (el conservador de la v3), los sd
paramétricos del nulo quedan: sd(Δ_in) = 9,04·√(2/72) = 1,5067
totales; sd(Δ_ho) = 9,04·√(2/48) = 1,8453 totales — held-out
sigue siendo el split más ruidoso (el patrón H3 de la v3 se
declara vigente), pero ya no por el margen que lo hacía inútil:
su SE de media apareada a sd 5,8 es 0,837 contra 1,3677 del
Δ de X9 a n=18.

**E3 = 24 réplicas (decisión declarada, con su justificación).**
El E3 vigente tiene **2** réplicas: su SE de media a sd 5,8 es
4,10 — como veto de signo es casi decorativo, y fue tolerable
solo porque ningún finalista llegó a él con los dos splits en
verde. En un ciclo cuyo objeto es la resolución, dejar el
tercer split en 2 sería dejar el eslabón más débil intacto. Se
adopta **24** (12× el actual): SE = 5,8/√24 = **1,1840**. Su rol
no cambia — veto de signo y tercera mirada ciega, no estimador
— y su límite queda declarado: reversiones en E3 menores a
~2,4 totales no se certifican a 2 SE ni con 24 (§12).

| split | hoy | L1 | SE de media (sd 5,8) |
|---|---|---|---|
| train (selección) | 18 | **72** | 1,3677 → **0,6835** |
| held-out | 12 | **48** | 1,6733* → **0,8372** |
| E3 | 2 | **24** | 4,1012 → **1,1840** |

*SE a n=12 con la misma sd, a título comparativo. El panel de
**confirmación no se toca**: [5000..5017]/[5100..5111], virgen,
sigue siendo la ganancia oficial de cualquier adopción (§8.3).

## 4. Rangos de ids: propuestos, barridos y declarados vírgenes

| uso | rango | n |
|---|---|---|
| train L1 | **[20000..20071]** | 72 |
| held-out L1 | **[21000..21047]** | 48 |
| E3 L1 | **[22000..22023]** | 24 |
| pool de calibración | **[23000..23059]** | 60 |

**Barrido de virginidad — corrido HOY, al redactar** (script y
salida cruda en `data_preregistro_L1_2026-10-16/`:
`barrido_virginidad_L1.py`, `barrido_virginidad.json`), con el
criterio estructural de la v3 (§5.6 de su pre-registro) sobre el
árbol **completo**: **402 archivos JSON/JSONL, 400 parseados**;
los 2 no parseables — los mismos de la v3
(`resultados/exp35-20260927/report.json` y
`producto/router-puro/mvp/shadow/mediciones.jsonl`) — se
inspeccionaron por texto, sin hits de candidatos. El barrido
incluye `integracion_fase21/` (la lección de la v2: el barrido
angosto de 256 archivos mintió una vez).

- **Controles que prueban que el barrido ve:** detectó los
  [200..219] de EXP64b en posición de réplica
  (`integracion_fase21/resultados/exp64b-…/report.json`,
  `/replicas`, 20+ hits estructurales) y el pool v3
  [4000..4029] en `data_recalibracion_delta_v3/resultados.json`
  (`/pool/ids`, 30 hits estructurales + 30 como claves de dict).
- **Resultado: los cuatro rangos L1 tienen 0 hits en posición
  de réplica** (ni en listas bajo claves
  replicas/seeds/panel/ids/train/held/split/e3, ni como escalares
  bajo esas claves, ni en secuencias de ≥2 enteros, ni como
  claves de dict id→valor). **Quedan declarados vírgenes** bajo
  este criterio y este alcance.
- **Hits de maquinaria ajena, declarados por transparencia**
  (ninguno es uso como réplica; se asientan como hizo la v3 con
  los índices GSM8K): 20000 como `max_chars` en
  `alma_service/evaluador_barato.py` y 20001 como largo de string
  de prueba en su test; 20000 como conteo de iteraciones en
  `producto/router-api/quorum_mock.py`; 21017/21022/21032/21043,
  22009 y varios 230xx como constantes dentro del venv empaquetado
  `producto/forense/piloto/venv/` (numpy/matplotlib); 23039 como
  escalar `/prompt_tokens` (conteo de tokens) en
  `producto/forense/piloto/resultados/piloto-a-ls20-01.jsonl`.
- **Obligación heredada de la v3:** el barrido amplio se repite
  **inmediatamente antes de ejecutar** el ciclo, sobre el
  workspace tal como esté ese día (Paso 1 de la ejecución). Si
  algún id declarado aparece usado en posición de réplica, se
  reemplaza el bloque por el rango virgen verificado más cercano
  y el reemplazo se asienta en el documento de resultados
  **antes** de evaluar nada — es el procedimiento funcionando,
  no una invalidación.

## 5. Recalibración de δ sobre el panel nuevo (metodología v3, sin re-inventar)

La v3 ya pagó los defectos de este procedimiento (la mezcla de
escalas de la v1, la validación mal especificada de la v2); este
ciclo la hereda **tal cual**, cambiando solo el panel y el pool:

- **Pool fresco: 60 réplicas vírgenes [23000..23059]** (§4) para
  estimar σ̂_pool **una sola vez**, al inicio. 60 en vez de los
  30 de la v3: el error relativo típico de σ̂ baja de ~13% a
  ~9%, y el pool sigue siendo barato (~0,02 s por réplica).
  Con ese pool se reporta la descomposición de fuentes completa
  (varianza entre bloques, entre réplicas, de medición repetida,
  del juez = 0 por construcción), como en la v3.
- **Diseño P (bootstrap paramétrico del Δ pareado), idéntico:**
  δ = z · sd(s), s = max(Δ_in, Δ_ho), **z = 2,0, B = 5000,
  semilla 12345**; Δ_in ~ N(0, 2σ²/n_in), Δ_ho ~ N(0, 2σ²/n_ho).
  **Escala única:** todo piso se expresa en escala δ (totales
  ÷ 24) **y** en totales junto a cada número; el congelamiento
  fija el par (δ escala δ ; δ × 24 en totales) como hizo la v3.
- **Validación y adopción son dos comparaciones distintas**
  (la corrección §2.2 de la v3, heredada exacta): la
  **validación** del estimador compara el piso paramétrico a
  panel 3/2 calculado con **σ̂_pool propio, sin regla max**,
  contra el piso **empírico** A/A por sorteo de paneles desde
  **ese mismo pool**, tolerancia **±0,10** escala δ. La
  **adopción** calcula el piso del panel nuevo con
  **σ_usado = max(σ̂_pool, 9,04)** — el colchón conservador se
  aplica solo al número que se adopta, nunca a la validación.
- **Controles A que deben reproducir, o todo se detiene:**
  (a) **determinismo 10/10** — 10 evaluaciones frescas del
  scaffold base sobre [0,1,2] + [3,4], sin caché, identidad
  exacta (reg_pol esperados: 71 · 83 · 90 · 84 · 81); cualquier
  diferencia detiene el ciclo. (b) **Control A**: el método
  original a panel 3/2 debe reproducir **δ_A = 0,5331 con
  |δ_A − 0,5331| ≤ 0,02** (la v3 midió 0,5320, desvío 0,0011,
  tercera reproducción consecutiva). Si no reproduce, el
  pipeline cambió y se investiga antes de mirar otro piso.
- **Cláusula de régimen:** si σ̂_pool > 11,30 (= 1,25 × 9,04),
  el generador/stream cambió de régimen: se investiga antes de
  adoptar cualquier número, sea cual sea el piso resultante.
- **Expectativa declarada antes de correr (no vinculante):**
  ambos splits se multiplican por 4 frente a 18/12 → los sd se
  dividen por 2 → δ_P(72/48) esperado ≈ **0,114 escala δ
  (≈ 2,74 totales)**, la mitad del vigente 0,2283, con
  σ_usado = 9,04. El número que manda es el medido con el
  σ_usado que resulte, no esta expectativa.

## 6. Reglas de decisión de la recalibración (fijadas antes de correr)

### 6.1 Cuándo adopta

**δ_L1 se adopta si y solo si se cumplen las tres:**
(1) la validación del estimador pasa en su especificación
(σ̂_pool propio contra empírico del mismo pool, ±0,10);
(2) ninguna cláusula de rareza de §6.2 se dispara;
(3) **δ_P(72/48) < 0,2283** — el piso nuevo mejora de verdad al
vigente. Esta tercera condición es la diferencia declarada con
la v3: el panel de L1 no se dimensiona persiguiendo un piso
objetivo (como el ≤ 0,25 de la v3) sino una **resolución**
(§3); por eso **este ciclo no tiene escalón**: no hay un panel
más grande esperando si el número sale «casi». Si δ_P(72/48)
queda ≥ 0,2283 con la validación en pie, el intento se archiva
como inconcluso con su diagnóstico (el instrumento no ganó
resolución útil) y no se busca un panel mayor bajo este papel.

### 6.2 Rarezas — no se adopta; se investiga y se archiva

- δ_P(72/48) ≥ δ_A de esta corrida (el nulo recalibrado no
  mejora al piso original en su propia escala);
- cualquier piso < 0,05 escala δ (sospecha de bug: paneles no
  independientes, RNG compartido entre ids, σ̂ ≈ 0);
- σ̂_pool en régimen (§5) o validación caída en su
  especificación;
- determinismo o control A fuera de tolerancia (§5).

### 6.3 Si adopta / si no adopta

- **Si adopta:** δ_nuevo y el panel nuevo (72/48, E3 24, con sus
  ids) quedan **congelados** en el documento de resultados, en
  el ledger y en el commit, **antes de evaluar cualquier
  candidato**, en las dos escalas. δ = 0,2283 y el panel 18/12
  vigentes quedan **superados** desde ese asiento. El
  **recableado** de `gate.py`/`metaloop.py` es un **paso
  separado y posterior** (como el del 16/10 tras la v3): compara
  en la escala declarada acá y exige evaluar el scaffold base
  sobre el panel nuevo (Δ base/base = 0 esperado) antes de
  cualquier candidato. Recién con el recableado asentado corre
  la re-medición de §8.
- **Si no adopta** (validación caída, rareza o §6.1(3)): **todo
  queda como está** — δ 0,2283, panel 18/12, E3 [500,501], el
  freno **sigue activo**, y este ciclo se archiva con su
  diagnóstico. La cláusula de salida de §9 **no** se ejecuta por
  esta vía: no se produjo el nulo certificado a resolución
  nueva que es su objeto; la decisión vuelve a Alejandro con el
  diagnóstico sobre la mesa. Recalibrar de nuevo, con otro
  número u otro panel, exige **otro pre-registro**.

## 7. El desbloqueo del freno, dentro del ciclo y solo ahí

- Este documento es el acta de revisión humana que el freno
  3/3 esperaba (§1). El desbloqueo **mecánico** ocurre una sola
  vez, al inicio de la ejecución de este ciclo, por el camino
  del arreglo de gobernanza del 16/10 (commit `f728cd1`):
  `desbloquear_freno` exige el token de la variable de entorno
  **`ALMA_TOKEN_HUMANO`**, que Alejandro define en su entorno
  en ese momento. Fail-closed: sin token configurado o con
  token incorrecto, el desbloqueo se rechaza y queda asentado.
- El desbloqueo habilita **únicamente** las corridas que este
  papel declara: la recalibración (§5, que no es corrida del
  loop pero corre con el sistema en revisión) y la re-medición
  acotada de §8. No habilita ninguna otra búsqueda, tanda ni
  proponente — para eso haría falta papel nuevo (§9).
- **Contabilidad del freno, declarada antes:** la re-medición
  de §8 cuenta como **una** corrida del meta-loop a efectos del
  freno. Si produce adopción, la racha vuelve a 0 por el camino
  normal. Si no produce adopción, se ejecuta la cláusula de
  salida (§9) y el freno queda **activo por esta acta** al
  cierre del ciclo, cualquiera sea el contador.

## 8. Alcance de re-medición: CERRADO (58 configuraciones, ni una más)

### 8.1 El conteo exacto, verificado contra los datos

El conteo ingenuo «24 + 11 + 8 + 18 = 61» cuenta registros, no
configuraciones. Verificado mecánicamente contra los datos
(recibo: `data_preregistro_L1_2026-10-16/conteo_alcance.json`):

| fuente | registros | configuraciones únicas | nota |
|---|---|---|---|
| hijos del crossover | 24 | 24 | `data_crossover_2026-10-16/mediciones.json` |
| tanda del generador (nemo) | 11 | 11 | `tanda_generador_1792192469.json` |
| mutaciones RSO seed 87859 | 8 | **7** | la mutación decay→0,75 se propuso dos veces (el «−0,50 repetido» del informe) |
| screening factorial | 18 | **17 sin la base** | 16 esquinas + 1 centro + el incumbente, que **es la base**: referencia, no candidata |
| **solape entre fuentes** | | **−1** | {0.25 · 0.0 · 4 · 1 · 2} — P10 del generador y a la vez esquina del screening |

**Alcance exacto: 58 configuraciones únicas, sin contar la
base.** Esas 58 y ninguna otra se re-miden en este ciclo.
**Anti-pesca, declarado:** sin proponentes nuevos, sin tandas
nuevas, sin hijos nuevos de crossover, sin mutaciones nuevas,
sin completar las 264 sin medir del espacio. Si una
configuración no está en la lista de las 58 (asentada en
`conteo_alcance.json`), no se mide en este ciclo — ni «de
curiosidad», porque en un simulador determinista cada medición
extra sobre el panel nuevo es una mirada más que el papel no
declaró.

### 8.2 Cómo se re-mide

1. **Medición independiente contra la base** sobre el panel
   train nuevo [20000..20071], con el validador congelado sin
   tocar: Δ_train^L1 de cada una de las 58 = media base − media
   config, en totales, sobre el mismo panel. Nada de voraz
   secuencial: cada Δ es de la configuración contra la base.
2. **Selección (umbral declarado):** recorren el camino de la
   puerta las configuraciones con **Δ_train^L1 > δ_nuevo (en
   totales)** — la selección exige que train, solo, supere el
   piso recalibrado (más exigente que la regla de la puerta,
   que pide el piso sobre el max de los dos splits; se declara
   la asimetría y su motivo: con 58 candidatas, la selección es
   la etapa que la maldición del ganador ataca, y es la que el
   diagnóstico encontró rota).
3. **Finalistas acotados:** en orden de Δ_train^L1 descendente,
   **máximo 3 finalistas** recorren la puerta (higiene de
   splits ciegos, la misma lógica del finalista único del
   crossover, con cupo declarado de 3 por la naturaleza de
   re-medición de este ciclo). Cada finalista: **held-out nuevo
   [21000..21047] → E3 nuevo [22000..22023] → regla vigente sin
   cambio de forma**: `Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(Δ_in, Δ_ho) >
   δ_nuevo`, con el E3 por su regla cableada. **La primera
   adopción cierra la re-medición**: no se evalúan más
   finalistas contra los splits ciegos.
4. **Sin adopción posible fuera de este camino:** ninguna de
   las 58 puede adoptarse por otra vía en este ciclo, y las
   mediciones viejas (panel 18/12) no se reciclan como
   evidencia de puerta — su único rol acá fue armar la lista.

### 8.3 Si hay adopción

La ganancia **oficial** es el Δ de **confirmación** contra el
incumbente anterior sobre el panel de confirmación
[5000..5017]/[5100..5111] — que sigue **virgen** y solo se
consume en este caso — con su evento `confirmacion_adopcion`
en el ledger; el Δ de la puerta queda registrado como «Δ de
selección», según el protocolo de la adenda 1 del generador.
La cláusula de salida (§9) **no** se ejecuta: el ciclo encontró
lo que buscaba y el loop sigue bajo gobernanza normal.

## 9. CLÁUSULA DE SALIDA — L5 se ejecuta por esta misma acta

**Disparo (las dos condiciones, en este orden):** (a) la
recalibración de §5 **adopta** δ_nuevo sobre el panel nuevo
(§6.1), y (b) la re-medición acotada de §8 — las 58, con su
selección y su cupo de finalistas — **no produce adopción**.

**Producido el disparo, queda ejecutado por esta acta, sin
necesidad de otra firma:**

1. **La búsqueda sobre este scaffold queda CERRADA.** El
   scaffold es el vigente: {decay 0.5 · gate_margin 0.0 · n0 4 ·
   umbral_base 1 · umbral_divisor 3} sobre el espacio EXP56 de
   324 configuraciones, con este validador congelado y esta
   tarea. La base queda declarada **óptimo operativo certificado
   a la resolución del panel nuevo** (SE de selección 0,6835,
   §3) sobre el alcance medido.
2. **El resultado final que se asienta** — en el documento de
   resultados del ciclo, en el ledger (evento de cierre del
   ciclo L1) y en el commit correspondiente — es el **nulo
   certificado**: 58 configuraciones propuestas por cuatro
   métodos (mutación, factorial como propuesta de esquinas,
   LLM coordinado, recombinación) re-medidas a resolución
   72/48/24, ninguna adoptada; el Δ_train^L1 máximo y su destino
   en la puerta quedan asentados con su número. Ese nulo es un
   **resultado del sistema**, no un intento fallido: es lo que
   el instrumento, ya capaz de ver efectos de +1,44 a más de
   2 SE, encontró.
3. **Queda prohibido sin papel nuevo que cambie el marco:**
   desbloquear el freno para buscar sobre este espacio;
   cualquier búsqueda, proponente, tanda, mutación o crossover
   nuevo sobre las 324; re-medir configuraciones del espacio
   fuera de la lista de §8 bajo este marco; y recalibrar δ o el
   panel **para este espacio** con el fin de reabrir la
   búsqueda. «Papel nuevo que cambie el marco» significa,
   taxativamente: **otro espacio** de scaffold o superficie
   editable, **otra tarea u otro validador**, u **otro
   instrumento** de medición — con su propio pre-registro y su
   propia autorización, como manda la disciplina de la casa.
4. **El freno queda activo al cierre** (§7): el loop no se
   desbloquea «para tenerlo disponible» sobre un espacio
   cerrado. Si un papel futuro de los de §9.3 lo reabre, lo
   hará por su propio acta de revisión.

**Lo que esta cláusula NO cierra:** el sistema ALMA ni su
gobernanza (ledger, pre-registros, frenos, verificador); la
vidriera (repo público, CI, artículo, perfil); el panel de
confirmación, que queda virgen para lo que un marco futuro lo
necesite; otros scaffolds, otras tareas y otros validadores
futuros; y la posibilidad misma de reabrir — lo que cierra es
**esta** búsqueda sobre **este** espacio con **este**
instrumento, no la investigación. Tampoco toca nada fuera del
laboratorio.

## 10. Hipótesis del ciclo (escritas antes de ejecutar)

- **H-L1-1 (resolución):** con el panel 72/48 y σ_usado de la
  corrida, δ_P(72/48) < 0,2283 — el piso baja porque sube n, no
  porque se afloje ningún criterio (z, estadístico y reglas de
  σ son los de la v3). Esperado ≈ 0,114 (§5).
- **H-L1-2 (el ruido era la historia):** re-medidas a SE 0,68,
  la mayoría de las 58 — y en particular los «ganadores»
  históricos (+1,4444, +0,7222, +0,6667, +0,6111, +0,0556) —
  dan Δ_train^L1 compatible con cero o negativo. Si en cambio
  alguno supera δ_nuevo en train y sobrevive a la puerta, esta
  hipótesis cae **en la dirección buena** y es el desenlace
  buscado del ciclo.
- **H-L1-3 (held-out manda el ruido del nulo):** en el panel
  nuevo, sd(Δ_ho) > sd(Δ_in) como en todo panel 3:2 previo
  (H3 de la v3), por n_ho < n_in.
- Ninguna hipótesis de este ciclo habla de tareas reales (§12).

## 11. Costos, tiempos y ventana

- **US$0.** Todo el ciclo es simulador determinista local: sin
  keys, sin juez LLM, sin servicio. Si cualquier paso exigiera
  gasto con key, queda **fuera** de este pre-registro y requiere
  otro, con presupuesto y «sí» explícito con costo y tiempo.
- **Tiempo de cómputo estimado, desde lo medido hoy:** una
  réplica ≈ 0,017–0,02 s (v3: evaluación completa de 5 réplicas
  = 0,0847 s; ~0,02 s/réplica en la v1). Recalibración: pool de
  60 + controles + sorteos ≈ **decenas de segundos** (la v3
  entera, con pool de 30, tardó 2,18 s). Re-medición: 58
  configuraciones × 72 réplicas = 4.176 réplicas ≈ **70–85 s**,
  más la base sobre el panel. Finalistas: ≤ 3 × (48 + 24) = 216
  réplicas ≈ **4 s**. Confirmación, solo si hay adopción: 30
  réplicas ≈ 0,6 s. **Total estimado del ciclo: menos de 5
  minutos de cómputo.** Si la duración medida superara 1 h se
  asienta y se reduce B antes de seguir (reducir B es cambio de
  resolución de Monte Carlo, no de criterio — regla heredada de
  la v3). El costo real del ciclo es el papel y la revisión
  humana, no el cómputo.
- **Ventana de ejecución declarada:** la **semana próxima**,
  con el «corré» de Alejandro sobre este documento y su token
  definido (§7). **Explícitamente fuera de ventana:** esta
  noche del 16/10 y el **17/10**, día de un
  compromiso laboral inamovible — el laboratorio no compite con esa fecha.

## 12. Qué NO prueba L1, y limitaciones declaradas

1. **Ni con adopción ni con nulo, L1 prueba mejora en tareas
   reales.** Prueba el mecanismo (seleccionar con resolución →
   medir → adoptar sobre el piso de ruido) dentro del simulador
   determinista. El informe del ciclo no debe decir otra cosa.
2. **El nulo, si sale, certifica el alcance medido a la
   resolución declarada** — 58 configuraciones sobre el panel
   nuevo — no la inexistencia absoluta de una configuración
   mejor entre las 324: quedan 206 sin medir ni siquiera en el
   alcance, y la cláusula de §9 cierra la búsqueda por decisión
   asentada, no por agotamiento demostrado del espacio.
3. **σ̂_pool se estima con 60 réplicas:** su error relativo
   típico es ~9%; el piso adoptado lo hereda. La regla
   max(σ̂_pool, 9,04) y la cláusula de régimen mitigan, no
   eliminan, esa incertidumbre. δ es una estimación, no una
   constante física (limitación §11.4 de la v3, vigente).
4. **Virginidad con alcance explícito:** «virgen» afirma el
   barrido estructural de §4 (árbol completo de JSON/JSONL,
   posiciones de id de réplica, hits ajenos clasificados y
   declarados). Su punto débil conocido es el alcance — por eso
   el barrido se repite antes de ejecutar, sobre el workspace
   tal como esté ese día.
5. **Sin holdout de ítems:** δ se calibra sobre el mismo stream
   congelado de 240 ítems que juzga a los candidatos; no hay
   holdout de ítems posible sin descongelar el validador.
   δ_L1 no se exporta a otro validador, otra batería ni otra
   escala — y si el validador fuera un juez LLM real, el panel
   72/48/24 costaría 144 × 240 = **34.560 juicios por candidato**
   evaluado completo: la fórmula (juicios × precio vigente) y
   su pre-registro de costo son obligación antes de exportar
   (advertencia §11.6 de la v3, vigente y agravada por el panel
   grande).
6. **El E3 de 24 sigue siendo un veto, no un estimador** (§3):
   reversiones en E3 menores a ~2,4 totales no se certifican a
   2 SE. Se declara para que nadie lea el E3 nuevo como
   precisión que no tiene.
7. **Multiplicidad acotada, no eliminada:** 58 mediciones con
   selección por umbral y cupo de 3 finalistas es el control
   declarado; la ganancia oficial sigue siendo el panel de
   confirmación virgen, que es donde una adopción se mide
   contra un panel que ninguna selección tocó.

## 13. Estado y entregables de la ejecución futura

**Estado al firmar este papel:** nada construido, nada
recalibrado, freno **3/3 ACTIVO e intacto**, δ vigente 0,2283
con panel 18/12, panel de confirmación virgen, adopciones
históricas del meta-loop: **0**. Este documento no autoriza por
sí solo ninguna corrida: la ejecución exige (a) el «corré» de
Alejandro sobre este pre-registro, (b) su token
`ALMA_TOKEN_HUMANO` definido en su entorno al momento de
ejecutar (§7) y (c) la repetición del barrido amplio de
virginidad (§4) con sus reemplazos asentados si los hubiera.

**Entregables cuando se ejecute:** documento de resultados del
ciclo L1 junto a este pre-registro (barrido repetido, Paso 0 de
determinismo, descomposición con σ̂_pool y σ_usado, control A
con su desvío, validación en la especificación de §5, δ_P(72/48)
y veredicto según §6; si adopta, el congelamiento en dos escalas
y el recableado asentado como paso separado; la tabla completa
de Δ_train^L1 de las 58; el recorrido de los finalistas; y el
desenlace: adopción con su Δ de confirmación, **o** la
ejecución de la cláusula de salida de §9 con el nulo certificado
asentado), más los eventos correspondientes en el ledger —
incluido, si dispara, el evento de cierre de la búsqueda sobre
este scaffold.

---

*Fuentes de cada dato: `revision-seccion9-2026-10-16.md` y
`data_diagnostico_divergencia_2026-10-16/` (D1/D2/D3, la fila 1
de la síntesis, el dato de ~65 réplicas, las palancas L1–L5);
`preregistro-diagnostico-divergencia-2026-10-16.md` (commit
`c71ea8a`: el papel del diagnóstico);
`preregistro-recalibracion-delta-v3-2026-10-16.md` y
`resultados-recalibracion-delta-v3-2026-10-16.md` (la metodología
heredada: diseño P, σ̂ propio para validar / σ castigado para
adoptar, controles A 0,5320 con desvío 0,0011, determinismo
10/10, δ adoptado 0,2283 = 5,4781 totales, panel 18/12, el
procedimiento de virginidad de su §5.6 y el incidente de su
§5.7); `recableado-puerta-delta-v3-2026-10-16.md` (el recableado
como paso separado); `resultados-crossover-2026-10-16.md` y
`data_crossover_2026-10-16/mediciones.json` (los 24 hijos, X9 =
+1,4444, el freno 3/3);
`resultados-corrida-generador-nemo-2026-10-16.md` y
`tanda_generador_1792192469.json` (los 11 de la tanda);
`metaloop_ledger.jsonl` (las 8 propuestas RSO de la corrida seed
87859, eventos 13–20, y el inventario de eventos al 16/10: 43);
`data_screening_factorial_2026-10-16/resultados.json` (las 16
esquinas, el centro y el incumbente del screening);
`data_preregistro_L1_2026-10-16/barrido_virginidad.json` (el
barrido de §4, corrido hoy) y
`data_preregistro_L1_2026-10-16/conteo_alcance.json` (el conteo
de §8.1, verificado hoy).*
