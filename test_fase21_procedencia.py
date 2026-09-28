#!/usr/bin/env python3
"""Fase 2.1 (Song h): procedencia y cuarentena para memoria y skills.

Checks: tercero/importado nace en cuarentena; lo en cuarentena no
alimenta decisiones (recuperación, detalle); la evicción archiva
primero lo en cuarentena; graduación explícita; skills igual.
"""

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alma_service.memoria import MemoriaExperiencias  # noqa: E402
from alma_service.procedencia import (  # noqa: E402
    ProcedenciaMemoria, ProcedenciaSkills)

CHECKS = []


def check(nombre, cond):
    CHECKS.append((nombre, bool(cond)))
    print(("PASS " if cond else "FAIL ") + nombre)


def registrar_exp(mem, clase, arch_id, reward):
    mem._db.execute(
        "INSERT INTO experiencias (problema_id, clase, arch_id,"
        " metricas, timestamp, prev_hash, hash) VALUES (?,?,?,?,?,?,?)",
        (f"p-{arch_id}", clase, arch_id,
         json.dumps({"reward": reward}), time.time(), "NA",
         f"h-{arch_id}"))
    mem._db.commit()
    return mem._db.execute("SELECT last_insert_rowid()").fetchone()[0]


d = tempfile.mkdtemp(prefix="alma_proc_")
mem = MemoriaExperiencias(os.path.join(d, "mem.db"))
proc = ProcedenciaMemoria(os.path.join(d, "mem.db"))

# 1. tercero nace en cuarentena; propio no.
id1 = registrar_exp(mem, "c1", "a1", 1.0)
id2 = registrar_exp(mem, "c1", "a2", 0.0)
proc.registrar(id1, "tercero")
proc.registrar(id2, "propio")
check("tercero nace en cuarentena", proc.en_cuarentena(id1))
check("propio no en cuarentena", not proc.en_cuarentena(id2))
check("origen_de correcto", proc.origen_de(id1) == "tercero")

# 2. Lo en cuarentena no alimenta decisiones.
rec = mem.recuperar_con_decaimiento("c1")
archs = [a for a, _, _ in rec]
check("cuarentena excluida del prior", "a1" not in archs
      and "a2" in archs)
det = mem.experiencias_detalle("c1")
check("cuarentena excluida del detalle",
      all(x["arch_id"] != "a1" for x in det))

# 3. Graduación explícita → vuelve a alimentar.
proc.graduar(id1)
check("graduar saca de cuarentena", not proc.en_cuarentena(id1))
rec = mem.recuperar_con_decaimiento("c1")
check("graduada alimenta el prior",
      "a1" in [a for a, _, _ in rec])

# 4. Evicción: archiva primero lo en cuarentena (aunque sea útil).
id3 = registrar_exp(mem, "c1", "a3", 1.0)
mem.registrar_uso(id3, 1.0)  # utilidad alta
proc.registrar(id3, "importado")
archivadas = mem.aplicar_eviccion(2)
check("eviccion prioriza cuarentena", id3 in archivadas
      and id1 not in archivadas and id2 not in archivadas)

# 5. Legado sin registro → tratado como propio (documentado).
id4 = registrar_exp(mem, "c1", "a4", 1.0)
check("legado sin registro no en cuarentena",
      not proc.en_cuarentena(id4) and proc.origen_de(id4) == "propio")

# 6. Origen inválido → ValueError.
try:
    proc.registrar(id4, "marciano")
    check("origen invalido rechazado", False)
except ValueError:
    check("origen invalido rechazado", True)

# 7. Skills: importado nace en cuarentena; habilitadas filtra.
ps = ProcedenciaSkills(os.path.join(d, "conf.db"))
ps.registrar("/skills/a/SKILL.md", "propio")
ps.registrar("/skills/b/SKILL.md", "importado")
check("skill importada en cuarentena",
      ps.en_cuarentena("/skills/b/SKILL.md"))
hab = ps.habilitadas(["/skills/a/SKILL.md", "/skills/b/SKILL.md"])
check("habilitadas filtra cuarentena", hab == ["/skills/a/SKILL.md"])
ps.graduar("/skills/b/SKILL.md")
check("skill graduada habilitada",
      ps.habilitadas(["/skills/b/SKILL.md"]) == ["/skills/b/SKILL.md"])

n_fails = sum(1 for _, c in CHECKS if not c)
print(f"\n{len(CHECKS) - n_fails}/{len(CHECKS)} checks en verde")
sys.exit(1 if n_fails else 0)
