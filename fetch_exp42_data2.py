#!/usr/bin/env python3
"""Descarga las 6 ventanas de EXP42 (888 velas c/u: 168 lookback + 720 stream).

Fuentes publicas, sin key, US$0:
  - W1/W4/W6 (periodo reciente 2026-08-28->2026-09-27): Kraken OHLC.
  - W2/W3/W5 (periodos viejos; Kraken ignora `since` y devuelve solo velas
    recientes): Coinbase Exchange candles (limite 300/llamada, en tramos).
Guarda data_exp42/<w>.json con esquema uniforme + campo "fuente".
"""
import calendar
import json
import os
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data_exp42")
os.makedirs(OUT, exist_ok=True)

LOOKBACK_H = 168
STREAM_H = 720
TOTAL = LOOKBACK_H + STREAM_H

# (ventana, fuente, par/producto, asset, inicio_utc, fin_utc)
VENTANAS = [
    ("W1", "kraken",   "XBTUSD",  "BTC", "2026-08-28T00:00:00", "2026-09-27T00:00:00"),
    ("W2", "coinbase", "BTC-USD", "BTC", "2026-05-01T00:00:00", "2026-05-31T00:00:00"),
    ("W3", "coinbase", "BTC-USD", "BTC", "2026-01-15T00:00:00", "2026-02-14T00:00:00"),
    ("W4", "kraken",   "ETHUSD",  "ETH", "2026-08-28T00:00:00", "2026-09-27T00:00:00"),
    ("W5", "coinbase", "ETH-USD", "ETH", "2026-04-01T00:00:00", "2026-05-01T00:00:00"),
    ("W6", "kraken",   "SOLUSD",  "SOL", "2026-08-28T00:00:00", "2026-09-27T00:00:00"),
]


def t_utc(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%S"))


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "alma-exp42"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def kraken(pair, desde):
    velas, since = [], desde
    while len(velas) < TOTAL:
        d = get_json(f"https://api.kraken.com/0/public/OHLC?pair={pair}"
                     f"&interval=60&since={since}")
        if d.get("error"):
            raise RuntimeError(f"Kraken error {pair}: {d['error']}")
        key = [k for k in d["result"] if k != "last"][0]
        lote = d["result"][key]
        if not lote:
            break
        # filtrar duplicados por timestamp
        vistos = {int(v[0]) for v in velas}
        lote = [v for v in lote if int(v[0]) not in vistos]
        if not lote:
            break
        velas += lote
        since = int(lote[-1][0]) + 3600
        time.sleep(1)
    velas.sort(key=lambda v: int(v[0]))
    return [(int(v[0]), float(v[1]), float(v[2]), float(v[3]), float(v[4]))
            for v in velas]


def coinbase(product, desde, hasta):
    # tramos de 10 dias (240 velas < limite 300)
    velas = []
    ini = desde
    while ini < hasta:
        fin = min(ini + 10 * 86400, hasta)
        s_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ini))
        e_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(fin))
        d = get_json(f"https://api.exchange.coinbase.com/products/{product}"
                     f"/candles?start={s_iso}&end={e_iso}&granularity=3600")
        if not isinstance(d, list):
            raise RuntimeError(f"Coinbase error {product}: {d}")
        # [time, low, high, open, close, volume], mas nuevas primero
        for c in d:
            velas.append((int(c[0]), float(c[3]), float(c[2]),
                          float(c[1]), float(c[4])))
        time.sleep(0.5)
        ini = fin
    velas.sort()
    return velas


def main():
    ok, fallidas = [], []
    for w, fuente, par, asset, s0, s1 in VENTANAS:
        t0, t1 = t_utc(s0), t_utc(s1)
        desde = t0 - LOOKBACK_H * 3600
        try:
            if fuente == "kraken":
                velas = kraken(par, desde)
            else:
                velas = coinbase(par, desde, t1)
            velas = [v for v in velas if desde <= v[0] < t1]
            if len(velas) != TOTAL:
                raise RuntimeError(f"solo {len(velas)} velas (esperadas {TOTAL})")
            for i in range(1, len(velas)):
                if velas[i][0] - velas[i - 1][0] != 3600:
                    raise RuntimeError(f"hueco en vela {i}")
            if velas[LOOKBACK_H][0] != t0:
                raise RuntimeError(f"desalineado: t[{LOOKBACK_H}]={velas[LOOKBACK_H][0]} != {t0}")
            d = {"ventana": w, "fuente": fuente, "par": par, "asset": asset,
                 "inicio": s0, "fin": s1,
                 "t": [v[0] for v in velas],
                 "open": [v[1] for v in velas],
                 "high": [v[2] for v in velas],
                 "low": [v[3] for v in velas],
                 "close": [v[4] for v in velas]}
            json.dump(d, open(os.path.join(OUT, f"{w}.json"), "w"))
            print(f"{w} {asset} {fuente}: OK ({len(velas)} velas)", flush=True)
            ok.append(w)
        except Exception as e:
            print(f"{w} {asset} {fuente}: FALLA ({e})", flush=True)
            fallidas.append((w, str(e)))
        time.sleep(2)
    print(f"\nOK: {ok}")
    print(f"FALLIDAS: {fallidas if fallidas else 'ninguna'}")
    return 0 if not fallidas else 1


if __name__ == "__main__":
    raise SystemExit(main())
