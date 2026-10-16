#!/usr/bin/env python3
"""Tests de la integración E3 al servicio vivo (mock, US$0).

Cubre:
  (a) defaults de configuración del servicio (documentados 28/9),
  (b) la regla pura vía el módulo integrado alma_service.puerta_e3,
  (c) el cableado MetaLoop._puerta_e3: short-circuit, veto, fail-closed,
      kill switch.

No toca el servicio vivo (puerto 8471): el MetaLoop se instancia sobre
una DB temporal.
"""

import os
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import alma_service.puerta_e3 as E3  # noqa: E402
import alma_service.metaloop as ML  # noqa: E402

FALLOS = []


def check(nombre, cond, detalle=""):
    if cond:
        print(f"  ok: {nombre}")
    else:
        FALLOS.append(nombre)
        print(f"  FALLO: {nombre} {detalle}")


# -- (a) defaults de configuración ----------------------------------------
def t_config():
    check("E3_REPS reservado [500,501]", E3.E3_REPS == [500, 501],
          repr(E3.E3_REPS))
    check("MARGEN_MIN_DEFAULT == 5.0 (conservador, documentado)",
          E3.MARGEN_MIN_DEFAULT == 5.0, repr(E3.MARGEN_MIN_DEFAULT))
    check("E3_HABILITADO por default", E3.E3_HABILITADO is True)
    check("SUPERFICIE_METALOOP == 'parametro'",
          E3.SUPERFICIE_METALOOP == "parametro")
    check("E3_REPS no colisiona con train/heldout/bench",
          not (set(E3.E3_REPS) & {0, 1, 2, 3, 4}), repr(E3.E3_REPS))
    cfg = E3.resumen_config_e3()
    check("resumen_config_e3 trae las claves",
          all(k in cfg for k in ("habilitado", "margen_min", "e3_reps",
                                 "regla_e3", "datos", "politica")),
          repr(sorted(cfg)))


# -- (b) regla pura vía el módulo integrado --------------------------------
def t_regla():
    ok, _ = E3.aceptar_e3(1.0, 2.0, 0.5)
    check("acepta sin regresión y con mejora", ok is True)
    ok, mot = E3.aceptar_e3(1.0, 2.0, -0.1)
    check("E3 veta ante regresión aunque E1/E2 pasen",
          ok is False and "E3 veta" in mot, mot)
    ok, mot = E3.aceptar_e3(0.0, 0.0, 0.0)
    check("rechaza sin mejora estricta", ok is False, mot)
    # decidir: short-circuit si dos splits rechazan
    r = E3.decidir(-1.0, 2.0, delta_e3=None, superficie="parametro",
                   margen_min=5.0)
    check("dos splits rechazan → E3 ni se evalúa",
          r["aceptado"] is False and r["e3_exigido"] is False, repr(r))
    # margen cómodo: bastan dos splits
    r = E3.decidir(6.0, 7.0, delta_e3=None, superficie="parametro",
                   margen_min=5.0)
    check("margen cómodo → E3 no exigido",
          r["aceptado"] is True and r["e3_exigido"] is False, repr(r))
    # margen fino: E3 exigido; sin datos → fail-closed (raise)
    try:
        E3.decidir(1.0, 6.0, delta_e3=None, superficie="parametro",
                   margen_min=5.0)
        check("margen fino sin delta_e3 → ValueError", False)
    except ValueError:
        check("margen fino sin delta_e3 → ValueError", True)
    # superficie desconocida → fail-closed en la configuración
    try:
        E3.exigir_e3(1.0, 1.0, superficie="otra")
        check("superficie desconocida → ValueError", False)
    except ValueError:
        check("superficie desconocida → ValueError", True)


# -- (c) cableado MetaLoop._puerta_e3 --------------------------------------
def _ml_tmp():
    d = tempfile.mkdtemp(prefix="alma_e3_test_")
    return ML.MetaLoop(os.path.join(d, "test.db"))


def _puerta(aceptado, d_in, d_ho):
    return {"aceptado": aceptado, "motivo": "m", "regla": "r",
            "delta_in": d_in, "delta_ho": d_ho}


def t_wiring_shortcircuit():
    ml = _ml_tmp()
    llamadas = []

    def fake_evaluar(scaffold, replicas, cache):
        llamadas.append(tuple(replicas))
        return 80.0, []
    ml._evaluar = fake_evaluar
    r = ml._puerta_e3({"a": 1}, {"a": 2}, {},
                      _puerta(False, -1.0, 2.0))
    check("puerta rechaza → E3 no evaluado",
          r["aceptado"] is False and r["e3_exigido"] is False
          and r["e3_evaluado"] is False, repr(r))
    check("puerta rechaza → _evaluar no corre E3_REPS",
          all(set(E3.E3_REPS) != set(c) for c in llamadas), repr(llamadas))


def t_wiring_endurecido_margen_comodo():
    # Endurecimiento 28/9: E3 SIEMPRE exigido cuando los dos splits
    # aceptan, aunque el margen sea cómodo.
    ml = _ml_tmp()
    llamadas = []

    def fake(scaffold, replicas, cache):
        llamadas.append(tuple(replicas))
        # vigente=80, candidato=78 → delta_e3=+2.0 (sin regresión)
        return (78.0, []) if scaffold.get("cand") else (80.0, [])
    ml._evaluar = fake
    r = ml._puerta_e3({"cand": False}, {"cand": True}, {},
                      _puerta(True, 6.0, 7.0))
    check("endurecimiento: margen cómodo → E3 exigido y evaluado",
          r["e3_exigido"] is True and r["e3_evaluado"] is True, repr(r))
    check("endurecimiento: margen cómodo + E3 sin regresión → aceptado",
          r["aceptado"] is True and abs(r["delta_e3"] - 2.0) < 1e-9,
          repr(r))
    check("endurecimiento: el split ciego corrió sobre E3_REPS",
          tuple(E3.E3_REPS) in llamadas, repr(llamadas))


def t_wiring_veto_y_aceptacion():
    ml = _ml_tmp()

    def fake(scaffold, replicas, cache):
        # vigente=80, candidato=78 → delta_e3=+2.0 (sin regresión)
        return (78.0, []) if scaffold.get("cand") else (80.0, [])
    ml._evaluar = fake
    r = ml._puerta_e3({"cand": False}, {"cand": True}, {},
                      _puerta(True, 1.0, 6.0))
    check("margen fino + E3 sin regresión → aceptado",
          r["aceptado"] is True and r["e3_exigido"] is True
          and r["e3_evaluado"] is True
          and abs(r["delta_e3"] - 2.0) < 1e-9, repr(r))

    def fake_reg(scaffold, replicas, cache):
        # candidato=81 → delta_e3=-1.0 (regresión en el ciego)
        return (81.0, []) if scaffold.get("cand") else (80.0, [])
    ml._evaluar = fake_reg
    r = ml._puerta_e3({"cand": False}, {"cand": True}, {},
                      _puerta(True, 1.0, 6.0))
    check("margen fino + E3 con regresión → veto",
          r["aceptado"] is False and "E3 veta" in r["motivo"], repr(r))


def t_wiring_failclosed():
    ml = _ml_tmp()

    def boom(scaffold, replicas, cache):
        raise RuntimeError("validador caído")
    ml._evaluar = boom
    r = ml._puerta_e3({"a": 1}, {"a": 2}, {},
                      _puerta(True, 1.0, 6.0))
    check("E3 exigido pero no evaluable → fail-closed (no adopción)",
          r["aceptado"] is False and r["e3_exigido"] is True
          and r["e3_evaluado"] is False
          and "fail-closed" in r["motivo"], repr(r))


def t_wiring_killswitch():
    ml = _ml_tmp()
    llamadas = []
    ml._evaluar = lambda s, reps, c: (llamadas.append(1), (80.0, []))[1]
    anterior = ML.E3_HABILITADO
    ML.E3_HABILITADO = False
    try:
        r = ml._puerta_e3({"a": 1}, {"a": 2}, {},
                          _puerta(True, 1.0, 6.0))
    finally:
        ML.E3_HABILITADO = anterior
    check("kill switch → vuelve a dos splits",
          r["aceptado"] is True and r["e3_exigido"] is False
          and "kill switch" in r["motivo"], repr(r))
    check("kill switch → no se evalúa E3", llamadas == [], repr(llamadas))


def main():
    print("== integración E3 (mock, US$0) ==")
    t_config()
    t_regla()
    t_wiring_shortcircuit()
    t_wiring_endurecido_margen_comodo()
    t_wiring_veto_y_aceptacion()
    t_wiring_failclosed()
    t_wiring_killswitch()
    print(f"\n{FALLOS and 'FALLOS: ' + str(FALLOS) or 'todo verde'}"
          f" ({17 - len(FALLOS)}/17 checks)")
    return 1 if FALLOS else 0


if __name__ == "__main__":
    raise SystemExit(main())
