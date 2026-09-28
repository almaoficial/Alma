#!/usr/bin/env python3
"""ALMA-EXP23: AGENTES-BATERIA vs PERSISTENTES a HORIZONTE LARGO (idea del usuario, mock).

Continuacion de EXP22 (R=10, FAIL): mismo modelo EXACTO pero R=50 rondas,
donde la deriva acumulada si muerde. 8 seeds nuevas para potencia.
Criterio pre-registrado (preregistro.json, escrito ANTES de correr):
M_baterias < M_persistentes en la media de las 8 seeds (s=1).
Regla de confiabilidad: cambio de signo entre seeds -> NO CONFIABLE.
Analisis secundario pre-registrado: curva de break-even del costo de spawn s.

100% mock: US$0, ninguna llamada a API. No toca DB ni servicio.
Uso: python3 run_experiment23.py [--out DIR]
"""
import argparse
import hashlib
import json
import os
import random

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp23-20260926")

SEEDS = [2321, 2322, 2323, 2324, 2325, 2326, 2327, 2328]
K = 7
R = 50
SIGMAS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.9, 1.1]
SIGMA_DRIFT = 0.15
PHI = 0.7
SIGMA_THETA = 0.5
SPAWN_COST = 1.0  # llamadas por spawn de bateria (pre-registrado, igual que EXP22)
S_GRID = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]  # curva de break-even (pre-registrada)


def _rng(*partes):
    digest = hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()
    return random.Random(int(digest, 16) % (2 ** 32))


def generar_theta(seed):
    rng = _rng("exp23", "theta", seed)
    th = [rng.gauss(0.0, 1.0)]
    for _ in range(1, R):
        th.append(PHI * th[-1] + rng.gauss(0.0, SIGMA_THETA))
    return th


def correr_seed(seed):
    theta = generar_theta(seed)
    rng_p = _rng("exp23", "persistentes", seed)
    rng_b = _rng("exp23", "baterias", seed)

    # --- Brazo A: persistentes (sesgo que deriva) ---
    sesgos = [0.0] * K
    mse_p = []
    for r in range(R):
        reportes = []
        for k in range(K):
            eps = rng_p.gauss(0.0, SIGMAS[k])
            reportes.append(theta[r] + sesgos[k] + eps)
        centro = sum(reportes) / K
        mse_p.append((centro - theta[r]) ** 2)
        sesgos = [b + rng_p.gauss(0.0, SIGMA_DRIFT) for b in sesgos]
    llamadas_p = K * R
    mse_medio_p = sum(mse_p) / R
    M_p = mse_medio_p * llamadas_p
    sesgo_abs_final = sum(abs(b) for b in sesgos) / K

    # --- Brazo B: baterias (nacen frescas, reportan, mueren) ---
    mse_b = []
    for r in range(R):
        reportes = []
        for k in range(K):
            eps = rng_b.gauss(0.0, SIGMAS[k])
            reportes.append(theta[r] + eps)  # b=0 siempre: sin historia
        centro = sum(reportes) / K
        mse_b.append((centro - theta[r]) ** 2)
    llamadas_b = K * R  # reportes; el spawn se modela via s en M
    mse_medio_b = sum(mse_b) / R
    M_b = mse_medio_b * llamadas_b * (1 + SPAWN_COST)

    # break-even por seed: s* tal que M_bat(s*) = M_pers
    # MSE_b*(1+s*) = MSE_p  =>  s* = MSE_p/MSE_b - 1
    s_star = mse_medio_p / mse_medio_b - 1.0 if mse_medio_b > 0 else float("inf")

    return {
        "seed": seed,
        "persistentes": {
            "mse_medio": round(mse_medio_p, 6),
            "llamadas": llamadas_p,
            "M": round(M_p, 6),
            "sesgo_abs_medio_ronda50": round(sesgo_abs_final, 4),
        },
        "baterias": {
            "mse_medio": round(mse_medio_b, 6),
            "llamadas_reportes": llamadas_b,
            "M_s1": round(M_b, 6),
            "s_star": round(s_star, 4),
        },
        "diff_M_pers_menos_bat_s1": round(M_p - M_b, 6),
    }


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

    def media(brazo, k):
        return sum(r[brazo][k] for r in por_seed) / len(por_seed)

    M_pers = media("persistentes", "M")
    M_bat = media("baterias", "M_s1")
    mse_pers = media("persistentes", "mse_medio")
    mse_bat = media("baterias", "mse_medio")
    diffs = [r["diff_M_pers_menos_bat_s1"] for r in por_seed]

    pasa = M_bat < M_pers
    signo_cambia = min(diffs) < 0 < max(diffs)
    if signo_cambia:
        veredicto = "NO CONFIABLE"
    else:
        veredicto = "PASS" if pasa else "FAIL"

    # --- Analisis secundario pre-registrado: curva de break-even de s ---
    # M_bat(s) = MSE_b_medio x K x R x (1+s); analitico desde los MSE registrados.
    s_stars = [r["baterias"]["s_star"] for r in por_seed]
    s_stars_sorted = sorted(s_stars)
    n = len(s_stars_sorted)
    s_star_mediana = (s_stars_sorted[n // 2 - 1] + s_stars_sorted[n // 2]) / 2
    s_star_media = sum(s_stars) / n
    llamadas_base = K * R
    curva = []
    for s in S_GRID:
        M_bat_s = mse_bat * llamadas_base * (1 + s)
        curva.append({
            "s": s,
            "M_baterias": round(M_bat_s, 4),
            "M_persistentes": round(M_pers, 4),
            "ganan_baterias": bool(M_bat_s < M_pers),
        })

    # sanity check diagnostico (no pre-registrado como criterio): con drift=0
    # los brazos son el mismo proceso y los MSE crudos deberian ser del mismo orden.
    global SIGMA_DRIFT
    _sd = SIGMA_DRIFT
    SIGMA_DRIFT = 0.0
    _chk = correr_seed(9999)
    SIGMA_DRIFT = _sd
    sanity = {
        "drift_cero_seed9999": {
            "mse_persistentes": _chk["persistentes"]["mse_medio"],
            "mse_baterias": _chk["baterias"]["mse_medio"],
            "nota": "con drift=0 ambos brazos son el mismo proceso: MSE del mismo "
                     "orden (no identicos: RNG distinto).",
        }
    }

    reporte = {
        "experimento": "ALMA-EXP23",
        "pregunta": "A horizonte largo (R=50), donde la deriva si muerde, "
                    "¿morir despues de reportar PAGA el renacimiento?",
        "seeds": SEEDS,
        "por_seed": por_seed,
        "medias": {
            "M_persistentes": round(M_pers, 6),
            "M_baterias_s1": round(M_bat, 6),
            "MSE_medio_persistentes": round(mse_pers, 6),
            "MSE_medio_baterias": round(mse_bat, 6),
            "sesgo_abs_medio_r50_persistentes": round(
                media("persistentes", "sesgo_abs_medio_ronda50"), 4),
        },
        "diffs_M_pers_menos_bat_s1": [round(d, 6) for d in diffs],
        "criterio": "M_baterias(s=1) < M_persistentes en la media de 8 seeds; "
                    "M = MSE_medio x llamadas",
        "veredicto": veredicto,
        "pasa": bool(pasa and not signo_cambia),
        "break_even_spawn": {
            "s_star_por_seed": [round(v, 4) for v in s_stars],
            "s_star_media": round(s_star_media, 4),
            "s_star_mediana": round(s_star_mediana, 4),
            "curva_M_vs_s": curva,
            "interpretacion": "s* = costo de spawn al que M_bat = M_pers. "
                              "s* >> 1: las baterias pagan holgadamente; "
                              "s* ~ 1: borde; s* < 1: ni con spawn barato pagan.",
        },
        "sanity_check_diagnostico": sanity,
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(reporte, f, indent=2)
    print(json.dumps({"veredicto": veredicto,
                      "M_pers": round(M_pers, 4),
                      "M_bat_s1": round(M_bat, 4),
                      "s_star_mediana": round(s_star_mediana, 4),
                      "diffs": [round(d, 4) for d in diffs]},
                     indent=2))


if __name__ == "__main__":
    main()
