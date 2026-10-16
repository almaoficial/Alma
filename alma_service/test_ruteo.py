"""Tests ruteo por tier — paso 3 del protocolo anti-quema.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 alma_service/test_ruteo.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alma_service.ruteo import (
    elegir_modelo, necesita_escalado, modelo_escalado,
    TIER_BARATO, TIER_CARO, TIERS,
)
from alma.backends import PRECIOS


def check(nombre, cond):
    print(("PASS" if cond else "FAIL") + " - " + nombre)
    if not cond:
        raise AssertionError(nombre)


def aprueba(_salida):
    return True


def reprueba(_salida):
    return False


def evaluador_roto(_salida):
    raise RuntimeError("boom")


check("default es tier barato", elegir_modelo() == TIER_BARATO)
check("forzar pinea el modelo", elegir_modelo(forzar="gpt-4o") == "gpt-4o")
check("forzar None no pinea", elegir_modelo(forzar=None) == TIER_BARATO)
check("tarea futura no cambia el default",
      elegir_modelo(tarea={"clase": "codigo"}) == TIER_BARATO)

check("evaluador que aprueba no escala",
      necesita_escalado("salida", aprueba) is False)
check("evaluador que reprueba escala",
      necesita_escalado("salida", reprueba) is True)
check("sin evaluador no se escala (fail-closed)",
      necesita_escalado("salida", None) is False)
check("evaluador roto no autoriza gasto",
      necesita_escalado("salida", evaluador_roto) is False)

check("escalado devuelve tier caro cuando reprueba",
      modelo_escalado(None, "salida", reprueba) == TIER_CARO)
check("escalado devuelve None cuando aprueba",
      modelo_escalado(None, "salida", aprueba) is None)
check("escalado devuelve None sin evaluador",
      modelo_escalado(None, "salida", None) is None)

check("tiers tienen precio tabulado",
      TIERS["barato"]["precio_in"] == PRECIOS[TIER_BARATO][0]
      and TIERS["caro"]["precio_out"] == PRECIOS[TIER_CARO][1])
check("el caro sale mas de 10x el barato por token in",
      TIERS["caro"]["precio_in"] > 10 * TIERS["barato"]["precio_in"])

print("\n13/13 checks en verde")
