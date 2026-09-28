#!/usr/bin/env python3
"""ALMA-EXP30: ¿el umbral de ruido 0.15 es robusto o un filo de navaja?

El umbral vive en producción (UMBRAL_RUIDO_DEFAULT): cada probe decide
compromiso-duro vs adaptativo según si el gap medido supera t.
Los gaps reales se amontonan en 0.14, justo debajo de 0.15.

Diseño (mock, US$0): 2 brazos, A mejor con p=0.7, B con p=0.7-g.
Probe de 8 pulls/brazo (Bernoulli). Si gap_medido > t → compromiso con
el ganador medido por el resto del horizonte; si no → Thompson
adaptativo (el probe cuenta como historia, como en el sistema real).
Horizonte post-probe: 40 pulls.

Criterio pre-registrado: PASS si el regret medio de t=0.15 a través de
gaps está dentro del 15% del mejor umbral.
Regla de confiabilidad: ranking de umbrales invertido entre seeds →
NO CONFIABLE.

Uso: python3 run_experiment30.py [--out DIR]
"""
import argparse
import hashlib
import json
import math
import os
import random

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp30-20260927")

SEEDS = [3021, 3022, 3023, 3024, 3025, 3026, 3027, 3028]
GAPS = [0.03, 0.06, 0.10, 0.14, 0.18, 0.25, 0.40]
UMBRALES = [0.05, 0.10, 0.15, 0.20, 0.30]
N_EPISODIOS = 200
PROBE_PULLS = 8
HORIZONTE = 40
P_A = 0.7


def _rng(*partes):
    digest = hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()
    return random.Random(int(digest, 16) % (2 ** 32))


def thompson_pull(rng, alpha, beta):
    muestras = [rng.betavariate(alpha[i], beta[i]) for i in range(2)]
    return max(range(2), key=lambda i: muestras[i])


def episodio(rng, gap, umbral):
    p = [P_A, P_A - gap]
    alpha = [1.0, 1.0]
    beta = [1.0, 1.0]
    regret = 0.0
    # probe: 8 pulls por brazo
    medias = []
    for i in range(2):
        exitos = 0
        for _ in range(PROBE_PULLS):
            r = 1 if rng.random() < p[i] else 0
            exitos += r
            alpha[i] += r
            beta[i] += 1 - r
            regret += p[0] - p[i]
        medias.append(exitos / PROBE_PULLS)
    gap_medido = abs(medias[0] - medias[1])
    ganador = 0 if medias[0] >= medias[1] else 1
    if gap_medido > umbral:
        # compromiso duro con el ganador medido
        for _ in range(HORIZONTE):
            regret += p[0] - p[ganador]
    else:
        # adaptativo: Thompson con la historia del probe
        for _ in range(HORIZONTE):
            i = thompson_pull(rng, alpha, beta)
            r = 1 if rng.random() < p[i] else 0
            alpha[i] += r
            beta[i] += 1 - r
            regret += p[0] - p[i]
    return regret


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=RES_DIR)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "preregistro.json")) as f:
        json.load(f)  # debe existir ANTES de correr

    # regret[seed][gap][umbral]
    por_seed = []
    for s in SEEDS:
        celdas = {}
        for g in GAPS:
            for t in UMBRALES:
                tot = 0.0
                for e in range(N_EPISODIOS):
                    rng = _rng("exp30", s, g, t, e)
                    tot += episodio(rng, g, t)
                celdas[f"{g}|{t}"] = round(tot / N_EPISODIOS, 4)
        por_seed.append({"seed": s, "celdas": celdas})

    def media(g, t):
        vals = [sd["celdas"][f"{g}|{t}"] for sd in por_seed]
        return sum(vals) / len(vals)

    matriz = {str(g): {str(t): round(media(g, t), 4) for t in UMBRALES}
              for g in GAPS}
    # mejor umbral por gap (media entre seeds)
    mejor_por_gap = {}
    for g in GAPS:
        bt = min(UMBRALES, key=lambda t: media(g, t))
        mejor_por_gap[str(g)] = bt
    # regret medio a través de gaps por umbral
    medio_por_umbral = {str(t): round(
        sum(media(g, t) for g in GAPS) / len(GAPS), 4) for t in UMBRALES}
    # peor caso por umbral
    peor_por_umbral = {str(t): round(
        max(media(g, t) for g in GAPS), 4) for t in UMBRALES}

    t015 = medio_por_umbral["0.15"]
    mejor = min(medio_por_umbral.values())
    dentro = t015 <= mejor * 1.15
    # confiabilidad: ¿0.15 queda entre los 2 mejores en todas las seeds?
    ranking_ok = True
    detalle = {}
    for sd in por_seed:
        med = {t: sum(sd["celdas"][f"{g}|{t}"] for g in GAPS) / len(GAPS)
               for t in UMBRALES}
        orden = sorted(UMBRALES, key=lambda t: med[t])
        detalle[sd["seed"]] = orden
        if orden.index(0.15) > 2:
            ranking_ok = False
    minimax_t = min(UMBRALES, key=lambda t: peor_por_umbral[str(t)])

    if not ranking_ok:
        veredicto = "NO CONFIABLE"
    elif dentro:
        veredicto = "PASS"
    else:
        veredicto = "FAIL"

    reporte = {
        "experimento": "ALMA-EXP30",
        "seeds": SEEDS, "gaps": GAPS, "umbrales": UMBRALES,
        "matriz_regret_medio": matriz,
        "mejor_umbral_por_gap": mejor_por_gap,
        "regret_medio_por_umbral": medio_por_umbral,
        "peor_caso_por_umbral": peor_por_umbral,
        "umbral_minimax": minimax_t,
        "ranking_por_seed": detalle,
        "criterio": "t=0.15 dentro del 15% del mejor (media entre gaps)",
        "veredicto": veredicto,
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    print("regret medio por umbral:", medio_por_umbral)
    print("peor caso por umbral:  ", peor_por_umbral)
    print("mejor umbral por gap:  ", mejor_por_gap)
    print("minimax:", minimax_t)
    print("VEREDICTO:", veredicto)


if __name__ == "__main__":
    main()
