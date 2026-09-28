#!/usr/bin/env python3
"""ALMA-EXP15: test de equifinalidad — ¿se justifica la complejidad?

Hipótesis (base de conocimiento ~/workspace/alma/conocimiento/, meta-patrón
transversal: "reglas locales simples → estructura global compleja
(equifinalidad)"): un selector TONTO — epsilon-greedy por clase, sin probe,
sin Thompson, sin re-probe, sin olvido — EMPATA al ALMA v2 completo.
Es el experimento más "refutación primero" de todos: apunta contra ALMA misma.

Diseño (aprobado por el usuario 26/9 ~12:35):
  - Mismo stream no estacionario con flip de EXP12/13/14 (10 bloques x 12,
    oráculo copiado, SIN medir de nuevo).
  - Dos políticas sobre el mismo stream y seed:
      a. control: réplica exacta de ALMA v2 de EXP13 (probe q=0,1,2 +
         re-probe q=10,11; Thompson; prior warm con olvido 0.5^d;
         fix1: default = prior-best, cambio si alternativo supera al
         prior-best por > 0.05; fix2: poda de brazos muertos).
      b. eps: epsilon-greedy POR CLASE (epsilon=0.1, pre-registrado):
         por cada problema, con prob 0.9 elige el brazo con mejor media
         empírica de ESA clase (init 0.5, sin historia previa), con prob 0.1
         un brazo al azar. Sin probe, sin Thompson, sin re-probe, sin
         olvido, sin transferencia entre clases. La regla local más tonta.
  - RNG con seed pre-registrada 1515, pareado por (politica,bloque,q).

Criterio PRE-REGISTRADO: la refutación PASA (la complejidad NO se justifica)
si regret(eps) <= regret(v2) + 0.5. Si el simple pierde por más de 0.5,
FAIL (la complejidad paga).

Restricciones duras:
  - Solo gpt-4o-mini. Si la proyección de costo supera US$1,00: detener
    (exit 2) y reportar.
  - La API key nunca se imprime ni se guarda (VaultBackend).

Uso:
    python3 run_experiment15.py --mock [--out /tmp/exp15-mock]
    python3 run_experiment15.py --api
"""
import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_experiment as rx
import run_experiment5 as rx5
import run_experiment12 as rx12
import run_experiment13 as rx13

NOMBRE = ('ALMA-EXP15: test de equifinalidad — epsilon-greedy tonto vs '
          'ALMA v2 completo')
ARMS3 = ["single", "cot", "reflexion"]
SEED = 1515
BLOQUE = 12
N_BLOQUES = 10
N_PROB = N_BLOQUES * BLOQUE  # 120
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (10, 11)
THOMPSON_Q = tuple(q for q in range(BLOQUE)
                   if q not in PROBE_Q1 + PROBE_Q2)
assert len(THOMPSON_Q) == 7
# Fases: el oráculo se COPIA de EXP12 (mismas mediciones, fase renombrada).
FASE_OR1_SRC, FASE_OR2_SRC = "12A-oracle-r1", "12A-oracle-r2"
FASE_OR1, FASE_OR2 = "15A-oracle-r1", "15A-oracle-r2"
FASE_CTL_PROBE, FASE_CTL_FULL = "15B-ctl-probe", "15B-ctl-full"
FASE_CTL = (FASE_OR1, FASE_OR2, FASE_CTL_PROBE, FASE_CTL_FULL)
FASE_EPS = "15B-eps"
EPSILON = 0.1            # pre-registrado: tasa de exploración del tonto
MARGEN_EQUIV = 0.5       # pre-registrado: el simple "empata" si no pierde
                         # por más de 0.5 de regret
DECAY = 0.5              # olvido exponencial rápido (maquinaria EXP9, control)
N0 = rx5.N0_PSEUDO       # fuerza del prior warm (EXP4, control)
MARGEN = rx5.PROBE_MARGEN  # 0.05 (control)
PODA_GAP = 0.10          # fix2: gap de media empírica para podar (control)
PODA_BLOQUES = 2         # fix2: bloques consecutivos con gap (control)
COSTO_STOP = 1.00        # freno duro de costo total proyectado (USD)

CRITERIO_EXP15 = {"eps_empata_a_v2": True, "epsilon": EPSILON,
                  "margen_equivalencia": MARGEN_EQUIV}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def copiar_oraculo_exp12(store, base):
    """Copia las 720 mediciones del oráculo de EXP12 al store nuevo con
    fases 15A-*. Sin llamadas a la API. Devuelve {(pid, arm): media}."""
    src = os.path.join(base, "resultados", "exp12-20260926",
                       "experiencias.jsonl")
    n = 0
    for line in open(src, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("fase") not in (FASE_OR1_SRC, FASE_OR2_SRC):
            continue
        nueva = {k: v for k, v in row.items()
                 if k not in ("hash", "prev_hash", "timestamp", "schema")}
        nueva["fase"] = (FASE_OR1 if row["fase"] == FASE_OR1_SRC
                         else FASE_OR2)
        store.append(nueva)
        n += 1
    assert n == N_PROB * 3 * 2, f"oráculo copiado incompleto: {n}/720"
    acc = defaultdict(list)
    for r in store.read_all():
        if r.get("fase") in (FASE_OR1, FASE_OR2):
            acc[(r["problema_id"], r["arch_id"])].append(
                r["metricas"]["reward"])
    assert len(acc) == N_PROB * 3, f"celdas: {len(acc)}/360"
    return {k: sum(v) / len(v) for k, v in acc.items()}


def main():
    ap = argparse.ArgumentParser(description="ALMA-EXP15: equifinalidad")
    ap.add_argument("--mock", action="store_true", default=True)
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    t0 = time.time()
    base = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(base, "resultados", "exp15-20260926")
    os.makedirs(out, exist_ok=True)
    prereg_path = os.path.join(out, "preregistro.json")

    cands = rx12.cargar_problemas(base)
    print(f"Candidatos: {len(cands)} problemas (72 sint + 24 gsm8k + 24 mmlu)")

    if args.api:
        backend = rx.VaultBackend()
        print(f"Backend real (vault): {backend.model} vía skill openai")
        limites = {rx.RESOLUCION: 50.0, rx.SELECCION: 1.0,
                   rx.EXPERIMENTACION: 5.0}
    else:
        index = {p["id"]: p for p in cands}
        backend = rx.MockBackend(index, tasas=rx12.TASAS12, seed=args.seed)
        print("Backend mock (tasas con flip real por diseño)")
        limites = {rx.RESOLUCION: 10.0, rx.SELECCION: 1.0,
                   rx.EXPERIMENTACION: 5.0}

    evaluator = rx.Evaluator(judge=rx.StubJudge())
    store = rx.ExperienceStore(os.path.join(out, "experiencias.jsonl"))
    budget = rx.BudgetManager(limites)

    # --- Oráculo: COPIA de EXP12 (sin medir de nuevo) ---
    print("Copiando oráculo de EXP12 (720 mediciones, sin API)...")
    oracle_mean = copiar_oraculo_exp12(store, base)
    print(f"   oráculo copiado: {len(oracle_mean)} celdas, $0.0000")

    pull, hechos = rx5.make_puller(store, backend, evaluator, budget)

    # --- Stream: mismo orden que EXP12 (verificado) ---
    bloques = rx12.bloques_clase_pura(cands)
    info = []
    for nombre, probs in bloques:
        mejor, medias, margen = rx12.mejor_brazo_bloque(probs, oracle_mean)
        info.append((nombre, mejor, probs, medias, margen))
    ordenado = rx12.ordenar_alternado([(n, m, p) for n, m, p, _, _ in info])
    por_nombre = {n: (m, md, mg) for n, m, _, md, mg in info}
    stream = []
    orden_bloques = []
    for nombre, mejor, probs in ordenado:
        medias, margen = por_nombre[nombre][1], por_nombre[nombre][2]
        for p in probs:
            stream.append((nombre, p))
        orden_bloques.append({"bloque": nombre, "mejor_oraculo": mejor,
                              "margen": round(margen, 4)})
    assert len(stream) == N_PROB
    # Verificar idéntico a EXP12.
    pre12 = json.load(open(os.path.join(
        base, "resultados", "exp12-20260926", "preregistro.json"),
        encoding="utf-8"))
    ord12 = [(b["bloque"], b["mejor_oraculo"])
             for b in pre12["orden_bloques"]]
    ord15 = [(b["bloque"], b["mejor_oraculo"]) for b in orden_bloques]
    assert ord15 == ord12, f"¡el stream difiere de EXP12! {ord15} vs {ord12}"
    print(f"   stream verificado idéntico a EXP12 "
          f"({[b + ':' + m for b, m in ord15]})")

    oracle_reward = {pos: max(oracle_mean[(p["id"], a)] for a in ARMS3)
                     for pos, (_c, p) in enumerate(stream)}

    # --- Freno de costo (proyección ANTES de las políticas) ---
    rep12 = json.load(open(os.path.join(
        base, "resultados", "exp12-20260926", "report.json"),
        encoding="utf-8"))
    avg_pull = (rep12["costo_total_usd"] / rep12["experiencias_nuevas"]
                if rep12["experiencias_nuevas"] else 0.0)
    # control: 10*(5*3 probe + 7 thompson) = 220; eps: 120 sin probe
    n_policy_pulls = (N_BLOQUES * (len(PROBE_Q1) + len(PROBE_Q2)) * 3
                      + N_BLOQUES * len(THOMPSON_Q) + N_PROB)
    policy_est = avg_pull * n_policy_pulls * 1.5  # margen de seguridad
    proyeccion = policy_est  # oráculo copiado: $0
    print(f"   proyección de costo total: ${proyeccion:.4f} "
          f"({n_policy_pulls} pulls x ~${avg_pull:.6f} x 1.5)")
    detenido = False
    if args.api and proyeccion > COSTO_STOP:
        detenido = True
        print(f"   ¡FRENO! proyección ${proyeccion:.4f} > ${COSTO_STOP:.2f}.")

    # --- Pre-registro (ANTES de las políticas; criterio fijo) ---
    diseno = {
        "oraculo": "COPIADO de EXP12 (3 brazos x 2 intentos, 720 mediciones, "
                   "fases 15A-*); sin medir de nuevo",
        "stream": "10 bloques x 12 idéntico a EXP12 (verificado), flip real "
                  "8/9 alternancias, brazos en juego: cot/single",
        "politica_control": "réplica exacta de ALMA v2 de EXP13 (probe "
                            "q=0,1,2 + re-probe q=10,11; Thompson; prior "
                            "warm con olvido 0.5^d; fix1: default = "
                            "prior-best warm, cambio si alternativo supera "
                            "por > 0.05; fix2: poda de brazos muertos)",
        "politica_eps": "epsilon-greedy POR CLASE (epsilon=0.1): por "
                       "problema, con prob 0.9 el brazo con mejor media "
                       "empírica de esa clase (init 0.5), con prob 0.1 un "
                       "brazo al azar. Sin probe, sin Thompson, sin "
                       "re-probe, sin olvido, sin transferencia entre "
                       "clases. Clave de clase = nombre del bloque.",
        "comparacion": "mejor brazo fijo entre los 3 (replay del oráculo)",
        "rng": f"pareado por (politica,bloque,q), seed {args.seed}",
        "freno_costo": "si proyección > US$1,00: detener (exit 2)",
    }
    if os.path.exists(prereg_path):
        with open(prereg_path, encoding="utf-8") as f:
            prereg = json.load(f)
        assert prereg["criterio_exito"] == CRITERIO_EXP15, \
            "¡criterio pre-registrado cambiado! abortar."
        print(f"Pre-registro existente verificado. Criterio: {CRITERIO_EXP15}")
    else:
        prereg = {
            "experimento": NOMBRE,
            "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "criterio_exito": CRITERIO_EXP15,
            "diseno": diseno,
            "orden_bloques": orden_bloques,
            "seed": args.seed,
            "modo": "api" if args.api else "mock",
        }
        with open(prereg_path, "w", encoding="utf-8") as f:
            json.dump(prereg, f, indent=2, ensure_ascii=False)
        print(f"Pre-registro escrito (políticas aún no corridas). "
              f"Criterio: {CRITERIO_EXP15}")

    resultados = {}
    if not detenido:
        # ============ CONTROL: réplica exacta de ALMA v2 (EXP13) ============
        tag, fases = "control", FASE_CTL
        f_probe, f_full = fases[2], fases[3]
        print("Política alma control (v2 EXP13)...")
        rewards = {}
        diag = []
        n_switch = 0
        thompson_arms = defaultdict(int)
        obs = {a: [] for a in ARMS3}   # medias empíricas (fix2)
        activas = list(ARMS3)
        podas = []
        cnt_gap = {a: 0 for a in ARMS3}

        def fila_full(pid):
            for a in activas:
                if (f_full, pid, a) in hechos:
                    return a, hechos[(f_full, pid, a)]
            return None

        for nb in range(N_BLOQUES):
            base_pos = nb * BLOQUE
            bandit = rx13.bandit_warm_ponderado_arms(
                rx13.repertorio_ponderado_fases(store, stream, base_pos,
                                               rx13.DECAY, fases),
                activas)
            prior_means = bandit.means()

            def probe_q(qs):
                prs = {}
                for q in qs:
                    p = stream[base_pos + q][1]
                    for a in ARMS3:
                        key = (f_probe, p["id"], a)
                        if key in hechos:
                            r, nuevo = hechos[key], False
                        else:
                            r, nuevo = pull(p, a, f_probe)
                        prs[(q, a)] = r
                        if nuevo:
                            bandit.update(a, r) if a in activas else None
                            obs[a].append(r)
                return prs

            def thompson_q(qs):
                for q in qs:
                    pos = base_pos + q
                    p = stream[pos][1]
                    hit = fila_full(p["id"])
                    if hit is not None:
                        arch, r = hit
                        bandit.update(arch, r)
                    else:
                        rng = random.Random(
                            f"{args.seed}-exp15-{tag}-{nb}-{q}")
                        arch = bandit.select(rng)
                        r, nuevo = pull(p, arch, f_full)
                        if nuevo:
                            bandit.update(arch, r)
                            obs[arch].append(r)
                    thompson_arms[arch] += 1
                    rewards[pos] = r

            prs = probe_q(PROBE_Q1)
            pm1 = {a: mean([prs[(q, a)] for q in PROBE_Q1])
                   for a in ARMS3}
            e1 = rx13.regla_v2(pm1, prior_means, activas)
            for q in PROBE_Q1:
                rewards[base_pos + q] = prs[(q, e1)]

            thompson_q(tuple(q for q in THOMPSON_Q if q < PROBE_Q2[0]))

            prs2 = probe_q(PROBE_Q2)
            todo = dict(prs)
            todo.update(prs2)
            qs_all = PROBE_Q1 + PROBE_Q2
            pm2 = {a: mean([todo[(q, a)] for q in qs_all])
                   for a in ARMS3}
            e2 = rx13.regla_v2(pm2, prior_means, activas)
            if e1 != e2:
                n_switch += 1
            for q in PROBE_Q2:
                rewards[base_pos + q] = todo[(q, e2)]

            thompson_q(tuple(q for q in THOMPSON_Q if q > PROBE_Q2[-1]))

            # Fix2: poda por media empírica.
            medias_emp = {a: mean(obs[a]) if obs[a] else 0.5
                          for a in ARMS3}
            mejor_m = max(medias_emp[a] for a in activas)
            for a in list(activas):
                if len(activas) <= 2:
                    break
                if mejor_m - medias_emp[a] > PODA_GAP:
                    cnt_gap[a] += 1
                else:
                    cnt_gap[a] = 0
                if cnt_gap[a] >= PODA_BLOQUES:
                    activas.remove(a)
                    podas.append({"bloque": nb, "brazo": a,
                                  "media_emp": round(medias_emp[a], 4),
                                  "mejor_emp": round(mejor_m, 4)})

            diag.append({"bloque": nb,
                         "clase": stream[base_pos][0],
                         "mejor_oraculo": orden_bloques[nb]["mejor_oraculo"],
                         "prior_means": prior_means,
                         "brazos_activos": list(activas),
                         "inicial": e1, "final": e2,
                         "cambio": e1 != e2})
        assert len(rewards) == N_PROB, \
            f"rewards control incompletos: {len(rewards)}"
        reg = sum(oracle_reward[pos] - rewards[pos]
                  for pos in range(N_PROB))
        resultados["control"] = {
            "regret": round(reg, 4),
            "diagnostico": diag,
            "cambios_reprobe": n_switch,
            "selecciones": dict(thompson_arms),
            "podas": podas,
            "brazos_activos_final": list(activas),
        }
        print(f"   control: regret={reg:.4f}, podas={podas}, "
              f"selecciones={dict(thompson_arms)}")

        # ============ EPS: epsilon-greedy tonto por clase ============
        print("Política eps (epsilon-greedy por clase, sin nada)...")
        rewards_e = {}
        diag_e = []
        sel_e = defaultdict(int)
        n_explora = 0
        hist = {}  # (clase, brazo) -> [rewards] propios de esta política
        for nb in range(N_BLOQUES):
            base_pos = nb * BLOQUE
            clase = stream[base_pos][0]
            for q in range(BLOQUE):
                pos = base_pos + q
                p = stream[pos][1]
                rng = random.Random(f"{args.seed}-exp15-eps-{nb}-{q}")
                medias = {}
                for a in ARMS3:
                    obs_a = hist.get((clase, a), [])
                    medias[a] = mean(obs_a) if obs_a else 0.5
                if rng.random() < EPSILON:
                    arch = rng.choice(ARMS3)
                    exploro = True
                else:
                    top = max(medias.values())
                    cands_e = [a for a in ARMS3 if medias[a] == top]
                    arch = rng.choice(cands_e)
                    exploro = False
                r, nuevo = pull(p, arch, FASE_EPS)
                hist.setdefault((clase, arch), []).append(r)
                sel_e[arch] += 1
                if exploro:
                    n_explora += 1
                rewards_e[pos] = r
            diag_e.append({
                "bloque": nb,
                "clase": clase,
                "mejor_oraculo": orden_bloques[nb]["mejor_oraculo"],
                "medias_finales": {a: round(
                    mean(hist.get((clase, a), []))
                    if hist.get((clase, a)) else 0.5, 4) for a in ARMS3},
                "selecciones": {a: sel_e[a] for a in ARMS3},
            })
        assert len(rewards_e) == N_PROB, \
            f"rewards eps incompletos: {len(rewards_e)}"
        reg_e = sum(oracle_reward[pos] - rewards_e[pos]
                    for pos in range(N_PROB))
        resultados["eps"] = {
            "regret": round(reg_e, 4),
            "diagnostico": diag_e,
            "exploraciones": n_explora,
            "selecciones": dict(sel_e),
            "podas": [],
            "brazos_activos_final": list(ARMS3),
        }
        print(f"   eps: regret={reg_e:.4f}, exploraciones={n_explora}, "
              f"selecciones={dict(sel_e)}")

    # --- Veredicto ---
    reg_fijas = {}
    for a in ARMS3:
        reg_fijas[a] = sum(
            oracle_reward[pos] - oracle_mean[(stream[pos][1]["id"], a)]
            for pos in range(N_PROB))
    mejor_fija = min(reg_fijas, key=lambda a: reg_fijas[a])

    verdad_bloque = []
    for nb in range(N_BLOQUES):
        s = {a: sum(oracle_mean[(stream[nb * BLOQUE + q][1]["id"], a)]
                    for q in range(BLOQUE)) for a in ARMS3}
        verdad_bloque.append(max(s, key=lambda a: s[a]))

    if detenido:
        pasa = None
        motivos = [
            f"DETENIDO por freno de costo: proyección ${proyeccion:.4f} > "
            f"${COSTO_STOP:.2f}",
            "No se corrieron las políticas; no hay veredicto PASS/FAIL.",
        ]
    else:
        r_ctl = resultados["control"]["regret"]
        r_eps = resultados["eps"]["regret"]
        rf = reg_fijas[mejor_fija]
        pasa = bool(r_eps <= r_ctl + MARGEN_EQUIV)
        motivos = [
            f"regret eps={r_eps:.4f} vs control v2={r_ctl:.4f} "
            f"(diff={r_eps - r_ctl:+.4f}; margen de equivalencia "
            f"{MARGEN_EQUIV})",
            f"criterio: PASS (refutación, complejidad no se justifica) si "
            f"eps <= v2 + {MARGEN_EQUIV}",
            f"referencia mejor fija ({mejor_fija})={rf:.4f} "
            f"(eps diff={r_eps - rf:+.4f})",
            f"regret fijas: "
            f"{', '.join(f'{a}={reg_fijas[a]:.2f}' for a in ARMS3)}",
            f"verdad por bloque: {verdad_bloque}",
            f"decisión final control por bloque: "
            f"{[d['final'] for d in resultados['control']['diagnostico']]}",
            f"medias finales eps por bloque: "
            f"{[d['medias_finales'] for d in resultados['eps']['diagnostico']]}",
            f"podas control: {resultados['control']['podas'] or 'ninguna'}",
            f"selecciones control: "
            f"{resultados['control']['selecciones']} | eps: "
            f"{resultados['eps']['selecciones']} "
            f"(exploraciones eps: {resultados['eps']['exploraciones']})",
        ]

    costo_total = sum(budget.gastado.values())
    report = {
        "preregistro": prereg,
        "regret_total": {
            **({f"alma_{t}": v["regret"]
                for t, v in resultados.items()} if resultados else {}),
            **{f"fija_{a}": round(v, 4) for a, v in reg_fijas.items()},
        },
        "verdad_bloque": verdad_bloque,
        "politicas": resultados,
        "costo_total_usd": round(costo_total, 4),
        "proyeccion_usd": round(proyeccion, 4),
        "detenido_por_costo": detenido,
        "experiencias_nuevas": len(store),
        "store_chain_ok": store.verify_chain(),
        "veredicto": {"pasa": pasa, "criterio": CRITERIO_EXP15,
                       "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO ================")
    for m in motivos:
        print("  " + m)
    print(f"  costo total: ${costo_total:.4f} USD  |  {len(store)} experiencias  "
          f"|  {report['duracion_s']}s")
    if detenido:
        print("  RESULTADO: DETENIDO — proyección de costo superó el freno")
        sys.exit(2)
    print(f"  RESULTADO: {'PASS' if pasa else 'FAIL'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
