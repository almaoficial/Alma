#!/usr/bin/env python3
"""ALMA-EXP36: stream REAL no estacionario — BTC horario, 30 días.

Pregunta: ¿la maquinaria de ALMA (probe continuo + re-probe + olvido, EXP7/9)
elige estrategia por bloque mejor que la mejor estrategia fija, en un stream
real de mercado (mitad 1 lateral -0.89%, mitad 2 en tendencia +9.35%)?

Brazos (papel, sin dinero real): momentum, reversión a la media, buy&hold,
no-operar. Replay puro sobre datos Kraken públicos: US$0, 0 llamadas.

Criterio PRE-REGISTRADO (ver resultados/exp36-20260927/preregistro.json):
    PASS iff P&L_neto_total(ALMA) > P&L_neto_total(mejor brazo fijo).
Sin mover la vara: si no se cumple, FAIL.

Uso: python3 run_experiment36.py
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alma.selector import BanditPorClase  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "resultados", "exp36-20260927")
ARMS = ["momentum", "meanrev", "buyhold", "flat"]
N_BLOQUES, H_BLOQUE = 30, 24
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (12, 13)
MARGEN = 0.02
N0 = 2
DECAY = 0.5
COSTO_BP = 0.0001
CAP = 0.02


def sign(x):
    return 1.0 if x >= 0 else -1.0


def cargar_serie():
    d = json.load(open(os.path.join(BASE, "data_exp36", "btc_h1.json")))
    c = d["close"][:720]
    assert len(c) == 720
    return [c[i + 1] / c[i] - 1 for i in range(len(c) - 1)]  # 719 retornos


def posiciones(rets):
    """{brazo: [pos_h]} para h=0..718. pos_{-1}=0 para el costo inicial."""
    pos = {}
    pos["momentum"] = [sign(rets[h - 1]) if h > 0 else 1.0
                       for h in range(len(rets))]
    pos["meanrev"] = [-p for p in pos["momentum"]]
    pos["buyhold"] = [1.0] * len(rets)
    pos["flat"] = [0.0] * len(rets)
    return pos


def pnl_hora(pos, rets):
    """{brazo: [pnl_h]} neto de costos."""
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


def regla_eleccion(medias_probe, medias_prior):
    orden = sorted(ARMS, key=lambda a: medias_probe[a], reverse=True)
    mejor, segundo = orden[0], orden[1]
    if medias_probe[mejor] - medias_probe[segundo] < MARGEN:
        fav = max(ARMS, key=lambda a: medias_prior[a])
        return fav
    return mejor


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    rets = cargar_serie()          # 719 retornos horarios
    pos = posiciones(rets)
    pnl = pnl_hora(pos, rets)
    H = len(rets)

    # --- control: brazos fijos ---
    pnl_fija = {a: sum(pnl[a]) for a in ARMS}
    mejor_fija = max(ARMS, key=lambda a: pnl_fija[a])

    # --- ALMA: probe continuo + re-probe + olvido, por bloque ---
    rep = {a: [] for a in ARMS}    # {(reward, peso)} del pasado
    pnl_alma_h = [0.0] * H
    diag = []
    n_switch = 0
    for b in range(N_BLOQUES):
        base = b * H_BLOQUE
        hs = [base + q for q in range(H_BLOQUE) if base + q < H]
        # warm con olvido: peso 0.5^d
        rep_w = {a: [(r, DECAY ** ((b * H_BLOQUE - 1 - hh) // H_BLOQUE))
                    for hh, r in rep[a]] for a in ARMS}
        bandit = bandit_warm_olvido(rep_w)
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

        prs1 = spy(PROBE_Q1)
        m1 = {a: sum(prs1[(q, a)] for q in PROBE_Q1) / len(PROBE_Q1)
              for a in ARMS}
        elegido1 = regla_eleccion(m1, prior_means)
        for q in PROBE_Q1:
            h = base + q
            if h < H:
                pnl_alma_h[h] = pnl[elegido1][h]

        for q in range(3, 12):
            h = base + q
            if h >= H:
                continue
            rng = random.Random(f"exp36-{b}-{h}")
            a = bandit.select(rng)
            r = a_reward(pnl[a][h])
            bandit.update(a, r)
            rep[a].append((h, r))
            pnl_alma_h[h] = pnl[a][h]

        prs2 = spy(PROBE_Q2)
        todo = dict(prs1)
        todo.update(prs2)
        qs_all = PROBE_Q1 + PROBE_Q2
        m2 = {a: sum(todo[(q, a)] for q in qs_all) / len(qs_all)
              for a in ARMS}
        elegido2 = regla_eleccion(m2, prior_means)
        if elegido1 != elegido2:
            n_switch += 1
        for q in PROBE_Q2:
            h = base + q
            if h < H:
                pnl_alma_h[h] = pnl[elegido2][h]

        for q in range(14, H_BLOQUE):
            h = base + q
            if h >= H:
                continue
            rng = random.Random(f"exp36-{b}-{h}")
            a = bandit.select(rng)
            r = a_reward(pnl[a][h])
            bandit.update(a, r)
            rep[a].append((h, r))
            pnl_alma_h[h] = pnl[a][h]

        diag.append({"bloque": b, "prior_means": prior_means,
                     "inicial": elegido1, "final": elegido2,
                     "cambio": elegido1 != elegido2,
                     "pnl_bloque_alma": round(sum(pnl_alma_h[base:base + 24]), 6),
                     "pnl_bloque_fijas": {a: round(sum(pnl[a][base:base + 24]), 6)
                                           for a in ARMS}})

    pnl_alma_total = sum(pnl_alma_h)
    mitad = H // 2
    pnl_alma_h1 = sum(pnl_alma_h[:mitad])
    pnl_alma_h2 = sum(pnl_alma_h[mitad:])
    pnl_fija_h1 = {a: sum(pnl[a][:mitad]) for a in ARMS}
    pnl_fija_h2 = {a: sum(pnl[a][mitad:]) for a in ARMS}

    pasa = bool(pnl_alma_total > pnl_fija[mejor_fija])
    motivos = [
        f"P&L total: ALMA={pnl_alma_total:+.4%} vs mejor fija "
        f"({mejor_fija})={pnl_fija[mejor_fija]:+.4%} "
        f"(diff={pnl_alma_total - pnl_fija[mejor_fija]:+.4%})",
        "P&L fijas: " + ", ".join(f"{a}={pnl_fija[a]:+.3%}" for a in ARMS),
        f"1ra mitad: ALMA={pnl_alma_h1:+.3%} | fijas: " +
        ", ".join(f"{a}={pnl_fija_h1[a]:+.3%}" for a in ARMS),
        f"2da mitad: ALMA={pnl_alma_h2:+.3%} | fijas: " +
        ", ".join(f"{a}={pnl_fija_h2[a]:+.3%}" for a in ARMS),
        f"cambios tras re-probe: {n_switch}/{N_BLOQUES} bloques",
    ]
    report = {
        "preregistro": "resultados/exp36-20260927/preregistro.json",
        "pnl_total": {"alma": round(pnl_alma_total, 6),
                      "fijas": {a: round(v, 6) for a, v in pnl_fija.items()},
                      "mejor_fija": mejor_fija},
        "pnl_mitades": {"alma_h1": round(pnl_alma_h1, 6),
                        "alma_h2": round(pnl_alma_h2, 6),
                        "fijas_h1": {a: round(v, 6) for a, v in pnl_fija_h1.items()},
                        "fijas_h2": {a: round(v, 6) for a, v in pnl_fija_h2.items()}},
        "diagnostico_bloques": diag,
        "costo_total_usd": 0.0,
        "veredicto": {"pasa": pasa,
                       "criterio": "pnl_total(alma) > pnl_total(mejor_fija)",
                       "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP36 ================")
    for m in motivos:
        print("  " + m)
    print(f"  costo: $0.0000 USD (replay puro) | {report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL",
          "— ALMA supera a la mejor fija" if pasa
          else "— ALMA no supera a la mejor fija (vara intacta)")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
