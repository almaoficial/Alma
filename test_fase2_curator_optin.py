"""Tests fase 2: consolidación LLM del Curator — opt-in APAGADA por default.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase2_curator_optin.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.curator import (
    consolidar_llm, ConsolidacionNoHabilitada, Curator)
from alma_service.skills import SkillIndex

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def main():
    d = tempfile.mkdtemp(prefix="alma_fase2_cur_")
    idx = SkillIndex(os.path.join(d, "skills-indice.db"))
    cur = Curator(idx, ledger_path=os.path.join(d, "curator-ledger.jsonl"))
    os.environ.pop("ALMA_CURATOR_LLM", None)

    # 1. Por default corta.
    try:
        consolidar_llm(cur)
        check("default corta", False)
    except ConsolidacionNoHabilitada:
        check("default corta", True)

    # 2. Con env=1 pero sin proveedor: también corta (nada que consolidar).
    os.environ["ALMA_CURATOR_LLM"] = "1"
    try:
        consolidar_llm(cur)
        check("opt-in sin proveedor corta", False)
    except ConsolidacionNoHabilitada:
        check("opt-in sin proveedor corta", True)
    os.environ.pop("ALMA_CURATOR_LLM", None)

    # 3. El barrido determinista sigue funcionando (correr_ciclo).
    check("correr_ciclo existe y corre",
          isinstance(cur.correr_ciclo(), list))

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
