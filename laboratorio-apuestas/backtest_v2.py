#!/usr/bin/env python3
"""Laboratorio de apuestas v2 — shrinkage Dixon-Coles hacia el mercado pre-partido.
Ver PREREGISTRO_V2.md (congelado antes de evaluar en test).
p_v2 = lam * p_dc + (1-lam) * p_market_pre ; lam elegido en validación minimizando log-loss.
"""
import os, json
import numpy as np
import pandas as pd

LAB = os.path.expanduser("~/workspace/alma-prototype/laboratorio-apuestas")
df = pd.read_pickle(os.path.join(LAB, "probs.pkl"))
VAL = {"2223"}; TEST = {"2324", "2425"}
THR = 1.05  # fijo a priori (PREREGISTRO_V2.md)
LAMBDAS = [round(x, 1) for x in np.arange(0.0, 1.01, 0.1)]
MP = {"H": 0, "D": 1, "A": 2}

def devig(odds):
    """odds: (n,3) array. Devuelve probs sin margen o NaN por fila inválida."""
    odds = np.asarray(odds, dtype=float)
    ok = ~np.isnan(odds).any(axis=1) & (odds > 1.0).all(axis=1)
    p = np.full_like(odds, np.nan)
    inv = 1.0 / odds[ok]
    p[ok] = inv / inv.sum(axis=1, keepdims=True)
    return p

# mercado pre-partido devigged (sin "C": no mirar el futuro)
df[["mktP_H", "mktP_D", "mktP_A"]] = devig(df[["AvgH", "AvgD", "AvgA"]].values)
# mercado de cierre devigged (referencia de calibración, como en v1)
df[["mktC_H", "mktC_D", "mktC_A"]] = devig(df[["AvgCH", "AvgCD", "AvgCA"]].values)

def onehot(ftr):
    y = np.zeros((len(ftr), 3)); y[np.arange(len(ftr)), ftr.map(MP).values] = 1.0
    return y

def logloss_brier(p, y):
    p = np.clip(p, 1e-9, 1)
    p = p / p.sum(axis=1, keepdims=True)
    ll = float(-np.mean(np.sum(y * np.log(p), axis=1)))
    br = float(np.mean(np.sum((p - y) ** 2, axis=1)))
    return ll, br

def valid_dc_mkt(sub):
    cols = ["pH_dc", "pD_dc", "pA_dc", "mktP_H", "mktP_D", "mktP_A"]
    return sub[cols].notna().all(axis=1).values

# ---------------- 1. Elegir lambda en VALIDACIÓN ----------------
dval = df[df.temp.isin(VAL)].sort_values("date").reset_index(drop=True)
mv = valid_dc_mkt(dval)
yv = onehot(dval.FTR[mv])
pdc_v = dval.loc[mv, ["pH_dc", "pD_dc", "pA_dc"]].values
pmk_v = dval.loc[mv, ["mktP_H", "mktP_D", "mktP_A"]].values
print(f"[VAL] partidos válidos: {mv.sum()} / {len(dval)}", flush=True)

best = None
for lam in LAMBDAS:
    pv = lam * pdc_v + (1 - lam) * pmk_v
    ll, br = logloss_brier(pv, yv)
    key = (round(ll, 12), round(br, 12), lam)  # min logloss, desempate brier, luego menor lam
    if best is None or key < best[0]:
        best = (key, lam, ll, br)
    print(f"  lam={lam:.1f} logloss={ll:.5f} brier={br:.5f}", flush=True)

lam_star = best[1]
print(f"[VAL] lambda* = {lam_star} (logloss={best[2]:.5f}, brier={best[3]:.5f})", flush=True)

# ---------------- 2. Congelar y evaluar en TEST ----------------
df["pH_v2"] = np.nan; df["pD_v2"] = np.nan; df["pA_v2"] = np.nan
mv_all = valid_dc_mkt(df)
pv_all = lam_star * df.loc[mv_all, ["pH_dc", "pD_dc", "pA_dc"]].values + \
         (1 - lam_star) * df.loc[mv_all, ["mktP_H", "mktP_D", "mktP_A"]].values
pv_all = pv_all / pv_all.sum(axis=1, keepdims=True)
df.loc[mv_all, ["pH_v2", "pD_v2", "pA_v2"]] = pv_all

dtest = df[df.temp.isin(TEST)].sort_values("date").reset_index(drop=True)

# 2a. Calibración en test
calib = {}
sets = {
    "dc": ["pH_dc", "pD_dc", "pA_dc"],
    "mercado_pre": ["mktP_H", "mktP_D", "mktP_A"],
    "v2": ["pH_v2", "pD_v2", "pA_v2"],
    "mercado_cierre": ["mktC_H", "mktC_D", "mktC_A"],
}
for name, cols in sets.items():
    sub = dtest[dtest[cols].notna().all(axis=1)]
    p = sub[cols].values; y = onehot(sub.FTR)
    ll, br = logloss_brier(p, y)
    calib[name] = {"logloss": ll, "brier": br, "n": int(len(sub))}
    print(f"[CALIB-TEST] {name:>14}: logloss={ll:.5f} brier={br:.5f} n={len(sub)}", flush=True)

# 2b. Simulación de apuestas v2 (idéntica regla que v1, umbral fijo 1.05)
def simulate(sub, thr):
    bets = []
    for _, r in sub.iterrows():
        pH, pA = r.pH_v2, r.pA_v2
        if pd.isna(pH) or pd.isna(pA):
            continue
        for side, p, price, close, res in (
                ("H", pH, r.MaxH, r.PSCH, r.FTR == "H"),
                ("A", pA, r.MaxA, r.PSCA, r.FTR == "A")):
            if pd.isna(price) or price <= 1.0:
                continue
            if p * price >= thr:
                profit = (price - 1.0) if res else -1.0
                clv = 1.0 if (not pd.isna(close) and price > close) else 0.0
                bets.append({"liga": r.liga, "temp": r.temp, "side": side,
                             "price": float(price), "p": float(p),
                             "profit": float(profit), "clv": clv})
    return pd.DataFrame(bets)

def metrics(bets):
    if len(bets) == 0:
        return {"n": 0, "profit": 0.0, "roi": 0.0, "clv": 0.0, "max_drawdown": 0.0}
    cum = bets.profit.cumsum().values
    dd = float((np.maximum.accumulate(cum) - cum).max())
    return {"n": int(len(bets)), "profit": float(bets.profit.sum()),
            "roi": float(bets.profit.sum() / len(bets)),
            "clv": float(bets.clv.mean()), "max_drawdown": dd}

b = simulate(dtest, THR)
m = metrics(b)
per_liga = {l: metrics(g) for l, g in b.groupby("liga")} if len(b) else {}
per_temp = {t: int((b.temp == t).sum()) for t in sorted(TEST)} if len(b) else {}

# sin filtro: lado con mayor p_v2
prof, n = 0.0, 0
for _, r in dtest.iterrows():
    if pd.isna(r.pH_v2) or pd.isna(r.pA_v2):
        continue
    if r.pH_v2 >= r.pA_v2 and not pd.isna(r.MaxH) and r.MaxH > 1.0:
        prof += (r.MaxH - 1.0) if r.FTR == "H" else -1.0; n += 1
    elif r.pA_v2 > r.pH_v2 and not pd.isna(r.MaxA) and r.MaxA > 1.0:
        prof += (r.MaxA - 1.0) if r.FTR == "A" else -1.0; n += 1
nf = {"n": n, "roi": prof / n if n else 0.0}

pasa = bool(m["roi"] > 0.02 and m["n"] >= 200 and m["clv"] >= 0.55)
print(f"[V2-TEST] n={m['n']} roi={m['roi']:.4f} clv={m['clv']:.3f} dd={m['max_drawdown']:.1f} "
      f"-> {'PASS' if pasa else 'FAIL'}", flush=True)

results = {
    "lambda_star": lam_star,
    "lambda_val": {str(lam): {"logloss": None} for lam in LAMBDAS},
    "umbral": THR,
    "calibracion_test": calib,
    "test": m,
    "por_liga": {l: {"n": v["n"], "roi": v["roi"], "clv": v["clv"]} for l, v in per_liga.items()},
    "n_por_temporada": per_temp,
    "sin_filtro": nf,
    "pasa_criterio": pasa,
}
with open(os.path.join(LAB, "results_v2.json"), "w") as f:
    json.dump(results, f, indent=1)
print("results_v2.json guardado", flush=True)
