"""Tests EXP78 — 4 patrones Forge/Agent Lens en ALMA (US$0).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_exp78_forge.py

Patrón 1 (esquema_traza): schema único TRACE_SCHEMA v1 que toda corrida
    emite; conversores desde_handoff/desde_adopcion; TraceLog persiste.
Patrón 2 (casos_fallo): el fallo de una candidata se archiva como caso
    de regresión; futuras candidatas se chequean contra la librería y
    se re-evalúan en las semillas archivadas (EXP76 se endurece).
Patrón 3 (torneo): campeón vs candidatas con el validador congelado.
Patrón 4 (versiones+lineage): asentar_con_linaje versiona con lineage
    explícito (split, Δ, regla, fecha); el DAG existente no cambia.

Cero gasto de API (todo mock determinista). DBs en /tmp.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.esquema_traza import (
    TRACE_SCHEMA_ID, validar_trace, nueva_traza, desde_handoff,
    desde_adopcion, TraceLog)
from alma_service.casos_fallo import BibliotecaFallos
from alma_service.torneo import Torneo
from alma_service import versiones as V
VersionadorSkills = V.VersionadorSkills
TIPO_CAPTURED = V.TIPO_CAPTURED
from alma_service.handoff import (
    probar_handoff, evaluar_skill_para_adopcion, REGLA_HANDOFF)
from alma_service.scaffold import DEFAULT_SCAFFOLD

PASSOS = []


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
    "(a, b, c, d, e, f)",
    "Interna: llamar al transformador con seis parámetros en orden.")


def tmpdb(nombre):
    d = tempfile.mkdtemp(prefix="alma_exp78_")
    return os.path.join(d, nombre)


def traza_base(**kw):
    base = {
        "origen": "handoff",
        "propuesta": {"id": "s1", "descripcion": "d", "tipo": "skill"},
        "split": {"nombre": "down+ref", "seed": {"down": 1, "ref": 2}},
        "metricas": {"delta_down": 0.36},
        "veredicto": {"decision": "aceptado", "motivo": "m",
                      "regla": REGLA_HANDOFF},
        "lineage": {"producido_por": "exp76", "version": 1,
                    "padre": None},
    }
    base.update(kw)
    return nueva_traza(**base)


def main():
    # ============ Patrón 1: schema único de traces ============
    t = traza_base()
    check("p1: traza válida pasa validar_trace",
          validar_trace(t) == [] and t["schema"] == TRACE_SCHEMA_ID)
    mala = dict(t)
    del mala["metricas"]
    check("p1: falta campo -> error",
          any("metricas" in e for e in validar_trace(mala)))
    check("p1: origen inválido -> error",
          validar_trace({**t, "origen": "ovni"}) != [])
    check("p1: veredicto inválido -> error",
          validar_trace({**t, "veredicto": {"decision": "quizas",
                                            "motivo": "", "regla": ""}})
          != [])
    check("p1: costo negativo -> error",
          validar_trace({**t, "costo_usd": -1.0}) != [])
    try:
        nueva_traza(origen="handoff", propuesta={}, split={},
                    metricas={}, veredicto={}, lineage={})
        ok = False
    except ValueError:
        ok = True
    check("p1: nueva_traza malformada levanta (fail-closed)", ok)

    # Conversor desde_handoff con un rechazo real.
    rej = evaluar_skill_para_adopcion("mala", MALA_MD, ayuda=0.10,
                                      rigidez=0.90)
    check("p1: fixture mala es rechazada", rej["aceptada"] is False)
    th = desde_handoff(rej["evidencia"]["handoff"])
    check("p1: desde_handoff -> traza válida",
          validar_trace(th) == [] and th["origen"] == "handoff")
    check("p1: desde_handoff refleja el rechazo",
          th["veredicto"]["decision"] == "rechazado"
          and th["metricas"]["delta_down"] == rej["delta_down"])
    ok2 = evaluar_skill_para_adopcion("buena", BUENA_MD, ayuda=0.80,
                                      rigidez=0.10)
    check("p1: fixture buena es aceptada", ok2["aceptada"] is True)
    th2 = desde_handoff(ok2["evidencia"]["handoff"])
    check("p1: desde_handoff refleja la aceptación",
          th2["veredicto"]["decision"] == "aceptado")

    # Conversor desde_adopcion.
    adop = {"adoptada": True, "id": 7, "diff": {"x": [1, 2]},
            "efecto_medido": {"delta_ho": 0.05, "delta_in": 0.01}}
    ta = desde_adopcion(adop, motivo_puerta="m", regla="r")
    check("p1: desde_adopcion -> traza válida",
          validar_trace(ta) == [] and ta["origen"] == "metaloop"
          and ta["metricas"]["delta_ho"] == 0.05)

    # TraceLog: roundtrip + fail-closed.
    tl = TraceLog(tmpdb("traces.db"))
    id1 = tl.emitir(t)
    id2 = tl.emitir(th)
    leidas = tl.leer()
    check("p1: TraceLog roundtrip",
          len(leidas) == 2 and leidas[0]["trace"]["schema"]
          == TRACE_SCHEMA_ID and leidas[0]["id"] == id1)
    check("p1: TraceLog filtra por origen",
          len(tl.leer(origen="handoff")) == 2
          and len(tl.leer(origen="metaloop")) == 0)
    try:
        tl.emitir({"schema": "nope"})
        ok3 = False
    except ValueError:
        ok3 = True
    check("p1: TraceLog rechaza traza inválida", ok3)
    est = tl.estado()
    check("p1: estado reporta conteos",
          est["trazas"] == 2 and est["por_origen"]["handoff"] == 2)

    # ============ Patrón 2: trace -> task ============
    bib = BibliotecaFallos(tmpdb("fallos.db"))
    try:
        bib.archivar_fallo(ok2)  # aceptada -> no se archiva
        ok4 = False
    except ValueError:
        ok4 = True
    check("p2: archivar aceptación levanta (fail-closed)", ok4)
    rej2 = evaluar_skill_para_adopcion("mala2", MALA_MD, ayuda=0.05,
                                       rigidez=0.95,
                                       seed_down=7701, seed_ref=7702)
    check("p2: fixture mala2 rechazada", rej2["aceptada"] is False)
    idf1 = bib.archivar_fallo(rej)
    idf2 = bib.archivar_fallo(rej2)
    check("p2: 2 fallos archivados",
          len(bib.casos()) == 2 and idf2 > idf1)
    check("p2: semillas distintas registradas",
          bib.semillas() == [(7601, 7602), (7701, 7702)])
    chk = bib.chequear_candidata(delta_down_cand=0.36)
    check("p2: candidata buena bate los fallos", chk["pasa"] is True)
    chk2 = bib.chequear_candidata(delta_down_cand=-0.70)
    check("p2: candidata peor que un fallo no pasa",
          chk2["pasa"] is False and "no bate" in chk2["motivo"])
    # -0.5 bate a ambos fallos (-0.6603, -0.624): pasa, como debe.
    chk3 = bib.chequear_candidata(delta_down_cand=-0.5)
    check("p2: candidata que bate los fallos pasa",
          chk3["pasa"] is True)
    # Endurecimiento: la candidata buena se re-evalúa en las semillas
    # de los fallos archivados.
    itf_buena = {"nombre": "resume_claro",
                 "descripcion": BUENA_MD.split("description: ")[1]
                 .split("\n")[0],
                 "firma": "(texto, n)"}
    evh = bib.evaluar_en_historial(probar_handoff, itf_buena,
                                   ayuda=0.80, rigidez=0.10)
    check("p2: evaluar_en_historial corre en las N semillas",
          evh["n_evaluaciones"] == 2
          and all("delta_down" in e for e in evh["evaluaciones"]))
    check("p2: candidata buena sobrevive al historial",
          evh["pasa"] is True)
    # Y una mala no sobrevive.
    itf_mala = {"nombre": "envuelve_rigido", "descripcion": "x" * 200,
                "firma": "(a, b, c, d, e, f)"}
    evh2 = bib.evaluar_en_historial(probar_handoff, itf_mala,
                                    ayuda=0.05, rigidez=0.95)
    check("p2: candidata mala no sobrevive al historial",
          evh2["pasa"] is False)
    check("p2: estado reporta casos y semillas",
          bib.estado()["casos_archivados"] == 2)

    # ============ Patrón 3: torneo campeón vs candidatas ============
    tor = Torneo(tmpdb("torneo.db"))
    clon = dict(DEFAULT_SCAFFOLD)
    tweak = dict(DEFAULT_SCAFFOLD)
    tweak["umbral_base"] = tweak["umbral_base"] * 1.5
    res = tor.correr(DEFAULT_SCAFFOLD,
                     [("clon", clon), ("tweak_umbral", tweak)])
    check("p3: torneo corre y reporta por candidata",
          res["aceptado"] is True and len(res["resultados"]) == 2)
    r_clon = [r for r in res["resultados"]
              if r["candidata"] == "clon"][0]
    check("p3: clon del campeón empata (mejora 0)",
          r_clon["mejora"] == 0.0 and r_clon["gana"] is False)
    r_tweak = [r for r in res["resultados"]
               if r["candidata"] == "tweak_umbral"][0]
    check("p3: tweak queda registrado con mejora numérica",
          isinstance(r_tweak["mejora"], float)
          and isinstance(r_tweak["gana"], bool))
    check("p3: historial persiste",
          len(tor.historial()) == 2)
    check("p3: campeon_actual None si nadie ganó",
          tor.campeon_actual() is None)
    # Camino positivo: fila ganadora insertada a mano (DB de test).
    import sqlite3
    con = sqlite3.connect(tor.db_path)
    con.execute(
        "INSERT INTO torneo_corridas (ts, candidata,"
        " scaffold_campeon_json, scaffold_candidata_json, reg_campeon,"
        " reg_candidata, mejora, n_replicas, detalle_json)"
        " VALUES (1,'ganadora','{}','{}',10.0,9.0,1.0,5,'{}')")
    con.commit()
    con.close()
    ca = tor.campeon_actual()
    check("p3: campeon_actual detecta a la ganadora",
          ca is not None and ca["candidata"] == "ganadora"
          and ca["mejora"] == 1.0)
    check("p3: estado reporta enfrentamientos",
          tor.estado()["enfrentamientos"] == 3)

    # ============ Patrón 4: registry con lineage ============
    ver = V.VersionadorSkills(tmpdb("versiones.db"))
    lin = {"split_nombre": "handoff:downstream+referencia",
           "split_seed": {"down": 7601, "ref": 7602},
           "delta_down": 0.3636, "delta_ref": 0.02,
           "regla": REGLA_HANDOFF, "fuente": "exp76_puerta_handoff"}
    a1 = ver.asentar_con_linaje("skills/x/resume/SKILL.md",
                                TIPO_CAPTURED, None,
                                "captura desde ejecución", {}, lin)
    check("p4: asentar_con_linaje versiona",
          a1["version"] == 1 and a1["tipo"] == TIPO_CAPTURED)
    lj = ver.linaje("skills/x/resume/SKILL.md")
    check("p4: linaje legible con split/Δ/regla",
          len(lj) == 1 and lj[0]["split_nombre"].startswith("handoff")
          and lj[0]["delta_down"] == 0.3636
          and lj[0]["regla"] == REGLA_HANDOFF
          and lj[0]["fuente"] == "exp76_puerta_handoff")
    check("p4: cadena de hash intacta tras lineage",
          ver.verificar_cadena("skills/x/resume/SKILL.md") is True)
    # Lineage incompleto: fail-closed, no escribe versión.
    try:
        ver.asentar_con_linaje("skills/x/otra/SKILL.md", TIPO_CAPTURED,
                               None, "d", {}, {"split_nombre": "s"})
        ok5 = False
    except ValueError:
        ok5 = True
    check("p4: lineage incompleto corta sin escribir",
          ok5 and ver.historial("skills/x/otra/SKILL.md") == [])
    # El camino viejo sigue sin lineage (no rompe nada existente).
    ver.fix("skills/x/resume/SKILL.md", "repara typo", {})
    check("p4: fix() clásico sigue funcionando",
          ver.historial("skills/x/resume/SKILL.md")[-1]["version"] == 2
          and len(ver.linaje("skills/x/resume/SKILL.md")) == 1)
    # linaje_desde_handoff: del record real al lineage.
    lin2 = V.linaje_desde_handoff(ok2)
    check("p4: linaje_desde_handoff extrae del record",
          lin2["regla"] == REGLA_HANDOFF
          and lin2["delta_down"] == ok2["delta_down"]
          and lin2["fuente"] == "exp76_puerta_handoff"
          and lin2["split_seed"] == {"down": 7601, "ref": 7602})
    a2 = ver.asentar_con_linaje("skills/x/buena/SKILL.md",
                                TIPO_CAPTURED, None,
                                "skill aceptada por handoff", {},
                                lin2)
    check("p4: lineage del handoff se asienta",
          a2["lineage"]["delta_down"] == ok2["delta_down"]
          and ver.linaje("skills/x/buena/SKILL.md",
                         version=1)[0]["regla"] == REGLA_HANDOFF)

    # ============ Integración: los 4 patrones juntos ============
    # rechazo -> caso archivado -> traza unificada -> lineage de la
    # aceptada. Todo con los mismos números, sin divergencias.
    bib2 = BibliotecaFallos(tmpdb("f2.db"))
    tl2 = TraceLog(tmpdb("t2.db"))
    ver2 = V.VersionadorSkills(tmpdb("v2.db"))
    rj = evaluar_skill_para_adopcion("m", MALA_MD, 0.10, 0.90)
    bib2.archivar_fallo(rj)
    tr = desde_handoff(rj["evidencia"]["handoff"], entorno="mock")
    tid = tl2.emitir(tr)
    ac = evaluar_skill_para_adopcion("b", BUENA_MD, 0.80, 0.10)
    ver2.asentar_con_linaje("skills/x/b/SKILL.md", TIPO_CAPTURED, None,
                            "aceptada", {}, V.linaje_desde_handoff(ac))
    check("p-int: pipeline completo consistente",
          bib2.estado()["casos_archivados"] == 1
          and tl2.estado()["trazas"] == 1
          and tid > 0
          and ver2.linaje("skills/x/b/SKILL.md")[0]["delta_down"]
          == ac["delta_down"]
          and bib2.casos()[0]["delta_down"] == rj["delta_down"])

    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")


if __name__ == "__main__":
    main()
