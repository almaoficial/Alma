"""Tests fase 2.6: disparo continuo por trazas (benchmark + meta-loop).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase26_disparo.py

Verifica (diseño integracion_fase21/DISENO_BENCHMARK_CONTINUO.md):
1. debe_correr(): tabla de verdad del criterio exacto (§6).
2. Loop A: cada n_b trazas con reward → benchmark en background + serie
   benchmark_recompensa_real + avance del watermark. Las trazas sin
   reward no cuentan. Solo mide (no toca el scaffold).
3. Callback fail-safe: un on_decision roto no rompe asentar_decision.
4. Loop B: evaluar_loop_b() — techo de 7 días, bloqueo ante regresión
   del benchmark posterior a una adopción (umbral −2,8), piso semanal.
5. marcar_corrida_metaloop(): avanza el watermark y retorna el contexto
   que va al pre-registro.
6. El pre-registro del meta-loop documenta las trazas frescas (diseño §5).

Todo mock US$0.
"""

import json
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.disparo import (
    DisparoContinuo, debe_correr, N_B, N_M, UMBRAL_REGRESION)
from alma_service.trazas import EventLog
from alma_service.benchmark import Benchmark
from alma_service.metaloop import MetaLoop
from alma_service.presupuesto import PresupuestoFase2
from alma_service.scaffold import DEFAULT_SCAFFOLD

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def tmpdir():
    return tempfile.mkdtemp(prefix="alma_fase26_")


def armar_loop_a(d, n_b=10):
    """EventLog + Benchmark + DisparoContinuo cableados como server.py."""
    ev_db = os.path.join(d, "eventos.db")
    ml_db = os.path.join(d, "ml.db")
    log = EventLog(ev_db)
    pres = PresupuestoFase2(ml_db, tope_mensual_usd=0.0)
    bench = Benchmark(ml_db, presupuesto=pres,
                      obtener_scaffold_vigente=lambda: dict(DEFAULT_SCAFFOLD))
    disp = DisparoContinuo(ml_db, event_log=log, benchmark=bench, n_b=n_b)
    log.on_decision = disp.notificar
    return log, bench, disp, ml_db


def n_benchmarks(ml_db):
    with sqlite3.connect(ml_db) as con:
        return con.execute(
            "SELECT COUNT(*) FROM benchmark_corridas").fetchone()[0]


def n_serie(ml_db):
    with sqlite3.connect(ml_db) as con:
        return con.execute(
            "SELECT COUNT(*) FROM benchmark_recompensa_real").fetchone()[0]


def test_constantes():
    check("N_B = 100 (aprobado §9.4)", N_B == 100)
    check("N_M = 500 (aprobado §9.4)", N_M == 500)
    check("umbral regresión = −2,8 (§8.2)", UMBRAL_REGRESION == -2.8)


def test_debe_correr():
    debe, mot = debe_correr(100, 3.0, True)
    check("techo: <7 días no corre",
          debe is False and "techo de cadencia" in mot)
    debe, mot = debe_correr(100, 7.0, True)
    check("borde: exactamente 7 días sí corre",
          debe is True and "piso semanal" in mot)
    debe, mot = debe_correr(600, 8.0, True)
    check("ventana fresca: ≥500 trazas corre",
          debe is True and "ventana fresca" in mot)
    debe, mot = debe_correr(100, 8.0, False)
    check("regresión: se bloquea y avisa",
          debe is False and "regresión" in mot and "avisa" in mot)
    debe, _ = debe_correr(0, None, True)
    check("nunca corrió: piso satisfecho", debe is True)
    debe, mot = debe_correr(499, 30.0, True)
    check("tráfico ralo: el piso no es opcional",
          debe is True and "piso semanal" in mot)


def test_loop_a_mide_cada_n_b():
    d = tmpdir()
    log, bench, disp, ml_db = armar_loop_a(d, n_b=10)

    for i in range(10):
        log.asentar_decision(firma_regimen="r", brazo_elegido="cot",
                             reward=0.5 + 0.01 * i)
    check("loop A terminó", disp.esperar_loop_a())
    check("1 benchmark tras 10 trazas con reward",
          n_benchmarks(ml_db) == 1)
    check("1 fila en la serie de reward real", n_serie(ml_db) == 1)
    serie = disp.serie_recompensa_real()
    check("serie: n=10", serie[0]["n"] == 10)
    check("serie: media correcta",
          abs(serie[0]["media"] - 0.545) < 1e-9)
    check("serie: ventana (0,10]",
          serie[0]["desde_id"] == 0 and serie[0]["hasta_id"] == 10)
    check("watermark benchmark avanzó a 10",
          disp._watermark("benchmark") == 10)

    # Trazas sin reward no cuentan para el disparo.
    for _ in range(10):
        log.asentar_decision(firma_regimen="r", brazo_elegido="cot")
    time.sleep(0.3)
    check("trazas sin reward no disparan", n_benchmarks(ml_db) == 1)

    # Segunda ventana: el disparo cruza el borde en cuanto llega la
    # traza 11 con reward (id 21): la ventana es (10,21], n=1.
    for i in range(10):
        log.asentar_decision(firma_regimen="r", brazo_elegido="cot",
                             reward=0.9)
    check("loop A (2da ventana) terminó", disp.esperar_loop_a())
    check("2do benchmark tras la 2da ventana", n_benchmarks(ml_db) == 2)
    serie = disp.serie_recompensa_real()
    check("serie: 2da fila ventana (10,21], n=1 (borde cruzado)",
          serie[1]["n"] == 1 and serie[1]["desde_id"] == 10
          and serie[1]["hasta_id"] == 21)
    check("serie: media de la 2da ventana = 0,9",
          abs(serie[1]["media"] - 0.9) < 1e-9)

    # El loop A no toca el scaffold: el benchmark compara vigente vs
    # baseline y el vigente nunca cambió.
    with sqlite3.connect(ml_db) as con:
        sc = con.execute(
            "SELECT scaffold_json FROM benchmark_corridas"
            " ORDER BY id DESC LIMIT 1").fetchone()[0]
    check("loop A solo mide: scaffold vigente intacto",
          json.loads(sc) == DEFAULT_SCAFFOLD)


def test_loop_a_reward_tardio_cuenta():
    d = tmpdir()
    log, bench, disp, ml_db = armar_loop_a(d, n_b=5)
    eids = [log.asentar_decision(firma_regimen="r", brazo_elegido="cot")
            for _ in range(5)]
    time.sleep(0.3)
    check("sin rewards medidos no hay benchmark", n_benchmarks(ml_db) == 0)
    for e in eids:
        log.actualizar_reward(e, 0.7)  # feedback a posteriori
    check("loop A terminó (reward tardío)", disp.esperar_loop_a())
    check("el reward completado por feedback cuenta",
          n_benchmarks(ml_db) == 1)
    check("serie con los 5 rewards tardíos",
          disp.serie_recompensa_real()[0]["n"] == 5)


def test_callback_fail_safe():
    d = tmpdir()
    log = EventLog(os.path.join(d, "ev.db"))

    def roto():
        raise RuntimeError("boom")
    log.on_decision = roto
    eid = log.asentar_decision(firma_regimen="r", brazo_elegido="cot",
                               reward=0.5)
    check("callback roto no rompe asentar_decision",
          isinstance(eid, int) and eid > 0)
    check("callback roto no rompe actualizar_reward",
          log.actualizar_reward(eid, 0.8) is True)

    # Sin callback: comportamiento idéntico al de antes de la fase 2.6.
    log2 = EventLog(os.path.join(d, "ev2.db"))
    check("on_decision default None", log2.on_decision is None)
    check("asentar sin callback ok",
          log2.asentar_decision(firma_regimen="r",
                                brazo_elegido="cot") > 0)


def armar_loop_b(d):
    ml_db = os.path.join(d, "ml.db")
    pres = PresupuestoFase2(ml_db, tope_mensual_usd=0.0)
    ml = MetaLoop(ml_db, presupuesto=pres, rondas=2)
    bench = Benchmark(ml_db, presupuesto=pres,
                      obtener_scaffold_vigente=ml.scaffold_vigente)
    log = EventLog(os.path.join(d, "eventos.db"))
    disp = DisparoContinuo(ml_db, event_log=log, benchmark=bench,
                           metaloop=ml)
    return ml, bench, disp, ml_db


def insertar_adopcion(ml_db, ts):
    with sqlite3.connect(ml_db) as con:
        con.execute(
            "INSERT INTO adopciones (ts, modo, estado,"
            " scaffold_antes_json, scaffold_despues_json)"
            " VALUES (?, 'auto', 'adoptada', '{}', '{}')",
            (ts,))


def insertar_benchmark(ml_db, ts, mejora):
    with sqlite3.connect(ml_db) as con:
        con.execute(
            "INSERT INTO benchmark_corridas (timestamp, scaffold_json,"
            " reg_vigente, reg_baseline, mejora, n_replicas)"
            " VALUES (?, '{}', 0, 0, ?, 5)",
            (ts, mejora))


def test_loop_b_piso_y_techo():
    d = tmpdir()
    ml, bench, disp, ml_db = armar_loop_b(d)
    ev = disp.evaluar_loop_b()
    check("fresco: debe correr (piso semanal)",
          ev["debe"] is True and "piso semanal" in ev["motivo"])
    check("fresco: benchmark_ok True", ev["benchmark_ok"] is True)
    check("fresco: dias_desde_ultima None", ev["dias_desde_ultima"] is None)

    ml._ledger_append({"tipo": "corrida_finalizada"})
    ev = disp.evaluar_loop_b()
    check("corrida reciente: techo bloquea",
          ev["debe"] is False and "techo de cadencia" in ev["motivo"])
    check("dias_desde_ultima ~ 0",
          ev["dias_desde_ultima"] is not None
          and ev["dias_desde_ultima"] < 0.01)


def test_loop_b_regresion_bloquea():
    d = tmpdir()
    ml, bench, disp, ml_db = armar_loop_b(d)
    ahora = time.time()
    insertar_adopcion(ml_db, ahora - 10)
    insertar_benchmark(ml_db, ahora - 5, mejora=-3.5)  # < −2,8
    ev = disp.evaluar_loop_b()
    check("regresión post-adopción: benchmark_ok False",
          ev["benchmark_ok"] is False)
    check("regresión: debe=False y avisa",
          ev["debe"] is False and "regresión" in ev["motivo"]
          and "avisa" in ev["motivo"])
    check("detalle: 1 regresión detectada",
          len(ev["detalle_benchmark"]["regresiones"]) == 1)

    # Aviso: el bloqueo por regresión deja evento de ciclo.
    disp.avisar_bloqueo(ev)
    tipos = [c["tipo"] for c in disp.event_log.ciclo()]
    check("aviso: evento disparo_bloqueo_regresion",
          "disparo_bloqueo_regresion" in tipos)

    # Sin regresión (mejora −1,0 > −2,8): pasa.
    d2 = tmpdir()
    ml2, bench2, disp2, ml_db2 = armar_loop_b(d2)
    insertar_adopcion(ml_db2, ahora - 10)
    insertar_benchmark(ml_db2, ahora - 5, mejora=-1.0)
    ev2 = disp2.evaluar_loop_b()
    check("sin regresión: benchmark_ok True y debe True",
          ev2["benchmark_ok"] is True and ev2["debe"] is True)


def test_loop_b_watermark_y_pre_registro():
    d = tmpdir()
    ml, bench, disp, ml_db = armar_loop_b(d)
    log = disp.event_log
    for i in range(7):
        log.asentar_decision(firma_regimen="r", brazo_elegido="cot",
                             reward=0.4)
    ctx = disp.marcar_corrida_metaloop()
    check("marcar: contexto con 7 trazas frescas",
          ctx["nuevas_trazas"] == 7)
    check("marcar: watermark metaloop = 7",
          disp._watermark("metaloop") == 7)
    check("marcar: definición documentada",
          "reward IS NOT NULL" in ctx["definicion_trazas"])
    ev = disp.evaluar_loop_b()
    check("tras marcar: 0 trazas nuevas", ev["nuevas_trazas"] == 0)

    # Watermark persistente: una instancia nueva lo lee.
    disp2 = DisparoContinuo(ml_db, event_log=log, benchmark=bench,
                            metaloop=ml)
    check("watermark sobrevive a la instancia",
          disp2._watermark("metaloop") == 7)

    # El pre-registro documenta las trazas frescas (diseño §5).
    r = ml.correr(seed=7, rondas=2, bloqueante=True,
                  contexto_disparo={"nuevas_trazas": 42,
                                    "n_m_referencia": N_M})
    check("corrida con contexto aceptada", r.get("aceptado") is True)
    pr_path = next(
        e["evento"]["preregistro"] for e in ml.ledger_leer()
        if e["evento"]["tipo"] == "corrida_iniciada")
    pr = json.load(open(pr_path, encoding="utf-8"))
    check("pre-registro trae contexto_disparo",
          pr.get("contexto_disparo", {}).get("nuevas_trazas") == 42)


def test_loop_b_sin_cablear_no_rompe():
    d = tmpdir()
    disp = DisparoContinuo(os.path.join(d, "x.db"))
    ev = disp.evaluar_loop_b()
    check("sin metaloop/benchmark: debe True (piso)",
          ev["debe"] is True)
    check("notificar sin benchmark no hace nada",
          disp.notificar() is None)
    check("estado no rompe", isinstance(disp.estado(), dict))


def main():
    test_constantes()
    test_debe_correr()
    test_loop_a_mide_cada_n_b()
    test_loop_a_reward_tardio_cuenta()
    test_callback_fail_safe()
    test_loop_b_piso_y_techo()
    test_loop_b_regresion_bloquea()
    test_loop_b_watermark_y_pre_registro()
    test_loop_b_sin_cablear_no_rompe()
    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
