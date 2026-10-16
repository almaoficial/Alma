"""Tests fase 0: Resolver — decisiones puras + bit-identidad vs EXP56.

La prueba central: correr_replica_servicio debe producir los MISMOS
reg_trat_bloques por réplica que la implementación independiente
exp56_rso/run_experiment56.py con el scaffold validado por EXP56/57
(n0=4, umbral_base=1), porque es la misma política con una arquitectura
distinta (Resolver + costura ProveedorSkills + scaffold.py).

Nota 27/9: antes comparaba contra el reporte de EXP51 (n0=2,
umbral_base=2). La integración de los defaults validados cambió la
política a propósito; la referencia ahora es el runner de EXP56.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase0_resolver.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "exp56_rso"))

import run_experiment47 as e47
import run_experiment56 as e56
from run_experiment51 import correr_replica_probe_barato, q1_decisivo
from alma_service.resolver import Resolver, correr_replica_servicio
from alma_service.scaffold import DEFAULT_SCAFFOLD

PASSOS = []
DIR = os.path.dirname(os.path.abspath(__file__))


def check(nombre, cond):
    PASSOS.append(cond)
    print(("PASS" if cond else "FAIL"), "-", nombre)


def test_decidir_salto():
    # mundo sintético: firma con soporte fuerte → salta; sin skill → no
    brazos = ["a", "b"]
    res = Resolver(brazos)
    # fabrica historial: firma "s" vista con brazo a ganando 3 veces
    for b0 in range(3):
        res.block_sig[b0] = "s"
        res.probe_obs[b0] = {"a": [1.0] * 5, "b": [0.0] * 5}
        for a in brazos:
            res.rep_hist[a].append((b0 * 10, 1.0 if a == "a" else 0.0, b0))
    dec = res.decidir_salto(3, "s")
    check("soporte fuerte → salta",
          dec["saltar"] and dec["skill_arm"] == "a" and dec["wins"] >= 2)
    dec2 = res.decidir_salto(0, "inexistente")
    check("sin skill → no salta", not dec2["saltar"])


def test_gate_q1():
    brazos = ["single", "cot"]
    res = Resolver(brazos)
    rs_q1 = {q: {"single": 1, "cot": 0} for q in e47.PROBE_Q1}
    check("Q1 estricto a favor → gate", res.gate_q1(rs_q1, "single"))
    # media empatada: Q1 no decide → sin gate
    rs_empate = {q: {"single": 1 if q == 0 else 0,
                     "cot": 0 if q == 0 else 1} for q in e47.PROBE_Q1}
    check("Q1 no estricto (empate) → sin gate",
          not res.gate_q1(rs_empate, "single"))
    check("sin skill → sin gate", not res.gate_q1(rs_q1, None))


def test_bit_identidad():
    import run_experiment51  # noqa: F401 (solo para TASAS_PATH)
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
    items = e47.construir_stream()  # bit-idéntico al stream de EXP47–51
    with open(os.path.join(DIR, "resultados", "exp51-20260927",
                           "report.json")) as f:
        ref = json.load(f)
    sc = dict(DEFAULT_SCAFFOLD)
    ok = True
    for rep in range(5):
        got = correr_replica_servicio(rep, items, tasas)
        # referencia independiente: runner de EXP56, misma política
        want = e56.correr_replica_param(rep, items, tasas, dict(sc))
        same_bloques = (got["reg_pol_bloques"] == want["reg_pol_bloques"])
        same_total = abs(got["reg_pol"] - want["reg_pol"]) < 1e-9
        same_pol = got["politica"] == "servicio-exp56"
        ok = ok and same_bloques and same_total and same_pol
        # el control verbatim no cambió: bit-identidad vs reporte EXP51
        ctrl = __import__("run_experiment49").correr_replica_endurecido(
            rep, items, tasas)
        same_ctrl = (ctrl["reg_pol_bloques"]
                     == ref["detalle_replicas"][rep]["reg_control_bloques"])
        ok = ok and same_ctrl
        print(f"  réplica {rep}: bit-idéntica servicio={same_bloques and same_total} control={same_ctrl}")
    check("bit-identidad total vs runner EXP56 con scaffold validado "
          "(5 réplicas)", ok)


if __name__ == "__main__":
    test_decidir_salto()
    test_gate_q1()
    test_bit_identidad()
    sys.exit(0 if all(PASSOS) else 1)
