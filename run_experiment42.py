#!/usr/bin/env python3
"""ALMA-EXP42: generalizacion a traves de ventanas.

La serie 36-41 corrio TODA sobre una sola ventana de 30 dias de BTC
(drift +8,55%). Cada veredicto cargo la honestidad incomoda "n=1".
EXP41 cerro la pregunta Hurst (sin senal explotable). El paso honesto
no es otra regla: es salir de la ventana unica.

Diseno:
- K=6 ventanas de 30 dias PRE-REGISTRADAS (3 BTC + 2 ETH + 1 SOL,
  APIs publicas Kraken, sin key), 720 velas horarias c/u + 168h lookback.
- Politicas fijas, sin tuning por ventana:
    buyhold, flat (fijas),
    regla36 (probe original EXP36: probe continuo + re-probe + olvido),
    regimen_adx (alternativa simple a Hurst, CONGELADA: ADX-14 sobre
      168h previas, umbral 25; tendencia -> momentum, si no -> flat).
- Common random numbers dentro de cada (ventana, replica): misma semilla
  Thompson entre politicas. R=4 replicas por ventana.
- Criterio PRE-REGISTRADO (ver resultados/exp42-20260927/preregistro.json):
    efecto(w, p) = media_replicas(P&L_p - P&L_buyhold) en ventana w
    PASS iff alguna politica no-buyhold tiene media_w(efecto) > 0
    y (media - 1*desvio_muestral) > -0.02.
- Replay puro, US$0, 0 llamadas, sin lookahead. Mock total.

Uso: python3 run_experiment42.py
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alma.selector import BanditPorClase  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
DOUT = os.path.join(BASE, "resultados", "exp42-20260927")
DDATA = os.path.join(BASE, "data_exp42")

ARMS = ["momentum", "meanrev", "buyhold", "flat"]
POLITICAS = ["buyhold", "flat", "regla36", "regimen_adx"]
N_BLOQUES, H_BLOQUE = 30, 24
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (12, 13)
MARGEN = 0.02
N0 = 2
DECAY = 0.5
COSTO_BP = 0.0001
CAP = 0.02
R_REPLICAS = 4
# regimen_adx (congelado, sin tuning):
ADX_PERIODO = 14
ADX_LOOKBACK_H = 168
ADX_UMBRAL = 25.0

VENTANAS = [
    ("W1", "XBTUSD", "BTC", "2026-08-28", "2026-09-27"),
    ("W2", "XBTUSD", "BTC", "2026-05-01", "2026-05-31"),
    ("W3", "XBTUSD", "BTC", "2026-01-15", "2026-02-14"),
    ("W4", "ETHUSD", "ETH", "2026-08-28", "2026-09-27"),
    ("W5", "ETHUSD", "ETH", "2026-04-01", "2026-05-01"),
    ("W6", "SOLUSD", "SOL", "2026-08-28", "2026-09-27"),
]


def sign(x):
    return 1.0 if x >= 0 else -1.0


def media(xs):
    return sum(xs) / len(xs)


def desvio(xs):
    m = media(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5 \
        if len(xs) > 1 else 0.0


def cargar_ventana(w):
    d = json.load(open(os.path.join(DDATA, f"{w}.json")))
    n = len(d["close"])
    assert n == ADX_LOOKBACK_H + 720, f"{w}: {n} velas"
    s = ADX_LOOKBACK_H  # el stream arranca aca
    o = d["open"][s - ADX_LOOKBACK_H:]
    h = d["high"][s - ADX_LOOKBACK_H:]
    l = d["low"][s - ADX_LOOKBACK_H:]
    c = d["close"][s - ADX_LOOKBACK_H:]
    closes = c[ADX_LOOKBACK_H:]  # 720 del stream
    rets = [closes[i + 1] / closes[i] - 1 for i in range(len(closes) - 1)]
    return {"o": o, "h": h, "l": l, "c": c, "rets": rets}


def posiciones(rets):
    pos = {}
    pos["momentum"] = [sign(rets[i - 1]) if i > 0 else 1.0
                       for i in range(len(rets))]
    pos["meanrev"] = [-p for p in pos["momentum"]]
    pos["buyhold"] = [1.0] * len(rets)
    pos["flat"] = [0.0] * len(rets)
    return pos


def pnl_hora(pos, rets):
    out = {}
    for a in ARMS:
        ps = pos[a]
        serie, prev = [], 0.0
        for hh in range(len(rets)):
            serie.append(ps[hh] * rets[hh] - COSTO_BP * abs(ps[hh] - prev))
            prev = ps[hh]
        out[a] = serie
    return out


def a_reward(p):
    return 0.5 + max(-CAP, min(CAP, p)) / (2 * CAP)


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


def regla_eleccion36(medias_probe, medias_prior):
    orden = sorted(ARMS, key=lambda a: medias_probe[a], reverse=True)
    mejor, segundo = orden[0], orden[1]
    if medias_probe[mejor] - medias_probe[segundo] < MARGEN:
        return max(ARMS, key=lambda a: medias_prior[a])
    return mejor


def adx_14(highs, lows, closes, p=ADX_PERIODO):
    """ADX de Wilder sobre la serie dada. Devuelve el ultimo valor."""
    n = len(closes)
    tr, pdm, mdm = [], [], []
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        dn = lows[i - 1] - lows[i]
        pdm.append(up if up > dn and up > 0 else 0.0)
        mdm.append(dn if dn > up and dn > 0 else 0.0)
        tr.append(max(highs[i] - lows[i],
                      abs(highs[i] - closes[i - 1]),
                      abs(lows[i] - closes[i - 1])))
    if len(tr) < 2 * p:
        return 0.0
    s_tr = sum(tr[:p])
    s_p = sum(pdm[:p])
    s_m = sum(mdm[:p])
    dxs = []
    for i in range(p, len(tr)):
        s_tr = s_tr - s_tr / p + tr[i]
        s_p = s_p - s_p / p + pdm[i]
        s_m = s_m - s_m / p + mdm[i]
        pdi = 100.0 * s_p / s_tr if s_tr else 0.0
        mdi = 100.0 * s_m / s_tr if s_tr else 0.0
        dxs.append(100.0 * abs(pdi - mdi) / (pdi + mdi)
                   if (pdi + mdi) else 0.0)
    a = sum(dxs[:p]) / p
    for v in dxs[p:]:
        a = (a * (p - 1) + v) / p
    return a


def regimen_bloque(ser, b):
    """ADX-14 sobre las 168h previas al inicio del bloque b (sin lookahead)."""
    fin = ADX_LOOKBACK_H + b * H_BLOQUE  # indice en las series extendidas
    ini = fin - ADX_LOOKBACK_H
    return adx_14(ser["h"][ini:fin], ser["l"][ini:fin], ser["c"][ini:fin])


def correr_regla36(NS, rets, pnl):
    H = len(rets)
    rep = {a: [] for a in ARMS}
    pnl_h = [0.0] * H
    for b in range(N_BLOQUES):
        base = b * H_BLOQUE
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


def correr_regimen_adx(ser, pnl):
    """Determinista: por bloque, ADX-14(168h previas) > 25 -> momentum,
    si no -> flat."""
    H = len(ser["rets"])
    total, diag = 0.0, []
    for b in range(N_BLOQUES):
        base = b * H_BLOQUE
        v = regimen_bloque(ser, b)
        brazo = "momentum" if v > ADX_UMBRAL else "flat"
        hs = [base + q for q in range(H_BLOQUE) if base + q < H]
        total += sum(pnl[brazo][h] for h in hs)
        diag.append({"bloque": b, "adx": round(v, 2), "brazo": brazo})
    return total, diag


def main():
    t0 = time.time()
    os.makedirs(DOUT, exist_ok=True)

    disponibles = [w for w, _, _, _, _ in VENTANAS
                   if os.path.exists(os.path.join(DDATA, f"{w}.json"))]
    for w, _, _, _, _ in VENTANAS:
        if w not in disponibles:
            print(f"  {w}: sin datos, excluida")
    VENT_EF = [v for v in VENTANAS if v[0] in disponibles]

    prereg = {
        "experimento": "ALMA-EXP42: generalizacion a traves de ventanas",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ventanas": [{"id": w, "pair": p, "asset": a, "desde": d, "hasta": h}
                     for w, p, a, d, h in VENTANAS],
        "K": len(VENTANAS),
        "ventanas_efectivas": disponibles,
        "nota_K": "W2 (BTC 2026-05-01->2026-05-31) excluida: hueco real de 5h "
                  "(2026-05-08 02:00-06:00 UTC) en los datos horarios de "
                  "Coinbase; K efectivo = 5, pre-registrado aqui",
        "fuentes": "Coinbase Exchange publico (BTC-USD/ETH-USD/SOL-USD, "
                   "granularity=3600) para las 6 ventanas. Kraken descartado: "
                   "verificado 2026-09-27 que ignora `since` y devuelve solo "
                   "las ~720 velas mas recientes, insuficiente para 888 "
                   "velas alineadas (168 lookback + 720 stream).",
        "replicas_por_ventana": R_REPLICAS,
        "politicas": POLITICAS,
        "regla36": "probe continuo + re-probe + olvido (identica a EXP36/39)",
        "regimen_adx": {
            "indicador": "ADX-14 Wilder", "lookback_h": ADX_LOOKBACK_H,
            "umbral": ADX_UMBRAL, "tendencia": "momentum", "lateral": "flat",
            "nota": "congelado, sin tuning por ventana",
        },
        "costo_bp": COSTO_BP,
        "crn": "misma semilla Thompson entre politicas dentro de "
               "(ventana, replica): NS=exp42-{w}-r{r}",
        "criterio": {
            "efecto": "media_replicas(P&L_politica - P&L_buyhold) por ventana",
            "pass": "alguna politica no-buyhold con media_w(efecto) > 0 "
                    "y (media - 1*desvio_muestral) > -0.02",
        },
        "modo": "mock, replay puro, US$0",
    }
    with open(os.path.join(DOUT, "preregistro.json"), "w") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito. K={len(VENTANAS)}, R={R_REPLICAS}")

    # tabla politica x ventana (efectos = media de replicas vs buyhold)
    tabla = {p: {} for p in POLITICAS if p != "buyhold"}
    diag_adx = {}
    for w, pair, asset, d0, d1 in VENT_EF:
        ser = cargar_ventana(w)
        rets = ser["rets"]
        pos = posiciones(rets)
        pnl = pnl_hora(pos, rets)
        pnl_bh = sum(pnl["buyhold"])
        pnl_flat = sum(pnl["flat"])
        print(f"{w} {asset}: buyhold={pnl_bh:+.3%} flat={pnl_flat:+.3%} "
              f"drift={rets[0] and (sum(rets)):+.3%}")

        ef = {p: [] for p in tabla}
        for r in range(R_REPLICAS):
            NS = f"exp42-{w}-r{r}"
            ef["regla36"].append(correr_regla36(NS, rets, pnl) - pnl_bh)
            # flat y regimen_adx son deterministicas: una sola corrida vale
            if r == 0:
                pnl_adx, dg = correr_regimen_adx(ser, pnl)
                ef["regimen_adx"].append(pnl_adx - pnl_bh)
                ef["flat"].append(pnl_flat - pnl_bh)
                diag_adx[w] = dg
            else:
                ef["regimen_adx"].append(ef["regimen_adx"][0])
                ef["flat"].append(ef["flat"][0])
        for p in tabla:
            tabla[p][w] = {"media": media(ef[p]),
                           "desvio": desvio(ef[p])}

    efectos_w = {p: [tabla[p][w]["media"] for w, _, _, _, _ in VENT_EF]
                 for p in tabla}
    resumen = {}
    for p in tabla:
        m = media(efectos_w[p])
        s = desvio(efectos_w[p])
        resumen[p] = {"media_ventanas": m, "desvio_ventanas": s,
                      "media_menos_1sd": m - s,
                      "pasa": bool(m > 0 and (m - s) > -0.02)}
    pasa = any(v["pasa"] for v in resumen.values())

    report = {
        "preregistro": prereg,
        "tabla_politica_x_ventana": {
            p: {w: round(tabla[p][w]["media"], 6) for w, _, _, _, _ in VENT_EF}
            for p in tabla},
        "efecto_medio_ventanas": {p: {k: round(v, 6) for k, v in resumen[p].items()
                                      if k != "pasa"} for p in resumen},
        "veredicto": {"pasa": pasa,
                      "criterio": prereg["criterio"]["pass"],
                      "motivos": [
                          f"{p}: media_w={resumen[p]['media_ventanas']:+.4%}, "
                          f"sd={resumen[p]['desvio_ventanas']:.4%}, "
                          f"media-1sd={resumen[p]['media_menos_1sd']:+.4%}"
                          for p in tabla]},
        "costo_total_usd": 0.0,
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(DOUT, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO ================")
    for m in report["veredicto"]["motivos"]:
        print("  " + m)
    print("  RESULTADO:", "PASS" if pasa else "FAIL")
    print("===========================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
