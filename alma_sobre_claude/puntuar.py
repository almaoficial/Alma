# -*- coding: utf-8 -*-
"""Puntúa la línea de base v0 (y el ancla de planes reales) con el
validador congelado v1 y deriva el δ del ciclo 1 según la fórmula del
pre-registro §8. Uso: python3 puntuar.py → resultados_v0.json"""
import json
import math
import os
import statistics as st

from validador_plan import puntuar

AQUI = os.path.dirname(os.path.abspath(__file__))


def cargar(nombre):
    with open(os.path.join(AQUI, nombre), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def resumen(nombre_planes, corpus):
    filas = []
    for p in cargar(nombre_planes):
        dia = corpus[p["fecha"]]
        r = puntuar(p["texto"], dia)
        filas.append({"fecha": p["fecha"], "rep": p.get("rep"),
                      "variante": p.get("variante", "v0"), **r})
    puntajes = [f["puntaje"] for f in filas]
    checks = {}
    for c in ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]:
        vals = [f[c] for f in filas if f[c] is not None]
        checks[c] = {"n": len(vals),
                     "tasa": (sum(1 for v in vals if v) / len(vals)
                              if vals else None)}
    por_dia = {}
    for f in filas:
        por_dia.setdefault(f["fecha"], []).append(f["puntaje"])
    return {
        "n": len(filas),
        "media": st.fmean(puntajes),
        "sd_muestral": st.stdev(puntajes) if len(puntajes) > 1 else 0.0,
        "min": min(puntajes), "max": max(puntajes),
        "checks": checks,
        "por_dia": {d: {"n": len(v), "media": st.fmean(v)}
                    for d, v in sorted(por_dia.items())},
        "filas": filas,
    }


def main():
    corpus = {d["fecha"]: d for d in cargar("corpus_planes.jsonl")}
    base = resumen("planes_v0.jsonl", corpus)
    ancla = resumen("planes_reales.jsonl", corpus)
    s0 = base["sd_muestral"]
    n_var = base["n"]
    se_dif = s0 * math.sqrt(2 / n_var)
    delta = max(0.10, 2 * se_dif)
    salida = {
        "linea_base_v0": {k: base[k] for k in
                          ("n", "media", "sd_muestral", "min", "max",
                           "checks", "por_dia")},
        "ancla_reales": {k: ancla[k] for k in
                         ("n", "media", "sd_muestral", "min", "max",
                          "checks", "por_dia")},
        "delta_ciclo1": {"s0": s0, "n_por_variante": n_var,
                         "se_dif": se_dif, "dos_se": 2 * se_dif,
                         "efecto_minimo_interes": 0.10, "delta": delta},
        "filas_v0": base["filas"], "filas_reales": ancla["filas"],
    }
    with open(os.path.join(AQUI, "resultados_v0.json"), "w",
              encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    print(f"v0: n={base['n']} media={base['media']:.4f} sd={s0:.4f} | "
          f"reales: n={ancla['n']} media={ancla['media']:.4f} | "
          f"SE_dif={se_dif:.4f} δ={delta:.4f}")


if __name__ == "__main__":
    main()
