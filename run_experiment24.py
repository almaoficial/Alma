#!/usr/bin/env python3
"""ALMA-EXP24: la transferencia con probe consciente de ruido (v2).

EXP21 mostró el mecanismo de rotura exacto: el probe-transfer v1 se compromete
a ciegas tras 8 pulls ruidosos (seed 2122: eligió reflexion con 8 pulls de
suerte -> 96 pulls de explotación ciega -> regret 28).

ALMA v2 (motor.py, decidir_compromiso) trae el antídoto: si el gap entre
candidatos no supera el umbral de ruido (default 0.15), NO hay compromiso duro;
se sigue con exploración adaptativa + re-probe (lección EXP7).

Pregunta: ¿el probe consciente de ruido repara la transferencia?
Diseño: misma trampa que EXP21 (5 clases, C1 trampa d=0.04 con mejor brazo
distinto), 120 pulls por estrategia, 4 seeds NUEVAS. Cuatro brazos:
  (a) probe-transfer v1: réplica exacta EXP21(b) — 8x3 probe, compromiso duro x96.
  (b) probe-transfer v2: 8x3 probe; gap=m1-m2; si gap>0.15 compromiso duro x96;
      si no, 96 pulls adaptativos (Thompson con priors del probe + re-probe
      cada 24 pulls: 1 pull forzado por candidata).
  (c) vecino manual: réplica exacta EXP21(a) — single x120.
  (d) desde cero: diagnóstico (fuera del criterio) — Thompson x120 sin memoria.
Métrica: regret = suma(0.90 - r_t). Criterio: media(b) < media(a) Y media(b) <
media(c). Regla de confiabilidad: cambio de signo en diffs(b-a) -> NO CONFIABLE.

100% mock: US$0, ninguna llamada a API. No toca DB ni servicio.
Uso: python3 run_experiment24.py [--out DIR]
"""
import argparse
import hashlib
import json
import math
import os
import random

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp24-20260926")

SEEDS = [2421, 2422, 2423, 2424]
BRAZOS = ["single", "cot", "reflexion"]
STREAM = 120
PULLS_PROBE_POR_BRAZO = 8
UMBRAL_RUIDO = 0.15  # motor.py UMBRAL_RUIDO_DEFAULT (ALMA v2)
REPROBE_CADA = 24

# Clase nueva N: mejor = cot (idéntico a EXP21)
RECOMP_N = {"cot": 0.90, "single": 0.78, "reflexion": 0.65}
P_ORACULO = 0.90

# Fingerprints (idénticos a EXP21)
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


def correr_seed(seed):
    # --- verificar la trampa: C1 debe ser la más cercana ---
    dists = sorted(((c, dist(FP[c], FP["N"])) for c in MEJOR_BRAZO),
                   key=lambda t: t[1])
    assert dists[0][0] == "C1", f"la trampa se rompió: {dists[0][0]}"
    candidatas = [MEJOR_BRAZO[c] for c, _ in dists[:3]]  # single, cot, reflexion
    res = {"seed": seed,
           "distancias": {c: round(d, 4) for c, d in dists},
           "candidatas_probe": candidatas}

    # --- (c) vecino manual: explota el brazo de C1 = single x120 ---
    rng_c = _rng("exp24", "vecino", seed)
    brazo_c = MEJOR_BRAZO["C1"]
    r_c = [pull(brazo_c, rng_c) for _ in range(STREAM)]
    res["vecino"] = {"brazo": brazo_c,
                     "regret": round(sum(P_ORACULO - r for r in r_c), 4)}

    # --- probe inicial común a (a) y (b): 8 pulls x 3 candidatas ---
    rng_p = _rng("exp24", "probe", seed)
    obs = {}  # brazo -> [exitos, fracasos]
    for b in candidatas:
        rs = [pull(b, rng_p) for _ in range(PULLS_PROBE_POR_BRAZO)]
        obs[b] = [sum(rs), len(rs) - sum(rs)]
    medias = {b: obs[b][0] / PULLS_PROBE_POR_BRAZO for b in candidatas}
    orden = sorted(candidatas, key=lambda b: medias[b], reverse=True)
    ganador = max(candidatas, key=lambda b: (medias[b], -candidatas.index(b)))
    gap = round(medias[orden[0]] - medias[orden[1]], 4)
    usados = PULLS_PROBE_POR_BRAZO * len(candidatas)
    res_probe = {"medias_probe": {b: round(v, 4) for b, v in medias.items()},
                 "ganador_probe": ganador, "gap": gap,
                 "acierto_probe": ganador == "cot"}

    # --- (a) probe-transfer v1: compromiso DURO con el ganador x96 ---
    rng_a = _rng("exp24", "v1-explota", seed)
    r_a = [pull(ganador, rng_a) for _ in range(STREAM - usados)]
    regret_a = sum(P_ORACULO - r
                   for b in candidatas for r in
                   [1] * obs[b][0] + [0] * obs[b][1]) + \
        sum(P_ORACULO - r for r in r_a)
    # (el regret incluye los 24 pulls del probe, como en EXP21)
    res["probe_v1"] = dict(res_probe, compromiso="duro",
                           regret=round(regret_a, 4))

    # --- (b) probe-transfer v2: consciente de ruido ---
    rng_b = _rng("exp24", "v2", seed)
    if gap > UMBRAL_RUIDO:
        compromiso = "duro"
        r_b_rest = [pull(ganador, rng_b) for _ in range(STREAM - usados)]
        pulls_adaptativos = 0
        re_probes = 0
    else:
        compromiso = "adaptativo"
        # Thompson con priors del probe (reutiliza ejecuciones, sin costo extra)
        alfa = {b: 1.0 + obs[b][0] for b in candidatas}
        beta = {b: 1.0 + obs[b][1] for b in candidatas}
        r_b_rest = []
        pulls_adaptativos = 0
        re_probes = 0
        for i in range(1, STREAM - usados + 1):
            if i % REPROBE_CADA == 0:
                # re-probe: 1 pull forzado por candidata (lección EXP7)
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
    regret_b = sum(P_ORACULO - r
                   for b in candidatas for r in
                   [1] * obs[b][0] + [0] * obs[b][1]) + \
        sum(P_ORACULO - r for r in r_b_rest)
    res["probe_v2"] = dict(res_probe, compromiso=compromiso,
                           pulls_adaptativos=pulls_adaptativos,
                           re_probes=re_probes,
                           regret=round(regret_b, 4))

    # --- (d) desde cero: Thompson x120, diagnóstico fuera del criterio ---
    rng_d = _rng("exp24", "cero", seed)
    alfa = {b: 1.0 for b in BRAZOS}
    beta = {b: 1.0 for b in BRAZOS}
    r_d = []
    for _ in range(STREAM):
        b = thompson_pick(rng_d, alfa, beta, BRAZOS)
        r = pull(b, rng_d)
        r_d.append(r)
        alfa[b] += r
        beta[b] += 1 - r
    res["cero_diag"] = {"regret": round(sum(P_ORACULO - r for r in r_d), 4),
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

    por_seed = [correr_seed(s) for s in SEEDS]

    def media(k):
        return sum(r[k]["regret"] for r in por_seed) / len(por_seed)

    reg_b = media("probe_v2")
    reg_a = media("probe_v1")
    reg_c = media("vecino")
    reg_d = media("cero_diag")
    diffs_ba = [r["probe_v2"]["regret"] - r["probe_v1"]["regret"]
                for r in por_seed]
    diffs_bc = [r["probe_v2"]["regret"] - r["vecino"]["regret"]
                for r in por_seed]

    pasa = (reg_b < reg_a) and (reg_b < reg_c)
    signo_cambia = min(diffs_ba) < 0 < max(diffs_ba)
    if signo_cambia:
        veredicto = "NO CONFIABLE"
    else:
        veredicto = "PASS" if pasa else "FAIL"

    reporte = {
        "experimento": "ALMA-EXP24",
        "seeds": SEEDS,
        "umbral_ruido": UMBRAL_RUIDO,
        "por_seed": por_seed,
        "medias_regret": {
            "probe_v2_noise_aware": round(reg_b, 4),
            "probe_v1_duro": round(reg_a, 4),
            "vecino_manual": round(reg_c, 4),
            "desde_cero_diag": round(reg_d, 4),
        },
        "diffs_v2_menos_v1": [round(d, 4) for d in diffs_ba],
        "diffs_v2_menos_vecino": [round(d, 4) for d in diffs_bc],
        "criterio": "regret(v2) < regret(v1) Y regret(v2) < regret(vecino) (medias)",
        "veredicto": veredicto,
        "pasa": bool(pasa and not signo_cambia),
        "compromisos_v2": [r["probe_v2"]["compromiso"] for r in por_seed],
        "gaps_v2": [r["probe_v2"]["gap"] for r in por_seed],
        "comparacion_exp21": {
            "exp21_probe_v1_media": 10.0,
            "exp21_vecino_media": 13.5,
            "exp21_cero_media": 7.5,
            "exp21_veredicto": "NO CONFIABLE (diffs con cambio de signo)",
            "nota": "EXP24 usa seeds nuevas (2421-2424); la comparación es "
                    "cualitativa, no pareada.",
        },
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    print(json.dumps(reporte["medias_regret"], indent=2, ensure_ascii=False))
    print("diffs v2-v1:", reporte["diffs_v2_menos_v1"])
    print("diffs v2-vecino:", reporte["diffs_v2_menos_vecino"])
    print("compromisos v2:", reporte["compromisos_v2"])
    print("VEREDICTO:", veredicto, "| pasa:", reporte["pasa"])


if __name__ == "__main__":
    main()
