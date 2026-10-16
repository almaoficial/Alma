"""Tests fase 0: el harness como puerta de calidad.

Verifica la disciplina mecánica, no los números:
1. El pre-registro se escribe ANTES de correr réplicas (si la escritura
   falla, el experimento no corre).
2. El veredicto se calcula contra el criterio pre-registrado.
3. experimento_fase0() define la puerta del scaffold evolucionado
   (EXP56/57).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase0_harness.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.harness import (Experimento, experimento_fase0,
                                  correr_experimento)

PASSOS = []


def check(nombre, cond):
    PASSOS.append(cond)
    print(("PASS" if cond else "FAIL"), "-", nombre)


def test_preregistro_antes_de_correr():
    tmp = tempfile.mkdtemp()
    llamadas = []

    def ejecutar(pre, items, tasas):
        # el pre-registro ya debe existir en disco cuando esto corre
        assert os.path.exists(os.path.join(tmp, "preregistro.json"))
        llamadas.append(True)
        return {"efectos": [-1.0, -2.0], "efecto_medio": -1.5,
                "reg_trat_bloques": [[1], [2]]}

    exp = Experimento(nombre="prueba-orden",
                      hipotesis="h", criterio_exito="media < 0")
    report, veredicto = correr_experimento(
        exp, tmp, tasas=None, items=None, report_referencia=None,
        ejecutar=ejecutar)
    check("el pre-registro existe antes de las réplicas", llamadas == [True])
    check("report.json escrito",
          os.path.exists(os.path.join(tmp, "report.json")))
    check("veredicto.md escrito",
          os.path.exists(os.path.join(tmp, "veredicto.md")))
    with open(os.path.join(tmp, "preregistro.json")) as f:
        pre = json.load(f)
    check("pre-registro con hipótesis y criterio",
          pre["hipotesis"] == "h" and pre["criterio_exito"] == "media < 0")
    check("veredicto PASS con media < 0 y bit asumido",
          veredicto.startswith("# Veredicto") and "**PASS**" in veredicto)


def test_veredicto_fail():
    tmp = tempfile.mkdtemp()

    def ejecutar(pre, items, tasas):
        return {"efectos": [3.0, 4.0], "efecto_medio": 3.5,
                "reg_trat_bloques": [[9]]}

    exp = Experimento(nombre="prueba-fail", criterio_exito="media < 0")
    _, veredicto = correr_experimento(
        exp, tmp, tasas=None, items=None, report_referencia=None,
        ejecutar=ejecutar)
    check("veredicto FAIL con media > 0", "**FAIL**" in veredicto)


def test_veredicto_bit_identidad():
    tmp = tempfile.mkdtemp()

    def ejecutar(pre, items, tasas):
        return {"efectos": [-2.0], "efecto_medio": -2.0,
                "reg_trat_bloques": [[1, 2]]}

    exp = Experimento(nombre="prueba-bit", criterio_exito="bit + media < 0")
    _, veredicto = correr_experimento(
        exp, tmp, tasas=None, items=None,
        report_referencia={"reg_trat_bloques": [[1, 3]]},
        ejecutar=ejecutar)
    check("FAIL si los bloques no son bit-idénticos", "**FAIL**" in veredicto
          and "bit-identidad vs referencia: False" in veredicto)


def test_experimento_fase0():
    exp = experimento_fase0()
    check("nombre de la puerta",
          exp.nombre == "fase0-scaffold-evolucionado")
    check("5 réplicas", exp.n_replicas == 5)
    check("control verbatim EXP49",
          exp.control == "run_experiment49.correr_replica_endurecido")
    check("tratamiento es el servicio",
          exp.tratamiento == "alma_service.resolver.correr_replica_servicio")
    check("criterio exige bit-identidad",
          "bit-idéntico" in exp.criterio_exito)
    check("criterio exige media < 0", "media(efecto) < 0" in exp.criterio_exito)
    check("notas registran el scaffold validado",
          "n0=4" in exp.notas_diseno.get("scaffold", "")
          and "umbral_base=1" in exp.notas_diseno.get("scaffold", ""))


if __name__ == "__main__":
    test_preregistro_antes_de_correr()
    test_veredicto_fail()
    test_veredicto_bit_identidad()
    test_experimento_fase0()
    sys.exit(0 if all(PASSOS) else 1)
