#!/usr/bin/env python3
"""ALMA-EXP32: ¿un probe con costo explícito (EVI) supera al probe siempre-activo?

Motivación: EXP18 seed 1821 (API real): ALMA acertó 9/10 decisiones finales
pero perdió (regret 6.795 vs 4.43 de la mejor fija) porque el costo de
probar+explorar superó el beneficio. El probe actual siempre prueba.
Idea: el probe calcula el Valor Esperado de la Información y solo prueba
si EVI > 0 (el costo del probe va dentro del cálculo); si no, va directo
a la mejor estrategia actual.

Diseño: ver resultados/exp32-20260927/preregistro.json (escrito ANTES de correr).
100% mock: US$0. No toca DB, servicio ni API real bajo ningún concepto.
Uso: python3 run_experiment32.py [--out DIR]
"""
import argparse
import hashlib
import json
import os
import random

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(DIR_BASE, "resultados", "exp32-20260927")

SEEDS = [3221, 3222, 3223, 3224, 3225, 3226, 3227, 3228]
BRAZOS = ["single", "cot", "reflexion"]
BLOQUES = 10
PULLS_BLOQUE = 80
PROBE_POR_BRAZO = 8
PROBE_TOTAL = PROBE_POR_BRAZO * len(BRAZOS)  # 24
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
    """Un probe simulado (8 Bernoulli/brazo) con medias verdaderas mu.
    Devuelve el ganador (desempate por orden fijo)."""
    exitos = []
    for a in range(3):
        k = sum(1 for _ in range(PROBE_POR_BRAZO) if rng.random() < mu[a])
        exitos.append(k)
    return max(range(3), key=lambda i: (exitos[i], -i))


def evi(rng, alfa, beta, horizonte=PULLS_BLOQUE):
    """Valor Esperado de la Información de probar, bajo la creencia actual.
    EVI = E[U(probar→ganador) − U(comprometer ya al mejor posterior)]."""
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


def bloque(p, tratamiento, alfa, beta, rng, tag_evi):
    """Un bloque de 80 pulls. Devuelve (regret, alfa, beta, probo)."""
    p_best = max(p)
    regret = 0.0
    probo = False
    if tratamiento == "siempre" or (
            tratamiento == "evi" and evi(rng, alfa, beta) > 0):
        probo = True
        # probe: 8 pulls por brazo
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
        for _ in range(PULLS_BLOQUE - PROBE_TOTAL):
            r = pull_real(ganador, p, rng)
            alfa[ganador] += r
            beta[ganador] += 1 - r
            regret += p_best - p[ganador]
    else:
        b0 = mejor_posterior(alfa, beta)
        for _ in range(PULLS_BLOQUE):
            r = pull_real(b0, p, rng)
            alfa[b0] += r
            beta[b0] += 1 - r
            regret += p_best - p[b0]
    return regret, alfa, beta, probo


def episodio(rng, s, e, regimen, tratamiento, orden):
    """Un episodio de 10 bloques. Devuelve (regret_total, tasa_probe)."""
    alfa = [1.0, 1.0, 1.0]
    beta = [1.0, 1.0, 1.0]
    regret = 0.0
    probes = 0
    for b in range(BLOQUES):
        if regimen == "estacionario":
            mejor = orden[0]
        else:  # flip: alterna entre los dos primeros sorteados
            mejor = orden[b % 2]
        p = [P_RESTO, P_RESTO, P_RESTO]
        p[mejor] = P_MEJOR
        if b > 0:
            alfa, beta = aplicar_olvido(alfa, beta)
        tag = _rng("exp32", s, e, regimen, tratamiento, "bloque", b)
        r, alfa, beta, probo = bloque(p, tratamiento, alfa, beta, tag, None)
        regret += r
        probes += 1 if probo else 0
    return regret, probes / BLOQUES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=RES_DIR)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "preregistro.json")) as f:
        json.load(f)  # debe existir ANTES de correr

    # res[seed][regimen][tratamiento] = lista de regrets por episodio
    # tasa[seed][regimen] = tasa media de probe del tratamiento EVI
    res = {}
    tasa = {}
    for s in SEEDS:
        res[s] = {}
        tasa[s] = {}
        for regimen in ("estacionario", "flip"):
            res[s][regimen] = {}
            tasas_evi = []
            for e in range(EPISODIOS):
                # sorteo de brazos pareado entre tratamientos
                orden_rng = _rng("exp32", s, regimen, "sorteo", e)
                orden = list(range(3))
                orden_rng.shuffle(orden)
                for tratamiento in ("siempre", "evi"):
                    rng = _rng("exp32", s, regimen, tratamiento, e)
                    r, tp = episodio(rng, s, e, regimen, tratamiento, orden)
                    res[s][regimen].setdefault(tratamiento, []).append(r)
                    if tratamiento == "evi":
                        tasas_evi.append(tp)
            tasa[s][regimen] = sum(tasas_evi) / len(tasas_evi)

    def media(s, regimen, tratamiento):
        v = res[s][regimen][tratamiento]
        return sum(v) / len(v)

    # medias por régimen (a través de seeds)
    resumen = {}
    for regimen in ("estacionario", "flip"):
        resumen[regimen] = {}
        for tratamiento in ("siempre", "evi"):
            resumen[regimen][tratamiento] = round(
                sum(media(s, regimen, tratamiento) for s in SEEDS)
                / len(SEEDS), 4)
    pooled = {}
    for tratamiento in ("siempre", "evi"):
        pooled[tratamiento] = round(
            sum(resumen[r][tratamiento] for r in ("estacionario", "flip"))
            / 2, 4)

    tasa_media = {r: round(sum(tasa[s][r] for s in SEEDS) / len(SEEDS), 4)
                  for r in ("estacionario", "flip")}

    # confiabilidad: cambio de signo en diffs por seed, por régimen
    diffs = {}
    confiable = True
    for regimen in ("estacionario", "flip"):
        diffs[regimen] = {}
        signos = set()
        for s in SEEDS:
            d = media(s, regimen, "evi") - media(s, regimen, "siempre")
            diffs[regimen][s] = round(d, 4)
            signos.add(1 if d < 0 else (-1 if d > 0 else 0))
        if len(signos - {0}) > 1:
            confiable = False

    gana_est = resumen["estacionario"]["evi"] < resumen["estacionario"]["siempre"]
    gana_flip = resumen["flip"]["evi"] < resumen["flip"]["siempre"]

    if not confiable:
        veredicto = "NO CONFIABLE"
    elif gana_est and gana_flip:
        veredicto = "PASS"
    else:
        veredicto = "FAIL"

    reporte = {
        "experimento": "ALMA-EXP32",
        "seeds": SEEDS,
        "episodios_por_seed_regimen": EPISODIOS,
        "regret_medio_por_regimen": resumen,
        "regret_medio_pooled": pooled,
        "tasa_probe_EVI_por_regimen": tasa_media,
        "diffs_evi_menos_siempre_por_seed": diffs,
        "gana_estacionario": gana_est,
        "gana_flip": gana_flip,
        "criterio": "PASS si EVI < siempre-activo en AMBOS regímenes",
        "veredicto": veredicto,
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    print("regret medio estacionario:", resumen["estacionario"])
    print("regret medio flip:       ", resumen["flip"])
    print("pooled:                  ", pooled)
    print("tasa probe EVI:          ", tasa_media)
    print("gana estacionario:", gana_est, "| gana flip:", gana_flip)
    print("VEREDICTO:", veredicto)


if __name__ == "__main__":
    main()
