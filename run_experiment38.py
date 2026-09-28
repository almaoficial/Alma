#!/usr/bin/env python3
"""ALMA-EXP38: mismo stream real que EXP36/37, solo el cambio (a) calibrado.

EXP37 FAIL: el desempate a flat + penal por cambio mató la mitad en
tendencia (14/15 bloques en flat). El umbral 0.02 estaba heredado sin
calibrar y el penal creó histéresis. Los dos cambios no se separaron.

EXP38 aísla el cambio (a) y calibra el detector:
  (a) Desempate del probe hacia `flat` cuando no hay brecha clara de señal.
  SIN penal por cambio (b): la estructura del bloque es la de EXP36
  (probe -> Thompson -> re-probe -> Thompson); solo cambia la regla de
  elección del probe.
  Calibración: "brecha clara" = gap > K_SENAL x se_gap, donde se_gap es el
  error estándar de la brecha estimado de las propias observaciones del
  probe de esta decisión (k=1 pre-registrado), en vez de un número fijo
  heredado. se_a = s_a / sqrt(n_a); se_gap = sqrt(se_best^2 + se_second^2).

Criterio PRE-REGISTRADO principal (ver resultados/exp38-20260927/preregistro.json):
    PASS iff P&L_neto_total(ALMA38) > P&L_neto_total(mejor brazo fijo).
Criterio secundario (honesto, no mueve el principal):
    (a) pnl_h1_38 > -0.04213  (recorta el sangrado lateral de EXP36)
    (b) pnl_h2_38 >= 0.08     (retiene al menos +8% en la mitad en tendencia;
                               EXP36 logró +12.671%)

Replay puro sobre datos Kraken públicos (idénticos a EXP36/37): US$0,
0 llamadas. Mock total.

Uso: python3 run_experiment38.py
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alma.selector import BanditPorClase  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "resultados", "exp38-20260927")
ARMS = ["momentum", "meanrev", "buyhold", "flat"]
N_BLOQUES, H_BLOQUE = 30, 24
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (12, 13)
K_SENAL = 1.0  # PRE-REGISTRADO: brecha mínima = k x se del propio probe
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


def se_media(xs):
    """Error estándar de la media (muestral, n-1)."""
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return (v ** 0.5) / (n ** 0.5)


def regla_eleccion38(obs_probe):
    """Devuelve (elegido, senal_debil, gap, umbral).

    Solo el cambio (a): desempate hacia `flat` si no hay brecha clara.
    SIN penal por cambio (b). El umbral se calibra contra el ruido del
    propio probe: señal clara iff gap > K_SENAL * se_gap.
    obs_probe: {(q, a): reward} de esta decisión (3 obs/brazo en q1,
    5 obs/brazo en el re-probe).
    """
    por_a = {}
    for (q, a), r in obs_probe.items():
        por_a.setdefault(a, []).append(r)
    medias = {a: sum(v) / len(v) for a, v in por_a.items()}
    orden = sorted(ARMS, key=lambda a: medias[a], reverse=True)
    mejor, segundo = orden[0], orden[1]
    gap = medias[mejor] - medias[segundo]
    se_gap = (se_media(por_a[mejor]) ** 2
              + se_media(por_a[segundo]) ** 2) ** 0.5
    umbral = K_SENAL * se_gap
    if gap > umbral:
        return mejor, False, gap, umbral
    return "flat", True, gap, umbral


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)

    # --- pre-registro ANTES de correr ---
    prereg = {
        "experimento": "ALMA-EXP38: (a) solo, umbral calibrado contra el ruido del probe",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cambio_vs_exp36": {
            "a": "desempate del probe hacia 'flat' si brecha no clara",
            "b": "ELIMINADO: sin penal por cambio; estructura de bloque = EXP36 "
                 "(probe -> Thompson -> re-probe -> Thompson)",
            "calibracion": "brecha clara iff gap > K_SENAL x se_gap; "
                           "se_gap estimado de las propias observaciones del "
                           "probe de esta decisión; K_SENAL=1.0 pre-registrado",
        },
        "umbrales": {"K_SENAL": K_SENAL},
        "criterio_principal": "pnl_total(alma38) > pnl_total(mejor_fija)",
        "criterio_secundario": {
            "recorta_sangrado": "pnl_h1_38 > -0.04213 (EXP36)",
            "retiene_tendencia": "pnl_h2_38 >= 0.08 (EXP36: +0.12671)",
        },
        "stream": "idéntico a EXP36/37: Kraken XBTUSD 1h, 720 velas, 719 retornos",
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
                rng = random.Random(f"exp38-{b}-{h}")
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
        elegido1, debil1, gap1, umbral1 = regla_eleccion38(prs1)
        fijar(PROBE_Q1, elegido1)
        if debil1:
            n_bloques_debiles += 1
        thompson(range(3, 12))   # (b) eliminado: Thompson siempre corre

        prs2 = spy(PROBE_Q2)
        todo = dict(prs1)
        todo.update(prs2)
        elegido2, debil2, gap2, umbral2 = regla_eleccion38(todo)
        if elegido1 != elegido2:
            n_switch += 1
        fijar(PROBE_Q2, elegido2)
        thompson(range(14, H_BLOQUE))

        diag.append({"bloque": b, "inicial": elegido1, "final": elegido2,
                     "debil_inicial": debil1, "debil_final": debil2,
                     "gap_inicial": round(gap1, 5),
                     "umbral_inicial": round(umbral1, 5),
                     "gap_final": round(gap2, 5),
                     "umbral_final": round(umbral2, 5),
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
    sec_b = pnl_alma_h2 >= 0.08
    motivos = [
        f"P&L total: ALMA38={pnl_alma_total:+.4%} vs mejor fija "
        f"({mejor_fija})={pnl_fija[mejor_fija]:+.4%} "
        f"(diff={pnl_alma_total - pnl_fija[mejor_fija]:+.4%})",
        "P&L fijas: " + ", ".join(f"{a}={pnl_fija[a]:+.3%}" for a in ARMS),
        f"1ra mitad (lateral): ALMA38={pnl_alma_h1:+.3%} "
        f"(EXP36: {EXP36_H1:+.3%}) | fijas: " +
        ", ".join(f"{a}={pnl_fija_h1[a]:+.3%}" for a in ARMS),
        f"2da mitad (tendencia): ALMA38={pnl_alma_h2:+.3%} "
        f"(EXP36: {EXP36_H2:+.3%}) | fijas: " +
        ", ".join(f"{a}={pnl_fija_h2[a]:+.3%}" for a in ARMS),
        f"bloques con señal débil (probe en flat): {n_bloques_debiles}/{N_BLOQUES} "
        f"(Thompson igual corrió)",
        f"cambios tras re-probe: {n_switch}/{N_BLOQUES} bloques",
        f"secundario: recorta sangrado={'SI' if sec_a else 'NO'}, "
        f"retiene tendencia={'SI' if sec_b else 'NO'}",
    ]
    report = {
        "preregistro": "resultados/exp38-20260927/preregistro.json",
        "umbrales": {"K_SENAL": K_SENAL},
        "pnl_total": {"alma38": round(pnl_alma_total, 6),
                      "fijas": {a: round(v, 6) for a, v in pnl_fija.items()},
                      "mejor_fija": mejor_fija},
        "pnl_mitades": {"alma38_h1": round(pnl_alma_h1, 6),
                        "alma38_h2": round(pnl_alma_h2, 6),
                        "exp36_h1": EXP36_H1, "exp36_h2": EXP36_H2,
                        "fijas_h1": {a: round(v, 6) for a, v in pnl_fija_h1.items()},
                        "fijas_h2": {a: round(v, 6) for a, v in pnl_fija_h2.items()}},
        "diagnostico_bloques": diag,
        "bloques_debiles": n_bloques_debiles,
        "switches_reprobe": n_switch,
        "criterio_secundario": {"recorta_sangrado": bool(sec_a),
                                "retiene_tendencia": bool(sec_b)},
        "costo_total_usd": 0.0,
        "veredicto": {"pasa": pasa,
                       "criterio": "pnl_total(alma38) > pnl_total(mejor_fija)",
                       "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP38 ================")
    for m in motivos:
        print("  " + m)
    print(f"  costo: $0.0000 USD (replay puro) | {report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL",
          "— ALMA38 supera a la mejor fija" if pasa
          else "— ALMA38 no supera a la mejor fija (vara intacta)")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
