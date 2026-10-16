"""Tests fase 2.1: minería de debilidades por firmas exactas.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase21_debilidades.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.debilidades import (
    MineroDebilidades, firma_meta, firma_feedback)

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def main():
    # 1. Firma meta: dirección numérica determinista.
    check("firma_meta sube",
          firma_meta("n0", 2, 4, "keep") == ("n0", "sube", "keep"))
    check("firma_meta baja",
          firma_meta("n0", 4, 2, "revert") == ("n0", "baja", "revert"))
    check("firma_meta no numérica",
          firma_meta("modo", "a", "b", "keep") == ("modo", "otro", "keep"))

    # 2. Firma de feedback: tramo por umbral 0.5, sin LLM.
    check("firma_feedback fallo",
          firma_feedback("aritmetica", "cot", 0.2)
          == ("aritmetica", "cot", "fallo"))
    check("firma_feedback ok",
          firma_feedback("aritmetica", "cot", 0.8)
          == ("aritmetica", "cot", "ok"))
    check("firma_feedback sin reward no inventa",
          firma_feedback("x", "y", None)[2] == "desconocido")

    # 3. Clustering por coincidencia exacta, ordenado por soporte.
    m = MineroDebilidades()
    firmas = [("n0", "sube", "revert")] * 5 + \
             [("n0", "baja", "keep")] * 3 + \
             [("umbral_base", "baja", "keep")]
    m.alimentar_varias(firmas)
    cs = m.clusters(n=5, minimo_soporte=2)
    check("clusters ordenados por soporte",
          cs[0]["firma"] == ["n0", "sube", "revert"] and cs[0]["n"] == 5
          and cs[1]["n"] == 3)
    check("minimo_soporte filtra singletons",
          all(c["n"] >= 2 for c in cs) and len(cs) == 2)
    check("fracción consistente",
          abs(cs[0]["fraccion"] - 5 / 9) < 1e-4)  # redondeo a 4 decimales

    # 4. El paquete de evidencia DESCRIBE, no prescribe (principio §3.2).
    ev = m.paquete_evidencia()
    check("paquete trae advertencia no prescriptiva",
          ev["tipo"] == "paquete_evidencia"
          and "no prescriptivo" in ev["advertencia"]
          and ev["total_firmas"] == 9)
    check("paquete no contiene instrucciones de edición",
          not any("mutar" in str(c) or "proponer" in str(c)
                  for c in ev["clusters"]))

    # 5. Estado vacío no rompe.
    m2 = MineroDebilidades()
    check("minero vacío: sin clusters",
          m2.clusters() == [] and m2.estado()["total_firmas"] == 0)

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
