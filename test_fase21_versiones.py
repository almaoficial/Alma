"""Tests fase 2.1: versionado FIX/DERIVED/CAPTURED + DAG (OpenSpace).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase21_versiones.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.versiones import (
    VersionadorSkills, TIPO_FIX, TIPO_DERIVED, TIPO_CAPTURED)

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def main():
    d = tempfile.mkdtemp(prefix="alma_fase21_ver_")
    v = VersionadorSkills(os.path.join(d, "versiones.db"))

    # 1. CAPTURED: patrón nuevo, sin padre, con evidencia.
    c = v.captured("skills/nueva/SKILL.md", "patrón detectado en prod",
                   {"ejecucion": "exp-123"})
    check("captured v1 sin padre",
          c["version"] == 1 and c["tipo"] == TIPO_CAPTURED
          and c["padre_path"] is None)

    # 2. FIX: in-place, misma identidad, v+1, encadena hash.
    f = v.fix("skills/nueva/SKILL.md", "repara instrucción rota")
    check("fix v2 misma skill",
          f["version"] == 2 and f["tipo"] == TIPO_FIX
          and f["prev_hash"] == c["hash"] and f["hash"] != c["hash"])

    # 3. DERIVED: especializa, nuevo path, link al padre; el padre coexiste.
    dr = v.derived("skills/nueva/SKILL.md", "skills/nueva_casos/SKILL.md",
                   "especialización para casos borde")
    check("derived con link al padre",
          dr["tipo"] == TIPO_DERIVED
          and dr["padre_path"] == "skills/nueva/SKILL.md")
    hijas = v.hijas("skills/nueva/SKILL.md")
    check("hijas lista la derivada",
          any(h["skill_path"] == "skills/nueva_casos/SKILL.md"
              for h in hijas))
    check("el padre conserva su historial",
          len(v.historial("skills/nueva/SKILL.md")) == 2)

    # 4. Historial ordenado + cadena de hashes verificable.
    h = v.historial("skills/nueva/SKILL.md")
    check("historial ordenado por versión",
          [x["version"] for x in h] == [1, 2]
          and h[0]["evidencia"] == {"ejecucion": "exp-123"})
    check("cadena de hashes válida", v.verificar_cadena(
        "skills/nueva/SKILL.md") is True)

    # 5. Validaciones de la taxonomía.
    try:
        v._asentar("skills/x/SKILL.md", "INVENTADO", None, "d", None)
        mala = False
    except ValueError:
        mala = True
    check("tipo inválido rechazado", mala)
    try:
        v._asentar("skills/y2/SKILL.md", TIPO_DERIVED, None, "d", None)
        sin_padre = False
    except ValueError:
        sin_padre = True
    check("DERIVED sin padre rechazado", sin_padre)
    try:
        v._asentar("skills/z/SKILL.md", TIPO_CAPTURED,
                   "skills/nueva/SKILL.md", "d", None)
        con_padre = False
    except ValueError:
        con_padre = True
    check("CAPTURED con padre rechazado", con_padre)

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
