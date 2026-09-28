#!/usr/bin/env python3
"""ALMA — Experimento 1: la prueba de la selección (sección 6 del informe).

Corre end-to-end el protocolo mínimo:
  - Pre-registro (criterio de éxito/fracaso ANTES de correr).
  - Fase A: matriz completa 5 clases × 6 arquitecturas → oráculo por clase.
  - Fase B: leave-one-class-out — el selector entrena en 4 clases y se
    evalúa en la 5ta (transferencia a clase no vista vía clase vecina).
  - Fase C (H2): persistente vs reiniciada vs fija_global vs prior_manual;
    curva de regret acumulado en llegada secuencial.
  - Demo de safety gates (privilegios + rollback).
  - Veredicto contra el criterio pre-registrado.

Uso:
    python run_experiment.py --mock            # mundo sintético, sin API key
    python run_experiment.py --api             # backend real (credencial del Secure Vault)
    python run_experiment.py --mock --seed 7 --out resultados2
"""

import argparse
import json
import os
import random
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma import __version__ as ALMA_VERSION
from alma import registry, evaluator as evaluator_mod, featurizer
from alma.backends import MockBackend, OpenAICompatBackend, VaultBackend, BackendError
from alma.budget import BudgetManager, RESOLUCION, SELECCION, EXPERIMENTACION
from alma.evaluator import Evaluator, StubJudge, LLMJudge
from alma.executors import ejecutar
from alma.experimenter import Experimenter
from alma.featurizer import CLASES, DESCONOCIDA, classify, TAXONOMY_VERSION
from alma.gates import SafetyGates, ReadOnlyStore, PrivilegeError
from alma.registry import list_archs, recomendada_para, REGISTRY_VERSION
from alma.selector import SelectorArquitecturas, BanditPorClase
from alma.store import ExperienceStore

# Nombre del experimento (lo usa el pre-registro). EXP2 lo sobrescribe
# al importar este módulo: el criterio NO se toca (replicación).
NOMBRE_EXPERIMENTO = "ALMA-EXP1: la prueba de la selección"

# Criterio de éxito/fracaso PRE-REGISTRADO.
# Calibrado durante el pilotaje en mock (seeds 42/7): el clasificador al 95%
# genera ~5% de rutas caras por mala clasificación → cost_ratio estructural
# ≈ 1.05; el umbral 1.25 rechaza selectores derrochadores (p. ej. siempre
# debate ≈ 2.5) y da margen al ruido de costos del mock. CONGELADO antes
# del primer run con API real: no se toca después.
CRITERIO = {
    "reward_ratio_min": 0.90,   # selector/oráculo en reward medio, promedio 5 folds
    "cost_ratio_max": 1.25,     # selector/oráculo en costo medio
    "min_clases_supera_global": 4,  # folds donde supera a la mejor fija global
}

# Transferencia leave-one-class-out: para cada clase, la clase VISTA más
# parecida, de la que el selector pide prestada la política cuando enfrenta
# una clase sin experiencia. Decisión de diseño documentada (no aprendida).
MAPEO_TRANSFER = {
    "calculo": "qa_multihop",    # preguntas que se responden razonando
    "qa_multihop": "calculo",
    "codigo": "herramientas",    # tareas imperativas/procedurales
    "herramientas": "codigo",
    "puzzles": "herramientas",   # imperativo + números, sin código
}


# ---------------------------------------------------------------- utilidades

def cargar_datasets(data_dir):
    problemas_por_clase, index = {}, {}
    for clase in CLASES:
        path = os.path.join(data_dir, f"{clase}.json")
        with open(path, encoding="utf-8") as f:
            probs = json.load(f)
        problemas_por_clase[clase] = probs
        for p in probs:
            index[p["id"]] = p
    return problemas_por_clase, index


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def ejecutar_y_evaluar(problema, arch_id, backend, evaluator, store, budget, fase):
    res = ejecutar(arch_id, problema, backend)
    met = evaluator.score(problema, res["respuesta"], arch_id, traza=res["traza"])
    budget.charge(RESOLUCION, res["costo_usd"], f"{fase}:{problema['id']}:{arch_id}")
    store.append({
        "problema_id": problema["id"],
        "features": featurizer.featurize(problema["enunciado"]),
        "clase": problema["clase"],
        "arch_id": arch_id,
        "config": registry.get_arch(arch_id)["parametros"],
        "respuesta": res["respuesta"][:2000],
        "traza": res["traza"],
        "metricas": met,
        "costo_usd": round(res["costo_usd"], 6),
        "fase": fase,
    })
    return res, met


# ---------------------------------------------------------------- Fase A

def fase_a(problemas_por_clase, backend, evaluator, store, budget):
    print("\n== Fase A: matriz completa 5 clases × 6 arquitecturas ==")
    for clase in CLASES:
        for problema in problemas_por_clase[clase]:
            for arch in list_archs():
                ejecutar_y_evaluar(problema, arch, backend, evaluator, store, budget, "A")
    print(f"   {len(store)} experiencias registradas.")

    stats = {c: {a: {"reward": [], "costo": [], "exito": []} for a in list_archs()}
             for c in CLASES}
    for row in store.read_all():
        if row.get("fase") != "A":
            continue
        s = stats[row["clase"]][row["arch_id"]]
        s["reward"].append(row["metricas"]["reward"])
        s["costo"].append(row["costo_usd"])
        s["exito"].append(row["metricas"]["exito"])

    oraculo, oracle_reward, oracle_cost = {}, {}, {}
    for clase in CLASES:
        # argmax reward medio; desempate por menor costo
        mejor = max(
            list_archs(),
            key=lambda a: (mean(stats[clase][a]["reward"]),
                           -mean(stats[clase][a]["costo"])),
        )
        oraculo[clase] = mejor
        oracle_reward[clase] = mean(stats[clase][mejor]["reward"])
        oracle_cost[clase] = mean(stats[clase][mejor]["costo"])
        print(f"   oráculo[{clase}] = {mejor} "
              f"(reward {oracle_reward[clase]:.3f}, costo ${oracle_cost[clase]:.5f})")

    # Mejor arquitectura fija global: mejor reward medio en TODOS los problemas.
    glob = {a: [] for a in list_archs()}
    for clase in CLASES:
        for a in list_archs():
            glob[a].extend(stats[clase][a]["reward"])
    mejor_fija = max(list_archs(), key=lambda a: mean(glob[a]))
    print(f"   mejor fija global = {mejor_fija} (reward {mean(glob[mejor_fija]):.3f})")
    return stats, oraculo, oracle_reward, oracle_cost, mejor_fija


# ---------------------------------------------------------------- Fase B

def fase_b(problemas_por_clase, backend, evaluator, store, budget,
           oraculo, oracle_reward, oracle_cost, mejor_fija, stats, seed):
    print("\n== Fase B: leave-one-class-out (transferencia a clase no vista) ==")
    filas_a = [r for r in store.read_all() if r.get("fase") == "A"]
    resultados = {}
    for held in CLASES:
        selector = SelectorArquitecturas()
        entreno = [r for r in filas_a if r["clase"] != held]
        rng = random.Random(seed)
        rng.shuffle(entreno)
        for r in entreno:  # replay batch de la experiencia (offline)
            selector.update(r["clase"], r["arch_id"], r["metricas"]["reward"])

        sel_rewards, sel_costos, aciertos, vias = [], [], [], []
        for problema in problemas_por_clase[held]:
            # La taxonomía es fija (infraestructura, no aprende): clasifica con
            # las 5 clases aunque el bandit no tenga experiencia en `held`.
            # La transferencia pide prestada la política de la clase vista
            # más parecida (MAPEO_TRANSFER).
            pred, conf, _scores = classify(problema["enunciado"])
            vecina = MAPEO_TRANSFER.get(pred, pred)
            if pred == DESCONOCIDA or vecina == held:
                # Ante incertidumbre total, gastar lo mínimo (minimax de costo).
                arch, via = "single", "fallback:single"
            else:
                arch, via = selector.select_greedy(vecina), f"transfer:{vecina}"
            res, met = ejecutar_y_evaluar(problema, arch, backend, evaluator,
                                          store, budget, "B")
            sel_rewards.append(met["reward"])
            sel_costos.append(res["costo_usd"])
            aciertos.append(1 if arch == oraculo[held] else 0)
            vias.append(via)

        glob_reward_held = mean(stats[held][mejor_fija]["reward"])
        resultados[held] = {
            "sel_reward": round(mean(sel_rewards), 4),
            "sel_cost": round(mean(sel_costos), 6),
            "oracle_reward": round(oracle_reward[held], 4),
            "oracle_cost": round(oracle_cost[held], 6),
            "selection_accuracy": round(mean(aciertos), 3),
            "reward_ratio": round(mean(sel_rewards) / oracle_reward[held], 4)
            if oracle_reward[held] else 0.0,
            "cost_ratio": round(mean(sel_costos) / oracle_cost[held], 4)
            if oracle_cost[held] else 0.0,
            "supera_global": bool(mean(sel_rewards) > glob_reward_held),
            "via_tipica": max(set(vias), key=vias.count),
        }
        r = resultados[held]
        print(f"   held={held}: sel_acc={r['selection_accuracy']:.2f} "
              f"reward_ratio={r['reward_ratio']:.3f} cost_ratio={r['cost_ratio']:.3f} "
              f"supera_global={r['supera_global']} ({r['via_tipica']})")
    return resultados


# ---------------------------------------------------------------- Fase C (H2)

def fase_c(problemas_por_clase, backend, evaluator, store, budget,
           oracle_reward, mejor_fija, seed):
    print("\n== Fase C (H2): persistente vs reiniciada vs fija_global vs prior_manual ==")
    todos = [p for c in CLASES for p in problemas_por_clase[c]]
    rng = random.Random(seed + 1)
    rng.shuffle(todos)

    def correr(politica):
        """persistente: bandit Thompson por clase, memoria en todo el run.
        reiniciada: bandit que se resetea en cada cambio de clase (olvida).
        fija_global: la mejor arquitectura fija de Fase A (sin memoria,
            sin siquiera usar la clase del problema).
        prior_manual: diseño manual clase→arquitectura (usa la taxonomía,
            pero no aprende de la experiencia)."""
        curvas, regret_acum = [], 0.0
        sel = SelectorArquitecturas() if politica == "persistente" else None
        bandit_actual, clase_actual = None, None
        for problema in todos:
            verdadera = problema["clase"]
            pred, _conf, _s = classify(problema["enunciado"])
            clase_sel = pred if pred != DESCONOCIDA else verdadera
            if politica == "persistente":
                arch = sel.select(clase_sel, rng)
            elif politica == "reiniciada":
                if verdadera != clase_actual:
                    bandit_actual, clase_actual = BanditPorClase(), verdadera
                arch = bandit_actual.select(rng)
            elif politica == "fija_global":
                arch = mejor_fija
            else:  # prior_manual
                arch = recomendada_para(clase_sel)
            res, met = ejecutar_y_evaluar(problema, arch, backend, evaluator,
                                          store, budget, f"C-{politica}")
            # Update con la clase VERDADERA (como si un humano la auditara;
            # ver README: simplificación documentada).
            if politica == "persistente":
                sel.update(verdadera, arch, met["reward"])
            elif politica == "reiniciada":
                bandit_actual.update(arch, met["reward"])
            regret_acum += oracle_reward[verdadera] - met["reward"]
            curvas.append(round(regret_acum, 4))
        return curvas

    curvas = {p: correr(p) for p in ("persistente", "reiniciada",
                                    "fija_global", "prior_manual")}
    for p, c in curvas.items():
        print(f"   {p}: regret acumulado final = {c[-1]:.3f}")
    return curvas


# ---------------------------------------------------------------- gates demo

def demo_gates(store, stats, oraculo):
    print("\n== Demo de safety gates ==")
    gates = SafetyGates()
    assert gates.verificar_nucleo(), "el núcleo cambió: abortar"
    print("   núcleo fijo intacto (registry/evaluator/taxonomía)")

    ro = ReadOnlyStore(store)
    try:
        ro.append({"problema_id": "x"})
        raise AssertionError("ReadOnlyStore permitió escribir: ¡fallo!")
    except PrivilegeError:
        print("   separación de privilegios: el selector no puede escribir en el store")
    except AssertionError:
        raise

    # Entrenar selector con toda la fase A y medir regret por clase.
    sel = SelectorArquitecturas()
    for r in store.read_all():
        if r.get("fase") == "A":
            sel.update(r["clase"], r["arch_id"], r["metricas"]["reward"])

    def regret_por_clase(s):
        out = {}
        for c in CLASES:
            pick = s.select_greedy(c)
            or_rw = mean(stats[c][oraculo[c]]["reward"])
            out[c] = round(or_rw - mean(stats[c][pick]["reward"]), 4)
        return out

    viejo = regret_por_clase(sel)
    snap = sel.snapshot()
    # Simular mala actualización: envenenar el brazo que el greedy
    # actualmente prefiere en 'calculo' (el que la política usaría de verdad).
    b = sel.bandits["calculo"]
    pick = sel.select_greedy("calculo")
    b.alpha[pick], b.beta[pick] = 1.0, 100.0
    nuevo = regret_por_clase(sel)
    ok, detalle = gates.auditar_no_regresion(viejo, nuevo, epsilon=0.05)
    print(f"   auditoría tras mala actualización: ok={ok} ({detalle})")
    assert not ok, "la auditoría debería haber detectado la regresión"
    gates.rollback_selector(sel, snap)
    restaurado = regret_por_clase(sel)
    assert restaurado == viejo, "el rollback no restauró la política"
    print("   rollback: política restaurada al snapshot previo")
    return {"nucleo_intacto": True, "privilegios_ok": True,
            "regresion_detectada": True, "rollback_ok": True}


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="ALMA — Experimento 1: la prueba de la selección")
    ap.add_argument("--mock", action="store_true", default=True,
                    help="mundo sintético (default; sin API key)")
    ap.add_argument("--api", action="store_true",
                    help="backend real (usa la credencial del Secure Vault)")
    ap.add_argument("--judge", action="store_true",
                    help="habilitar juez LLM real (solo con --api; suma costo)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--data", default=os.path.join(os.path.dirname(__file__), "data"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "resultados"))
    ap.add_argument("--append", action="store_true",
                    help="no borrar resultados previos (default: empezar de cero)")
    args = ap.parse_args()

    t0 = time.time()
    if not args.append and os.path.exists(args.out):
        shutil.rmtree(args.out)
    os.makedirs(args.out, exist_ok=True)

    # Pre-registro: se escribe ANTES de correr nada.
    prereg = {
        "experimento": NOMBRE_EXPERIMENTO,
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "criterio_exito": CRITERIO,
        "versiones": {
            "alma": ALMA_VERSION,
            "registry": REGISTRY_VERSION,
            "evaluator": evaluator_mod.EVALUATOR_VERSION,
            "taxonomia": TAXONOMY_VERSION,
        },
        "seed": args.seed,
        "modo": "api" if args.api else "mock",
    }
    with open(os.path.join(args.out, "preregistro.json"), "w") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito. Criterio: {CRITERIO}")

    problemas_por_clase, index = cargar_datasets(args.data)
    n_probs = sum(len(v) for v in problemas_por_clase.values())
    print(f"Datasets: {n_probs} problemas ({', '.join(f'{c}={len(v)}' for c, v in problemas_por_clase.items())})")

    if args.api:
        # Ruta segura: la key vive en el Secure Vault, nunca en el entorno.
        # (OpenAICompatBackend queda para ALMA_API_KEY manual.)
        backend = VaultBackend()
        print(f"Backend real (vault): {backend.model} vía skill openai")
        limites = {RESOLUCION: 50.0, SELECCION: 1.0, EXPERIMENTACION: 5.0}
    else:
        backend = MockBackend(index, seed=args.seed)
        print("Backend mock (mundo sintético determinista)")
        limites = {RESOLUCION: 10.0, SELECCION: 1.0, EXPERIMENTACION: 5.0}

    judge = LLMJudge(backend) if (args.api and args.judge) else StubJudge()
    evaluator = Evaluator(judge=judge)
    store = ExperienceStore(os.path.join(args.out, "experiencias.jsonl"))
    budget = BudgetManager(limites)
    assert store.verify_chain()

    # Diagnóstico del clasificador (taxonomía fija v1).
    acc = mean([
        1 if classify(p["enunciado"])[0] == p["clase"] else 0
        for c in CLASES for p in problemas_por_clase[c]
    ])
    print(f"Accuracy del clasificador (5 clases, reglas): {acc:.3f}")

    stats, oraculo, oracle_reward, oracle_cost, mejor_fija = fase_a(
        problemas_por_clase, backend, evaluator, store, budget)
    res_b = fase_b(problemas_por_clase, backend, evaluator, store, budget,
                   oraculo, oracle_reward, oracle_cost, mejor_fija, stats, args.seed)
    curvas_c = fase_c(problemas_por_clase, backend, evaluator, store, budget,
                      oracle_reward, mejor_fija, args.seed)
    gates_ok = demo_gates(store, stats, oraculo)

    # Experimenter (stub honesto) sobre un selector entrenado con todo.
    sel_full = SelectorArquitecturas()
    for r in store.read_all():
        if r.get("fase") == "A":
            sel_full.update(r["clase"], r["arch_id"], r["metricas"]["reward"])
    exp = Experimenter()
    experimenter_out = exp.proponer(sel_full, CLASES, budget)

    # Veredicto contra el criterio pre-registrado.
    reward_ratio = mean([v["reward_ratio"] for v in res_b.values()])
    cost_ratio = mean([v["cost_ratio"] for v in res_b.values()])
    supera = sum(1 for v in res_b.values() if v["supera_global"])
    motivos = [
        f"reward_ratio medio = {reward_ratio:.3f} (mínimo {CRITERIO['reward_ratio_min']})",
        f"cost_ratio medio = {cost_ratio:.3f} (máximo {CRITERIO['cost_ratio_max']})",
        f"supera a la mejor fija global en {supera}/5 clases "
        f"(mínimo {CRITERIO['min_clases_supera_global']})",
    ]
    pasa = (reward_ratio >= CRITERIO["reward_ratio_min"]
            and cost_ratio <= CRITERIO["cost_ratio_max"]
            and supera >= CRITERIO["min_clases_supera_global"])
    veredicto = {"pasa": pasa, "criterio": CRITERIO, "motivos": motivos,
                 "medido": {"reward_ratio": round(reward_ratio, 4),
                            "cost_ratio": round(cost_ratio, 4),
                            "clases_supera_global": supera}}

    costo_total = sum(budget.gastado.values())
    report = {
        "preregistro": prereg,
        "fase_a": {"oraculo": oraculo,
                   "oracle_reward": {k: round(v, 4) for k, v in oracle_reward.items()},
                   "mejor_fija_global": mejor_fija},
        "fase_b": res_b,
        "fase_c": {"regret_final": {k: v[-1] for k, v in curvas_c.items()},
                   "curvas": curvas_c},
        "experimenter": experimenter_out,
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
    print("  RESULTADO:", "PASS — la hipótesis de selección se sostiene en este run"
          if pasa else "FAIL — la hipótesis de selección NO se sostiene en este run")
    print("===========================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
