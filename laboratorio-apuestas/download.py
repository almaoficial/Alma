#!/usr/bin/env python3
"""Descarga los 30 CSVs de football-data.co.uk con pausas respetuosas."""
import os, time, urllib.request

BASE = "https://www.football-data.co.uk/mmz4281"
SEASONS = ["1920", "2021", "2122", "2223", "2324", "2425"]
LEAGUES = ["E0", "SP1", "I1", "D1", "F1"]
OUT = os.path.expanduser("~/workspace/alma-prototype/laboratorio-apuestas/data")
os.makedirs(OUT, exist_ok=True)

ok, fail = 0, []
for s in SEASONS:
    for l in LEAGUES:
        url = f"{BASE}/{s}/{l}.csv"
        dst = os.path.join(OUT, f"{l}_{s}.csv")
        if os.path.exists(dst) and os.path.getsize(dst) > 5000:
            print(f"skip {l}_{s} (ya existe)")
            ok += 1
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ALMA-research-personal/1.0 (uso privado)"})
            with urllib.request.urlopen(req, timeout=30) as r, open(dst, "wb") as f:
                f.write(r.read())
            print(f"ok {l}_{s} ({os.path.getsize(dst)} bytes)")
            ok += 1
        except Exception as e:
            print(f"FAIL {l}_{s}: {e}")
            fail.append((s, l, str(e)))
        time.sleep(2)  # pausa respetuosa

print(f"\nDescargados/ok: {ok}/30, fallos: {len(fail)}")
for s, l, e in fail:
    print(" -", s, l, e)
