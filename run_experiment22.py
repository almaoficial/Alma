#!/usr/bin/env python3
"""ALMA-EXP22: AGENTES-BATERIA vs PERSISTENTES (idea del usuario, modo mock).

Pregunta honesta: ¿morir despues de reportar produce mejor señal por
dolar que persistir con ruido acumulado?

Modelo (pre-registrado en preregistro.json ANTES de correr):
- R=10 rondas; señal theta_r: theta_0 ~ N(0,1), theta_r = 0.7*theta_{r-1}+N(0,0.5).
- K=7 agentes heterogeneos, sigmas de observacion [0.3..1.1].
- PERSISTENTES: b_{k,0}=0; b_{k,r+1} = b_{k,r} + N(0,0.15);
  x_{k,r} = theta_r + b_{k,r} + eps_{k,r}. Costo: 7 reportes/ronda (70 total).
- BATERIAS: cada ronda nacen frescos (b=0), reportan y mueren:
  x_{k,r} = theta_r + eps_{k,r}. Costo: 7 reportes + 7 spawns/ronda (140 total).
- Centro: theta_hat_r = media de los K reportes. MSE_r = (theta_hat_r-theta_r)^2.
- Metrica: M = MSE_medio x llamadas_totales (menor es mejor).
- Criterio: M_bat < M_pers en la media de 4 seeds [2221..2224].
  Regla de confiabilidad: cambio de signo entre seeds -> NO CONFIABLE.

100% mock: US$0, ninguna llamada a API. No toca DB ni servicio.
Uso: python3 run_experiment22.py [--out DIR]
"""
import argparse
import hashlib
import json
import math
import os
import random
import statistics

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp22-20260926")

SEEDS = [2221, 2222, 2223, 2224]
K = 7
R = 10
SIGMAS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.9, 1.1]
SIGMA_DRIFT = 0.15
PHI = 0.7
SIGMA_THETA = 0.5
SPAWN_COST = 1.0  # llamadas por spawn de bateria (pre-registrado)


def _rng(*partes):
    digest = hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()
    return random.Random(int(digest, 16) % (2 ** 32))


def generar_theta(seed):
    rng = _rng("exp22", "theta", seed)
    th = [rng.gauss(0.0, 1.0)]
    for _ in range(1, R):
        th.append(PHI * th[-1] + rng.gauss(0.0, SIGMA_THETA))
    return th


def correr_seed(seed):
    theta = generar_theta(seed)
    rng_p = _rng("exp22", "persistentes", seed)
    rng_b = _rng("exp22", "baterias", seed)

    # --- Brazo A: persistentes (sesgo que deriva) ---
    sesgos = [0.0] * K
    mse_p, sesgo_abs_acum = [], []
    for r in range(R):
        reportes = []
        for k in range(K):
            eps = rng_p.gauss(0.0, SIGMAS[k])
            reportes.append(theta[r] + sesgos[k] + eps)
        centro = sum(reportes) / K
        mse_p.append((centro - theta[r]) ** 2)
        sesgo_abs_acum.append(sum(abs(b) for b in sesgos) / K)
        # el sesgo deriva para la proxima ronda (el contexto se pudre)
        sesgos = [b + rng_p.gauss(0.0, SIGMA_DRIFT) for b in sesgos]
    llamadas_p = K * R
    mse_medio_p = sum(mse_p) / R
    M_p = mse_medio_p * llamadas_p

    # --- Brazo B: baterias (nacen frescas, reportan, mueren) ---
    mse_b = []
    for r in range(R):
        reportes = []
        for k in range(K):
            eps = rng_b.gauss(0.0, SIGMAS[k])
            reportes.append(theta[r] + eps)  # b=0 siempre: sin historia
        centro = sum(reportes) / K
        mse_b.append((centro - theta[r]) ** 2)
    llamadas_b = int(K * R * (1 + SPAWN_COST))
    mse_medio_b = sum(mse_b) / R
    M_b = mse_medio_b * llamadas_b

    return {
        "seed": seed,
        "persistentes": {
            "mse_medio": round(mse_medio_p, 6),
            "llamadas": llamadas_p,
            "M": round(M_p, 6),
            "sesgo_abs_medio_ronda10": round(sesgo_abs_acum[-1], 4),
            "mse_por_ronda": [round(v, 4) for v in mse_p],
        },
        "baterias": {
            "mse_medio": round(mse_medio_b, 6),
            "llamadas": llamadas_b,
            "M": round(M_b, 6),
            "mse_por_ronda": [round(v, 4) for v in mse_b],
        },
        "diff_M_pers_menos_bat": round(M_p - M_b, 6),
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
    M_bat = media("baterias", "M")
    mse_pers = media("persistentes", "mse_medio")
    mse_bat = media("baterias", "mse_medio")
    diffs = [r["diff_M_pers_menos_bat"] for r in por_seed]

    pasa = M_bat < M_pers
    signo_cambia = min(diffs) < 0 < max(diffs)
    if signo_cambia:
        veredicto = "NO CONFIABLE"
    else:
        veredicto = "PASS" if pasa else "FAIL"

    # sanity check no pre-registrado (diagnostico): con drift=0 los brazos
    # deberian empatar en MSE crudo. Se corre 1 seed con SIGMA_DRIFT=0.
    global SIGMA_DRIFT
    _sd = SIGMA_DRIFT
    SIGMA_DRIFT = 0.0
    _chk = correr_seed(9999)
    SIGMA_DRIFT = _sd
    sanity = {
        "drift_cero_seed9999": {
            "mse_persistentes": _chk["persistentes"]["mse_medio"],
            "mse_baterias": _chk["baterias"]["mse_medio"],
            "nota": "con drift=0 ambos brazos son el mismo proceso: los MSE "
                     "deberian ser del mismo orden (no identicos: RNG distinto).",
        }
    }

    reporte = {
        "experimento": "ALMA-EXP22",
        "pregunta": "¿Morir despues de reportar produce mejor señal por costo que persistir?",
        "seeds": SEEDS,
        "por_seed": por_seed,
        "medias": {
            "M_persistentes": round(M_pers, 6),
            "M_baterias": round(M_bat, 6),
            "MSE_medio_persistentes": round(mse_pers, 6),
            "MSE_medio_baterias": round(mse_bat, 6),
            "sesgo_abs_medio_r10_persistentes": round(
                sum(r["persistentes"]["sesgo_abs_medio_ronda10"] for r in por_seed) / len(por_seed), 4),
        },
        "diffs_M_pers_menos_bat": [round(d, 6) for d in diffs],
        "criterio": "M_baterias < M_persistentes (medias de 4 seeds); M = MSE_medio x llamadas",
        "veredicto": veredicto,
        "pasa": bool(pasa and not signo_cambia),
        "sanity_check_diagnostico": sanity,
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(reporte, f, indent=2)
    print(json.dumps({"veredicto": veredicto, "M_pers": round(M_pers, 4),
                      "M_bat": round(M_bat, 4), "diffs": [round(d, 4) for d in diffs]},
                     indent=2))


if __name__ == "__main__":
    main()
