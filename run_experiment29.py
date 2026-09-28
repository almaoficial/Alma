#!/usr/bin/env python3
"""ALMA-EXP29: ¿la distancia del fingerprint predice cuándo el mapa acierta?

Toda la v2.1 (diseño de dos carriles) depende de una pregunta sin responder:
¿existe un umbral de distancia que sirva como gate de confianza?
  distancia < umbral → copiar directo el mejor brazo del vecino (sin probe)
  distancia >= umbral → probe sin mapa como seguro

Modelo de campo espacial (mock): el espacio [0,1]^4 se particiona en M
celdas de Voronoi; cada celda tiene un mejor brazo aleatorio (5 brazos).
12 clases conocidas muestrean el campo; 400 tareas nuevas por corrida.
Para cada tarea: d = distancia euclídea al vecino conocido más cercano;
acierto = (mejor brazo del vecino == mejor brazo verdadero de la tarea).

M en {2, 5, 20, 50, 200}: de estructura fuerte (celdas grandes) a débil.
Métrica: precisión del mapa en el cuartil de distancia más cercano (Q1)
vs el más lejano (Q4).

Criterio pre-registrado: en M=20, precisión(Q1) >= 0.60 Y
precisión(Q1) >= 2 × precisión(Q4) → PASS (el gate existe).
Regla de confiabilidad: cambio de signo en (Q1-Q4) entre seeds en M=20
→ NO CONFIABLE.

Nota honesta: el mock mide CUÁNTA estructura necesita el gate, no si el
fingerprint real la tiene. Eso se mide con datos reales (pendiente).

100% mock: US$0. No toca DB ni servicio.
Uso: python3 run_experiment29.py [--out DIR]
"""
import argparse
import hashlib
import json
import math
import os
import random

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp29-20260927")

SEEDS = [2921, 2922, 2923, 2924, 2925, 2926, 2927, 2928]
M_NIVELES = [2, 5, 20, 50, 200]
N_CLASES = 12
N_TAREAS = 400
N_BRAZOS = 5
M_CRITERIO = 20


def _rng(*partes):
    digest = hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()
    return random.Random(int(digest, 16) % (2 ** 32))


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def campo(rng, m):
    """M prototipos: (punto, mejor brazo). El campo asigna a cada punto
    el brazo de su prototipo más cercano."""
    protos = [([rng.random() for _ in range(4)], rng.randrange(N_BRAZOS))
              for _ in range(m)]
    def mejor(fp):
        return min(protos, key=lambda p: dist(fp, p[0]))[1]
    return mejor


def correr_nivel(seed, m):
    rng = _rng("exp29", "mundo", seed, m)
    mejor = campo(rng, m)
    clases_fp = [[rng.random() for _ in range(4)] for _ in range(N_CLASES)]
    clases_mejor = [mejor(fp) for fp in clases_fp]

    rng_t = _rng("exp29", "tareas", seed, m)
    pares = []  # (distancia, acierto)
    for _ in range(N_TAREAS):
        fp = [rng_t.random() for _ in range(4)]
        j = min(range(N_CLASES), key=lambda k: dist(fp, clases_fp[k]))
        d = dist(fp, clases_fp[j])
        acierto = 1 if mejor(fp) == clases_mejor[j] else 0
        pares.append((d, acierto))

    pares.sort(key=lambda t: t[0])
    q = N_TAREAS // 4
    q1 = pares[:q]
    q4 = pares[-q:]
    p1 = sum(a for _, a in q1) / q
    p4 = sum(a for _, a in q4) / q
    return {"m": m,
            "q1_precision": round(p1, 4),
            "q4_precision": round(p4, 4),
            "q1_umbral_dist": round(q1[-1][0], 4),
            "q1_n": q, "q4_n": q}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=RES_DIR)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    pre = os.path.join(args.out, "preregistro.json")
    assert os.path.exists(pre), "preregistro.json debe existir ANTES de correr"
    with open(pre) as f:
        json.load(f)

    por_seed = []
    for s in SEEDS:
        niveles = [correr_nivel(s, m) for m in M_NIVELES]
        por_seed.append({"seed": s, "niveles": niveles})

    def media(m, k):
        vals = [nv[k] for sd in por_seed
                for nv in sd["niveles"] if nv["m"] == m]
        return sum(vals) / len(vals)

    curva = [{"m": m,
              "q1_precision_media": round(media(m, "q1_precision"), 4),
              "q4_precision_media": round(media(m, "q4_precision"), 4),
              "q1_umbral_dist_medio": round(media(m, "q1_umbral_dist"), 4)}
             for m in M_NIVELES]

    crit = next(c for c in curva if c["m"] == M_CRITERIO)
    diffs = []
    for sd in por_seed:
        nv = next(n for n in sd["niveles"] if n["m"] == M_CRITERIO)
        diffs.append(round(nv["q1_precision"] - nv["q4_precision"], 4))

    pasa = (crit["q1_precision_media"] >= 0.60 and
            crit["q1_precision_media"] >= 2 * crit["q4_precision_media"])
    signo_cambia = min(diffs) < 0 < max(diffs)
    veredicto = "NO CONFIABLE" if signo_cambia else ("PASS" if pasa else "FAIL")

    reporte = {
        "experimento": "ALMA-EXP29",
        "seeds": SEEDS,
        "m_niveles": M_NIVELES,
        "por_seed": por_seed,
        "curva_precision_por_m": curva,
        "diffs_q1_menos_q4_en_m20": diffs,
        "criterio": f"en M={M_CRITERIO}: Q1>=0.60 Y Q1>=2×Q4 → PASS",
        "veredicto": veredicto,
        "pasa": bool(pasa and not signo_cambia),
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    for c in curva:
        print(f"M={c['m']:>3}: Q1={c['q1_precision_media']:.3f} "
              f"Q4={c['q4_precision_media']:.3f} "
              f"umbral_d~{c['q1_umbral_dist_medio']:.3f}")
    print("diffs Q1-Q4 en M=20:", diffs)
    print("VEREDICTO:", veredicto, "| pasa:", reporte["pasa"])


if __name__ == "__main__":
    main()
