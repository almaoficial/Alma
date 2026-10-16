"""Tests EXP80 — capa fina del formato abierto Agent Skills (US$0).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_exp80_agentskills.py

Cubre:
1. validar_spec: casos válidos e inválidos (fail-closed con motivo).
2. parse_frontmatter_yaml: mapas anidados (metadata:).
3. cargar_skill_spec: references/ además de referencias/, scripts/ y
   assets/ como passthrough (se listan, no se ejecutan).
4. exportar_skill: SKILL.md válido que re-valida; mapeo de metadata,
   lineage y renombre referencias/ -> references/; estado no exportado.
5. SkillIndex: migración v1 -> v2 aditiva sobre DB vieja; nuevas
   columnas en registrar/listar.
6. Round-trip export -> import.

Cero gasto de API (todo mock determinista). DBs en /tmp.
"""

import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.skills import (
    Skill, SkillIndex, SkillInvalida, cargar_skill,
)
from alma_service.agentskills_spec import (
    parse_frontmatter_yaml, validar_spec, cargar_skill_spec,
    exportar_skill,
)
from alma_service import versiones as V

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def escribir(tmp, categoria, nombre, frontmatter, cuerpo="# Cuerpo\n\nTexto.",
             subdirs=()):
    d = os.path.join(tmp, "skills", categoria, nombre)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("---\n" + frontmatter + "\n---\n\n" + cuerpo + "\n")
    for sub in subdirs:
        sd = os.path.join(d, sub)
        os.makedirs(sd, exist_ok=True)
        with open(os.path.join(sd, "nota.md"), "w") as f:
            f.write("# nota\n")
    return os.path.join(d, "SKILL.md")


FM_OK = ("name: mi-skill\ndescription: Hace X cuando Y.\n"
         "license: Apache-2.0\ncompatibility: cli\n"
         "metadata:\n  version: 2\n  author: test\n")


def test_validar_spec_ok():
    fm, _ = parse_frontmatter_yaml("---\n" + FM_OK + "---\ncuerpo")
    spec = validar_spec(fm, "mi-skill")
    check("spec válida pasa", spec["name"] == "mi-skill")
    check("license aceptada", spec["license"] == "Apache-2.0")
    check("compatibility aceptada", spec["compatibility"] == "cli")
    check("metadata es dict", spec["metadata"] == {"version": "2",
                                                   "author": "test"})
    check("escalar coerceado a str",
          isinstance(spec["metadata"]["version"], str))


def test_validar_spec_rechazos():
    casos = [
        ("mayúsculas en name",
         {"name": "Mi-Skill", "description": "d"}, "mi-skill"),
        ("name > 64 chars",
         {"name": "a" * 65, "description": "d"}, "a" * 65),
        ("name != dirname",
         {"name": "otra", "description": "d"}, "mi-skill"),
        ("doble guion",
         {"name": "mi--skill", "description": "d"}, "mi--skill"),
        ("guion final",
         {"name": "mi-skill-", "description": "d"}, "mi-skill-"),
        ("guion inicial",
         {"name": "-mi-skill", "description": "d"}, "-mi-skill"),
        ("description > 1024",
         {"name": "mi-skill", "description": "x" * 1025}, "mi-skill"),
        ("sin description",
         {"name": "mi-skill"}, "mi-skill"),
        ("sin name",
         {"description": "d"}, "mi-skill"),
        ("compatibility > 500",
         {"name": "mi-skill", "description": "d",
          "compatibility": "y" * 501}, "mi-skill"),
        ("metadata no-dict",
         {"name": "mi-skill", "description": "d",
          "metadata": "texto"}, "mi-skill"),
        ("allowed-tools tipo raro",
         {"name": "mi-skill", "description": "d",
          "allowed-tools": 123}, "mi-skill"),
    ]
    for titulo, fm, dname in casos:
        try:
            validar_spec(fm, dname)
            check("rechaza: " + titulo, False)
        except SkillInvalida as e:
            check("rechaza: " + titulo, len(str(e)) > 0)
    # name vacío también falla
    try:
        validar_spec({"name": "", "description": "d"}, "")
        check("rechaza name vacío", False)
    except SkillInvalida:
        check("rechaza name vacío", True)


def test_yaml_anidado():
    txt = ("---\nname: anidada\ndescription: d\nmetadata:\n"
           "  version: 3\n  tags:\n    - a\n    - b\n---\ncuerpo")
    fm, cuerpo = parse_frontmatter_yaml(txt)
    check("metadata anidado es dict",
          isinstance(fm["metadata"], dict))
    check("lista anidada preservada",
          fm["metadata"]["tags"] == ["a", "b"])
    check("cuerpo intacto", cuerpo == "cuerpo")
    for malo, titulo in [
        ("sin frontmatter", "falla sin ---"),
        ("---\n\n---\nvacio", "falla frontmatter vacío"),
        ("---\n- solo\n- lista\n---\nx", "falla frontmatter no-dict"),
        ("---\nname: [mal\n---\nx", "falla YAML inválido"),
    ]:
        try:
            parse_frontmatter_yaml(malo)
            check(titulo, False)
        except SkillInvalida:
            check(titulo, True)


def test_cargar_skill_spec_dirs():
    tmp = tempfile.mkdtemp()
    p = escribir(tmp, "cat", "mi-skill", FM_OK,
                 subdirs=("references", "referencias", "scripts",
                          "assets"))
    s = cargar_skill_spec(p)
    check("carga spec válida", s.nombre == "mi-skill")
    check("license en objeto", s.license == "Apache-2.0")
    check("metadata en objeto", s.metadata.get("author") == "test")
    refs = s.archivos_referencia
    check("references/ listado",
          any(r.startswith("references/") for r in refs))
    check("referencias/ listado (legacy)",
          any(r.startswith("referencias/") for r in refs))
    check("scripts passthrough listado",
          any(r.startswith("scripts/") for r in s.scripts))
    check("assets passthrough listado",
          any(r.startswith("assets/") for r in s.assets))
    # solo references/ (sin referencias/) también funciona
    tmp2 = tempfile.mkdtemp()
    p2 = escribir(tmp2, "cat", "solo-ref", FM_OK.replace("mi-skill",
                                                         "solo-ref"),
                  subdirs=("references",))
    s2 = cargar_skill_spec(p2)
    check("solo references/ ok",
          any(r.startswith("references/") for r in
              s2.archivos_referencia))
    # name != dirname falla al cargar
    tmp3 = tempfile.mkdtemp()
    p3 = escribir(tmp3, "cat", "otro-dir", FM_OK)
    try:
        cargar_skill_spec(p3)
        check("cargar falla si name != dirname", False)
    except SkillInvalida:
        check("cargar falla si name != dirname", True)


def test_exportar_skill():
    tmp = tempfile.mkdtemp()
    p = escribir(tmp, "cat", "mi-skill", FM_OK,
                 subdirs=("referencias", "scripts"))
    s = cargar_skill_spec(p)
    # versionador con lineage para probar el mapeo
    ver = V.VersionadorSkills(os.path.join(tmp, "ver.db"))
    ver.asentar_con_linaje(
        s.path, "CAPTURED", None, "desc", {},
        {"split_nombre": "handoff:downstream+referencia",
         "delta_down": 0.36, "delta_ref": 0.10,
         "regla": "puerta-doble-split", "fuente": "exp76"})
    out = os.path.join(tmp, "export")
    dir_skill, texto = exportar_skill(s, out, versionador=ver)
    check("exporta SKILL.md",
          os.path.isfile(os.path.join(dir_skill, "SKILL.md")))
    # lo exportado re-valida contra la spec (su propia puerta)
    fm2, _ = parse_frontmatter_yaml(texto)
    spec2 = validar_spec(fm2, "mi-skill")
    check("exportado re-valida", spec2["name"] == "mi-skill")
    check("metadata trae version/author (la declarada en frontmatter manda)",
          spec2["metadata"].get("version") == "2"
          and spec2["metadata"].get("author") == "test")
    check("lineage en metadata",
          spec2["metadata"].get("alma_split")
          == "handoff:downstream+referencia"
          and spec2["metadata"].get("alma_delta") == "0.36")
    check("estado NO exportado", "estado" not in fm2)
    check("referencias/ -> references/",
          os.path.isdir(os.path.join(dir_skill, "references"))
          and not os.path.isdir(os.path.join(dir_skill, "referencias")))
    check("scripts/ passthrough copiado",
          os.path.isdir(os.path.join(dir_skill, "scripts")))
    # sin versionador también exporta (metadata sin lineage)
    dir2, texto2 = exportar_skill(s, os.path.join(tmp, "export2"))
    fm3, _ = parse_frontmatter_yaml(texto2)
    check("exporta sin lineage",
          "alma_split" not in validar_spec(fm3, "mi-skill")["metadata"])
    # name inválido no escribe nada
    s_mala = Skill(path=p, categoria="cat", nombre="MALA",
                   descripcion="d", cuerpo="c")
    try:
        exportar_skill(s_mala, os.path.join(tmp, "export3"))
        check("export falla con name inválido (no escribe)", False)
    except SkillInvalida:
        check("export falla con name inválido (no escribe)",
              not os.path.isdir(os.path.join(tmp, "export3", "MALA")))
    ver_path = os.path.join(tmp, "ver.db")
    del ver


def test_indice_migracion_v1_v2():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "vieja.sqlite")
    # DB v1 a mano (sin las columnas nuevas)
    con = sqlite3.connect(db)
    con.execute(
        """CREATE TABLE skills (
               path TEXT PRIMARY KEY, name TEXT NOT NULL,
               description TEXT NOT NULL, categoria TEXT NOT NULL,
               created_by TEXT NOT NULL DEFAULT 'agent',
               estado TEXT NOT NULL DEFAULT 'active',
               version INTEGER NOT NULL DEFAULT 1,
               use_count INTEGER NOT NULL DEFAULT 0,
               last_used_at REAL, created_at REAL NOT NULL,
               tokens_idx INTEGER NOT NULL, schema TEXT NOT NULL)""")
    con.execute(
        "INSERT INTO skills (path, name, description, categoria,"
        " created_at, tokens_idx, schema) VALUES (?,?,?,?,?,?,?)",
        ("/x/vieja/SKILL.md", "vieja", "skill anterior", "cat",
         123.0, 5, "skill-index-v1"))
    con.commit()
    con.close()
    # abrir con el código nuevo: migra sin romper
    idx = SkillIndex(db)
    cols = {r[1] for r in idx._db.execute(
        "PRAGMA table_info(skills)").fetchall()}
    check("migración agrega license",
          "license" in cols and "compatibility" in cols
          and "metadata_json" in cols)
    filas = idx.listar()
    check("fila vieja legible tras migrar",
          len(filas) == 1 and filas[0]["name"] == "vieja")
    check("fila vieja metadata default {}",
          filas[0]["metadata"] == {})
    # registrar skill nueva con campos spec
    p = escribir(tmp, "nueva", "con-meta", FM_OK.replace("mi-skill",
                                                        "con-meta"))
    s = cargar_skill_spec(p)
    idx.registrar(s, presupuesto_tokens=10_000)
    fila = [f for f in idx.listar() if f["name"] == "con-meta"][0]
    check("license guardada", fila["license"] == "Apache-2.0")
    check("metadata guardada",
          fila["metadata"].get("author") == "test")
    check("schema v2 en filas nuevas",
          idx._db.execute(
              "SELECT schema FROM skills WHERE name='con-meta'"
          ).fetchone()[0] == "skill-index-v2")
    # re-registrar actualiza (upsert) los campos nuevos
    s2 = cargar_skill_spec(p)
    s2.license = "MIT"
    idx.registrar(s2, presupuesto_tokens=10_000)
    fila2 = [f for f in idx.listar() if f["name"] == "con-meta"][0]
    check("upsert actualiza license", fila2["license"] == "MIT")
    idx.close()


def test_roundtrip():
    tmp = tempfile.mkdtemp()
    p = escribir(tmp, "cat", "ida-vuelta", FM_OK.replace("mi-skill",
                                                        "ida-vuelta"),
                 subdirs=("references",))
    s = cargar_skill_spec(p)
    dir_skill, _texto = exportar_skill(s, os.path.join(tmp, "out"))
    s2 = cargar_skill_spec(os.path.join(dir_skill, "SKILL.md"))
    check("roundtrip name", s2.nombre == s.nombre)
    check("roundtrip description", s2.descripcion == s.descripcion)
    check("roundtrip metadata version (se preserva la declarada)",
          s2.metadata.get("version") == "2")
    check("roundtrip references renombrada",
          any(r.startswith("references/") for r in
              s2.archivos_referencia))
    # la skill legacy (cargar_skill) sigue funcionando igual
    s3 = cargar_skill(p)
    check("cargar_skill legacy intacto", s3.nombre == "ida-vuelta")


if __name__ == "__main__":
    test_validar_spec_ok()
    test_validar_spec_rechazos()
    test_yaml_anidado()
    test_cargar_skill_spec_dirs()
    test_exportar_skill()
    test_indice_migracion_v1_v2()
    test_roundtrip()
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if all(PASSOS) else 1)
