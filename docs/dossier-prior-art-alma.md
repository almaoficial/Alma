# Dossier: ¿ALMA ya existe?

**Fecha:** 25/9/2026. **Método:** búsqueda web amplia sobre papers (arXiv) y sistemas open-source, más verificación en vivo de los candidatos más cercanos. Parte de la descripción documentada de ALMA (ver `ORIGENES.md`) y del prototipo mínimo ya construido.

**Límite honesto de entrada:** no encontrar una coincidencia significa *no encontrada en las fuentes revisadas*, nunca prueba de novedad. El campo se mueve rápido: los candidatos más cercanos son de 2024–2025.

## Las 6 afirmaciones centrales de ALMA (la vara)

Cada candidato se puntúa 0 (no), 1 (parcial) o 2 (sí) contra estas seis:

1. **Selección por problema:** elige la *familia de arquitectura* según la clase de problema (no solo "modelo fuerte o débil").
2. **Memoria entre problemas:** guarda experiencias y con ellas actualiza el mapeo problema → arquitectura.
3. **Experimentador abierto:** puede inventar configuraciones fuera del repertorio conocido cuando nada funciona.
4. **Runtime continuo:** el ciclo corre en producción, problema tras problema (no es una búsqueda offline por benchmark).
5. **No-regresión:** al aprender algo nuevo no olvida ni rompe lo que ya funcionaba.
6. **Vara externa:** el evaluador se apoya en señales verificables, no en la auto-opinión del modelo.

## Tabla de puntajes (sobre 12)

| # | Candidato | 1 | 2 | 3 | 4 | 5 | 6 | Total | Fuente |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Darwin–Gödel Machine | 0 | 2 | 2 | 1 | 2 | 2 | **9** | [paper](https://arxiv.org/abs/2505.22954) |
| 2 | Voyager | 0 | 2 | 1 | 2 | 1 | 2 | **8** | [paper](https://arxiv.org/abs/2305.16291) |
| 3 | ADAS / Meta Agent Search | 0 | 1 | 2 | 0 | 1 | 2 | **6** | [paper](https://arxiv.org/abs/2408.08435) |
| 4 | AFlow | 0 | 1 | 1 | 0 | 0 | 2 | **4** | [paper](https://arxiv.org/abs/2410.10762) |
| 5 | Gödel Agent | 0 | 1 | 1 | 1 | 0 | 1 | **4** | [paper](https://arxiv.org/abs/2410.04444) |
| 6 | Absolute Zero | 0 | 0 | 1 | 1 | 0 | 2 | **4** | [paper](https://arxiv.org/abs/2505.03335) |
| 7 | Reflexion | 0 | 1 | 0 | 1 | 0 | 1 | **3** | [paper](https://arxiv.org/abs/2303.11366) |
| 8 | Archon | 0 | 0 | 1 | 0 | 0 | 2 | **3** | [paper](https://arxiv.org/abs/2409.15254) |
| 9 | GPTSwarm | 0 | 0 | 1 | 1 | 0 | 1 | **3** | [paper](https://arxiv.org/abs/2402.16823) |
| 10 | AI Scientist v2 | 0 | 1 | 0 | 1 | 0 | 1 | **3** | [paper](https://arxiv.org/abs/2504.08066) |
| 11 | DynaSwarm | 1 | 0 | 0 | 0 | 0 | 1 | **2** | [paper](https://arxiv.org/abs/2507.23261v1) ⚠️ |
| 12 | RouteLLM | 1 | 0 | 0 | 0 | 0 | 1 | **2** | [paper](https://arxiv.org/abs/2406.18510) |
| 13 | FrugalGPT | 1 | 0 | 0 | 0 | 0 | 1 | **2** | [paper](https://arxiv.org/abs/2305.05176) |
| 14 | DSPy | 0 | 0 | 0 | 0 | 0 | 2 | **2** | [paper](https://arxiv.org/abs/2310.03714) |

⚠️ **DynaSwarm:** en arXiv figura que una versión posterior del paper fue retirada por uno de sus autores. La v1 sigue consultable, pero el dato obliga a cautela: es el candidato conceptualmente más cercano a la afirmación 1 y a la vez el más frágil como fuente.

## Los 4 más cercanos, en detalle

### 1. Darwin–Gödel Machine (9/12) — el ciclo completo, sin selector por problema
Un agente de programación que **reescribe su propio código** y valida cada cambio contra benchmarks reales de coding, con un **archivo abierto** de variantes (si una modificación es mala, no envenena la línea: la ablación del paper muestra que sin archivo abierto la evolución colapsa). Pasó SWE-bench de 20% a 50% solo. Es el único sistema publicado con el loop experiencia → modificación → evaluación → nueva experiencia funcionando de verdad.
**Qué le falta para ALMA:** no elige arquitectura según el problema entrante — hay un único agente que se muta a sí mismo, offline, para un dominio (coding). No hay taxonomía de problemas ni política de selección.
[Sakana AI](https://sakana.ai/dgm/) · [código](https://github.com/jennyzzt/dgm)

### 2. Voyager (8/12) — memoria continua, arquitectura fija
Agente en Minecraft con **currículum automático** y una **biblioteca creciente de habilidades verificadas** (código que funciona y se reutiliza). Es el mejor precedente de "aprender entre problemas sin estancarse".
**Qué le falta para ALMA:** lo que aprende son habilidades, no arquitecturas; la arquitectura del agente nunca cambia.
[paper](https://arxiv.org/abs/2305.16291)

### 3. ADAS / Meta Agent Search (6/12) — el "meta" que inventa agentes
Un **meta-agente programa agentes nuevos en código** a partir de un archivo de descubrimientos previos; los agentes descubiertos superan a los diseñados a mano y transfieren entre dominios. ICLR 2025.
**Qué le falta para ALMA:** optimiza *un* diseño por dominio, *offline*. El meta-agente mejora al sistema objetivo, no a sí mismo, y en producción no hay selección por problema.
[paper](https://arxiv.org/abs/2408.08435)

### 4. DynaSwarm (2/12 pero clave) — lo único que selecciona por muestra
Ataca exactamente "una sola arquitectura no sirve para todos los inputs": optimiza grafos de agentes con A2C y un **selector que elige el grafo por muestra de entrada** (ablación: sin selector cae el rendimiento). Es la existencia publicada más próxima a la afirmación 1 de ALMA.
**Qué le falta para ALMA:** el espacio son topologías de *un* multi-agente fijo, el selector se entrena offline por benchmark, y no hay memoria entre problemas ni invención fuera del espacio. Más la cautela de la versión retirada.
[paper](https://arxiv.org/abs/2507.23261v1) · [código](https://github.com/yuki-2025/dynaswarm)

## El resto, en una línea cada uno

- **AFlow / Archon:** buscan el mejor workflow *para un benchmark*, offline. Encuentran *la* arquitectura, no una política de selección.
- **Gödel Agent:** se auto-modifica en runtime, pero solo fragmentos chicos de su lógica; no elige entre familias arquitectónicas.
- **Absolute Zero:** proposer + solver con ejecutor de código como verificador; el loop auto-supervisado existe, pero sin memoria de mapeo problema → arquitectura.
- **Reflexion:** intentar → evaluar → reflexionar en lenguaje → reintentar, con memoria episódica *dentro* de una tarea. La extensión "entre tareas" es natural pero no publicada como sistema.
- **RouteLLM / FrugalGPT:** routing por query, pero solo entre modelo fuerte/débil o en cascada por dificultad. No tocan arquitectura multi-agente.
- **DSPy:** optimiza prompts dentro de una estructura fija escrita por un humano; no inventa topologías.
- **GPTSwarm:** el formalismo (agentes como grafos optimizables) que ALMA necesitaría para representar su espacio de arquitecturas — pero sin selector por clase de problema.
- **AI Scientist v2:** loop cerrado de investigación con arquitectura fija diseñada a mano. Es el tipo de sistema que ALMA querría *elegir*, no un competidor.

## Veredicto

**ALMA como sistema integrado no existe.** Ningún paper ni repo público combina las seis afirmaciones.

Desglose honesto del concepto:
- **~70% ya publicado:** routing (RouteLLM, FrugalGPT), reflexión con memoria (Reflexion), optimización de prompts (DSPy), búsqueda de diseños agénticos (ADAS, AFlow, Archon), grafos optimizables (GPTSwarm), auto-modificación con validación empírica (Darwin–Gödel Machine), memoria continua de habilidades (Voyager).
- **~20% extensión natural no publicada:** pegar esas piezas en un solo runtime — un orquestador con selector por problema + ejecutores heterogéneos + evaluador con verificadores + memoria persistente entre problemas + experimentador. Ingeniería de sistemas seria, pero cada flecha del diagrama ya tiene paper.
- **~10% problema abierto genuino:** (a) evaluación no hackeable del propio evaluador — que el sistema no aprenda a engañar su vara; (b) descubrimiento automático de *clases* de problema (¿quién define la taxonomía?); (c) experimentación en producción sin degradar lo que ya funciona.

**Lo que sí parece genuinamente nuevo, formulado con rigor:** aprender, en runtime y de forma persistente entre problemas, una **política de selección π(clase de problema) → familia arquitectónica** — no una arquitectura ganadora, no una mutación del propio código — con un operador de **expansión del espacio** (inventar familias nuevas) gobernado por **no-regresión**. En la literatura revisada no hay un trabajo que formule y evalúe exactamente ese objeto. DynaSwarm es lo más cercano y se queda corto en cuatro de las seis afirmaciones.

**Incertidumbre declarada:** la búsqueda cubrió papers indexados en arXiv y repos open-source accesibles vía web al 25/9/2026. Laboratorios privados (DeepMind, OpenAI, Anthropic, Meta) pueden tener sistemas internos equivalentes sin publicar. La ausencia de coincidencia no es prueba de novedad: es "no encontrado".
