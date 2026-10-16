"""Biblioteca de casos de fallo — patrón Forge/Agent Lens #2 (EXP78).

El flywheel más apretado de la demo de W&B ("Arya", estudio Forge
1/10/2026): un fallo real se convierte en task de regresión. Las
variantes futuras no solo tienen que pasar la puerta: tienen que
sobrevivir a la historia acumulada de fallos.

Acá: cuando una skill candidata FALLA la puerta de handoff
(EXP76), su trace de fallo se archiva como caso de test reservado.
Las candidatas futuras se evalúan también contra la librería
acumulada:

  1. chequear_candidata(): la candidata tiene que batir
     estrictamente el Δ de TODOS los fallos archivados (si empata o
     pierde contra un fallo conocido, no pasa la regresión).
  2. evaluar_en_historial(): re-corre probar_handoff sobre las
     semillas de cada fallo archivado y exige que la regla del handoff
     se cumpla en TODAS. Cuantos más fallos se archivan, más semillas
     tiene que sobrevivir la candidata: EXP76 se endurece con el
     tiempo, por construcción.

No modifica handoff.py: consume probar_handoff (puro) y los records
de audit_record_handoff. La regla de la puerta no cambia; esto es una
exigencia ADICIONAL, no un reemplazo.

Mock US$0, determinista. Solo archiva rechazos (aceptado=False):
archivar una aceptación levanta ValueError (fail-closed).
"""

import json
import os
import sqlite3
import threading
import time


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


class BibliotecaFallos:
    """Casos de fallo del handoff como tests de regresión reservados."""

    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.expanduser(
            "~/workspace/alma-prototype/alma_casos_fallo.db")
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
                """CREATE TABLE IF NOT EXISTS casos_fallo (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       ts REAL NOT NULL,
                       skill TEXT NOT NULL,
                       q_interfaz REAL,
                       delta_down REAL NOT NULL,
                       delta_ref REAL NOT NULL,
                       motivo TEXT NOT NULL DEFAULT '',
                       regla TEXT NOT NULL DEFAULT '',
                       seed_down INTEGER,
                       seed_ref INTEGER,
                       trace_json TEXT NOT NULL DEFAULT '{}'
                   )""")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_fallos_skill"
                " ON casos_fallo(skill)")

    def archivar_fallo(self, registro_handoff):
        """Archiva el fallo de una candidata. registro_handoff: lo que
        retorna evaluar_skill_para_adopcion (o el record de
        audit_record_handoff + deltas). Solo rechazos."""
        if registro_handoff.get("aceptada", False):
            raise ValueError(
                "solo se archivan fallos: la skill fue aceptada")
        ev = registro_handoff.get("evidencia") or {}
        rec = ev.get("handoff") or registro_handoff
        propuesta = rec.get("propuesta") or {}
        skill = (registro_handoff.get("skill")
                 or propuesta.get("skill") or "?")
        seed = rec.get("seed_tareas") or {}
        with self._lock, self._con() as con:
            cur = con.execute(
                """INSERT INTO casos_fallo
                   (ts, skill, q_interfaz, delta_down, delta_ref,
                    motivo, regla, seed_down, seed_ref, trace_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (time.time(), str(skill),
                 rec.get("q_interfaz"),
                 float(registro_handoff.get("delta_down",
                                            rec.get("delta_down", 0.0))),
                 float(registro_handoff.get("delta_ref",
                                            rec.get("delta_ref", 0.0))),
                 str(registro_handoff.get("motivo",
                                          rec.get("motivo", ""))),
                 str(rec.get("regla", "")),
                 seed.get("down"), seed.get("ref"),
                 _canonical(rec)))
            return cur.lastrowid

    def casos(self, limite=1000):
        with self._lock, self._con() as con:
            filas = con.execute(
                "SELECT id, ts, skill, q_interfaz, delta_down,"
                " delta_ref, motivo, regla, seed_down, seed_ref"
                " FROM casos_fallo ORDER BY id LIMIT ?",
                (int(limite),)).fetchall()
        return [dict(f) for f in filas]

    def semillas(self):
        """Pares (seed_down, seed_ref) de los fallos archivados, sin
        duplicados y sin Nones. Para re-evaluar candidatas."""
        vistos, out = set(), []
        for c in self.casos(limite=100000):
            par = (c["seed_down"], c["seed_ref"])
            if None in par or par in vistos:
                continue
            vistos.add(par)
            out.append(par)
        return out

    def chequear_candidata(self, delta_down_cand, delta_ref_cand=None):
        """La candidata tiene que batir estrictamente el Δ_down de cada
        fallo archivado. Retorna {pasa, detalle}.

        Nota honesta: la puerta ya exige Δ_down > 0 y los fallos tienen
        Δ_down <= 0, así que una candidata que pasa la puerta suele
        pasar acá. El valor está en (a) documentar que la barra sube
        con cada fallo archivado y (b) detectar el caso patológico
        donde una candidata empata lo peor conocido.
        """
        d = float(delta_down_cand)
        peor = None
        for c in self.casos(limite=100000):
            if peor is None or c["delta_down"] > peor["delta_down"]:
                peor = c
            if not d > c["delta_down"]:
                return {"pasa": False,
                        "motivo": (f"no bate el fallo #{c['id']} de"
                                   f" {c['skill']}: Δ_down={d:.4f} <="
                                   f" {c['delta_down']:.4f}"),
                        "fallo": c}
        return {"pasa": True,
                "motivo": (f"bate los {len(self.casos())} fallos"
                           f" archivados (mejor Δ_down de fallo:"
                           f" {peor['delta_down']:.4f})"
                           if peor else "sin fallos archivados"),
                "n_casos": len(self.casos())}

    def evaluar_en_historial(self, probar_handoff_fn, interfaz,
                             ayuda, rigidez):
        """Endurecimiento real: re-corre el handoff sobre las semillas
        de cada fallo archivado y exige la regla (Δ_down > 0,
        Δ_ref >= 0) en TODAS.

        probar_handoff_fn: alma_service.handoff.probar_handoff (inyectado
        para no acoplar el import).
        Retorna {pasa, evaluaciones: [{seed_down, seed_ref, delta_down,
        delta_ref, pasa}], n_evaluaciones}.
        """
        pares = self.semillas()
        evaluaciones = []
        pasa_todo = True
        for sd, sr in pares:
            res = probar_handoff_fn(interfaz, ayuda, rigidez,
                                    seed_tareas_down=sd,
                                    seed_tareas_ref=sr)
            d_down = res["score_down_con"] - res["score_down_sin"]
            d_ref = res["score_ref_con"] - res["score_ref_sin"]
            ok = d_down > 0 and d_ref >= 0
            pasa_todo = pasa_todo and ok
            evaluaciones.append({"seed_down": sd, "seed_ref": sr,
                                 "delta_down": round(d_down, 4),
                                 "delta_ref": round(d_ref, 4),
                                 "pasa": ok})
        return {"pasa": pasa_todo, "n_evaluaciones": len(evaluaciones),
                "evaluaciones": evaluaciones}

    def estado(self):
        with self._lock, self._con() as con:
            n = con.execute(
                "SELECT COUNT(*) FROM casos_fallo").fetchone()[0]
        return {"db": self.db_path, "casos_archivados": n,
                "semillas_distintas": len(self.semillas())}
