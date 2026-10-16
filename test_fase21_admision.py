"""Tests fase 2.1: pipeline de admisión por etapas (OpenSpace).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase21_admision.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.admision import (
    PipelineAdmision, ETAPA_RECHAZADA, ETAPA_VALIDACION_FALLIDA,
    ETAPA_COMMITTED)
from alma_service.skills import SkillIndex
from alma_service.confianza import ConfianzaSkills, CONFIANZA_PROVISIONAL
from alma_service.versiones import VersionadorSkills, TIPO_CAPTURED

PASSOS = []

SKILL_OK = """---
name: skill-admision-test
description: Skill de prueba del pipeline de admisión.
---
# Skill de prueba

Contenido mínimo válido para el pipeline.
"""

SKILL_MALA = "esto no es un SKILL.md válido"


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def nuevo_pipeline(d):
    ledger = []
    idx = SkillIndex(os.path.join(d, "skills-indice.db"))
    conf = ConfianzaSkills(os.path.join(d, "confianza.db"))
    ver = VersionadorSkills(os.path.join(d, "versiones.db"))
    pa = PipelineAdmision(
        os.path.join(d, "admision.db"),
        skills_dir=os.path.join(d, "skills"),
        skill_index=idx, confianza=conf, versionador=ver,
        registrar_ledger=ledger.append)
    return pa, idx, conf, ver, ledger


def main():
    # 1. Pipeline completo: propuesta→evidencia→decisión→validación→commit.
    d = tempfile.mkdtemp(prefix="alma_fase21_adm_")
    pa, idx, conf, ver, ledger = nuevo_pipeline(d)
    r = pa.proponer("skill-admision-test", "desc", SKILL_OK)
    cid = r["id"]
    check("proponer crea caso en etapa propuesta", r["etapa"] == "propuesta")
    r = pa.adjuntar_evidencia(cid, {"observacion": "3 fallos con firma X"})
    check("evidencia mueve de etapa", r["etapa"] == "evidencia")
    r = pa.decidir(cid, True, motivo="evidencia sólida")
    check("decidir True → staging (gate humano)", r["etapa"] == "staging")
    r = pa.validar(cid)
    check("validar ok con SKILL.md válido",
          r["ok"] is True and r["etapa"] == "validacion_ok"
          and all(c["ok"] for c in r["checks"]))
    r = pa.commit(cid)
    check("commit admite la skill",
          r["etapa"] == ETAPA_COMMITTED and r["path"].endswith("SKILL.md"))
    check("SKILL.md escrito en disco", os.path.exists(r["path"]))
    check("registrada en el índice",
          any(s["name"] == "skill-admision-test" for s in idx.listar()))
    check("nace PROVISIONAL (trust no se hereda ni se otorga)",
          conf.confianza_de(r["path"]) == CONFIANZA_PROVISIONAL)
    hist = ver.historial(r["path"])
    check("abre versión CAPTURED en el DAG",
          len(hist) == 1 and hist[0]["tipo"] == TIPO_CAPTURED)
    tipos = [e["tipo"] for e in ledger]
    check("ledger audita las etapas",
          {"admision_propuesta", "admision_evidencia", "admision_decision",
           "admision_validacion", "admision_commit"} <= set(tipos))
    check("commit saca de pendientes",
          not any(p["id"] == cid for p in pa.pendientes()))

    # 2. Rechazo humano: terminal, nada se aplica.
    d2 = tempfile.mkdtemp(prefix="alma_fase21_adm2_")
    pa2, idx2, _c2, _v2, _l2 = nuevo_pipeline(d2)
    c2 = pa2.proponer("skill-rechazada", "desc", SKILL_OK)["id"]
    pa2.adjuntar_evidencia(c2, {"observacion": "débil"})
    r = pa2.decidir(c2, False, motivo="no convence")
    check("decidir False → rechazada*", r["etapa"] == ETAPA_RECHAZADA)
    try:
        pa2.validar(c2)
        sigue = False
    except ValueError:
        sigue = True
    check("rechazada no avanza a validación", sigue)
    check("rechazada no escribe SKILL.md",
          not os.path.exists(os.path.join(d2, "skills", "skill-rechazada",
                                          "SKILL.md")))

    # 3. Validación determinista rechaza contenido inválido.
    d3 = tempfile.mkdtemp(prefix="alma_fase21_adm3_")
    pa3, _i3, _c3, _v3, _l3 = nuevo_pipeline(d3)
    c3 = pa3.proponer("skill-mala", "desc", SKILL_MALA)["id"]
    pa3.adjuntar_evidencia(c3, {"observacion": "x"})
    pa3.decidir(c3, True)
    r = pa3.validar(c3)
    check("SKILL.md inválido → validacion_fallida*",
          r["ok"] is False and r["etapa"] == ETAPA_VALIDACION_FALLIDA
          and r["checks"][0]["check"] == "skllmd_parsea")
    try:
        pa3.commit(c3)
        pudo = True
    except ValueError:
        pudo = False
    check("validación fallida no hace commit", not pudo)

    # 4. Orden de etapas estricto.
    d4 = tempfile.mkdtemp(prefix="alma_fase21_adm4_")
    pa4, _i4, _c4, _v4, _l4 = nuevo_pipeline(d4)
    c4 = pa4.proponer("skill-orden", "desc", SKILL_OK)["id"]
    try:
        pa4.decidir(c4, True)  # salta evidencia
        salto = True
    except ValueError:
        salto = False
    check("no se puede decidir sin evidencia", not salto)
    check("pendientes lista etapas no terminales",
          any(p["id"] == c4 for p in pa4.pendientes()))

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
