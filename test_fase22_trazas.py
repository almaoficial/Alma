"""Tests fase 2.2: trazas unificadas — event log del servicio.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase22_trazas.py

Verifica:
1. EventLog: round-trip de decisiones (contrato §4.1) y eventos de ciclo.
2. actualizar_reward: el feedback completa el reward a posteriori.
3. Puente minero: firmas (firma_regimen, brazo, tramo) sobre operación
   real; solo eventos con reward medido.
4. rotar(): retención determinista.
5. Instrumentación del Motor: resolver() asienta la decisión sin cambiar
   su respuesta; feedback() completa el reward. Con trazas=None no
   cambia nada (fail-safe).
6. Meta-loop, Curator y revisión emiten eventos de ciclo al log.
"""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.trazas import EventLog
from alma_service.debilidades import (
    firma_decision, minar_decisiones, MineroDebilidades)

PASSOS = []
TMP = tempfile.mkdtemp()


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def test_event_log_decisiones():
    log = EventLog(os.path.join(TMP, "ev1.db"))
    eid = log.asentar_decision(
        firma_regimen="aritmetica", brazo_elegido="cot", reward=0.8,
        costo_usd=0.001, latencia_ms=12.5, scaffold_version="abc123",
        veredicto_probe="cot", modo="probe",
        backend_efectivo="demo_forzado_modo_barato",
        extras={"gap": 0.3})
    check("asentar_decision retorna id", isinstance(eid, int) and eid > 0)
    ds = log.decisiones()
    check("decisiones round-trip: 1 evento", len(ds) == 1)
    d = ds[0]
    check("contrato §4.1 completo",
          d["firma_regimen"] == "aritmetica"
          and d["veredicto_probe"] == "cot"
          and d["brazo_elegido"] == "cot"
          and d["reward"] == 0.8
          and d["costo_usd"] == 0.001
          and d["latencia_ms"] == 12.5
          and d["scaffold_version"] == "abc123"
          and d["modo"] == "probe"
          and d["backend_efectivo"] == "demo_forzado_modo_barato"
          and d["extras"]["gap"] == 0.3
          and d["ts"] > 0)
    check("filtro por firma_regimen",
          len(log.decisiones(firma_regimen="otra")) == 0
          and len(log.decisiones(firma_regimen="aritmetica")) == 1)


def test_actualizar_reward():
    log = EventLog(os.path.join(TMP, "ev2.db"))
    eid = log.asentar_decision(firma_regimen="x", brazo_elegido="single")
    check("sin reward: no la ve el minero",
          log.decisiones(con_reward=True) == [])
    check("actualizar_reward ok", log.actualizar_reward(eid, 0.9) is True)
    ds = log.decisiones(con_reward=True)
    check("con reward medido: visible",
          len(ds) == 1 and ds[0]["reward"] == 0.9)
    check("actualizar_reward inexistente",
          log.actualizar_reward(999999, 0.5) is False)


def test_eventos_ciclo():
    log = EventLog(os.path.join(TMP, "ev3.db"))
    log.asentar_ciclo("metaloop_propuesta", "metaloop", {"clave": "n0"})
    log.asentar_ciclo("curator_transicion", "curator", {"skill": "s"})
    evs = log.ciclo()
    check("ciclo round-trip: 2 eventos", len(evs) == 2)
    check("filtro por tipo",
          len(log.ciclo(tipo="metaloop_propuesta")) == 1
          and log.ciclo(tipo="metaloop_propuesta")[0]["actor"] == "metaloop"
          and log.ciclo(tipo="metaloop_propuesta")[0]["detalle"]["clave"]
          == "n0")
    check("ciclo tipo inexistente", log.ciclo(tipo="zzz") == [])


def test_puente_minero():
    check("firma_decision fallo",
          firma_decision("arit", "cot", 0.2) == ("arit", "cot", "fallo"))
    check("firma_decision ok",
          firma_decision("arit", "cot", 0.8) == ("arit", "cot", "ok"))
    check("firma_decision sin reward no inventa",
          firma_decision("a", "b", None)[2] == "desconocido")
    filas = [
        {"firma_regimen": "arit", "brazo_elegido": "cot", "reward": 0.1},
        {"firma_regimen": "arit", "brazo_elegido": "cot", "reward": 0.2},
        {"firma_regimen": "arit", "brazo_elegido": "single",
         "reward": 0.9},
        {"firma_regimen": "arit", "brazo_elegido": "cot", "reward": None},
    ]
    ev = minar_decisiones(filas, minimo_soporte=2)
    check("minar_decisiones: cluster dominante",
          ev["clusters"][0]["firma"] == ["arit", "cot", "fallo"]
          and ev["clusters"][0]["n"] == 2)
    check("minar_decisiones: sin reward no entra",
          ev["total_firmas"] == 3)
    check("paquete descriptivo, no prescriptivo",
          "no prescriptivo" in ev["advertencia"])


def test_paquete_debilidades_end_to_end():
    log = EventLog(os.path.join(TMP, "ev4.db"))
    for _ in range(3):
        log.asentar_decision(firma_regimen="raz", brazo_elegido="cot",
                             reward=0.1)
    log.asentar_decision(firma_regimen="raz", brazo_elegido="single",
                         reward=0.95)
    log.asentar_decision(firma_regimen="raz", brazo_elegido="cot")  # sin r
    ev = log.paquete_debilidades(minimo_soporte=2)
    check("paquete_debilidades end-to-end",
          ev["clusters"][0]["firma"] == ["raz", "cot", "fallo"]
          and ev["total_firmas"] == 4)
    est = log.estado()
    check("estado del log",
          est["decisiones"] == 5 and est["decisiones_con_reward"] == 4)


def test_rotar():
    import sqlite3
    log = EventLog(os.path.join(TMP, "ev5.db"))
    log.asentar_decision(firma_regimen="a", brazo_elegido="single",
                         reward=0.5)
    log.asentar_decision(firma_regimen="b", brazo_elegido="cot", reward=0.5)
    log.asentar_ciclo("x", "metaloop", {})
    # envejece todo 40 días por SQL directo
    con = sqlite3.connect(os.path.join(TMP, "ev5.db"))
    viejo = time.time() - 40 * 86400.0
    con.execute("UPDATE eventos_decision SET ts=?", (viejo,))
    con.execute("UPDATE eventos_ciclo SET ts=?", (viejo,))
    con.commit()
    con.close()
    r = log.rotar(dias_decision=30, dias_ciclo=30)
    check("rotar borra lo viejo de ambas tablas",
          r == {"decisiones_borradas": 2, "ciclo_borrados": 1}
          and log.decisiones() == [] and log.ciclo() == [])
    log.asentar_decision(firma_regimen="nueva", brazo_elegido="single")
    r2 = log.rotar(dias_decision=30, dias_ciclo=30)
    check("rotar no toca lo nuevo",
          r2["decisiones_borradas"] == 0 and len(log.decisiones()) == 1)


def test_motor_instrumentacion():
    sys.path.insert(0, os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "servicio"))
    from servicio.motor import Motor
    db = os.path.join(TMP, "motor.db")
    log = EventLog(os.path.join(TMP, "ev6.db"))
    m = Motor(db)
    m.trazas = log
    m.version_scaffold_fn = lambda: {"n0": 4}
    r = m.resolver("¿cuánto es 2+2?", clase="aritmetica")
    check("resolver responde igual con trazas",
          r["clase"] == "aritmetica" and "brazo" in r
          and "respuesta" in r and "experiencia_id" in r)
    ds = log.decisiones()
    check("resolver asentó 1 decisión", len(ds) == 1)
    d = ds[0]
    check("traza con firma, brazo, latencia y versión",
          d["firma_regimen"] == "aritmetica"
          and d["brazo_elegido"] == r["brazo"]
          and d["latencia_ms"] is not None and d["latencia_ms"] >= 0
          and len(d["scaffold_version"]) == 12
          and d["modo"] == "thompson")
    check("backend efectivo registrado",
          d["backend_efectivo"] in ("demo", "demo_forzado_modo_barato",
                                    "vault", "openai"))
    fb = m.feedback(r["experiencia_id"], 0.9)
    check("feedback ok", fb["reward"] == 0.9)
    d2 = log.decisiones(con_reward=True)
    check("feedback completa el reward en la traza",
          len(d2) == 1 and abs(d2[0]["reward"] - 0.9) < 1e-9)
    # Sin trazas: el camino default no cambia ni rompe.
    m2 = Motor(os.path.join(TMP, "motor2.db"))
    r2 = m2.resolver("hola mundo")
    check("sin trazas: resolver igual",
          "brazo" in r2 and "respuesta" in r2)
    m2.feedback(r2["experiencia_id"], 0.5)
    check("sin trazas: feedback no rompe", True)


def test_emisores_ciclo():
    from alma_service.metaloop import MetaLoop
    from alma_service.curator import Curator
    from alma_service.skills import SkillIndex
    from alma_service.revision import RevisionBackground
    log = EventLog(os.path.join(TMP, "ev7.db"))
    # Meta-loop: el helper emite sin correr el loop.
    ml = MetaLoop(os.path.join(TMP, "ml.db"),
                  ledger_path=os.path.join(TMP, "ml_ledger.jsonl"))
    ml.event_log = log
    ml._emitir_ciclo("metaloop_puerta", {"aceptado": True})
    # Curator: _transicionar emite (skill real en índice temporal).
    idx = SkillIndex(os.path.join(TMP, "skills.sqlite"))
    cur = Curator(idx, ledger_path=os.path.join(TMP, "cur_ledger.jsonl"))
    cur.event_log = log
    cur._emitir_ciclo("curator_transicion", {"skill": "s", "desde": "a",
                                             "hacia": "b"})
    # Revisión: _proponer emite.
    rev = RevisionBackground(os.path.join(TMP, "rev.db"))
    rev.event_log = log
    rid = rev._proponer("nota_test", {"texto": "hola"})
    rev.aprobar(rid)
    tipos = [e["tipo"] for e in log.ciclo()]
    check("emisores de ciclo escriben al log",
          tipos == ["metaloop_puerta", "curator_transicion",
                    "revision_propuesta", "revision_aprobada"])
    check("actores correctos",
          [e["actor"] for e in log.ciclo()]
          == ["metaloop", "curator", "revision_background",
              "revision_background"])


def test_schema_y_resumen():
    from alma_service.trazas import SCHEMA_VERSION
    log = EventLog(os.path.join(TMP, "ev8.db"))
    import sqlite3
    con = sqlite3.connect(os.path.join(TMP, "ev8.db"))
    v = con.execute(
        "SELECT valor FROM _meta WHERE clave='schema_version'"
        ).fetchone()[0]
    con.close()
    check("schema_version sellada en _meta", v == str(SCHEMA_VERSION))
    for _ in range(3):
        log.asentar_decision(firma_regimen="arit", brazo_elegido="cot",
                             reward=0.2, costo_usd=0.01)
    log.asentar_decision(firma_regimen="arit", brazo_elegido="single",
                         reward=0.9, costo_usd=0.02)
    log.asentar_decision(firma_regimen="otro", brazo_elegido="cot",
                         reward=0.5)
    res = log.resumen_operacion(minimo_soporte=2)
    check("resumen: solo grupos con soporte",
          len(res) == 1 and res[0]["firma_regimen"] == "arit"
          and res[0]["brazo_elegido"] == "cot"
          and res[0]["n"] == 3 and res[0]["n_con_reward"] == 3)
    check("resumen: promedios correctos",
          abs(res[0]["reward_medio"] - 0.2) < 1e-9
          and abs(res[0]["costo_medio"] - 0.01) < 1e-9)
    res1 = log.resumen_operacion(minimo_soporte=1)
    check("resumen con soporte 1 trae los 3 grupos", len(res1) == 3)
    est = log.estado()
    check("estado expone schema_version",
          est["schema_version"] == SCHEMA_VERSION)


def main():
    test_event_log_decisiones()
    test_actualizar_reward()
    test_eventos_ciclo()
    test_puente_minero()
    test_paquete_debilidades_end_to_end()
    test_rotar()
    test_motor_instrumentacion()
    test_emisores_ciclo()
    test_schema_y_resumen()
    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
