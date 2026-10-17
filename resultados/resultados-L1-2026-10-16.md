# Resultados — Ciclo L1: panel grande + recalibración de δ + re-medición acotada

**Fecha:** 2026-10-16 · **Pre-registro:**
`preregistro-L1-panel-grande-2026-10-16.md` (commit `fa7cb8f`) ·
**Autorización:** Alejandro — «L1: panel grande + recalibrar δ»
y «Corre» sobre el pre-registro (adelanta la ventana declarada:
su orden manda) · **Costo total: US$0** · **Cómputo total del
ciclo: ~2 min** (recalibración 2,8 s; evaluación base 5,0 s;
re-medición 84,0 s; suites ~30 s por corrida).

**VEREDICTO DEL CICLO: NULO CERTIFICADO.** La recalibración
adoptó δ_L1 = 0,1141 (2,7391 totales) con el panel 72/48/24; el
gate quedó recableado; las 58 configuraciones del alcance
cerrado se re-midieron a la resolución nueva y **ninguna superó
la selección** (mejor marca +0,1528 totales = 0,22 SE): sin
finalistas, sin adopción. Producido el disparo, la **cláusula de
salida §9 se ejecutó por la misma acta**: la búsqueda sobre este
scaffold queda **cerrada** con el nulo certificado a resolución
72/48/24 como resultado final (§7).

---

## 1. La desviación verificada durante la ejecución — y su resolución

A mitad de la ejecución, el agente principal frenó el ciclo con
una alerta: el §6.1 del pre-registro exige δ_P(72/48) < 0,2283
para adoptar, y su lectura de gate.py le daba un δ adoptado de
**0,3923** (con un piso de 28,2462), que no cumpliría la
condición — en cuyo caso el §6.3 mandaba archivar el ciclo en la
recalibración, sin recableado ni re-medición. La ejecución se
detuvo en ese punto (la re-medición no había corrido, ningún
finalista había recorrido la puerta, ninguna adopción estaba
asentada) y se verificó todo contra disco y contra recomputación
independiente. Resolución, con los números crudos a la vista:

- **gate.py en disco declara `PISO_RUIDO_DELTA = 2.7391`** y el
  par congelado (0,1141 escala δ ; 2,7391 totales). Los números
  0,3923 y 28,2462 **no aparecen en ningún artefacto de este
  ciclo** (barrido de texto sobre el árbol: solo constantes
  ajenas del venv empaquetado).
- **δ_P(72/48) medido = 0,1141 escala δ = 2,7391 totales**
  (diseño P, σ_usado = 9,04). Recomputado de forma independiente
  desde los datos guardados: **idéntico**. Y 0,1141 < 0,2283:
  la condición §6.1(3) **se cumple**.
- El único 0,392x en la historia del proyecto es **δ_C =
  0,3922**: el nulo A/A con panel 6/4 de la recalibración **v1,
  archivada** (`resultados-recalibracion-delta-2026-10-16.md`)
  — otra cantidad, de otra corrida, con otro panel. Y 28,2462
  ≈ 0,3923 × 72 sería convertir esa escala δ multiplicando por
  el tamaño del train en vez de por la conversión declarada
  (totales = δ × 24). La alerta nació de esa colisión de
  números; el cableado de este ciclo es el par que el §6.1
  autoriza. La verificación completa quedó asentada además en
  el evento `recableado_puerta_delta_L1` del ledger.

Con la desviación resuelta sobre evidencia, el ciclo continuó
desde el recableado correcto. La medición del panel nuevo
(pool, A/A, validación) nunca estuvo en duda y se conserva
entera en `data_L1_2026-10-16/`.

---

## 2. Paso 1 — Re-barrido de virginidad (antes de ejecutar)

El barrido amplio de §4 se repitió hoy sobre el workspace tal
como está, con el mismo script y criterio (salida:
`data_L1_2026-10-16/barrido_virginidad_ejecucion.json`):
**402 archivos JSON/JSONL, 400 parseados**; los 2 no parseables
de siempre inspeccionados por texto. Controles que prueban que
el barrido ve: EXP64b [200..219] con 23 hits en posición de
réplica; pool v3 [4000..4029] con 60. **Los cuatro rangos L1:
0 hits en posición de réplica** (train [20000..20071], held-out
[21000..21047], E3 [22000..22023], pool [23000..23059]). Único
hit, el ya declarado al redactar: 23039 como `/prompt_tokens`
en un resultado del piloto forense (escalar bajo otra clave —
maquinaria ajena, no uso como réplica). **Rangos vírgenes: se
ejecuta con los declarados, sin reemplazos.**

## 3. Paso 2 — Recalibración de δ (metodología v3 heredada)

Script: `data_L1_2026-10-16/run_recalibracion_L1.py`; datos:
`data_L1_2026-10-16/recalibracion_resultados.json`. Duración:
2,8 s.

**Paso 0 — determinismo:** 10 evaluaciones frescas del scaffold
base sobre [0,1,2]+[3,4]: **10/10 idénticas**, diferencia máxima
0,0; ancla reg_pol = **71 · 83 · 90 · 84 · 81** exacta.

**Paso 1 — pool fresco [23000..23059] (60 réplicas):** media
85,1000; **σ̂_pool = 8,5384** (ddof=1); descomposición: varianza
entre bloques dentro de réplica, media 2,5476 (sd típica 1,5961);
varianza de medición repetida = 0 (Paso 0); varianza del juez
= 0 por construcción. **σ_usado = max(8,5384 ; 9,04) = 9,04.**
Cláusula de régimen (σ̂ > 11,30): **no activada**.

**Paso 2 — control A:** el método original a panel 3/2
reproduce **δ_A = 0,5320** — desvío 0,0011 contra 0,5331
(tolerancia ±0,02). Cuarta reproducción consecutiva del control.

**Paso 3 — validación (especificación §2.2 de la v3):** piso
empírico A/A por sorteo de paneles 3/2 desde el pool de 60 =
**0,5381**; piso paramétrico P(3/2) con σ̂_pool propio =
**0,5281**; diferencia **0,0100 ≤ ±0,10 → VALIDA**. Referencia
informativa (no puerta): P(3/2) con σ_usado = 0,5591, contra
0,5623 de la v1 (desvío 0,0032).

**Paso 4 — δ_P(72/48) con σ_usado:** sd(Δ_in) = 1,5264 totales,
sd(Δ_ho) = 1,8387 totales (teóricos 1,5067 / 1,8453);
**δ_P(72/48) = 2,7391 totales = 0,1141 escala δ.**

**Decisión §6.1 — las tres condiciones:** (1) validación pasa
✓ · (2) sin rarezas ✓ (δ_P < δ_A: 0,1141 < 0,5320; ningún piso
< 0,05 — el mínimo es 0,1141; σ̂ fuera de régimen; controles en
tolerancia) · (3) δ_P(72/48) = 0,1141 **< 0,2283** ✓ (la
expectativa declarada era ≈0,114). **ADOPTA.**

**Congelamiento (antes de evaluar cualquier candidato):**
par **(0,1141 escala δ ; 2,7391 totales)**, panel train
[20000..20071] / held-out [21000..21047] / E3 [22000..22023],
asentado en el ledger — evento `recalibracion_delta_L1`, hash
`718b401a60d8…` — y en el commit `3b400a8`. δ = 0,2283 y el
panel 18/12 quedan superados desde ese asiento. Sin escalón,
como el papel manda.

---

## 4. Paso 3 — Recableado de la puerta (paso separado, §6.3)

Cambios (procedencia escrita en el código, equivalencia del par
en las dos escalas junto a cada número):

- `alma_service/gate.py`: `PISO_RUIDO_DELTA` 5,4781 → **2,7391
  totales** + `REGLA_AUTO_ADOPCION` + notas de escala e historia
  (el par v3 queda asentado como valor anterior superado).
- `alma_service/metaloop.py`: `TRAIN_REPS` → [20000..20071],
  `HELDOUT_REPS` → [21000..21047], con la nota de procedencia;
  la maquinaria de e56, intacta.
- `alma_service/puerta_e3.py`: `E3_REPS` [500,501] →
  **[22000..22023]** (decisión §3 del pre-registro: el E3 de 2
  réplicas tenía SE 4,10 — veto casi decorativo; con 24, SE
  1,1840). La regla E3 no cambia.

**Base evaluada sobre el panel nuevo antes de cualquier
candidato** (`run_recableado_base_L1.py` →
`resultados_base_L1.json`): cableado verificado importando los
módulos vivos; ancla histórica 71/83/90/84/81 exacta; medias
base: **train 83,2639 (72) · held-out 83,5000 (48) · E3 nuevo
82,8750 (24)**; segunda evaluación con caché fresco idéntica
por réplica; **Δ base/base = 0,0 / 0,0** por la ruta real de la
puerta.

**Suites:** baseline pre-recableado **51/51 PASS**;
post-recableado en crudo 49/51 — las únicas 2 fallas fueron los
fixtures atados al cableado viejo (`test_piso_ruido_puerta.py`,
`alma_service/test_e3_integracion.py`), actualizados y
declarados (banda Δ=2,0 y borde 2,7391 en la suite del piso;
rango L1 en la de E3); **post-recableado: 51/51 PASS**. Evento
`recableado_puerta_delta_L1` en el ledger (hash `8cdaf021865f…`);
commit `e486631`. Ningún candidato evaluado en este paso.

---

## 5. Paso 4 — Re-medición de las 58 (§8, alcance cerrado)

Medición independiente contra la base sobre el panel train
nuevo, con el validador congelado sin tocar (script:
`run_remedicion_L1.py`; datos crudos: `remedicion_resultados.json`).
Ancla fail-closed: los reg_pol de la base reprodujeron exactos
los del recableado antes de medir a nadie. Duración: 84,0 s.

**Selección declarada: Δ_train^L1 > 2,7391 totales. Resultado:
0 de 58.** Sin finalistas: la puerta no se recorrió, held-out
y E3 del panel nuevo no se consumieron en candidatos, y la
regla del token nunca entró en juego (no hubo adopción que
asentar).

Distribución de los Δ_train^L1: **9/58 positivos, todos ≤
+0,1528**; mediana −0,8889; media −1,8278; mínimo **−6,5417**.
La mejor marca, **+0,1528, es el 5,6% del piso nuevo y 0,22 SE**
(SE de selección 0,6835): compatible con cero. El instrumento
nuevo sí ve los efectos grandes — en la dirección negativa hay
marcas de −6,5, a más de 9 SE — así que el nulo no es ceguera:
es lo que hay en el alcance medido.

**Los ganadores históricos, re-medidos a 72 réplicas:**

| config | qué era (a 18 réplicas) | Δ_train^L1 (a 72) |
|---|---|---|
| {0.75 · 0.05 · 1 · 1 · 6} | X9, finalista del crossover: **+1,4444** | **+0,1389** |
| {0.75 · 0.05 · 2 · 1 · 4} | P5, el keep del generador: **+0,0556** | **+0,0139** |
| {0.25 · 0.1 · 2 · 1 · 3} | X10, positivo del crossover: **+0,0556** | **−0,1389** |

H-L1-2 queda confirmada en su forma fuerte: el «positivo de
train» de las tres búsquedas era ruido seleccionado, y a la
resolución que el diagnóstico pidió, desaparece.

### Tabla completa — Δ_train^L1 de las 58 (orden descendente)

(media base en train nuevo = 83,2639; Δ en totales; umbral de
selección = 2,7391 — ninguna fila lo supera)

| # | decay | gm | n0 | ub | ud | Δ_train^L1 | fuente |
|---|---|---|---|---|---|---|---|
| 1 | 0.75 | 0.05 | 2 | 1 | 3 | +0.1528 | crossover |
| 2 | 0.75 | 0.1 | 2 | 1 | 3 | +0.1528 | generador |
| 3 | 0.75 | 0.05 | 1 | 1 | 6 | +0.1389 | crossover |
| 4 | 0.75 | 0.05 | 2 | 1 | 6 | +0.1389 | crossover |
| 5 | 0.75 | 0.1 | 1 | 1 | 6 | +0.1389 | screening |
| 6 | 0.75 | 0.1 | 2 | 1 | 6 | +0.1389 | crossover |
| 7 | 0.25 | 0.0 | 2 | 1 | 4 | +0.0694 | crossover |
| 8 | 0.25 | 0.05 | 2 | 1 | 6 | +0.0417 | crossover |
| 9 | 0.75 | 0.05 | 2 | 1 | 4 | +0.0139 | generador |
| 10 | 0.5 | 0.05 | 2 | 1 | 3 | +0.0000 | crossover |
| 11 | 0.5 | 0.05 | 4 | 1 | 3 | +0.0000 | RSO |
| 12 | 0.5 | 0.1 | 2 | 1 | 3 | +0.0000 | crossover |
| 13 | 0.5 | 0.1 | 4 | 1 | 3 | +0.0000 | RSO |
| 14 | 0.75 | 0.0 | 4 | 1 | 3 | -0.0139 | RSO |
| 15 | 0.25 | 0.0 | 1 | 1 | 6 | -0.0556 | screening |
| 16 | 0.5 | 0.0 | 4 | 1 | 4 | -0.0833 | RSO |
| 17 | 0.75 | 0.0 | 4 | 1 | 6 | -0.1250 | screening |
| 18 | 0.75 | 0.05 | 4 | 1 | 6 | -0.1250 | generador |
| 19 | 0.25 | 0.0 | 4 | 1 | 6 | -0.1389 | crossover |
| 20 | 0.25 | 0.05 | 4 | 1 | 6 | -0.1389 | crossover |
| 21 | 0.25 | 0.1 | 2 | 1 | 3 | -0.1389 | crossover |
| 22 | 0.25 | 0.1 | 4 | 1 | 6 | -0.1389 | screening |
| 23 | 0.5 | 0.0 | 4 | 1 | 6 | -0.1667 | crossover |
| 24 | 0.5 | 0.05 | 4 | 1 | 6 | -0.1667 | crossover |
| 25 | 0.5 | 0.05 | 1 | 1 | 4 | -0.1806 | crossover |
| 26 | 0.25 | 0.0 | 4 | 2 | 6 | -0.6667 | generador |
| 27 | 0.75 | 0.05 | 4 | 1 | 2 | -0.7361 | crossover |
| 28 | 0.75 | 0.1 | 4 | 1 | 2 | -0.7361 | screening |
| 29 | 0.25 | 0.0 | 4 | 1 | 2 | -0.8472 | generador+screening |
| 30 | 0.5 | 0.0 | 4 | 1 | 2 | -0.9306 | RSO |
| 31 | 0.75 | 0.0 | 1 | 1 | 2 | -1.1250 | screening |
| 32 | 0.75 | 0.05 | 1 | 1 | 2 | -1.1250 | crossover |
| 33 | 0.25 | 0.1 | 1 | 1 | 2 | -1.4722 | screening |
| 34 | 0.75 | 0.05 | 2 | 2 | 6 | -1.6667 | generador |
| 35 | 0.75 | 0.05 | 4 | 2 | 6 | -1.6667 | crossover |
| 36 | 0.5 | 0.05 | 1 | 2 | 6 | -2.0417 | generador |
| 37 | 0.5 | 0.05 | 2 | 2 | 4 | -2.2917 | screening |
| 38 | 0.5 | 0.1 | 2 | 2 | 4 | -2.2917 | crossover |
| 39 | 0.25 | 0.0 | 4 | 3 | 6 | -2.5972 | screening |
| 40 | 0.5 | 0.0 | 4 | 2 | 3 | -2.6250 | RSO |
| 41 | 0.25 | 0.0 | 2 | 2 | 4 | -2.7917 | crossover |
| 42 | 0.75 | 0.05 | 4 | 2 | 3 | -2.8333 | crossover |
| 43 | 0.75 | 0.1 | 2 | 2 | 3 | -2.9583 | crossover |
| 44 | 0.5 | 0.1 | 1 | 2 | 3 | -3.2778 | generador |
| 45 | 0.75 | 0.1 | 4 | 3 | 6 | -3.4722 | screening |
| 46 | 0.25 | 0.1 | 1 | 3 | 6 | -3.5833 | screening |
| 47 | 0.75 | 0.0 | 1 | 3 | 6 | -4.2222 | screening |
| 48 | 0.5 | 0.0 | 4 | 3 | 3 | -4.3472 | RSO |
| 49 | 0.75 | 0.05 | 2 | 3 | 4 | -4.5000 | crossover |
| 50 | 0.75 | 0.05 | 2 | 2 | 2 | -4.6806 | crossover |
| 51 | 0.25 | 0.1 | 2 | 3 | 4 | -5.2083 | generador |
| 52 | 0.75 | 0.0 | 4 | 3 | 2 | -5.2083 | screening |
| 53 | 0.75 | 0.05 | 4 | 3 | 2 | -5.2083 | crossover |
| 54 | 0.75 | 0.05 | 1 | 2 | 2 | -5.2222 | generador |
| 55 | 0.25 | 0.1 | 4 | 3 | 2 | -5.7361 | screening |
| 56 | 0.5 | 0.05 | 1 | 3 | 2 | -6.4028 | generador |
| 57 | 0.25 | 0.0 | 1 | 3 | 2 | -6.5139 | screening |
| 58 | 0.75 | 0.1 | 1 | 3 | 2 | -6.5417 | screening |

---

## 6. Finalistas y puerta

**Ninguno.** Sin configuraciones sobre la selección no hay
finalistas que recorrer: held-out [21000..21047] y E3
[22000..22023] solo se evaluaron para la base (anclas del paso
de recableado). La regla del token — detener la ejecución antes
de asentar una adopción, porque `ALMA_TOKEN_HUMANO` no está
definido y nadie lo define en este ciclo — quedó sin uso: no
hubo adopción pendiente que reportar. No se llamó a
`desbloquear_freno` en ningún paso del ciclo.

## 7. Veredicto y cláusula de salida (§9) — EJECUTADA

**Veredicto del ciclo: NULO CERTIFICADO a resolución 72/48/24.**

Disparo de la cláusula, verificado en orden: (a) la
recalibración **adoptó** δ_L1 sobre el panel nuevo (§3 de este
documento) ∧ (b) la re-medición acotada de las 58 **no produjo
adopción** (§5). Producido el disparo, la cláusula quedó
ejecutada por la misma acta del pre-registro, sin otra firma,
y asentada en el ledger (evento `cierre_busqueda_scaffold_L1`,
hash `91d24c9d3b78…`, tras el evento `remedicion_L1`, hash
`25e4db8b75df…`):

1. **La búsqueda sobre este scaffold queda CERRADA.** El
   scaffold vigente {decay 0,5 · gate_margin 0,0 · n0 4 ·
   umbral_base 1 · umbral_divisor 3} sobre el espacio EXP56 de
   324 configuraciones, con este validador y esta tarea, queda
   declarado **óptimo operativo certificado a la resolución
   del panel nuevo** (SE de selección 0,6835) sobre el alcance
   medido.
2. **El resultado final asentado es el nulo certificado:** 58
   configuraciones propuestas por cuatro métodos (mutación
   puntual, screening factorial, LLM coordinado,
   recombinación), re-medidas a resolución 72/48/24; ninguna
   supera la selección; ninguna adoptada; Δ_train^L1 máximo
   +0,1528. Es un resultado del sistema, no un intento fallido.
3. **Queda prohibido sin papel nuevo que cambie el marco**
   (otro espacio o superficie, otra tarea u otro validador, u
   otro instrumento): desbloquear el freno para buscar sobre
   este espacio; nuevas búsquedas/proponentes/tandas sobre las
   324; re-medir fuera de la lista de §8 bajo este marco;
   recalibrar δ o el panel para este espacio para reabrir.
4. **El freno queda activo al cierre** (§7 del pre-registro).

**Lo que la cláusula NO cierra** (declarado en el acta): el
sistema ALMA ni su gobernanza; la vidriera; el panel de
confirmación, que queda **virgen**; otros scaffolds, tareas y
validadores futuros; nada fuera del laboratorio. **Límite del
nulo (§12.2 del pre-registro):** certifica el alcance medido —
58 configuraciones — a la resolución declarada; quedan 206 sin
medir, y el cierre es por decisión asentada, no por agotamiento
demostrado del espacio.

---

## 8. Hipótesis del ciclo, contrastadas

- **H-L1-1 (resolución): CONFIRMADA.** δ_P(72/48) = 0,1141 <
  0,2283, sobre la expectativa declarada (≈0,114): el piso bajó
  porque subió n — z, estadístico y reglas de σ intactos.
- **H-L1-2 (el ruido era la historia): CONFIRMADA.** A SE
  0,68, los ganadores históricos dan compatible con cero
  (+0,1389 / +0,0139 / −0,1389) y ninguna de las 58 supera la
  selección (§5).
- **H-L1-3 (held-out manda el ruido del nulo): CONFIRMADA.**
  En el panel nuevo, sd(Δ_ho) > sd(Δ_in) en las dos vías:
  paramétrica 72/48 (1,8387 > 1,5264) y empírica A/A 3/2 del
  pool (8,5311 > 6,9252, escala de ese panel).

## 9. Estado final verificado

- **Freno de estancamiento: ACTIVO 3/3** (DB `alma_store.db`:
  racha 3, activo 1 — sin cambios en todo el ciclo). Ningún
  token fue definido ni usado; `desbloquear_freno` nunca se
  llamó; el loop no corrió.
- **Ledger: 47 eventos, cadena de hashes recomputada íntegra**
  (último `91d24c9d3b78…` = cierre del ciclo). Los 4 eventos de
  este ciclo: `recalibracion_delta_L1` (718b401a…) ·
  `recableado_puerta_delta_L1` (8cdaf021…) · `remedicion_L1`
  (25e4db8b…) · `cierre_busqueda_scaffold_L1` (91d24c9d…).
- **Gate cableado:** piso 2,7391 totales (δ 0,1141), panel
  train [20000..20071] / held-out [21000..21047] / E3
  [22000..22023] — es el estado que la cláusula deja vigente:
  el instrumento queda calibrado aunque la búsqueda sobre
  este espacio esté cerrada.
- **Scaffold vigente:** la base {0,5 · 0,0 · 4 · 1 · 3}
  (verificado en DB, origen `default_validado_EXP56_57`).
  **Adopciones históricas del meta-loop: 0** (tabla
  `adopciones` vacía). Lo que el ciclo adoptó fue un piso y un
  panel — el instrumento — no una configuración.
- **Panel de confirmación [5000..5017]/[5100..5111]: VIRGEN,
  sin consumir.**
- **Validador congelado: sin tocar.**
- **Suites de gobernanza al cierre: 51/51 PASS**
  (`data_L1_2026-10-16/suites_finales.log`).
- **Commits locales del ciclo, en orden:** `3b400a8`
  (re-barrido + recalibración + evento) · `e486631`
  (recableado + fixtures + evento) · `c185e01` (re-medición +
  cláusula + eventos) · el de este documento (resultados +
  suites finales).
- **Duración total de ejecución:** ~35 min de reloj (la mayor
  parte, las tres corridas de suites); cómputo de medición
  ~92 s. **Costo: US$0.**

**Qué NO prueba este ciclo** (§12 del pre-registro, vigente):
ni el nulo ni una adopción habrían probado mejora en tareas
reales — L1 prueba el mecanismo (seleccionar con resolución →
medir → decidir sobre el piso de ruido) dentro del simulador
determinista. Este informe no afirma otra cosa.

*Fin de los resultados del ciclo L1.*
