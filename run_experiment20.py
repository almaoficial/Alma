#!/usr/bin/env python3
"""ALMA-EXP20: ¿sobrevive la selección con ERRORES CORRELACIONADOS?

Réplica de EXP19 con el caveat atacado: los 7 agentes ahora correlacionan
sus errores (los LLMs reales no yerran de forma independiente).

Modelo de correlación (pre-registrado): latente gaussiana equicorrelacionada
por candidato. C ~ N(0,1) compartida por candidato;
Z_a = sqrt(rho)*C + sqrt(1-rho)*eps_a, eps_a ~ N(0,1) independientes;
el agente a acierta sii Phi(Z_a) < p_a(label), p_a = TPR_a si label=1
sino TNR_a; rho = 0.5. Preserva las marginales exactas de EXP19.

Brazos: (a) individual al azar, (b) voto x7, (c) enjambre x7 CON probe
(16 etiquetados, argmax accuracy, empate -> índice menor).
Métrica: E = F1/llamadas*1000. Criterio: E_probe > E_ind Y E_probe > E_voto
en la media de 4 seeds. Regla de confiabilidad: cambio de signo -> NO CONFIABLE.

100% mock: US$0, ninguna llamada a API. No toca DB ni servicio.
Uso: python3 run_experiment20.py [--out DIR]
"""
import argparse
import hashlib
import json
import math
import os
import random
import statistics

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp20-20260926")

SEEDS = [2021, 2022, 2023, 2024]
N_AGENTS = 7
M_POOL = 5000
D_FEATS = 8
P_PROBE = 16
RHO = 0.5

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

_ND = statistics.NormalDist()
_S_RHO = math.sqrt(RHO)
_S_1MRHO = math.sqrt(1.0 - RHO)


def _rng(*partes):
    digest = hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()
    return random.Random(int(digest, 16) % (2 ** 32))


def generar_pool(seed):
    rng = _rng("exp20", "pool", seed)
    cands = []
    for _ in range(M_POOL):
        feats = [rng.randint(0, 1) for _ in range(D_FEATS)]
        label = 1 if (feats[1] == 1 and feats[4] == 1 and feats[7] == 0) else 0
        cands.append((feats, label))
    return cands


def generar_probe(seed):
    rng = _rng("exp20", "probe", seed)
    cands = []
    for _ in range(P_PROBE):
        feats = [rng.randint(0, 1) for _ in range(D_FEATS)]
        label = 1 if (feats[1] == 1 and feats[4] == 1 and feats[7] == 0) else 0
        cands.append((feats, label))
    return cands


def probs_para(label):
    # Probabilidad de PREDECIR 1 dado el label — marginales idénticas a EXP19:
    #   P(pred=1|y=1) = TPR_a ; P(pred=1|y=0) = 1 - TNR_a.
    # El agente acierta sii pred == label.
    return [(AGENTES[a][0] if label == 1 else 1.0 - AGENTES[a][1]) for a in ORDEN]


def clasificar_todos(probs, rng):
    """Clasifica un candidato con len(probs) agentes, errores correlacionados.

    probs: lista de p_a (prob. de acierto de cada agente para este label).
    Una C compartida por candidato induce correlación rho en la latente.
    """
    C = rng.gauss(0.0, 1.0)
    out = []
    for p in probs:
        eps = rng.gauss(0.0, 1.0)
        Z = _S_RHO * C + _S_1MRHO * eps
        out.append(1 if _ND.cdf(Z) < p else 0)
    return out


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


def corr_pearson(xs, ys):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return 0.0
    return cov / math.sqrt(vx * vy)


def correr_seed(seed):
    pool = generar_pool(seed)
    y_true = [label for _, label in pool]
    probe = generar_probe(seed)
    py_true = [label for _, label in probe]
    res = {"seed": seed}

    # --- Brazo (c): enjambre CON probe (errores correlacionados también acá) ---
    rng_p = _rng("exp20", "probe-clf", seed)
    accs = {a: [] for a in ORDEN}
    for _, lab in probe:
        preds = clasificar_todos(probs_para(lab), rng_p)
        for a, pr in zip(ORDEN, preds):
            accs[a].append(pr)
    acc_probe = {a: accuracy(py_true, accs[a]) for a in ORDEN}
    mejor = max(ORDEN, key=lambda a: (acc_probe[a], -ORDEN.index(a)))
    idx_mejor = ORDEN.index(mejor)
    rng_c = _rng("exp20", "brazo-probe", seed)
    pred_c = []
    for lab in y_true:
        q = AGENTES[mejor][0] if lab == 1 else 1.0 - AGENTES[mejor][1]  # P(pred=1|label): TPR / (1-TNR)
        pred_c.append(clasificar_todos([q], rng_c)[0])
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
    rng_a = _rng("exp20", "brazo-ind", seed)
    agente_ind = ORDEN[rng_a.randrange(N_AGENTS)]
    rng_ai = _rng("exp20", "brazo-ind-clf", seed)
    pred_a = []
    for lab in y_true:
        q = AGENTES[agente_ind][0] if lab == 1 else 1.0 - AGENTES[agente_ind][1]  # P(pred=1|label): TPR / (1-TNR)
        pred_a.append(clasificar_todos([q], rng_ai)[0])
    llamadas_a = M_POOL
    f1_a = f1_score(y_true, pred_a)
    res["individual"] = {
        "agente": agente_ind,
        "f1": round(f1_a, 4),
        "llamadas": llamadas_a,
        "E": round(f1_a / llamadas_a * 1000, 6),
    }

    # --- Brazo (b): voto mayoritario x7 (correlacionado) ---
    rng_v = _rng("exp20", "brazo-voto", seed)
    pred_v = []
    errores_por_agente = {a: [] for a in ORDEN}
    for lab in y_true:
        preds = clasificar_todos(probs_para(lab), rng_v)
        for a, pr in zip(ORDEN, preds):
            errores_por_agente[a].append(0 if pr == lab else 1)
        pred_v.append(1 if sum(preds) >= 4 else 0)
    llamadas_v = N_AGENTS * M_POOL
    f1_v = f1_score(y_true, pred_v)
    # sanity check: correlación media de errores por pares
    corrs = []
    for i in range(N_AGENTS):
        for j in range(i + 1, N_AGENTS):
            corrs.append(corr_pearson(errores_por_agente[ORDEN[i]],
                                      errores_por_agente[ORDEN[j]]))
    corr_media = sum(corrs) / len(corrs)
    res["voto"] = {
        "f1": round(f1_v, 4),
        "llamadas": llamadas_v,
        "E": round(f1_v / llamadas_v * 1000, 6),
    }
    res["corr_error_media_pares"] = round(corr_media, 4)
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
        json.load(f)

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
        "experimento": "ALMA-EXP20",
        "seeds": SEEDS,
        "rho_latente": RHO,
        "por_seed": por_seed,
        "medias": {
            "E_probe": round(E_probe, 6),
            "E_individual": round(E_ind, 6),
            "E_voto": round(E_voto, 6),
            "F1_probe": round(media("f1", "probe"), 4),
            "F1_individual": round(media("f1", "individual"), 4),
            "F1_voto": round(media("f1", "voto"), 4),
            "corr_error_media": round(sum(r["corr_error_media_pares"] for r in por_seed) / len(por_seed), 4),
        },
        "diffs_E_probe_menos_ind": [round(d, 6) for d in diffs],
        "criterio": "E_probe > E_individual Y E_probe > E_voto (medias)",
        "veredicto": veredicto,
        "pasa": bool(pasa and not signo_cambia),
        "acierto_probe_seeds": sum(1 for r in por_seed if r["probe"]["acierto_probe"]),
        "comparacion_exp19": {
            "E_probe": 0.0940, "E_individual": 0.0554, "E_voto": 0.0148,
            "F1_probe": 0.4807, "F1_individual": 0.2770, "F1_voto": 0.5164,
        },
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    print(json.dumps(reporte["medias"], indent=2, ensure_ascii=False))
    print("diffs:", reporte["diffs_E_probe_menos_ind"])
    print("VEREDICTO:", veredicto, "| pasa:", reporte["pasa"])


if __name__ == "__main__":
    main()
