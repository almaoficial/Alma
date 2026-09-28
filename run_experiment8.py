#!/usr/bin/env python3
"""ALMA-EXP8: enderezar la vara — re-medir el oráculo con 3 intentos.

La honestidad incómoda de EXP5: el oráculo se midió de un solo intento por
(problema, brazo) con temperature 0.2 → la vara contra la que se juzga todo
es ruidosa. EXP8 no inventa nada nuevo: toma 2 intentos más por
(problema, brazo) (fases 8A-oracle-r2/r3; el intento 1 es 5A-oracle),
promedia los 3, y RECALCULA los veredictos de EXP5/6/7 con la vara firme,
sin correr ninguna política de nuevo (sus rewards ya están guardadas).

Criterio PRE-REGISTRADO:
  - EXP5: regret(alma-full) < mejor fija, < thompson-global, y gana >=6/10
    bloques vs mejor fija  → veredicto original: PASS
  - EXP6: regret(probe5) < regret(control probe3)  → original: FAIL
  - EXP7: regret(continuo) < regret(control)  → original: PASS
  Éxito del paso = los 3 veredictos se mantienen con la vara firme.
  Si alguno cambia, ese ES el hallazgo (se reporta, no se esconde).

Costo: 480 llamadas nuevas (~US$0,03). Todo idempotente (resume-safe).

Uso:
    python3 run_experiment8.py --mock
    python3 run_experiment8.py --api
"""
import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_experiment as rx
import run_experiment5 as rx5
from run_experiment6 import control_rewards

rx.NOMBRE_EXPERIMENTO = "ALMA-EXP8: oráculo de 3 intentos (enderezar la vara)"

ARMS = ["single", "cot"]
FASE_R2 = "8A-oracle-r2"
FASE_R3 = "8A-oracle-r3"
SHOTS = (("5A-oracle", "exp5"), (FASE_R2, "exp8"), (FASE_R3, "exp8"))


def mean(xs):
    return sum(xs) / len(xs)


def hechos_de(store):
    h = {}
    for r in store.read_all():
        h[(r.get("fase"), r.get("problema_id"), r.get("arch_id"))] = \
            r["metricas"]["reward"]
    return h


def medir_oraculo_extra(stream, pull):
    """Toma los intentos 2 y 3 del oráculo. Idempotente vía pull."""
    for fase in (FASE_R2, FASE_R3):
        for _pos, (_clase, p) in enumerate(stream):
            for arch in ARMS:
                pull(p, arch, fase)


def replay_fija_thompson(exp5_hechos, fase, stream):
    return {pos: exp5_hechos[(fase, p["id"], a)]
            for pos, (_c, p) in enumerate(stream)
            for a in ARMS if (fase, p["id"], a) in exp5_hechos}


def replay_exp6_probe5(stream, orden, h6):
    rewards = {}
    for b in range(len(orden)):
        base = b * 12
        prs = {(q, a): h6[("6B-alma-probe", stream[base + q][1]["id"], a)]
               for q in range(5) for a in ARMS}
        elegido = rx5.probe_choice(
            {a: [prs[(q, a)] for q in range(5)] for a in ARMS})
        for q in range(5):
            rewards[base + q] = prs[(q, elegido)]
        for q in range(5, 12):
            pid = stream[base + q][1]["id"]
            for a in ARMS:
                if ("6B-alma-full", pid, a) in h6:
                    rewards[base + q] = h6[("6B-alma-full", pid, a)]
                    break
    return rewards


def replay_exp7_continuo(stream, orden, h7):
    Q1, Q2 = (0, 1, 2), (6, 7)
    rewards = {}
    for b in range(len(orden)):
        base = b * 12
        prs = {(q, a): h7[("7B-alma-probe", stream[base + q][1]["id"], a)]
               for q in Q1 for a in ARMS}
        e1 = rx5.probe_choice(
            {a: [prs[(q, a)] for q in Q1] for a in ARMS})
        for q in Q1:
            rewards[base + q] = prs[(q, e1)]
        prs2 = {(q, a): h7[("7B-alma-probe", stream[base + q][1]["id"], a)]
                for q in Q2 for a in ARMS}
        todo = dict(prs)
        todo.update(prs2)
        e2 = rx5.probe_choice(
            {a: [todo[(q, a)] for q in Q1 + Q2] for a in ARMS})
        for q in Q2:
            rewards[base + q] = todo[(q, e2)]
        for q in (3, 4, 5, 8, 9, 10, 11):
            pid = stream[base + q][1]["id"]
            for a in ARMS:
                if ("7B-alma-full", pid, a) in h7:
                    rewards[base + q] = h7[("7B-alma-full", pid, a)]
                    break
    return rewards


def main():
    ap = argparse.ArgumentParser(description="ALMA-EXP8: oráculo de 3 intentos")
    ap.add_argument("--mock", action="store_true", default=True)
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--seed", type=int, default=999)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "resultados", "exp8-20260926"))
    ap.add_argument("--append", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    if not args.append and os.path.exists(args.out):
        shutil.rmtree(args.out)
    os.makedirs(args.out, exist_ok=True)

    base = os.path.dirname(os.path.abspath(__file__))
    exp5_out = os.path.join(base, "resultados", "exp5-20260926")
    exp6_out = os.path.join(base, "resultados", "exp6-20260926")
    exp7_out = os.path.join(base, "resultados", "exp7-20260926")

    prereg = {
        "experimento": rx.NOMBRE_EXPERIMENTO,
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "criterio_exito": {
            "exp5_mantiene_pass": True,
            "exp6_mantiene_fail": True,
            "exp7_mantiene_pass": True,
        },
        "diseno": {
            "oraculo": "3 intentos por (problema, brazo): 5A-oracle + "
                       "8A-oracle-r2 + 8A-oracle-r3; vara = max sobre brazos "
                       "del promedio de 3",
            "politicas": "replay de datos guardados, 0 llamadas nuevas",
            "stream": "reutilizado de EXP5: 10 clases x 12, seed 999",
        },
        "seed": args.seed,
        "modo": "api" if args.api else "mock",
    }
    with open(os.path.join(args.out, "preregistro.json"), "w") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito. Criterio: {prereg['criterio_exito']}")

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
    exp5_store = rx.ExperienceStore(os.path.join(exp5_out, "experiencias.jsonl"))
    store8 = rx.ExperienceStore(os.path.join(args.out, "experiencias.jsonl"))
    budget = rx.BudgetManager(limites)
    pull, _hechos8 = rx5.make_puller(store8, backend, evaluator, budget)

    print("Midiendo intentos 2 y 3 del oráculo (480 llamadas)...")
    tpol = time.time()
    medir_oraculo_extra(stream, pull)
    print(f"   oráculo completo ({time.time() - tpol:.0f}s)")

    # Vara firme: promedio de 3 intentos por (problema, brazo).
    h5 = hechos_de(exp5_store)
    h8 = hechos_de(store8)
    fuentes = {"exp5": h5, "exp8": h8}
    oracle3 = {}
    for _pos, (_c, p) in enumerate(stream):
        for a in ARMS:
            tiros = [fuentes[donde][(fase, p["id"], a)] for fase, donde in SHOTS]
            assert len(tiros) == 3, f"faltan tiros para {p['id']}/{a}"
            oracle3[(p["id"], a)] = mean(tiros)
    oracle_reward = {pos: max(oracle3[(p["id"], a)] for a in ARMS)
                     for pos, (_c, p) in enumerate(stream)}

    # Dispersión del intento único vs el promedio (cuán ruidosa era la vara).
    import statistics
    desvios = []
    for _pos, (_c, p) in enumerate(stream):
        for a in ARMS:
            tiros = [fuentes[d][(f, p["id"], a)] for f, d in SHOTS]
            if statistics.pstdev(tiros) > 0 or len(set(tiros)) > 1:
                desvios.append(statistics.pstdev(tiros))
    print(f"   vara vieja (1 intento): dispersión media entre intentos = "
          f"{mean(desvios) if desvios else 0:.4f} "
          f"({len(desvios)}/240 celdas con variación)")

    # Replay de políticas (0 llamadas nuevas).
    h6 = hechos_de(rx.ExperienceStore(
        os.path.join(exp6_out, "experiencias.jsonl")))
    h7 = hechos_de(rx.ExperienceStore(
        os.path.join(exp7_out, "experiencias.jsonl")))
    politicas = {
        "fija-single": replay_fija_thompson(h5, "5B-fija-single", stream),
        "fija-cot": replay_fija_thompson(h5, "5B-fija-cot", stream),
        "thompson-global": replay_fija_thompson(h5, "5B-thompson-global", stream),
        "alma-full": control_rewards(exp5_store, stream, orden),
        "exp6-probe5": replay_exp6_probe5(stream, orden, h6),
        "exp6-control": control_rewards(exp5_store, stream, orden),
        "exp7-continuo": replay_exp7_continuo(stream, orden, h7),
        "exp7-control": control_rewards(exp5_store, stream, orden),
    }
    for nombre, rw in politicas.items():
        assert len(rw) == 120, f"{nombre}: {len(rw)} != 120"

    regret = {n: {pos: oracle_reward[pos] - rw[pos] for pos in range(120)}
              for n, rw in politicas.items()}
    tot = {n: sum(r.values()) for n, r in regret.items()}

    def bloques_ganados(nom, vs):
        g = 0
        for b in range(10):
            base = b * 12
            if sum(regret[nom][base + q] for q in range(12)) < \
               sum(regret[vs][base + q] for q in range(12)):
                g += 1
        return g

    # Re-evaluar los 3 criterios originales con la vara firme.
    mejor_fija = min(tot["fija-single"], tot["fija-cot"])
    bf = "fija-single" if tot["fija-single"] <= tot["fija-cot"] else "fija-cot"
    exp5_pass = bool(tot["alma-full"] < mejor_fija
                     and tot["alma-full"] < tot["thompson-global"]
                     and bloques_ganados("alma-full", bf) >= 6)
    exp6_fail_mantiene = bool(tot["exp6-probe5"] >= tot["exp6-control"])
    exp7_pass = bool(tot["exp7-continuo"] < tot["exp7-control"])

    detalle = {
        "exp5": {
            "veredicto_original": "PASS", "veredicto_nuevo":
            "PASS" if exp5_pass else "FAIL",
            "regret": {n: round(tot[n], 4) for n in
                       ("alma-full", "fija-single", "fija-cot",
                        "thompson-global")},
            "bloques_ganados_vs_mejor_fija":
            bloques_ganados("alma-full", bf),
        },
        "exp6": {
            "veredicto_original": "FAIL", "veredicto_nuevo":
            "FAIL" if exp6_fail_mantiene else "PASS",
            "regret": {n: round(tot[n], 4) for n in
                       ("exp6-probe5", "exp6-control")},
        },
        "exp7": {
            "veredicto_original": "PASS", "veredicto_nuevo":
            "PASS" if exp7_pass else "FAIL",
            "regret": {n: round(tot[n], 4) for n in
                       ("exp7-continuo", "exp7-control")},
        },
    }
    exito = bool(exp5_pass and exp6_fail_mantiene and exp7_pass)
    motivos = [
        f"EXP5: {detalle['exp5']['veredicto_original']} → "
        f"{detalle['exp5']['veredicto_nuevo']} "
        f"(alma-full {tot['alma-full']:.2f} vs mejor fija {mejor_fija:.2f})",
        f"EXP6: {detalle['exp6']['veredicto_original']} → "
        f"{detalle['exp6']['veredicto_nuevo']} "
        f"(probe5 {tot['exp6-probe5']:.2f} vs control {tot['exp6-control']:.2f})",
        f"EXP7: {detalle['exp7']['veredicto_original']} → "
        f"{detalle['exp7']['veredicto_nuevo']} "
        f"(continuo {tot['exp7-continuo']:.2f} vs control "
        f"{tot['exp7-control']:.2f})",
    ]
    costo_total = sum(budget.gastado.values())
    report = {
        "preregistro": prereg,
        "vara": {
            "intentos_por_celda": 3,
            "celdas_con_variacion": len(desvios),
            "dispersion_media_entre_intentos":
            round(mean(desvios), 4) if desvios else 0.0,
        },
        "re_evaluacion": detalle,
        "costo_total_usd": round(costo_total, 4),
        "experiencias_nuevas": len(store8),
        "veredicto": {"pasa": exito,
                       "criterio": prereg["criterio_exito"],
                       "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO ================")
    for m in motivos:
        print("  " + m)
    print(f"  costo llamadas nuevas: ${costo_total:.4f} USD  |  "
          f"{len(store8)} experiencias nuevas  |  {report['duracion_s']}s")
    print("  RESULTADO:", "PASS — los 3 veredictos se mantienen con la vara "
          "firme" if exito else "HALLAZGO — algún veredicto cambió con la "
          "vara firme (ver detalle)")
    print("===========================================")
    return 0 if exito else 1


if __name__ == "__main__":
    sys.exit(main())
