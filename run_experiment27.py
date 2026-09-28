#!/usr/bin/env python3
"""ALMA-EXP27: transferencia SIN mapa de parecido.

Diagnóstico de EXP26: el probe acierta ~al azar y el problema no es cuánto
medir sino A QUIÉN pedirle prestado — el fingerprint de parecido es el
eslabón débil, no el probe.

Pregunta: ¿el mapa de parecido agrega valor, o es peso muerto?
Diseño: el probe evalúa candidatos de TODAS las clases por igual (shortlist
por frecuencia global de "mejor brazo"), sin ningún juicio de similitud.
Si le gana al fingerprint, el mapa va a la basura.

Dos episodios por seed (120 pulls c/u):
  EP1 fingerprint-correcto: N_a cerca de C0, comparten mejor brazo (cot).
        fingerprint shortlist = top-3 de C0 = [cot, single, plan]
        mapless shortlist     = top-3 por frecuencia = [cot, single, reflexion]
  EP2 trampa: N_b cerca de C1, mejor brazo distinto (cot vs single).
        fingerprint shortlist = top-3 de C1 = [single, debate, plan] (sin cot!)
        mapless shortlist     = [cot, single, reflexion]

Tratamientos (misma regla de ruido v2 en a y b: 8 pulls x brazo,
gap>0.15 -> compromiso duro, si no Thompson adaptativo + re-probe c/24):
  (a) fingerprint + probe v2
  (b) mapless + probe v2
  (c) vecino manual x120 (referencia)
  (d) desde cero Thompson x120 (diagnóstico)

Criterio pre-registrado: media regret(b) < media regret(a) -> PASS.
Regla de confiabilidad: cambio de signo en diffs(b-a) -> NO CONFIABLE.

100% mock: US$0. No toca DB ni servicio.
Uso: python3 run_experiment27.py [--out DIR]
"""
import argparse
import hashlib
import json
import math
import os
import random

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp27-20260927")

SEEDS = [2721, 2722, 2723, 2724, 2725, 2726, 2727, 2728]
BRAZOS = ["single", "cot", "reflexion", "plan", "debate"]
STREAM = 120
PULLS_PROBE_POR_BRAZO = 8
UMBRAL_RUIDO = 0.15
REPROBE_CADA = 24
P_ORACULO = 0.90

# Recompensas por clase conocida (mejor brazo primero en el dict)
RECOMP_CLASE = {
    "C0": {"cot": 0.88, "single": 0.80, "plan": 0.79, "reflexion": 0.74, "debate": 0.62},
    "C1": {"single": 0.90, "debate": 0.80, "plan": 0.75, "cot": 0.70, "reflexion": 0.65},
    "C2": {"reflexion": 0.88, "cot": 0.79, "single": 0.73, "debate": 0.66, "plan": 0.61},
    "C3": {"cot": 0.89, "reflexion": 0.81, "single": 0.75, "plan": 0.69, "debate": 0.63},
    "C4": {"plan": 0.88, "single": 0.80, "cot": 0.76, "debate": 0.68, "reflexion": 0.62},
}
FP = {
    "C0": [0.9, 0.1, 0.2, 0.1],
    "C1": [0.18, 0.82, 0.18, 0.28],
    "C2": [0.5, 0.5, 0.5, 0.5],
    "C3": [0.3, 0.4, 0.3, 0.6],
    "C4": [0.1, 0.2, 0.9, 0.1],
}
MEJOR_BRAZO = {c: max(r, key=lambda b: r[b]) for c, r in RECOMP_CLASE.items()}
TOP3_CLASE = {c: sorted(r, key=lambda b: r[b], reverse=True)[:3]
              for c, r in RECOMP_CLASE.items()}

# Episodios: (tag, fingerprint de N, recompensas verdaderas de N,
#             vecino esperado por fingerprint)
EPISODIOS = [
    ("EP1", [0.85, 0.15, 0.25, 0.12],
     {"cot": 0.90, "single": 0.78, "reflexion": 0.72, "plan": 0.66, "debate": 0.60},
     "C0"),
    ("EP2", [0.2, 0.8, 0.2, 0.3],
     {"cot": 0.90, "single": 0.78, "reflexion": 0.72, "plan": 0.66, "debate": 0.60},
     "C1"),
]


def _rng(*partes):
    digest = hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()
    return random.Random(int(digest, 16) % (2 ** 32))


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def vecino_mas_cercano(fp_n):
    return min(MEJOR_BRAZO, key=lambda c: dist(FP[c], fp_n))


def shortlist_mapless():
    # top-3 brazos por frecuencia de ser el mejor entre clases conocidas,
    # desempate por orden fijo de BRAZOS. Sin juicio de parecido.
    freq = {b: 0 for b in BRAZOS}
    for c in MEJOR_BRAZO:
        freq[MEJOR_BRAZO[c]] += 1
    return sorted(BRAZOS, key=lambda b: (-freq[b], BRAZOS.index(b)))[:3]


def pull(brazo, recomp, rng):
    return 1 if rng.random() < recomp[brazo] else 0


def thompson_pick(rng, alfa, beta, brazos):
    thetas = {b: rng.betavariate(alfa[b], beta[b]) for b in brazos}
    return max(brazos, key=lambda x: thetas[x])


def correr_probe_v2(candidatas, recomp, tag_rng):
    """Probe consciente de ruido (idéntico en a y b). Devuelve dict con
    regret del episodio, ganador del probe, gap, compromiso y acierto."""
    rng_p = _rng("exp27", "probe", tag_rng)
    obs = {}
    for b in candidatas:
        rs = [pull(b, recomp, rng_p) for _ in range(PULLS_PROBE_POR_BRAZO)]
        obs[b] = [sum(rs), len(rs) - sum(rs)]
    medias = {b: obs[b][0] / PULLS_PROBE_POR_BRAZO for b in candidatas}
    orden = sorted(candidatas, key=lambda b: medias[b], reverse=True)
    ganador = orden[0]
    gap = round(medias[orden[0]] - medias[orden[1]], 4)
    usados = PULLS_PROBE_POR_BRAZO * len(candidatas)
    regret_probe = sum(P_ORACULO - r for b in candidatas
                       for r in [1] * obs[b][0] + [0] * obs[b][1])

    rng_e = _rng("exp27", "explota", tag_rng)
    if gap > UMBRAL_RUIDO:
        compromiso = "duro"
        resto = [pull(ganador, recomp, rng_e) for _ in range(STREAM - usados)]
    else:
        compromiso = "adaptativo"
        alfa = {b: 1.0 + obs[b][0] for b in candidatas}
        beta = {b: 1.0 + obs[b][1] for b in candidatas}
        resto = []
        for i in range(1, STREAM - usados + 1):
            if i % REPROBE_CADA == 0:
                for b in candidatas:
                    r = pull(b, recomp, rng_e)
                    resto.append(r)
                    alfa[b] += r
                    beta[b] += 1 - r
            else:
                b = thompson_pick(rng_e, alfa, beta, candidatas)
                r = pull(b, recomp, rng_e)
                resto.append(r)
                alfa[b] += r
                beta[b] += 1 - r
    regret = regret_probe + sum(P_ORACULO - r for r in resto)
    mejor_verdadero = max(recomp, key=lambda b: recomp[b])
    return {"regret": round(regret, 4),
            "candidatas": candidatas,
            "ganador_probe": ganador,
            "gap": gap,
            "compromiso": compromiso,
            "acierto_probe": ganador == mejor_verdadero}


def correr_seed(seed):
    res = {"seed": seed, "episodios": {}}
    tot_a = tot_b = tot_c = tot_d = 0.0
    aciertos_a = aciertos_b = 0
    n_ep = 0
    for ep_tag, fp_n, recomp, vecino_esperado in EPISODIOS:
        # --- verificar el setup del episodio ---
        vecino = vecino_mas_cercano(fp_n)
        assert vecino == vecino_esperado, \
            f"{ep_tag}: setup roto, vecino={vecino} esperado={vecino_esperado}"
        short_a = TOP3_CLASE[vecino]          # con mapa: top-3 del vecino
        short_b = shortlist_mapless()          # sin mapa: top-3 por frecuencia
        ep = {"vecino_fingerprint": vecino,
              "shortlist_fingerprint": short_a,
              "shortlist_mapless": short_b}

        tag = f"{seed}-{ep_tag}"
        ra = correr_probe_v2(short_a, recomp, tag + "-a")
        rb = correr_probe_v2(short_b, recomp, tag + "-b")
        ep["a_fingerprint"] = ra
        ep["b_mapless"] = rb
        tot_a += ra["regret"]
        tot_b += rb["regret"]
        aciertos_a += ra["acierto_probe"]
        aciertos_b += rb["acierto_probe"]
        n_ep += 1

        # --- (c) vecino manual: mejor brazo del vecino x120 ---
        rng_c = _rng("exp27", "vecino", tag)
        brazo_c = MEJOR_BRAZO[vecino]
        r_c = [pull(brazo_c, recomp, rng_c) for _ in range(STREAM)]
        rc = round(sum(P_ORACULO - r for r in r_c), 4)
        ep["c_vecino"] = {"brazo": brazo_c, "regret": rc}
        tot_c += rc

        # --- (d) desde cero: Thompson x120 sobre los 5 brazos ---
        rng_d = _rng("exp27", "cero", tag)
        alfa = {b: 1.0 for b in BRAZOS}
        beta = {b: 1.0 for b in BRAZOS}
        rd = 0.0
        for _ in range(STREAM):
            b = thompson_pick(rng_d, alfa, beta, BRAZOS)
            r = pull(b, recomp, rng_d)
            rd += P_ORACULO - r
            alfa[b] += r
            beta[b] += 1 - r
        ep["d_cero"] = {"regret": round(rd, 4)}
        tot_d += rd

        res["episodios"][ep_tag] = ep

    res["totales"] = {
        "a_fingerprint": round(tot_a, 4),
        "b_mapless": round(tot_b, 4),
        "c_vecino": round(tot_c, 4),
        "d_cero": round(tot_d, 4),
        "aciertos_probe_a": f"{aciertos_a}/{n_ep}",
        "aciertos_probe_b": f"{aciertos_b}/{n_ep}",
    }
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

    # verificación global del diseño (independiente de seed)
    assert shortlist_mapless() == ["cot", "single", "reflexion"], \
        f"shortlist mapless inesperada: {shortlist_mapless()}"
    assert TOP3_CLASE["C0"] == ["cot", "single", "plan"], TOP3_CLASE["C0"]
    assert TOP3_CLASE["C1"] == ["single", "debate", "plan"], TOP3_CLASE["C1"]

    por_seed = [correr_seed(s) for s in SEEDS]

    def media(k):
        return sum(r["totales"][k] for r in por_seed) / len(por_seed)

    reg_a = media("a_fingerprint")
    reg_b = media("b_mapless")
    reg_c = media("c_vecino")
    reg_d = media("d_cero")
    diffs = [r["totales"]["b_mapless"] - r["totales"]["a_fingerprint"]
             for r in por_seed]

    pasa = reg_b < reg_a
    signo_cambia = min(diffs) < 0 < max(diffs)
    veredicto = "NO CONFIABLE" if signo_cambia else ("PASS" if pasa else "FAIL")

    ac_a = sum(int(r["totales"]["aciertos_probe_a"].split("/")[0]) for r in por_seed)
    ac_b = sum(int(r["totales"]["aciertos_probe_b"].split("/")[0]) for r in por_seed)
    n_ep_total = len(SEEDS) * len(EPISODIOS)

    reporte = {
        "experimento": "ALMA-EXP27",
        "seeds": SEEDS,
        "por_seed": por_seed,
        "medias_regret": {
            "a_fingerprint_probe_v2": round(reg_a, 4),
            "b_mapless_probe_v2": round(reg_b, 4),
            "c_vecino_manual": round(reg_c, 4),
            "d_desde_cero_diag": round(reg_d, 4),
        },
        "diffs_b_menos_a": [round(d, 4) for d in diffs],
        "criterio": "media regret(b) < media regret(a) → PASS (el mapa es peso muerto)",
        "veredicto": veredicto,
        "pasa": bool(pasa and not signo_cambia),
        "acierto_probe_global": {
            "a_fingerprint": f"{ac_a}/{n_ep_total}",
            "b_mapless": f"{ac_b}/{n_ep_total}",
        },
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    print(json.dumps(reporte["medias_regret"], indent=2, ensure_ascii=False))
    print("diffs b-a:", reporte["diffs_b_menos_a"])
    print("acierto probe:", reporte["acierto_probe_global"])
    print("VEREDICTO:", veredicto, "| pasa:", reporte["pasa"])


if __name__ == "__main__":
    main()
