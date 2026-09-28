#!/usr/bin/env python3
"""ALMA-EXP26: ¿el probe-transfer aporta algo sobre Thompson pelado, o es peso muerto?

Refutación primero. En EXP24 el Thompson desde cero (5,0) le ganó al probe v2
(8,1); en EXP25 k=64 le ganó 4x (6,7 vs 27,1). Este experimento va contra ALMA
misma: ALMA v2 completa vs Thompson pelado desde cero, en 4 clases nuevas
frescas (ninguna de EXP21/24/25), dos horizontes (120, 240), 6 seeds nuevas
por horizonte.

Brazos por clase nueva:
  (a) alma_v2: probe 8 pulls x candidatas (brazos deduplicados de las 3
      conocidas más cercanas por fingerprint); gap=m1-m2; si gap>0.15
      compromiso duro con el ganador; si no, Thompson adaptativo con priors
      del probe + re-probe cada 24 pulls.
  (b) thompson_cero: Thompson pelado, prior uniforme Beta(1,1), 3 brazos,
      sin probe, sin memoria.
  (c) mejor_fijo: mejor brazo fijo por clase (diagnóstico, techo).

Criterio POR HORIZONTE: media(a) < media(b), 6 seeds; cambio de signo en
diffs(a-b) -> NO CONFIABLE. Si (b) <= (a) confiable -> PESO MUERTO.

100% mock: US$0, ninguna llamada a API. No toca DB ni servicio ni EXP18.
Uso: python3 run_experiment26.py [--out DIR]
"""
import argparse
import hashlib
import json
import math
import os
import random

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp26-20260926")

SEEDS = {"h120": [2621, 2622, 2623, 2624, 2625, 2626],
         "h240": [2631, 2632, 2633, 2634, 2635, 2636]}
HORIZONTES = [120, 240]
BRAZOS = ["single", "cot", "reflexion"]
PULLS_PROBE = 8
UMBRAL_RUIDO = 0.15
REPROBE_CADA = 24
P_ORACULO = 0.90

# --- Clases conocidas (memoria) ---
CONOCIDAS = {
    "K0": {"fp": [0.1, 0.1, 0.5, 0.5], "mejor": "cot"},
    "K1": {"fp": [0.9, 0.1, 0.5, 0.5], "mejor": "single"},
    "K2": {"fp": [0.1, 0.9, 0.5, 0.5], "mejor": "reflexion"},
    "K3": {"fp": [0.9, 0.9, 0.5, 0.5], "mejor": "single"},
}
# --- Clases nuevas frescas (ninguna de EXP21/24/25) ---
NUEVAS = {
    "N0": {"fp": [0.85, 0.15, 0.5, 0.5], "mejor": "cot",
           "recomp": {"cot": 0.90, "single": 0.78, "reflexion": 0.65}},
    "N1": {"fp": [0.15, 0.15, 0.5, 0.5], "mejor": "single",
           "recomp": {"single": 0.90, "cot": 0.78, "reflexion": 0.65}},
    "N2": {"fp": [0.85, 0.85, 0.5, 0.5], "mejor": "reflexion",
           "recomp": {"reflexion": 0.90, "single": 0.78, "cot": 0.65}},
    "N3": {"fp": [0.15, 0.85, 0.5, 0.5], "mejor": "cot",
           "recomp": {"cot": 0.90, "reflexion": 0.78, "single": 0.65}},
}


def _rng(*partes):
    digest = hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()
    return random.Random(int(digest, 16) % (2 ** 32))


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def verificar_trampas():
    """Cada clase nueva: la conocida más cercana es TRAMPA (mejor brazo
    distinto) y el brazo verdadero está entre las candidatas."""
    info = {}
    for n, nd in NUEVAS.items():
        orden = sorted(CONOCIDAS.items(),
                       key=lambda kv: dist(nd["fp"], kv[1]["fp"]))
        mas_cercana = orden[0][0]
        assert CONOCIDAS[mas_cercana]["mejor"] != nd["mejor"], \
            f"trampa rota en {n}: {mas_cercana}"
        candidatas = []
        for k, kd in orden[:3]:
            if kd["mejor"] not in candidatas:
                candidatas.append(kd["mejor"])
        assert nd["mejor"] in candidatas, \
            f"brazo verdadero fuera de candidatas en {n}"
        info[n] = {"trampa": mas_cercana,
                   "candidatas": candidatas,
                   "distancias": {k: round(dist(nd["fp"], kd["fp"]), 4)
                                  for k, kd in orden}}
    return info


TRAMPAS = verificar_trampas()


def pull(recomp, brazo, rng):
    return 1 if rng.random() < recomp[brazo] else 0


def thompson_pick(rng, alfa, beta, brazos):
    thetas = {b: rng.betavariate(alfa[b], beta[b]) for b in brazos}
    return max(brazos, key=lambda x: thetas[x])


def correr_clase(n, horizonte, seed):
    nd = NUEVAS[n]
    recomp = nd["recomp"]
    mejor = nd["mejor"]
    candidatas = TRAMPAS[n]["candidatas"]
    det = {"clase": n, "mejor": mejor, "candidatas": candidatas}

    # --- (a) ALMA v2 completa ---
    rng_p = _rng("exp26", "a-probe", horizonte, n, seed)
    obs = {}
    for b in candidatas:
        rs = [pull(recomp, b, rng_p) for _ in range(PULLS_PROBE)]
        obs[b] = [sum(rs), len(rs) - sum(rs)]
    medias = {b: obs[b][0] / PULLS_PROBE for b in candidatas}
    orden = sorted(candidatas, key=lambda b: medias[b], reverse=True)
    ganador = max(candidatas, key=lambda b: (medias[b], -candidatas.index(b)))
    gap = round(medias[orden[0]] - medias[orden[1]], 4) if len(orden) > 1 else 1.0
    usados = PULLS_PROBE * len(candidatas)
    regret_probe = sum(P_ORACULO - r for b in candidatas
                       for r in [1] * obs[b][0] + [0] * obs[b][1])

    rng_a = _rng("exp26", "a-resto", horizonte, n, seed)
    if gap > UMBRAL_RUIDO:
        compromiso = "duro"
        resto = [pull(recomp, ganador, rng_a)
                 for _ in range(horizonte - usados)]
        adapt, reprobes = 0, 0
    else:
        compromiso = "adaptativo"
        alfa = {b: 1.0 + obs[b][0] for b in candidatas}
        beta = {b: 1.0 + obs[b][1] for b in candidatas}
        resto, adapt, reprobes = [], 0, 0
        for i in range(1, horizonte - usados + 1):
            if i % REPROBE_CADA == 0:
                reprobes += 1
                for b in candidatas:
                    r = pull(recomp, b, rng_a)
                    resto.append(r)
                    alfa[b] += r
                    beta[b] += 1 - r
            else:
                b = thompson_pick(rng_a, alfa, beta, candidatas)
                r = pull(recomp, b, rng_a)
                resto.append(r)
                alfa[b] += r
                beta[b] += 1 - r
                adapt += 1
    reg_a = regret_probe + sum(P_ORACULO - r for r in resto)
    det["a"] = {"gap": gap, "compromiso": compromiso,
                "ganador_probe": ganador,
                "acierto_probe": ganador == mejor,
                "pulls_adaptativos": adapt, "re_probes": reprobes,
                "regret": round(reg_a, 4)}

    # --- (b) Thompson pelado desde cero ---
    rng_b = _rng("exp26", "b", horizonte, n, seed)
    alfa = {b: 1.0 for b in BRAZOS}
    beta = {b: 1.0 for b in BRAZOS}
    rb = []
    for _ in range(horizonte):
        b = thompson_pick(rng_b, alfa, beta, BRAZOS)
        r = pull(recomp, b, rng_b)
        rb.append(r)
        alfa[b] += r
        beta[b] += 1 - r
    det["b"] = {"regret": round(sum(P_ORACULO - r for r in rb), 4)}

    # --- (c) mejor brazo fijo (diagnóstico) ---
    rng_c = _rng("exp26", "c", horizonte, n, seed)
    rc = [pull(recomp, mejor, rng_c) for _ in range(horizonte)]
    det["c"] = {"brazo": mejor,
                "regret": round(sum(P_ORACULO - r for r in rc), 4)}
    return det


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=RES_DIR)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    pre = os.path.join(args.out, "preregistro.json")
    assert os.path.exists(pre), "preregistro.json debe existir ANTES de correr"
    with open(pre) as f:
        json.load(f)

    reporte = {"experimento": "ALMA-EXP26", "umbral_ruido": UMBRAL_RUIDO,
               "trampas": TRAMPAS, "por_horizonte": {}}

    for h in HORIZONTES:
        por_seed = []
        for s in SEEDS[f"h{h}"]:
            clases = [correr_clase(n, h, s) for n in sorted(NUEVAS)]
            por_seed.append({
                "seed": s,
                "regret_a": round(sum(c["a"]["regret"] for c in clases) / 4, 4),
                "regret_b": round(sum(c["b"]["regret"] for c in clases) / 4, 4),
                "regret_c": round(sum(c["c"]["regret"] for c in clases) / 4, 4),
                "por_clase": clases,
            })
        ma = sum(r["regret_a"] for r in por_seed) / len(por_seed)
        mb = sum(r["regret_b"] for r in por_seed) / len(por_seed)
        mc = sum(r["regret_c"] for r in por_seed) / len(por_seed)
        diffs = [r["regret_a"] - r["regret_b"] for r in por_seed]
        signo_cambia = min(diffs) < 0 < max(diffs)
        if signo_cambia:
            veredicto = "NO CONFIABLE"
        elif ma < mb:
            veredicto = "PASS"
        else:
            veredicto = "PESO MUERTO"
        reporte["por_horizonte"][f"h{h}"] = {
            "seeds": SEEDS[f"h{h}"],
            "media_regret_a": round(ma, 4),
            "media_regret_b": round(mb, 4),
            "media_regret_c_diag": round(mc, 4),
            "diffs_a_menos_b": [round(d, 4) for d in diffs],
            "criterio": "regret(a) < regret(b) (medias); cambio de signo -> NO CONFIABLE",
            "veredicto": veredicto,
            "por_seed": por_seed,
        }

    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    for h in HORIZONTES:
        r = reporte["por_horizonte"][f"h{h}"]
        print(f"h={h}: a={r['media_regret_a']} b={r['media_regret_b']} "
              f"c={r['media_regret_c_diag']} | diffs={r['diffs_a_menos_b']} "
              f"| VEREDICTO: {r['veredicto']}")
    print("costo: US$0 (mock)")


if __name__ == "__main__":
    main()
