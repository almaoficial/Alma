#!/usr/bin/env python3
"""ALMA-EXP19: ¿la SELECCION es lo que hace funcionar al enjambre?

Replica minima (mock puro, US$0) del patron "swarm" de las noticias del
26/9: filtrar candidatos con señal escondida y marcar los hits.

Brazos: (a) agente individual (azar), (b) enjambre x7 por voto mayoritario,
(c) enjambre x7 CON probe estilo ALMA (micro-evaluacion en 16 etiquetados,
seleccion del mejor por accuracy).

Criterio pre-registrado (resultados/exp19-20260926/preregistro.json):
  E_probe > E_individual Y E_probe > E_voto, con E = F1/llamadas*1000,
  en la media de las 4 seeds. Regla de confiabilidad: si el signo de
  (E_probe - E_individual) cambia entre seeds -> NO CONFIABLE.

100% mock: ninguna llamada a API, no toca la DB ni el servicio.
Uso: python3 run_experiment19.py [--out DIR]
"""
import argparse
import hashlib
import json
import os
import random
import sys

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp19-20260926")

SEEDS = [1921, 1922, 1923, 1924]
N_AGENTS = 7
M_POOL = 5000
D_FEATS = 8
P_PROBE = 16

# Tabla fija de skills (TPR, TNR) — pre-registrada.
AGENTES = {
    "A": (0.60, 0.60),
    "B": (0.65, 0.62),
    "C": (0.58, 0.70),
    "D": (0.75, 0.72),
    "E": (0.62, 0.58),
    "F": (0.85, 0.82),
    "G": (0.55, 0.55),
}
ORDEN = ["A", "B", "C", "D", "E", "F", "G"]


def _rng(*partes):
    digest = hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()
    return random.Random(int(digest, 16) % (2 ** 32))


def generar_pool(seed):
    """M candidatos: features binarias; HIT <=> f1 & f4 & ~f7."""
    rng = _rng("exp19", "pool", seed)
    cands = []
    for _ in range(M_POOL):
        feats = [rng.randint(0, 1) for _ in range(D_FEATS)]
        label = 1 if (feats[1] == 1 and feats[4] == 1 and feats[7] == 0) else 0
        cands.append((feats, label))
    return cands


def generar_probe(seed):
    rng = _rng("exp19", "probe", seed)
    cands = []
    for _ in range(P_PROBE):
        feats = [rng.randint(0, 1) for _ in range(D_FEATS)]
        label = 1 if (feats[1] == 1 and feats[4] == 1 and feats[7] == 0) else 0
        cands.append((feats, label))
    return cands


def clasificar(agente, label, rng):
    """Un 'pull' mock: el agente acierta segun su TPR/TNR."""
    tpr, tnr = AGENTES[agente]
    p_pos = tpr if label == 1 else (1.0 - tnr)
    return 1 if rng.random() < p_pos else 0


def f1_score(y_true, y_pred):
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    if tp == 0:
        return 0.0
    prec = tp / (tp + fp)
    rec = tp / (tp + fn)
    return 2 * prec * rec / (prec + rec)


def accuracy(y_true, y_pred):
    return sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)


def correr_seed(seed):
    pool = generar_pool(seed)
    y_true = [label for _, label in pool]
    probe = generar_probe(seed)
    py_true = [label for _, label in probe]

    res = {"seed": seed}

    # --- Brazo (c): enjambre CON probe ---
    rng_probe = _rng("exp19", "probe-clf", seed)
    acc_probe = {}
    for a in ORDEN:
        preds = [clasificar(a, lab, rng_probe) for _, lab in probe]
        acc_probe[a] = accuracy(py_true, preds)
    mejor = max(ORDEN, key=lambda a: (acc_probe[a], -ORDEN.index(a)))
    # (max con key (acc, -idx): a igualdad de accuracy gana el indice menor)
    rng_c = _rng("exp19", "brazo-probe", seed)
    pred_c = [clasificar(mejor, lab, rng_c) for lab in y_true]
    llamadas_c = N_AGENTS * P_PROBE + M_POOL
    f1_c = f1_score(y_true, pred_c)
    res["probe"] = {
        "agente_seleccionado": mejor,
        "acc_probe_por_agente": {a: round(v, 4) for a, v in acc_probe.items()},
        "acierto_probe": mejor == "F",
        "f1": round(f1_c, 4),
        "llamadas": llamadas_c,
        "E": round(f1_c / llamadas_c * 1000, 6),
    }

    # --- Brazo (a): agente individual al azar ---
    rng_a = _rng("exp19", "brazo-ind", seed)
    agente_ind = ORDEN[rng_a.randrange(N_AGENTS)]
    rng_ai = _rng("exp19", "brazo-ind-clf", seed)
    pred_a = [clasificar(agente_ind, lab, rng_ai) for lab in y_true]
    llamadas_a = M_POOL
    f1_a = f1_score(y_true, pred_a)
    res["individual"] = {
        "agente": agente_ind,
        "f1": round(f1_a, 4),
        "llamadas": llamadas_a,
        "E": round(f1_a / llamadas_a * 1000, 6),
    }

    # --- Brazo (b): enjambre por voto mayoritario ---
    rng_v = _rng("exp19", "brazo-voto", seed)
    pred_v = []
    for lab in y_true:
        votos = sum(clasificar(a, lab, rng_v) for a in ORDEN)
        pred_v.append(1 if votos >= 4 else 0)
    llamadas_v = N_AGENTS * M_POOL
    f1_v = f1_score(y_true, pred_v)
    res["voto"] = {
        "f1": round(f1_v, 4),
        "llamadas": llamadas_v,
        "E": round(f1_v / llamadas_v * 1000, 6),
    }

    res["hits_pool"] = sum(y_true)
    res["hits_probe"] = sum(py_true)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=RES_DIR)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    pre = os.path.join(args.out, "preregistro.json")
    assert os.path.exists(pre), "preregistro.json debe existir ANTES de correr"
    with open(pre) as f:
        json.load(f)  # valida

    por_seed = [correr_seed(s) for s in SEEDS]

    def media(k, brazo):
        return sum(r[brazo][k] for r in por_seed) / len(por_seed)

    E_probe = media("E", "probe")
    E_ind = media("E", "individual")
    E_voto = media("E", "voto")
    diffs = [r["probe"]["E"] - r["individual"]["E"] for r in por_seed]

    pasa = (E_probe > E_ind) and (E_probe > E_voto)
    signo_cambia = min(diffs) < 0 < max(diffs)
    if signo_cambia:
        veredicto = "NO CONFIABLE"
    else:
        veredicto = "PASS" if pasa else "FAIL"

    reporte = {
        "experimento": "ALMA-EXP19",
        "seeds": SEEDS,
        "por_seed": por_seed,
        "medias": {
            "E_probe": round(E_probe, 6),
            "E_individual": round(E_ind, 6),
            "E_voto": round(E_voto, 6),
            "F1_probe": round(media("f1", "probe"), 4),
            "F1_individual": round(media("f1", "individual"), 4),
            "F1_voto": round(media("f1", "voto"), 4),
        },
        "diffs_E_probe_menos_ind": [round(d, 6) for d in diffs],
        "criterio": "E_probe > E_individual Y E_probe > E_voto (medias)",
        "veredicto": veredicto,
        "pasa": bool(pasa and not signo_cambia),
        "acierto_probe_seeds": sum(1 for r in por_seed if r["probe"]["acierto_probe"]),
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    print(json.dumps(reporte["medias"], indent=2, ensure_ascii=False))
    print("diffs:", reporte["diffs_E_probe_menos_ind"])
    print("VEREDICTO:", veredicto, "| pasa:", reporte["pasa"])


if __name__ == "__main__":
    main()
