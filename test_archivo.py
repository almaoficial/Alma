"""Tests del archivo de variantes (alma_service/archivo.py).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_archivo.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.archivo import ArchivoVariantes, NOMBRE_DEFAULT
from alma_service.gate import REGLA

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "test_archivo.jsonl")
        arch = ArchivoVariantes(ruta)

        # 1. El archivo se crea vacío.
        check("crea el archivo si no existe",
              os.path.exists(ruta) and arch.listar() == [])

        # 2. Guardar una variante adoptada: agrega ts + archivo_id, no muta.
        rec_in = {"tipo": "audit_propuesta", "propuesta": "v1",
                  "delta_in": 0.3, "delta_ho": 0.2,
                  "aceptado": True, "motivo": "aceptada"}
        rec_out = arch.guardar(rec_in)
        check("guardar retorna ts y archivo_id",
              "ts" in rec_out and rec_out["archivo_id"] == "av-1")
        check("no muta el registro de entrada", "ts" not in rec_in)

        # 3. Guardar una rechazada: también queda (el greedy no descarta).
        rec_out2 = arch.guardar({"tipo": "audit_propuesta",
                                 "propuesta": "v2", "delta_in": -0.1,
                                 "delta_ho": 0.5, "aceptado": False,
                                 "motivo": "regresión en train"})
        check("la rechazada también se archiva",
              rec_out2["archivo_id"] == "av-2")

        # 4. listar() devuelve en orden, con el contenido intacto.
        regs = arch.listar()
        check("listar devuelve las 2 en orden",
              len(regs) == 2 and regs[0]["propuesta"] == "v1"
              and regs[1]["propuesta"] == "v2")
        check("deltas intactos",
              regs[0]["delta_in"] == 0.3 and regs[1]["delta_ho"] == 0.5)

        # 5. El archivo es JSONL real (una línea por registro).
        with open(ruta, encoding="utf-8") as f:
            lineas = [l for l in f if l.strip()]
        check("JSONL: 2 líneas parseables",
              len(lineas) == 2 and all(
                  json.loads(l)["archivo_id"] for l in lineas))

        # 6. resumen() cuenta adoptadas vs rechazadas.
        res = arch.resumen()
        check("resumen: total 2, 1 adoptada, 1 rechazada",
              res == {"total": 2, "adoptadas": 1, "rechazadas": 1})

        # 7. Persistencia: una nueva instancia ve lo guardado.
        arch2 = ArchivoVariantes(ruta)
        rec_out3 = arch2.guardar({"aceptado": True})
        check("ids monotónicos entre instancias",
              rec_out3["archivo_id"] == "av-3"
              and arch2.resumen()["total"] == 3)

    # 8. La puerta no se tocó: la regla es idéntica.
    check("gate.py intacto: REGLA sin cambios",
          REGLA == "delta_in>=0 & delta_ho>=0 & max(delta_in,delta_ho)>0")

    # 9. Nombre default junto al ledger.
    check("nombre default", NOMBRE_DEFAULT == "metaloop_archivo.jsonl")

    print()
    ok = all(PASSOS)
    print(f"{sum(PASSOS)}/{len(PASSOS)} PASS")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
