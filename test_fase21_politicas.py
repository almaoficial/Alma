#!/usr/bin/env python3
"""Fase 2.1 (Song g): puerta determinística de políticas.

Checks: default-deny, confinamiento de rutas, narrowing inmediato,
expansión solo con aprobación humana, ledger encadenado, y que ningún
LLM toca el camino de enforcement.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alma_service.politicas import (  # noqa: E402
    PuertaPoliticas, politica_default, verificar_carga_skill,
    SIN_CUBRIR)
from alma_service.skills import cargar_skill  # noqa: E402

CHECKS = []


def check(nombre, cond):
    CHECKS.append((nombre, bool(cond)))
    print(("PASS " if cond else "FAIL ") + nombre)


def puerta_tmp():
    d = tempfile.mkdtemp(prefix="alma_pol_")
    os.makedirs(os.path.join(d, "skills"))
    return PuertaPoliticas(
        {"skills": os.path.join(d, "skills"), "workspace": d},
        ledger_path=os.path.join(d, "ledger.jsonl")), d


# 1. Default-deny: herramienta no listada (comando_shell) → denegada.
p, d = puerta_tmp()
r = p.evaluar("comando_shell", {"cmd": "ls"})
check("default-deny: comando_shell no listado", not r["permitido"])

# 2. Ruta dentro de la raíz → permitida.
r = p.evaluar("cargar_skill",
              {"path": os.path.join(d, "skills", "x", "SKILL.md")})
check("allowlist: ruta dentro de skills", r["permitido"])

# 3. Escape con .. → denegado.
r = p.evaluar("cargar_skill",
              {"path": os.path.join(d, "skills", "..", "secreto.txt")})
check("deniega escape con ..", not r["permitido"])

# 4. Argumento no permitido → denegado.
r = p.evaluar("cargar_skill",
              {"path": os.path.join(d, "skills", "x.md"), "extra": 1})
check("deniega argumento no listado", not r["permitido"])

# 5. Argumento requerido faltante → denegado.
r = p.evaluar("cargar_skill", {})
check("deniega sin argumento requerido", not r["permitido"])

# 6. Narrowing: aplica de inmediato, sin aprobación.
p.estrechar("ejecutar_benchmark")
r = p.evaluar("ejecutar_benchmark", {})
check("narrowing inmediato", not r["permitido"])

# 7. Expansión: pendiente → sigue denegada; aprobada → permitida.
sol = p.solicitar_ampliacion(
    "comando_shell", {"cmd": ("regex", r"ls( -l)?")})
r = p.evaluar("comando_shell", {"cmd": "ls"})
check("expansion pendiente sigue denegada", not r["permitido"])
ap = p.aprobar_ampliacion(sol["id"])
r = p.evaluar("comando_shell", {"cmd": "ls"})
check("expansion aprobada permite", ap["ok"] and r["permitido"])
r = p.evaluar("comando_shell", {"cmd": "rm -rf /"})
check("expansion aprobada respeta regex", not r["permitido"])

# 8. Ledger: narrowing y expansion_aprobada quedan asentados.
tipos = []
with open(p.ledger_path, encoding="utf-8") as f:
    for linea in f:
        fila = json.loads(linea)
        tipos.append(fila["evento"]["tipo"])
check("ledger registra narrowing+expansion",
      "narrowing" in tipos and "expansion_aprobada" in tipos)

# 9. verificar_carga_skill: skill que declara herramienta fuera de la
#    allowlist → se rechaza la carga.
sd = os.path.join(d, "skills", "mala")
os.makedirs(sd)
with open(os.path.join(sd, "SKILL.md"), "w", encoding="utf-8") as fh:
    fh.write("---\nname: mala\ndescription: x\nherramientas: comando_shell\n---\n# X\n")
sk = cargar_skill(os.path.join(sd, "SKILL.md"))
p2, _ = puerta_tmp()  # política default: sin comando_shell
ok, motivo = verificar_carga_skill(sk, p2)
check("carga rechaza herramienta no listada", not ok)
ok, _ = verificar_carga_skill(sk, p)  # p sí lo tiene (expansión)
check("carga permite herramienta listada", ok)

# 10. Ningún LLM en el camino de enforcement.
src = open(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "alma_service", "politicas.py"), encoding="utf-8").read()
check("politicas.py no importa LLM",
      "import llm" not in src and "from .llm" not in src
      and "from alma_service.llm" not in src)

# 11. SIN_CUBRIR documenta los límites (no promete de más).
check("SIN_CUBRIR documentado",
      "sandbox" in SIN_CUBRIR and "AgentPoison" in SIN_CUBRIR)

n_fails = sum(1 for _, c in CHECKS if not c)
print(f"\n{len(CHECKS) - n_fails}/{len(CHECKS)} checks en verde")
sys.exit(1 if n_fails else 0)
