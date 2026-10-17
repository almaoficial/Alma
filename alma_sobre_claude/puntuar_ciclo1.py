# -*- coding: utf-8 -*-
"""Puntúa el ciclo 1 (v1) con el validador congelado v1 y aplica las
reglas de veredicto del pre-registro §10 con el δ congelado (§8):
  ADOPCIÓN       si media(v1) − media(v0) ≥ δ = 0,1000
  SEÑAL PARCIAL  si 0 < diferencia < δ
  NULO           si diferencia ≤ 0
La línea de base v0 se lee de resultados_v0.json (Fase 2, asentada en el
ledger); no se recalcula ni se mueve nada. Uso: python3 puntuar_ciclo1.py
→ resultados_ciclo1.json"""
import hashlib
import json
import math
import os
import statistics as st

from puntuar import cargar, resumen

AQUI = os.path.dirname(os.path.abspath(__file__))
DELTA_CONGELADO = 0.10


def sha256(nombre):
    with open(os.path.join(AQUI, nombre), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    corpus = {d["fecha"]: d for d in cargar("corpus_planes.jsonl")}
    with open(os.path.join(AQUI, "resultados_v0.json"), encoding="utf-8") as f:
        prev = json.load(f)
    base = prev["linea_base_v0"]
    v1 = resumen("planes_v1.jsonl", corpus)

    dif = v1["media"] - base["media"]
    se_papel = prev["delta_ciclo1"]["se_dif"]  # s0·√(2/60), congelado
    se_ambas = math.sqrt(base["sd_muestral"] ** 2 / base["n"]
                         + v1["sd_muestral"] ** 2 / v1["n"])
    if dif >= DELTA_CONGELADO:
        veredicto = "ADOPCION"
    elif dif > 0:
        veredicto = "SEÑAL PARCIAL"
    else:
        veredicto = "NULO"

    checks = {}
    for c in ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]:
        checks[c] = {"v0": base["checks"][c], "v1": v1["checks"][c],
                     "dif": (v1["checks"][c]["tasa"]
                             - base["checks"][c]["tasa"])}

    salida = {
        "ciclo": 1,
        "validador_sha256": sha256("validador_plan.py"),
        "planes_v1_sha256": sha256("planes_v1.jsonl"),
        "v1": {k: v1[k] for k in ("n", "media", "sd_muestral", "min", "max",
                                  "checks", "por_dia")},
        "v0_referencia": {"n": base["n"], "media": base["media"],
                          "sd_muestral": base["sd_muestral"]},
        "comparacion": {"delta_media": dif, "se_dif_papel": se_papel,
                        "se_ambas_sd": se_ambas,
                        "delta_congelado": DELTA_CONGELADO,
                        "techo_posible": 1.0 - base["media"],
                        "veredicto": veredicto},
        "checks_comparados": checks,
        "filas_v1": v1["filas"],
    }
    with open(os.path.join(AQUI, "resultados_ciclo1.json"), "w",
              encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    print(f"v1: n={v1['n']} media={v1['media']:.4f} sd={v1['sd_muestral']:.4f}"
          f" min={v1['min']:.3f} max={v1['max']:.3f}")
    print(f"v0: media={base['media']:.4f} | Δ={dif:+.4f} | "
          f"SE(papel)={se_papel:.4f} SE(ambas)={se_ambas:.4f} | "
          f"δ={DELTA_CONGELADO} → {veredicto}")
    for c, d in checks.items():
        print(f"  {c}: v0={d['v0']['tasa']:.3f} (n={d['v0']['n']}) "
              f"v1={d['v1']['tasa']:.3f} (n={d['v1']['n']}) "
              f"dif={d['dif']:+.3f}")


if __name__ == "__main__":
    main()
