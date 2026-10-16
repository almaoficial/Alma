"""Tests fase 1: proveedor real, generador de skills, presupuesto.

Convención del repo: funciones planas, sin pytest. Sin key, sin red:
los backends son falsos y deterministas. Correr:
    python3 test_fase1_proveedor.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.llm import Presupuesto, ClienteMedido, PresupuestoAgotado
from alma_service.memoria import MemoriaExperiencias
from alma_service.skills import SkillIndex, cargar_skill
from alma_service.curator import Curator
from alma_service.proveedor_real import (
    ProveedorSkillsReal, ProveedorSkillsNulo, GeneradorSkills,
    BackendConSkill, slug_firma,
)

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
    """Backend determinista: devuelve texto fijo y uso fijo."""

    def __init__(self, texto="42", prompt_tokens=100, completion_tokens=20):
        self.texto = texto
        self.uso = {"prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens}
        self.llamados = []
        self.precios = (0.15, 0.60)

    def complete(self, prompt, **kw):
        self.llamados.append({"prompt": prompt, "kw": kw})
        return self.texto, dict(self.uso)

    def costo(self, uso):
        pin, pout = self.precios
        return (uso["prompt_tokens"] * pin
                + uso["completion_tokens"] * pout) / 1e6


class BackendGenFalso(BackendFalso):
    """Si el prompt pide un SKILL.md, devuelve uno válido parametrizado."""

    def complete(self, prompt, **kw):
        self.llamados.append({"prompt": prompt, "kw": kw})
        if "SKILL.md" in prompt:
            import re
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
            return texto, dict(self.uso)
        return self.texto, dict(self.uso)


def _entorno():
    tmp = tempfile.mkdtemp()
    mem = MemoriaExperiencias(os.path.join(tmp, "mem.db"))
    idx = SkillIndex(os.path.join(tmp, "idx.db"))
    cur = Curator(idx, ledger_path=os.path.join(tmp, "ledger.jsonl"))
    return tmp, mem, idx, cur


def _experiencia(mem, clase, brazo, reward, enunciado="¿Cuánto es 2 + 2?"):
    mem.append_experiencia({
        "problema_id": f"p-{clase}-{brazo}-{reward}",
        "clase": clase, "arch_id": brazo,
        "features": {"enunciado": enunciado},
        "respuesta": "4", "traza": "t",
        "metricas": {"reward": reward},
        "costo_usd": 0.0,
    })


def test_presupuesto_corte_duro():
    pre = Presupuesto(0.001)
    cli = ClienteMedido(BackendFalso(), pre)
    ok = False
    try:
        cli.complete("hola")  # 120 tokens ≈ 0.000027 USD: entra
        cli.complete("hola")  # sigue entrando...
        for _ in range(100):
            cli.complete("hola")
    except PresupuestoAgotado:
        ok = True
    check("presupuesto corta antes de exceder", ok)
    check("gasto registrado no supera el tope",
          cli.total_usd <= 0.001 + 1e-9)


def test_generador_crea_skill_valida():
    tmp, mem, idx, cur = _entorno()
    for i in range(8):
        _experiencia(mem, "aritmetica", "single", 1.0)
        _experiencia(mem, "aritmetica", "cot", 0.0)
    gen = GeneradorSkills(idx, mem, os.path.join(tmp, "skills"),
                          curator=cur, min_experiencias=6)
    cli = ClienteMedido(BackendGenFalso())
    accion, det = gen.maybe_generar_o_refinar("aritmetica", cli,
                                              ("single", "cot"))
    check("genera skill con evidencia suficiente", accion == "generada")
    prov = ProveedorSkillsReal(idx, mem, ("single", "cot"))
    check("proveedor.existe tras generar", prov.existe(0, "aritmetica"))
    sk = prov.cargar_skill("aritmetica")
    check("skill cargable con cuerpo", sk is not None and len(sk.cuerpo) > 0)
    check("recomienda el brazo ganador",
          prov.recomienda_brazo("aritmetica") == "single")
    check("brazo() = argmax con decaimiento",
          prov.brazo(0, "aritmetica") == "single")


def test_generador_omite_sin_evidencia():
    tmp, mem, idx, cur = _entorno()
    _experiencia(mem, "aritmetica", "single", 1.0)
    gen = GeneradorSkills(idx, mem, os.path.join(tmp, "skills"),
                          curator=cur, min_experiencias=6)
    cli = ClienteMedido(BackendGenFalso())
    n_antes = len(cli.backend.llamados)
    accion, det = gen.maybe_generar_o_refinar("aritmetica", cli,
                                              ("single", "cot"))
    check("omite generar sin evidencia (no gasta)",
          accion == "omitida" and len(cli.backend.llamados) == n_antes)


def test_refinamiento_ante_contradiccion():
    tmp, mem, idx, cur = _entorno()
    for _ in range(8):
        _experiencia(mem, "aritmetica", "single", 1.0)
    gen = GeneradorSkills(idx, mem, os.path.join(tmp, "skills"),
                          curator=cur, min_experiencias=6,
                          max_refinamientos=2)
    cli = ClienteMedido(BackendGenFalso())
    a1, _ = gen.maybe_generar_o_refinar("aritmetica", cli,
                                        ("single", "cot"))
    check("v1 generada", a1 == "generada")
    # El mundo cambia: cot pasa a ganar.
    for _ in range(8):
        _experiencia(mem, "aritmetica", "cot", 1.0)
        _experiencia(mem, "aritmetica", "single", 0.0)
    a2, det = gen.maybe_generar_o_refinar("aritmetica", cli,
                                          ("single", "cot"))
    check("refina ante contradicción", a2 == "refinada")
    check("versión 2", det.get("version") == 2)
    prov = ProveedorSkillsReal(idx, mem, ("single", "cot"))
    check("recomendación actualizada",
          prov.recomienda_brazo("aritmetica") == "cot")
    # Sin contradicción nueva no refina (no gasta de más).
    n_llamados = len(cli.backend.llamados)
    a3, _ = gen.maybe_generar_o_refinar("aritmetica", cli,
                                        ("single", "cot"))
    check("no refina sin contradicción",
          a3 == "omitida" and len(cli.backend.llamados) == n_llamados)


def test_soporte_sobre_probes_reales():
    tmp, mem, idx, cur = _entorno()
    prov = ProveedorSkillsReal(idx, mem, ("single", "cot"))
    # 3 bloques con probe completo donde single gana siempre.
    for b in range(3):
        mem.registrar_bloque_probe(
            b, "aritmetica",
            {"single": [1, 1, 1], "cot": [0, 1, 0]})
    fuerte, wins, k, umbral = prov.soporte(9, "aritmetica", "single")
    check("wins pareados correctos", wins == 3 and k == 3)
    check("umbral endurecido 1+floor(3/3)=2", umbral == 2)
    check("soporte fuerte con 3/3", fuerte is True)
    # Con 2 bloques y 1 win se alcanza el umbral validado (1): más confianza en la skill (EXP56/57).
    mem2_path = os.path.join(tmp, "mem2.db")
    mem2 = MemoriaExperiencias(mem2_path)
    prov2 = ProveedorSkillsReal(idx, mem2, ("single", "cot"))
    mem2.registrar_bloque_probe(
        0, "aritmetica", {"single": [1, 1], "cot": [0, 0]})
    mem2.registrar_bloque_probe(
        1, "aritmetica", {"single": [0, 0], "cot": [1, 1]})
    fuerte2, wins2, k2, umbral2 = prov2.soporte(9, "aritmetica", "single")
    check("soporte fuerte con 1/2 wins (umbral validado=1)",
          fuerte2 is True and wins2 == 1 and k2 == 2)


def test_backend_con_skill_inyecta_guia():
    b = BackendFalso(texto="ok")
    cli = ClienteMedido(b)
    tmp, mem, idx, cur = _entorno()
    for _ in range(8):
        _experiencia(mem, "aritmetica", "single", 1.0)
    gen = GeneradorSkills(idx, mem, os.path.join(tmp, "skills"),
                          curator=cur, min_experiencias=6)
    cli2 = ClienteMedido(BackendGenFalso())
    gen.maybe_generar_o_refinar("aritmetica", cli2, ("single",))
    prov = ProveedorSkillsReal(idx, mem, ("single",))
    sk = prov.cargar_skill("aritmetica")
    env = BackendConSkill(cli, sk)
    env.complete("¿Cuánto es 2+2?", system="Sos conciso.")
    sys_usado = b.llamados[-1]["kw"].get("system", "")
    check("inyecta el cuerpo de la skill en system",
          sk.cuerpo[:30] in sys_usado and "Sos conciso." in sys_usado)


def test_proveedor_nulo():
    nulo = ProveedorSkillsNulo()
    check("nulo nunca tiene skills", nulo.existe(0, "x") is False)
    check("nulo sin brazo", nulo.brazo(0, "x") is None)
    check("nulo sin soporte", nulo.soporte(0, "x", "single")[0] is False)


if __name__ == "__main__":
    test_presupuesto_corte_duro()
    test_generador_crea_skill_valida()
    test_generador_omite_sin_evidencia()
    test_refinamiento_ante_contradiccion()
    test_soporte_sobre_probes_reales()
    test_backend_con_skill_inyecta_guia()
    test_proveedor_nulo()
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if all(PASSOS) else 1)
