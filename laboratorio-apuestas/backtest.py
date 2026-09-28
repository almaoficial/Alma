#!/usr/bin/env python3
"""Laboratorio de apuestas v1 — backtest walk-forward estricto.
Brazos: mercado devigged (baseline calibración), Elo simple, Dixon-Coles.
Ver PREREGISTRO.md (congelado antes de correr).
"""
import os, json, glob, math, warnings
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
import pandas as pd
from scipy.optimize import minimize

warnings.filterwarnings("ignore")
LAB = os.path.expanduser("~/workspace/alma-prototype/laboratorio-apuestas")
DATA = os.path.join(LAB, "data")
rng = np.random.default_rng(7)

# ---------------- 1. Carga ----------------
def load():
    frames = []
    for f in sorted(glob.glob(os.path.join(DATA, "*.csv"))):
        base = os.path.basename(f).replace(".csv", "")
        liga, temp = base.split("_")
        d = pd.read_csv(f, usecols=lambda c: c in (
            "Date","HomeTeam","AwayTeam","FTHG","FTAG","FTR",
            "MaxH","MaxD","MaxA","AvgH","AvgD","AvgA",
            "MaxCH","MaxCD","MaxCA","AvgCH","AvgCD","AvgCA",
            "PSCH","PSCD","PSCA","B365H","B365A"))
        d["liga"] = liga; d["temp"] = temp
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y")
    df = df.sort_values(["date"]).reset_index(drop=True)
    df["mid"] = np.arange(len(df))
    return df

df = load()
print(f"partidos: {len(df)}, ligas: {sorted(df.liga.unique())}, temps: {sorted(df.temp.unique())}",
      flush=True)
if os.environ.get("SMOKE") == "1":
    df = df[df.liga.isin(["E0", "D1"]) & df.temp.isin(["1920", "2021", "2122", "2223"])].copy()
    print(f"[SMOKE] partidos: {len(df)}", flush=True)

TRAIN = {"1920","2021","2122"}; VAL = {"2223"}; TEST = {"2324","2425"}
K_ELO, HFA = 20.0, 65.0
THRESHOLDS = [1.03, 1.05, 1.08, 1.10]

# ---------------- 2. Elo walk-forward (por liga, sin leakage intra-fecha) ----------------
def run_elo(df):
    elos = defaultdict(lambda: 1500.0)
    seen = defaultdict(set)          # liga -> equipos vistos
    final_prev = {}                  # (liga,temp) -> elo final por equipo
    ph, pd_, pa = {}, {}, {}
    # buckets de empate: tasa empírica por |diff| con pasado (ventana expansiva por liga)
    for temp in sorted(df.temp.unique()):
        dft = df[df.temp == temp].sort_values("date")
        # altas: equipos nuevos
        for liga in dft.liga.unique():
            cur = set(pd.concat([dft[dft.liga==liga].HomeTeam, dft[dft.liga==liga].AwayTeam]).unique())
            new = cur - seen[liga]
            for t in new:
                prev_temp = {"2021":"1920","2122":"2021","2223":"2122","2324":"2223","2425":"2324"}.get(temp)
                vals = []
                if prev_temp:
                    releg = [e for e in seen[liga] if e not in cur]
                    vals = [final_prev.get((liga,prev_temp),{}).get(e) for e in releg]
                    vals = [v for v in vals if v is not None]
                elos[(liga,t)] = float(np.mean(vals)) if vals else 1500.0
            seen[liga] |= cur
        for date, g in dft.groupby("date"):
            # predecir todo el día con estado < date
            for _, r in g.iterrows():
                liga = r.liga
                eh, ea = elos[(liga,r.HomeTeam)], elos[(liga,r.AwayTeam)]
                dh = eh + HFA - ea
                p_h = 1.0/(1.0+10.0**(-dh/400.0))
                # prob de empate: tasa empírica por bucket de |dh| con pasado de la liga
                past = df[(df.liga==liga)&(df.date<date)]
                if len(past) > 60:
                    ad = np.abs(past["_dh"].values) if "_dh" in past else None
                    # _dh se guarda abajo; fallback a tasa global
                    q = np.quantile(np.abs(ad if ad is not None else np.zeros(len(past))), [0.2,0.4,0.6,0.8])
                    b = int(np.digitize(abs(dh), q))
                    pb = past[np.digitize(np.abs(past["_dh"].values), q)==b]
                    p_d = (pb.FTR=="D").mean() if len(pb)>20 else (past.FTR=="D").mean()
                else:
                    p_d = 0.25
                p_a = max(0.0, 1.0-p_h-p_d); s = p_h+p_d+p_a
                ph[r.mid], pd_[r.mid], pa[r.mid] = p_h/s, p_d/s, p_a/s
                # guardar dh para buckets futuros (truco: lo anotamos en df)
            # actualizar con resultados del día
            for _, r in g.iterrows():
                liga = r.liga
                eh, ea = elos[(liga,r.HomeTeam)], elos[(liga,r.AwayTeam)]
                dh = eh + HFA - ea
                df.loc[df.mid==r.mid, "_dh"] = dh
                p_h = 1.0/(1.0+10.0**(-dh/400.0))
                s_h = 1.0 if r.FTR=="H" else (0.5 if r.FTR=="D" else 0.0)
                s_a = 1.0 - s_h
                elos[(liga,r.HomeTeam)] = eh + K_ELO*(s_h-p_h)
                elos[(liga,r.AwayTeam)] = ea + K_ELO*(s_a-(1.0-p_h))
        for liga in dft.liga.unique():
            final_prev[(liga,temp)] = {t: elos[(liga,t)] for t in seen[liga]}
    df["pH_elo"], df["pD_elo"], df["pA_elo"] = df.mid.map(ph), df.mid.map(pd_), df.mid.map(pa)
    return df

df = run_elo(df)
print("Elo OK", flush=True)

# ---------------- 3. Dixon-Coles walk-forward (reajuste mensual por liga) ----------------
def dc_negloglik(params, matches, teams):
    # params: [log_a_i..., log_d_i..., log_home_adv, rho]
    n = len(teams)
    la = params[:n] - params[:n].mean()
    ld = params[n:2*n] - params[n:2*n].mean()
    lha, rho = params[2*n], params[2*n+1]
    idx = {t:i for i,t in enumerate(teams)}
    ll = 0.0
    for h,a,gh,ga in matches:
        i,j = idx[h], idx[a]
        lam = math.exp(la[i]+ld[j]+lha); mu = math.exp(la[j]+ld[i])
        # Poisson bivariado independiente + corrección tau Dixon-Coles
        def pois(k,l): return math.exp(-l)*l**k/math.factorial(k)
        p = pois(gh,lam)*pois(ga,mu)
        tau=1.0
        if gh==0 and ga==0: tau=1-lam*mu*rho
        elif gh==0 and ga==1: tau=1+lam*rho
        elif gh==1 and ga==0: tau=1+mu*rho
        elif gh==1 and ga==1: tau=1-rho
        p *= max(tau,1e-9)
        ll += math.log(max(p,1e-12))
    return -ll

def fit_dc(matches, teams):
    n = len(teams)
    x0 = np.zeros(2*n+2); x0[2*n]=0.25
    bounds=[(-3,3)]*(2*n)+[(-1,1.5),(-0.25,0.25)]
    res = minimize(dc_negloglik, x0, args=(matches,teams), method="L-BFGS-B",
                   bounds=bounds, options={"maxiter":200})
    p=res.x; la=p[:n]-p[:n].mean(); ld=p[n:2*n]-p[n:2*n].mean()
    return {t:(la[i],ld[i]) for i,t in enumerate(teams)}, p[2*n], p[2*n+1]

def dc_probs(str_h, str_a, lha, rho, gmax=10):
    (lah,ldh),(laa,lda)=str_h,str_a
    lam=math.exp(lah+lda+lha); mu=math.exp(laa+ldh)
    def pois(k,l): return math.exp(-l)*l**k/math.factorial(k)
    pH=pD=pA=0.0
    for gh in range(gmax+1):
        for ga in range(gmax+1):
            p=pois(gh,lam)*pois(ga,mu); tau=1.0
            if gh==0 and ga==0: tau=1-lam*mu*rho
            elif gh==0 and ga==1: tau=1+lam*rho
            elif gh==1 and ga==0: tau=1+mu*rho
            elif gh==1 and ga==1: tau=1-rho
            p*=max(tau,1e-9)
            if gh>ga: pH+=p
            elif gh==ga: pD+=p
            else: pA+=p
    s=pH+pD+pA; return pH/s,pD/s,pA/s

def run_dc(df):
    ph,pd_,pa={},{},{}
    start = df[df.temp.isin(VAL|TEST)].date.min().replace(day=1)
    end = df.date.max()+timedelta(days=40)
    for liga in sorted(df.liga.unique()):
        dfl = df[df.liga==liga]
        teams_hist = sorted(set(dfl.HomeTeam)|set(dfl.AwayTeam))
        month = start
        while month < end:
            past = dfl[dfl.date<month]
            if len(past)>=200:
                teams = sorted(set(past.HomeTeam)|set(past.AwayTeam))
                matches=[(r.HomeTeam,r.AwayTeam,int(r.FTHG),int(r.FTAG))
                         for _,r in past.iterrows()]
                try:
                    strs,lha,rho = fit_dc(matches, teams)
                except Exception:
                    strs,lha,rho = ({t:(0,0) for t in teams},0.25,0.0)
                cur = dfl[(dfl.date>=month)&(dfl.date<month+timedelta(days=32))]
                for _,r in cur.iterrows():
                    sh=strs.get(r.HomeTeam,(0,0)); sa=strs.get(r.AwayTeam,(0,0))
                    h,d,a=dc_probs(sh,sa,lha,rho)
                    ph[r.mid],pd_[r.mid],pa[r.mid]=h,d,a
            month += timedelta(days=32)
    df["pH_dc"]=df.mid.map(ph); df["pD_dc"]=df.mid.map(pd_); df["pA_dc"]=df.mid.map(pa)
    return df

df = run_dc(df)
print("Dixon-Coles OK", flush=True)
df.to_pickle(os.path.join(LAB,"probs.pkl"))
print("probs.pkl guardado", flush=True)
