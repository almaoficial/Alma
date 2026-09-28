#!/usr/bin/env python3
"""ALMA-EXP25: barrido de presupuesto del probe en transferencia.

EXP24 dejó la frase quirúrgica: "con 8 pulls, un evento de cola cruza cualquier
umbral razonable — ruido irreducible". Este experimento no pregunta sí/no:
mapea CUÁNTOS pulls necesita el probe para que la transferencia sea confiable.

Diseño: misma trampa que EXP21/24. Presupuestos k = 8, 16, 32, 64 pulls por
candidata (3 candidatas). STREAM_k = 3k + 96 (96 post-probe constantes, igual
que EXP21/24). Todas las estrategias usan el mismo STREAM_k intra-presupuesto.
Brazos por presupuesto: probe v2 noise-aware (gap>0.15 -> duro, si no Thompson
adaptativo con priors del probe + re-probe cada 24), vecino manual (single de
la trampa C1), desde-cero Thompson (diagnóstico).
4 seeds nuevas [2521-2524], mismas en los 4 presupuestos (RNG namespaced por
presupuesto). Criterio POR PRESUPUESTO: media(probe) < media(vecino) +
regla de confiabilidad (cambio de signo -> NO CONFIABLE).

100% mock: US$0, ninguna llamada a API. No toca DB ni servicio.
Uso: python3 run_experiment25.py [--out DIR]
"""
import argparse
import hashlib
import json
import math
import os
import random

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp25-20260926")

SEEDS = [2521, 2522, 2523, 2524]
PRESUPUESTOS = [8, 16, 32, 64]
POST_PROBE = 96  # pulls post-probe constantes (igual que EXP21/24)
BRAZOS = ["single", "cot", "reflexion"]
UMBRAL_RUIDO = 0.15  # motor.py UMBRAL_RUIDO_DEFAULT (ALMA v2)
REPROBE_CADA = 24

RECOMP_N = {"cot": 0.90, "single": 0.78, "reflexion": 0.65}
P_ORACULO = 0.90

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


def thompson_pick(rng, alfa, beta, brazos):
    thetas = {b: rng.betavariate(alfa[b], beta[b]) for b in brazos}
    return max(brazos, key=lambda x: thetas[x])


def correr_celda(seed, k):
    """Una celda del barrido: presupuesto k, seed dada. Todas las estrategias
    usan STREAM = 3k + 96 pulls."""
    stream = 3 * k + POST_PROBE
    ns = f"exp25-k{k}"
    dists = sorted(((c, dist(FP[c], FP["N"])) for c in MEJOR_BRAZO),
                   key=lambda t: t[1])
    assert dists[0][0] == "C1", f"la trampa se rompió: {dists[0][0]}"
    candidatas = [MEJOR_BRAZO[c] for c, _ in dists[:3]]  # single, cot, reflexion
    res = {"seed": seed, "k": k, "stream": stream,
           "candidatas_probe": candidatas}

    # --- vecino manual: single (brazo de C1) x stream ---
    rng_c = _rng(ns, "vecino", seed)
    brazo_c = MEJOR_BRAZO["C1"]
    r_c = [pull(brazo_c, rng_c) for _ in range(stream)]
    reg_c = sum(P_ORACULO - r for r in r_c)
    res["vecino"] = {"brazo": brazo_c, "regret": round(reg_c, 4),
                     "regret_por_pull": round(reg_c / stream, 4)}

    # --- probe inicial: k pulls x 3 candidatas ---
    rng_p = _rng(ns, "probe", seed)
    obs = {}
    for b in candidatas:
        rs = [pull(b, rng_p) for _ in range(k)]
        obs[b] = [sum(rs), len(rs) - sum(rs)]
    medias = {b: obs[b][0] / k for b in candidatas}
    orden = sorted(candidatas, key=lambda b: medias[b], reverse=True)
    ganador = max(candidatas, key=lambda b: (medias[b], -candidatas.index(b)))
    gap = round(medias[orden[0]] - medias[orden[1]], 4)
    usados = k * len(candidatas)
    regret_probe_fase = sum(P_ORACULO - r
                            for b in candidatas for r in
                            [1] * obs[b][0] + [0] * obs[b][1])
    res_probe = {"medias_probe": {b: round(v, 4) for b, v in medias.items()},
                 "ganador_probe": ganador, "gap": gap,
                 "acierto_probe": ganador == "cot"}

    # --- probe v2 noise-aware ---
    rng_b = _rng(ns, "v2", seed)
    if gap > UMBRAL_RUIDO:
        compromiso = "duro"
        r_b_rest = [pull(ganador, rng_b) for _ in range(stream - usados)]
        pulls_adaptativos, re_probes = 0, 0
    else:
        compromiso = "adaptativo"
        alfa = {b: 1.0 + obs[b][0] for b in candidatas}
        beta = {b: 1.0 + obs[b][1] for b in candidatas}
        r_b_rest = []
        pulls_adaptativos, re_probes = 0, 0
        for i in range(1, stream - usados + 1):
            if i % REPROBE_CADA == 0:
                re_probes += 1
                for b in candidatas:
                    r = pull(b, rng_b)
                    r_b_rest.append(r)
                    alfa[b] += r
                    beta[b] += 1 - r
            else:
                b = thompson_pick(rng_b, alfa, beta, candidatas)
                r = pull(b, rng_b)
                r_b_rest.append(r)
                alfa[b] += r
                beta[b] += 1 - r
                pulls_adaptativos += 1
    reg_b = regret_probe_fase + sum(P_ORACULO - r for r in r_b_rest)
    res["probe_v2"] = dict(res_probe, compromiso=compromiso,
                           pulls_adaptativos=pulls_adaptativos,
                           re_probes=re_probes,
                           regret=round(reg_b, 4),
                           regret_por_pull=round(reg_b / stream, 4))

    # --- desde cero: Thompson x stream (diagnóstico) ---
    rng_d = _rng(ns, "cero", seed)
    alfa = {b: 1.0 for b in BRAZOS}
    beta = {b: 1.0 for b in BRAZOS}
    r_d = []
    for _ in range(stream):
        b = thompson_pick(rng_d, alfa, beta, BRAZOS)
        r = pull(b, rng_d)
        r_d.append(r)
        alfa[b] += r
        beta[b] += 1 - r
    reg_d = sum(P_ORACULO - r for r in r_d)
    res["cero_diag"] = {"regret": round(reg_d, 4),
                        "regret_por_pull": round(reg_d / stream, 4),
                        "nota": "diagnóstico, fuera del criterio pre-registrado"}
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

    por_presupuesto = {}
    for k in PRESUPUESTOS:
        celdas = [correr_celda(s, k) for s in SEEDS]

        def media(key):
            return sum(c[key]["regret"] for c in celdas) / len(celdas)

        def media_pp(key):
            return sum(c[key]["regret_por_pull"] for c in celdas) / len(celdas)

        reg_b, reg_c, reg_d = media("probe_v2"), media("vecino"), media("cero_diag")
        diffs = [c["probe_v2"]["regret"] - c["vecino"]["regret"] for c in celdas]
        pasa = reg_b < reg_c
        signo_cambia = min(diffs) < 0 < max(diffs)
        veredicto = "NO CONFIABLE" if signo_cambia else ("PASS" if pasa else "FAIL")
        por_presupuesto[str(k)] = {
            "k": k, "stream": 3 * k + POST_PROBE, "seeds": SEEDS,
            "celdas": celdas,
            "medias_regret": {
                "probe_v2": round(reg_b, 4),
                "vecino_manual": round(reg_c, 4),
                "desde_cero_diag": round(reg_d, 4),
            },
            "medias_regret_por_pull": {
                "probe_v2": round(media_pp("probe_v2"), 4),
                "vecino_manual": round(media_pp("vecino"), 4),
                "desde_cero_diag": round(media_pp("cero_diag"), 4),
            },
            "diffs_probe_menos_vecino": [round(d, 4) for d in diffs],
            "compromisos": [c["probe_v2"]["compromiso"] for c in celdas],
            "gaps": [c["probe_v2"]["gap"] for c in celdas],
            "aciertos_probe": [c["probe_v2"]["acierto_probe"] for c in celdas],
            "veredicto": veredicto,
            "pasa": bool(pasa and not signo_cambia),
        }

    # ¿dónde se estabiliza? menor k con veredicto confiable
    umbral = next((k for k in PRESUPUESTOS
                   if por_presupuesto[str(k)]["veredicto"] != "NO CONFIABLE"),
                  None)
    reporte = {
        "experimento": "ALMA-EXP25: barrido de presupuesto del probe",
        "presupuestos": PRESUPUESTOS,
        "umbral_ruido": UMBRAL_RUIDO,
        "por_presupuesto": por_presupuesto,
        "umbral_estabilizacion_k": umbral,
        "lectura_umbral": (
            f"el menor presupuesto con veredicto confiable es k={umbral}"
            if umbral is not None else
            "NINGÚN presupuesto hasta k=64 da veredicto confiable: "
            "límite estructural declarado según preregistro"),
        "criterio": "POR PRESUPUESTO: media(regret probe_v2) < media(regret vecino); "
                    "cambio de signo en diffs -> NO CONFIABLE en ese presupuesto",
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    print(f"{'k':>4} {'stream':>6} {'probe':>8} {'vecino':>8} {'cero':>8} "
          f"{'veredicto':>12}  compromisos")
    for k in PRESUPUESTOS:
        p = por_presupuesto[str(k)]
        m = p["medias_regret"]
        print(f"{k:>4} {p['stream']:>6} {m['probe_v2']:>8.2f} "
              f"{m['vecino_manual']:>8.2f} {m['desde_cero_diag']:>8.2f} "
              f"{p['veredicto']:>12}  {p['compromisos']}")
    print("UMBRAL DE ESTABILIZACIÓN:", reporte["lectura_umbral"])


if __name__ == "__main__":
    main()
