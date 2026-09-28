#!/usr/bin/env python3
"""ALMA-EXP34: ¿EVI + detección de cambios supera a los controles con flips RALOS?

Motivación: EXP33 NO CONFIABLE — el detector tiene lag de 1 bloque por
construcción; con flips en cada bloque, cuando dispara el mundo ya volvió a
flipear y el probe forzado es costo puro. Hipótesis: la detección vale cuando
los flips son ralos respecto del lag (1 flip por episodio, como la vida real).
Además se corrige el ruido RNG de EXP33: números aleatorios comunes entre
tratamientos vía potential outcomes.

Diseño: ver resultados/exp34-20260927/preregistro.json (escrito ANTES de correr).
100% mock: US$0. No toca DB, servicio ni API real bajo ningún concepto.
Uso: python3 run_experiment34.py [--out DIR]
"""
import argparse
import hashlib
import json
import math
import os
import random

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp34-20260927")

SEEDS = [3421, 3422, 3423, 3424, 3425, 3426, 3427, 3428]
TRATS = ["siempre", "evi", "evi-cd"]
REGIMENES = ["estacionario", "flip_ralo"]
BLOQUES = 10
PULLS_BLOQUE = 80
PROBE_POR_BRAZO = 8
PROBE_TOTAL = PROBE_POR_BRAZO * 3  # 24
P_MEJOR = 0.85
P_RESTO = 0.70
EPISODIOS = 50
EVI_MUESTRAS = 120
OLVIDO = 0.5


def _rng(*partes):
    digest = hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()
    return random.Random(int(digest, 16) % (2 ** 32))


def medias_post(alfa, beta):
    return [alfa[i] / (alfa[i] + beta[i]) for i in range(3)]


def mejor_posterior(alfa, beta):
    m = medias_post(alfa, beta)
    return max(range(3), key=lambda i: (m[i], -i))  # desempate: orden fijo


def simular_probe_ganador(rng, mu):
    """Un probe simulado (8 Bernoulli/brazo) con medias verdaderas mu."""
    exitos = []
    for a in range(3):
        k = sum(1 for _ in range(PROBE_POR_BRAZO) if rng.random() < mu[a])
        exitos.append(k)
    return max(range(3), key=lambda i: (exitos[i], -i))


def evi(rng, alfa, beta, horizonte=PULLS_BLOQUE):
    """Valor Esperado de la Información de probar, bajo la creencia actual."""
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
    """Intervalo central [q_lo, q_hi] de la BetaBinomial(n, a, b) exacta
    (pmf vía lgamma; determinista)."""
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
    """prev = (snap_alfa, snap_beta, brazo, n, k) del bloque anterior.
    True si los éxitos observados caen fuera del intervalo predictivo 95%
    de la posterior que regía al inicio de ese bloque."""
    snap_a, snap_b, brazo, n, k = prev
    qlo, qhi = intervalo_predictivo(n, snap_a[brazo], snap_b[brazo])
    return k < qlo or k > qhi


class Mundo:
    """Potential outcomes de un bloque: matriz R[brazo][pull] compartida
    por los 3 tratamientos (números aleatorios comunes). Cada tratamiento
    lleva sus propios índices de consumo."""

    def __init__(self, R):
        self.R = R
        self.idx = [0, 0, 0]

    def pull(self, brazo):
        i = self.idx[brazo]
        self.idx[brazo] = i + 1
        return self.R[brazo][i]


def bloque(p, probo, alfa, beta, mundo):
    """Ejecuta un bloque con la decisión ya tomada, leyendo del mundo
    compartido. Devuelve (regret, alfa, beta, brazo_comprometido, n_comp,
    k_comp)."""
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


def episodio(s, e, regimen, tratamiento, orden, flip_bloque):
    """Un episodio de 10 bloques. Devuelve (regret, tasa_probe,
    bloques_deteccion)."""
    alfa = [1.0, 1.0, 1.0]
    beta = [1.0, 1.0, 1.0]
    regret = 0.0
    probes = 0
    fires = []
    prev = None  # (snap_alfa, snap_beta, brazo, n, k) del bloque anterior
    for b in range(BLOQUES):
        if regimen == "estacionario":
            mejor = orden[0]
        else:  # flip_ralo: 1 flip por episodio, efectivo al inicio de F
            mejor = orden[0] if b < flip_bloque else orden[1]
        p = [P_RESTO, P_RESTO, P_RESTO]
        p[mejor] = P_MEJOR
        if b > 0:
            alfa, beta = aplicar_olvido(alfa, beta)
        # mundo compartido entre tratamientos (potential outcomes)
        mr = _rng("exp34", s, e, regimen, "mundo", b)
        R = [[1 if mr.random() < p[a] else 0 for _ in range(PULLS_BLOQUE)]
             for a in range(3)]
        mundo = Mundo(R)
        # rng propio del EVI (compartido entre evi y evi-cd)
        er = _rng("exp34", s, e, regimen, "evi", b)
        snap_a, snap_b = list(alfa), list(beta)
        if tratamiento == "siempre":
            probo = True
        elif tratamiento == "evi":
            probo = evi(er, alfa, beta) > 0
        else:  # evi-cd
            det = prev is not None and detectar(prev)
            if det:
                fires.append(b)
            probo = evi(er, alfa, beta) > 0 or det
        r, alfa, beta, bc, nbc, kbc = bloque(p, probo, alfa, beta, mundo)
        regret += r
        probes += 1 if probo else 0
        prev = (snap_a, snap_b, bc, nbc, kbc)
    return regret, probes / BLOQUES, fires


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=RES_DIR)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "preregistro.json")) as f:
        json.load(f)  # debe existir ANTES de correr

    res, tasa = {}, {}
    diag = {}  # (s) -> lista de (F, fires) para evi-cd en flip_ralo
    for s in SEEDS:
        res[s] = {}
        tasa[s] = {}
        diag[s] = []
        for regimen in REGIMENES:
            res[s][regimen] = {t: [] for t in TRATS}
            tp = {t: [] for t in TRATS}
            for e in range(EPISODIOS):
                # sorteo del mundo compartido por los 3 tratamientos
                orden_rng = _rng("exp34", s, e, regimen, "sorteo")
                orden = list(range(3))
                orden_rng.shuffle(orden)
                flip_bloque = None
                if regimen == "flip_ralo":
                    fr = _rng("exp34", s, e, regimen, "flip")
                    flip_bloque = fr.randint(2, 8)
                for tratamiento in TRATS:
                    r, tpr, fires = episodio(s, e, regimen, tratamiento,
                                            orden, flip_bloque)
                    res[s][regimen][tratamiento].append(r)
                    tp[tratamiento].append(tpr)
                    if regimen == "flip_ralo" and tratamiento == "evi-cd":
                        diag[s].append((flip_bloque, fires))
            for t in TRATS:
                tasa.setdefault((s, regimen), {})[t] = sum(tp[t]) / len(tp[t])

    def media(s, regimen, tratamiento):
        v = res[s][regimen][tratamiento]
        return sum(v) / len(v)

    resumen = {}
    for regimen in REGIMENES:
        resumen[regimen] = {}
        for t in TRATS:
            resumen[regimen][t] = round(
                sum(media(s, regimen, t) for s in SEEDS) / len(SEEDS), 4)
    pooled = {t: round(sum(resumen[r][t] for r in REGIMENES) / 2, 4)
              for t in TRATS}
    tasa_media = {r: {t: round(sum(tasa[(s, r)][t] for s in SEEDS)
                               / len(SEEDS), 4)
                      for t in TRATS}
                  for r in REGIMENES}

    # diagnóstico del detector en flip_ralo (evi-cd)
    n_ep = 0
    tp = late = 0
    lags = []
    fp_por_episodio = 0.0
    for s in SEEDS:
        for (F, fires) in diag[s]:
            n_ep += 1
            fs = set(fires)
            if (F + 1) in fs:
                tp += 1
                lags.append(0)
            else:
                post = sorted(x for x in fs if x > F + 1)
                if post:
                    late += 1
                    lags.append(post[0] - (F + 1))
            fp_por_episodio += sum(1 for x in fs if x < F + 1)
    det_diag = {
        "episodios": n_ep,
        "p_deteccion_en_F+1": round(tp / n_ep, 4),
        "p_deteccion_tardia_dado_no_TP": round(
            late / (n_ep - tp), 4) if n_ep > tp else 0.0,
        "lag_medio_bloques": round(sum(lags) / len(lags), 3) if lags else None,
        "falsos_positivos_por_episodio": round(fp_por_episodio / n_ep, 4),
    }

    # diffs por seed y confiabilidad (ambas comparaciones, ambos regímenes)
    diffs = {}
    confiable = True
    for regimen in REGIMENES:
        diffs[regimen] = {"vs_siempre": {}, "vs_evi": {}}
        for clave, otro in (("vs_siempre", "siempre"), ("vs_evi", "evi")):
            signos = set()
            for s in SEEDS:
                d = media(s, regimen, "evi-cd") - media(s, regimen, otro)
                diffs[regimen][clave][s] = round(d, 4)
                signos.add(1 if d < 0 else (-1 if d > 0 else 0))
            if len(signos - {0}) > 1:
                confiable = False

    gana = {}
    for regimen in REGIMENES:
        gana[regimen] = {
            "vs_siempre": (resumen[regimen]["evi-cd"]
                           < resumen[regimen]["siempre"]),
            "vs_evi": (resumen[regimen]["evi-cd"]
                       < resumen[regimen]["evi"]),
        }

    if not confiable:
        veredicto = "NO CONFIABLE"
    elif all(gana[r][c] for r in REGIMENES for c in ("vs_siempre", "vs_evi")):
        veredicto = "PASS"
    else:
        veredicto = "FAIL"

    reporte = {
        "experimento": "ALMA-EXP34",
        "seeds": SEEDS,
        "episodios_por_seed_regimen": EPISODIOS,
        "tratamientos": TRATS,
        "regimenes": REGIMENES,
        "regret_medio_por_regimen": resumen,
        "regret_medio_pooled": pooled,
        "tasa_probe_por_regimen": tasa_media,
        "diagnostico_detector_flip_ralo": det_diag,
        "diffs_evi_cd_menos_control_por_seed": diffs,
        "gana": gana,
        "criterio": ("PASS si regret_medio(evi-cd) < regret_medio(siempre) Y "
                     "< regret_medio(evi) en AMBOS regímenes"),
        "veredicto": veredicto,
    }
    with open(os.path.join(args.out, "report.json"), "w",
              encoding="utf-8") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    print("regret medio estacionario:", resumen["estacionario"])
    print("regret medio flip_ralo:  ", resumen["flip_ralo"])
    print("pooled:                  ", pooled)
    print("tasa probe:              ", tasa_media)
    print("detector (flip_ralo):    ", det_diag)
    print("gana:", gana)
    print("VEREDICTO:", veredicto)


if __name__ == "__main__":
    main()
