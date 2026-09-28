"""Trazas unificadas — event log estructurado del servicio (fase 2.2).

El cimiento del paquete único autogestionado (DISENO_PAQUETE_UNICO.md §5):
UN event log en SQLite, UN formato, UN lugar. Lo que emite el servicio:

- `eventos_decision`: cada decisión del resolver — el contrato §4.1:
  (ts, firma_regimen, veredicto_probe, brazo_elegido, reward,
   costo_usd, latencia_ms, scaffold_version) + modo, backend y extras.
- `eventos_ciclo`: cada evento del ciclo de mejora — propuestas del
  meta-loop, veredictos de la puerta de dos splits, adopciones/rollbacks,
  transiciones del Curator, propuestas/aprobaciones de la revisión.

Deliberadamente SEPARADO del observador del asistente
(`servicio/trazas.py` + `trazas.db`): ese registra conducta del asistente
con feedback del usuario; este registra decisiones del servicio con
reward medido. Semántica distinta; mezclarlos contaminaría al minero.

El minero (`debilidades.py`) lee solo eventos con reward medido y agrupa
por firma exacta (firma_regimen, brazo_elegido, tramo_reward) — ver
`minar_decisiones()` en debilidades.py.

Retención: `rotar()` borra lo viejo por ventana (mismo espíritu que el
olvido de la memoria: lo viejo pesa menos). Determinista, sin LLM.

Todo es aditivo y fail-safe: los emisores (motor, metaloop, curator,
revision) envuelven cada llamada en try/except — el log nunca rompe el
camino crítico.
"""

import json
import os
import sqlite3
import threading
import time

# Mismo directorio que las demás DBs del servicio, nombre distinto al
# observador del asistente (trazas.db) para no mezclar semánticas.
DB_DEFAULT = os.path.expanduser(
    "~/workspace/alma-prototype/alma_eventos.db")

RETENCION_DECISION_DIAS = 90
RETENCION_CICLO_DIAS = 180

# Versión del esquema del event log. Los lectores viejos siguen
# funcionando contra esquemas nuevos mientras la versión sea la que
# conocen; las migraciones futuras la incrementan.
SCHEMA_VERSION = 1


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


class EventLog:
    """Event log unificado del servicio. Hilo-seguro, SQLite + WAL."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_DEFAULT
        d = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(d, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    # -- persistencia ----------------------------------------------------
    def _con(self):
        con = sqlite3.connect(self.db_path, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self):
        with self._lock, self._con() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS _meta (
                       clave TEXT PRIMARY KEY,
                       valor TEXT NOT NULL
                   )""")
            cur = con.execute(
                "SELECT valor FROM _meta WHERE clave='schema_version'")
            fila = cur.fetchone()
            if fila is None:
                con.execute(
                    "INSERT INTO _meta(clave, valor) VALUES (?, ?)",
                    ("schema_version", str(SCHEMA_VERSION)))
            elif fila[0] != str(SCHEMA_VERSION):
                raise RuntimeError(
                    "schema_version del event log=%s, este módulo espera %s"
                    % (fila[0], SCHEMA_VERSION))
            con.execute(
                """CREATE TABLE IF NOT EXISTS eventos_decision (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       ts REAL NOT NULL,
                       firma_regimen TEXT NOT NULL DEFAULT '',
                       veredicto_probe TEXT,
                       brazo_elegido TEXT NOT NULL DEFAULT '',
                       reward REAL,
                       costo_usd REAL NOT NULL DEFAULT 0.0,
                       latencia_ms REAL,
                       scaffold_version TEXT NOT NULL DEFAULT '',
                       modo TEXT NOT NULL DEFAULT '',
                       backend_efectivo TEXT NOT NULL DEFAULT '',
                       extras_json TEXT NOT NULL DEFAULT '{}'
                   )""")
            con.execute(
                """CREATE TABLE IF NOT EXISTS eventos_ciclo (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       ts REAL NOT NULL,
                       tipo TEXT NOT NULL,
                       actor TEXT NOT NULL DEFAULT '',
                       detalle_json TEXT NOT NULL DEFAULT '{}'
                   )""")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_dec_ts"
                " ON eventos_decision(ts)")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_dec_firma"
                " ON eventos_decision(firma_regimen)")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_ciclo_tipo"
                " ON eventos_ciclo(tipo)")

    # -- decisiones -------------------------------------------------------
    def asentar_decision(self, firma_regimen, brazo_elegido, reward=None,
                         costo_usd=0.0, latencia_ms=None,
                         scaffold_version="", veredicto_probe=None,
                         modo="", backend_efectivo="", extras=None):
        """Asienta una decisión del resolver. Retorna el id del evento."""
        with self._lock, self._con() as con:
            cur = con.execute(
                """INSERT INTO eventos_decision
                   (ts, firma_regimen, veredicto_probe, brazo_elegido,
                    reward, costo_usd, latencia_ms, scaffold_version,
                    modo, backend_efectivo, extras_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (time.time(), str(firma_regimen or ""),
                 (str(veredicto_probe)
                  if veredicto_probe is not None else None),
                 str(brazo_elegido or ""),
                 (float(reward) if reward is not None else None),
                 float(costo_usd or 0.0), latencia_ms,
                 str(scaffold_version or ""), str(modo or ""),
                 str(backend_efectivo or ""),
                 _canonical(extras or {})))
            return cur.lastrowid

    def actualizar_reward(self, evento_id, reward):
        """Completa el reward medido a posteriori (feedback explícito)."""
        with self._lock, self._con() as con:
            cur = con.execute(
                "UPDATE eventos_decision SET reward=? WHERE id=?",
                (float(reward), int(evento_id)))
            return cur.rowcount > 0

    def decisiones(self, firma_regimen=None, con_reward=False,
                   desde=None, hasta=None, limite=1000):
        """Lee decisiones con filtros. con_reward=True: solo reward
        medido (lo que el minero puede leer, §4.2)."""
        q = ("SELECT id, ts, firma_regimen, veredicto_probe,"
             " brazo_elegido, reward, costo_usd, latencia_ms,"
             " scaffold_version, modo, backend_efectivo, extras_json"
             " FROM eventos_decision")
        conds, args = [], []
        if firma_regimen is not None:
            conds.append("firma_regimen=?")
            args.append(str(firma_regimen))
        if con_reward:
            conds.append("reward IS NOT NULL")
        if desde is not None:
            conds.append("ts>=?")
            args.append(float(desde))
        if hasta is not None:
            conds.append("ts<?")
            args.append(float(hasta))
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY id LIMIT ?"
        args.append(int(limite))
        with self._lock, self._con() as con:
            filas = con.execute(q, args).fetchall()
        out = []
        for f in filas:
            d = dict(f)
            d["extras"] = json.loads(d.pop("extras_json") or "{}")
            out.append(d)
        return out

    # -- ciclo -------------------------------------------------------------
    def asentar_ciclo(self, tipo, actor="", detalle=None):
        """Asienta un evento del ciclo de mejora. Retorna el id."""
        with self._lock, self._con() as con:
            cur = con.execute(
                """INSERT INTO eventos_ciclo (ts, tipo, actor, detalle_json)
                   VALUES (?, ?, ?, ?)""",
                (time.time(), str(tipo), str(actor or ""),
                 _canonical(detalle or {})))
            return cur.lastrowid

    def ciclo(self, tipo=None, desde=None, hasta=None, limite=1000):
        q = ("SELECT id, ts, tipo, actor, detalle_json FROM eventos_ciclo")
        conds, args = [], []
        if tipo is not None:
            conds.append("tipo=?")
            args.append(str(tipo))
        if desde is not None:
            conds.append("ts>=?")
            args.append(float(desde))
        if hasta is not None:
            conds.append("ts<?")
            args.append(float(hasta))
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY id LIMIT ?"
        args.append(int(limite))
        with self._lock, self._con() as con:
            filas = con.execute(q, args).fetchall()
        out = []
        for f in filas:
            d = dict(f)
            d["detalle"] = json.loads(d.pop("detalle_json") or "{}")
            out.append(d)
        return out

    # -- retención ----------------------------------------------------------
    def rotar(self, dias_decision=RETENCION_DECISION_DIAS,
              dias_ciclo=RETENCION_CICLO_DIAS):
        """Borra eventos más viejos que la ventana. Determinista.

        Misma filosofía que el olvido de la memoria: lo viejo pesa
        menos; acá directamente se archiva (se borra del log caliente).
        Retorna conteos.
        """
        ahora = time.time()
        with self._lock, self._con() as con:
            c1 = con.execute(
                "DELETE FROM eventos_decision WHERE ts < ?",
                (ahora - dias_decision * 86400.0,)).rowcount
            c2 = con.execute(
                "DELETE FROM eventos_ciclo WHERE ts < ?",
                (ahora - dias_ciclo * 86400.0,)).rowcount
        return {"decisiones_borradas": c1, "ciclo_borrados": c2}

    # -- agregados ------------------------------------------------------------
    def resumen_operacion(self, minimo_soporte=2):
        """Agregado determinista por (firma_regimen, brazo_elegido).

        Retorna una lista de dicts: n, n_con_reward, reward_medio,
        costo_medio. Solo grupos con n >= minimo_soporte. Insumo para
        el digest dominical y para el minero; describe, no prescribe.
        """
        with self._lock, self._con() as con:
            filas = con.execute(
                """SELECT firma_regimen, brazo_elegido, COUNT(*),
                          COUNT(reward), AVG(reward), AVG(costo_usd)
                   FROM eventos_decision
                   GROUP BY firma_regimen, brazo_elegido
                   ORDER BY COUNT(*) DESC""").fetchall()
        out = []
        for firma, brazo, n, n_r, r_med, c_med in filas:
            if int(n) < int(minimo_soporte):
                continue
            out.append({"firma_regimen": firma, "brazo_elegido": brazo,
                        "n": int(n), "n_con_reward": int(n_r),
                        "reward_medio": r_med, "costo_medio": c_med})
        return out

    # -- minería --------------------------------------------------------------
    def paquete_debilidades(self, minimo_soporte=2):
        """Evidencia descriptiva sobre operación REAL (no experimentos).

        Lee solo decisiones con reward medido y las agrupa por firma
        exacta (firma_regimen, brazo_elegido, tramo_reward). Describe,
        no prescribe (lección EXP58).
        """
        from alma_service.debilidades import minar_decisiones
        return minar_decisiones(self.decisiones(con_reward=True,
                                               limite=100000),
                                minimo_soporte=minimo_soporte)

    def estado(self):
        with self._lock, self._con() as con:
            n_dec = con.execute(
                "SELECT COUNT(*) FROM eventos_decision").fetchone()[0]
            n_cic = con.execute(
                "SELECT COUNT(*) FROM eventos_ciclo").fetchone()[0]
            n_rew = con.execute(
                "SELECT COUNT(*) FROM eventos_decision"
                " WHERE reward IS NOT NULL").fetchone()[0]
        return {"db": self.db_path, "schema_version": SCHEMA_VERSION,
                "decisiones": n_dec,
                "decisiones_con_reward": n_rew, "eventos_ciclo": n_cic}
