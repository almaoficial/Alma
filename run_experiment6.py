#!/usr/bin/env python3
"""ALMA-EXP6: calibrar el probe — ¿5 problemas de prueba deciden mejor que 3?

EXP5 dejó el punto débil a la vista: el probe (3 problemas × {single, cot},
margen 0.05) eligió el brazo equivocado en el bloque de lógica y eso costó
0.66 de regret — casi todo el margen sobre thompson-global (-0.09).

Diseño: mismo stream de 120 problemas (10 clases × 12, seed 999) y mismo
oráculo medido de EXP5 (fase 5A-oracle; se reutiliza, cero llamadas nuevas).
Dos políticas:
  1. control: alma-full de EXP5 con probe=3 (replay del store, 0 llamadas).
  2. probe5: alma-full con probe=5 problemas por clase (mismo margen 0.05).

Todo lo demás idéntico a EXP5: bandit por clase, warm-start desde repertorio
hacia adelante (n0=2; usa 5A-oracle + fases 6B propias), RNG pareado por
posición (seed 999 → mismos draws que EXP5).

Criterio PRE-REGISTRADO (PASS):
  - regret(probe5) < regret(probe3-control)
Diagnóstico: tasa de acierto del probe por bloque (¿eligió el mejor brazo
fijo del bloque según lo medido en 5B?), costo extra vs ganancia.

Uso:
    python3 run_experiment6.py --mock
    python3 run_experiment6.py --api
"""
import argparse
import json
import os
import random
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_experiment as rx
import run_experiment5 as rx5

rx.NOMBRE_EXPERIMENTO = "ALMA-EXP6: calibrar el probe (3 vs 5)"

ARMS = ["single", "cot"]
PROBE_N6 = 5
FASE_PROBE6 = "6B-alma-probe"
FASE_FULL6 = "6B-alma-full"
FASES6 = (FASE_PROBE6, FASE_FULL6)

CRITERIO_EXP6 = {
    "gana_a_control": True,   # regret(probe5) < regret(probe3 de EXP5)
}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def repertorio6(exp5_store, store6, stream, pos_limite):
    """Medias globales por brazo con observaciones de posiciones < pos_limite.
    Fuentes: 5A-oracle (EXP5, conocimiento previo del sistema) + fases 6B
    propias. Hacia adelante, como EXP4/EXP5."""
    pos_de_pid = {p["id"]: i for i, (_c, p) in enumerate(stream)}
    rep = {a: [] for a in ARMS}
    for r in exp5_store.read_all():
        if r.get("fase") != "5A-oracle":
            continue
        if r.get("arch_id") not in ARMS:
            continue
        if pos_de_pid.get(r.get("problema_id", ""), 10 ** 9) < pos_limite:
            rep[r["arch_id"]].append(r["metricas"]["reward"])
    for r in store6.read_all():
        if r.get("fase") not in FASES6:
            continue
        if r.get("arch_id") not in ARMS:
            continue
        if pos_de_pid.get(r.get("problema_id", ""), 10 ** 9) < pos_limite:
            rep[r["arch_id"]].append(r["metricas"]["reward"])
    return rep


def correr_alma_probe5(stream, orden, pull, hechos, exp5_store, store6, seed):
    """Idéntico a correr_alma_full de EXP5 pero con probe de 5 problemas y
    fases 6B. Idempotente vía pull."""
    rewards = {}

    def filas_probe(pid):
        return [(a, hechos[(FASE_PROBE6, pid, a)])
                for a in ARMS if (FASE_PROBE6, pid, a) in hechos]

    def fila_full(pid):
        for a in ARMS:
            if (FASE_FULL6, pid, a) in hechos:
                return a, hechos[(FASE_FULL6, pid, a)]
        return None

    for b, clase in enumerate(orden):
        base = b * 12
        rep = repertorio6(exp5_store, store6, stream, base)
        bandit = rx5.bandit_warm(rep)
        probe_rs = {(q, a): None for q in range(PROBE_N6) for a in ARMS}
        for q in range(PROBE_N6):
            qp = stream[base + q][1]
            for a, r in filas_probe(qp["id"]):
                probe_rs[(q, a)] = r
                bandit.update(a, r)
        for q in range(PROBE_N6):
            qp = stream[base + q][1]
            for arch in ARMS:
                if probe_rs[(q, arch)] is None:
                    r, nuevo = pull(qp, arch, FASE_PROBE6)
                    probe_rs[(q, arch)] = r
                    if nuevo:
                        bandit.update(arch, r)
        por_arch = {a: [probe_rs[(q, a)] for q in range(PROBE_N6)]
                    for a in ARMS}
        elegido = rx5.probe_choice(por_arch)
        for q in range(PROBE_N6):
            rewards[base + q] = probe_rs[(q, elegido)]
        for q in range(PROBE_N6, 12):
            pos = base + q
            p = stream[pos][1]
            hit = fila_full(p["id"])
            if hit is not None:
                arch, r = hit
                bandit.update(arch, r)
                rewards[pos] = r
                continue
            rng = random.Random(f"{seed}-exp6-{pos}")
            arch = bandit.select(rng)
            r, nuevo = pull(p, arch, FASE_FULL6)
            if nuevo:
                bandit.update(arch, r)
            rewards[pos] = r
    return rewards


def control_rewards(exp5_store, stream, orden):
    """Replay del alma-full de EXP5 (probe=3): 0 llamadas nuevas."""
    probe, full = {}, {}
    for r in exp5_store.read_all():
        f, pid, a = r.get("fase"), r.get("problema_id"), r.get("arch_id")
        if f == "5B-alma-probe":
            probe[(pid, a)] = r["metricas"]["reward"]
        elif f == "5B-alma-full":
            full[(pid, a)] = r["metricas"]["reward"]
    rewards = {}
    for b, _clase in enumerate(orden):
        base = b * 12
        por_arch = {a: [probe[(stream[base + q][1]["id"], a)]
                        for q in range(3)] for a in ARMS}
        elegido = rx5.probe_choice(por_arch)
        for q in range(3):
            pid = stream[base + q][1]["id"]
            rewards[base + q] = probe[(pid, elegido)]
        for q in range(3, 12):
            pid = stream[base + q][1]["id"]
            arch = next(a for a in ARMS if (pid, a) in full)
            rewards[base + q] = full[(pid, arch)]
    assert len(rewards) == 120
    return rewards


def main():
    ap = argparse.ArgumentParser(description="ALMA-EXP6: calibrar el probe")
    ap.add_argument("--mock", action="store_true", default=True)
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--seed", type=int, default=999)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "resultados", "exp6-20260926"))
    ap.add_argument("--append", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    if not args.append and os.path.exists(args.out):
        shutil.rmtree(args.out)
    os.makedirs(args.out, exist_ok=True)

    base = os.path.dirname(os.path.abspath(__file__))
    exp5_out = os.path.join(base, "resultados", "exp5-20260926")
    prereg = {
        "experimento": rx.NOMBRE_EXPERIMENTO,
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "criterio_exito": CRITERIO_EXP6,
        "diseno": {
            "stream": "reutilizado de EXP5: 10 clases x 12, seed 999",
            "oraculo": "reutilizado de EXP5 (fase 5A-oracle), 0 llamadas",
            "control": "alma-full EXP5 probe=3 (replay, 0 llamadas)",
            "tratamiento": "alma-full probe=5, margen 0.05, fases 6B",
            "rng": "pareado por posición (seed 999), mismos draws que EXP5",
        },
        "seed": args.seed,
        "modo": "api" if args.api else "mock",
    }
    with open(os.path.join(args.out, "preregistro.json"), "w") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito. Criterio: {CRITERIO_EXP6}")

    problemas_por_clase = rx5.cargar_todo(base)
    orden = rx5.ordenar_stream(args.seed)
    stream = [(clase, p) for clase in orden for p in problemas_por_clase[clase]]
    assert len(stream) == 120

    if args.api:
        backend = rx.VaultBackend()
        print(f"Backend real (vault): {backend.model} vía skill openai")
        limites = {rx.RESOLUCION: 50.0, rx.SELECCION: 1.0, rx.EXPERIMENTACION: 5.0}
    else:
        index = {p["id"]: p for ps in problemas_por_clase.values() for p in ps}
        backend = rx.MockBackend(index, seed=args.seed)
        print("Backend mock (mundo sintético determinista)")
        limites = {rx.RESOLUCION: 10.0, rx.SELECCION: 1.0, rx.EXPERIMENTACION: 5.0}

    evaluator = rx.Evaluator(judge=rx.StubJudge())
    exp5_store = rx.ExperienceStore(
        os.path.join(exp5_out, "experiencias.jsonl"))
    store6 = rx.ExperienceStore(os.path.join(args.out, "experiencias.jsonl"))
    budget = rx.BudgetManager(limites)

    # Oráculo reutilizado de EXP5.
    oracle_reward = {}
    o5 = {}
    for r in exp5_store.read_all():
        if r.get("fase") == "5A-oracle":
            o5[(r["problema_id"], r["arch_id"])] = r["metricas"]["reward"]
    for pos, (_c, p) in enumerate(stream):
        rs = {a: o5[(p["id"], a)] for a in ARMS}
        oracle_reward[pos] = max(rs.values())
    assert len(oracle_reward) == 120
    print("Oráculo reutilizado de EXP5: "
          f"{sum(1 for pos in range(120) if o5[(stream[pos][1]['id'], 'cot')] >= o5[(stream[pos][1]['id'], 'single')])}/120 → cot")

    pull, hechos = rx5.make_puller(store6, backend, evaluator, budget)

    print("Control (replay EXP5, probe=3)...")
    rew_control = control_rewards(exp5_store, stream, orden)
    print("Tratamiento (probe=5, fases 6B)...")
    tpol = time.time()
    rew_probe5 = correr_alma_probe5(stream, orden, pull, hechos, exp5_store,
                                    store6, args.seed)
    assert len(rew_probe5) == 120
    print(f"   probe5 completo ({time.time() - tpol:.0f}s)")

    reg = {n: {pos: oracle_reward[pos] - rw[pos] for pos in range(120)}
           for n, rw in (("control", rew_control), ("probe5", rew_probe5))}
    r_control = sum(reg["control"].values())
    r_probe5 = sum(reg["probe5"].values())

    # Diagnóstico: acierto del probe por bloque (vs mejor brazo fijo de 5B).
    fijas = {}
    for r in exp5_store.read_all():
        f = r.get("fase")
        if f in ("5B-fija-single", "5B-fija-cot"):
            fijas[(f, r["problema_id"])] = r["metricas"]["reward"]
    diag = {"control": [], "probe5": []}
    for nombre, fase_p, n_probe, fuente in (
            ("control", "5B-alma-probe", 3, exp5_store),
            ("probe5", FASE_PROBE6, PROBE_N6, store6)):
        tab = {(r["problema_id"], r["arch_id"]): r["metricas"]["reward"]
               for r in fuente.read_all() if r.get("fase") == fase_p}
        for b, _c in enumerate(orden):
            base = b * 12
            r_s = sum(oracle_reward[base + q] - fijas[("5B-fija-single", stream[base + q][1]["id"])]
                      for q in range(12))
            r_c = sum(oracle_reward[base + q] - fijas[("5B-fija-cot", stream[base + q][1]["id"])]
                      for q in range(12))
            mejor = "single" if r_s <= r_c else "cot"
            por_arch = {a: [tab[(stream[base + q][1]["id"], a)]
                            for q in range(n_probe)] for a in ARMS}
            elegido = rx5.probe_choice(por_arch)
            diag[nombre].append(1 if elegido == mejor else 0)
    ac_control = sum(diag["control"])
    ac_probe5 = sum(diag["probe5"])

    pasa = bool(r_probe5 < r_control)
    motivos = [
        f"regret probe5={r_probe5:.4f} vs control probe3={r_control:.4f} "
        f"(diff={r_probe5 - r_control:+.4f})",
        f"acierto del probe por bloque: probe5 {ac_probe5}/10 vs "
        f"control {ac_control}/10",
    ]
    costo_total = sum(budget.gastado.values())
    report = {
        "preregistro": prereg,
        "regret_total": {"control_probe3": round(r_control, 4),
                         "probe5": round(r_probe5, 4)},
        "acierto_probe_por_bloque": {"control": diag["control"],
                                     "probe5": diag["probe5"]},
        "costo_total_usd": round(costo_total, 4),
        "experiencias_nuevas": len(store6),
        "veredicto": {"pasa": pasa, "criterio": CRITERIO_EXP6,
                       "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO ================")
    for m in motivos:
        print("  " + m)
    print(f"  costo llamadas nuevas: ${costo_total:.4f} USD  |  "
          f"{len(store6)} experiencias nuevas  |  {report['duracion_s']}s")
    print("  RESULTADO:", "PASS — el probe más largo decide mejor"
          if pasa else "FAIL — más prueba no compra mejor decisión")
    print("===========================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
