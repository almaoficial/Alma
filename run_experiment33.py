#!/usr/bin/env python3
"""ALMA-EXP33: ¿EVI + detección de cambios supera al probe siempre-activo?

Motivación: EXP32 FAIL — el probe-EVI puro tritura en estacionario pero
pierde en flip porque tras un flip la creencia queda confidentemente
equivocada y el EVI salta el probe justo cuando más vale.
Idea: EVI + detección de cambios — forzar el probe cuando las recompensas
recientes del brazo comprometido se desvían de lo que predice su posterior.

Diseño: ver resultados/exp33-20260927/preregistro.json (escrito ANTES de correr).
100% mock: US$0. Replicación exacta de EXP32 (mismas seeds, mismos streams RNG
para siempre/evi — verificada automáticamente) + tratamiento nuevo evi-cd.
Uso: python3 run_experiment33.py [--out DIR]
"""
import argparse
import hashlib
import json
import math
import os
import random

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp33-20260927")
REP32 = os.path.join(DIR_BASE, "resultados", "exp32-20260927", "report.json")

SEEDS = [3221, 3222, 3223, 3224, 3225, 3226, 3227, 3228]
TRATS = ["siempre", "evi", "evi-cd"]
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


def pull_real(brazo, p, rng):
    return 1 if rng.random() < p[brazo] else 0


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


def bloque(p, probo, alfa, beta, rng):
    """Ejecuta un bloque con la decisión ya tomada.
    Devuelve (regret, alfa, beta, brazo_comprometido, n_comp, k_comp).
    El orden de consumo del rng es idéntico al de EXP32."""
    p_best = max(p)
    regret = 0.0
    if probo:
        exitos = []
        for a in range(3):
            k = 0
            for _ in range(PROBE_POR_BRAZO):
                r = pull_real(a, p, rng)
                k += r
                alfa[a] += r
                beta[a] += 1 - r
                regret += p_best - p[a]
            exitos.append(k)
        ganador = max(range(3), key=lambda i: (exitos[i], -i))
        kc = exitos[ganador]
        for _ in range(PULLS_BLOQUE - PROBE_TOTAL):
            r = pull_real(ganador, p, rng)
            kc += r
            alfa[ganador] += r
            beta[ganador] += 1 - r
            regret += p_best - p[ganador]
        n_comp = PROBE_POR_BRAZO + (PULLS_BLOQUE - PROBE_TOTAL)
        return regret, alfa, beta, ganador, n_comp, kc
    b0 = mejor_posterior(alfa, beta)
    kc = 0
    for _ in range(PULLS_BLOQUE):
        r = pull_real(b0, p, rng)
        kc += r
        alfa[b0] += r
        beta[b0] += 1 - r
        regret += p_best - p[b0]
    return regret, alfa, beta, b0, PULLS_BLOQUE, kc


def episodio(s, e, regimen, tratamiento, orden):
    """Un episodio de 10 bloques. Devuelve (regret, tasa_probe, tasa_det)."""
    alfa = [1.0, 1.0, 1.0]
    beta = [1.0, 1.0, 1.0]
    regret = 0.0
    probes = 0
    dets = 0
    prev = None  # (snap_alfa, snap_beta, brazo, n, k) del bloque anterior
    for b in range(BLOQUES):
        if regimen == "estacionario":
            mejor = orden[0]
        else:  # flip: alterna entre los dos primeros sorteados
            mejor = orden[b % 2]
        p = [P_RESTO, P_RESTO, P_RESTO]
        p[mejor] = P_MEJOR
        if b > 0:
            alfa, beta = aplicar_olvido(alfa, beta)
        snap_a, snap_b = list(alfa), list(beta)
        if tratamiento == "siempre":
            tag = _rng("exp32", s, e, regimen, "siempre", "bloque", b)
            probo = True
        elif tratamiento == "evi":
            tag = _rng("exp32", s, e, regimen, "evi", "bloque", b)
            probo = evi(tag, alfa, beta) > 0
        else:  # evi-cd
            tag = _rng("exp33", s, e, regimen, "evi-cd", "bloque", b)
            det = prev is not None and detectar(prev)
            dets += 1 if det else 0
            probo = evi(tag, alfa, beta) > 0 or det
        r, alfa, beta, bc, nbc, kbc = bloque(p, probo, alfa, beta, tag)
        regret += r
        probes += 1 if probo else 0
        prev = (snap_a, snap_b, bc, nbc, kbc)
    return regret, probes / BLOQUES, dets / BLOQUES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=RES_DIR)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "preregistro.json")) as f:
        json.load(f)  # debe existir ANTES de correr
    with open(REP32) as f:
        rep32 = json.load(f)

    res, tasa, tasa_det = {}, {}, {}
    for s in SEEDS:
        res[s] = {}
        tasa[s] = {}
        tasa_det[s] = {}
        for regimen in ("estacionario", "flip"):
            res[s][regimen] = {t: [] for t in TRATS}
            tp = {t: [] for t in TRATS}
            td = []
            for e in range(EPISODIOS):
                orden_rng = _rng("exp32", s, regimen, "sorteo", e)
                orden = list(range(3))
                orden_rng.shuffle(orden)
                for tratamiento in TRATS:
                    r, tpr, tdt = episodio(s, e, regimen, tratamiento, orden)
                    res[s][regimen][tratamiento].append(r)
                    tp[tratamiento].append(tpr)
                    if tratamiento == "evi-cd":
                        td.append(tdt)
            for t in TRATS:
                tasa.setdefault((s, regimen), {})[t] = sum(tp[t]) / len(tp[t])
            tasa_det[(s, regimen)] = sum(td) / len(td)

    def media(s, regimen, tratamiento):
        v = res[s][regimen][tratamiento]
        return sum(v) / len(v)

    resumen = {}
    for regimen in ("estacionario", "flip"):
        resumen[regimen] = {}
        for t in TRATS:
            resumen[regimen][t] = round(
                sum(media(s, regimen, t) for s in SEEDS) / len(SEEDS), 4)
    pooled = {t: round(sum(resumen[r][t]
                           for r in ("estacionario", "flip")) / 2, 4)
              for t in TRATS}
    tasa_media = {r: {t: round(sum(tasa[(s, r)][t] for s in SEEDS)
                               / len(SEEDS), 4)
                      for t in TRATS}
                  for r in ("estacionario", "flip")}
    det_media = {r: round(sum(tasa_det[(s, r)] for s in SEEDS)
                          / len(SEEDS), 4)
                 for r in ("estacionario", "flip")}

    # verificación de replicación exacta de EXP32
    for regimen in ("estacionario", "flip"):
        for t in ("siempre", "evi"):
            v32 = rep32["regret_medio_por_regimen"][regimen][t]
            v33 = resumen[regimen][t]
            assert v32 == v33, (
                f"replicación rota: {regimen}/{t}: EXP32={v32} vs EXP33={v33}")

    # diffs por seed y confiabilidad (ambas comparaciones, ambos regímenes)
    diffs = {}
    confiable = True
    for regimen in ("estacionario", "flip"):
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
    for regimen in ("estacionario", "flip"):
        gana[regimen] = {
            "vs_siempre": (resumen[regimen]["evi-cd"]
                           < resumen[regimen]["siempre"]),
            "vs_evi": (resumen[regimen]["evi-cd"]
                       < resumen[regimen]["evi"]),
        }

    if not confiable:
        veredicto = "NO CONFIABLE"
    elif all(gana[r][c] for r in ("estacionario", "flip")
             for c in ("vs_siempre", "vs_evi")):
        veredicto = "PASS"
    else:
        veredicto = "FAIL"

    reporte = {
        "experimento": "ALMA-EXP33",
        "seeds": SEEDS,
        "episodios_por_seed_regimen": EPISODIOS,
        "tratamientos": TRATS,
        "regret_medio_por_regimen": resumen,
        "regret_medio_pooled": pooled,
        "tasa_probe_por_regimen": tasa_media,
        "tasa_deteccion_evi_cd_por_regimen": det_media,
        "diffs_evi_cd_menos_control_por_seed": diffs,
        "gana": gana,
        "criterio": ("PASS si regret_medio(evi-cd) < regret_medio(siempre) Y "
                     "< regret_medio(evi) en AMBOS regímenes"),
        "replicacion_exp32_verificada": True,
        "veredicto": veredicto,
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    print("replicación EXP32 verificada: OK")
    print("regret medio estacionario:", resumen["estacionario"])
    print("regret medio flip:       ", resumen["flip"])
    print("pooled:                  ", pooled)
    print("tasa probe:              ", tasa_media)
    print("tasa detección (evi-cd): ", det_media)
    print("gana:", gana)
    print("VEREDICTO:", veredicto)


if __name__ == "__main__":
    main()
