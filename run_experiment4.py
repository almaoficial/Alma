#!/usr/bin/env python3
"""ALMA-EXP4: forward transfer — ¿la experiencia acumulada abarata aprender
en territorio nuevo?

La pregunta H2 honesta. Las fases C de EXP1/EXP2 mostraron que un bandit
global y fijo le gana a uno persistente en un mundo estacionario — como
debe ser. La pregunta real es otra: cuando llega una clase NUEVA, ¿aprender
es más barato si el sistema trae experiencia acumulada?

Diseño: stream de las 10 clases (5 EXP1 + 5 EXP2) en orden aleatorio
(seed 789). Para cada clase k ≥ 2, dos políticas pareadas sobre los mismos
12 problemas en el mismo orden, con los mismos draws de Thompson sampling:

  - cold: bandit con prior uniforme (no sabe nada).
  - warm: bandit con pseudo-observaciones del repertorio acumulado
    (n0=2 por brazo, medias = medias históricas globales por arquitectura).

El repertorio se alimenta con TODAS las observaciones reales (proxy del
oráculo + cold + warm). La clase 1 solo corre cold (siembra el repertorio).

Métrica: regret acumulado vs oráculo en la ventana de exploración
(problemas 1–6), donde el warm-start debería notarse. Secundario: 1–12.

Criterio PRE-REGISTRADO:
  - media(warm − cold en regret 1–6) < 0
  - warm gana en ≥ 5/9 clases

"Ganar" = la experiencia acumulada reduce el costo de aprender lo nuevo.
Si da nulo, el hallazgo también es real: la acumulación ingenua no
transfiere (haría falta transferencia por similitud, como el probe).

Decisiones documentadas:
  - Oráculo proxy = mejor de {single, cot} (10 clases de evidencia de que
    el oráculo siempre cae ahí; medir la matriz 6×12 por clase costaría
    720 llamadas por un refinamiento que no cambia la pregunta).
  - RNG por (clase, problema): random.Random(f"{seed}-{clase}-{i}") idéntico
    para cold y warm → draws pareados y resume-safe.
  - Warm usa medias GLOBALES (no por similitud): es el test más simple de
    "acumular ayuda"; si no alcanza, la conclusión es que hace falta
    transferencia inteligente, no más acumulación.
  - Sin demo de gates: EXP4 no toca el núcleo (gates PASS ×3 ya establecido).

Uso:
    python3 run_experiment4.py --mock
    python3 run_experiment4.py --api
    python3 resume_experiment4.py --out resultados/exp4-20260925
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

rx.NOMBRE_EXPERIMENTO = "ALMA-EXP4: forward transfer (warm vs cold)"

CLASES_EXP1 = ["calculo", "codigo", "qa_multihop", "herramientas", "puzzles"]
CLASES_EXP2 = ["logica", "traduccion", "resumen", "depuracion", "conocimiento"]
CLASES10 = CLASES_EXP1 + CLASES_EXP2

SEED = 789
N0_PSEUDO = 2   # fuerza del prior warm (pseudo-observaciones por brazo)
VENTANA = 6     # problemas donde se mide el regret (exploración)

CRITERIO_EXP4 = {
    "diff_regret_medio_max": 0.0,  # media(warm-cold) < 0 en ventana 1-6
    "min_clases_gana_warm": 5,     # de 9
}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def cargar_todo(base):
    problemas_por_clase, index = {}, {}
    for clase in CLASES_EXP1:
        path = os.path.join(base, "data", f"{clase}.json")
        with open(path, encoding="utf-8") as f:
            probs = json.load(f)
        problemas_por_clase[clase] = probs
        for p in probs:
            index[p["id"]] = p
    for clase in CLASES_EXP2:
        path = os.path.join(base, "data_exp2", f"{clase}.json")
        with open(path, encoding="utf-8") as f:
            probs = json.load(f)
        problemas_por_clase[clase] = probs
        for p in probs:
            index[p["id"]] = p
    return problemas_por_clase, index


def indice_store(store):
    return {(r.get("fase"), r.get("problema_id"), r.get("arch_id")): r
            for r in store.read_all()}


def reconstruir_repertorio(store, clases):
    """Repertorio determinista desde el store: todas las observaciones
    reales (proxy + cold + warm) de las clases dadas. Resume-safe por
    construcción (no hay estado incremental en memoria)."""
    rep = {a: [] for a in rx.list_archs()}
    for r in store.read_all():
        if r.get("fase") in ("4A-oracle", "4B-cold", "4B-warm"):
            pid = r.get("problema_id", "")
            if any(pid.startswith(c + "-") for c in clases):
                rep[r["arch_id"]].append(r["metricas"]["reward"])
    return rep


def oracle_proxy(clase, problemas, backend, evaluator, store, budget):
    """Mejor de {single, cot} por reward medio. Lee el store antes de correr."""
    medias, obs = {}, {}
    for arch in ("single", "cot"):
        rs = []
        for p in problemas:
            idx = indice_store(store)
            row = idx.get(("4A-oracle", p["id"], arch))
            if row is None:
                _res, met = rx.ejecutar_y_evaluar(p, arch, backend, evaluator,
                                                 store, budget, "4A-oracle")
                rs.append(met["reward"])
                obs.setdefault(arch, []).append(met["reward"])
            else:
                rs.append(row["metricas"]["reward"])
        medias[arch] = mean(rs)
    mejor = max(medias, key=lambda a: medias[a])
    return mejor, medias[mejor], medias, obs


def replay(fase, problemas, store):
    """Reconstruye (actualizaciones, recompensas, i0) desde el store.

    actualizaciones: [(arch_id, reward)] en orden de problema.
    i0: primer índice de problema sin filas registradas.
    """
    por_problema = {}
    for r in store.read_all():
        if r.get("fase") == fase:
            por_problema.setdefault(r["problema_id"], []).append(r)
    acts, recs = [], []
    i0 = len(problemas)
    for i, p in enumerate(problemas):
        rows = por_problema.get(p["id"], [])
        if not rows:
            i0 = i
            break
        for r in rows:
            acts.append((r["arch_id"], r["metricas"]["reward"]))
            recs.append(r["metricas"]["reward"])
    return acts, recs, i0


def run_bandit(clase, problemas, bandit, tag, backend, evaluator, store,
               budget, seed):
    """Loop online con Thompson sampling. Resume-safe vía replay + RNG
    determinista por (clase, problema)."""
    fase = f"4B-{tag}"
    acts, recs, i0 = replay(fase, problemas, store)
    for arch_id, reward in acts:
        bandit.update(arch_id, reward)
    for i in range(i0, len(problemas)):
        p = problemas[i]
        rng = random.Random(f"{seed}-{clase}-{i}")
        arch = bandit.select(rng)
        res, met = rx.ejecutar_y_evaluar(p, arch, backend, evaluator,
                                        store, budget, fase)
        if res is None:
            # Lo registró una corrida interrumpida; replay ya lo incorporó.
            row = indice_store(store).get((fase, p["id"], arch))
            assert row is not None
            recs.append(row["metricas"]["reward"])
        else:
            bandit.update(arch, met["reward"])
            recs.append(met["reward"])
    return recs


def bandit_warm(repertorio):
    b = rx.BanditPorClase()
    for a in b.arch_ids:
        rs = repertorio.get(a, [])
        m = mean(rs) if rs else 0.5
        b.alpha[a] = 1.0 + N0_PSEUDO * m
        b.beta[a] = 1.0 + N0_PSEUDO * (1.0 - m)
        b.pulls[a] = N0_PSEUDO
    return b


def main():
    ap = argparse.ArgumentParser(description="ALMA-EXP4: forward transfer")
    ap.add_argument("--mock", action="store_true", default=True)
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "resultados"))
    ap.add_argument("--append", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    if not args.append and os.path.exists(args.out):
        shutil.rmtree(args.out)
    os.makedirs(args.out, exist_ok=True)

    base = os.path.dirname(os.path.abspath(__file__))
    prereg = {
        "experimento": rx.NOMBRE_EXPERIMENTO,
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "criterio_exito": CRITERIO_EXP4,
        "diseno": {
            "clases": CLASES10,
            "orden_seed": args.seed,
            "n0_pseudo": N0_PSEUDO,
            "ventana_regret": VENTANA,
            "oraculo": "proxy mejor-de-{single,cot}",
            "warm": "medias globales del repertorio (no por similitud)",
            "rng": "determinista por (clase, problema), pareado cold/warm",
        },
        "versiones": {
            "alma": rx.ALMA_VERSION,
            "registry": rx.registry.REGISTRY_VERSION,
            "evaluator": rx.evaluator_mod.EVALUATOR_VERSION,
        },
        "seed": args.seed,
        "modo": "api" if args.api else "mock",
    }
    with open(os.path.join(args.out, "preregistro.json"), "w") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito. Criterio: {CRITERIO_EXP4}")

    problemas_por_clase, index = cargar_todo(base)
    n_probs = sum(len(v) for v in problemas_por_clase.values())
    print(f"Datasets: {n_probs} problemas en {len(problemas_por_clase)} clases")

    if args.api:
        backend = rx.VaultBackend()
        print(f"Backend real (vault): {backend.model} vía skill openai")
        limites = {rx.RESOLUCION: 50.0, rx.SELECCION: 1.0, rx.EXPERIMENTACION: 5.0}
    else:
        backend = rx.MockBackend(index, seed=args.seed)
        print("Backend mock (mundo sintético determinista)")
        limites = {rx.RESOLUCION: 10.0, rx.SELECCION: 1.0, rx.EXPERIMENTACION: 5.0}

    evaluator = rx.Evaluator(judge=rx.StubJudge())
    store = rx.ExperienceStore(os.path.join(args.out, "experiencias.jsonl"))
    budget = rx.BudgetManager(limites)
    assert store.verify_chain()

    orden = CLASES10[:]
    random.Random(args.seed).shuffle(orden)
    print(f"Orden del stream: {orden}")

    repertorio = {a: [] for a in rx.list_archs()}
    resultados = {}
    for k, clase in enumerate(orden):
        problemas = problemas_por_clase[clase]
        # El repertorio es lo acumulado en las clases ANTERIORES (resume-safe).
        repertorio = reconstruir_repertorio(store, orden[:k])
        or_arch, or_media, medias_proxy, obs_proxy = oracle_proxy(
            clase, problemas, backend, evaluator, store, budget)

        recs_cold = run_bandit(clase, problemas, rx.BanditPorClase(), "cold",
                               backend, evaluator, store, budget, args.seed)

        entry = {"oraculo_proxy": or_arch,
                 "oraculo_media": round(or_media, 4),
                 "n_repertorio_antes": sum(len(v) for v in repertorio.values())}
        if k == 0:
            entry["nota"] = "siembra del repertorio (solo cold)"
            print(f"   [{k+1}/10] {clase}: oráculo~{or_arch} "
                  f"({or_media:.3f}) — siembra")
        else:
            warm = bandit_warm(repertorio)
            recs_warm = run_bandit(clase, problemas, warm, "warm",
                                   backend, evaluator, store, budget, args.seed)
            reg_cold = sum(or_media - r for r in recs_cold[:VENTANA])
            reg_warm = sum(or_media - r for r in recs_warm[:VENTANA])
            reg_cold12 = sum(or_media - r for r in recs_cold)
            reg_warm12 = sum(or_media - r for r in recs_warm)
            diff = reg_warm - reg_cold
            entry.update({
                "regret_cold_6": round(reg_cold, 4),
                "regret_warm_6": round(reg_warm, 4),
                "regret_cold_12": round(reg_cold12, 4),
                "regret_warm_12": round(reg_warm12, 4),
                "diff_warm_menos_cold": round(diff, 4),
                "gana_warm": bool(diff < 0),
            })
            print(f"   [{k+1}/10] {clase}: oráculo~{or_arch} "
                  f"| regret cold={reg_cold:.3f} warm={reg_warm:.3f} "
                  f"diff={diff:+.3f}")
        resultados[clase] = entry

    diffs = [v["diff_warm_menos_cold"] for v in resultados.values()
             if "diff_warm_menos_cold" in v]
    gana = sum(1 for v in resultados.values() if v.get("gana_warm"))
    dmedio = mean(diffs)
    motivos = [
        f"diff medio de regret (warm-cold, ventana 1-6) = {dmedio:+.4f} "
        f"(criterio < {CRITERIO_EXP4['diff_regret_medio_max']})",
        f"warm gana en {gana}/9 clases "
        f"(mínimo {CRITERIO_EXP4['min_clases_gana_warm']})",
    ]
    pasa = (dmedio < CRITERIO_EXP4["diff_regret_medio_max"]
            and gana >= CRITERIO_EXP4["min_clases_gana_warm"])
    veredicto = {"pasa": pasa, "criterio": CRITERIO_EXP4, "motivos": motivos,
                 "medido": {"diff_regret_medio": round(dmedio, 4),
                            "clases_gana_warm": gana}}

    costo_total = sum(budget.gastado.values())
    report = {
        "preregistro": prereg,
        "orden_stream": orden,
        "por_clase": resultados,
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
    print("  RESULTADO:", "PASS — la experiencia acumulada abarata lo nuevo"
          if pasa else "FAIL — acumular (así) no abarata lo nuevo")
    print("===========================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
