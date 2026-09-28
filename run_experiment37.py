#!/usr/bin/env python3
"""ALMA-EXP37: mismo stream real que EXP36, con regla de decisión endurecida.

EXP36 FAIL: ALMA +8,458% vs buyhold +8,504%. Ganó la mitad en tendencia
(+12,67%) pero sangró en la mitad lateral (-4,21%) porque el desempate del
probe defaulteó a orden de lista (momentum) en vez del brazo seguro (flat)
cuando no había brecha de señal.

Cambios pre-registrados (ver resultados/exp37-20260927/preregistro.json):
  (a) Desempate hacia `flat` cuando no hay brecha clara de señal.
      "Brecha clara" = (mejor - segundo mejor) >= UMBRAL_SENAL en medias
      ajustadas del probe. UMBRAL_SENAL = 0.02 (igual que el MARGEN de EXP36,
      continuidad).
  (b) Costo de exploración explícito:
      - Penalización por cambio de brazo: CAMBIO_PENAL = 0.01 (unidades de
        reward) restada a la media del probe de todo brazo distinto del
        brazo final del bloque anterior (bloque 0: sin penalización).
      - Si no hay brecha clara -> bloque en `flat` COMPLETO: sin Thompson,
        sin exploración, sin costo de cambio. Solo se re-evalúa en el
        re-probe (q=12,13); si ahí la señal se aclara, se cambia al ganador
        y Thompson retoma en q=14..23.

Criterio PRE-REGISTRADO principal:
    PASS iff P&L_neto_total(ALMA37) > P&L_neto_total(mejor brazo fijo).
Criterio secundario (honesto, no mueve el principal):
    (a) pnl_h1_37 > pnl_h1_36 (recorta el sangrado lateral de -4,213%) y
    (b) pnl_h2_37 >= pnl_h2_36 - 0.02 (no pierde más de 2 puntos de la
    ganancia en tendencia de +12,671%).

Replay puro sobre datos Kraken públicos: US$0, 0 llamadas. Mock total.

Uso: python3 run_experiment37.py
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alma.selector import BanditPorClase  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "resultados", "exp37-20260927")
ARMS = ["momentum", "meanrev", "buyhold", "flat"]
N_BLOQUES, H_BLOQUE = 30, 24
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (12, 13)
UMBRAL_SENAL = 0.02   # "brecha clara" entre mejor y 2do mejor (reward)
CAMBIO_PENAL = 0.01   # penalización por cambiar de brazo (reward)
N0 = 2
DECAY = 0.5
COSTO_BP = 0.0001
CAP = 0.02

# Referencias EXP36 para el criterio secundario (del veredicto EXP36)
EXP36_H1 = -0.04213
EXP36_H2 = 0.12671


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


def regla_eleccion37(medias_probe, brazo_anterior):
    """Devuelve (elegido, senal_debil, brecha).

    (b) Penaliza cambiar de brazo: todo brazo distinto del final del bloque
    anterior pierde CAMBIO_PENAL en su media del probe.
    (a) Si la brecha ajustada < UMBRAL_SENAL -> flat (brazo seguro).
    """
    adj = {a: medias_probe[a] - (CAMBIO_PENAL if brazo_anterior is not None
                                 and a != brazo_anterior else 0.0)
           for a in ARMS}
    orden = sorted(ARMS, key=lambda a: adj[a], reverse=True)
    mejor, segundo = orden[0], orden[1]
    brecha = adj[mejor] - adj[segundo]
    if brecha >= UMBRAL_SENAL:
        return mejor, False, brecha
    return "flat", True, brecha


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)

    # --- pre-registro ANTES de correr ---
    prereg = {
        "experimento": "ALMA-EXP37: desempate a flat + costo de exploración",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cambios_vs_exp36": {
            "a": "desempate del probe hacia 'flat' si brecha < UMBRAL_SENAL",
            "b": "CAMBIO_PENAL=0.01 a todo brazo != brazo anterior; "
                 "sin brecha clara -> bloque completo en flat (sin Thompson)",
        },
        "umbrales": {"UMBRAL_SENAL": UMBRAL_SENAL,
                     "CAMBIO_PENAL": CAMBIO_PENAL},
        "criterio_principal": "pnl_total(alma37) > pnl_total(mejor_fija)",
        "criterio_secundario": {
            "recorta_sangrado": "pnl_h1_37 > -0.04213 (EXP36)",
            "no_pierde_tendencia": "pnl_h2_37 >= 0.12671 - 0.02",
        },
        "stream": "idéntico a EXP36: Kraken XBTUSD 1h, 720 velas, 719 retornos",
        "modo": "mock, replay puro, US$0",
    }
    with open(os.path.join(OUT, "preregistro.json"), "w") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito. Criterio: {prereg['criterio_principal']}")

    rets = cargar_serie()
    pos = posiciones(rets)
    pnl = pnl_hora(pos, rets)
    H = len(rets)

    pnl_fija = {a: sum(pnl[a]) for a in ARMS}
    mejor_fija = max(ARMS, key=lambda a: pnl_fija[a])

    rep = {a: [] for a in ARMS}
    pnl_alma_h = [0.0] * H
    diag = []
    n_switch = 0
    n_bloques_debiles = 0
    brazo_anterior = None

    for b in range(N_BLOQUES):
        base = b * H_BLOQUE
        rep_w = {a: [(r, DECAY ** ((b * H_BLOQUE - 1 - hh) // H_BLOQUE))
                    for hh, r in rep[a]] for a in ARMS}
        bandit = bandit_warm_olvido(rep_w)

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
                rng = random.Random(f"exp37-{b}-{h}")
                a = bandit.select(rng)
                r = a_reward(pnl[a][h])
                bandit.update(a, r)
                rep[a].append((h, r))
                pnl_alma_h[h] = pnl[a][h]

        def fijar(qs, brazo):
            for q in qs:
                h = base + q
                if h < H:
                    pnl_alma_h[h] = pnl[brazo][h]

        prs1 = spy(PROBE_Q1)
        m1 = {a: sum(prs1[(q, a)] for q in PROBE_Q1) / len(PROBE_Q1)
              for a in ARMS}
        elegido1, debil1, brecha1 = regla_eleccion37(m1, brazo_anterior)
        fijar(PROBE_Q1, elegido1)
        if debil1:
            n_bloques_debiles += 1
            fijar(range(3, 12), "flat")   # (b) sin exploración si no hay señal
        else:
            thompson(range(3, 12))

        prs2 = spy(PROBE_Q2)
        todo = dict(prs1)
        todo.update(prs2)
        qs_all = PROBE_Q1 + PROBE_Q2
        m2 = {a: sum(todo[(q, a)] for q in qs_all) / len(qs_all)
              for a in ARMS}
        elegido2, debil2, brecha2 = regla_eleccion37(m2, brazo_anterior)
        if elegido1 != elegido2:
            n_switch += 1
        fijar(PROBE_Q2, elegido2)
        if debil2:
            fijar(range(14, H_BLOQUE), "flat")
        else:
            thompson(range(14, H_BLOQUE))

        brazo_anterior = elegido2
        diag.append({"bloque": b, "inicial": elegido1, "final": elegido2,
                     "debil_inicial": debil1, "debil_final": debil2,
                     "brecha_inicial": round(brecha1, 4),
                     "brecha_final": round(brecha2, 4),
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
    sec_a = pnl_alma_h1 > EXP36_H1
    sec_b = pnl_alma_h2 >= EXP36_H2 - 0.02
    motivos = [
        f"P&L total: ALMA37={pnl_alma_total:+.4%} vs mejor fija "
        f"({mejor_fija})={pnl_fija[mejor_fija]:+.4%} "
        f"(diff={pnl_alma_total - pnl_fija[mejor_fija]:+.4%})",
        "P&L fijas: " + ", ".join(f"{a}={pnl_fija[a]:+.3%}" for a in ARMS),
        f"1ra mitad (lateral): ALMA37={pnl_alma_h1:+.3%} "
        f"(EXP36: {EXP36_H1:+.3%}) | fijas: " +
        ", ".join(f"{a}={pnl_fija_h1[a]:+.3%}" for a in ARMS),
        f"2da mitad (tendencia): ALMA37={pnl_alma_h2:+.3%} "
        f"(EXP36: {EXP36_H2:+.3%}) | fijas: " +
        ", ".join(f"{a}={pnl_fija_h2[a]:+.3%}" for a in ARMS),
        f"bloques con señal débil (flat completo): {n_bloques_debiles}/{N_BLOQUES}",
        f"cambios tras re-probe: {n_switch}/{N_BLOQUES} bloques",
        f"secundario: recorta sangrado={'SI' if sec_a else 'NO'}, "
        f"no pierde tendencia={'SI' if sec_b else 'NO'}",
    ]
    report = {
        "preregistro": "resultados/exp37-20260927/preregistro.json",
        "umbrales": {"UMBRAL_SENAL": UMBRAL_SENAL,
                     "CAMBIO_PENAL": CAMBIO_PENAL},
        "pnl_total": {"alma37": round(pnl_alma_total, 6),
                      "fijas": {a: round(v, 6) for a, v in pnl_fija.items()},
                      "mejor_fija": mejor_fija},
        "pnl_mitades": {"alma37_h1": round(pnl_alma_h1, 6),
                        "alma37_h2": round(pnl_alma_h2, 6),
                        "exp36_h1": EXP36_H1, "exp36_h2": EXP36_H2,
                        "fijas_h1": {a: round(v, 6) for a, v in pnl_fija_h1.items()},
                        "fijas_h2": {a: round(v, 6) for a, v in pnl_fija_h2.items()}},
        "diagnostico_bloques": diag,
        "bloques_debiles": n_bloques_debiles,
        "switches_reprobe": n_switch,
        "criterio_secundario": {"recorta_sangrado": bool(sec_a),
                                "no_pierde_tendencia": bool(sec_b)},
        "costo_total_usd": 0.0,
        "veredicto": {"pasa": pasa,
                       "criterio": "pnl_total(alma37) > pnl_total(mejor_fija)",
                       "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP37 ================")
    for m in motivos:
        print("  " + m)
    print(f"  costo: $0.0000 USD (replay puro) | {report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL",
          "— ALMA37 supera a la mejor fija" if pasa
          else "— ALMA37 no supera a la mejor fija (vara intacta)")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
