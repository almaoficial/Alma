#!/usr/bin/env python3
"""Descarga las 6 ventanas de EXP42 desde Coinbase Exchange publico.

Kraken quedo descartado: ignora `since` y devuelve solo las ~720 velas
mas recientes (verificado 2026-09-27), insuficiente para 888 velas
alineadas (168 lookback + 720 stream). Coinbase candles acepta start/end
explicitos. Sin key, US$0.

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

# (ventana, producto coinbase, asset, inicio_utc, fin_utc)
VENTANAS = [
    ("W1", "BTC-USD", "BTC", "2026-08-28T00:00:00", "2026-09-27T00:00:00"),
    ("W2", "BTC-USD", "BTC", "2026-05-01T00:00:00", "2026-05-31T00:00:00"),
    ("W3", "BTC-USD", "BTC", "2026-01-15T00:00:00", "2026-02-14T00:00:00"),
    ("W4", "ETH-USD", "ETH", "2026-08-28T00:00:00", "2026-09-27T00:00:00"),
    ("W5", "ETH-USD", "ETH", "2026-04-01T00:00:00", "2026-05-01T00:00:00"),
    ("W6", "SOL-USD", "SOL", "2026-08-28T00:00:00", "2026-09-27T00:00:00"),
]


def t_utc(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%S"))


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "alma-exp42"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def descargar(product, desde, hasta):
    # tramos de 10 dias (240 velas < limite 300 por llamada)
    por_ts = {}
    ini = desde
    while ini < hasta:
        fin = min(ini + 10 * 86400, hasta)
        s_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ini))
        e_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(fin))
        d = get_json(f"https://api.exchange.coinbase.com/products/{product}"
                     f"/candles?start={s_iso}&end={e_iso}&granularity=3600")
        if not isinstance(d, list):
            raise RuntimeError(f"Coinbase error {product}: {d}")
        # [time, low, high, open, close, volume]; dedupe por timestamp
        for c in d:
            ts = int(c[0])
            por_ts[ts] = (ts, float(c[3]), float(c[2]), float(c[1]), float(c[4]))
        time.sleep(0.4)
        ini = fin
    velas = [por_ts[ts] for ts in sorted(por_ts) if desde <= ts < hasta]
    return velas


def main():
    ok, fallidas = [], []
    for w, product, asset, s0, s1 in VENTANAS:
        t0, t1 = t_utc(s0), t_utc(s1)
        desde = t0 - LOOKBACK_H * 3600
        try:
            velas = descargar(product, desde, t1)
            if len(velas) != TOTAL:
                raise RuntimeError(
                    f"{len(velas)} velas (esperadas {TOTAL}) en rango")
            for i in range(1, len(velas)):
                if velas[i][0] - velas[i - 1][0] != 3600:
                    raise RuntimeError(f"hueco en vela {i}")
            if velas[LOOKBACK_H][0] != t0:
                raise RuntimeError("desalineado con t0")
            d = {"ventana": w, "fuente": "coinbase", "par": product,
                 "asset": asset, "inicio": s0, "fin": s1,
                 "t": [v[0] for v in velas],
                 "open": [v[1] for v in velas],
                 "high": [v[2] for v in velas],
                 "low": [v[3] for v in velas],
                 "close": [v[4] for v in velas]}
            json.dump(d, open(os.path.join(OUT, f"{w}.json"), "w"))
            print(f"{w} {asset} coinbase: OK ({len(velas)} velas)", flush=True)
            ok.append(w)
        except Exception as e:
            print(f"{w} {asset} coinbase: FALLA ({e})", flush=True)
            fallidas.append((w, str(e)))
        time.sleep(1)
    print(f"\nOK: {ok}")
    print(f"FALLIDAS: {fallidas if fallidas else 'ninguna'}")
    return 0 if not fallidas else 1


if __name__ == "__main__":
    raise SystemExit(main())
