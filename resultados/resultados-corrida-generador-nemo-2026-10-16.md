# Resultados — Corrida del generador con mistral-nemo (excepción paga, adenda 3)

**Fecha:** 2026-10-16 (cuarto movimiento del día sobre esta
corrida). **Documentos rectores:**
`preregistro-generador-sakana-2026-10-16.md` +
`adenda-preregistro-generador-2026-10-16.md` (commit `79208b6`) +
`adenda2-preregistro-generador-2026-10-16.md` (commit `16f81c0`) +
`adenda3-preregistro-generador-2026-10-16.md` (commit `5143edb`,
escrita y commiteada ANTES de cualquier llamado pago, como la
adenda manda). **Informes previos:**
`resultados-corrida-generador-2026-10-16.md` y
`resultados-corrida-generador-reintento-2026-10-16.md` (ambos: NO
REALIZADA por bloqueo de plataforma) y
`resultados-corrida-generador-forma-2026-10-16.md` (generación
ejecutada, tanda insuficiente 0/14).
**Autorización:** Alejandro, 16/10/2026 — «sí» explícito a la
opción «Nemo pago: US$0,0004 con papel nuevo».

## Veredicto en una línea

**LA CORRIDA SE REALIZÓ — SIN ADOPCIÓN, con señal parcial
mínima (H1 sí, H2 no).** La generación con
`mistralai/mistral-nemo` produjo tanda suficiente (**11/14
válidos**, primera tanda válida del día) por un costo real total
de **US$0,0001774**. Los 11 candidatos se evaluaron: **uno solo
mejoró en train, por +0,0556** (el 1,0% del piso de la puerta),
quedó como candidato final y la puerta lo rechazó por
**regresión en held-out (Δ_ho = −0,7500)** — el E3 ni se evaluó
(los dos splits ya rechazaban). Freno de estancamiento: **1/3 →
2/3** (§8: hubo corrida evaluada, sin adopción). Es el desenlace
«señal parcial» del §7 del pre-registro, en su magnitud más
chica posible; su lectura sustantiva está en §5 de este informe.

---

## 1. La excepción y su costo real

La adenda 3 (commit `5143edb`, en disco y en git antes de las
23:13 UTC) declaró la excepción única a la prohibición de ruta
paga: modelo `mistralai/mistral-nemo`, máximo 3 llamados de
generación, **tope duro total US$0,01**, todo el resto del
protocolo sin cambios. La generación corrió 23:13:14–23:14:29
UTC (~75 s):

| llamado | hora UTC | tokens prompt | tokens salida | costo real (US$) |
|---------|----------|---------------|---------------|------------------|
| 1 | 23:14:02 | 918 | 1.435 | 0,0000697 |
| 2 | 23:14:15 | 1.429 | 415 | 0,0000539 |
| 3 | 23:14:29 | 1.429 | 414 | 0,0000539 |
| **total** | | | | **0,0001774** |

Costo calculado desde el uso que devolvió OpenRouter por
llamado (registro en `data_corrida_generador_nemo_2026-10-16/costos.json`),
al precio del catálogo verificado hoy (US$0,029/M prompt ·
US$0,03/M salida; snapshot en la misma carpeta). El total quedó
en el **1,8% del tope duro** y por debajo incluso de la
estimación de peor caso de la adenda (≈US$0,0004). La excepción
se consumió y murió con esta corrida, como estaba declarado.

## 2. La tanda — primera válida del día

Invocación declarada en la adenda 3:
`correr_generador.py --generar --modelo "mistralai/mistral-nemo"`.
Resultado: **11 válidos de 14 objetivo** (sobre el mínimo de 8:
la corrida se lanza), 21 crudos en total entre los 3 llamados,
**10 descartes: 9× `diversidad_insuficiente` y 1×
`movimiento_simple`** — y **cero `respuesta_no_parseable`**: las
3 respuestas vinieron en el formato pedido. La reputación
medida de nemo obedeciendo formato (28/30 en EXP-JUEZ-001) se
sostuvo en generación. El modo de descarte dominante es el piso
de diversidad trabajando como fue diseñado: el modelo insistió
con variaciones a distancia 1 de candidatos ya aceptados, y la
validación mecánica las frenó sin reparar nada a mano. La tanda
completa (válidos + descartados con motivo + prompts) quedó
congelada en `tanda_generador_1792192469.json` antes de evaluar
a nadie, como manda el §6.

## 3. La corrida — Δ por candidato

`correr_generador.py --tanda tanda_generador_1792192469.json`
(23:14:39–23:14:44 UTC; pre-registro máquina
`metaloop_preregistro_1792192480.json`). Semántica greedy
secuencial declarada (§6.2): los candidatos 1–5 se midieron
contra la base; el 5 quedó *keep* y los candidatos 6–11 se
midieron contra él. Regret medio de la base en train: 85,2222.

| # | config (cambios vs base) | Δ_train | destino |
|---|--------------------------|---------|---------|
| 1 | decay .75, gm .05, n0 1, ub 2, ud 2 | −4,3333 | revert |
| 2 | decay .25, gm .10, n0 2, ub 3, ud 4 | −3,7222 | revert |
| 3 | decay .75, gm .05, n0 4, ub 1, ud 6 | −0,4444 | revert |
| 4 | gm .10, n0 1, ub 2 (decay y ud = base) | −3,8889 | revert |
| 5 | decay .75, gm .05, n0 2, ub 1, ud 4 | **+0,0556** | **KEEP → candidato final** |
| 6 | decay .25, n0 4, ub 2, ud 6 | −1,3333 | revert |
| 7 | gm .05, n0 1, ub 3, ud 2 | −5,0556 | revert |
| 8 | decay .75, gm .10, n0 2, ub 1 | −0,6667 | revert |
| 9 | gm .05, n0 1, ub 2, ud 6 | −1,6111 | revert |
| 10 | decay .25, n0 4, ud 2 | −2,9444 | revert |
| 11 | decay .75, gm .05, n0 2, ub 2, ud 6 | −1,2222 | revert |

(gm = gate_margin, ub = umbral_base, ud = umbral_divisor; los
Δ 6–11 son contra el candidato 5 retenido, no contra la base.)

## 4. La puerta sobre el candidato final

Candidato final: {decay 0,75 · gate_margin 0,05 · n0 2 ·
umbral_base 1 · umbral_divisor 4}. La puerta de dos splits lo
evaluó contra la base original:

- **Δ_in (train) = +0,0556** · **Δ_ho (held-out) = −0,7500**
- Veredicto asentado: «regresión: delta_in=0.0556,
  delta_ho=−0.7500» — dos splits rechazan; **E3 no evaluado**
  (solo se exige cuando ambos splits aceptan), `puerta_pass`
  falso, **sin auto-adopción** y sin banda de «sí» explícito.
- El piso de ruido (5,4781) ni siquiera entró en juego para el
  max: el mejor Δ_train de la tanda es el **1,0% del piso**
  (0,0556/5,4781) y encima cambió de signo en held-out.

## 5. Veredicto formal (§7) y su lectura honesta

**Formal, por el papel madre:** **SEÑAL PARCIAL (H1 sin H2).**
H1 — «al menos un candidato logra Δ_train > 0» — se cumple por
un candidato (+0,0556, retenido en train). H2 — «al menos un
candidato es auto-adoptado» — no: la puerta lo rechazó. No es
«fracaso informativo» en la letra (ese exige 0 positivos).

**Lectura honesta de la magnitud, separada del veredicto
formal:** la «señal» es de +0,0556 totales sobre una media de
85,2222 (0,07%), equivale al 1,0% del piso que la puerta
exige, y **se revirtió en held-out** (−0,7500, trece veces más
grande en magnitud y de signo contrario). Es el patrón exacto
que un Δ compatible con ruido entre paneles produce. Sumado a
los otros 10 candidatos — todos negativos, el mejor de ellos
−0,4444 — y al screening factorial de la adenda 1 (sin
interacciones detectables), la evidencia acumulada del día
apunta a lo mismo que la corrida RSO de la mañana: **la base es
un óptimo local robusto también para la búsqueda coordinada de
un LLM** que leyó la tabla exacta de fracasos. La hipótesis de
§1 («la búsqueda coordinada ve algo que la simple no vio»)
queda, con esta tanda, **sin apoyo medido**: lo único que «vio»
no sobrevivió al segundo split. Esto no prueba que ningún
proponente pueda encontrar mejora en este espacio de 324
configuraciones — prueba que *este* proponente, con *esta*
tanda de 11, no la encontró.

## 6. Estado tras la corrida (verificado en disco y en la DB)

- **Freno de estancamiento: 2/3, inactivo** — la corrida contó
  (§8: evaluada y sin adopción); la próxima corrida plana lo
  activa.
- **Ledger: 37 eventos** (23 previos + 14 de esta corrida:
  `corrida_iniciada`, 11× `audit_propuesta`, `audit_propuesta_e3`,
  `corrida_finalizada`), **cadena de hashes recomputada e
  íntegra**, último hash `c48cd906f844…`. Adopciones históricas
  del meta-loop: **siguen en 0**.
- **Scaffold vigente: sin cambios** — la base de siempre
  ({decay 0.5, gate_margin 0.0, n0 4, umbral_base 1,
  umbral_divisor 3}).
- **Panel de confirmación: NO consumido** — sin adopción no hay
  medición que hacer (adenda 1): cero eventos
  `confirmacion_adopcion`; [5000..5017]/[5100..5111] siguen
  declarados y vírgenes.
- **Piso, panel de puerta y validador: intocados** (5,4781;
  18/12 + E3; esta tarea no tocó `gate.py`, `metaloop.py` ni
  el panel cableado).
- **Destino de la tanda (§9): cumplido** — la tanda completa
  vive en `tanda_generador_1792192469.json`, en el ledger (los
  11 audit records con sus Δ) y en el archivo de variantes (el
  candidato final evaluado por la puerta): es la **población
  inicial asentada para el futuro crossover**, que sigue
  requiriendo su propia autorización.

## 7. Suites al cierre

- **Archivos de suite del árbol: 50/50 PASS · 0 FAIL** (raíz +
  `alma_service/`; detalle en
  `data_corrida_generador_nemo_2026-10-16/suites.log` y
  `test-results-nemo.json`).
- **Suite del generador, corrida directa: 77/77 checks en
  verde** (cortafuegos y frontera por hashes incluidos).
- **Duración total del movimiento:** ~15 minutos de reloj
  (adenda commiteada 23:12 UTC → suites cerradas ~23:27 UTC),
  con 75 s de generación y ~5 s de corrida.
- **Costo real total del día en esta corrida: US$0,0001774** —
  el primer gasto distinto de cero del generador, autorizado,
  pre-registrado y asentado por llamado en §1.

## 8. Alcance, dicho como el papel madre manda

Esta corrida prueba el **mecanismo** completo, por fin de punta
a punta con un proponente LLM real: proponer con criterio →
congelar → medir en train → puerta de dos splits con piso de
ruido → rechazo asentado con cadena de hashes. No prueba que
el scaffold mejore en tareas reales, y la respuesta de la
puerta acá fue **no**. Lo que el día deja medido, en orden: el
bloqueo era de plataforma, después de formato, y al final —
con formato y plataforma resueltos por US$0,0001774 — **el
paisaje**: 11 candidatos coordinados no encontraron mejora que
sobreviva a held-out. La próxima palanca sobre este problema no
es otro modelo que proponga en el mismo espacio: es el
crossover sobre la población que hoy quedó asentada, o un
espacio de scaffold más rico. Ambas son papel nuevo, no
continuación de este.
