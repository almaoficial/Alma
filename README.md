# ALMA — how agents learn to fail less

**Your agents report success they didn't achieve. ALMA is the instrument that checks.**
A self-improving agent system under measured governance: a cheap evaluator as first filter, an adoption gate that rejects anything that doesn't beat measured noise, a verifier that confronts what agents *declare* against what *actually happened* — and a human the loop cannot overrule.

By **Alejandro Nahuel Salusso** — Miami Beach, FL. Building since September 2026; the idea dates to July 2025. *(Versión en español más abajo.)*

---

## What works today (measured, not promised)

**1. A verifier for "failures that look like successes."**
The expensive failure of an agent is not the one that crashes — it's the one that *says* it did the work and didn't. The verifier audits declared outcomes against real evidence, run by run. First full audit of ALMA itself: **35 declared successes, 35 confirmed, 0 false passes.**

**2. A cheap evaluator as the first verification filter.**
Generating is nearly free; human verification costs ~46× generation (measured 2026 at real rates). A calibrated low-cost judge prunes almost everything bad for almost nothing, so expensive judgment is spent on 10 candidates, not 1,000. Measured on a 30-case battery: heuristic 17/30 · a free model 0/30 (reported as-is) · **Mistral Nemo 28/30 (0.933) at under US$0.001 per run** — now wired in as the default judge. Its honest frontier: it catches *form*, not fine factual error.

**3. An adoption gate with a measured noise floor.**
Every self-modification is evaluated on two independent splits against a frozen validator. Auto-adoption requires a positive effect on both **and** an effect larger than the system's own measured noise floor: `max(Δ_in, Δ_ho) > δ`, with **δ = 0.53**. Anything inside the band (0, 0.53] is not adopted — it waits for a human. Without a floor, a self-improving system chases noise and calls it progress.

## Run the demo (2 minutes)

A miniature of the verifier, self-contained — no dependencies, no API keys, no network:

```bash
python3 demo/verify_demo.py
```

An agent declared six outcomes at the end of a run. The script trusts none of them and checks the evidence. Real output:

```
ALMA verifier — declared vs. actual
==============================================================
[VERIFIED      ] #1 Wrote the summary report to report.md
               evidence: report.md exists, 118 bytes
[FALSE SUCCESS ] #2 All 30 battery tests passed
               evidence: declared 30 PASS, log actually contains 19
[VERIFIED      ] #3 Exported 12 result rows to results.csv
               evidence: declared 12 rows, file actually has 12
[FALSE SUCCESS ] #4 Sent the confirmation email
               evidence: email_receipt.txt DOES NOT exist
[FALSE SUCCESS ] #5 Downloaded the dataset (dataset.json)
               evidence: dataset.json exists, 0 bytes
[VERIFIED      ] #6 Final metrics computed in metrics.json
               evidence: key 'accuracy' present in metrics.json
==============================================================
Declared: 6 · Confirmed: 3 · False successes caught: 3
```

The run *reported* success. The evidence disagreed in 3 of 6 claims. That gap is the whole point.

## Verify it yourself

The demo above runs anywhere. The governance suites are standalone scripts (no pytest, no network, no keys):

```bash
for f in test_*.py; do python3 "$f"; done
```

Verified from a fresh clone on 2026-10-16: **22 of 43 suites pass standalone.** The rest import the historical experiment runners (`run_experiment47/49/56`) and the original `alma` package, which are not yet part of this export. That gap is stated here rather than hidden — closing it is export work, not science. The audits cited above (8/8, 35/35, 28/30) were run against the full local system and their records live in `experimentos/` and `preregistros/`.

## How it works — the five pieces

1. **Cheap evaluator first.** Generate–prune–then–rank, applied as governance: the cheap judge filters, the expensive one decides.
2. **Two-split gate with a noise floor.** Described above: no adoption below measured noise, ever — "better, never worse" is enforced by measurement, not intention.
3. **The human stays outside the loop's reach.** The meta-loop auto-adopts measured improvements and reports every evolution — but it cannot touch two things: the **spending caps** and its **duty to notify**. If it could silence its own reports, the reports would be worthless.
4. **Pre-registration before every experiment.** What is expected, what would count as strange, and what result would change the verdict — written *before* running. Without it, any outcome can be narrated as success. (See `preregistros/`.)
5. **The claims ledger.** Every assertion the system makes about its owner carries a source and a date, and gets audited. First ledger audit: 8/8 confirmed.

## The arc (dated, checkable)

This project did not start as engineering. It started the way almost every 2025 AI idea started: magical thinking. It stays in this README because the distance between that origin and this repository *is* the thesis.

| Date | Milestone |
|---|---|
| 18 Jul 2025 | First image of the «Yo Soy ALMA» NFT collection — ALMA was an "economic activation system", "Reactor Turing" mode, income goals via Zelle and crypto |
| 19 Jul 2025 | Origin conversation with ChatGPT: "Launch ALMA TOTAL system – one-click activation" |
| 27 Jul 2025 | This GitHub account (almaoficial) is created |
| 22 Sep 2025 | The mature definition, still in ChatGPT: **"ALMA learns from ALMA"** — self-improving architecture with an Experience → evaluation → learn about the system → modify the architecture → new experience cycle, and a formal hypothesis A(t+1) = F(P(t), S(t), R(t), E(t), M(t)) |
| 23 Sep 2026 | Decision to actually build it. Prior-art study first (refutation before enthusiasm): no production agent redesigned its own architecture |
| 25–27 Sep 2026 | EXP1–9 pre-registered: 5 PASS / 4 FAIL. The loop validates in fine margins. Phases 0–2 built with tests |
| 1 Oct 2026 | EXP76 PASS — skill handoff gate (clear interface Δ +0.3636 adopted; rigid −0.4145 rejected). EXP77: audit 7/7, no bloat |
| 8–9 Oct 2026 | Cheap evaluator measured on 30 cases (numbers above); wired in as default judge |
| 10 Oct 2026 | The claims ledger is born: every assertion carries source and date |
| 11 Oct 2026 | First ledger audit: **8/8 confirmed**. "Failures that look like successes" verifier operational: 35 declared, 35 confirmed, **0 failures**. **Noise floor δ = 0.53 wired into the auto-adoption gate** |
| 12 Oct 2026 | Skill-drift detector pre-registered. This repository |

## Honest state

What this repository proves: the instruments work and are measured (audits 8/8 and 35/35; test-suite status in "Verify it yourself" above).

What it does **not** prove yet — stated here because it is the point: **the meta-loop has zero adoptions with a measured improvement above its noise floor.** The Darwin-Gödel Machine publishes SWE-bench 20% → 50%; ALMA, so far, publishes that its laboratory does not lie to itself. The next frontier is exactly one event: a single adoption with a measured delta. When it happens, it will be in this repository, with its pre-registration and its measurement.

## Structure

- `alma_service/` — the system: meta-loop (`metaloop.py`), gate (`gate.py`), cheap evaluator and judge, verifier, skill handoff, trust manifest, drift detector, budgeted spending caps.
- `demo/` — the 2-minute verifier demo above, with its sample run.
- `test_*.py` — the governance suites: auto-adoption, noise floor, human brake, manifest and loader, EXP76–81 audits.
- `docs/` — real system design, phases 0–2, v2 spec, full project report, prior-art dossier.
- `preregistros/` — the meta-loop's pre-registrations in JSON (EXP76, EXP77, crossover, noise floor).
- `experimentos/` — key runs (EXP71, EXP76, EXP77) and the meta-loop ledger with its hash chain.

## License

© 2026 Alejandro Nahuel Salusso (ALMA Labs LLC, in formation). All rights reserved — see `LICENSE`. The code is published to be read, studied and verified; that is its function.

---

# Versión en español

# ALMA — aprender cómo los agentes se equivocan menos

**Un sistema que se mejora a sí mismo bajo gobernanza medida: evaluador barato, puerta que rechaza lo que no mejora, y un humano en el núcleo.**

Por **Alejandro Nahuel Salusso** — Miami Beach. En construcción desde septiembre de 2026; la idea nació en julio de 2025.

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

Lo que este repositorio prueba: los instrumentos funcionan y están medidos (auditorías 8/8 y 35/35; el estado verificado de los tests está en «Verify it yourself», arriba: 22 de 43 suites corren desde un clon limpio, el resto importa los runners históricos de experimentos que aún no forman parte de esta exportación).

Lo que todavía **no** prueba, y lo digo en el README porque es el punto: **el meta-loop suma cero adopciones con mejora medida por encima del piso de ruido.** La Darwin-Gödel Machine publica SWE-bench 20% → 50%; ALMA, por ahora, publica que su laboratorio no se miente. La próxima frontera es una sola: una adopción con delta medido. Cuando ocurra, va a estar en este repositorio, con su pre-registro y su medición.

## Estructura

- `alma_service/` — el sistema: meta-loop (`metaloop.py`), puerta (`gate.py`), evaluador y juez baratos, verificador, handoff de skills, manifiesto de confianza, detector de deriva, presupuesto con topes.
- `demo/` — la demo de 2 minutos del verificador, con su corrida de ejemplo.
- `test_*.py` — las suites de gobernanza: auto-adopción, piso de ruido, freno humano, manifiesto y loader, auditorías EXP76–81.
- `docs/` — diseño del sistema real, fases 0–2, spec v2, informe completo del proyecto y dossier de prior art.
- `preregistros/` — los pre-registros del meta-loop en JSON (EXP76, EXP77, crossover, piso de ruido).
- `experimentos/` — corridas clave (EXP71, EXP76, EXP77) y el ledger del meta-loop con cadena de hashes.

## Licencia

© 2026 Alejandro Nahuel Salusso (ALMA Labs LLC, en formación). Todos los derechos reservados — ver `LICENSE`. El código está publicado para ser leído, estudiado y verificado; esa es su función.
