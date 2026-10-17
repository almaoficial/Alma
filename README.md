# ALMA — how agents learn to fail less

**Your agents report success they didn't achieve. ALMA is the instrument that checks.**
A self-improving agent system under measured governance: a cheap evaluator as first filter, an adoption gate that rejects anything that doesn't beat measured noise, a verifier that confronts what agents *declare* against what *actually happened* — and a human the loop cannot overrule.

By **Alejandro Nahuel Salusso** — Miami Beach, FL. Building since September 2026; the idea dates to July 2025. *(Versión en español más abajo.)*

*Name note: this ALMA — in development since July 2025 — is unrelated to the academic framework "ALMA: Automated meta-Learning of Memory designs for Agentic systems" (Xiong, Hu & Clune, arXiv:2602.07755, February 2026). Same acronym, different projects.*

---

## What works today (measured, not promised)

**1. A verifier for "failures that look like successes."**
The expensive failure of an agent is not the one that crashes — it's the one that *says* it did the work and didn't. The verifier audits declared outcomes against real evidence, run by run. First full audit of ALMA itself: **35 declared successes, 35 confirmed, 0 false passes.**

**2. A cheap evaluator as the first verification filter.**
Generating is nearly free; human verification costs ~46× generation (measured 2026 at real rates). A calibrated low-cost judge prunes almost everything bad for almost nothing, so expensive judgment is spent on 10 candidates, not 1,000. Measured on a 30-case battery: heuristic 17/30 · a free model 0/30 (reported as-is) · **Mistral Nemo 28/30 (0.933) at under US$0.001 per run** — now wired in as the default judge. Its honest frontier: it catches *form*, not fine factual error.

**3. An adoption gate with a measured noise floor.**
Every self-modification is evaluated on two independent splits against a frozen validator. Auto-adoption requires a positive effect on both **and** an effect larger than the system's own measured noise floor: `max(Δ_in, Δ_ho) > δ`. The floor is recalibrated only under pre-registration, and it has moved — always downward, always by measurement, never by convenience: **δ = 0.53** (2026-09-30) → **0.2283** (2026-10-16, recalibration v3 adopted) → **0.1141** (2026-10-16, large-panel cycle L1). The gate compares in totals, so the value wired today in `alma_service/gate.py` is `PISO_RUIDO_DELTA = 2.7391` totals ≡ 0.1141 × 24 (see "How each number was measured"). Anything inside the band (0, δ] is not adopted — it waits for a human. Without a floor, a self-improving system chases noise and calls it progress.

## How each number was measured

Every headline number above, with its method, its n, its date — and its stated limit.

- **Noise floor δ — the full arc.** First calibrated on 2026-09-30 (experiment EXP-piso-ruido): block bootstrap (B = 2000, z = 2.0) over repeated validator runs of an *unchanged* system, measuring how much "improvement" pure measurement fluctuation produces on its own. Result: 0.5331, rounded to 0.53 and wired into `alma_service/gate.py` as `PISO_RUIDO_DELTA = 0.53`. On 2026-10-16 the floor was recalibrated under its own pre-registration (`preregistros/preregistro-recalibracion-delta-v3-2026-10-16.md`; v1 and v2 were archived by their own rules — scale mixing, mis-specified validation): **δ = 0.2283 adopted and frozen**, panel 18/12, and the gate was rewired to compare in the scale it always actually computed in — totals: 0.2283 × 24 = 5.4781. That same night, cycle L1 (large panel 72/48, blind third split of 24) recalibrated again by its pre-registered design: **δ = 0.1141**, wired as **2.7391 totals**, which is the floor in the code today.
- **Verifier audit 35/35.** Run on 2026-10-11 over the window 2026-09-27 → 2026-10-10, at US$0 cost. Method: every declared success was confronted against the actual files and logs — 13 daily-routine runs, 8 English-practice runs (7 confirmed directly in the scorecard table, plus 1 first flagged as missing and resolved during the same audit as a timezone labeling issue), 13 study runs, 1 evaluator run. 35 declared, 35 confirmed, 0 false passes. What this audit does **not** measure: honest reports are not system improvement — the scorecard itself says so; improvement is the meta-loop's instrument (next bullets). The audit now runs monthly.
- **Cheap evaluator 28/30.** One 30-case battery; three candidate judges scored on the *same* 30 cases: heuristic 17/30 · free model 0/30 · Mistral Nemo 28/30 (0.933) at under US$0.001 per run. The battery was used to **select** the judge — not to train or tune it. Declared limitation: there is **no independent holdout set yet**; a held-out replication is stated future work, not a result.
- **Meta-loop adoptions: 0.** As of this writing, the number of self-modifications adopted with a measured improvement above δ is zero. That is the honest state this repository is organized around — see "October 16–17" and "Honest state" below, where the search that produced this zero is documented in full.

## October 16–17: the gate was made passable — and the search certified a null

The full narrative is in [`RESULTS-2026-10-16.md`](RESULTS-2026-10-16.md); every step below has its pre-registration in `preregistros/` and its report in `resultados/`, with run data under `data_*/`.

- **The gate was repaired first.** Recalibration v3 (adopted, frozen): δ 0.53 → 0.2283, and the rewiring of `gate.py` to the totals scale (5.4781) the comparison had always lived in.
- **Three searches against the new gate — all partial signal, zero adoptions.** (1) RSO mutations: 8 rounds, every candidate ≤ 0 on train. (2) A Sakana-style LLM candidate generator (`alma_service/generador_candidatos.py`): after two attempts blocked by the free tier (HTTP 429, reported as blocked, not failed), one real run with Mistral Nemo at a real cost of **US$0.0001774** produced 11/14 valid candidates; the best reached +0.0556 on train (1.0% of the gate) and reversed on held-out (−0.7500) — rejected. (3) Crossover over that batch (`alma_service/crossover.py`): 24 children, 6 positive on train — the best hit rate of any search — finalist +1.4444 on train, −3.0833 on held-out — rejected. The stall brake reached 3/3, by design.
- **The diagnosis (§9 review).** The pattern — wins on train, reversals on held-out — was measured three ways (split-half, jackknife, and a declared diagnostic spend of the held-out set): the "train positives" were **selected noise**. Certifying an effect of +1.44 at 2 standard errors needs ~65 replicates; the selection panel had 18. The bottleneck was the **resolution of the selection panel**, not the gate and not the search. The space was *not* proven exhausted (264 of 324 configurations unmeasured).
- **L1: the large-panel cycle.** Pre-registered the same night and run: virgin panels of 72/48/24 replicates, δ recalibrated and adopted at 0.1141 (2.7391 totals), and all 58 configurations of the closed scope re-measured. **0 of 58 pass selection** (best: +0.1528 = 0.22 standard errors; the historical winners evaporated: +1.4444 → +0.1389). The pre-registration's own exit clause then executed: **the search over this scaffold is closed, with a certified null at 72/48/24 resolution.** The base configuration is the certified operating optimum over the measured scope (58 measured; 206 unmeasured — closure by settled decision, not by exhaustion). Reopening requires a new pre-registration that changes the frame — a different space, task, or instrument.
- **Governance holes closed the day an external audit found them.** An outside review (brought in by the author) identified two real defects, both verified in code and fixed the same day (2026-10-16, report in `resultados/arreglo-freno-rollback-2026-10-16.md`): the stall-brake unlock accepted a mere `"humano"` label — it now requires a token from the `ALMA_TOKEN_HUMANO` environment variable, compared in constant time and **fail-closed** (no token configured, no unlock, ever); and `revertir()` restored reverted versions as new ones, so a double rollback could resurrect what was reverted — it now walks the stack of adoptions in effect. Suite: `test_gobernanza_freno_rollback.py`.
- **A second frame opened (2026-10-17): ALMA on Muse.** Under a new pre-registration that changes the task (the assistant's real daily work) and the instrument (high-volume offline screen batteries over real-task corpora, plus the owner's live outcomes as a small, precious confirmation panel), the same governance now measures the assistant's *own configuration*. Baseline measured the same night: the codified morning-plan policy scores 0.9828 on a 60-instance deterministic battery, while the 15 plans actually lived score 0.8511 against the same frozen validator — a 0.132 gap between the policy applied carefully and the policy applied under real morning load. Cycle 1 (fixed slots + mandatory time for the day's commitment): Δ +0.0144, **partial signal**, no adoption. The screen battery's corpus is private (it is built from the owner's real days) and is **not published**; the public copy under `alma_sobre_claude/` ships the full battery code with a synthetic example corpus — see `alma_sobre_claude/SANEADO.md`.

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

The demo above runs anywhere. The governance suites are standalone scripts (no pytest, no network, no keys). Run them all with the included runner — each suite in its own subprocess, with a JSON summary:

```bash
python3 scripts/run_test_suites.py
```

These suites also run in CI: GitHub Actions (`.github/workflows/tests.yml`) executes the same runner on every push and pull request.

Verified from a clean export tree on 2026-10-17: **all 47 suites pass standalone** (43 in the 2026-10-15 export, plus the generator, crossover, EXP82 and brake/rollback-governance suites). The export includes the historical experiment runners (`run_experiment47/49/51/56`, `run_exp77`, `run_exp82`), the original `alma` package, the live `servicio/` tree, and the EXP44 dataset those runners exercise (`data_exp44/feed_units.json` + `tasas.json`). The original `feed_units.json` mixed fictional units with units carrying the author's real personal and financial data, so the published file is a **sanitized version**: 12 of its 94 units were replaced by synthetic units of the same category, date and structure, each marked in its own text as invented (see `data_exp44/SANEADO.md` for the replacement criteria); the other 82 units are identical to the original, and the original file stays local. The runner reports **47 PASS**: since 2026-10-16 it classifies each suite by its exit code, not by scanning printed output. (It used to grep for failure markers, which flagged a false positive: `test_exp77_auditoria` still prints `FAIL -` lines by design — the program under test demonstrates its own fail-closed path — and counts as PASS because it exits 0 with 24/24 checks green.) The audits cited above (8/8, 35/35, 28/30) were run against the full local system and their records live in `experimentos/` and `preregistros/`. What this export adds, excludes and sanitizes relative to the local prototype is declared in [`EXPORT-2026-10-17.md`](EXPORT-2026-10-17.md).

## How it works — the five pieces

1. **Cheap evaluator first.** Generate–prune–then–rank, applied as governance: the cheap judge filters, the expensive one decides.
2. **Two-split gate with a noise floor.** Described above: no adoption below measured noise, ever — "better, never worse" is enforced by measurement, not intention.
3. **The human stays outside the loop's reach.** The meta-loop auto-adopts measured improvements and reports every evolution — but it cannot touch two things: the **spending caps** and its **duty to notify**. If it could silence its own reports, the reports would be worthless.
4. **Pre-registration before every experiment.** What is expected, what would count as strange, and what result would change the verdict — written *before* running. Without it, any outcome can be narrated as success. (See `preregistros/`.)
5. **The claims ledger.** Every assertion the system makes about its owner carries a source and a date, and gets audited. First ledger audit: 8/8 confirmed. (The ledger itself is the owner's personal record and is not published; its method is described here and its audits are cited with their counts.)

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
| 15 Oct 2026 | **This repository goes public** (curated export, sanitized dataset) and the thesis article is published on LinkedIn |
| 16 Oct 2026 | **δ recalibrated and adopted: 0.53 → 0.2283** (v3; v1/v2 archived by their own rules); gate rewired to the totals scale (5.4781). Three searches against the new gate — RSO, LLM generator (one real run, US$0.0001774), crossover (24 children) — all partial signal, **zero adoptions**; stall brake 3/3 by design |
| 16 Oct 2026 | **§9 diagnosis:** the train "winners" were selected noise; the bottleneck was selection-panel resolution (~65 replicates needed vs 18 available) |
| 16 Oct 2026 | **Governance fixes the same day an external audit named them:** brake unlock now requires the `ALMA_TOKEN_HUMANO` token, fail-closed; rollback now walks the adoption stack |
| 16 Oct 2026 (night) | **L1 large-panel cycle:** δ → **0.1141** (2.7391 totals), 58 configurations re-measured on virgin 72/48/24 panels, **0 pass** — the exit clause executes: **search over this scaffold closed with a certified null** |
| 17 Oct 2026 | `RESULTS-2026-10-16.md` published. New frame opened — **ALMA on Muse**: baseline (0.9828 policy vs 0.8511 lived anchor) and cycle 1 (partial signal) measured under the full governance. This export |

## Honest state

What this repository proves: the instruments work and are measured (audits 8/8 and 35/35; test-suite status in "Verify it yourself" above).

What it does **not** prove — stated here because it is the point: **the meta-loop has zero adoptions with a measured improvement above its noise floor.** That number has not moved. What changed on 2026-10-16 is that the zero is now a *measured* zero: the gate was recalibrated until it was passable, three different searches and a 72-replicate re-measurement of everything ever proposed all failed to clear it, and the search over the original scaffold was closed by its own pre-registered exit clause — not abandoned, **measured shut**. The Darwin-Gödel Machine publishes SWE-bench 20% → 50%; ALMA publishes that its laboratory does not lie to itself, and now publishes the certificate. The open frontier moved to the second frame — whether the same governance can improve the assistant's own configuration on real tasks — and its first two measurements (baseline, cycle 1) are in this repository with their limits stated, including the ones that forbid calling them improvement.

## Structure

- `alma_service/` — the system: meta-loop (`metaloop.py`), gate (`gate.py`), cheap evaluator and judge, verifier, skill handoff, trust manifest, drift detector, budgeted spending caps — plus the 2026-10-16 search instruments: candidate generator (`generador_candidatos.py`) and crossover (`crossover.py`).
- `alma/` — the original prototype package (selector, backends, evaluator, registry) that the historical runners and the live service import.
- `servicio/` — the live phase-2 service tree (`server.py`, motor, memory store) that several suites exercise end to end.
- `alma_sobre_claude/` — the second frame's screen battery (frozen plan validator, scorers, corpus builder). The corpus published here is a **synthetic example**; the real one is private (see its `SANEADO.md`). The program's event ledger is `alma-sobre-claude-ledger.jsonl` at the root.
- `run_experiment*.py`, `run_exp77.py`, `run_exp82.py`, `correr_generador.py`, `correr_crossover.py` — the experiment runners the governance suites replicate against.
- `scripts/` — `run_test_suites.py`, the suite runner used for the count above.
- `demo/` — the 2-minute verifier demo above, with its sample run.
- `test_*.py` — the governance suites: auto-adoption, noise floor, human brake and rollback, manifest and loader, EXP76–82 audits, generator and crossover.
- `docs/` — real system design, phases 0–2, v2 spec, full project report, prior-art dossier.
- `preregistros/` — the meta-loop's pre-registrations (JSON run records and the Markdown pre-registrations of 2026-10-16/17, with their addenda).
- `resultados/` — the result reports: δ recalibrations, generator runs, crossover, §9 review, L1 closure, governance fix, and the second frame's baseline and cycle 1.
- `experimentos/` — key runs (EXP71, EXP76, EXP77) and the meta-loop ledger with its hash chain (also at the root, where the newer suites read it).
- `data_*/` — run data for the 2026-10-16/17 cycles (measurements, summaries, logs). Raw third-party catalog dumps and raw virginity-sweep dumps are excluded — see `EXPORT-2026-10-17.md`.
- `RESULTS-2026-10-16.md` — the public results narrative of October 16.
- `EXPORT-2026-10-17.md` — what this export changed, excluded and sanitized, and the verified suite count.

## License

© 2026 Alejandro Nahuel Salusso (ALMA Labs LLC, in formation). All rights reserved — see `LICENSE`. The code is published to be read, studied and verified; that is its function.

---

# Versión en español

# ALMA — aprender cómo los agentes se equivocan menos

**Un sistema que se mejora a sí mismo bajo gobernanza medida: evaluador barato, puerta que rechaza lo que no mejora, y un humano en el núcleo.**

Por **Alejandro Nahuel Salusso** — Miami Beach. En construcción desde septiembre de 2026; la idea nació en julio de 2025.

*Nota sobre el nombre: este ALMA — en desarrollo desde julio de 2025 — no tiene relación con el framework académico «ALMA: Automated meta-Learning of Memory designs for Agentic systems» (Xiong, Hu & Clune, arXiv:2602.07755, febrero de 2026). Misma sigla, proyectos distintos.*

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
| 15/10/2026 | **Este repositorio se hace público** (exportación curada, dataset saneado) y se publica el artículo de tesis en LinkedIn |
| 16/10/2026 | **δ recalibrado y adoptado: 0,53 → 0,2283** (v3; v1/v2 archivadas por sus propias reglas); puerta recableada a la escala de totales (5,4781). Tres búsquedas contra la puerta nueva — RSO, generador con LLM (una corrida real, US$0,0001774), crossover (24 hijos) — todas con señal parcial, **cero adopciones**; freno de estancamiento 3/3 por diseño |
| 16/10/2026 | **Diagnóstico §9:** los «ganadores» de train eran ruido seleccionado; el cuello de botella era la resolución del panel de selección (~65 réplicas necesarias contra 18 disponibles) |
| 16/10/2026 | **Arreglos de gobernanza el mismo día en que una auditoría externa los señaló:** el desbloqueo del freno ahora exige el token `ALMA_TOKEN_HUMANO`, fail-closed; el rollback ahora camina la pila de adopciones |
| 16/10/2026 (noche) | **Ciclo L1 de panel grande:** δ → **0,1141** (2,7391 totales), 58 configuraciones re-medidas en paneles vírgenes 72/48/24, **0 superan** — se ejecuta la cláusula de salida: **búsqueda sobre este scaffold cerrada con nulo certificado** |
| 17/10/2026 | `RESULTS-2026-10-16.md` publicado. Nuevo marco abierto — **ALMA sobre Muse**: línea de base (política 0,9828 vs ancla vivida 0,8511) y ciclo 1 (señal parcial) medidos bajo la gobernanza completa. Esta exportación |

## Cómo trabaja — las cinco piezas

1. **Evaluador barato como primer filtro.** Generar es casi gratis; verificar con humanos cuesta 46× lo que cuesta generar (medición 2026 con tarifas reales). Un juez barato que caza *forma* (no verdad fina — esa es su frontera honesta) poda casi todo lo malo por casi nada, y la verificación cara se hace sobre 10 candidatos, no sobre 1.000. Es la técnica *generate-prune-then-rank* aplicada como gobernanza.
2. **Puerta de dos splits con piso de ruido.** Cada cambio candidato se evalúa en dos conjuntos independientes contra un validador congelado. La auto-adopción exige efecto positivo en ambos **y** mayor que el piso de ruido medido del propio sistema: `max(Δ_in, Δ_ho) > δ`. El piso se recalibra solo bajo pre-registro y se movió siempre hacia abajo y siempre por medición: **δ = 0,53** (30/9/2026) → **0,2283** (16/10/2026, recalibración v3 adoptada) → **0,1141** (16/10/2026, ciclo L1 de panel grande); la puerta compara en totales, así que el valor cableado hoy en `alma_service/gate.py` es `PISO_RUIDO_DELTA = 2.7391` totales ≡ 0,1141 × 24. Lo que cae en la banda (0, δ] no se adopta solo — espera aprobación humana. Sin piso, el sistema persigue ruido y lo llama progreso.
3. **El humano en el núcleo, fuera del alcance del loop.** El meta-loop auto-adopta mejoras medidas y avisa cada evolución. Pero no puede tocar dos cosas: los **topes de gasto** y su **obligación de avisar**. Si pudiera silenciar los avisos, el «avísame» no valdría nada.
4. **Pre-registro antes de cada experimento.** Qué se espera, qué contaría como raro y qué resultado cambiaría el veredicto — escrito *antes* de correr. Sin pre-registro, cualquier resultado se narra como éxito. (Ver `preregistros/`.)
5. **Verificador de «fallas que parecen éxitos».** La falla cara de un agente no es la que explota: es la que *dice* que hizo algo y no lo hizo. El verificador confronta lo declarado contra lo real, corrida por corrida, y el ledger de afirmaciones audita lo que el sistema afirma sobre su dueño. (El ledger es el registro personal de su dueño y no se publica; su método está descrito acá y sus auditorías se citan con sus conteos.)

## Cómo se midió cada número

Cada número de este README, con su método, su n y su fecha — y su límite declarado.

- **Piso de ruido δ — el arco completo.** Calibrado el 30/9/2026 (experimento EXP-piso-ruido): bootstrap por bloques (B = 2000, z = 2,0) sobre corridas repetidas del validador con el sistema **sin cambios**, midiendo cuánta «mejora» produce la pura fluctuación de medición. Resultado: 0,5331, redondeado a 0,53 y cableado en `alma_service/gate.py` como `PISO_RUIDO_DELTA = 0.53`. El 16/10/2026 se recalibró bajo su propio pre-registro (`preregistros/preregistro-recalibracion-delta-v3-2026-10-16.md`; v1 y v2 se archivaron por sus propias reglas — mezcla de escalas, validación mal especificada): **δ = 0,2283 adoptado y congelado**, panel 18/12, y la puerta se recableó a la escala en la que siempre computó — totales: 0,2283 × 24 = 5,4781. Esa misma noche, el ciclo L1 (panel grande 72/48, tercer split ciego de 24) recalibró por su diseño pre-registrado: **δ = 0,1141**, cableado como **2,7391 totales**, que es el piso en el código hoy.
- **Auditoría del verificador 35/35.** Corrida del 11/10/2026 sobre la ventana 27/9–10/10/2026, costo US$0. Método: cada éxito declarado se confrontó contra los archivos y registros reales — 13 corridas de rutina diaria, 8 de inglés (7 confirmadas directo en la tabla del scorecard, más 1 marcada primero como faltante y resuelta en la misma auditoría como un problema de etiqueta de zona horaria), 13 de estudios, 1 del evaluador. 35 declarados, 35 confirmados, 0 falsos éxitos. Lo que esta auditoría **no** mide: reportes honestos no son mejora del sistema — el propio scorecard lo declara; la mejora la mide el instrumento del meta-loop (puntos siguientes). La auditoría corre ahora una vez por mes.
- **Evaluador barato 28/30.** Una batería de 30 casos; tres jueces candidatos puntuados sobre **los mismos** 30 casos: heurística 17/30 · modelo gratuito 0/30 · Mistral Nemo 28/30 (0,933) por menos de US$0,001 por corrida. La batería se usó para **seleccionar** el juez, no para entrenarlo ni ajustarlo. Limitación declarada: **todavía no hay un set holdout independiente**; replicarlo con holdout es trabajo futuro declarado, no un resultado.
- **Adopciones del meta-loop: 0.** Al día de hoy, las auto-modificaciones adoptadas con mejora medida por encima de δ son cero. Es el estado honesto alrededor del cual se organiza este repositorio — ver «16–17 de octubre» y «Estado honesto», donde la búsqueda que produjo este cero está documentada entera.

## 16–17 de octubre: la puerta se hizo pasable — y la búsqueda certificó un nulo

La narrativa completa está en [`RESULTS-2026-10-16.md`](RESULTS-2026-10-16.md); cada paso tiene su pre-registro en `preregistros/` y su informe en `resultados/`, con los datos de corrida en `data_*/`.

- **Primero se reparó la puerta.** Recalibración v3 (adoptada, congelada): δ 0,53 → 0,2283, y el recableado de `gate.py` a la escala de totales (5,4781) en la que la comparación siempre había vivido.
- **Tres búsquedas contra la puerta nueva — todas con señal parcial, cero adopciones.** (1) Mutaciones RSO: 8 rondas, todo candidato ≤ 0 en train. (2) Un generador de candidatos con LLM estilo Sakana (`alma_service/generador_candidatos.py`): tras dos intentos bloqueados por el tier gratuito (HTTP 429, asentados como bloqueados, no como fallas), una corrida real con Mistral Nemo a un costo real de **US$0,0001774** produjo 11/14 candidatos válidos; el mejor llegó a +0,0556 en train (1,0% de la puerta) y revirtió en held-out (−0,7500) — rechazado. (3) Crossover sobre esa tanda (`alma_service/crossover.py`): 24 hijos, 6 positivos en train — la mejor tasa de todas las búsquedas —; finalista +1,4444 en train, −3,0833 en held-out — rechazado. El freno de estancamiento llegó a 3/3, por diseño.
- **El diagnóstico (revisión §9).** El patrón — ganar en train, revertir en held-out — se midió de tres maneras (split-half, jackknife y un gasto diagnóstico declarado del held-out): los «positivos de train» eran **ruido seleccionado**. Certificar un efecto de +1,44 a 2 errores estándar exige ~65 réplicas; el panel de selección tenía 18. El cuello de botella era la **resolución del panel de selección**, no la puerta ni la búsqueda. El espacio **no** quedó probado agotado (264 de 324 configuraciones sin medir).
- **L1: el ciclo de panel grande.** Pre-registrado la misma noche y corrido: paneles vírgenes de 72/48/24 réplicas, δ recalibrado y adoptado en 0,1141 (2,7391 totales), y las 58 configuraciones del alcance cerrado re-medidas. **0 de 58 superan la selección** (mejor marca: +0,1528 = 0,22 errores estándar; los ganadores históricos se evaporaron: +1,4444 → +0,1389). La cláusula de salida del propio pre-registro se ejecutó: **la búsqueda sobre este scaffold quedó cerrada, con un nulo certificado a resolución 72/48/24.** La base es el óptimo operativo certificado sobre el alcance medido (58 medidas; 206 sin medir — cierre por decisión asentada, no por agotamiento). Reabrirla exige un pre-registro nuevo que cambie el marco: otro espacio, otra tarea u otro instrumento.

- **Los huecos de gobernanza, cerrados el día en que una auditoría externa los señaló.** Una revisión externa (traída por el autor) identificó dos defectos reales, ambos verificados en código y corregidos el mismo día (16/10/2026; informe en `resultados/arreglo-freno-rollback-2026-10-16.md`): el desbloqueo del freno aceptaba la mera etiqueta «humano» — ahora exige un token de la variable de entorno `ALMA_TOKEN_HUMANO`, comparado en tiempo constante y **fail-closed** (sin token configurado no hay desbloqueo, nunca); y `revertir()` restauraba lo revertido como versión nueva, de modo que un doble rollback podía resucitar lo deshecho — ahora camina la pila de adopciones en efecto. Suite: `test_gobernanza_freno_rollback.py`.
- **Un segundo marco abierto (17/10/2026): ALMA sobre Muse.** Bajo un pre-registro nuevo que cambia la tarea (el trabajo diario real del asistente) y el instrumento (baterías offline de alto volumen sobre corpus de tareas reales, más los resultados en vivo de su dueño como panel de confirmación chico y precioso), la misma gobernanza ahora mide la **propia configuración del asistente**. Línea de base medida esa misma noche: la política codificada del plan matutino puntúa 0,9828 en una batería determinista de 60 instancias, mientras los 15 planes realmente vividos puntúan 0,8511 contra el mismo validador congelado — una brecha de 0,132 entre la política aplicada con cuidado y la aplicada bajo la carga real de la mañana. Ciclo 1 (ranuras fijas + horario obligatorio del compromiso): Δ +0,0144, **señal parcial**, sin adopción. El corpus de la batería de pantalla es privado (se construye desde los días reales de su dueño) y **no se publica**; la copia pública en `alma_sobre_claude/` trae el código completo de la batería con un corpus sintético de ejemplo — ver `alma_sobre_claude/SANEADO.md`.

## Estado honesto

Lo que este repositorio prueba: los instrumentos funcionan y están medidos (auditorías 8/8 y 35/35; el estado verificado de los tests está en «Verify it yourself», arriba: las 47 suites pasan desde un árbol de exportación limpio, contra la versión saneada y publicada del dataset de EXP44 — 12 de sus 94 unidades reemplazadas por sintéticas por contener datos personales y financieros reales del autor; el detalle está en `data_exp44/SANEADO.md`).

Lo que todavía **no** prueba, y lo digo en el README porque es el punto: **el meta-loop suma cero adopciones con mejora medida por encima del piso de ruido.** Ese número no se movió. Lo que cambió el 16/10/2026 es que el cero ahora es un cero *medido*: la puerta se recalibró hasta ser pasable, tres búsquedas distintas y una re-medición con 72 réplicas de todo lo propuesto alguna vez no lograron cruzarla, y la búsqueda sobre el scaffold original se cerró por la cláusula de salida de su propio pre-registro — no abandonada: **cerrada por medición**. La Darwin-Gödel Machine publica SWE-bench 20% → 50%; ALMA, por ahora, publica que su laboratorio no se miente, y ahora publica el certificado. La frontera abierta se movió al segundo marco — si la misma gobernanza puede mejorar la configuración del propio asistente en tareas reales — y sus dos primeras mediciones (línea de base, ciclo 1) están en este repositorio con sus límites declarados, incluidos los que prohíben llamarlas mejora.

## Estructura

- `alma_service/` — el sistema: meta-loop (`metaloop.py`), puerta (`gate.py`), evaluador y juez baratos, verificador, handoff de skills, manifiesto de confianza, detector de deriva, presupuesto con topes — más los instrumentos de búsqueda del 16/10/2026: generador de candidatos (`generador_candidatos.py`) y crossover (`crossover.py`).
- `alma/` — el paquete original del prototipo (selector, backends, evaluador, registro) que importan los runners históricos y el servicio en vivo.
- `servicio/` — el árbol del servicio fase 2 en vivo (`server.py`, motor, memoria) que varias suites ejercitan de punta a punta.
- `alma_sobre_claude/` — la batería de pantalla del segundo marco (validador de planes congelado, puntuadores, constructor de corpus). El corpus publicado es un **ejemplo sintético**; el real es privado (ver su `SANEADO.md`). El ledger de eventos del programa es `alma-sobre-claude-ledger.jsonl`, en la raíz.
- `run_experiment*.py`, `run_exp77.py`, `run_exp82.py`, `correr_generador.py`, `correr_crossover.py` — los runners de experimentos contra los que replican las suites de gobernanza.
- `scripts/` — `run_test_suites.py`, el runner de suites con el que se verificó el conteo de arriba.
- `demo/` — la demo de 2 minutos del verificador, con su corrida de ejemplo.
- `test_*.py` — las suites de gobernanza: auto-adopción, piso de ruido, freno humano y rollback, manifiesto y loader, auditorías EXP76–82, generador y crossover.
- `docs/` — diseño del sistema real, fases 0–2, spec v2, informe completo del proyecto y dossier de prior art.
- `preregistros/` — los pre-registros del meta-loop (registros JSON de corrida y los pre-registros en Markdown del 16–17/10/2026, con sus adendas).
- `resultados/` — los informes de resultados: recalibraciones de δ, corridas del generador, crossover, revisión §9, cierre L1, arreglo de gobernanza, y la línea de base y el ciclo 1 del segundo marco.
- `experimentos/` — corridas clave (EXP71, EXP76, EXP77) y el ledger del meta-loop con cadena de hashes (también en la raíz, donde lo leen las suites nuevas).
- `data_*/` — datos de corrida de los ciclos del 16–17/10/2026 (mediciones, resúmenes, logs). Los dumps crudos de catálogo de terceros y los dumps crudos de barrido de virginidad se excluyen — ver `EXPORT-2026-10-17.md`.
- `RESULTS-2026-10-16.md` — la narrativa pública de resultados del 16 de octubre.
- `EXPORT-2026-10-17.md` — qué cambió, qué se excluyó y qué se saneó en esta exportación, y el conteo de suites verificado.

## Licencia

© 2026 Alejandro Nahuel Salusso (ALMA Labs LLC, en formación). Todos los derechos reservados — ver `LICENSE`. El código está publicado para ser leído, estudiado y verificado; esa es su función.
