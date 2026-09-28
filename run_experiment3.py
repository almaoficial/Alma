#!/usr/bin/env python3
"""ALMA-EXP3: probe transfer vs blind borrow.

Responde al FAIL de EXP2. Misma distribución (5 clases de data_exp2,
taxonomía v2), mismo protocolo de medición, pero la fase B compara dos
mecanismos de transferencia a clase no vista:

  - blind borrow (réplica de EXP2): pide prestada la política de la clase
    vecina según MAPEO_TRANSFER, a ciegas.
  - probe transfer (nuevo): antes de elegir, gasta un presupuesto chico
    y fijo (N_PROBE problemas × 2 arquitecturas baratas) para MEDIR cuál
    familia encaja con la clase nueva, y recién ahí elige.

Hipótesis: medir barato antes de pedir prestado repara el FAIL de EXP2
(costo disparado por pedir prestado al vecino equivocado).

Criterio PRE-REGISTRADO (nuevo: EXP3 pone a prueba el mecanismo de
transferencia, no la hipótesis de selección de EXP1/EXP2): el MISMO
criterio de EXP1/EXP2, aplicado al probe — reward_ratio >= 0.90,
cost_ratio <= 1.25, supera a la mejor fija global en >= 4/5 clases.
"Reparar" = el probe pasa la vara que el blind no pasó. Los números del
blind se reportan como diagnóstico secundario.

Decisiones documentadas:
  - PROBE_ARCHS = {single, cot}: prior empírico — en 10 clases medidas
    (EXP1+EXP2, fase A real) el oráculo siempre fue single o cot.
    El probe NO conoce el oráculo de la clase nueva: lo estima.
  - Fase A se corre de cero (no se reutiliza el store de EXP2):
    experimento autocontenido; de paso re-mide los oráculos.
  - Fase C (H2) omitida: no es lo que EXP3 pone a prueba.

Uso:
    python3 run_experiment3.py --mock            # validación sin API key
    python3 run_experiment3.py --api             # backend real (Secure Vault)
    python3 resume_experiment3.py --out resultados/exp2-20260925  # retomar
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
import run_experiment2 as rx2  # noqa: F401 — al importar aplica los parches EXP2

rx.NOMBRE_EXPERIMENTO = "ALMA-EXP3: probe transfer vs blind borrow"

# Criterio de éxito/fracaso PRE-REGISTRADO para EXP3 (ver docstring).
# Es el MISMO criterio de EXP1/EXP2, aplicado al probe: "reparar" significa
# que la transferencia por probe pasa la vara que la transferencia ciega
# no pasó. Los números de blind se reportan como diagnóstico secundario.
CRITERIO_EXP3 = {
    "reward_ratio_min": 0.90,    # probe/oráculo en reward medio, 5 clases
    "cost_ratio_max": 1.25,      # probe/oráculo en costo medio
    "min_clases_supera_global": 4,  # clases donde el probe supera a la fija
}

# Presupuesto de medición: problemas × arquitecturas candidatas.
N_PROBE = 3
PROBE_ARCHS = ["single", "cot"]
# Margen para elegir la arquitectura cara: cot solo si supera a single
# por más de MARGEN en el probe. Regularización hacia lo barato: con
# muestras chicas el ruido puede fabricar una "ventaja" mínima de cot
# que después se paga en cost_ratio (el modo de fallo de EXP2).
MARGEN_PROBE = 0.05


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def fase_b3(problemas_por_clase, backend, evaluator, store, budget,
            oraculo, oracle_reward, oracle_cost, seed):
    print("\n== Fase B3: blind-borrow vs probe-transfer (clase no vista) ==")
    filas_a = [r for r in store.read_all() if r.get("fase") == "A"]
    resultados = {}
    for held in rx.CLASES:
        # Bandit entrenado en las 4 clases vistas (igual que EXP1/EXP2).
        selector = rx.SelectorArquitecturas()
        entreno = [r for r in filas_a if r["clase"] != held]
        rng = random.Random(seed)
        rng.shuffle(entreno)
        for r in entreno:
            selector.update(r["clase"], r["arch_id"], r["metricas"]["reward"])

        # --- blind borrow (réplica exacta de EXP2) ---
        b_rw, b_cost = [], []
        for problema in problemas_por_clase[held]:
            pred, _conf, _s = rx.classify(problema["enunciado"])
            vecina = rx.MAPEO_TRANSFER.get(pred, pred)
            if pred == rx.DESCONOCIDA or vecina == held:
                arch = "single"
            else:
                arch = selector.select_greedy(vecina)
            res, met = rx.ejecutar_y_evaluar(problema, arch, backend,
                                            evaluator, store, budget, "B-blind")
            b_rw.append(met["reward"])
            b_cost.append(res["costo_usd"])

        # --- probe transfer: medir barato antes de elegir ---
        sonda = problemas_por_clase[held][:N_PROBE]
        medias = {}
        for arch in PROBE_ARCHS:
            rs = []
            for problema in sonda:
                _res, met = rx.ejecutar_y_evaluar(problema, arch, backend,
                                                 evaluator, store, budget,
                                                 "B-probe")
                rs.append(met["reward"])
            medias[arch] = mean(rs)
        # Desempate y regularización → la barata salvo ventaja clara.
        elegida = ("cot" if medias["cot"] - medias["single"] > MARGEN_PROBE
                   else "single")

        p_rw, p_cost = [], []
        for problema in problemas_por_clase[held]:
            res, met = rx.ejecutar_y_evaluar(problema, elegida, backend,
                                            evaluator, store, budget,
                                            "B-probe-eval")
            p_rw.append(met["reward"])
            p_cost.append(res["costo_usd"])

        o_rw, o_cost = oracle_reward[held], oracle_cost[held]
        b_rr, b_cr = mean(b_rw) / o_rw, mean(b_cost) / o_cost
        p_rr, p_cr = mean(p_rw) / o_rw, mean(p_cost) / o_cost
        resultados[held] = {
            "oraculo": oraculo[held],
            "probe_arch_elegida": elegida,
            "probe_medias": {k: round(v, 4) for k, v in medias.items()},
            "blind": {"reward_ratio": round(b_rr, 4),
                      "cost_ratio": round(b_cr, 4)},
            "probe": {"reward_ratio": round(p_rr, 4),
                      "cost_ratio": round(p_cr, 4)},
            "probe_mas_barato_que_blind": bool(p_cr < b_cr),
        }
        r = resultados[held]
        print(f"   held={held}: oráculo={r['oraculo']} probe→{elegida} "
              f"| blind rr={b_rr:.3f} cr={b_cr:.3f} "
              f"| probe rr={p_rr:.3f} cr={p_cr:.3f} "
              f"más_barato={r['probe_mas_barato_que_blind']}")
    return resultados


def main():
    ap = argparse.ArgumentParser(description="ALMA-EXP3: probe vs blind transfer")
    ap.add_argument("--mock", action="store_true", default=True)
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--seed", type=int, default=456)
    ap.add_argument("--data", default=os.path.join(os.path.dirname(__file__),
                                                   "data_exp2"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "resultados"))
    ap.add_argument("--append", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    if not args.append and os.path.exists(args.out):
        shutil.rmtree(args.out)
    os.makedirs(args.out, exist_ok=True)

    prereg = {
        "experimento": rx.NOMBRE_EXPERIMENTO,
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "criterio_exito": CRITERIO_EXP3,
        "diseno": {
            "n_probe": N_PROBE,
            "probe_archs": PROBE_ARCHS,
            "margen_probe": MARGEN_PROBE,
            "justificacion_probe": ("prior empírico: oráculo siempre en "
                                    "{single, cot} en 10 clases EXP1+EXP2; "
                                    "margen pro-barato: no pagar razonamiento "
                                    "caro por ventajas ruidosas en 3 muestras"),
            "fase_c_omitida": "EXP3 evalúa transferencia, no H2",
        },
        "versiones": {
            "alma": rx.ALMA_VERSION,
            "registry": rx.registry.REGISTRY_VERSION,
            "evaluator": rx.evaluator_mod.EVALUATOR_VERSION,
            "taxonomia": rx.TAXONOMY_VERSION,
        },
        "seed": args.seed,
        "modo": "api" if args.api else "mock",
    }
    with open(os.path.join(args.out, "preregistro.json"), "w") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito. Criterio: {CRITERIO_EXP3}")

    problemas_por_clase, index = rx.cargar_datasets(args.data)
    n_probs = sum(len(v) for v in problemas_por_clase.values())
    print(f"Datasets: {n_probs} problemas "
          f"({', '.join(f'{c}={len(v)}' for c, v in problemas_por_clase.items())})")

    if args.api:
        backend = rx.VaultBackend()
        print(f"Backend real (vault): {backend.model} vía skill openai")
        limites = {rx.RESOLUCION: 50.0, rx.SELECCION: 1.0, rx.EXPERIMENTACION: 5.0}
    else:
        backend = rx.MockBackend(index, seed=args.seed)
        print("Backend mock (mundo sintético determinista)")
        limites = {rx.RESOLUCION: 10.0, rx.SELECCION: 1.0, rx.EXPERIMENTACION: 5.0}

    judge = rx.LLMJudge(backend) if (args.api and args.judge) else rx.StubJudge()
    evaluator = rx.Evaluator(judge=judge)
    store = rx.ExperienceStore(os.path.join(args.out, "experiencias.jsonl"))
    budget = rx.BudgetManager(limites)
    assert store.verify_chain()

    acc = mean([1 if rx.classify(p["enunciado"])[0] == p["clase"] else 0
                for c in rx.CLASES for p in problemas_por_clase[c]])
    print(f"Accuracy del clasificador ({rx.TAXONOMY_VERSION}): {acc:.3f}")

    stats, oraculo, oracle_reward, oracle_cost, mejor_fija = rx.fase_a(
        problemas_por_clase, backend, evaluator, store, budget)
    res_b3 = fase_b3(problemas_por_clase, backend, evaluator, store, budget,
                     oraculo, oracle_reward, oracle_cost, args.seed)
    gates_ok = rx2.demo_gates2(store, stats, oraculo)

    # Veredicto contra el criterio pre-registrado de EXP3 (el original,
    # aplicado al probe).
    rr = mean([v["probe"]["reward_ratio"] for v in res_b3.values()])
    cr = mean([v["probe"]["cost_ratio"] for v in res_b3.values()])
    # supera_global del probe: vs la mejor fija global en la clase held,
    # usando las stats de fase A (igual que EXP1/EXP2).
    glob = {}
    for held in rx.CLASES:
        rewards_fija = [r["metricas"]["reward"] for r in store.read_all()
                        if r.get("fase") == "A" and r["clase"] == held
                        and r["arch_id"] == mejor_fija]
        probe_rw = [r["metricas"]["reward"] for r in store.read_all()
                    if r.get("fase") == "B-probe-eval"
                    and r["problema_id"].startswith(held)]
        glob[held] = mean(probe_rw) > mean(rewards_fija)
    supera = sum(1 for v in glob.values() if v)
    # Diagnóstico secundario: blind borrow (réplica EXP2) con el mismo bar.
    b_rr = mean([v["blind"]["reward_ratio"] for v in res_b3.values()])
    b_cr = mean([v["blind"]["cost_ratio"] for v in res_b3.values()])
    motivos = [
        f"probe reward_ratio medio = {rr:.3f} "
        f"(mínimo {CRITERIO_EXP3['reward_ratio_min']})",
        f"probe cost_ratio medio = {cr:.3f} "
        f"(máximo {CRITERIO_EXP3['cost_ratio_max']})",
        f"probe supera a la mejor fija global en {supera}/5 clases "
        f"(mínimo {CRITERIO_EXP3['min_clases_supera_global']})",
        f"(diagnóstico) blind: reward_ratio={b_rr:.3f} cost_ratio={b_cr:.3f}",
    ]
    pasa = (rr >= CRITERIO_EXP3["reward_ratio_min"]
            and cr <= CRITERIO_EXP3["cost_ratio_max"]
            and supera >= CRITERIO_EXP3["min_clases_supera_global"])
    veredicto = {"pasa": pasa, "criterio": CRITERIO_EXP3, "motivos": motivos,
                 "medido": {"reward_ratio_probe": round(rr, 4),
                            "cost_ratio_probe": round(cr, 4),
                            "clases_supera_global": supera,
                            "blind_reward_ratio": round(b_rr, 4),
                            "blind_cost_ratio": round(b_cr, 4)}}

    costo_total = sum(budget.gastado.values())
    report = {
        "preregistro": prereg,
        "fase_a": {"oraculo": oraculo,
                   "oracle_reward": {k: round(v, 4)
                                     for k, v in oracle_reward.items()},
                   "mejor_fija_global": mejor_fija},
        "fase_b3": res_b3,
        "gates": gates_ok,
        "budget": budget.report(),
        "costo_total_usd": round(costo_total, 4),
        "experiencias": len(store),
        "store_chain_ok": store.verify_chain(),
        "veredicto": veredicto,
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO ================")
    for m in motivos:
        print("  " + m)
    print(f"  costo total: ${costo_total:.4f} USD  |  {len(store)} experiencias  "
          f"|  {report['duracion_s']}s")
    print("  RESULTADO:", "PASS — el probe repara el FAIL de EXP2"
          if pasa else "FAIL — el probe NO repara el FAIL de EXP2")
    print("===========================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
