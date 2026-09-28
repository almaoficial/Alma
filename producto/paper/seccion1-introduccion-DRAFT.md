# SECCIÓN 1 — Introducción (DRAFT)

> **ESTADO: DRAFT — NO PUBLICAR.** Borrador de trabajo, pendiente de la revisión
> del autor contra la lista de puntos no publicables antes de cualquier salida.
> Fecha del draft: 2026-09-28 · Costo: US$0 · Contacto con terceros: ninguno.

**Título de trabajo:** *ALMA: un loop adaptativo chico que aprende qué modo usar —
evidencia a favor y en contra*

---

## 1. Introducción

### El problema

Usar un modelo de lenguaje cuesta. No solo dinero: cuesta en tiempo, en cómputo y
en respuestas que llegan mal o tarde. Y la mayoría de los modelos modernos no
tienen una sola forma de responder: tienen modos. Pedirle una respuesta directa
es barato y rápido. Pedirle que razone paso a paso (`chain-of-thought`) cuesta
más. Pedirle que razone a fondo con esfuerzo máximo (`reflexión` o pensamiento
profundo) cuesta muchísimo más — en nuestras mediciones, el modo de razonamiento
profundo llega a salir entre 10 y 40 veces más caro por llamada que la respuesta
directa, por una ganancia de calidad que muchas veces es marginal.

El problema es que el modo correcto depende del problema. En nuestras mediciones
sobre 180 problemas de tres benchmarks estándar, el modo con razonamiento
paso a paso resolvió el 96,7% de los problemas de matemática (GSM8K), mientras que
la respuesta directa solo resolvió el 63,3%. Pero en preguntas de conocimiento
general (MMLU) la respuesta directa ganó con 91,7%, y en programación (MBPP)
también ganó la respuesta directa — aunque ahí todos los modos anduvieron mal
(entre 5% y 11% de éxito). No hay un modo ganador universal. Hay un modo ganador
*por tipo de tarea*.

Entonces la pregunta práctica es esta: ¿cómo elegir el modo correcto para cada
tipo de problema sin pagar de más por averiguarlo? Si elegís fijo, perdés donde
el fijo no es el mejor. Si probás todo el tiempo, el costo de probar se come la
ventaja. Esa tensión — entre elegir bien y pagar poco por aprender a elegir —
es el problema que ataca este trabajo.

### La idea

ALMA nació como idea en julio de 2025: en vez de decidir el modo a mano, o con
reglas fijas escritas por un humano, construir un *loop* chico que aprenda solo
qué modo usar según el tipo de problema que tiene enfrente. No un modelo nuevo.
No una plataforma. Una capa de decisión delgada, que se puede meter entre
cualquier aplicación y cualquier proveedor de modelos, y que decide — problema
por problema — qué modo conviene.

La idea se puso a prueba en una serie experimental intensiva durante septiembre
de 2026: más de 70 experimentos, cada uno con la vara escrita *antes* de correr
(pre-registro), incluyendo deliberadamente experimentos diseñados para romper la
tesis. Este paper cuenta lo que salió bien y lo que salió mal, con el mismo peso.

### Qué es ALMA, en palabras llanas

ALMA es un loop de seis piezas. Cada pieza se puede explicar en una frase:

1. **El probe (la sonda).** Cada tanto, en vez de usar lo que ya se sabe, el
   sistema prueba los modos lado a lado en un puñado de problemas y mide cuál
   anda mejor *para ese tipo de problema*. Es caro, pero es la única forma de
   enterarse cuando el mundo cambió.
2. **El skip.** Si el sistema ya sabe con confianza qué modo gana en este tipo
   de problema, se salta la sonda y usa lo que sabe. No re-testea por deporte.
3. **Thompson sampling con prior condicionado.** Entre sonda y sonda, la elección
   de modo no es a ciegas ni es rígida: es una apuesta probabilística que se
   apoya en lo medido hasta ahora para cada tipo de problema, explorando más
   donde hay más duda y explotando donde hay más certeza.
4. **Memoria con olvido.** Lo reciente pesa más que lo viejo, con un decaimiento
   explícito (la mitad de peso cada día). Si el mundo cambia, el sistema lo sigue
   sin que nadie le avise.
5. **La puerta de dos splits.** Ninguna mejora se adopta porque "parece mejor":
   tiene que medir mejor en datos que el sistema nunca vio, dos veces, antes de
   entrar. Es la diferencia entre una corazonada y una evidencia.
6. **La auto-adopción gobernada.** Cuando una mejora pasa la puerta, el sistema
   la adopta solo y avisa qué cambió y con qué efecto medido. Pero hay un núcleo
   intocable: los topes de gasto, las reglas de validación y la obligación de
   notificar no los puede tocar ni el propio loop. El sistema se mejora a sí
   mismo, pero no peor — solo ante mejora medida — y nunca en silencio.

Ninguna de estas piezas es nueva por separado. Lo que se evalúa acá es la
combinación — chica, embebible, barata de correr — y la disciplina con la que
se valida cada cambio.

### Las preguntas que responde este paper

Este trabajo se organiza alrededor de cinco preguntas, cada una con un
experimento (o una serie) diseñado para contestarla — o para refutarla:

1. **¿El loop le gana a la mejor política fija?** Es la pregunta madre. La
   respuesta es sí, pero condicional: en un mundo heterogéneo — donde distintos
   tipos de problema premian distintos modos — el loop completo logró un regret
   total de 3,445 contra 10,945 de la mejor política fija y 10,995 de un
   aprendiz global sin estructura por tipo de problema (EXP67, 180 problemas
   frescos de GSM8K, MMLU y MBPP, primera evidencia fuera del mundo sintético).
2. **¿La ventaja es del loop o del mundo?** En un mundo homogéneo — donde un
   solo modo gana en casi todo — el loop *pierde*: 4,82 contra −0,03 de la
   política fija obvia, con la sonda acertando 10 de 10 bloques pero sin nada
   que explotar (EXP62). La ventaja de ALMA es condicional a la heterogeneidad
   del mundo, no una propiedad intrínseca del loop. Ese FAIL es tan importante
   como el PASS anterior: dibuja el techo.
3. **¿Cuánto cuesta aprender?** Explorar tiene precio. Cuando la ventaja entre
   modos es chica y ruidosa, el costo de la sonda supera el beneficio — el loop
   elige bien el modo correcto en 9 de 10 bloques y aun así pierde (EXP18). Y
   quitar la pieza que evita re-testear (el skip) empeora el resultado en +6,55
   de regret en promedio (EXP64): el skip no es decoración, carga peso.
4. **¿Se puede elegir proveedor con la misma lógica?** Un router que elige
   proveedor por rendimiento medido por dólar (no por precio del token) eligió
   al ganador ex post en 3 de 3 segmentos y generalizó a datos nunca vistos
   (EXP69). La idea se aplica a modos y a proveedores por igual.
5. **¿Cómo se gobierna un sistema que se modifica solo?** La propuesta de este
   trabajo: auto-adopción solo ante mejora medida, notificación de cada cambio,
   y un núcleo de reglas fuera del alcance del propio loop. La gobernanza no es
   un apéndice ético: es parte del diseño y se evalúa como tal.

### Cómo leer este paper

La metodología es parte del aporte, no un adorno. Tres reglas rigieron toda la
serie y se pueden copiar sin copiar el sistema: **pre-registro** (la vara se
escribe antes de gastar, y los FAILs se aceptan sin moverla); **mock-first**
(ningún gasto en una pregunta que el simulador gratis ya respondió — en un caso,
US$0,08 aprobados quedaron en US$0,00 gastados porque la simulación refutó el
fix antes de tocar la API); y **refutación primero** (varios experimentos existen
para intentar romper la tesis, no para confirmarla).

Los resultados se reportan con los FAILs al mismo peso visual que los PASS,
porque son la mitad del valor: lo que la serie refutó — el techo de la
homogeneidad, el costo de explorar, los límites de la auto-mejora — es lo que
distingue este informe de un publirreportaje. Si al final de la lectura el
autor no quedó incómodo en al menos un párrafo, el paper está endulzado; la
sección de discusión (§7) existe para que eso no pase.

El resto del paper: §2 ubica el trabajo frente a lo existente (bandits,
Thompson sampling, agentes que se mejoran solos); §3 describe el método en alto
nivel; §4 detalla el diseño experimental; §5 reporta los resultados experimento
por experimento; §6 discute lo que la serie refutó; §7 propone la gobernanza de
la auto-mejora como diseño; §8 lista el trabajo futuro; §9 declara
reproducibilidad y límites — incluyendo lo que este paper explícitamente *no*
afirma.

---

*[VERIFICAR: ninguno pendiente — todos los números del draft salen de veredictos
en disco: EXP67 `integracion_fase21/resultados/exp67-benchmark-real-20260927/veredicto.md`,
EXP62 `resultados/exp62_veredicto.md`, EXP18 (seed 1824, memoria del 27/9),
EXP64-skip `integracion_fase21/resultados/exp64-ablacion-skip-20260928/veredicto.md`,
EXP69 (memoria del 27/9), EXP66 `integracion_fase21/resultados/exp66-minero-20260927/veredicto.md`.
El perfil del oráculo (gsm8k/mmlu/mbpp) sale del veredicto de EXP67.]*
