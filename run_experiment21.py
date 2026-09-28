#!/usr/bin/env python3
"""ALMA-EXP21: la revancha de la transferencia.

EXP2/EXP3 fallaron porque ALMA pidió prestado al vecino equivocado
(transfirió de la clase más parecida por mapa manual, y era la incorrecta).
Desde entonces se validó la SELECCIÓN por probe (EXP19/20).

Pregunta: ¿la selección por probe repara la transferencia?
Diseño: 5 clases conocidas con fingerprint; clase trampa C1 = la más cercana
a la clase nueva N por fingerprint (d=0.04) pero con mejor brazo DISTINTO.
Tres estrategias compiten en N (120 pulls c/u):
  (a) vecino manual (baseline EXP2): explota el brazo de C1 (single) x120.
  (b) probe-transfer: 8 pulls x {single, cot, reflexion} (mejores brazos de
      las 3 clases más cercanas), elige por media medida, explota x96.
  (c) desde cero: Thompson sampling Beta-Bernoulli x120, sin memoria.
Métrica: regret = suma(0.90 - r_t). Criterio: regret(b) < regret(a) Y
regret(b) < regret(c) en la media de 4 seeds. Regla de confiabilidad:
cambio de signo en diffs(b-a) -> NO CONFIABLE.

100% mock: US$0, ninguna llamada a API. No toca DB ni servicio.
Uso: python3 run_experiment21.py [--out DIR]
"""
import argparse
import hashlib
import json
import math
import os
import random

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp21-20260926")

SEEDS = [2121, 2122, 2123, 2124]
BRAZOS = ["single", "cot", "reflexion"]
STREAM = 120
PULLS_PROBE_POR_BRAZO = 8

# Clase nueva N: mejor = cot
RECOMP_N = {"cot": 0.90, "single": 0.78, "reflexion": 0.65}
P_ORACULO = 0.90

# Fingerprints (documentados en preregistro.json)
FP = {
    "C0": [0.9, 0.1, 0.2, 0.1],
    "C1": [0.18, 0.82, 0.18, 0.28],   # TRAMPA: más cercana a N, brazo wrong
    "C2": [0.5, 0.5, 0.5, 0.5],
    "C3": [0.3, 0.4, 0.3, 0.6],
    "C4": [0.9, 0.1, 0.2, 0.1],
    "N":  [0.2, 0.8, 0.2, 0.3],
}
MEJOR_BRAZO = {"C0": "cot", "C1": "single", "C2": "reflexion",
               "C3": "cot", "C4": "single"}


def _rng(*partes):
    digest = hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()
    return random.Random(int(digest, 16) % (2 ** 32))


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def pull(brazo, rng):
    return 1 if rng.random() < RECOMP_N[brazo] else 0


def correr_seed(seed):
    # --- verificar la trampa: C1 debe ser la más cercana ---
    dists = sorted(((c, dist(FP[c], FP["N"])) for c in MEJOR_BRAZO),
                   key=lambda t: t[1])
    mas_cercana = dists[0][0]
    assert mas_cercana == "C1", f"la trampa se rompió: más cercana = {mas_cercana}"
    candidatas = [MEJOR_BRAZO[c] for c, _ in dists[:3]]  # single, cot, reflexion
    res = {"seed": seed,
           "distancias": {c: round(d, 4) for c, d in dists},
           "candidatas_probe": candidatas}

    # --- (a) vecino manual: explota el brazo de C1 = single ---
    rng_a = _rng("exp21", "vecino", seed)
    brazo_a = MEJOR_BRAZO["C1"]
    r_a = [pull(brazo_a, rng_a) for _ in range(STREAM)]
    regret_a = sum(P_ORACULO - r for r in r_a)
    res["vecino"] = {"brazo": brazo_a, "regret": round(regret_a, 4)}

    # --- (b) probe-transfer: 8 pulls x 3 candidatas, elige, explota ---
    rng_b = _rng("exp21", "probe", seed)
    recomp_probe = {}
    for b in candidatas:
        recomp_probe[b] = [pull(b, rng_b) for _ in range(PULLS_PROBE_POR_BRAZO)]
    medias = {b: sum(rs) / len(rs) for b, rs in recomp_probe.items()}
    ganador = max(candidatas, key=lambda b: (medias[b], -candidatas.index(b)))
    usados = PULLS_PROBE_POR_BRAZO * len(candidatas)
    rng_be = _rng("exp21", "probe-explota", seed)
    r_b = [r for b in candidatas for r in recomp_probe[b]]
    r_b += [pull(ganador, rng_be) for _ in range(STREAM - usados)]
    regret_b = sum(P_ORACULO - r for r in r_b)
    res["probe"] = {"ganador": ganador,
                    "medias_probe": {b: round(v, 4) for b, v in medias.items()},
                    "acierto": ganador == "cot",
                    "regret": round(regret_b, 4)}

    # --- (c) desde cero: Thompson sampling ---
    rng_c = _rng("exp21", "cero", seed)
    alfa = {b: 1.0 for b in BRAZOS}
    beta = {b: 1.0 for b in BRAZOS}
    r_c = []
    for _ in range(STREAM):
        thetas = {b: rng_c.betavariate(alfa[b], beta[b]) for b in BRAZOS}
        b = max(BRAZOS, key=lambda x: thetas[x])
        r = pull(b, rng_c)
        r_c.append(r)
        alfa[b] += r
        beta[b] += 1 - r
    regret_c = sum(P_ORACULO - r for r in r_c)
    res["cero"] = {"regret": round(regret_c, 4)}

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

    def media(brazo):
        return sum(r[brazo]["regret"] for r in por_seed) / len(por_seed)

    reg_probe = media("probe")
    reg_vec = media("vecino")
    reg_cero = media("cero")
    diffs_pv = [r["probe"]["regret"] - r["vecino"]["regret"] for r in por_seed]
    diffs_pc = [r["probe"]["regret"] - r["cero"]["regret"] for r in por_seed]

    pasa = (reg_probe < reg_vec) and (reg_probe < reg_cero)
    signo_cambia = min(diffs_pv) < 0 < max(diffs_pv)
    if signo_cambia:
        veredicto = "NO CONFIABLE"
    else:
        veredicto = "PASS" if pasa else "FAIL"

    reporte = {
        "experimento": "ALMA-EXP21",
        "seeds": SEEDS,
        "por_seed": por_seed,
        "medias_regret": {
            "probe_transfer": round(reg_probe, 4),
            "vecino_manual": round(reg_vec, 4),
            "desde_cero": round(reg_cero, 4),
        },
        "diffs_probe_menos_vecino": [round(d, 4) for d in diffs_pv],
        "diffs_probe_menos_cero": [round(d, 4) for d in diffs_pc],
        "criterio": "regret(probe) < regret(vecino) Y regret(probe) < regret(cero) (medias)",
        "veredicto": veredicto,
        "pasa": bool(pasa and not signo_cambia),
        "acierto_probe_seeds": sum(1 for r in por_seed if r["probe"]["acierto"]),
        "vecino_eligio_trampa": all(r["vecino"]["brazo"] == "single"
                                    for r in por_seed),
        "nota_exp2": "EXP2 FAIL (reward_ratio 0.97, cost_ratio 3.72x, 2/5 clases): "
                     "el mapa manual transfirió al vecino equivocado.",
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    print(json.dumps(reporte["medias_regret"], indent=2, ensure_ascii=False))
    print("diffs probe-vecino:", reporte["diffs_probe_menos_vecino"])
    print("diffs probe-cero:", reporte["diffs_probe_menos_cero"])
    print("VEREDICTO:", veredicto, "| pasa:", reporte["pasa"])


if __name__ == "__main__":
    main()
