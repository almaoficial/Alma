#!/usr/bin/env python3
"""ALMA-EXP40: test de régimen previo al probe.

La serie 36-39 mostró que ninguna variante del probe le gana a buyhold en
el stream BTC 30d, y que el ruido de semilla (±10 pts) domina al
efecto-regla. EXP39 cerró: "sin un test de régimen previo al probe no hay
qué decidir".

EXP40 prueba exactamente eso: antes del probe de cada bloque (24h), un test
barato sobre la ventana trailing clasifica el régimen; la política es
condicional (sin probe):
    tendencia  -> brazo momentum (todo el bloque)
    lateral    -> flat (todo el bloque)

Test PRE-REGISTRADO: exponente de Hurst por rescaled range (R/S) sobre los
retornos logarítmicos de las 72h previas al bloque; H >= 0.55 -> tendencia,
si no lateral. Ventana mínima 24 puntos; sin historia suficiente
(bloque 0) -> lateral por defecto (conservador).

Comparación bajo common random numbers contra regla36 (EXP36, con su
Thompson) y contra buyhold, 6 réplicas como EXP39. EXP40 es determinista
(sin Thompson), así que el CRN solo afecta a regla36; las réplicas de
EXP40 son idénticas por construcción (se reportan igual).

Criterio PRE-REGISTRADO (ver resultados/exp40-20260927/preregistro.json):
    efecto = P&L_exp40(réplica) - P&L_buyhold
    PASS iff media(efecto) > 0 y media(efecto) - 1*desvío(efecto) > -0.01.
Secundario honesto: tasa de acierto del clasificador vs régimen "verdadero"
ex-post, definido de forma simple y pre-registrada:
    verdadero = "tendencia" iff |retorno total del bloque| > 0.02.
La tasa se mide en bloques 1..29 (el bloque 0 no tiene historia y se
excluye, pre-registrado).

Replay puro sobre datos Kraken públicos (idénticos a EXP36-39): US$0, 0
llamadas. Mock total. Sin lookahead: el test usa solo closes <= inicio
del bloque.

Uso: python3 run_experiment40.py
"""
import json
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alma.selector import BanditPorClase  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "resultados", "exp40-20260927")
ARMS = ["momentum", "meanrev", "buyhold", "flat"]
N_BLOQUES, H_BLOQUE = 30, 24
MARGEN = 0.02          # regla EXP36 (comparación)
N0 = 2
DECAY = 0.5
COSTO_BP = 0.0001
CAP = 0.02
N_REPLICAS = 6         # PRE-REGISTRADO (como EXP39)

# --- test de régimen (PRE-REGISTRADO) ---
HURST_WIN = 72         # closes trailing
HURST_MIN = 24         # ventana mínima; si no, lateral por defecto
H_TREND = 0.55         # H >= umbral -> tendencia
HURST_KS = (8, 12, 18, 24, 36)   # tamaños de sub-ventana del R/S
UMBRAL_VERDAD = 0.02   # |retorno del bloque| > umbral -> tendencia ex-post


def sign(x):
    return 1.0 if x >= 0 else -1.0


def cargar_serie():
    d = json.load(open(os.path.join(BASE, "data_exp36", "btc_h1.json")))
    c = d["close"][:720]
    assert len(c) == 720
    rets = [c[i + 1] / c[i] - 1 for i in range(len(c) - 1)]  # 719 retornos
    return rets, c


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


# ---------------- test de régimen: Hurst por R/S ----------------

def hurst_rs(logp):
    """Hurst por R/S sobre los RETORNOS logarítmicos (estándar en finanzas).

    Serie: r_i = logp[i+1]-logp[i]. Para cada tamaño k: chunks no solapados
    de retornos; Y = desvíos acumulados respecto de la media del chunk;
    R = rango(Y); S = desvío de los retornos del chunk. H = pendiente de
    log(R/S) ~ log(k). Random walk -> 0.5; persistente -> >0.5;
    anti-persistente -> <0.5 (verificado en sintéticos).

    CORRECCIÓN 2026-09-27: la primera versión aplicaba el R/S sobre los
    NIVELES de log-precios con S = desvío de niveles, lo que da H~0.9 para
    un random walk (no estima nada). Se corrigió a retornos antes de la
    corrida oficial; el run buggy quedó archivado en
    report_run1_hurst_levels_bug.json. El criterio pre-registrado no cambió.
    """
    r = [logp[i + 1] - logp[i] for i in range(len(logp) - 1)]
    n = len(r)
    ks = [k for k in HURST_KS if 4 <= k <= n // 2]
    pts = []
    for k in ks:
        m = n // k
        rss = []
        for i in range(m):
            seg = r[i * k:(i + 1) * k]
            mu = sum(seg) / k
            y, mx, mn = 0.0, 0.0, 0.0
            for x in seg:
                y += x - mu
                if y > mx:
                    mx = y
                if y < mn:
                    mn = y
            R = mx - mn
            var = sum((x - mu) ** 2 for x in seg) / k
            S = math.sqrt(var) if var > 0 else 0.0
            if S > 0 and R > 0:
                rss.append(R / S)
        if rss:
            pts.append((math.log(k), math.log(sum(rss) / len(rss))))
    if len(pts) < 2:
        return 0.5
    mx = sum(p[0] for p in pts) / len(pts)
    my = sum(p[1] for p in pts) / len(pts)
    num = sum((p[0] - mx) * (p[1] - my) for p in pts)
    den = sum((p[0] - mx) ** 2 for p in pts)
    if den <= 0:
        return 0.5
    return max(0.0, min(1.0, num / den))


# ---------------- regla EXP36 (comparación, idéntica a EXP39) ----------------

def regla_eleccion36(medias_probe, medias_prior):
    """EXP36: si brecha < MARGEN, desempata al favorito del prior."""
    orden = sorted(ARMS, key=lambda a: medias_probe[a], reverse=True)
    mejor, segundo = orden[0], orden[1]
    if medias_probe[mejor] - medias_probe[segundo] < MARGEN:
        return max(ARMS, key=lambda a: medias_prior[a])
    return mejor


def _base_bloque(b, rep):
    rep_w = {a: [(r, DECAY ** ((b * H_BLOQUE - 1 - hh) // H_BLOQUE))
                 for hh, r in rep[a]] for a in ARMS}
    return bandit_warm_olvido(rep_w)


def correr_regla36(NS, rets, pos, pnl):
    H = len(rets)
    rep = {a: [] for a in ARMS}
    pnl_h = [0.0] * H
    PROBE_Q1 = (0, 1, 2)
    PROBE_Q2 = (12, 13)
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


# ---------------- EXP40: política condicional por régimen ----------------

def correr_exp40(rets, closes):
    """Test de régimen previo al probe; sin probe ni Thompson.

    Devuelve (pnl_total, clasificaciones por bloque).
    """
    H = len(rets)
    logp_all = [math.log(c) for c in closes]
    pos_m = posiciones(rets)["momentum"]
    pnl_h = [0.0] * H
    clasif = []
    prev_pos = 0.0
    for b in range(N_BLOQUES):
        base = b * H_BLOQUE
        # Ventana trailing: hasta 72 closes, terminando en el inicio del
        # bloque (sin lookahead: el close base se conoce antes del retorno h=base).
        win = logp_all[max(0, base - (HURST_WIN - 1)):base + 1]
        if len(win) < HURST_MIN:
            h_est, clase = None, "lateral"
        else:
            h_est = hurst_rs(win)
            clase = "tendencia" if h_est >= H_TREND else "lateral"
        en_tendencia = (clase == "tendencia")
        for q in range(H_BLOQUE):
            h = base + q
            if h >= H:
                continue
            p = pos_m[h] if en_tendencia else 0.0
            pnl_h[h] = p * rets[h] - COSTO_BP * abs(p - prev_pos)
            prev_pos = p
        rb = sum(rets[base:min(base + H_BLOQUE, H)])
        verdad = "tendencia" if abs(rb) > UMBRAL_VERDAD else "lateral"
        clasif.append({"bloque": b, "hurst": h_est, "clase": clase,
                       "verdad": verdad,
                       "retorno_bloque": rb})
    return sum(pnl_h), clasif


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

    rets, closes = cargar_serie()
    pos = posiciones(rets)
    pnl = pnl_hora(pos, rets)
    pnl_buyhold = sum(pnl["buyhold"])

    # --- chequeo de fidelidad: regla36 con los NS de EXP39 reproduce su tabla ---
    esperados = [-0.00828, -0.02036, -0.02998, 0.22040, 0.09511, 0.12473]
    for r in range(N_REPLICAS):
        t = correr_regla36(f"exp39-r{r}", rets, pos, pnl)
        assert abs(t - esperados[r]) < 5e-4, \
            f"fidelidad rota en r{r}: {t:.6f} vs {esperados[r]:.6f}"
    print("Fidelidad regla36 vs EXP39: OK (6/6 réplicas).")

    # --- pre-registro ANTES de correr el experimento ---
    prereg = {
        "experimento": "ALMA-EXP40: test de régimen previo al probe",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "motivacion": "Serie 36-39: ninguna variante del probe le gana a "
                      "buyhold; el ruido de semilla domina al efecto-regla. "
                      "EXP39: 'sin un test de régimen previo al probe no hay "
                      "qué decidir'.",
        "diseno": {
            "test_regimen": "exponente de Hurst por R/S sobre los retornos "
                            "logarítmicos de las 72h previas al bloque "
                            f"(sub-ventanas {list(HURST_KS)}); sin lookahead "
                            "(corrección 2026-09-27: el run 1 usó R/S sobre "
                            "niveles por error, archivado en "
                            "report_run1_hurst_levels_bug.json)",
            "umbral": f"H >= {H_TREND} -> tendencia, si no lateral",
            "warmup": f"ventana < {HURST_MIN} puntos (bloque 0) -> lateral "
                      "por defecto",
            "politica": "tendencia -> brazo momentum todo el bloque; "
                        "lateral -> flat todo el bloque (sin probe)",
            "comparacion": "common random numbers contra regla36 (EXP36) y "
                           "buyhold; EXP40 es determinista (réplicas "
                           "idénticas por construcción)",
            "replicas": N_REPLICAS,
            "stream": "idéntico a EXP36-39: Kraken XBTUSD 1h, 720 velas, "
                      "719 retornos",
            "costos": "1bp por cambio de posición, exactos en la trayectoria "
                      "de EXP40 (incluye transiciones entre bloques)",
        },
        "criterio": {
            "efecto": "P&L_exp40(réplica) - P&L_buyhold",
            "pass": "media(efecto) > 0 y media(efecto) - 1*desvío(efecto) > -0.01",
            "secundario": "tasa de acierto del clasificador vs régimen "
                          "verdadero ex-post (|retorno del bloque| > "
                          f"{UMBRAL_VERDAD}), medida en bloques 1..29",
        },
        "modo": "mock, replay puro, US$0",
    }
    with open(os.path.join(OUT, "preregistro.json"), "w") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito ({N_REPLICAS} réplicas, CRN vs regla36).")

    tabla = {"exp40": [], "regla36": []}
    clasif = None
    for r in range(N_REPLICAS):
        NS = f"exp40-r{r}"
        t40, clasif = correr_exp40(rets, closes)
        t36 = correr_regla36(NS, rets, pos, pnl)
        tabla["exp40"].append(t40)
        tabla["regla36"].append(t36)
        print(f"  réplica r{r}: EXP40={t40:+.4%} regla36={t36:+.4%}", flush=True)

    efectos = {n: [t - pnl_buyhold for t in ts]
               for n, ts in tabla.items()}
    resumen = {}
    for n, ef in efectos.items():
        m, s = media(ef), desvio(ef)
        resumen[n] = {"media": m, "desvio": s, "media_menos_1sd": m - s}

    # secundario: acierto del clasificador (bloques 1..29)
    ev = [c for c in clasif if c["bloque"] > 0]
    aciertos = sum(1 for c in ev if c["clase"] == c["verdad"])
    hit_rate = aciertos / len(ev)
    n_clas_t = sum(1 for c in ev if c["clase"] == "tendencia")
    n_verd_t = sum(1 for c in ev if c["verdad"] == "tendencia")
    tp = sum(1 for c in ev if c["clase"] == "tendencia"
             and c["verdad"] == "tendencia")

    pasa = (resumen["exp40"]["media"] > 0
            and resumen["exp40"]["media_menos_1sd"] > -0.01)

    motivos = [
        f"buyhold (referencia fija): {pnl_buyhold:+.4%}",
        f"exp40: P&L={tabla['exp40'][0]:+.4%} "
        f"(idéntico en las {N_REPLICAS} réplicas: determinista), "
        f"efecto neto media={resumen['exp40']['media']:+.4%}, "
        f"desvío={resumen['exp40']['desvio']:+.4%}, "
        f"media-1sd={resumen['exp40']['media_menos_1sd']:+.4%}",
        f"regla36 (CRN): efecto neto media={resumen['regla36']['media']:+.4%}, "
        f"desvío={resumen['regla36']['desvio']:+.4%}",
        f"clasificador: acierto {aciertos}/{len(ev)} = {hit_rate:.1%} "
        f"(bloques 1..29); clasificó tendencia en {n_clas_t}, "
        f"verdad ex-post tendencia en {n_verd_t}, "
        f"verdaderos positivos {tp}",
        "PASS" if pasa else "no cumple media>0 y media-1sd>-1% (vara intacta)",
    ]

    report = {
        "preregistro": "resultados/exp40-20260927/preregistro.json",
        "replicas": N_REPLICAS,
        "pnl_buyhold": round(pnl_buyhold, 6),
        "tabla_regla_x_replica": {
            n: [round(t, 6) for t in ts] for n, ts in tabla.items()},
        "efecto_neto": {n: {k: round(v, 6) for k, v in rs.items()}
                        for n, rs in resumen.items()},
        "clasificador": {
            "hit_rate_bloques_1_29": round(hit_rate, 4),
            "aciertos": aciertos, "n_bloques": len(ev),
            "clasifico_tendencia": n_clas_t,
            "verdad_tendencia": n_verd_t,
            "verdaderos_positivos": tp,
            "detalle": [{**c,
                         "hurst": None if c["hurst"] is None
                         else round(c["hurst"], 4),
                         "retorno_bloque": round(c["retorno_bloque"], 6)}
                        for c in clasif],
        },
        "costo_total_usd": 0.0,
        "veredicto": {"pasa": bool(pasa),
                       "criterio": prereg["criterio"], "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP40 ================")
    for m in motivos:
        print("  " + m)
    print(f"  costo: $0.0000 USD (replay puro) | {report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
