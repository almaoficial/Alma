#!/usr/bin/env python3
"""Fase 2.1 (Cherny e): loop de verificación con criterio de parada a priori.

Checks: declarar_criterio valida; rondas_fijas para en N; sin_mejora
para tras K planas; umbral_mejora para al alcanzar el umbral; el trail
audita cada paso.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alma_service.verificacion import (  # noqa: E402
    LoopVerificacion, declarar_criterio)

CHECKS = []


def check(nombre, cond):
    CHECKS.append((nombre, bool(cond)))
    print(("PASS " if cond else "FAIL ") + nombre)


# 1. Sin criterio declarado no hay loop.
for mala in (lambda: declarar_criterio("magia"),
             lambda: declarar_criterio("rondas_fijas"),
             lambda: declarar_criterio("rondas_fijas", n=-1),
             lambda: declarar_criterio("sin_mejora", k=3),
             lambda: declarar_criterio("umbral_mejora", umbral=0,
                                       max_rondas=10)):
    try:
        mala()
        check("criterio invalido rechazado", False)
        break
    except ValueError:
        pass
else:
    check("criterio invalido rechazado", True)

c = declarar_criterio("rondas_fijas", n=5)
check("criterio valido declarado", c == {"tipo": "rondas_fijas", "n": 5})

# 2. rondas_fijas: exactamente N iteraciones, parada declarada.
estado = {"x": 0}


def prod():
    return {"v": estado["x"]}


def obs(p):
    return {"m": p["v"]}


def comp(p, o):
    return {"mejora": 0.0, "aceptar": False}


loop = LoopVerificacion(declarar_criterio("rondas_fijas", n=4))
res = loop.correr(prod, obs, comp)
check("rondas_fijas para en N",
      res["iteraciones"] == 4 and res["parado_por"] == "rondas_fijas n=4"
      and len(res["trail"]) == 4)

# 3. sin_mejora: para tras K iteraciones planas.
mejoras = [1.0, 0.0, 0.0, 0.0, 5.0]
it = {"i": 0}


def comp2(p, o):
    m = mejoras[it["i"]]
    it["i"] += 1
    return {"mejora": m, "aceptar": m > 0}


loop = LoopVerificacion(declarar_criterio("sin_mejora", k=3,
                                         max_rondas=100))
res = loop.correr(prod, obs, comp2)
check("sin_mejora para tras K planas",
      res["iteraciones"] == 4 and res["parado_por"] == "sin_mejora k=3")

# 4. umbral_mejora: para al alcanzar el umbral.
it["i"] = 0
loop = LoopVerificacion(declarar_criterio("umbral_mejora", umbral=2.0,
                                         max_rondas=100))
res = loop.correr(prod, obs, comp2)
check("umbral_mejora para al umbral",
      res["parado_por"] == "umbral_mejora 2.0")

# 5. El trail audita mejora y aceptación por paso.
check("trail con mejora por paso",
      [p["mejora"] for p in res["trail"]] == [1.0, 0.0, 0.0, 0.0, 5.0]
      and [p["aceptado"] for p in res["trail"]]
      == [True, False, False, False, True])

# 6. on_paso recibe prop/obs/comp (side effects del harness).
vistos = []
loop = LoopVerificacion(declarar_criterio("rondas_fijas", n=2))
loop.correr(prod, obs, comp,
            on_paso=lambda pr, ob, co, pa: vistos.append(pa["iter"]))
check("on_paso corre por iteracion", vistos == [1, 2])

n_fails = sum(1 for _, c in CHECKS if not c)
print(f"\n{len(CHECKS) - n_fails}/{len(CHECKS)} checks en verde")
sys.exit(1 if n_fails else 0)
