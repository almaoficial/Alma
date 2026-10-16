"""Tests evaluador barato — idea 1 de la revisión nocturna 7/10.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 alma_service/test_evaluador_barato.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alma_service.evaluador_barato import (
    EvaluadorBarato, medir, no_vacia, dentro_de_cota, formato_esperado,
)
from alma_service.ruteo import modelo_escalado, TIER_CARO


def check(nombre, cond):
    print(("PASS" if cond else "FAIL") + " - " + nombre)
    if not cond:
        raise AssertionError(nombre)


# -- verificadores sueltos ----------------------------------------------------
check("vacía reprueba", no_vacia("   ") is False)
check("no vacía aprueba", no_vacia("hola") is True)
check("no string reprueba", no_vacia(None) is False)
check("cota atrapa desborde", dentro_de_cota("x" * 20001) is False)
check("cota respeta config", dentro_de_cota("abc", min_chars=5) is False)
check("json válido aprueba", formato_esperado('{"a": 1}', "json") is True)
check("json roto reprueba", formato_esperado("{a: 1}", "json") is False)
check("sin formato no asume nada", formato_esperado("cualquier cosa") is True)

# -- el evaluador ---------------------------------------------------------------
ev = EvaluadorBarato()
check("salida normal aprueba", ev("una respuesta razonable") is True)
check("salida vacía reprueba", ev("  ") is False)
check("salida gigante reprueba", ev("x" * 20001) is False)

ev_json = EvaluadorBarato(formato="json")
check("json pedido y válido aprueba", ev_json('{"ok": true}') is True)
check("json pedido y roto reprueba", ev_json("no es json") is False)

# -- juez con modelo (opt-in) ----------------------------------------------------
def juez_exigente(salida, contexto=None):
    return "excelente" in salida

ev_juez = EvaluadorBarato(juez=juez_exigente)
check("juez aprueba lo bueno", ev_juez("un trabajo excelente") is True)
check("juez reprueba lo mediocre", ev_juez("un trabajo normal") is False)
check("juez no se consulta si lo determinista falla",
      ev_juez("   ") is False and ev_juez.rechazos["juez"] == 1)

def juez_roto(salida, contexto=None):
    raise RuntimeError("caído")

ev_roto = EvaluadorBarato(juez=juez_roto)
check("juez roto se abstiene: vale lo determinista",
      ev_roto("salida válida") is True)

# -- enchufe con ruteo -------------------------------------------------------------
check("integra con ruteo: salida mala escala",
      modelo_escalado(None, "   ", EvaluadorBarato()) == TIER_CARO)
check("integra con ruteo: salida buena no escala",
      modelo_escalado(None, "respuesta válida", EvaluadorBarato()) is None)

# -- medición del evaluador ----------------------------------------------------------
pares = [
    ("respuesta completa y útil", True),
    ("   ", False),
    ("x" * 20001, False),
    ("otra respuesta válida", True),
]
m = medir(EvaluadorBarato(), pares)
check("medir: acuerdo perfecto en set trivial",
      m["acuerdo"] == 1.0 and m["falsos_rechazos"] == 0)

pares2 = [("respuesta válida", True), ("también válida", True)]
m2 = medir(EvaluadorBarato(juez=juez_exigente), pares2)
check("medir: cuenta falsos rechazos del juez",
      m2["falsos_rechazos"] == 2 and m2["tasa_falso_rechazo"] == 1.0)

r = ev.resumen()
check("resumen cuenta evaluadas", r["evaluadas"] == 3)

print("\n24/24 checks en verde")
