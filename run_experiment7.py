#!/usr/bin/env python3
"""ALMA-EXP7: probe continuo — ¿re-espiar a mitad de bloque corrige el sesgo?

EXP6 refutó "más muestras = mejor decisión": el probe-5 eligió los mismos
brazos que el probe-3 (7/10). El análisis posterior mostró el sesgo
sistemático: en 9/10 bloques el probe mide empate (single≈cot, margen -0.01)
y la regla (cot solo si gana por >0.05) defaultea a single; en 3 bloques la
verdad era cot y el probe se quedó con single. Los primeros 3 problemas no
representan al bloque.

Diseño: mismo stream de 120 problemas (seed 999) y mismo oráculo de EXP5
(5A-oracle; 0 llamadas nuevas). Dos políticas:
  1. control: alma-full EXP5, probe frontal de 3 (replay, 0 llamadas).
  2. probe-continuo: espía 3 problemas al inicio (q=0,1,2) y re-espía 2 a
     mitad de bloque (q=6,7); decide con la regla de margen (>0.05) primero
     con 3 y después con los 5 acumulados, y puede CAMBIAR de brazo.
     Válido en streaming: no ve el futuro, solo reparte la exploración.

Resto idéntico: bandit por clase, warm-start repertorio hacia adelante
(5A-oracle + fases 7B propias, n0=2), Thompson en problemas no-probe con
RNG pareado por posición (seed 999).

Criterio PRE-REGISTRADO (PASS):
  - regret(probe-continuo) < regret(control)
Diagnóstico: cambios de decisión por bloque tras el re-probe, y acierto
final vs mejor brazo fijo del bloque (medido en 5B).

Uso:
    python3 run_experiment7.py --mock
    python3 run_experiment7.py --api
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
from run_experiment6 import control_rewards  # noqa: F401

rx.NOMBRE_EXPERIMENTO = "ALMA-EXP7: probe continuo (re-probe mitad de bloque)"

ARMS = ["single", "cot"]
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (6, 7)
FASE_PROBE7 = "7B-alma-probe"
FASE_FULL7 = "7B-alma-full"
FASES7 = (FASE_PROBE7, FASE_FULL7)

CRITERIO_EXP7 = {
    "gana_a_control": True,   # regret(continuo) < regret(probe3 de EXP5)
}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def repertorio7(exp5_store, store7, stream, pos_limite):
    pos_de_pid = {p["id"]: i for i, (_c, p) in enumerate(stream)}
    rep = {a: [] for a in ARMS}
    for r in exp5_store.read_all():
        if r.get("fase") != "5A-oracle":
            continue
        if r.get("arch_id") not in ARMS:
            continue
        if pos_de_pid.get(r.get("problema_id", ""), 10 ** 9) < pos_limite:
            rep[r["arch_id"]].append(r["metricas"]["reward"])
    for r in store7.read_all():
        if r.get("fase") not in FASES7:
            continue
        if r.get("arch_id") not in ARMS:
            continue
        if pos_de_pid.get(r.get("problema_id", ""), 10 ** 9) < pos_limite:
            rep[r["arch_id"]].append(r["metricas"]["reward"])
    return rep


def correr_continuo(stream, orden, pull, hechos, exp5_store, store7, seed):
    """Probe en q=0,1,2 y re-probe en q=6,7; la decisión puede cambiar.
    Idempotente vía pull."""
    rewards = {}
    switches = {}

    def fila_full(pid):
        for a in ARMS:
            if (FASE_FULL7, pid, a) in hechos:
                return a, hechos[(FASE_FULL7, pid, a)]
        return None

    def probe_q(qs):
        """{(q,a): reward} para qs: rehidrata del store lo existente y
        pullea lo faltante. Un bandit.update por observación (como EXP5)."""
        prs = {}
        for q in qs:
            pid = stream[base + q][1]["id"]
            for a in ARMS:
                if (FASE_PROBE7, pid, a) in hechos:
                    prs[(q, a)] = hechos[(FASE_PROBE7, pid, a)]
                    bandit.update(a, prs[(q, a)])
        for q in qs:
            qp = stream[base + q][1]
            for arch in ARMS:
                if (q, arch) not in prs:
                    r, nuevo = pull(qp, arch, FASE_PROBE7)
                    prs[(q, arch)] = r
                    if nuevo:
                        bandit.update(arch, r)
        return prs

    def thompson_q(qs):
        for q in qs:
            pos = base + q
            p = stream[pos][1]
            hit = fila_full(p["id"])
            if hit is not None:
                arch, r = hit
                bandit.update(arch, r)
                rewards[pos] = r
                continue
            rng = random.Random(f"{seed}-exp7-{pos}")
            arch = bandit.select(rng)
            r, nuevo = pull(p, arch, FASE_FULL7)
            if nuevo:
                bandit.update(arch, r)
            rewards[pos] = r

    for b, _clase in enumerate(orden):
        base = b * 12
        rep = repertorio7(exp5_store, store7, stream, base)
        bandit = rx5.bandit_warm(rep)

        # Probe inicial q=0,1,2 → primera decisión.
        prs = probe_q(PROBE_Q1)
        por_arch = {a: [prs[(q, a)] for q in PROBE_Q1] for a in ARMS}
        elegido1 = rx5.probe_choice(por_arch)
        for q in PROBE_Q1:
            rewards[base + q] = prs[(q, elegido1)]

        # Thompson q=3,4,5.
        thompson_q((3, 4, 5))

        # Re-probe q=6,7 → re-decisión con los 5 acumulados.
        prs2 = probe_q(PROBE_Q2)
        todo = dict(prs)
        todo.update(prs2)
        qs_all = PROBE_Q1 + PROBE_Q2
        por_arch2 = {a: [todo[(q, a)] for q in qs_all] for a in ARMS}
        elegido2 = rx5.probe_choice(por_arch2)
        switches[b] = (elegido1, elegido2)
        for q in PROBE_Q2:
            rewards[base + q] = todo[(q, elegido2)]

        # Thompson q=8..11.
        thompson_q((8, 9, 10, 11))
    return rewards, switches


def main():
    ap = argparse.ArgumentParser(description="ALMA-EXP7: probe continuo")
    ap.add_argument("--mock", action="store_true", default=True)
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--seed", type=int, default=999)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "resultados", "exp7-20260926"))
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
        "criterio_exito": CRITERIO_EXP7,
        "diseno": {
            "stream": "reutilizado de EXP5: 10 clases x 12, seed 999",
            "oraculo": "reutilizado de EXP5 (fase 5A-oracle), 0 llamadas",
            "control": "alma-full EXP5 probe frontal de 3 (replay, 0 llamadas)",
            "tratamiento": "probe continuo: espía q=0,1,2 y re-espía q=6,7; "
                           "la decisión puede cambiar; fases 7B",
            "rng": "pareado por posición (seed 999)",
        },
        "seed": args.seed,
        "modo": "api" if args.api else "mock",
    }
    with open(os.path.join(args.out, "preregistro.json"), "w") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito. Criterio: {CRITERIO_EXP7}")

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
    store7 = rx.ExperienceStore(os.path.join(args.out, "experiencias.jsonl"))
    budget = rx.BudgetManager(limites)

    oracle_reward = {}
    o5 = {}
    for r in exp5_store.read_all():
        if r.get("fase") == "5A-oracle":
            o5[(r["problema_id"], r["arch_id"])] = r["metricas"]["reward"]
    for pos, (_c, p) in enumerate(stream):
        rs = {a: o5[(p["id"], a)] for a in ARMS}
        oracle_reward[pos] = max(rs.values())
    assert len(oracle_reward) == 120

    pull, hechos = rx5.make_puller(store7, backend, evaluator, budget)

    print("Control (replay EXP5, probe frontal de 3)...")
    rew_control = control_rewards(exp5_store, stream, orden)
    print("Tratamiento (probe continuo, fases 7B)...")
    tpol = time.time()
    rew_cont, switches = correr_continuo(stream, orden, pull, hechos,
                                          exp5_store, store7, args.seed)
    assert len(rew_cont) == 120
    print(f"   continuo completo ({time.time() - tpol:.0f}s)")

    reg = {n: {pos: oracle_reward[pos] - rw[pos] for pos in range(120)}
           for n, rw in (("control", rew_control), ("continuo", rew_cont))}
    r_control = sum(reg["control"].values())
    r_cont = sum(reg["continuo"].values())

    # Diagnóstico: verdad por bloque (mejor fijo 5B) y decisión final.
    fijas = {}
    for r in exp5_store.read_all():
        f = r.get("fase")
        if f in ("5B-fija-single", "5B-fija-cot"):
            fijas[(f, r["problema_id"])] = r["metricas"]["reward"]
    tab7 = {(r["problema_id"], r["arch_id"]): r["metricas"]["reward"]
            for r in store7.read_all() if r.get("fase") == FASE_PROBE7}
    diag = []
    n_switch = 0
    for b, _c in enumerate(orden):
        base = b * 12
        r_s = sum(oracle_reward[base + q] - fijas[("5B-fija-single", stream[base + q][1]["id"])]
                  for q in range(12))
        r_c = sum(oracle_reward[base + q] - fijas[("5B-fija-cot", stream[base + q][1]["id"])]
                  for q in range(12))
        mejor = "single" if r_s <= r_c else "cot"
        e1, e2 = switches[b]
        if e1 != e2:
            n_switch += 1
        diag.append({"bloque": b, "verdad": mejor, "inicial": e1,
                     "final": e2, "cambio": e1 != e2,
                     "acierto_final": e2 == mejor})

    pasa = bool(r_cont < r_control)
    motivos = [
        f"regret continuo={r_cont:.4f} vs control={r_control:.4f} "
        f"(diff={r_cont - r_control:+.4f})",
        f"cambios de decisión tras re-probe: {n_switch}/10 bloques; "
        f"acierto final {sum(d['acierto_final'] for d in diag)}/10",
    ]
    costo_total = sum(budget.gastado.values())
    report = {
        "preregistro": prereg,
        "regret_total": {"control_probe3": round(r_control, 4),
                         "continuo": round(r_cont, 4)},
        "diagnostico_bloques": diag,
        "costo_total_usd": round(costo_total, 4),
        "experiencias_nuevas": len(store7),
        "veredicto": {"pasa": pasa, "criterio": CRITERIO_EXP7,
                       "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO ================")
    for m in motivos:
        print("  " + m)
    print(f"  costo llamadas nuevas: ${costo_total:.4f} USD  |  "
          f"{len(store7)} experiencias nuevas  |  {report['duracion_s']}s")
    print("  RESULTADO:", "PASS — re-espiar corrige el sesgo"
          if pasa else "FAIL — ni repartiendo la exploración se corrige")
    print("===========================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
