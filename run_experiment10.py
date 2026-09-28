#!/usr/bin/env python3
"""ALMA-EXP10: ¿escala la selección cuando el menú crece?

EXP1-9 usaron 2 brazos (single/cot). El mundo real no es binario. EXP10
suma un tercer brazo del registry existente: `reflexion` (actor + crítico
+ hasta 2 reintentos, costo_relativo 4.0). El reward ya penaliza el costo
(0.75*éxito + 0.25*eficiencia), así que reflexion tiene que GANARSE su precio.

Diseño (aprobado: ~US$0,06, ~25 min):
  - 10A-oracle: reflexion sobre los 120 problemas x 2 intentos
    (fases 10A-oracle-r1/r2; 2 intentos bastan: EXP8 mostró estabilidad).
  - Política alma-3: probe continuo sobre 3 brazos en el stream con flip
    del EXP9 (orden nuevo [1,7,9,3,5,4,2,0,6,8]).
    * Probe q=0,1,2 y re-probe q=6,7. single/cot: rewards 7B-alma-probe
      grabados (mismos problemas, mismas posiciones); reflexion: pulls
      nuevos (fase 10B-alma-probe).
    * Regla de decisión (espíritu EXP3): default single; se cambia al mejor
      alternativo solo si supera a single por > 0.05 en media de probe.
    * Thompson q=3,4,5,8,9,10,11 con prior warm UNIFORME (aisla el efecto
      "cantidad de brazos"; el decaimiento fue pregunta del EXP9).
      Pulls nuevos (fase 10B-alma-full), RNG pareado por (bloque,q).
  - Oráculo para regret: max sobre 3 brazos de la media de intentos
    (single/cot: EXP8 firme de 3; reflexion: media de 2 nuevos).
  - Comparación: mejor brazo FIJO entre los 3 (replay del oráculo).

Criterio PRE-REGISTRADO (PASS):
  - regret(alma-3) < regret(mejor fija entre 3)

Uso:
    python3 run_experiment10.py --mock
    python3 run_experiment10.py --api
"""
import argparse
import json
import os
import random
import shutil
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_experiment as rx
import run_experiment5 as rx5

NOMBRE = "ALMA-EXP10: selección con 3 brazos (single/cot/reflexion)"
ARMS3 = ["single", "cot", "reflexion"]
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (6, 7)
THOMPSON_Q = (3, 4, 5, 8, 9, 10, 11)
FASE_OR1 = "10A-oracle-r1"
FASE_OR2 = "10A-oracle-r2"
FASE_PROBE10 = "10B-alma-probe"
FASE_FULL10 = "10B-alma-full"
FASE_PROBE7 = "7B-alma-probe"
ORDEN_FLIP = [1, 7, 9, 3, 5, 4, 2, 0, 6, 8]

CRITERIO_EXP10 = {"alma3_gana_a_mejor_fija": True}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def probe_choice_3(probe_rs):
    """Default single; se cambia al mejor alternativo solo si lo supera
    por el margen (generalización de la regla EXP3)."""
    m = {a: mean(rs) for a, rs in probe_rs.items()}
    mejor_alt = max([a for a in ARMS3 if a != "single"], key=lambda a: m[a])
    return mejor_alt if m[mejor_alt] - m["single"] > rx5.PROBE_MARGEN else "single"


def main():
    ap = argparse.ArgumentParser(description="ALMA-EXP10: 3 brazos")
    ap.add_argument("--mock", action="store_true", default=True)
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--seed", type=int, default=999)
    args = ap.parse_args()

    t0 = time.time()
    base = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(base, "resultados", "exp10-20260926")
    os.makedirs(out, exist_ok=True)

    prereg = {
        "experimento": NOMBRE,
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "criterio_exito": CRITERIO_EXP10,
        "diseno": {
            "brazos": ARMS3,
            "oraculo_reflexion": "120 problemas x 2 intentos (fases 10A-oracle-r1/r2)",
            "stream": "flip EXP9: orden nuevo [1,7,9,3,5,4,2,0,6,8]",
            "politica": "probe continuo 3 brazos + Thompson prior uniforme",
            "regla_probe": "default single; cambio si el mejor alternativo supera por > 0.05",
            "rng": "pareado por (bloque,q), seed 999",
        },
        "seed": args.seed,
        "modo": "api" if args.api else "mock",
    }
    with open(os.path.join(out, "preregistro.json"), "w") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito. Criterio: {CRITERIO_EXP10}")

    problemas = rx5.cargar_todo(base)
    orden_orig = rx5.ordenar_stream(args.seed)
    orden_nuevo = [orden_orig[i] for i in ORDEN_FLIP]
    stream = [(c, p) for c in orden_nuevo for p in problemas[c]]
    assert len(stream) == 120

    if args.api:
        backend = rx.VaultBackend()
        print(f"Backend real (vault): {backend.model} vía skill openai")
        limites = {rx.RESOLUCION: 50.0, rx.SELECCION: 1.0, rx.EXPERIMENTACION: 5.0}
    else:
        index = {p["id"]: p for ps in problemas.values() for p in ps}
        backend = rx.MockBackend(index, seed=args.seed)
        print("Backend mock (mundo sintético determinista)")
        limites = {rx.RESOLUCION: 10.0, rx.SELECCION: 1.0, rx.EXPERIMENTACION: 5.0}

    evaluator = rx.Evaluator(judge=rx.StubJudge())
    exp5_store = rx.ExperienceStore(
        os.path.join(base, "resultados", "exp5-20260926", "experiencias.jsonl"))
    store7 = rx.ExperienceStore(
        os.path.join(base, "resultados", "exp7-20260926", "experiencias.jsonl"))
    store10 = rx.ExperienceStore(os.path.join(out, "experiencias.jsonl"))
    budget = rx.BudgetManager(limites)
    pull, hechos = rx5.make_puller(store10, backend, evaluator, budget)

    hechos7 = {(r["fase"], r["problema_id"], r["arch_id"]): r["metricas"]["reward"]
               for r in store7.read_all()}

    # --- Fase 10A: oráculo de reflexion (2 intentos) ---
    print("Fase 10A: oráculo reflexion x2 (idempotente)...")
    t_or = time.time()
    for fase in (FASE_OR1, FASE_OR2):
        for _pos, (_c, p) in enumerate(stream):
            pull(p, "reflexion", fase)
    print(f"   oráculo completo ({time.time() - t_or:.0f}s)")

    # --- Oráculo firme de 3 brazos ---
    acc = defaultdict(list)
    for r in exp5_store.read_all():
        if r.get("fase") == "5A-oracle" and r.get("arch_id") in ("single", "cot"):
            acc[(r["problema_id"], r["arch_id"])].append(r["metricas"]["reward"])
    store8 = rx.ExperienceStore(
        os.path.join(base, "resultados", "exp8-20260926", "experiencias.jsonl"))
    for r in store8.read_all():
        if r.get("arch_id") in ("single", "cot"):
            acc[(r["problema_id"], r["arch_id"])].append(r["metricas"]["reward"])
    for (f, pid, a), rw in hechos.items():
        if f in (FASE_OR1, FASE_OR2) and a == "reflexion":
            acc[(pid, a)].append(rw)
    oracle_mean = {k: sum(v) / len(v) for k, v in acc.items()}
    oracle_reward = {pos: max(oracle_mean[(p["id"], a)] for a in ARMS3)
                     for pos, (_c, p) in enumerate(stream)}

    # --- Política alma-3 ---
    print("Política alma-3 (probe continuo + Thompson)...")
    pos_de_pid = {p["id"]: i for i, (_c, p) in enumerate(stream)}

    def repertorio(pos_limite):
        rep = {a: [] for a in ARMS3}
        for r in exp5_store.read_all():
            if r.get("fase") != "5A-oracle" or r.get("arch_id") not in ARMS3:
                continue
            if pos_de_pid.get(r.get("problema_id", ""), 10 ** 9) < pos_limite:
                rep[r["arch_id"]].append(r["metricas"]["reward"])
        for (f, pid, a), rw in hechos7.items():
            if f != FASE_PROBE7 or a not in ARMS3:
                continue
            if pos_de_pid.get(pid, 10 ** 9) < pos_limite:
                rep[a].append(rw)
        for (f, pid, a), rw in hechos.items():
            if a not in ARMS3:
                continue
            if pos_de_pid.get(pid, 10 ** 9) < pos_limite:
                rep[a].append(rw)
        return rep

    rewards = {}
    diag = []
    n_switch = 0
    n_probe_pulls = 0
    for nb, _clase in enumerate(orden_nuevo):
        base_pos = nb * 12
        bandit = rx5.bandit_warm(repertorio(base_pos))
        prior_means = bandit.means()

        def probe_q(qs):
            prs = {}
            for q in qs:
                pid = stream[base_pos + q][1]["id"]
                for a in ARMS3:
                    if a in ("single", "cot"):
                        key = (FASE_PROBE7, pid, a)
                        assert key in hechos7, f"falta probe grabado {key}"
                        prs[(q, a)] = hechos7[key]
                    else:
                        r, _nuevo = pull(stream[base_pos + q][1], a, FASE_PROBE10)
                        prs[(q, a)] = r
                    bandit.update(a, prs[(q, a)])
            return prs

        prs = probe_q(PROBE_Q1)
        n_probe_pulls += len(PROBE_Q1) * len(ARMS3)
        e1 = probe_choice_3({a: [prs[(q, a)] for q in PROBE_Q1] for a in ARMS3})
        for q in PROBE_Q1:
            rewards[base_pos + q] = prs[(q, e1)]

        for q in (3, 4, 5):
            pos = base_pos + q
            rng = random.Random(f"{args.seed}-exp10-{nb}-{q}")
            arch = bandit.select(rng)
            r, _nuevo = pull(stream[pos][1], arch, FASE_FULL10)
            bandit.update(arch, r)
            rewards[pos] = r

        prs2 = probe_q(PROBE_Q2)
        n_probe_pulls += len(PROBE_Q2) * len(ARMS3)
        todo = dict(prs)
        todo.update(prs2)
        qs_all = PROBE_Q1 + PROBE_Q2
        e2 = probe_choice_3({a: [todo[(q, a)] for q in qs_all] for a in ARMS3})
        if e1 != e2:
            n_switch += 1
        for q in PROBE_Q2:
            rewards[base_pos + q] = todo[(q, e2)]

        for q in (8, 9, 10, 11):
            pos = base_pos + q
            rng = random.Random(f"{args.seed}-exp10-{nb}-{q}")
            arch = bandit.select(rng)
            r, _nuevo = pull(stream[pos][1], arch, FASE_FULL10)
            bandit.update(arch, r)
            rewards[pos] = r

        diag.append({"bloque_nuevo": nb, "prior_means": prior_means,
                     "inicial": e1, "final": e2, "cambio": e1 != e2})
    assert len(rewards) == 120

    # --- Veredicto ---
    reg_alma = sum(oracle_reward[pos] - rewards[pos] for pos in range(120))
    reg_fijas = {}
    for a in ARMS3:
        reg_fijas[a] = sum(
            oracle_reward[pos] - oracle_mean[(stream[pos][1]["id"], a)]
            for pos in range(120))
    mejor_fija = min(reg_fijas, key=lambda a: reg_fijas[a])

    verdad_bloque = []
    for nb in range(10):
        s = {a: sum(oracle_mean[(stream[nb * 12 + q][1]["id"], a)]
                    for q in range(12)) for a in ARMS3}
        verdad_bloque.append(max(s, key=lambda a: s[a]))

    pasa = bool(reg_alma < reg_fijas[mejor_fija])
    costo_total = sum(budget.gastado.values())
    motivos = [
        f"regret alma-3={reg_alma:.4f} vs mejor fija ({mejor_fija})="
        f"{reg_fijas[mejor_fija]:.4f} "
        f"(diff={reg_alma - reg_fijas[mejor_fija]:+.4f})",
        f"regret fijas: {', '.join(f'{a}={reg_fijas[a]:.2f}' for a in ARMS3)}",
        f"verdad por bloque: {verdad_bloque}",
        f"decisión final por bloque: {[d['final'] for d in diag]}",
        f"cambios tras re-probe: {n_switch}/10",
    ]
    report = {
        "preregistro": prereg,
        "regret_total": {"alma_3": round(reg_alma, 4),
                         **{f"fija_{a}": round(v, 4)
                             for a, v in reg_fijas.items()}},
        "verdad_bloque": verdad_bloque,
        "diagnostico_bloques": diag,
        "costo_total_usd": round(costo_total, 4),
        "experiencias_nuevas": len(store10),
        "veredicto": {"pasa": pasa, "criterio": CRITERIO_EXP10,
                       "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO ================")
    for m in motivos:
        print("  " + m)
    print(f"  costo llamadas nuevas: ${costo_total:.4f} USD  |  "
          f"{len(store10)} experiencias nuevas  |  {report['duracion_s']}s")
    print("  RESULTADO:", "PASS — la selección escala a 3 brazos"
          if pasa else "FAIL — con 3 brazos, mejor quedarse con uno fijo")
    print("===========================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
