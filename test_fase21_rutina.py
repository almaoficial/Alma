#!/usr/bin/env python3
"""Fase 2.1 (Cherny f): el meta-loop corre como ROUTINE — memoria
compartida, contexto NO compartido.

Checks: cada corrida reconstruye el minero desde el ledger (lo inyectado
in-memory no cruza corridas); el pre-registro lleva el criterio de
parada declarado a priori.
"""

import glob
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alma_service.metaloop import MetaLoop  # noqa: E402

CHECKS = []


def check(nombre, cond):
    CHECKS.append((nombre, bool(cond)))
    print(("PASS " if cond else "FAIL ") + nombre)


d = tempfile.mkdtemp(prefix="alma_rutina_")
ml = MetaLoop(db_path=os.path.join(d, "meta.db"))

# Inyecto estado in-memory que NO está en el ledger (simula contexto de
# una corrida anterior que no debería cruzar).
ml.minero.alimentar(("fantasma", "no-en-ledger"))
check("minero in-memory tiene la firma fantasma",
      ml.minero.estado()["total_firmas"] >= 1)

# Una corrida corta reconstruye el minero desde el ledger al inicio.
ml.correr(seed=7, rondas=1, bloqueante=True)
check("corrida termina",
      ml._estado["fase"] == "inactivo")
firmas = [k for k in ml.minero._conteo]
check("contexto in-memory no cruza corridas",
      not any("fantasma" in str(k) for k in firmas)
      and ml.minero.estado()["total_firmas"] == 1)

# El pre-registro lleva el criterio de parada declarado a priori.
preregs = glob.glob(os.path.join(d, "metaloop_preregistro_*.json"))
check("pre-registro escrito", len(preregs) >= 1)
pr = json.load(open(preregs[-1], encoding="utf-8"))
check("criterio de parada en pre-registro",
      pr.get("criterio_parada", {}).get("tipo") == "rondas_fijas"
      and pr["criterio_parada"].get("n") == 1)
check("ledger tiene corrida_finalizada",
      any("corrida_finalizada" in l for l in
          open(os.path.join(d, "metaloop_ledger.jsonl"),
               encoding="utf-8").read().splitlines()))

n_fails = sum(1 for _, c in CHECKS if not c)
print(f"\n{len(CHECKS) - n_fails}/{len(CHECKS)} checks en verde")
sys.exit(1 if n_fails else 0)
