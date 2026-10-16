"""Tests EXP81 — formato ECC en la capa fina Agent Skills (US$0).

ADOPTAR Patrón 1 del estudio ECC (2026-10-02): secciones fijas del
cuerpo (When to Use, When NOT to Use, Workflow, Anti-Patterns,
Related Skills), description <=30 palabras como presupuesto de
contexto (WARNING, no fallo: la spec manda), y check_skill_format()
para uso futuro del gate (sin conectar todavía).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_exp81_ecc_formato.py

Cero gasto de API (todo mock determinista). DBs en /tmp.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.skills import (
    Skill, SkillInvalida, cargar_skill,
)
from alma_service.agentskills_spec import (
    SECCIONES_ECC, MAX_PALABRAS_DESCRIPCION,
    parse_frontmatter_yaml, validar_spec, cargar_skill_spec,
    exportar_skill, dividir_secciones_ecc, check_skill_format,
)

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


CUERPO_ECC = """# Mi skill

Intro breve de la skill.

## Workflow

1. Paso uno.
2. Paso dos.

## When to Use

Cuando necesitás X.

## Related Skills

- otra-skill

## When NOT to Use

No usar cuando Z.

## Anti-Patterns

- No hacer W.
"""

FM_BASE = "name: ecc-skill\ndescription: Hace X cuando Y.\n"


def escribir(tmp, categoria, nombre, frontmatter, cuerpo):
    d = os.path.join(tmp, "skills", categoria, nombre)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "SKILL.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("---\n" + frontmatter + "\n---\n\n" + cuerpo + "\n")
    return p


def desc_palabras(n):
    return " ".join(f"palabra{i}" for i in range(n))


def test_loader_parsea_secciones():
    tmp = tempfile.mkdtemp()
    p = escribir(tmp, "cat", "ecc-skill", FM_BASE, CUERPO_ECC)
    s = cargar_skill_spec(p)
    check("loader trae las 5 secciones",
          set(s.ecc_secciones) == {c for c, _t in SECCIONES_ECC})
    check("when_to_use parseado",
          s.ecc_secciones["when_to_use"] == "Cuando necesitás X.")
    check("when_not_to_use parseado",
          "No usar cuando Z." in s.ecc_secciones["when_not_to_use"])
    # cuerpo conserva el texto COMPLETO (proveedor_real lo inyecta
    # íntegro al prompt): ecc_secciones es vista, no reemplazo.
    check("cuerpo intacto (texto completo)",
          "## Workflow" in s.cuerpo and "Intro breve" in s.cuerpo)


def test_exporta_secciones_orden_canonico():
    # Secciones en orden revuelto en el archivo -> el exportador
    # las emite en orden canónico.
    s = Skill(path="/tmp/x/SKILL.md", categoria="cat", nombre="ecc-skill",
              descripcion="Hace X cuando Y.", cuerpo=CUERPO_ECC,
              ecc_secciones={})
    tmp = tempfile.mkdtemp()
    _dir, texto = exportar_skill(s, os.path.join(tmp, "out"))
    posiciones = [texto.index(f"## {t}") for _c, t in SECCIONES_ECC]
    check("emite las 5 secciones", len(posiciones) == 5)
    check("orden canónico", posiciones == sorted(posiciones))
    # re-valida contra la spec (su propia puerta)
    fm, _ = parse_frontmatter_yaml(texto)
    check("exportado re-valida", validar_spec(fm, "ecc-skill")["name"]
          == "ecc-skill")


def test_ecc_secciones_explicitas_mandan():
    # Si el registro trae ecc_secciones explícitas, tienen prioridad
    # sobre las detectadas en el cuerpo (sin duplicar).
    s = Skill(path="/tmp/x/SKILL.md", categoria="cat", nombre="ecc-skill",
              descripcion="Hace X cuando Y.",
              cuerpo="Intro.\n\n## Workflow\n\nViejo.",
              ecc_secciones={"workflow": "Nuevo."})
    tmp = tempfile.mkdtemp()
    _dir, texto = exportar_skill(s, os.path.join(tmp, "out"))
    check("explícita manda sobre la detectada",
          "Nuevo." in texto and "Viejo." not in texto)
    check("sin duplicados", texto.count("## Workflow") == 1)


def test_roundtrip_ecc_estable():
    tmp = tempfile.mkdtemp()
    p = escribir(tmp, "cat", "ecc-skill", FM_BASE, CUERPO_ECC)
    s = cargar_skill_spec(p)
    d1, t1 = exportar_skill(s, os.path.join(tmp, "out1"))
    s2 = cargar_skill_spec(os.path.join(d1, "SKILL.md"))
    d2, t2 = exportar_skill(s2, os.path.join(tmp, "out2"))
    check("export->load->export estable (texto idéntico)", t1 == t2)
    check("secciones iguales tras roundtrip",
          s2.ecc_secciones == s.ecc_secciones)
    # y un tercer ciclo no diverge (punto fijo)
    s3 = cargar_skill_spec(os.path.join(d2, "SKILL.md"))
    _d3, t3 = exportar_skill(s3, os.path.join(tmp, "out3"))
    check("punto fijo en el tercer ciclo", t2 == t3)


def test_seccion_desconocida_se_preserva():
    cuerpo = ("Intro.\n\n## Workflow\n\nPasos.\n\n"
              "## Notas varias\n\nTexto libre no-ECC.\n")
    tmp = tempfile.mkdtemp()
    p = escribir(tmp, "cat", "ecc-skill", FM_BASE, cuerpo)
    s = cargar_skill_spec(p)
    check("encabezado desconocido no crea sección",
          "notas_varias" not in s.ecc_secciones
          and set(s.ecc_secciones) == {"workflow"})
    d1, t1 = exportar_skill(s, os.path.join(tmp, "out1"))
    check("contenido desconocido preservado verbatim",
          "## Notas varias" in t1 and "Texto libre no-ECC." in t1)
    s2 = cargar_skill_spec(os.path.join(d1, "SKILL.md"))
    _d2, t2 = exportar_skill(s2, os.path.join(tmp, "out2"))
    check("roundtrip estable con sección desconocida", t1 == t2)


def test_normalizacion_titulos():
    cuerpo = "Intro.\n\n## WHEN not TO use\n\nNo usar.\n"
    intro, secs = dividir_secciones_ecc(cuerpo)
    check("título con mayúsculas raras se reconoce",
          secs.get("when_not_to_use") == "No usar.")
    check("intro separada", intro == "Intro.")


def test_solo_secciones_sin_intro():
    cuerpo = "## When to Use\n\nUsar acá.\n\n## Workflow\n\nPasos.\n"
    tmp = tempfile.mkdtemp()
    p = escribir(tmp, "cat", "ecc-skill", FM_BASE, cuerpo)
    s = cargar_skill_spec(p)  # cuerpo no vacío: tiene secciones
    check("carga sin intro", set(s.ecc_secciones)
          == {"when_to_use", "workflow"})
    d1, t1 = exportar_skill(s, os.path.join(tmp, "out1"))
    s2 = cargar_skill_spec(os.path.join(d1, "SKILL.md"))
    _d2, t2 = exportar_skill(s2, os.path.join(tmp, "out2"))
    check("roundtrip estable sin intro", t1 == t2)


def test_sin_secciones_sin_cambios():
    # Skill legacy sin secciones ECC: comportamiento idéntico al
    # anterior (cuerpo verbatim, ecc_secciones vacío).
    cuerpo = "# Simple\n\nTexto plano sin secciones."
    tmp = tempfile.mkdtemp()
    p = escribir(tmp, "cat", "ecc-skill", FM_BASE, cuerpo)
    s = cargar_skill_spec(p)
    check("sin secciones -> dict vacío", s.ecc_secciones == {})
    check("cuerpo intacto", s.cuerpo.strip() == cuerpo)
    d1, t1 = exportar_skill(s, os.path.join(tmp, "out1"))
    check("export verbatim sin secciones", t1.endswith(cuerpo + "\n"))
    # el loader legacy sigue igual
    s3 = cargar_skill(p)
    check("cargar_skill legacy intacto", s3.nombre == "ecc-skill")


def test_warning_description_larga():
    base = "name: ecc-skill\ndescription: {}\n"
    # 30 palabras: sin warning (borde)
    f30 = check_skill_format("---\n" + base.format(desc_palabras(30))
                             + "---\ncuerpo")
    check("30 palabras no dispara warning",
          [f for f in f30 if f["seccion"] == "description"] == [])
    # 31 palabras: warning en description
    f31 = check_skill_format("---\n" + base.format(desc_palabras(31))
                             + "---\ncuerpo")
    warns = [f for f in f31 if f["seccion"] == "description"]
    check("31 palabras dispara warning",
          len(warns) == 1 and warns[0]["severidad"] == "warning")
    check("finding tiene seccion/severidad/mensaje",
          set(warns[0]) == {"seccion", "severidad", "mensaje"})


def test_spec_manda_sobre_ecc():
    # 40 palabras (< 1024 chars): la spec lo permite -> validar_spec
    # NO falla. El límite ECC de 30 es warning, no validez.
    fm = {"name": "ecc-skill", "description": desc_palabras(40)}
    try:
        spec = validar_spec(fm, "ecc-skill")
        check("spec acepta 40 palabras (<1024 chars)",
              spec["description"].startswith("palabra0"))
    except SkillInvalida:
        check("spec acepta 40 palabras (<1024 chars)", False)
    findings = check_skill_format(
        "---\nname: ecc-skill\ndescription: {}\n---\ncuerpo".format(
            desc_palabras(40)))
    check("pero check_skill_format avisa",
          any(f["seccion"] == "description"
              and f["severidad"] == "warning" for f in findings))


def test_warning_sin_when_not_to_use():
    cuerpo_sin = "Intro.\n\n## When to Use\n\nUsar.\n"
    f_sin = check_skill_format("---\n" + FM_BASE + "---\n" + cuerpo_sin)
    check("falta When NOT to Use -> warning",
          any(f["seccion"] == "when_not_to_use"
              and f["severidad"] == "warning" for f in f_sin))
    cuerpo_con = cuerpo_sin + "\n## When NOT to Use\n\nNo usar.\n"
    f_con = check_skill_format("---\n" + FM_BASE + "---\n" + cuerpo_con)
    check("con When NOT to Use -> sin warning",
          [f for f in f_con if f["seccion"] == "when_not_to_use"]
          == [])


def test_check_skill_format_path_y_texto():
    tmp = tempfile.mkdtemp()
    p = escribir(tmp, "cat", "ecc-skill", FM_BASE, CUERPO_ECC)
    por_path = check_skill_format(p)
    with open(p, encoding="utf-8") as f:
        por_texto = check_skill_format(f.read())
    check("path y texto dan lo mismo", por_path == por_texto)
    # skill completa y prolija: cero findings
    check("skill ECC completa -> sin findings", por_path == [])


def test_check_skill_format_invalido_falla():
    for malo, titulo in [
        ("sin frontmatter", "falla sin frontmatter"),
        ("---\nname: x\n---\ncuerpo", "falla sin description"),
        (123, "falla con tipo no-str"),
    ]:
        try:
            check_skill_format(malo)
            check(titulo, False)
        except SkillInvalida:
            check(titulo, True)


def test_metadata_origin_passthrough():
    # metadata.origin: primer campo de provenance (autodeclarado:
    # etiqueta útil, NO prueba criptográfica — ver ClawHavoc).
    fm = FM_BASE + "metadata:\n  origin: ecc\n  version: 1\n"
    tmp = tempfile.mkdtemp()
    p = escribir(tmp, "cat", "ecc-skill", fm, CUERPO_ECC)
    s = cargar_skill_spec(p)
    check("origin preservado en metadata",
          s.metadata.get("origin") == "ecc")
    _d, texto = exportar_skill(s, os.path.join(tmp, "out"))
    fm2, _ = parse_frontmatter_yaml(texto)
    check("origin sobrevive al export",
          validar_spec(fm2, "ecc-skill")["metadata"].get("origin")
          == "ecc")


def test_export_escapa_dos_puntos_en_description():
    # Regresión: una description con ": " rompía el YAML generado por el
    # exportador (el re-parse fallaba). El exportador debe entrecomillar.
    fm = FM_BASE.replace("description: Hace X cuando Y.",
                         'description: "Genera ángulos para Meta Ads: 30 listos"')
    tmp = tempfile.mkdtemp()
    p = escribir(tmp, "cat", "ecc-skill", fm, "cuerpo simple")
    s = cargar_skill_spec(p)
    _d, texto = exportar_skill(s, os.path.join(tmp, "out"))
    fm2, _ = parse_frontmatter_yaml(texto)  # no debe explotar
    check("export con ': ' en description re-parsea",
          fm2["description"] == "Genera ángulos para Meta Ads: 30 listos")
    s2 = cargar_skill_spec(os.path.join(_d, "SKILL.md"))
    check("description sobrevive round-trip con ': '",
          s2.descripcion == s.descripcion)


if __name__ == "__main__":
    test_loader_parsea_secciones()
    test_exporta_secciones_orden_canonico()
    test_ecc_secciones_explicitas_mandan()
    test_roundtrip_ecc_estable()
    test_seccion_desconocida_se_preserva()
    test_normalizacion_titulos()
    test_solo_secciones_sin_intro()
    test_sin_secciones_sin_cambios()
    test_warning_description_larga()
    test_spec_manda_sobre_ecc()
    test_warning_sin_when_not_to_use()
    test_check_skill_format_path_y_texto()
    test_check_skill_format_invalido_falla()
    test_metadata_origin_passthrough()
    test_export_escapa_dos_puntos_en_description()
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if all(PASSOS) else 1)
