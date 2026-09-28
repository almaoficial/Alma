#!/usr/bin/env python3
"""Parte 2: simulación de apuestas, umbral en validación, métricas y veredicto."""
import os, json
import numpy as np
import pandas as pd

LAB = os.path.expanduser("~/workspace/alma-prototype/laboratorio-apuestas")
df = pd.read_pickle(os.path.join(LAB, "probs.pkl"))
VAL = {"2223"}; TEST = {"2324", "2425"}
THRESHOLDS = [1.03, 1.05, 1.08, 1.10]
ARMS = {"elo": ("pH_elo", "pD_elo", "pA_elo"), "dc": ("pH_dc", "pD_dc", "pA_dc")}

def simulate(sub, arm, thr):
    cH, cA = ARMS[arm][0], ARMS[arm][2]
    bets = []
    for _, r in sub.iterrows():
        pH, pA = r[cH], r[cA]
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
    peak = np.maximum.accumulate(cum)
    dd = float((peak - cum).max())
    return {"n": int(len(bets)), "profit": float(bets.profit.sum()),
            "roi": float(bets.profit.sum() / len(bets)),
            "clv": float(bets.clv.mean()), "max_drawdown": dd}

def no_filter_roi(sub, arm):
    cH, cA = ARMS[arm][0], ARMS[arm][2]
    prof, n = 0.0, 0
    for _, r in sub.iterrows():
        pH, pA = r[cH], r[cA]
        if pd.isna(pH) or pd.isna(pA):
            continue
        if pH >= pA and not pd.isna(r.MaxH) and r.MaxH > 1.0:
            prof += (r.MaxH - 1.0) if r.FTR == "H" else -1.0; n += 1
        elif pA > pH and not pd.isna(r.MaxA) and r.MaxA > 1.0:
            prof += (r.MaxA - 1.0) if r.FTR == "A" else -1.0; n += 1
    return {"n": n, "roi": prof / n if n else 0.0}

def calib(sub):
    out = {}
    for name, cols in {**ARMS, "mercado": ("mktH", "mktD", "mktA")}.items():
        if name == "mercado":
            inv = 1 / sub[["AvgCH", "AvgCD", "AvgCA"]].values
            p = inv / inv.sum(axis=1, keepdims=True)
        else:
            p = sub[[cols[0], cols[1], cols[2]]].values
        y = np.zeros_like(p)
        mp = {"H": 0, "D": 1, "A": 2}
        for i, ftr in enumerate(sub.FTR.values):
            y[i, mp[ftr]] = 1
        mask = ~np.isnan(p).any(axis=1)
        p, y = p[mask], y[mask]
        ll = float(-np.mean(np.sum(y * np.log(np.clip(p, 1e-9, 1)), axis=1)))
        br = float(np.mean(np.sum((p - y) ** 2, axis=1)))
        out[name] = {"logloss": ll, "brier": br, "n": int(mask.sum())}
    return out

results = {"thresholds": {}, "arms": {}}
dval = df[df.temp.isin(VAL)].sort_values("date")
dtest = df[df.temp.isin(TEST)].sort_values("date")

for arm in ARMS:
    # 1. elegir umbral en validación
    best, best_m = 1.05, None
    for thr in THRESHOLDS:
        b = simulate(dval, arm, thr); m = metrics(b)
        key = (m["roi"] if m["n"] >= 50 else -9, m["n"])
        if best_m is None or key > (best_m["roi"] if best_m["n"] >= 50 else -9, best_m["n"]):
            best, best_m = thr, m
    if best_m["n"] < 50:
        best = 1.05
        best_m = metrics(simulate(dval, arm, best))
    results["thresholds"][arm] = {"umbral": best, "val_n": best_m["n"],
                                  "val_roi": best_m["roi"], "val_clv": best_m["clv"]}
    # 2. aplicar al test
    b = simulate(dtest, arm, best)
    m = metrics(b)
    per_liga = {l: metrics(g) for l, g in b.groupby("liga")} if len(b) else {}
    per_temp = {t: int((b.temp == t).sum()) for t in sorted(TEST)} if len(b) else {}
    nf = no_filter_roi(dtest, arm)
    pasa = (m["roi"] > 0.02 and m["n"] >= 200 and m["clv"] >= 0.55)
    results["arms"][arm] = {
        "umbral_usado": best, "test": m,
        "por_liga": {l: {"n": v["n"], "roi": v["roi"], "clv": v["clv"]} for l, v in per_liga.items()},
        "n_por_temporada": per_temp,
        "sin_filtro": nf,
        "pasa_criterio": bool(pasa),
    }
    print(f"[{arm}] umbral={best} val: n={best_m['n']} roi={best_m['roi']:.4f} | "
          f"test: n={m['n']} roi={m['roi']:.4f} clv={m['clv']:.3f} dd={m['max_drawdown']:.1f} "
          f"-> {'PASS' if pasa else 'FAIL'}", flush=True)

results["calibracion_test"] = calib(dtest)
results["pass_global"] = bool(any(v["pasa_criterio"] for v in results["arms"].values()))
with open(os.path.join(LAB, "results.json"), "w") as f:
    json.dump(results, f, indent=1)
print("PASS GLOBAL:", results["pass_global"], flush=True)
print("results.json guardado", flush=True)
