# ALMA — aprender cómo los agentes se equivocan menos

**Un sistema que se mejora a sí mismo bajo gobernanza medida: evaluador barato, puerta que rechaza lo que no mejora, y un humano en el núcleo.**

Por **Alejandro Nahuel Salusso** — Miami Beach. En construcción desde septiembre de 2026; la idea nació en julio de 2025.

---

## La tesis

> El hombre controla a la IA y el resultado siempre termina dependiendo del hombre: por eso mi lugar no es el modelo, es construir el instrumento que evalúa barato qué configuración de inteligencia necesita cada problema.
>
> ALMA aprende de ALMA: aprende de sus experiencias, y solo adopta lo que mide mejor — nunca peor.
>
> Y cuando eso me funcione a mí, dejo de construir ideas para mí y empiezo a hacer para los demás lo mismo que me funcionó, mejorándolo día a día.

ALMA no es un enjambre de agentes — los enjambres ya son commodity (hay repositorios gratuitos con 280 agentes-persona y 154.000 estrellas). ALMA es un **meta-loop con gobernanza**: un sistema que propone cambios sobre sí mismo, los valida empíricamente contra un validador congelado, y solo adopta los que miden mejor. El error, medido, es la señal de aprendizaje.

## El arco (todo con fecha, todo chequeable)

Este proyecto no nació como ingeniería. Nació como casi todas las ideas con IA en 2025: pensamiento mágico. Lo dejo escrito porque la distancia entre ese origen y este repositorio *es* la tesis.

| Fecha | Hito |
|---|---|
| 18/7/2025 | Primera imagen de la colección de NFTs «Yo Soy ALMA» — ALMA era un «sistema de activación económica», modo «Reactor Turing», metas de ingreso por Zelle y cripto |
| 19/7/2025 | Conversación de origen con ChatGPT: «Lanzar sistema ALMA TOTAL – Activación por un solo clic» |
| 27/7/2025 | Se crea esta cuenta de GitHub (almaoficial) |
| 22/9/2025 | La definición madura, todavía en ChatGPT: **«ALMA aprende de ALMA»** — arquitectura auto-mejorable con ciclo Experiencia → evaluación → aprender sobre el sistema → modificar la arquitectura → nueva experiencia, e hipótesis formal A(t+1) = F(P(t), S(t), R(t), E(t), M(t)) |
| 23/9/2026 | Decisión de construirlo de verdad. Estudio de prior art primero (refutación antes que entusiasmo): ningún agente en producción se rediseñaba su arquitectura |
| 25–27/9/2026 | EXP1–9 pre-registrados: 5 PASS / 4 FAIL. El loop valida en márgenes finos. Fases 0–2 construidas con tests |
| 1/10/2026 | EXP76 PASS — puerta de handoff para skills (interfaz clara Δ +0,3636 adoptada; rígida −0,4145 rechazada). EXP77: auditoría 7/7 sin bloat |
| 8–9/10/2026 | Evaluador barato medido sobre 30 casos: heurística 17/30 · modelo gratuito 0/30 (reportado tal cual) · **Mistral Nemo 28/30 (0,933) por <US$0,001** — cableado como juez por defecto |
| 10/10/2026 | Nace el **ledger de afirmaciones**: cada afirmación del sistema sobre su dueño lleva fuente y fecha y se audita |
| 11/10/2026 | Primera auditoría del ledger: **8/8 confirmadas**. Verificador «fallas que parecen éxitos» operativo: 35 éxitos declarados, 35 confirmados, **0 fallas**. **Piso de ruido δ = 0,53 cableado en la puerta de auto-adopción** |
| 12/10/2026 | Pre-registro del detector de deriva de skills. Este repositorio |

## Cómo trabaja — las cinco piezas

1. **Evaluador barato como primer filtro.** Generar es casi gratis; verificar con humanos cuesta 46× lo que cuesta generar (medición 2026 con tarifas reales). Un juez barato que caza *forma* (no verdad fina — esa es su frontera honesta) poda casi todo lo malo por casi nada, y la verificación cara se hace sobre 10 candidatos, no sobre 1.000. Es la técnica *generate-prune-then-rank* aplicada como gobernanza.
2. **Puerta de dos splits con piso de ruido.** Cada cambio candidato se evalúa en dos conjuntos independientes contra un validador congelado. La auto-adopción exige efecto positivo en ambos **y** mayor que el piso de ruido medido del propio sistema (δ = 0,53): `max(Δ_in, Δ_ho) > 0,53`. Lo que cae en la banda (0, 0,53] no se adopta solo — espera aprobación humana. Sin piso, el sistema persigue ruido y lo llama progreso.
3. **El humano en el núcleo, fuera del alcance del loop.** El meta-loop auto-adopta mejoras medidas y avisa cada evolución. Pero no puede tocar dos cosas: los **topes de gasto** y su **obligación de avisar**. Si pudiera silenciar los avisos, el «avísame» no valdría nada.
4. **Pre-registro antes de cada experimento.** Qué se espera, qué contaría como raro y qué resultado cambiaría el veredicto — escrito *antes* de correr. Sin pre-registro, cualquier resultado se narra como éxito. (Ver `preregistros/`.)
5. **Verificador de «fallas que parecen éxitos».** La falla cara de un agente no es la que explota: es la que *dice* que hizo algo y no lo hizo. El verificador confronta lo declarado contra lo real, corrida por corrida, y el ledger de afirmaciones audita lo que el sistema afirma sobre su dueño.

## Estado honesto

Lo que este repositorio prueba: los instrumentos funcionan y están medidos (tests en verde; auditorías 8/8 y 35/35).

Lo que todavía **no** prueba, y lo digo en el README porque es el punto: **el meta-loop suma cero adopciones con mejora medida por encima del piso de ruido.** La Darwin-Gödel Machine publica SWE-bench 20% → 50%; ALMA, por ahora, publica que su laboratorio no se miente. La próxima frontera es una sola: una adopción con delta medido. Cuando ocurra, va a estar en este repositorio, con su pre-registro y su medición.

## Estructura

- `alma_service/` — el sistema: meta-loop (`metaloop.py`), puerta (`gate.py`), evaluador y juez baratos, verificador, handoff de skills, manifiesto de confianza, detector de deriva, presupuesto con topes.
- `test_*.py` — las suites de gobernanza: auto-adopción, piso de ruido, freno humano, manifiesto y loader, auditorías EXP76–81.
- `docs/` — diseño del sistema real, fases 0–2, spec v2, informe completo del proyecto y dossier de prior art.
- `preregistros/` — los pre-registros del meta-loop en JSON (EXP76, EXP77, crossover, piso de ruido).
- `experimentos/` — corridas clave (EXP71, EXP76, EXP77) y el ledger del meta-loop con cadena de hashes.

## Licencia

© 2026 Alejandro Nahuel Salusso (ALMA Labs LLC, en formación). Todos los derechos reservados — ver `LICENSE`. El código está publicado para ser leído, estudiado y verificado; esa es su función.
