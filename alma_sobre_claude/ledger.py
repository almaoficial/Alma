# -*- coding: utf-8 -*-
"""Ledger del programa «ALMA sobre Muse» con cadena de hashes.

Archivo: ~/workspace/alma-prototype/alma-sobre-claude-ledger.jsonl
Cada evento: {ts, tipo, datos, prev, hash} con
hash = sha256(prev + '|' + json({ts,tipo,datos})). Uso:
  python3 ledger.py asentar <tipo> <json_datos>
  python3 ledger.py verificar
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(os.path.dirname(AQUI), "alma-sobre-claude-ledger.jsonl")


def _hash(prev, cuerpo):
    return hashlib.sha256(
        (prev + "|" + json.dumps(cuerpo, ensure_ascii=False,
                                 sort_keys=True)).encode("utf-8")).hexdigest()


def eventos():
    if not os.path.exists(LEDGER):
        return []
    with open(LEDGER, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def asentar(tipo, datos):
    evs = eventos()
    prev = evs[-1]["hash"] if evs else "GENESIS"
    cuerpo = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "tipo": tipo, "datos": datos}
    ev = {**cuerpo, "prev": prev, "hash": _hash(prev, cuerpo)}
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return ev


def verificar():
    prev = "GENESIS"
    for ev in eventos():
        cuerpo = {"ts": ev["ts"], "tipo": ev["tipo"], "datos": ev["datos"]}
        if ev["prev"] != prev or ev["hash"] != _hash(prev, cuerpo):
            return False
        prev = ev["hash"]
    return True


if __name__ == "__main__":
    if sys.argv[1] == "asentar":
        ev = asentar(sys.argv[2], json.loads(sys.argv[3]))
        print(ev["hash"])
    elif sys.argv[1] == "verificar":
        print("cadena íntegra" if verificar() else "CADENA ROTA")
