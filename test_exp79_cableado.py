"""Tests EXP79 — cableado Forge -> servicio en vivo (US$0).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_exp79_cableado.py

Cableado (alma_service/cableado_forge.py, aprobado por el usuario 1/10):
  1. evaluar_skill_para_adopcion_con_traza(): la puerta decide igual
     (handoff.py intacto); tras el veredicto emite traza unificada,
     archiva el rechazo en BibliotecaFallos, y asienta lineage si hubo
     adopción. Todo best-effort: un fallo del cableado no altera el
     veredicto.
  2. correr_torneo_semanal(): campeón (scaffold vigente) vs candidatas
     de staging, con validador congelado; emite traza origen="torneo".
  3. Endpoint POST /fase2/torneo/semanal en servicio/server.py.

Cero gasto de API (todo mock determinista). DBs en /tmp.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.cableado_forge import (
    evaluar_skill_para_adopcion_con_traza,
    correr_torneo_semanal,
)
from alma_service.esquema_traza import TraceLog, validar_trace
from alma_service.casos_fallo import BibliotecaFallos
from alma_service.torneo import Torneo
from alma_service.versiones import VersionadorSkills
from alma_service.handoff import evaluar_skill_para_adopcion
from alma_service.scaffold import DEFAULT_SCAFFOLD

PASSOS = []
_TMP = tempfile.mkdtemp(prefix="exp79_")


def tmpdb(nombre):
    return os.path.join(_TMP, nombre)


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def skill_md(nombre, descripcion, firma, cuerpo):
    return (f"---\nname: {nombre}\ndescription: {descripcion}\n"
            f"firma: {firma}\n---\n{cuerpo}\n")


BUENA_MD = skill_md(
    "resume_claro",
    "Resume un texto en N frases. Ejemplo: resume_claro('texto', 3)"
    " -> ['f1', 'f2', 'f3'].",
    "(texto, n)",
    "Interna: partir en oraciones, rankear por similitud, top N.")
MALA_MD = skill_md(
    "envuelve_rigido",
    "Esta skill provee una envoltura genérica y comprehensiva para"
    " diversos tipos de transformaciones de contenido textual y"
    " estructurado considerando múltiples dimensiones de configuración"
    " opcional y extensible para casos de uso variados y heterogéneos.",
    "(x)",
    "Interna: envolver.")


def _modulos(suf):
    return (TraceLog(tmpdb(f"traces_{suf}.db")),
            BibliotecaFallos(tmpdb(f"fallos_{suf}.db")),
            VersionadorSkills(tmpdb(f"versiones_{suf}.db")))


def t_wrapper_rechazo():
    tl, bib, reg = _modulos("rej")
    v = evaluar_skill_para_adopcion_con_traza(
        "mala", MALA_MD, ayuda=0.10, rigidez=0.90,
        tracelog=tl, biblioteca=bib, registro=reg)
    directo = evaluar_skill_para_adopcion(
        "mala", MALA_MD, ayuda=0.10, rigidez=0.90)
    check("w1: veredicto intacto (rechazo)",
          v["aceptada"] is False
          and v["aceptada"] == directo["aceptada"]
          and v["delta_down"] == directo["delta_down"]
          and v["motivo"] == directo["motivo"])
    cab = v["cableado"]
    check("w1: traza emitida", bool(cab["traza_emitida"])
          and not cab["errores"])
    trazas = tl.leer(origen="handoff")
    check("w1: traza unificada del rechazo",
          len(trazas) == 1
          and validar_trace(trazas[0]["trace"]) == []
          and trazas[0]["trace"]["veredicto"]["decision"] == "rechazado")
    check("w1: fallo archivado en biblioteca",
          bool(cab["fallo_archivado"]) and len(bib.casos()) == 1)
    check("w1: sin lineage en rechazo",
          cab["lineage_asentado"] is False
          and reg.linaje("skills/mala.md") == [])


def t_wrapper_aceptacion():
    tl, bib, reg = _modulos("acep")
    adop = {"adoptada": True, "id": 3, "diff": {"k": [1, 2]},
            "efecto_medido": {"delta_ho": 0.05, "delta_in": 0.01}}
    v = evaluar_skill_para_adopcion_con_traza(
        "buena", BUENA_MD, ayuda=0.80, rigidez=0.10,
        adoptar_fn=lambda deltas, ev: adop,
        tracelog=tl, biblioteca=bib, registro=reg)
    check("w2: aceptada y adoptada via fn",
          v["aceptada"] is True and v["adoptada_via_fn"] is True)
    cab = v["cableado"]
    trazas = tl.leer(origen="handoff")
    check("w2: traza unificada de la aceptación",
          bool(cab["traza_emitida"]) and len(trazas) == 1
          and trazas[0]["trace"]["veredicto"]["decision"] == "aceptado")
    check("w2: rechazo no archiva (biblioteca vacía)",
          len(bib.casos()) == 0 and cab["fallo_archivado"] is False)
    lin = reg.linaje("skills/buena.md")
    check("w2: lineage asentado con split del handoff",
          bool(cab["lineage_asentado"]) and len(lin) == 1
          and lin[0]["split_nombre"] == "handoff:downstream+referencia"
          and lin[0]["delta_down"] == v["delta_down"])
    check("w2: cadena del DAG verifica",
          reg.verificar_cadena("skills/buena.md"))


def t_wrapper_failsafe():
    class Roto:
        def emitir(self, t):
            raise RuntimeError("db caída")

    _, bib, _ = _modulos("fs")
    v = evaluar_skill_para_adopcion_con_traza(
        "mala", MALA_MD, ayuda=0.10, rigidez=0.90,
        tracelog=Roto(), biblioteca=bib, registro=None)
    check("w3: veredicto intacto aunque falle la traza",
          v["aceptada"] is False and v["delta_down"] < 0)
    cab = v["cableado"]
    check("w3: error registrado, resto del cableado sigue",
          len(cab["errores"]) == 1 and "traza" in cab["errores"][0]
          and bool(cab["fallo_archivado"]))


def t_wrapper_sin_modulos():
    v = evaluar_skill_para_adopcion_con_traza(
        "buena", BUENA_MD, ayuda=0.80, rigidez=0.10)
    directo = evaluar_skill_para_adopcion(
        "buena", BUENA_MD, ayuda=0.80, rigidez=0.10)
    check("w4: sin módulos el wrapper es la puerta pelada",
          v["aceptada"] == directo["aceptada"]
          and v["cableado"] == {"traza_emitida": False,
                                "fallo_archivado": False,
                                "lineage_asentado": False,
                                "errores": []})


class _FakeMetaLoop:
    def __init__(self, scaffold):
        self._sc = scaffold

    def scaffold_vigente(self):
        return self._sc


class _FakePromotor:
    def __init__(self, pendiente):
        self._pend = pendiente

    def pendiente(self):
        return self._pend


def t_torneo_sin_campeon():
    r = correr_torneo_semanal(_FakeMetaLoop(None), _FakePromotor(None))
    check("t1: sin campeón no corre",
          r["corrio"] is False and "scaffold" in r["motivo"])


def t_torneo_sin_candidatas():
    r = correr_torneo_semanal(_FakeMetaLoop(dict(DEFAULT_SCAFFOLD)),
                              _FakePromotor(None))
    check("t2: sin candidatas no corre",
          r["corrio"] is False and "staging" in r["motivo"])


def t_torneo_corre():
    campeon = dict(DEFAULT_SCAFFOLD)
    cand = dict(DEFAULT_SCAFFOLD)
    cand["gate_margin"] = float(cand["gate_margin"]) + 0.01
    prom = _FakePromotor({"id": 9, "scaffold_despues": cand})
    tl = TraceLog(tmpdb("traces_torneo.db"))
    tor = Torneo(tmpdb("torneo.db"))
    r = correr_torneo_semanal(_FakeMetaLoop(campeon), prom,
                              torneo=tor, tracelog=tl,
                              bloqueante=True)
    check("t3: torneo corre campeón vs staging",
          r["corrio"] is True and r["candidatas"] == ["staging-9"]
          and len(r["resultados"]) == 1
          and set(r["resultados"][0]) >= {"mejora", "gana"})
    tr = tl.leer(origen="torneo")
    check("t3: traza unificada del torneo",
          len(tr) == 1 and validar_trace(tr[0]["trace"]) == []
          and tr[0]["trace"]["metricas"]["n_candidatas"] == 1.0)
    check("t3: historial del torneo registra el enfrentamiento",
          len(tor.historial()) == 1)


def t_endpoint_server():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "servicio", "server.py"),
               encoding="utf-8").read()
    check("e1: endpoint /fase2/torneo/semanal en server.py",
          '"/fase2/torneo/semanal"' in src
          and "correr_torneo_semanal" in src)


if __name__ == "__main__":
    t_wrapper_rechazo()
    t_wrapper_aceptacion()
    t_wrapper_failsafe()
    t_wrapper_sin_modulos()
    t_torneo_sin_campeon()
    t_torneo_sin_candidatas()
    t_torneo_corre()
    t_endpoint_server()
    n_ok = sum(1 for p in PASSOS if p)
    print(f"\n{PASSOS.count(True)}/{len(PASSOS)} PASS")
    if not all(PASSOS):
        raise SystemExit(1)
