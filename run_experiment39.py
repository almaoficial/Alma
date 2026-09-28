#!/usr/bin/env python3
"""ALMA-EXP39: common random numbers para las tres reglas del probe.

Hallazgo de EXP38: el camino aleatorio de Thompson domina el resultado
(+-7 puntos) frente al efecto-regla (+-1-2), y la serie 36/37/38 mezclo
efecto-regla con efecto-semilla porque cada experimento uso un namespace
de semilla distinto ("exp36-", "exp37-", "exp38-").

EXP39 arregla la medicion ANTES de tocar otra regla: re-corre las tres
reglas (EXP36 original, EXP37 con penal, EXP38 con desempate calibrado)
bajo *common random numbers*: dentro de cada replica, las tres reglas
usan la MISMA semilla de Thompson por posicion (replica, bloque, hora).
Replicas distintas usan semillas distintas.

Detalle de validez: el unico azar del sistema es la seleccion de Thompson
(random.Random por (NS,b,h) + bandit.select); el probe/spy es
determinista. Con el mismo NS, el sorteo en cada posicion (b,h) es
identico entre reglas, asi que la diferencia entre reglas dentro de una
replica es efecto-regla puro (mas la divergencia de estado del bandit que
cada regla induce, que es parte de la regla).

Criterio PRE-REGISTRADO (ver resultados/exp39-20260927/preregistro.json):
    efecto_regla(r) = P&L_regla(r) - P&L_buyhold   (por replica)
    efecto_neto(regla) = media sobre replicas; dispersion = desvio muestral
    PASS iff alguna regla tiene media > 0 y (media - 1*desvio) > -0.01.
Sin mover la vara.

Replay puro sobre datos Kraken publicos (identicos a EXP36/37/38):
US$0, 0 llamadas. Mock total.

Uso: python3 run_experiment39.py
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alma.selector import BanditPorClase  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "resultados", "exp39-20260927")
ARMS = ["momentum", "meanrev", "buyhold", "flat"]
N_BLOQUES, H_BLOQUE = 30, 24
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (12, 13)
MARGEN = 0.02          # regla EXP36
UMBRAL_SENAL = 0.02    # regla EXP37
CAMBIO_PENAL = 0.01    # regla EXP37
K_SENAL = 1.0          # regla EXP38
N0 = 2
DECAY = 0.5
COSTO_BP = 0.0001
CAP = 0.02
N_REPLICAS = 6         # PRE-REGISTRADO


def sign(x):
    return 1.0 if x >= 0 else -1.0


def cargar_serie():
    d = json.load(open(os.path.join(BASE, "data_exp36", "btc_h1.json")))
    c = d["close"][:720]
    assert len(c) == 720
    return [c[i + 1] / c[i] - 1 for i in range(len(c) - 1)]  # 719 retornos


def posiciones(rets):
    pos = {}
    pos["momentum"] = [sign(rets[h - 1]) if h > 0 else 1.0
                       for h in range(len(rets))]
    pos["meanrev"] = [-p for p in pos["momentum"]]
    pos["buyhold"] = [1.0] * len(rets)
    pos["flat"] = [0.0] * len(rets)
    return pos


def pnl_hora(pos, rets):
    out = {}
    for a in ARMS:
        ps = pos[a]
        serie, prev = [], 0.0
        for h in range(len(rets)):
            serie.append(ps[h] * rets[h] - COSTO_BP * abs(ps[h] - prev))
            prev = ps[h]
        out[a] = serie
    return out


def a_reward(pnl):
    return 0.5 + max(-CAP, min(CAP, pnl)) / (2 * CAP)


def bandit_warm_olvido(rep_w):
    b = BanditPorClase(ARMS)
    for a in ARMS:
        obs = rep_w.get(a, [])
        if obs:
            sw = sum(w for _, w in obs)
            m = sum(r * w for r, w in obs) / sw if sw else 0.5
        else:
            m = 0.5
        b.alpha[a] = 1.0 + N0 * m
        b.beta[a] = 1.0 + N0 * (1.0 - m)
        b.pulls[a] = N0
    return b


def se_media(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return (v ** 0.5) / (n ** 0.5)


# ---------------- reglas de eleccion del probe ----------------

def regla_eleccion36(medias_probe, medias_prior):
    """EXP36: si brecha < MARGEN, desempata al favorito del prior."""
    orden = sorted(ARMS, key=lambda a: medias_probe[a], reverse=True)
    mejor, segundo = orden[0], orden[1]
    if medias_probe[mejor] - medias_probe[segundo] < MARGEN:
        return max(ARMS, key=lambda a: medias_prior[a])
    return mejor


def regla_eleccion37(medias_probe, brazo_anterior):
    """EXP37: penal por cambio + desempate a flat si brecha < UMBRAL."""
    adj = {a: medias_probe[a] - (CAMBIO_PENAL if brazo_anterior is not None
                                 and a != brazo_anterior else 0.0)
           for a in ARMS}
    orden = sorted(ARMS, key=lambda a: adj[a], reverse=True)
    mejor, segundo = orden[0], orden[1]
    if adj[mejor] - adj[segundo] >= UMBRAL_SENAL:
        return mejor
    return "flat"


def regla_eleccion38(obs_probe):
    """EXP38: desempate a flat si brecha no clara; umbral = k x se_gap."""
    por_a = {}
    for (q, a), r in obs_probe.items():
        por_a.setdefault(a, []).append(r)
    medias = {a: sum(v) / len(v) for a, v in por_a.items()}
    orden = sorted(ARMS, key=lambda a: medias[a], reverse=True)
    mejor, segundo = orden[0], orden[1]
    gap = medias[mejor] - medias[segundo]
    se_gap = (se_media(por_a[mejor]) ** 2
              + se_media(por_a[segundo]) ** 2) ** 0.5
    if gap > K_SENAL * se_gap:
        return mejor
    return "flat"


# ---------------- corridas (NS = namespace de semilla, comun) ----------------

def _base_bloque(b, rep):
    rep_w = {a: [(r, DECAY ** ((b * H_BLOQUE - 1 - hh) // H_BLOQUE))
                 for hh, r in rep[a]] for a in ARMS}
    return bandit_warm_olvido(rep_w)


def correr_regla36(NS, rets, pos, pnl):
    H = len(rets)
    rep = {a: [] for a in ARMS}
    pnl_h = [0.0] * H
    for b in range(N_BLOQUES):
        base = b * H_BLOQUE
        bandit = _base_bloque(b, rep)
        prior_means = {a: bandit.mean(a) for a in ARMS}

        def spy(qs):
            prs = {}
            for q in qs:
                h = base + q
                if h >= H:
                    continue
                for a in ARMS:
                    r = a_reward(pnl[a][h])
                    prs[(q, a)] = r
                    bandit.update(a, r)
                    rep[a].append((h, r))
            return prs

        def thompson(qs):
            for q in qs:
                h = base + q
                if h >= H:
                    continue
                rng = random.Random(f"{NS}-{b}-{h}")
                a = bandit.select(rng)
                r = a_reward(pnl[a][h])
                bandit.update(a, r)
                rep[a].append((h, r))
                pnl_h[h] = pnl[a][h]

        def fijar(qs, brazo):
            for q in qs:
                h = base + q
                if h < H:
                    pnl_h[h] = pnl[brazo][h]

        prs1 = spy(PROBE_Q1)
        m1 = {a: sum(prs1[(q, a)] for q in PROBE_Q1) / len(PROBE_Q1)
              for a in ARMS}
        fijar(PROBE_Q1, regla_eleccion36(m1, prior_means))
        thompson(range(3, 12))

        prs2 = spy(PROBE_Q2)
        todo = dict(prs1)
        todo.update(prs2)
        qs_all = PROBE_Q1 + PROBE_Q2
        m2 = {a: sum(todo[(q, a)] for q in qs_all) / len(qs_all)
              for a in ARMS}
        fijar(PROBE_Q2, regla_eleccion36(m2, prior_means))
        thompson(range(14, H_BLOQUE))
    return sum(pnl_h)


def correr_regla37(NS, rets, pos, pnl):
    H = len(rets)
    rep = {a: [] for a in ARMS}
    pnl_h = [0.0] * H
    brazo_anterior = None
    for b in range(N_BLOQUES):
        base = b * H_BLOQUE
        bandit = _base_bloque(b, rep)

        def spy(qs):
            prs = {}
            for q in qs:
                h = base + q
                if h >= H:
                    continue
                for a in ARMS:
                    r = a_reward(pnl[a][h])
                    prs[(q, a)] = r
                    bandit.update(a, r)
                    rep[a].append((h, r))
            return prs

        def thompson(qs):
            for q in qs:
                h = base + q
                if h >= H:
                    continue
                rng = random.Random(f"{NS}-{b}-{h}")
                a = bandit.select(rng)
                r = a_reward(pnl[a][h])
                bandit.update(a, r)
                rep[a].append((h, r))
                pnl_h[h] = pnl[a][h]

        def fijar(qs, brazo):
            for q in qs:
                h = base + q
                if h < H:
                    pnl_h[h] = pnl[brazo][h]

        prs1 = spy(PROBE_Q1)
        m1 = {a: sum(prs1[(q, a)] for q in PROBE_Q1) / len(PROBE_Q1)
              for a in ARMS}
        elegido1 = regla_eleccion37(m1, brazo_anterior)
        fijar(PROBE_Q1, elegido1)
        if elegido1 == "flat":
            fijar(range(3, 12), "flat")
        else:
            thompson(range(3, 12))

        prs2 = spy(PROBE_Q2)
        todo = dict(prs1)
        todo.update(prs2)
        qs_all = PROBE_Q1 + PROBE_Q2
        m2 = {a: sum(todo[(q, a)] for q in qs_all) / len(qs_all)
              for a in ARMS}
        elegido2 = regla_eleccion37(m2, brazo_anterior)
        fijar(PROBE_Q2, elegido2)
        if elegido2 == "flat":
            fijar(range(14, H_BLOQUE), "flat")
        else:
            thompson(range(14, H_BLOQUE))
        brazo_anterior = elegido2
    return sum(pnl_h)


def correr_regla38(NS, rets, pos, pnl):
    H = len(rets)
    rep = {a: [] for a in ARMS}
    pnl_h = [0.0] * H
    for b in range(N_BLOQUES):
        base = b * H_BLOQUE
        bandit = _base_bloque(b, rep)

        def spy(qs):
            prs = {}
            for q in qs:
                h = base + q
                if h >= H:
                    continue
                for a in ARMS:
                    r = a_reward(pnl[a][h])
                    prs[(q, a)] = r
                    bandit.update(a, r)
                    rep[a].append((h, r))
            return prs

        def thompson(qs):
            for q in qs:
                h = base + q
                if h >= H:
                    continue
                rng = random.Random(f"{NS}-{b}-{h}")
                a = bandit.select(rng)
                r = a_reward(pnl[a][h])
                bandit.update(a, r)
                rep[a].append((h, r))
                pnl_h[h] = pnl[a][h]

        def fijar(qs, brazo):
            for q in qs:
                h = base + q
                if h < H:
                    pnl_h[h] = pnl[brazo][h]

        prs1 = spy(PROBE_Q1)
        fijar(PROBE_Q1, regla_eleccion38(prs1))
        thompson(range(3, 12))

        prs2 = spy(PROBE_Q2)
        todo = dict(prs1)
        todo.update(prs2)
        fijar(PROBE_Q2, regla_eleccion38(todo))
        thompson(range(14, H_BLOQUE))
    return sum(pnl_h)


REGLAS = {
    "regla36": ("EXP36 original (desempate a favorito del prior)", correr_regla36),
    "regla37": ("EXP37 (penal por cambio + desempate a flat)", correr_regla37),
    "regla38": ("EXP38 (desempate a flat, umbral calibrado k=1)", correr_regla38),
}


def media(xs):
    return sum(xs) / len(xs)


def desvio(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = media(xs)
    return (sum((x - m) ** 2 for x in xs) / (n - 1)) ** 0.5


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)

    # --- pre-registro ANTES de correr ---
    prereg = {
        "experimento": "ALMA-EXP39: common random numbers para las tres reglas",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "motivacion": "EXP38: el camino aleatorio de Thompson (+-7pts) domina "
                      "al efecto-regla (+-1-2); la serie 36/37/38 mezclo ambos "
                      "por namespaces de semilla distintos.",
        "diseno": {
            "reglas": {k: v[0] for k, v in REGLAS.items()},
            "common_random_numbers": "dentro de cada replica, las tres reglas "
                "usan el mismo namespace de semilla de Thompson "
                "'exp39-r{replica}-{b}-{h}'; el probe/spy es determinista, asi "
                "que la diferencia intra-replica es efecto-regla puro",
            "replicas": N_REPLICAS,
            "stream": "identico a EXP36/37/38: Kraken XBTUSD 1h, 720 velas, "
                      "719 retornos",
        },
        "criterio": {
            "efecto": "P&L_regla(replica) - P&L_buyhold",
            "pass": "alguna regla con media(efecto) > 0 y "
                    "media(efecto) - 1*desvio(efecto) > -0.01",
        },
        "modo": "mock, replay puro, US$0",
    }
    with open(os.path.join(OUT, "preregistro.json"), "w") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito ({N_REPLICAS} replicas x 3 reglas, CRN).")

    rets = cargar_serie()
    pos = posiciones(rets)
    pnl = pnl_hora(pos, rets)
    pnl_buyhold = sum(pnl["buyhold"])

    tabla = {}  # regla -> [pnl por replica]
    for nombre, (desc, fn) in REGLAS.items():
        tabla[nombre] = []
        for r in range(N_REPLICAS):
            NS = f"exp39-r{r}"
            t = fn(NS, rets, pos, pnl)
            tabla[nombre].append(t)
            print(f"  {nombre} replica r{r}: P&L={t:+.4%}", flush=True)

    efectos = {n: [t - pnl_buyhold for t in ts] for n, ts in tabla.items()}
    resumen = {}
    for n, ef in efectos.items():
        m, s = media(ef), desvio(ef)
        resumen[n] = {"media": m, "desvio": s, "media_menos_1sd": m - s}

    ganadoras = [n for n, rs in resumen.items()
                 if rs["media"] > 0 and rs["media_menos_1sd"] > -0.01]
    pasa = bool(ganadoras)

    motivos = [
        f"buyhold (referencia fija): {pnl_buyhold:+.4%}",
    ]
    for n in REGLAS:
        rs = resumen[n]
        ef = efectos[n]
        motivos.append(
            f"{n}: efecto neto media={rs['media']:+.4%}, "
            f"desvio={rs['desvio']:+.4%}, media-1sd={rs['media_menos_1sd']:+.4%} "
            f"| por replica: " + ", ".join(f"{e:+.3%}" for e in ef))
    motivos.append(
        "PASS" if pasa
        else "ninguna regla cumple media>0 y media-1sd>-1% (vara intacta)")

    report = {
        "preregistro": "resultados/exp39-20260927/preregistro.json",
        "replicas": N_REPLICAS,
        "pnl_buyhold": round(pnl_buyhold, 6),
        "tabla_regla_x_replica": {
            n: [round(t, 6) for t in ts] for n, ts in tabla.items()},
        "efecto_neto": {n: {k: round(v, 6) for k, v in rs.items()}
                        for n, rs in resumen.items()},
        "costo_total_usd": 0.0,
        "veredicto": {"pasa": pasa, "reglas_que_pasan": ganadoras,
                       "criterio": prereg["criterio"], "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP39 ================")
    for m in motivos:
        print("  " + m)
    print(f"  costo: $0.0000 USD (replay puro) | {report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
