# Resultados — Corrida de crossover sobre la población del generador

**Fecha:** 2026-10-16 · **Pre-registro:**
`preregistro-crossover-2026-10-16.md` (commit `41b3adf`) ·
**Autorización:** Alejandro, «Correr» — sobre el papel tal como
está escrito (tanda de 24, finalista único, sin cambios) ·
**Construcción:** commit `8008ba4` (operador + suite + corredor) ·
**Presupuesto ejecutado: US$0** — ningún LLM en ningún paso.

## 1. Veredicto (§8 del pre-registro): SEÑAL PARCIAL

**H1 se confirmó; H2 no.** La recombinación produjo hijos que
superan en train al mejor padre: el mejor hijo marcó
**Δ_train +1,4444**, es decir **26× la marca de P5 (+0,0556)** y el
26,4% del piso de la puerta (5,4781) — y no fue un solo hijo:
**6 de 24 dieron Δ_train > 0** y 5 de ellos superaron la marca
del mejor padre. Ninguna búsqueda anterior había producido
material positivo en train a esta tasa (mutación puntual: 0/8;
generador LLM, medido independiente contra la base: 1 keep en su
corrida voraz).

Pero el finalista **cayó en la puerta por regresión en
held-out**: Δ_in +1,4444 / Δ_ho **−3,0833**. Sin adopción, sin
E3 (la puerta de dos splits rechaza y el camino normal ni lo
evalúa), panel de confirmación sin consumir. La lectura honesta
queda en §5.

## 2. La tanda (generada y congelada antes de medir a nadie)

- Operador `alma_service/crossover.py` (mezcla uniforme, sin
  mutación posterior), corredor `correr_crossover.py`, semilla
  declarada **20261016**.
- Conjunto de exclusión extraído mecánicamente al congelar:
  **36 configuraciones** (12 de la población ∪ historial del
  ledger por simulación keep/revert ∪ las 18 del screening
  factorial).
- **24/24 hijos válidos** en 25 pares procesados de 66. Un par
  saltado: **(P5, P11)**, agotó sus 10 re-rolls sin hijo válido.
  Rolls descartados: 22 — `no_hereda_de_ambos` 18,
  `duplicado_en_tanda` 4, `ya_medido_train` 0.
- Congelamiento verificado: regenerar la tanda desde la
  semilla reproduce exactamente los 24 hijos del archivo
  `tanda_crossover_1792193957.json` (34.176 bytes, con pares,
  herencia por parámetro y cada roll con su motivo).
- Suite del operador: **37/37 checks** (orden de pares,
  herencia, inelegibilidad a distancia 1, deduplicación,
  extracción de exclusión, determinismo, paridad de puerta,
  frontera por hashes). Batería de gobernanza al cierre:
  **51/51 archivos PASS**.

## 3. Mediciones independientes contra la base (panel train [400..417])

Media train de la base: **85,2222** (la de siempre en este
panel). Δ_train = media base − media hijo, en totales.

| hijo | padres | decay | gm | n0 | ub | ud | Δ_train |
|---|---|---|---|---|---|---|---|
| 1 | P0×P5 | 0.5 | 0.05 | 2 | 1 | 3 | −0,5556 |
| 2 | P1×P5 | 0.75 | 0.05 | 1 | 1 | 2 | −2,6667 |
| 3 | P2×P5 | 0.75 | 0.05 | 2 | 3 | 4 | −3,5556 |
| 4 | P3×P5 | 0.75 | 0.05 | 2 | 1 | 6 | **+0,6667** |
| 5 | P4×P5 | 0.5 | 0.1 | 2 | 2 | 4 | −3,0000 |
| 6 | P5×P6 | 0.25 | 0.0 | 2 | 2 | 4 | −2,3889 |
| 7 | P5×P7 | 0.5 | 0.05 | 1 | 1 | 4 | **+0,7222** |
| 8 | P5×P8 | 0.75 | 0.05 | 2 | 1 | 3 | −0,6111 |
| 9 | P5×P9 | 0.75 | 0.05 | 1 | 1 | 6 | **+1,4444** |
| 10 | P5×P10 | 0.25 | 0.0 | 2 | 1 | 4 | +0,0556 |
| 11 | P0×P3 | 0.5 | 0.0 | 4 | 1 | 6 | −0,0556 |
| 12 | P1×P3 | 0.75 | 0.05 | 4 | 1 | 2 | −3,2778 |
| 13 | P2×P3 | 0.25 | 0.05 | 2 | 1 | 6 | **+0,6111** |
| 14 | P3×P4 | 0.75 | 0.05 | 4 | 2 | 3 | −3,7222 |
| 15 | P3×P6 | 0.25 | 0.05 | 4 | 1 | 6 | −0,0556 |
| 16 | P3×P7 | 0.75 | 0.05 | 4 | 3 | 2 | −3,1111 |
| 17 | P3×P8 | 0.75 | 0.1 | 2 | 1 | 6 | **+0,6667** |
| 18 | P3×P9 | 0.5 | 0.05 | 4 | 1 | 6 | −0,0556 |
| 19 | P3×P10 | 0.25 | 0.0 | 4 | 1 | 6 | −0,0556 |
| 20 | P3×P11 | 0.75 | 0.05 | 4 | 2 | 6 | −2,1111 |
| 21 | P0×P8 | 0.5 | 0.1 | 2 | 1 | 3 | −0,5556 |
| 22 | P1×P8 | 0.75 | 0.05 | 2 | 2 | 2 | −3,5000 |
| 23 | P2×P8 | 0.25 | 0.1 | 2 | 1 | 3 | −0,6111 |
| 24 | P4×P8 | 0.75 | 0.1 | 2 | 2 | 3 | −3,0000 |

Positivos: 6 (hijos 4, 7, 9, 10, 13, 17). El hijo 10 empata
exacto la marca del mejor padre (+0,0556); los otros cinco la
superan. Negativos: 18. Detalle completo en
`data_crossover_2026-10-16/mediciones.json`.

## 4. El finalista y la puerta

**Finalista único** (el mejor positivo, §7.2): hijo 9,
**P5×P9** = {decay 0,75 · gate_margin 0,05 · n0 1 ·
umbral_base 1 · umbral_divisor 6}. Recombinación genuina
verificada mecánicamente: en disputa estaban decay, n0,
umbral_base y umbral_divisor; heredó **decay y umbral_base de
P5** y **n0 y umbral_divisor de P9** (gate_margin 0,05 es común
a ambos padres). Media train: 83,7778 contra 85,2222 de la
base.

Recorrido por el camino normal (audit record `av-3` en
`metaloop_archivo.jsonl`, con `origen_operador='crossover'` y
sus dos padres):

- **Puerta de dos splits: RECHAZA por regresión** —
  Δ_in **+1,4444**, Δ_ho **−3,0833** (media held-out del
  finalista: 83,7500 contra 80,6667 de la base).
- **E3: no evaluado** — el camino normal corta cuando los dos
  splits rechazan; el tercer split no relaja ni se gasta.
- **Auto-adopción: no** (la puerta no aceptó; no es caso de
  banda del piso). El piso 5,4781 ni siquiera entró en juego:
  el rechazo fue por regresión, no por margen.
- Los otros cinco positivos quedaron asentados con su Δ_train
  como señal (§7.2): no pasaron a held-out ni a E3 en esta
  corrida — un solo candidato por corrida ante los splits
  ciegos, como declara el papel.

## 5. Lectura (lo que el número dice y lo que no)

El patrón de la corrida del generador se repitió a mayor
escala: la ganancia en train **se revirtió en held-out con más
del doble de magnitud** (+1,4444 → −3,0833; con P5 había sido
+0,0556 → −0,7500). Es el tercer candidato seleccionado por
train que se revierte fuera de train — la maldición del
ganador dejando de ser metáfora: sobre este simulador, la
varianza entre réplicas domina y el máximo de train es, en
gran parte, ruido seleccionado.

El matiz nuevo y medido, a favor de la hipótesis H1: la
recombinación **sí aportó sobre sus ingredientes** en el
split donde se la midió independiente — 6 positivos de 24 y
un mejor hijo 26× sobre el mejor padre. Lo que este
experimento refuta no es «recombinar genera mejoras en
train», sino la cadena completa: ninguna mejora de train, de
ningún método, sobrevivió todavía al held-out del mismo
simulador. Sumando métodos, la lectura «la base es un óptimo
local robusto de este espacio» descansa hoy en cuatro
búsquedas distintas (mutación puntual, screening factorial,
generador LLM, crossover) y en **60 de 324 configuraciones**
con medición train asentada (36 previas + estos 24 hijos).

Esto **no** prueba que el scaffold mejore en tareas reales
(§11 del pre-registro), ni que no exista una configuración
mejor entre las 324: prueba que la recombinación uniforme
sobre esta población de 12, con esta tanda de 24, no produjo
una adopción — y que el cuello de botella medido ya no es
«generar candidatos positivos en train», sino que un Δ
positivo en train **generalice** entre paneles del mismo
mundo determinista.

## 6. El freno quedó ACTIVO — por diseño (§9)

La corrida se registró con `registrar_corrida(adoptado=False)`
por el camino normal: la racha pasó de **2/3 a 3/3** y el
**freno de estancamiento quedó ACTIVO** (evento
`metaloop_freno_estancamiento` asentado en el ledger). Desde
este momento `correr()` se niega a arrancar cualquier corrida
hasta la revisión humana, y el desbloqueo exige el token
`ALMA_TOKEN_HUMANO` (arreglo de gobernanza de hoy, commit
`f728cd1`). Nadie lo desbloqueó ni lo va a desbloquear en
esta tarea: **esta detención es el comportamiento correcto
del sistema, declarado en el §9 del pre-registro antes de
correr** — tres métodos de búsqueda evaluados en serio sin
una adopción es exactamente el punto donde el diseño manda
parar y que Alejandro mire el conjunto.

## 7. Panel de confirmación: sin consumir

No hubo auto-adopción, así que el panel de confirmación
[5000..5017]/[5100..5111] **no se evaluó**: sigue declarado y
virgen para la próxima corrida que lo necesite, como manda el
protocolo de la adenda 1 del generador. No existe evento
`confirmacion_adopcion` de esta corrida.

## 8. Estado al cierre (verificado)

- **Ledger:** 42 eventos (37 previos + `corrida_iniciada`,
  `corrida_crossover`, `audit_propuesta_e3`,
  `corrida_finalizada`, `metaloop_freno_estancamiento`),
  cadena de hashes **recomputada e íntegra**, último hash
  `6323c3c06616…`.
- **Archivo de variantes:** 3 registros; `av-3` = el finalista,
  rechazado, con origen crossover y padres P5×P9.
- **Scaffold vigente:** la base {0,5 · 0,0 · 4 · 1 · 3}, sin
  cambios. **Adopciones históricas del meta-loop: 0.**
- **Freno:** racha 3/3, **activo** (ver §6).
- **Suites:** batería de gobernanza completa **51/51 archivos
  PASS** (incluye la suite nueva del crossover, 37/37) —
  `data_crossover_2026-10-16/suites.log` y
  `test-results-crossover.json`.
- **Frontera:** `gate.py`, el panel cableado en `metaloop.py`
  y el validador quedaron intactos (la suite lo verifica por
  hashes; el camino del finalista reutilizó `_evaluar`,
  `_puerta_e3`, `PuertaDosSplits.decidir`,
  `decidir_auto_adopcion` y `promotor.auto_adoptar` del camino
  normal, sin tocar su código).
- **Tiempos:** generación y congelamiento de la tanda ~0,1 s;
  la corrida completa (24 mediciones + puerta) ~9,5 s.
  **Costo: US$0.**
- **Evidencia:** `data_crossover_2026-10-16/` (tanda congelada
  — copia; la canónica vive en la raíz —, `mediciones.json`,
  `resumen_corrida.json`, `correr.log`, `suites.log`,
  `test-results-crossover.json`) + el pre-registro de la
  corrida `metaloop_preregistro_1792193964.json` que el
  camino normal escribió en la raíz.

## 9. Qué sigue (fuera de este papel)

Nada, sin papel nuevo: el loop está detenido por el freno a
la espera de la revisión de Alejandro con las tres corridas
sobre la mesa (mutación puntual, generador, crossover), tal
como el §9 del pre-registro lo escribió antes de correr. Las
palancas siguientes — espacio de scaffold más rico, otros
tamaños de paso, otra superficie editable, o revisar la señal
train misma a la luz de la reversión medida — son cada una
un pre-registro nuevo con su autorización.
