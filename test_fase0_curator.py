"""Tests fase 0: Curator — ciclo de vida determinista, sin LLM.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase0_curator.py
"""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.curator import Curator, LedgerCurator, CURABLES
from alma_service.skills import SkillIndex

PASSOS = []
SKILL_MD = """---
name: {name}
description: Skill de prueba del curator.
created_by: {created_by}
---

# cuerpo
"""


def check(nombre, cond):
    PASSOS.append(cond)
    print(("PASS" if cond else "FAIL"), "-", nombre)


def montar(n=3, created_by="agent", horas_uso=None):
    tmp = tempfile.mkdtemp()
    idx = SkillIndex(os.path.join(tmp, "skills.sqlite"))
    paths = []
    ahora = time.time()
    for i in range(n):
        d = os.path.join(tmp, "skills", "cat", f"skill-{i}")
        os.makedirs(d)
        p = os.path.join(d, "SKILL.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(SKILL_MD.format(name=f"skill-{i}",
                                    created_by=created_by))
        from alma_service.skills import cargar_skill
        idx.registrar(cargar_skill(p), presupuesto_tokens=100_000)
        # simula creación/último uso hace `horas_uso` horas
        h = horas_uso[i] if horas_uso else 1
        ts = ahora - h * 3600.0
        idx._db.execute(
            "UPDATE skills SET created_at=?, last_used_at=? WHERE path=?",
            (ts, ts, p))
        idx._db.commit()
        paths.append(p)
    cur = Curator(idx, ledger_path=os.path.join(tmp, "ledger.jsonl"))
    return idx, cur, paths, ahora


def test_active_a_stale():
    idx, cur, paths, ahora = montar(n=2, horas_uso=[24 * 20, 1])
    tr = cur.barrer(ahora=ahora)
    check("una transición active→stale",
          len(tr) == 1 and tr[0]["hacia"] == "stale"
          and tr[0]["desde"] == "active")
    check("el índice refleja el cambio",
          len(idx.listar("stale")) == 1 and len(idx.listar("active")) == 1)
    activa = idx.listar("active")
    check("la recién usada queda active", len(activa) == 1)
    check("ledger verificable", cur.ledger.verificar())
    idx.close()


def test_stale_a_archived():
    idx, cur, paths, ahora = montar(n=1, horas_uso=[24 * 40])
    idx.transicionar(paths[0], "stale")
    tr = cur.barrer(ahora=ahora)
    check("transición stale→archived",
          len(tr) == 1 and tr[0]["hacia"] == "archived")
    check("archivar no borra del índice",
          idx.listar("archived") != [])
    check("ledger intacto tras 2 barridos", cur.ledger.verificar())
    idx.close()


def test_no_toca_externas():
    idx, cur, paths, ahora = montar(n=2, created_by="externo",
                                    horas_uso=[24 * 60, 24 * 60])
    tr = cur.barrer(ahora=ahora)
    check("Curator no toca skills externas", tr == [])
    check("las externas siguen active",
          len(idx.listar("active")) == 2)
    idx.close()


def test_determinismo():
    idx, cur, paths, ahora = montar(n=1, horas_uso=[24 * 20])
    tr1 = cur.barrer(ahora=ahora)
    tr2 = cur.barrer(ahora=ahora)  # idempotente: ya es stale
    check("segundo barrido no duplica", len(tr1) == 1 and len(tr2) == 0)
    evs = cur.ledger.leer()
    check("ledger con 1 evento", len(evs) == 1
          and evs[0]["evento"]["hacia"] == "stale")
    check("hash encadenado", evs[0]["prev_hash"] == "GENESIS")
    idx.close()


if __name__ == "__main__":
    test_active_a_stale()
    test_stale_a_archived()
    test_no_toca_externas()
    test_determinismo()
    sys.exit(0 if all(PASSOS) else 1)
