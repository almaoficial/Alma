"""Benchmark propio — la puerta de calidad del servicio, fase 2.

El estudio de agentes que se mejoran solos (§4, hallazgo 6) marca el hueco
general: NINGÚN benchmark público mide si estos loops mejoran con el
tiempo. Este módulo existe para no repetir ese hueco: el servicio mide
su propia mejora o no-mejora sobre un benchmark FIJO.

El benchmark es mock US$0 por default (mundo y validador congelados de
e47/e56, réplicas pareadas): compara el scaffold VIGENTE contra el
baseline fijo (DEFAULT_SCAFFOLD validado en EXP56/57). Cada corrida queda
en `benchmark_corridas`; `tendencia()` expone la serie para el /estado.

Si el meta-loop adopta un scaffold peor, el benchmark lo muestra en la
próxima corrida: la evidencia manda, no la intención.
"""

import json
import os
import sqlite3
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                               "exp56_rso"))

import run_experiment47 as e47  # noqa: E402  (mundo congelado)
import run_experiment56 as e56  # noqa: E402  (validador congelado)
from alma_service.scaffold import DEFAULT_SCAFFOLD  # noqa: E402
from alma_service.presupuesto import (  # noqa: E402
    PresupuestoFase2, BUCKET_METALOOP)

REPS_BENCH = [0, 1, 2, 3, 4]


class Benchmark:
    def __init__(self, db_path, presupuesto=None,
                 obtener_scaffold_vigente=None):
        self.db_path = db_path
        self.presupuesto = presupuesto or PresupuestoFase2(db_path)
        self._obtener_scaffold = obtener_scaffold_vigente
        self._lock = threading.Lock()
        self._en_curso = False
        self._init_db()

    def _con(self):
        con = sqlite3.connect(self.db_path, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init_db(self):
        with self._con() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS benchmark_corridas (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       timestamp REAL NOT NULL,
                       scaffold_json TEXT NOT NULL,
                       reg_vigente REAL NOT NULL,
                       reg_baseline REAL NOT NULL,
                       mejora REAL NOT NULL,
                       n_replicas INTEGER NOT NULL,
                       detalle_json TEXT NOT NULL DEFAULT '{}'
                   )""")

    def correr(self, bloqueante=False):
        """Corre el benchmark en background. Mock US$0: el presupuesto
        siempre lo autoriza (costo estimado 0)."""
        if not self.presupuesto.autorizar(BUCKET_METALOOP, 0.0):
            return {"aceptado": False, "motivo": "presupuesto agotado"}
        with self._lock:
            if self._en_curso:
                return {"aceptado": False,
                        "motivo": "benchmark ya en curso"}
            self._en_curso = True
        t = threading.Thread(target=self._correr_bg, daemon=True)
        t.start()
        if bloqueante:
            t.join()
            with self._lock:
                return {"aceptado": True, "resultado": self._ultimo()}
        return {"aceptado": True}

    def _correr_bg(self):
        try:
            vigente = (self._obtener_scaffold()
                       if self._obtener_scaffold
                       else dict(DEFAULT_SCAFFOLD))
            items = e47.construir_stream()
            tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
            rv, rb, det = [], [], []
            for r in REPS_BENCH:
                a = e56.correr_replica_param(r, items, tasas,
                                             dict(vigente))["reg_pol"]
                b = e56.correr_replica_param(r, items, tasas,
                                             dict(DEFAULT_SCAFFOLD))["reg_pol"]
                rv.append(a)
                rb.append(b)
                det.append({"rep": r, "vigente": a, "baseline": b})
            mv = sum(rv) / len(rv)
            mb = sum(rb) / len(rb)
            with self._con() as con:
                con.execute(
                    "INSERT INTO benchmark_corridas (timestamp,"
                    " scaffold_json, reg_vigente, reg_baseline, mejora,"
                    " n_replicas, detalle_json)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (time.time(), json.dumps(vigente,
                                             ensure_ascii=False,
                                             sort_keys=True),
                     mv, mb, mb - mv, len(REPS_BENCH),
                     json.dumps(det, ensure_ascii=False)))
        finally:
            with self._lock:
                self._en_curso = False

    def _ultimo(self):
        with self._con() as con:
            fila = con.execute(
                "SELECT id, timestamp, scaffold_json, reg_vigente,"
                " reg_baseline, mejora, n_replicas FROM benchmark_corridas"
                " ORDER BY id DESC LIMIT 1").fetchone()
        if not fila:
            return None
        return {"id": fila[0], "timestamp": fila[1],
                "scaffold": json.loads(fila[2]),
                "reg_vigente": round(fila[3], 2),
                "reg_baseline": round(fila[4], 2),
                "mejora": round(fila[5], 2),  # >0 = el vigente gana
                "n_replicas": fila[6]}

    def tendencia(self, n=10):
        with self._con() as con:
            filas = con.execute(
                "SELECT id, timestamp, reg_vigente, reg_baseline, mejora"
                " FROM benchmark_corridas ORDER BY id DESC LIMIT ?",
                (n,)).fetchall()
        serie = [{"id": f[0], "timestamp": f[1],
                  "reg_vigente": round(f[2], 2),
                  "reg_baseline": round(f[3], 2),
                  "mejora": round(f[4], 2)} for f in filas]
        return list(reversed(serie))

    def estado(self):
        with self._lock:
            en_curso = self._en_curso
        ultimo = self._ultimo()
        return {"en_curso": en_curso, "ultimo": ultimo,
                "n_corridas": len(self.tendencia(n=100000))}
