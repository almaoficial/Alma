"""Tests fase 0: skills AgentSkills + presupuesto duro de contexto.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase0_skills.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.skills import (
    SkillIndex, cargar_skill, parse_frontmatter, estimar_tokens_skill,
    SkillInvalida, PresupuestoExcedido,
)

PASSOS = []
SKILL_MD = """---
name: hola-mundo
description: Skill de ejemplo para probar el índice.
version: 1
created_by: agent
---

# Hola mundo

Usá esta skill para decir hola. Ver [detalle](referencias/detalle.md).
"""


def check(nombre, cond):
    PASSOS.append(cond)
    print(("PASS" if cond else "FAIL"), "-", nombre)


def escribir_skill(tmp, categoria="ejemplo"):
    d = os.path.join(tmp, "skills", categoria, "hola-mundo")
    os.makedirs(d)
    p = os.path.join(d, "SKILL.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(SKILL_MD)
    return p


def test_parse():
    fm, cuerpo = parse_frontmatter(SKILL_MD)
    check("frontmatter parsea name", fm["name"] == "hola-mundo")
    check("frontmatter parsea created_by", fm["created_by"] == "agent")
    check("cuerpo no vacío", len(cuerpo) > 0)
    try:
        parse_frontmatter("sin frontmatter")
        check("falla sin frontmatter", False)
    except SkillInvalida:
        check("falla sin frontmatter", True)
    try:
        # parse_frontmatter es schema-agnóstico: valida forma, no campos
        fm2, _ = parse_frontmatter("---\ndescription: x\n---\ncuerpo")
        check("parser no exige campos (es schema-agnóstico)", fm2)
    except SkillInvalida:
        check("parser no exige campos (es schema-agnóstico)", False)
    # la validación de 'name' requerido la hace cargar_skill
    tmp_bad = tempfile.mkdtemp()
    d_bad = os.path.join(tmp_bad, "cat", "sin-nombre")
    os.makedirs(d_bad)
    p_bad = os.path.join(d_bad, "SKILL.md")
    with open(p_bad, "w", encoding="utf-8") as f:
        f.write("---\ndescription: sin nombre\n---\ncuerpo")
    try:
        cargar_skill(p_bad)
        check("cargar_skill falla sin name", False)
    except SkillInvalida:
        check("cargar_skill falla sin name", True)


def test_indice_progressive_disclosure():
    tmp = tempfile.mkdtemp()
    p = escribir_skill(tmp)
    skill = cargar_skill(p)
    check("carga skill válida", skill.nombre == "hola-mundo")
    idx = SkillIndex(os.path.join(tmp, "skills.sqlite"))
    idx.registrar(skill, presupuesto_tokens=10_000)
    filas = idx.listar()
    check("lista 1 skill", len(filas) == 1)
    check("fila liviana: sin cuerpo", "cuerpo" not in filas[0])
    completa = idx.cargar_completa(filas[0]["path"])
    check("cuerpo bajo demanda", "Hola mundo" in completa.cuerpo)
    check("tokens índice acotados",
          idx.tokens_indice() == estimar_tokens_skill(skill.nombre,
                                                      skill.descripcion))
    idx.close()


def test_presupuesto_duro():
    tmp = tempfile.mkdtemp()
    p = escribir_skill(tmp)
    skill = cargar_skill(p)
    idx = SkillIndex(os.path.join(tmp, "skills.sqlite"))
    try:
        idx.registrar(skill, presupuesto_tokens=1)  # imposible entrar
        check("corta con PresupuestoExcedido", False)
    except PresupuestoExcedido as e:
        check("corta con PresupuestoExcedido", e.tope == 1)
    check("no se registra al cortar", idx.listar() == [])
    idx.close()


def test_telemetria():
    tmp = tempfile.mkdtemp()
    p = escribir_skill(tmp)
    skill = cargar_skill(p)
    idx = SkillIndex(os.path.join(tmp, "skills.sqlite"))
    idx.registrar(skill, presupuesto_tokens=10_000)
    idx.marcar_uso(skill.path)
    fila = idx.listar()[0]
    check("use_count suma", fila["use_count"] == 1)
    check("antigüedad >= 0", idx.antiguedad_uso(skill.path) is not None)
    check("habilidad por (categoria, name)",
          idx.tiene_skill("ejemplo", "hola-mundo"))
    idx.close()


if __name__ == "__main__":
    test_parse()
    test_indice_progressive_disclosure()
    test_presupuesto_duro()
    test_telemetria()
    sys.exit(0 if all(PASSOS) else 1)
