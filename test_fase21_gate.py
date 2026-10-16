"""Tests fase 2.1: puerta de dos splits (Self-Harness §3.4).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase21_gate.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.gate import (
    PuertaDosSplits, aceptar, audit_record, REGLA)

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def main():
    # 1. La regla: sin regresión en ningún split, mejora estricta en ≥1.
    ok, _ = aceptar(0.0, 0.5)
    check("acepta: mejora solo en held-out", ok is True)
    ok, _ = aceptar(0.5, 0.0)
    check("acepta: mejora solo en train", ok is True)
    ok, _ = aceptar(0.3, 0.2)
    check("acepta: mejora en ambos", ok is True)

    # 2. Trade-offs rechazados aunque el total suba (núcleo del paper).
    ok, motivo = aceptar(-0.1, 0.9)
    check("rechaza: regresión en train aunque held-out mejore mucho",
          ok is False and "regresión" in motivo)
    ok, motivo = aceptar(0.9, -0.1)
    check("rechaza: regresión en held-out aunque train mejore",
          ok is False and "regresión" in motivo)

    # 3. Sin mejora estricta no hay adopción.
    ok, _ = aceptar(0.0, 0.0)
    check("rechaza: deltas cero", ok is False)

    # 4. PuertaDosSplits.decidir con métricas (regret: menor es mejor).
    d = PuertaDosSplits.decidir(5.0, 6.0, 4.0, 5.5)
    check("decidir acepta (d_in=1.0, d_ho=0.5)",
          d["aceptado"] is True and d["delta_in"] == 1.0
          and d["delta_ho"] == 0.5 and d["regla"] == REGLA)
    d = PuertaDosSplits.decidir(5.0, 6.0, 5.2, 5.5)
    check("decidir rechaza regresión en train", d["aceptado"] is False)

    # 5. Audit record: estructura completa (Self-Harness §3.3).
    ar = audit_record(
        propuesta={"clave": "n0", "anterior": 2, "nuevo": 4},
        delta_in=0.3, delta_ho=0.1, aceptado=True, motivo="ok",
        debilidad={"firma": ["n0", "sube", "revert"], "n": 5},
        superficie="scaffold:n0", efecto_esperado="bajar regret",
        riesgo_regresion="ninguno medido")
    check("audit record trae tipo/regla/veredicto",
          ar["tipo"] == "audit_propuesta" and ar["regla"] == REGLA
          and ar["aceptado"] is True
          and ar["debilidad_objetivo"]["n"] == 5)

    # 6. delta_ho=None permitido en propuestas de ronda.
    ar2 = audit_record(propuesta={"clave": "n0"}, delta_in=0.2,
                       delta_ho=None, aceptado=False, motivo="revert")
    check("audit de ronda admite delta_ho=None", ar2["delta_ho"] is None)

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
