# Pre-registro — Corrida de crossover sobre la población del generador

**Fecha:** 2026-10-16 · **Estado:** REDACTADO a pedido de Alejandro
(«Si lo hagamos»); **este documento es solo el papel — no hay
código nuevo ni corrida autorizada todavía**: construir el
operador y correr requieren su «corré» sobre este documento,
como fue con el generador. **Presupuesto: US$0** (el crossover
es código determinista local y la evaluación es el simulador
congelado; ningún LLM participa en ningún paso — §10).

**Documento que sucede:** `metaloop_preregistro_crossover.json`
(11–12/10/2026, aprobado entonces como diseño sin código). Ese
papel diseñó el crossover para un archivo de variantes vacío
(0 variantes al 11/10) y nunca se construyó. Este documento lo
**activa con cambios declarados** (§2): la población ya existe
— la tanda del generador de hoy — y el estado del loop cambió
(puerta recableada, freno en 2/3, panel de confirmación). Donde
este documento y el del 12/10 difieran, manda este.

## 1. Pregunta e hipótesis

Tres búsquedas ya chocaron contra la misma base
({decay 0.5, gate_margin 0.0, n0 4, umbral_base 1,
umbral_divisor 3}) sin encontrar mejora que sobreviva:

- **mutación puntual** (corrida RSO, seed 87859): 8/8 con
  Δ_train ≤ 0 — explora de a un parámetro desde el incumbente;
- **screening factorial** 2^(5−1) (adenda 1 del generador):
  SIN interacciones detectables a su resolución; único efecto
  principal detectable, umbral_base +3,2569 (subirlo empeora);
- **generador LLM coordinado** (corrida con nemo, hoy): 11
  candidatos multiparamétricos leyeron la tabla exacta de
  fracasos; el mejor dio +0,0556 en train y −0,7500 en
  held-out — sin adopción.

**Hipótesis del crossover:** recombinar parámetros de padres
DISTINTOS de esa población ya medida puede producir un hijo
en un punto del espacio que ningún padre ocupa y que ninguna
de las tres búsquedas visitó: la mezcla hereda subconjuntos de
cambios coordinados que por separado rindieron «menos mal» en
genomas distintos. Es la palanca que la literatura (DGM,
Sakana/UBC 2025) documenta como *stepping stones*: ramificar
también desde variantes peores pero diversas, no solo desde
el incumbente.

**H1:** al menos un hijo supera en train al **mejor padre**
(Δ_train > +0,0556, la marca de P5) — la recombinación aportó
algo que ningún ingrediente tenía solo.
**H2 (la que importa):** al menos un hijo es AUTO-ADOPTADO
por la puerta vigente, sin tocar piso, panel ni validador.

**Regla «hijo ≠ padre disfrazado» (heredada del 12/10, se
mantiene exacta):** un hijo solo cuenta como recombinación si
(a) toma **≥ 1 parámetro de cada padre** entre los parámetros
en que los padres difieren, y por lo tanto (b) **difiere de
AMBOS padres en ≥ 1 parámetro**. Un «hijo» que copia a un
padre en todos los parámetros en disputa es un clon de ese
padre con pasos extra: no prueba nada sobre recombinar y la
validación mecánica lo descarta antes de evaluar (§5).

## 2. Relación con el pre-registro del 12/10: qué se mantiene y qué cambia

**Se mantiene (sin tocar):** el operador de mezcla uniforme
por parámetro; las reglas de validez del hijo de §1; la
elegibilidad de pares (padres que difieren en ≥ 2 parámetros;
si difieren en 1, toda mezcla es un clon); el camino de la
puerta **idéntico** al de cualquier candidato, sin atajos ni
criterios propios del crossover; la trazabilidad por
`origen_operador='crossover'` (observabilidad, no cambia
ninguna regla); el presupuesto US$0.

**Cambia (declarado acá, con su motivo):**

| aspecto | 12/10 (diseño) | este papel | motivo |
|---|---|---|---|
| población | incumbente × mejor variante del archivo | 12 padres declarados (§4) | el archivo (`metaloop_archivo.jsonl`) solo guarda candidatos finales (2 registros); la población real es la tanda, como el §9 del generador la destinó |
| modo | operador mezclado en las rondas RSO (P=0.25 por ronda, greedy) | **tanda independiente**: hijos generados, congelados y evaluados contra la base | aislar el aporte de la recombinación; mezclado con mutación y greedy, un hijo ganador no atribuye su Δ a recombinar |
| evaluación | keep/revert greedy en train | **independiente contra la base** para todos los hijos (§7) | atribución limpia: cada Δ_train es del hijo contra la base, no contra un retenido intermedio |
| piso de la puerta | δ=0.53 «si ya está cableado» | **5,4781 totales** (δ 0,2283, recalibración v3 + recableado, commits b834e3d/ddb2859) y **panel de confirmación** de la adenda 1 del generador | el estado vigente del loop; el papel viejo es anterior a ambos |
| freno | no contemplado | esta corrida es la tercera con riesgo de plana: **2/3 → 3/3 si no adopta** (§9) | el freno se creó después; su consecuencia se declara antes de correr, no después |

## 3. Contexto medido (no opinado)

- **Puerta vigente:** max(Δ_in, Δ_ho) > **5,4781 totales**
  (≡ δ 0,2283), panel **18/12** (train [400..417], held-out
  [600..611], E3 [500,501]). **Panel de confirmación**
  [5000..5017]/[5100..5111]: declarado y **VIRGEN** — solo se
  consume si hay adopción (§7).
- **Freno de estancamiento: 2/3** (corrida RSO plana +
  corrida del generador plana). Adopciones históricas del
  meta-loop: **0**. Scaffold vigente: la base de §1.
- El espacio completo tiene 3×3×3×3×4 = **324
  configuraciones**; con medición train asentada hay ~40
  (la base, 10 mutaciones puntuales de las corridas seed 23 y
  87859, las 17 del screening sin contar el incumbente, los
  11 de la tanda). Ninguna superó +0,0556 en train.

## 4. Población de padres (cerrada, declarada antes de generar)

**SPACES vigentes** (EXP56, los mismos del generador):
decay ∈ {0.25, 0.5, 0.75} · gate_margin ∈ {0.0, 0.05, 0.1} ·
n0 ∈ {1, 2, 4} · umbral_base ∈ {1, 2, 3} · umbral_divisor ∈
{2, 3, 4, 6}.

La población son **12 padres**: la base (P0) + los 11 válidos
de la tanda del generador (`tanda_generador_1792192469.json`),
en su orden de tanda (P1–P11). Δ_train = el asentado en
`resultados-corrida-generador-nemo-2026-10-16.md`:

| padre | decay | gm | n0 | ub | ud | Δ_train registrado | medido contra |
|---|---|---|---|---|---|---|---|
| P0 (base) | 0.5 | 0.0 | 4 | 1 | 3 | 0 (referencia) | — |
| P1 | 0.75 | 0.05 | 1 | 2 | 2 | −4,3333 | base |
| P2 | 0.25 | 0.10 | 2 | 3 | 4 | −3,7222 | base |
| P3 | 0.75 | 0.05 | 4 | 1 | 6 | −0,4444 | base |
| P4 | 0.5 | 0.10 | 1 | 2 | 3 | −3,8889 | base |
| P5 | 0.75 | 0.05 | 2 | 1 | 4 | **+0,0556** | base (KEEP) |
| P6 | 0.25 | 0.0 | 4 | 2 | 6 | −1,3333 | P5 |
| P7 | 0.5 | 0.05 | 1 | 3 | 2 | −5,0556 | P5 |
| P8 | 0.75 | 0.10 | 2 | 1 | 3 | −0,6667 | P5 |
| P9 | 0.5 | 0.05 | 1 | 2 | 6 | −1,6111 | P5 |
| P10 | 0.25 | 0.0 | 4 | 1 | 2 | −2,9444 | P5 |
| P11 | 0.75 | 0.05 | 2 | 2 | 6 | −1,2222 | P5 |

**Salvedad declarada:** los Δ de P6–P11 se midieron contra
P5 retenido (semántica greedy de esa corrida), no contra la
base. En este experimento los Δ registrados se usan **solo
como etiqueta de estrato** para ordenar pares (§6); la
medición que vale es la de cada hijo, independiente contra
la base (§7). Ningún padre se re-mide: no hace falta para la
pregunta y re-medir sería gastar panel sin información nueva
sobre la hipótesis.

**Estratos (regla de diversidad / stepping stones):**
- **ÉLITE** = los 3 mejores Δ registrados: **P5, P3, P8**.
- **RESTO** = P0, P1, P2, P4, P6, P7, P9, P10, P11 — incluye
  los genéticamente raros de la población: gate_margin 0.0
  fuera de la base solo vive en P6 y P10; decay 0.25 solo en
  P2, P6, P10; umbral_base 3 solo en P2 y P7; umbral_divisor
  2 solo en P1, P7, P10. La regla de pares de §6 garantiza
  cruces élite×resto y resto×resto: no se cruza solo entre
  «los mejores», que es exactamente el sesgo que DGM abla.

**Exclusiones declaradas:** las variantes históricas de un
solo parámetro (corridas seed 23 y 87859: 10 mutaciones sobre
la base) **no** entran como padres. Motivos: (a) difieren de
la base en exactamente 1 parámetro → contra P0 son pares
inelegibles por la regla de §1, y su aporte genético ya está
contenido en los valores que los padres de la tanda portan;
(b) sus efectos principales ya están medidos dos veces
(corrida RSO y screening factorial); (c) fidelidad al destino
que el §9 del pre-registro del generador le dio a la tanda:
«la población inicial para un futuro crossover» es la tanda,
no el historial entero. Los descartados de la tanda (10
crudos por diversidad/movimiento simple) tampoco entran:
nunca fueron candidatos válidos ni tienen Δ medido.

## 5. El operador (mecánico, determinista, sin LLM)

- **Pares elegibles:** todo par no ordenado de padres que
  difiera en **≥ 2 parámetros**. (La tanda ya garantizaba
  distancia ≥ 2 entre sus miembros y la base dista ≥ 2 de
  cada uno — mínimo: P0×P10, en decay y umbral_divisor — así
  que los **66 pares** de la población son elegibles.)
- **Mezcla uniforme por parámetro:** por cada uno de los 5
  parámetros, el hijo toma el valor de uno de los dos padres
  con probabilidad 1/2, con el rng sembrado por la semilla
  de la corrida (la del pre-registro máquina de siempre:
  reproducible entera a partir de esa semilla).
- **Validez del hijo (mecánica, antes de evaluar):**
  (i) hereda ≥ 1 parámetro-en-disputa de **cada** padre (la
  regla de §1: difiere de ambos en ≥ 1); (ii) no es idéntico
  a ningún padre ni a ningún hijo ya aceptado en la tanda;
  (iii) no coincide con **ninguna configuración que ya tenga
  medición train asentada** — conjunto de exclusión extraído
  mecánicamente al congelar de: la población, el historial
  del ledger (mutaciones seed 23/87859 y tanda) y las 18
  configuraciones del screening
  (`data_screening_factorial_2026-10-16/`): re-evaluar un
  punto ya medido en un simulador determinista no agrega
  información, solo gasta el conteo de la tanda.
  Hasta **10 re-rolls** por par con el mismo rng; si no sale
  un hijo válido, el par se salta y queda asentado con
  motivo. Todo descarte se registra con su motivo, como en
  la tanda del generador.
- **Sin mutación posterior:** declarado explícitamente —
  ningún paso de mutación toca al hijo después del cruce.
  Si un hijo gana, su Δ es atribuible a recombinar (más el
  azar de la mezcla, fijado por semilla); con mutación
  encima, la atribución se pierde y la hipótesis de §1 no
  se puede ni confirmar ni refutar.
- **Congelamiento antes de medir:** la tanda completa de
  hijos (pares, padres, herencia por parámetro, semilla)
  queda escrita en `tanda_crossover_<ts>.json` **antes** de
  evaluar a nadie. Prohibido bajo este papel: regenerar la
  tanda tras ver resultados, agregar pares, cambiar el
  tamaño ni «ayudar» con selección manual.

## 6. Tamaño de tanda y selección de pares

**Tanda objetivo: 24 hijos válidos** (mínimo 8 para lanzar;
con menos, la corrida **no se lanza** — «tanda insuficiente»,
el freno no se mueve — espejo del §7 del generador).
Criterio del 24: la evaluación es el simulador determinista
local (la corrida de 11 candidatos tardó ~5 s; 24 hijos
quedan en el orden de decenas de segundos, US$0), y 24
alcanza para cubrir **todos** los pares del mejor padre
(11), todos los de la élite restante y una cola de cruces
resto×resto, sin abrir la puerta a «generar hasta que algo
pase»: el tamaño se fija acá, antes, y la garantía
estadística la cargan la puerta y el panel de confirmación,
no el volumen de la tanda.

**Orden de procesamiento de pares (determinista, declarado):**
(1) los pares de **P5** con cada otro padre, por índice del
otro padre; (2) los pares de **P3** y después los de **P8**
aún no procesados, por índice; (3) los pares de **P0** aún
no procesados, por índice; (4) todos los pares restantes,
en orden lexicográfico (i, j). Se genera de a un hijo por
par bajando por esta lista hasta llegar a 24 válidos o
agotar los 66 pares. El orden privilegia a la élite sin
excluir a los stepping stones: los estratos RESTO entran
como pareja de la élite desde el primer bloque y entre sí
en el cuarto.

## 7. Evaluación y camino a la puerta

1. **Medición independiente:** cada hijo se evalúa con el
   validador congelado (`MetaLoop._evaluar`, sin tocarlo)
   sobre el panel train [400..417] y su **Δ_train se calcula
   contra la base** (media de la base − media del hijo, en
   totales). Nada de greedy secuencial: ningún hijo se mide
   contra otro hijo ni contra un retenido. (Nota de
   implementación declarada: el camino `correr(candidatos=…)`
   existente es greedy y **no** satisface esta semántica; la
   implementación futura mide independiente y recién
   después invoca el camino de decisión normal para el
   finalista. Esa implementación es trabajo posterior a la
   autorización de correr, con las pruebas del papel del
   12/10 adaptadas: mezcla con semilla fija, hijo que difiere
   de ambos y hereda de ambos, par a distancia 1 inelegible,
   deduplicación contra el conjunto de exclusión, paridad de
   puerta.)
2. **Finalista único:** los hijos con Δ_train > 0 se ordenan
   por Δ_train descendente y **solo el mejor** recorre el
   camino completo de la puerta contra la base — dos splits
   (Δ_in, Δ_ho), E3 ciego, piso 5,4781, auto-adopción por el
   camino normal — asentado con `origen_operador='crossover'`
   y sus dos padres en el audit record. Los demás positivos
   quedan asentados con su Δ_train como señal; **no** pasan
   a held-out ni a E3 en esta corrida. Motivo: cada pasada
   extra por los splits ciegos es una mirada adaptativa más
   sobre el mismo panel (la advertencia central del estudio
   externo de hoy); la puerta ve un candidato por corrida,
   como siempre.
3. **Si el finalista auto-adopta:** la ganancia **oficial**
   es el Δ de **confirmación** sobre el panel virgen
   [5000..5017]/[5100..5111] contra el incumbente anterior,
   con evento `confirmacion_adopcion` en el ledger y el Δ
   de la puerta registrado como «Δ de selección» — el
   protocolo exacto de la adenda 1 del generador (ajuste 2).
   Sin adopción, el panel **no se consume**.

## 8. Criterios (declarados antes de correr)

| veredicto | condición | qué afirma / refuta |
|---|---|---|
| **ADOPCIÓN (éxito, H2)** | el finalista pasa la puerta completa y auto-adopta | la recombinación encontró, en este paisaje, un punto que tres búsquedas no encontraron; la ganancia oficial es la de confirmación, no la de selección |
| **SEÑAL PARCIAL (H1 sin H2)** | ≥ 1 hijo con Δ_train > **+0,0556** (mejor padre) y ninguna adopción | recombinar aportó sobre su mejor ingrediente en train; la puerta o el segundo split mandan — la señal queda asentada, no inflada |
| **FRACASO INFORMATIVO** | **ningún** hijo supera al mejor padre en train (max Δ_train hijos ≤ +0,0556) | la recombinación no aportó sobre su mejor ingrediente en esta población; sumado al screening (sin interacciones detectables) y a la tanda LLM (sin ganancia que sobreviva a held-out), la lectura «la base es un óptimo local robusto de este espacio» pasa a descansar en cuatro métodos de búsqueda distintos. Sub-caso fuerte: si además ningún hijo da Δ_train > 0, ni siquiera hubo material positivo que heredar |

- **TANDA INSUFICIENTE:** < 8 hijos válidos tras agotar los
  pares → la corrida no se lanza, el freno no se mueve, y se
  reporta como falla de generación de la tanda (no como
  corrida plana).
- Ningún otro desenlace mueve el arco: no hay «casi» ni
  reintentos bajo este papel.

## 9. Contabilidad del freno — y la detención que viene escrita

Esta corrida **es** una corrida del meta-loop a efectos del
freno (`registrar_corrida` del camino normal): **con
adopción, la racha vuelve a 0; sin adopción, pasa de 2/3 a
3/3 y el freno se ACTIVA**: `correr()` se niega a seguir
hasta revisión humana, y desde el arreglo de gobernanza de
hoy (commit f728cd1) el desbloqueo exige el token humano
(`ALMA_TOKEN_HUMANO`) — ya no es una etiqueta que cualquier
llamador pueda declarar.

**Declarado antes de correr: esa detención, si llega, es el
comportamiento correcto del sistema, no una falla.** El freno
existe exactamente para esto: tres métodos de búsqueda
evaluados en serio (mutación puntual, generador LLM,
crossover) sin una sola adopción es el punto donde el diseño
manda parar y que un humano mire el conjunto, en vez de
seguir gastando paneles ciegos en una cuarta, quinta, sexta
búsqueda. Lo que Alejandro revisaría con los datos de las
tres corridas sobre la mesa — la tabla completa de Δ de
~65 configuraciones medidas sobre 324, el screening sin
interacciones, la señal de +0,0556 que se revirtió en
held-out, y el veredicto de esta tanda — es **dónde está el
cuello de botella**: si el espacio de scaffold (5 parámetros,
324 puntos) está agotado como fuente de mejora medible, las
palancas siguientes son de otro tipo (espacio más rico,
otros tamaños de paso, otra superficie editable) y cada una
es papel nuevo con su propia autorización — no una cuarta
corrida de búsqueda bajo papeles viejos.

## 10. Costos

**US$0.** El crossover es código sobre configuraciones ya
congeladas; la evaluación es el simulador determinista
local; no hay llamados a modelos en ningún paso del diseño.
Si una variante futura quisiera un LLM en cualquier punto
(elegir pares, «arreglar» hijos), eso es **otro papel**:
queda fuera de alcance de este pre-registro por declaración.

## 11. Fronteras y qué NO prueba este experimento

- **Intocables:** piso (5,4781), panel (18/12 + E3), panel
  de confirmación, validador congelado (e47/e56), regla de
  la puerta y del auto-adoptar, y el freno. El crossover
  propone; la gobernanza decide.
- Una adopción acá probaría el **mecanismo** (recombinar →
  medir → adoptar sobre el piso de ruido) dentro del
  simulador determinista. **No prueba que el scaffold
  mejore en tareas reales**, y el informe de la corrida no
  debe decirlo.
- Un fracaso informativo **no** prueba que no exista una
  configuración mejor entre las 324: prueba que la
  recombinación uniforme sobre esta población de 12, con
  esta tanda de 24, no la encontró. El espacio no queda
  agotado; la palanca, medida.
- La población es la que el generador produjo con un solo
  modelo y un solo prompt: sus sesgos (concentración en
  decay 0.75 / gate_margin 0.05) son también los de esta
  tanda. Declarado, no escondido.

## 12. Estado y próximos pasos

Este documento deja el experimento **listo para autorizar**,
nada más: sin código del operador, sin tanda generada, sin
ninguna evaluación corrida. Los pasos que siguen requieren
cada uno su momento: (1) el «corré» de Alejandro sobre este
papel; (2) la implementación del operador con sus pruebas
(§7.1) y las suites de gobernanza en verde; (3) la
generación y congelamiento de la tanda; (4) la corrida, una
sola vez, con su informe de resultados propio.
