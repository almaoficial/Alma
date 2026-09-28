#!/usr/bin/env python3
"""Generador de datos SINTÉTICOS para validar el pipeline de EXP44.

NO son datos reales. Su única función es verificar que run_experiment44.py
corre de punta a punta. Ningún número que salga de acá es un veredicto.
"""
import json
import os
import random

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data_exp44", "feed_units.json")

# (bloque -> distribución de categorías): rotación de intereses sintética
PLAN = {
    0: ["tecnologia"] * 7 + ["ciencia"] * 3,
    1: ["tecnologia"] * 6 + ["ciencia"] * 4,
    2: ["deportes"] * 7 + ["cultura"] * 3,
    3: ["deportes"] * 6 + ["cultura"] * 4,
    4: ["politica"] * 6 + ["economia"] * 4,
    5: ["economia"] * 6 + ["politica"] * 4,
}

rng = random.Random(44)
units = []
uid = 0
for b in range(6):
    cats = PLAN[b][:]
    rng.shuffle(cats)
    for i, c in enumerate(cats):
        units.append({
            "id": f"smoke-{uid}",
            "_SINTETICO": True,
            "published_at": f"2026-09-{10 + b:02d}T{8 + i:02d}:00:00",
            "title": f"Titular sintético {uid} sobre {c}",
            "text": f"Cuerpo sintético {uid}.",
            "category": c,
        })
        uid += 1

json.dump(units, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(f"SMOKE: {len(units)} unidades SINTÉTICAS -> {OUT}")
print("Recordatorio: esto NO es el stream real. Reemplazar con la exportación "
      "del feed antes del run real.")
