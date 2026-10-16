"""Tests fase 0: detector de recurrencia (compuerta del sistema).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase0_recurrencia.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.recurrencia import DetectorRecurrencia

PASSOS = []


def check(nombre, cond):
    PASSOS.append(cond)
    print(("PASS" if cond else "FAIL"), "-", nombre)


def test_mundo_recurrencia_alta():
    # 3 firmas rotando: todo recurre → modo skills
    d = DetectorRecurrencia(ventana=20, umbral=0.30)
    for i in range(30):
        d.observar(f"firma-{i % 3}")
    check("recurrencia alta ≈ 1.0", d.tasa_recurrencia() > 0.9)
    check("modo skills", d.modo() == "skills")


def test_mundo_sin_recurrencia():
    # feed real de EXP44: todo distinto → modo adaptativo
    d = DetectorRecurrencia(ventana=20, umbral=0.30)
    for i in range(30):
        d.observar(f"categoria-unica-{i}")
    check("recurrencia ≈ 0.0", d.tasa_recurrencia() < 0.01)
    check("modo adaptativo (no invierte en skills)", d.modo() == "adaptativo")


def test_borde_y_ventana():
    d = DetectorRecurrencia(ventana=10, umbral=0.30)
    check("sin datos → tasa 0", d.tasa_recurrencia() == 0.0)
    check("sin datos → adaptativo", d.modo() == "adaptativo")
    # exactamente 3 de 10 recurren (0.30 >= umbral): 6 únicas + 4 "repite"
    # (la primera ocurrencia de "repite" es nueva; las 3 siguientes recurren)
    for i in range(6):
        d.observar(f"unica-{i}")
    for i in range(4):
        d.observar("repite")
    t = d.tasa_recurrencia()
    check("borde 0.30 → skills", abs(t - 0.30) < 1e-9
          and d.modo() == "skills")
    # ventana deslizante: lo viejo sale
    d2 = DetectorRecurrencia(ventana=5, umbral=0.30)
    for i in range(20):
        d2.observar("misma")
    for i in range(5):
        d2.observar(f"nueva-{i}")
    check("ventana olvida lo viejo", d2.modo() == "adaptativo")
    try:
        DetectorRecurrencia(ventana=0)
        check("ventana 0 inválida", False)
    except ValueError:
        check("ventana 0 inválida", True)


if __name__ == "__main__":
    test_mundo_recurrencia_alta()
    test_mundo_sin_recurrencia()
    test_borde_y_ventana()
    sys.exit(0 if all(PASSOS) else 1)
