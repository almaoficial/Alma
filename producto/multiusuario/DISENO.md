# Multiusuario: ¿puede el loop de ALMA aprender de muchos usuarios a la vez?

**Frente:** investigación/diseño · **Estado:** solo diseño, sin código · **Costo:** US$0

## 1. Punto de partida

ALMA hoy es un sistema meta-evolutivo **individual**: cada instancia corre su propio loop
(Thompson sampling + probe + skip + memoria con olvido `0.5^días` + puerta de dos splits
para auto-adopción), con frenos duros: topes de gasto por presupuesto y la obligación de
notificar cada evolución. La pregunta que encara este documento: si el router de
proveedores —o el servicio— se convierte en un producto con muchos clientes, ¿el
aprendizaje se comparte entre usuarios? ¿O cada uno arranca de cero?

Fijate que compartir aprendizaje **no** significa compartir datos crudos. Lo que viaja,
si viaja, son estadísticas agregadas: posteriors del Thompson, parámetros del scaffold,
firmas de fallo. La pregunta es qué compartir, con qué garantías, y a qué costo.

## 2. Tres opciones de arquitectura

### Opción (a) — Federado: cada usuario su loop, se agregan priors

Cada usuario corre su loop completo en su propia instalación o tenant. Periódicamente,
cada loop sube **solo agregados** a un servidor central:

- conteos de Thompson (α, β por brazo y clase), nunca las trazas;
- hiperparámetros del scaffold validados por la puerta de dos splits;
- estadísticas del detector (p. ej. efecto medido en mundos homogéneos vs heterogéneos).

El servidor promedia los priors (FedAvg sobre estadísticas suficientes) y devuelve un
**prior global** que cada loop local mezcla con su posterior local, con peso configurable.
Es el patrón clásico de *federated learning* (McMahan et al., 2017) aplicado a la política
en vez de a un modelo neuronal.

**Cómo calza con ALMA:** el loop ya distingue "prior warm" del posterior local; el prior
global federado entra exactamente como un warm mejor. El olvido `0.5^días` se aplica
también a la contribución del prior global, así que un usuario con mucho historial local
termina dominado por su propia experiencia (personalización emergente), mientras que un
usuario nuevo aprende rápido del colectivo (cold start resuelto).

### Opción (b) — Jerárquico: loop global + personalización por usuario

Un único loop corre en el servidor. Modela dos niveles: parámetros **globales** (comportamiento
típico del brazo a través de usuarios) y parámetros **por usuario** (desvío personal). Es un
modelo jerárquico bayesiano: el posterior global actúa como prior informado para cada
usuario, y cada usuario actualiza su propio posterior con su experiencia.

**Cómo calza con ALMA:** es la opción más cercana a la literatura de *multi-task bandits*:
Wan, Ge y Song (2021, arXiv:2108.06422) proponen exactamente esto —bandits multi-tarea con
modelos jerárquicos bayesianos y Thompson sampling meta-aprendido que comparte información
entre tareas vía metadata— y Hong et al. (2020, "Non-Stationary Latent Bandits", Google
Research) resuelven el problema gemelo: prototipos de comportamiento aprendidos offline,
estado latente del usuario inferido online, posterior sampling para decidir. La diferencia
práctica con (a): acá el servidor sí corre inferencia por usuario, con lo cual necesita
recibir la experiencia (rewards por brazo) aunque no los datos crudos del dominio.

### Opción (c) — Pool de experiencias compartidas anonimizadas

Un repositorio común donde cada instalación deposita **experiencias anonimizadas**: tuplas
`(firma del régimen, brazo elegido, reward medido, costo)` con el contenido del problema
removido o hasheado. Cualquier loop puede consultar el pool como un "oráculo histórico":
warm-start del Thompson, calibración del probe, y —clave— el **minero de debilidades**
puede minar firmas de fallo sobre datos de todos los usuarios, que es justo donde el
volumen importa (el EXP66 mostró que minar sobre una sola corrida tiene señal limitada).

**Cómo calza con ALMA:** el paquete único de la fase 2.1 ya define trazas unificadas
→ minero → validador → promotor. El pool extiende "trazas unificadas" a "trazas
unificadas de N usuarios". La puerta de dos splits sigue siendo local: una promoción
solo se adopta si mejora medida en **tu** split, así que experiencias ajenas malas no
pueden degradarte —solo pueden no ayudarte.

## 3. Trade-offs comparados

| Dimensión | (a) Federado | (b) Jerárquico | (c) Pool compartido |
|---|---|---|---|
| **Privacidad** | Alta: solo agregados numéricos salen del tenant. Compatible con differential privacy en bandits (Tossou 2016; Shariff 2018) agregando ruido a los conteos. | Media: el servidor ve rewards por usuario (aunque no el contenido). Requiere confianza en el operador. | Media-alta si el anonimizado es real: solo firmas y rewards. Riesgo de re-identificación si las firmas son muy específicas —hay que auditarlo. |
| **Costo** | Bajo-marginal: agregación periódica barata; la inferencia sigue siendo local. | Alto: inferencia jerárquica por usuario en el servidor, escala con usuarios × brazos. | Bajo: el pool es un datastore + consultas; el minero corre en batch. |
| **Complejidad** | Media: protocolo de agregación, versionado de priors, manejo de usuarios que se desconectan. | Alta: modelo jerárquico bien calibrado es delicado; los hiperparámetros del nivel global (varianza entre usuarios) son otro objeto a tunear. | Baja-media: schema de experiencias + anonimización + API de consulta. |
| **Velocidad de aprendizaje** | Media: el prior global acelera el cold start, pero la agregación es por lotes (diaria/semanal). | Alta en teoría: el shrinkage jerárquico transfiere en cada decisión. | Alta para lo que es raro: firmas de fallo que un usuario solo vería una vez al año aparecen en el pool con frecuencia estadística. |
| **Riesgo de contaminación** | Bajo: un usuario ruidoso aporta poco peso al promedio; y el olvido local lo diluye. | **Alto**: es el riesgo central. Si los usuarios son heterogéneos (distintos dominios, distintos regímenes), el nivel global arrastra a todos hacia la media —exactamente el "mundo heterogéneo" donde el EXP68 midió 0,00. Requiere el detector de heterogeneidad como compuerta: si el usuario difiere del global más que un umbral, se desacopla. | Medio: mitigado por diseño porque la **adopción sigue siendo local** —la puerta de dos splits rechaza lo que no mejore en tus datos. El pool propone, tu puerta dispone. |

Hay un cuarto riesgo que atraviesa las tres: **incentivos adversos**. Si el aprendizaje
compartido mejora el producto para todos, un competidor podría conectarse solo para
extraer el prior global sin aportar (free-riding), o peor, envenenar los agregados con
experiencias falsas. En (a) y (c) esto se mitiga exigiendo contribuciones mínimas y
validando agregados contra la mediana robusta en vez de la media; en (b) el servidor
puede detectar usuarios cuyas experiencias contradicen sistemáticamente al resto.

## 4. Qué dice la literatura (breve)

- **Federated bandits.** Shi et al. (2021, arXiv:2010.12763, "Federated Bandit: A
  Gossiping Approach"): agentes descentralizados que comparten solo copias privadas de
  su información con vecinos (gossip), con garantías de regret `O(poly(N,M) log T)` y
  una variante con ε-differential privacy (Fed_UCB). Mensaje para ALMA: compartir
  posteriors sin compartir observaciones tiene fundamento teórico y cotas conocidas;
  la privacidad diferencial en bandits cuesta regret extra (`1/ε`), o sea: se paga.
- **Multi-task / transfer en bandits.** Azizi et al. (2022, arXiv:2206.08556, ICML):
  Thompson sampling con transferencia robusta entre tareas similares-pero-no-idénticas,
  con análisis frecuentista y mejor performance empírica que UCB con transferencia.
  Mensaje: el Thompson —que es lo que ALMA ya usa— transfiere bien entre tareas
  relacionadas; no hay que cambiar el algoritmo, hay que darle el prior correcto.
- **Jerárquico bayesiano para bandits.** Wan, Ge y Song (2021, arXiv:2108.06422):
  metadata por tarea + modelo jerárquico + Thompson sampling meta; el Bayes regret
  demuestra el beneficio de compartir. Mensaje: (b) funciona cuando las tareas son
  genuinamente emparentadas; cuando no, el modelo lo tiene que detectar, no asumirlo.
- **Latent bandits no estacionarios.** Hong et al. (Google Research, 2020):
  prototipos offline + inferencia online del estado latente del usuario + posterior
  sampling. Mensaje: la arquitectura "global offline, personalización online" es la
  que usan los recomendadores en producción; es (b) con otro nombre.
- **Práctica de industria.** GrowthBook (docs, 2026): contextual bandits que
  particionan usuarios en hojas por contexto y corren Thompson **dentro de cada hoja**.
  Mensaje: una vía intermedia muy pragmática —no un global ni N loops aislados, sino
  clusters de usuarios similares que comparten aprendizaje. ALMA podría clusterizar por
  firma de régimen en vez de por usuario.

Conclusión de la literatura: nadie comparte datos crudos; todos comparten
**parámetros, posteriors o gradientes**. Y el consenso implícito es que la
heterogeneidad entre usuarios es el enemigo número uno —todos los métodos serios
incluyen algún mecanismo para no contaminar (shrinkage adaptativo, clustering,
detección de drift).

## 5. Recomendación para ALMA

**Recomiendo (a) federado como arquitectura objetivo, con (c) pool de experiencias
como primera fase, y (b) jerárquico descartado por ahora.**

El porqué, en criollo:

1. **(c) primero porque es lo más barato de probar y lo que más señal da.** El minero
   de debilidades es el componente que más se beneficia del volumen: un usuario solo
   rara vez genera suficientes fallos para minar una firma; cien usuarios sí. Y como
   la adopción sigue pasando por tu puerta de dos splits local, el riesgo de
   contaminación es casi nulo por construcción. Es aprendizaje compartido con
   freno local.
2. **(a) después, porque preserva la arquitectura actual.** El loop no cambia: solo
   el "prior warm" pasa a venir —en parte— del agregado federado en vez de solo del
   historial local. El olvido `0.5^días` ya implementa el desacoplamiento automático:
   tu experiencia pesa más que la del colectivo a medida que acumulás historial.
   Además es la única opción donde la privacidad es defendible de entrada (solo
   números agregados cruzan la red), lo que importa si el router se vende como
   producto.
3. **(b) no, por ahora.** El riesgo de contaminación es el más alto y es justo el
   modo de fallo que ALMA ya midió y teme (EXP68: en mundo heterogéneo el efecto es
   0,00 —y eso era con un detector a favor). Un jerárquico mal calibrado promedia
   usuarios distintos y degrada a todos en silencio. Recién tendría sentido cuando
   haya evidencia medida de que los usuarios del producto son homogéneos en la
   firma que importa (misma distribución de regímenes), y esa evidencia hoy no existe.

**Líneas rojas que se mantienen en cualquier diseño:** el núcleo es intocable —
los topes de gasto (key apagada por default, sin tope no gasta) y la obligación de
notificar cada evolución valen para el loop local, el agregador y el pool. Ningún
componente multiusuario puede silenciar avisos ni mover topes. Además: ningún
agregado sale del tenant sin consentimiento explícito del usuario (opt-in, no
opt-out), y el consentimiento se puede revocar —al revocarse, sus contribuciones
dejan de ponderar en el siguiente ciclo de agregación.

## 6. Roadmap por fases (solo diseño, sin fechas comprometidas)

**Fase M0 — Pool de experiencias (diseño + mock).**
Definir el schema de experiencia anonimizada `(firma_régimen, brazo, reward, costo,
timestamp)` y el protocolo de depósito/consulta. Validar en mock (US$0): simular
N usuarios sintéticos con heterogeneidad controlada y medir si el minero sobre el
pool encuentra firmas que el minero single-user no encuentra. Vara pre-registrada
antes de correr: el pool solo avanza si el minero multiusuario supera al
single-user en el mock. Sin fase con key: la pregunta es estadística, no de modelo.

**Fase M1 — Agregación federada de priors (diseño + mock).**
Protocolo: cada loop sube (α, β) por brazo/clase + hiperparámetros del scaffold;
el servidor agrega con media robusta (mediana por coordenada) y devuelve el prior
global; el loop local lo mezcla con peso `w_global` que decae con el historial propio
(el olvido hace el resto). Validar en mock: N usuarios, regímenes heterogéneos, medir
regret vs. loops aislados. Criterio de avance: mejora en cold start sin regresión en
usuarios maduros (el "no peor" de la regla de auto-adopción, aplicado al colectivo).

**Fase M2 — Endurecimiento.**
Differential privacy en los agregados (ruido calibrado a los conteos, con el costo
en regret medido y documentado —la literatura avisa que se paga); defensa contra
envenenamiento (agregación robusta + detección de contribuyentes anómalos);
consentimiento y revocación; auditoría de re-identificación del pool.

**Fase M3 — Re-evaluar (b).**
Solo si M0–M2 están en producción y hay evidencia medida de homogeneidad entre
usuarios (el detector de heterogeneidad reportando "mundo homogéneo" de forma
sostenida). Recién ahí diseñar el jerárquico, empezando por clustering por firma
de régimen (la vía GrowthBook: Thompson dentro de cada cluster) antes que un
jerárquico puro.

**Puertas entre fases:** cada fase avanza solo con veredicto PASS pre-registrado en
mock; ninguna fase toca el servicio vivo (puerto 8471) hasta que el diseño esté
cerrado y aprobado; y cualquier componente que mueva agregados entre tenants
requiere tu "sí" explícito antes de implementarse —el freno humano rige también
para el roadmap.

## 7. Preguntas abiertas (para decidir antes de M0)

1. ¿El producto es multi-tenant en un servidor nuestro, o instalaciones separadas
   por cliente? (Si es lo segundo, (a) federado es casi obligatorio; si es lo
   primero, (c) es trivial de operar.)
2. ¿Qué tan heterogéneos esperás que sean los usuarios del router? (Si cada cliente
   usa el router para dominios totalmente distintos, ni (a) ni (c) transfieren mucho
   y el diseño debería enfocarse en cold start, no en transferencia continua.)
3. ¿El consentimiento para compartir agregados es opt-in por defecto? (Recomendación:
   sí, opt-in explícito.)
