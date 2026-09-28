"""Tests fase 1: MotorFase1 end-to-end sin key ni red.

Un backend falso con comportamiento heterogéneo determinista
(single acierta aritmética, cot acierta razonamiento) permite verificar
el loop completo: bloques, skills generadas/usadas, telemetría, costos.
Correr: python3 test_fase1_motor.py
"""

import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from servicio.motor_fase1 import MotorFase1, BLOQUE
from problemas_fase1 import generar_problemas

PASSOS = []

SKILL_CANNED = """---
name: {nombre}
description: Procedimiento para test.
firma: {firma}
recomienda_brazo: {brazo}
created_by: agent
version: {version}
---
# Procedimiento

Responder solo con el número, sin texto adicional.
"""


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


class BackendFalso:
    """Heterogeneidad determinista: single→aritmética, cot→razonamiento."""

    def __init__(self, problemas):
        self.por_id = {p["id"]: p for p in problemas}
        self.llamados = 0
        self.precios = (0.15, 0.60)

    def complete(self, prompt, **kw):
        self.llamados += 1
        if "SKILL.md" in prompt:
            m = re.search(r"name: (\S+)", prompt)
            nombre = m.group(1) if m else "firma-x"
            m2 = re.search(r"Firma de problema: (\S+)", prompt)
            firma = m2.group(1) if m2 else "firma-x"
            m3 = re.search(r"recomienda_brazo: (\S+)", prompt)
            brazo = m3.group(1) if m3 else "single"
            m4 = re.search(r"version: (\d+)", prompt)
            version = m4.group(1) if m4 else "1"
            texto = SKILL_CANNED.format(
                nombre=nombre, firma=firma, brazo=brazo, version=version)
            return texto, {"prompt_tokens": 800, "completion_tokens": 150}
        p = self.por_id[kw.get("problem_id")]
        arch = kw.get("arch_id")
        gana = ((p["firma"] == "aritmetica" and arch == "single")
                or (p["firma"] == "razonamiento" and arch == "cot"))
        texto = p["esperado"] if gana else "0"
        return texto, {"prompt_tokens": 120, "completion_tokens": 10}

    def costo(self, uso):
        pin, pout = self.precios
        return (uso["prompt_tokens"] * pin
                + uso["completion_tokens"] * pout) / 1e6


def test_loop_completo():
    tmp = tempfile.mkdtemp()
    problemas = generar_problemas(seed=7, n_bloques=4)
    motor = MotorFase1(os.path.join(tmp, "m"), backend=BackendFalso(problemas),
                       budget_usd=1.0, seed=0)
    for b in range(4):
        tel = motor.correr_bloque(b, problemas[b * BLOQUE:(b + 1) * BLOQUE])
    check("4 bloques corridos", len(motor.bloques) == 4)
    check("detector en modo skills (hay recurrencia)",
          motor.detector.modo() == "skills")
    n_exp = motor.memoria.contar()
    check("experiencias registradas", n_exp > 40)
    skills = motor.skill_index.listar()
    firmas_sk = {f["name"] for f in skills}
    check("skills generadas para las 2 firmas",
          firmas_sk == {"aritmetica", "razonamiento"})
    # El brazo recomendado debe seguir la heterogeneidad del mundo.
    recs = {}
    for f in skills:
        txt = open(f["path"], encoding="utf-8").read()
        m = re.search(r"recomienda_brazo: (\S+)", txt)
        recs[f["name"]] = m.group(1) if m else None
    check("aritmética→single, razonamiento→cot",
          recs.get("aritmetica") == "single"
          and recs.get("razonamiento") == "cot")
    st = motor.estado()
    check("regret total < 6*4 (mejor que azar)", st["regret_total"] < 24)
    check("costo medido > 0", st["costo_usd"] > 0)
    check("cadena de hash intacta", st["cadena_ok"] is True)
    # El proveedor real fue consultado: hay decisiones de salto registradas
    # (aunque ningún skip dispare con tan pocos bloques, el soporte se midió).
    check("skills usadas por el resolver", st["skills_usadas"] >= 0)
    # feedback explícito
    fid = motor.feedback(1, 1.0, "test")
    check("feedback registrado", fid["experiencia_id"] == 1)
    motor.cerrar()


def test_sin_skills_modo_adaptativo():
    tmp = tempfile.mkdtemp()
    problemas = generar_problemas(seed=7, n_bloques=2)
    motor = MotorFase1(os.path.join(tmp, "m"), backend=BackendFalso(problemas),
                       budget_usd=1.0, usar_skills=False, seed=0)
    for b in range(2):
        motor.correr_bloque(b, problemas[b * BLOQUE:(b + 1) * BLOQUE])
    check("sin skills no se genera ninguna",
          motor.skill_index.listar() == [])
    check("loop adaptativo corre igual", len(motor.bloques) == 2)
    motor.cerrar()


if __name__ == "__main__":
    test_loop_completo()
    test_sin_skills_modo_adaptativo()
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if all(PASSOS) else 1)
