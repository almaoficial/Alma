#!/usr/bin/env python3
"""Fase 2.1 (Yao c): las 4 reglas ACI como checklist de herramientas.

Checks: resumir (1), editar_con_guardrails (2), resultado/sin_resultados
(3), curar_contexto (4).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alma_service.aci import (  # noqa: E402
    resumir, editar_con_guardrails, resultado, sin_resultados,
    curar_contexto, MARCA_RECORTE)

CHECKS = []


def check(nombre, cond):
    CHECKS.append((nombre, bool(cond)))
    print(("PASS " if cond else "FAIL ") + nombre)


# Regla 1: suprimir verbosidad.
check("resumir deja lo corto intacto", resumir("abc", tope=10) == "abc")
largo = resumir("x" * 3000, tope=2000)
check("resumir recorta con marca",
      len(largo) < 3000 and MARCA_RECORTE in largo)

# Regla 2: guardrails en edición.
d = "/tmp/alma_aci_test"
os.makedirs(d, exist_ok=True)
orig = os.path.join(d, "f.txt")
with open(orig, "w", encoding="utf-8") as fh:
    fh.write("original")


def valida_ok(tmp):
    return True, "bien"


def valida_no(tmp):
    with open(tmp, encoding="utf-8") as fh:
        contenido = fh.read()
    return ("MALO" not in contenido,
            "contiene MALO" if "MALO" in contenido else "ok")


r = editar_con_guardrails(orig, "nuevo contenido", valida_ok)
check("edicion valida escribe",
      r["ok"] and open(orig, encoding="utf-8").read() == "nuevo contenido")
r = editar_con_guardrails(orig, "contenido MALO", valida_no)
check("edicion invalida no toca el original",
      not r["ok"] and open(orig, encoding="utf-8").read()
      == "nuevo contenido")


def valida_explota(tmp):
    raise RuntimeError("boom")


r = editar_con_guardrails(orig, "otro", valida_explota)
check("excepcion en validador reporta sin romper",
      not r["ok"] and "boom" in r["motivo"])

# Regla 3: feedback explícito.
r = resultado(True, "todo bien", n=3)
check("resultado con forma", r["ok"] and r["resumen"] == "todo bien"
      and r["n"] == 3)
r = sin_resultados("evidencia")
check("sin_resultados nunca es silencio",
      r["ok"] and "sin evidencia" in r["resumen"] and r["n"] == 0)

# Regla 4: curación de contexto.
items = ([{"tipo": "error", "texto": f"error {i}"} for i in range(5)]
         + [{"tipo": "obs", "texto": f"obs {i}"} for i in range(30)])
cur = curar_contexto(items, max_items=20)
errores = [it for it in cur if it["tipo"] == "error"]
colapsos = [it for it in cur if it["tipo"] == "colapso"]
obs = [it for it in cur if it["tipo"] == "obs"]
check("curar conserva solo el primer error",
      len(errores) == 1 and errores[0]["texto"] == "error 0")
check("curar colapsa obs viejas",
      len(colapsos) == 1 and "10" in colapsos[0]["texto"]
      and len(obs) == 20)
check("curar deja intacto lo corto",
      curar_contexto([{"tipo": "obs", "texto": "x"}])
      == [{"tipo": "obs", "texto": "x"}])

n_fails = sum(1 for _, c in CHECKS if not c)
print(f"\n{len(CHECKS) - n_fails}/{len(CHECKS)} checks en verde")
sys.exit(1 if n_fails else 0)
