#!/usr/bin/env python3
"""ALMA-EXP35: ¿a partir de qué frecuencia de cambios el seguro EVI+CD se paga solo?

Motivación: EXP34 FAIL mostró que el probe EVI+CD es un seguro — ahorra
~10/episodio con flips ralos, cuesta ~0.5 en estacionario. La pregunta ya no es
de mecanismo sino de tasa base: barrido de f en flips/episodio, estimación de
la frecuencia de corte f* por interpolación lineal del cruce por cero.

Diseño: ver resultados/exp35-20260927/preregistro.json (escrito ANTES de correr).
100% mock: US$0. No toca DB, servicio ni API real bajo ningún concepto.
Uso: python3 run_experiment35.py [--out DIR]
"""
import argparse
import hashlib
import json
import math
import os
import random

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp35-20260927")

SEEDS = [3521, 3522, 3523, 3524, 3525, 3526, 3527, 3528]
TRATS = ["siempre", "evi", "evi-cd"]
FREQS = [0, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]  # flips por episodio
BLOQUES = 10
PULLS_BLOQUE = 80
PROBE_POR_BRAZO = 8
PROBE_TOTAL = PROBE_POR_BRAZO * 3  # 24
P_MEJOR = 0.85
P_RESTO = 0.70
EPISODIOS = 60
EVI_MUESTRAS = 120
OLVIDO = 0.5


def _rng(*partes):
    digest = hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()
    return random.Random(int(digest, 16) % (2 ** 32))


def _poisson(rng, lam):
    # Knuth, suficiente para lam <= 2
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


def medias_post(alfa, beta):
    return [alfa[i] / (alfa[i] + beta[i]) for i in range(3)]


def mejor_posterior(alfa, beta):
    m = medias_post(alfa, beta)
    return max(range(3), key=lambda i: (m[i], -i))


def simular_probe_ganador(rng, mu):
    exitos = []
    for a in range(3):
        k = sum(1 for _ in range(PROBE_POR_BRAZO) if rng.random() < mu[a])
        exitos.append(k)
    return max(range(3), key=lambda i: (exitos[i], -i))


def evi(rng, alfa, beta, horizonte=PULLS_BLOQUE):
    b0 = mejor_posterior(alfa, beta)
    tot = 0.0
    for _ in range(EVI_MUESTRAS):
        mu = [rng.betavariate(alfa[a], beta[a]) for a in range(3)]
        u_commit = horizonte * mu[b0]
        w = simular_probe_ganador(rng, mu)
        u_probe = (PROBE_POR_BRAZO * sum(mu)
                   + (horizonte - PROBE_TOTAL) * mu[w])
        tot += u_probe - u_commit
    return tot / EVI_MUESTRAS


def aplicar_olvido(alfa, beta):
    return ([1.0 + (a - 1.0) * OLVIDO for a in alfa],
            [1.0 + (b - 1.0) * OLVIDO for b in beta])


def intervalo_predictivo(n, a, b, lo=0.025, hi=0.975):
    if n <= 0:
        return (0, 0)
    logB = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    cum = 0.0
    qlo, qhi = 0, n
    lo_ok = False
    for k in range(n + 1):
        lp = (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
              + math.lgamma(k + a) + math.lgamma(n - k + b)
              - math.lgamma(n + a + b) - logB)
        cum += math.exp(lp)
        if not lo_ok and cum >= lo:
            qlo = k
            lo_ok = True
        if cum >= hi:
            qhi = k
            break
    return (qlo, qhi)


def detectar(prev):
    snap_a, snap_b, brazo, n, k = prev
    qlo, qhi = intervalo_predictivo(n, snap_a[brazo], snap_b[brazo])
    return k < qlo or k > qhi


class Mundo:
    def __init__(self, R):
        self.R = R
        self.idx = [0, 0, 0]

    def pull(self, brazo):
        i = self.idx[brazo]
        self.idx[brazo] = i + 1
        return self.R[brazo][i]


def bloque(p, probo, alfa, beta, mundo):
    p_best = max(p)
    regret = 0.0
    if probo:
        exitos = []
        for a in range(3):
            k = 0
            for _ in range(PROBE_POR_BRAZO):
                r = mundo.pull(a)
                k += r
                alfa[a] += r
                beta[a] += 1 - r
                regret += p_best - p[a]
            exitos.append(k)
        ganador = max(range(3), key=lambda i: (exitos[i], -i))
        kc = exitos[ganador]
        for _ in range(PULLS_BLOQUE - PROBE_TOTAL):
            r = mundo.pull(ganador)
            kc += r
            alfa[ganador] += r
            beta[ganador] += 1 - r
            regret += p_best - p[ganador]
        n_comp = PROBE_POR_BRAZO + (PULLS_BLOQUE - PROBE_TOTAL)
        return regret, alfa, beta, ganador, n_comp, kc
    b0 = mejor_posterior(alfa, beta)
    kc = 0
    for _ in range(PULLS_BLOQUE):
        r = mundo.pull(b0)
        kc += r
        alfa[b0] += r
        beta[b0] += 1 - r
        regret += p_best - p[b0]
    return regret, alfa, beta, b0, PULLS_BLOQUE, kc


def episodio(s, e, f, tratamiento, orden, flips):
    """flips = lista ordenada de bloques donde el mejor alterna."""
    alfa = [1.0, 1.0, 1.0]
    beta = [1.0, 1.0, 1.0]
    regret = 0.0
    probes = 0
    fires = 0
    det_tp = 0  # detecciones en el bloque siguiente a un flip
    prev = None
    lado = 0  # 0 -> orden[0] es mejor; 1 -> orden[1]
    fi = 0
    for b in range(BLOQUES):
        while fi < len(flips) and flips[fi] == b:
            lado = 1 - lado
            fi += 1
        mejor = orden[lado]
        p = [P_RESTO, P_RESTO, P_RESTO]
        p[mejor] = P_MEJOR
        if b > 0:
            alfa, beta = aplicar_olvido(alfa, beta)
        mr = _rng("exp35", s, e, f, "mundo", b)
        R = [[1 if mr.random() < p[a] else 0 for _ in range(PULLS_BLOQUE)]
             for a in range(3)]
        mundo = Mundo(R)
        er = _rng("exp35", s, e, f, "evi", b)
        snap_a, snap_b = list(alfa), list(beta)
        if tratamiento == "siempre":
            probo = True
        elif tratamiento == "evi":
            probo = evi(er, alfa, beta) > 0
        else:
            det = prev is not None and detectar(prev)
            if det:
                fires += 1
                if b - 1 in flips:
                    det_tp += 1
            probo = evi(er, alfa, beta) > 0 or det
        r, alfa, beta, bc, nbc, kbc = bloque(p, probo, alfa, beta, mundo)
        regret += r
        probes += 1 if probo else 0
        prev = (snap_a, snap_b, bc, nbc, kbc)
    return regret, probes / BLOQUES, fires, det_tp, len(flips)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=RES_DIR)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "preregistro.json")) as f:
        json.load(f)  # debe existir ANTES de correr

    # res[s][f][t] = lista de regrets por episodio
    res = {}
    diag = {}  # (s,f) -> [fires_tot, det_tp_tot, flips_tot, tasa_probe_evi_cd]
    for s in SEEDS:
        res[s] = {}
        for f in FREQS:
            res[s][f] = {t: [] for t in TRATS}
            fires_tot = det_tp_tot = flips_tot = 0
            probe_tot = 0
            n_ep = 0
            for e in range(EPISODIOS):
                orden_rng = _rng("exp35", s, e, f, "sorteo")
                orden = list(range(3))
                orden_rng.shuffle(orden)
                wr = _rng("exp35", s, e, f, "mundo")
                k = _poisson(wr, f)
                bloques_disp = list(range(2, 9))
                wr.shuffle(bloques_disp)
                flips = sorted(bloques_disp[:min(k, len(bloques_disp))])
                for tratamiento in TRATS:
                    r, tpr, fires, det_tp, nf = episodio(
                        s, e, f, tratamiento, orden, flips)
                    res[s][f][tratamiento].append(r)
                    if tratamiento == "evi-cd":
                        fires_tot += fires
                        det_tp_tot += det_tp
                        flips_tot += nf
                        probe_tot += tpr
                        n_ep += 1
            diag[(s, f)] = {
                "fires_por_episodio": round(fires_tot / n_ep, 4),
                "p_deteccion_en_F+1": (round(det_tp_tot / flips_tot, 4)
                                       if flips_tot else None),
                "flips_totales": flips_tot,
                "tasa_probe_evi_cd": round(probe_tot / n_ep, 4),
            }

    def media(s, f, t):
        v = res[s][f][t]
        return sum(v) / len(v)

    # medias pooled por frecuencia y tratamiento
    pooled = {f: {t: round(sum(media(s, f, t) for s in SEEDS) / len(SEEDS), 4)
                  for t in TRATS}
              for f in FREQS}
    # diffs pooled y por seed
    diffs_pooled = {}
    diffs_seed = {}
    for c in ("evi", "siempre"):
        diffs_pooled[c] = {f: round(pooled[f]["evi-cd"] - pooled[f][c], 4)
                           for f in FREQS}
        diffs_seed[c] = {s: {f: round(media(s, f, "evi-cd") - media(s, f, c), 4)
                             for f in FREQS}
                         for s in SEEDS}

    def cruces(d):
        """Índices i (entre FREQS[i], FREQS[i+1]) donde d cruza cero
        descendiendo o ascendiendo; devuelve lista de (i, dirección)."""
        out = []
        for i in range(len(FREQS) - 1):
            a, b = d[FREQS[i]], d[FREQS[i + 1]]
            if a == 0:
                continue
            if (a > 0) != (b > 0):
                out.append((i, "desc" if a > 0 else "asc"))
        return out

    def interpolar(d, i):
        f0, f1 = FREQS[i], FREQS[i + 1]
        a, b = d[f0], d[f1]
        return f0 + (0 - a) * (f1 - f0) / (b - a)

    # estimación de f* vs evi (comparación difícil)
    cr_pooled = cruces(diffs_pooled["evi"])
    fstar_seeds = {}
    for s in SEEDS:
        cr = cruces(diffs_seed["evi"][s])
        # cruce descendente único y bracketed dentro de (0, 2.0]
        desc = [i for (i, d) in cr if d == "desc"]
        if len(cr) == 1 and len(desc) == 1 and FREQS[desc[0]] >= 0:
            fstar_seeds[s] = round(interpolar(diffs_seed["evi"][s], desc[0]), 4)
        else:
            fstar_seeds[s] = None
    validas = {s: v for s, v in fstar_seeds.items() if v is not None}
    if validas:
        vals = list(validas.values())
        m = sum(vals) / len(vals)
        var = sum((v - m) ** 2 for v in vals) / len(vals)
        fstar_media = round(m, 4)
        fstar_desvio = round(math.sqrt(var), 4)
        fstar_cv = round(math.sqrt(var) / m, 4) if m > 0 else None
    else:
        fstar_media = fstar_desvio = fstar_cv = None
    fstar_pooled = None
    if len(cr_pooled) == 1 and cr_pooled[0][1] == "desc":
        fstar_pooled = round(interpolar(diffs_pooled["evi"], cr_pooled[0][0]), 4)

    # veredicto según preregistro
    d0 = diffs_pooled["evi"][0]
    dmax = diffs_pooled["evi"][2.0]
    n_validas = len(validas)
    if d0 < 0:
        veredicto = "FAIL"  # f*=0: el seguro es gratis, no hay corte interior
        motivo = (f"d_evi pooled ya <0 en f=0 ({d0}): f*=0, "
                  "sin corte interior en (0, 2.0]")
    elif dmax >= 0:
        veredicto = "FAIL"
        motivo = (f"d_evi pooled >=0 en toda la grilla (f=2.0: {dmax}): "
                  "el seguro nunca se paga en rango")
    elif not (len(cr_pooled) == 1 and cr_pooled[0][1] == "desc"):
        veredicto = "NO CONFIABLE"
        motivo = f"cruces pooled != 1 descendente: {cr_pooled}"
    elif n_validas < 7:
        veredicto = "NO CONFIABLE"
        motivo = f"solo {n_validas}/8 seeds con cruce bracketed"
    elif fstar_cv is not None and fstar_cv >= 1.0:
        veredicto = "NO CONFIABLE"
        motivo = f"CV de f* = {fstar_cv} >= 1.0 (impreciso)"
    else:
        veredicto = "PASS"
        motivo = (f"f* = {fstar_media} ± {fstar_desvio} flips/episodio "
                  f"(CV={fstar_cv}, {n_validas}/8 seeds; pooled {fstar_pooled})")

    reporte = {
        "experimento": "ALMA-EXP35",
        "seeds": SEEDS,
        "episodios_por_seed_frecuencia": EPISODIOS,
        "frecuencias_flips_por_episodio": FREQS,
        "tratamientos": TRATS,
        "regret_medio_pooled": pooled,
        "diffs_pooled_evi_cd_menos_control": diffs_pooled,
        "diffs_por_seed": diffs_seed,
        "fstar_vs_evi_por_seed": fstar_seeds,
        "fstar_vs_evi_media": fstar_media,
        "fstar_vs_evi_desvio": fstar_desvio,
        "fstar_vs_evi_cv": fstar_cv,
        "fstar_vs_evi_pooled": fstar_pooled,
        "diagnostico_detector_por_frecuencia": diag,
        "criterio": ("PASS si d_evi pooled cruza cero exactamente una vez en "
                     "(0, 2.0] descendiendo, >=7/8 seeds con cruce bracketed "
                     "y CV(f*)<1.0"),
        "veredicto": veredicto,
        "motivo": motivo,
    }
    with open(os.path.join(args.out, "report.json"), "w",
              encoding="utf-8") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    print("frecuencia | siempre | evi    | evi-cd | d_vs_evi | d_vs_siempre")
    for f in FREQS:
        print(f"  {f:>4}     | {pooled[f]['siempre']:>7} | "
              f"{pooled[f]['evi']:>6} | {pooled[f]['evi-cd']:>6} | "
              f"{diffs_pooled['evi'][f]:>8} | {diffs_pooled['siempre'][f]:>8}")
    print("f* por seed (vs evi):", fstar_seeds)
    print(f"f* media: {fstar_media} ± {fstar_desvio} (CV={fstar_cv}), "
          f"pooled: {fstar_pooled}")
    print("VEREDICTO:", veredicto, "-", motivo)


if __name__ == "__main__":
    main()
