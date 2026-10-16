"""Torneo campeón vs candidatas — patrón Forge/Agent Lens #3 (EXP78).

La extensión natural del benchmark propio (benchmark.py) y del ciclo
semanal: en vez de comparar el scaffold vigente contra el baseline
fijo, el campeón actual se enfrenta a las candidatas acumuladas con el
validador congelado (e56, réplicas pareadas). Como los jobs nocturnos
de CI de la demo de W&B ("Arya"): variantes candidatas bencheando
contra la librería de tasks, con el campeón defendiendo el título.

No modifica benchmark.py: es un comparador ADICIONAL. El validador
sigue congelado (no se redefine qué cuenta como mejora: núcleo
protegido intacto).

Convención: regret menor es mejor (como en benchmark.py).
mejora = reg_campeon - reg_candidata; > 0 la candidata gana.

Mock US$0: réplicas deterministas del mundo/validador congelados.
Pensado para correr en el ciclo semanal o a pedido.
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
from alma_service.benchmark import REPS_BENCH  # noqa: E402


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


class Torneo:
    """Campeón vs candidatas con el validador congelado."""

    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.expanduser(
            "~/workspace/alma-prototype/alma_torneo.db")
        d = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(d, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _con(self):
        con = sqlite3.connect(self.db_path, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self):
        with self._lock, self._con() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS torneo_corridas (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       ts REAL NOT NULL,
                       candidata TEXT NOT NULL,
                       scaffold_campeon_json TEXT NOT NULL,
                       scaffold_candidata_json TEXT NOT NULL,
                       reg_campeon REAL NOT NULL,
                       reg_candidata REAL NOT NULL,
                       mejora REAL NOT NULL,
                       n_replicas INTEGER NOT NULL,
                       detalle_json TEXT NOT NULL DEFAULT '{}'
                   )""")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_torneo_candidata"
                " ON torneo_corridas(candidata)")

    def correr(self, campeon, candidatas, bloqueante=True):
        """Enfrenta al campeón contra cada candidata.

        campeon: dict scaffold vigente (el que defiende).
        candidatas: [(nombre, scaffold_dict), ...].
        Retorna {"aceptado": True, "resultados": [...]} con mejora por
        candidata (> 0 = la candidata gana). En background salvo
        bloqueante=True.
        """
        cands = [(str(n), dict(s)) for n, s in candidatas]
        if bloqueante:
            return {"aceptado": True,
                    "resultados": self._correr(dict(campeon), cands)}
        t = threading.Thread(target=self._correr,
                             args=(dict(campeon), cands), daemon=True)
        t.start()
        return {"aceptado": True, "resultados": None}

    def _correr(self, campeon, candidatas):
        items = e47.construir_stream()
        tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
        resultados = []
        for nombre, sc in candidatas:
            rc, rd, det = [], [], []
            for r in REPS_BENCH:
                a = e56.correr_replica_param(
                    r, items, tasas, dict(campeon))["reg_pol"]
                b = e56.correr_replica_param(
                    r, items, tasas, dict(sc))["reg_pol"]
                rc.append(a)
                rd.append(b)
                det.append({"rep": r, "campeon": a, "candidata": b})
            mc = sum(rc) / len(rc)
            md = sum(rd) / len(rd)
            mejora = mc - md  # > 0: la candidata gana (menos regret)
            with self._lock, self._con() as con:
                cur = con.execute(
                    """INSERT INTO torneo_corridas
                       (ts, candidata, scaffold_campeon_json,
                        scaffold_candidata_json, reg_campeon,
                        reg_candidata, mejora, n_replicas, detalle_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (time.time(), nombre, _canonical(campeon),
                     _canonical(sc), mc, md, mejora, len(REPS_BENCH),
                     _canonical(det)))
                rid = cur.lastrowid
            resultados.append({"id": rid, "candidata": nombre,
                               "reg_campeon": round(mc, 2),
                               "reg_candidata": round(md, 2),
                               "mejora": round(mejora, 2),
                               "gana": mejora > 0,
                               "n_replicas": len(REPS_BENCH)})
        return resultados

    def historial(self, candidata=None, n=50):
        q = ("SELECT id, ts, candidata, reg_campeon, reg_candidata,"
             " mejora, n_replicas FROM torneo_corridas")
        args = []
        if candidata is not None:
            q += " WHERE candidata=?"
            args.append(str(candidata))
        q += " ORDER BY id DESC LIMIT ?"
        args.append(int(n))
        with self._lock, self._con() as con:
            filas = con.execute(q, args).fetchall()
        return [{"id": f[0], "ts": f[1], "candidata": f[2],
                 "reg_campeon": round(f[3], 2),
                 "reg_candidata": round(f[4], 2),
                 "mejora": round(f[5], 2), "gana": f[5] > 0,
                 "n_replicas": f[6]} for f in filas]

    def campeon_actual(self):
        """La candidata con mejor mejora registrada, o None si el
        campeón nunca perdió. Describe, no prescribe: promover a la
        ganadora sigue siendo decisión del meta-loop con la puerta."""
        with self._lock, self._con() as con:
            fila = con.execute(
                "SELECT candidata, MAX(mejora) FROM torneo_corridas"
                " WHERE mejora > 0").fetchone()
        if fila is None or fila[0] is None:
            return None
        return {"candidata": fila[0], "mejora": round(fila[1], 2)}

    def estado(self):
        with self._lock, self._con() as con:
            n = con.execute(
                "SELECT COUNT(*) FROM torneo_corridas").fetchone()[0]
        return {"db": self.db_path, "enfrentamientos": n,
                "campeon_actual": self.campeon_actual()}
