#!/usr/bin/env python3
"""Descarga las ventanas de EXP42 desde la API publica de Kraken (sin key).

Ventanas PRE-REGISTRADAS (UTC):
  W1 BTC XBTUSD 2026-08-28 -> 2026-09-27 (ventana original, ancla)
  W2 BTC XBTUSD 2026-05-01 -> 2026-05-31
  W3 BTC XBTUSD 2026-01-15 -> 2026-02-14
  W4 ETH ETHUSD  2026-08-28 -> 2026-09-27
  W5 ETH ETHUSD  2026-04-01 -> 2026-05-01
  W6 SOL SOLUSD  2026-08-28 -> 2026-09-27

Por ventana: 720 velas horarias del stream + 168 velas previas de lookback
(para el ADX sin lookahead). Guarda data_exp42/<w>.json con ohlc completo.
"""
import json
import os
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data_exp42")
os.makedirs(OUT, exist_ok=True)

VENTANAS = [
    ("W1", "XBTUSD", "BTC", "2026-08-28T00:00:00", "2026-09-27T00:00:00"),
    ("W2", "XBTUSD", "BTC", "2026-05-01T00:00:00", "2026-05-31T00:00:00"),
    ("W3", "XBTUSD", "BTC", "2026-01-15T00:00:00", "2026-02-14T00:00:00"),
    ("W4", "ETHUSD", "ETH", "2026-08-28T00:00:00", "2026-09-27T00:00:00"),
    ("W5", "ETHUSD", "ETH", "2026-04-01T00:00:00", "2026-05-01T00:00:00"),
    ("W6", "SOLUSD", "SOL", "2026-08-28T00:00:00", "2026-09-27T00:00:00"),
]
LOOKBACK_H = 168
STREAM_H = 720


def ts(s):
    return int(time.mktime(time.strptime(s, "%Y-%m-%dT%H:%M:%S")))


def ohlc(pair, since):
    url = (f"https://api.kraken.com/0/public/OHLC?pair={pair}"
           f"&interval=60&since={since}")
    req = urllib.request.Request(url, headers={"User-Agent": "alma-exp42"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if d.get("error"):
        raise RuntimeError(f"Kraken error {pair}: {d['error']}")
    key = [k for k in d["result"] if k != "last"][0]
    return d["result"][key], d["result"]["last"]


def descargar(w, pair, t0):
    desde = t0 - LOOKBACK_H * 3600
    velas, last = ohlc(pair, desde)
    # Kraken devuelve hasta 720 por llamada; si faltan, segunda llamada
    while len(velas) < LOOKBACK_H + STREAM_H:
        velas2, last = ohlc(pair, int(velas[-1][0]) + 3600)
        if not velas2:
            break
        velas += velas2
        time.sleep(1)
    velas = [v for v in velas if int(v[0]) >= desde]
    velas = velas[:LOOKBACK_H + STREAM_H]
    if len(velas) < LOOKBACK_H + STREAM_H:
        raise RuntimeError(f"{w}: solo {len(velas)} velas")
    # verificar continuidad horaria
    for i in range(1, len(velas)):
        if int(velas[i][0]) - int(velas[i - 1][0]) != 3600:
            raise RuntimeError(f"{w}: hueco en vela {i}")
    return velas


def main():
    ok, fallidas = [], []
    for w, pair, asset, s0, s1 in VENTANAS:
        t0 = ts(s0)
        try:
            velas = descargar(w, pair, t0)
            d = {
                "ventana": w, "pair": pair, "asset": asset,
                "inicio": s0, "fin": s1,
                "t": [int(v[0]) for v in velas],
                "open": [float(v[1]) for v in velas],
                "high": [float(v[2]) for v in velas],
                "low": [float(v[3]) for v in velas],
                "close": [float(v[4]) for v in velas],
            }
            # el stream arranca en t0: las primeras LOOKBACK_H son lookback
            assert d["t"][LOOKBACK_H] == t0, f"{w}: desalineado"
            json.dump(d, open(os.path.join(OUT, f"{w}.json"), "w"))
            print(f"{w} {asset} {s0}: OK ({len(velas)} velas)")
            ok.append(w)
        except Exception as e:
            print(f"{w} {asset} {s0}: FALLA ({e})")
            fallidas.append((w, str(e)))
        time.sleep(2)
    print(f"\nOK: {ok}")
    print(f"FALLIDAS: {fallidas if fallidas else 'ninguna'}")
    return 0 if not fallidas else 1


if __name__ == "__main__":
    raise SystemExit(main())
