"""Store de experiencias en SQLite — memoria persistente del servicio.

Misma filosofía que alma/store.py (append-only, hash encadenado,
verificable), pero en SQLite para que el servicio la consulte rápido
(priors warm con olvido) sin leer todo el archivo cada vez.

Tablas:
  experiencias: una fila por problema resuelto por el motor.
  feedback:     recompensas explícitas posteriores (ej: "¿te sirvió el
                análisis de anoche?"), también encadenadas.

No hay UPDATE ni DELETE: corregir = agregar fila nueva.
"""

import hashlib
import json
import os
import sqlite3
import time

from alma_service.procedencia import (
    crear_tabla_memoria, registrar_en_con, ORIGEN_PROPIO,
    ORIGEN_IMPORTADO)

SCHEMA_VERSION = "store-sqlite-v1"

_MIGRADOS = set()  # (problema_id, arch_id, fase) ya migrados, anti-duplicados


def _origen_a_procedencia(origen):
    """Mapea el `origen` de la fila a un origen de procedencia.

    - propio: escritores internos del sistema (el motor, el servicio, la
      revisión en background y sus variantes con prefijo). Son
      componentes del propio código: su contenido no es de terceros.
    - importado: 'migracion-*', 'import*' (ingesta masiva no verificada).
    - cualquier otro / ausente → importado (FAIL-CLOSED: lo desconocido
      nace en cuarentena, nunca como propio). Fix A2 del red-team.

    Alcance honesto: un atacante con acceso al proceso podría escribir
    con origen="servicio"; esa amenaza (código no confiable dentro del
    proceso) está fuera del modelo — la cuarentena frena contenido
    malicioso que entra por los write paths, no código hostil local.
    """
    o = (origen or "").strip().lower()
    if o in ("servicio", "motor-fase1", "revision_background"):
        return ORIGEN_PROPIO
    if o.startswith(("servicio-", "motor-", "revision_", "revision-",
                      "harness-", "benchmark-")):
        return ORIGEN_PROPIO
    return ORIGEN_IMPORTADO


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash_row(body, prev_hash):
    h = hashlib.sha256()
    h.update(prev_hash.encode("utf-8"))
    h.update(_canonical(body).encode("utf-8"))
    return h.hexdigest()


class SQLiteStore:
    def __init__(self, path):
        self.path = path
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS experiencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                problema_id TEXT NOT NULL,
                clase TEXT NOT NULL,
                arch_id TEXT NOT NULL,
                config TEXT NOT NULL DEFAULT '{}',
                features TEXT NOT NULL DEFAULT '{}',
                respuesta TEXT NOT NULL DEFAULT '',
                traza TEXT NOT NULL DEFAULT '',
                metricas TEXT NOT NULL DEFAULT '{}',
                costo_usd REAL NOT NULL DEFAULT 0,
                fase TEXT NOT NULL DEFAULT 'servicio',
                origen TEXT NOT NULL DEFAULT 'servicio',
                timestamp REAL NOT NULL,
                prev_hash TEXT NOT NULL,
                hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiencia_id INTEGER NOT NULL,
                reward REAL NOT NULL,
                nota TEXT NOT NULL DEFAULT '',
                timestamp REAL NOT NULL,
                prev_hash TEXT NOT NULL,
                hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_exp_clase ON experiencias(clase);
            CREATE INDEX IF NOT EXISTS idx_exp_ts ON experiencias(timestamp);
            """
        )
        self._db.commit()
        # Fix A2 (red-team): procedencia cableada en el write path. Cada
        # experiencia nueva registra su origen; lo desconocido nace en
        # cuarentena (fail-closed). La tabla vive en esta misma DB.
        crear_tabla_memoria(self._db)
        self._db.commit()

    # -- append-only -----------------------------------------------------
    def _ultimo_hash(self, tabla):
        cur = self._db.execute(
            f"SELECT hash FROM {tabla} ORDER BY id DESC LIMIT 1"
        )
        fila = cur.fetchone()
        return fila["hash"] if fila else "GENESIS"

    def append_experiencia(self, row):
        """row: dict con problema_id, clase, arch_id, config, features,
        respuesta, traza, metricas, costo_usd. Devuelve la fila guardada."""
        for campo in ("problema_id", "clase", "arch_id", "metricas"):
            if campo not in row:
                raise ValueError(f"falta campo requerido: {campo}")
        prev = self._ultimo_hash("experiencias")
        body = {
            "problema_id": row["problema_id"],
            "clase": row["clase"],
            "arch_id": row["arch_id"],
            "config": row.get("config", {}),
            "features": row.get("features", {}),
            "respuesta": row.get("respuesta", ""),
            "traza": row.get("traza", ""),
            "metricas": row["metricas"],
            "costo_usd": float(row.get("costo_usd", 0.0)),
            "fase": row.get("fase", "servicio"),
            "origen": row.get("origen", "servicio"),
            "timestamp": row.get("timestamp", time.time()),
            "schema": SCHEMA_VERSION,
        }
        h = _hash_row(body, prev)
        self._db.execute(
            """INSERT INTO experiencias
               (problema_id, clase, arch_id, config, features, respuesta,
                traza, metricas, costo_usd, fase, origen, timestamp,
                prev_hash, hash)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                body["problema_id"], body["clase"], body["arch_id"],
                _canonical(body["config"]), _canonical(body["features"]),
                body["respuesta"], body["traza"], _canonical(body["metricas"]),
                body["costo_usd"], body["fase"], body["origen"],
                body["timestamp"], prev, h,
            ),
        )
        guardada = dict(body)
        guardada["prev_hash"] = prev
        guardada["hash"] = h
        guardada["id"] = self._db.execute("SELECT last_insert_rowid()").fetchone()[0]
        # Fix A2: registrar procedencia al escribir (fail-closed), en la
        # misma conexión/transacción (funciona también con :memory:).
        registrar_en_con(self._db, "memoria_procedencia",
                         "experiencia_id", guardada["id"],
                         _origen_a_procedencia(body["origen"]))
        self._db.commit()
        return guardada

    def append_feedback(self, experiencia_id, reward, nota=""):
        prev = self._ultimo_hash("feedback")
        ts = time.time()
        body = {
            "experiencia_id": experiencia_id,
            "reward": float(reward),
            "nota": nota,
            "timestamp": ts,
            "schema": SCHEMA_VERSION,
        }
        h = _hash_row(body, prev)
        self._db.execute(
            "INSERT INTO feedback (experiencia_id, reward, nota, timestamp,"
            " prev_hash, hash) VALUES (?,?,?,?,?,?)",
            (experiencia_id, float(reward), nota, ts, prev, h),
        )
        self._db.commit()
        return self._db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # -- lecturas ---------------------------------------------------------
    def recompensas_por_clase(self, clase):
        """Lista de (arch_id, reward, timestamp) para el prior warm.

        V2.1: las experiencias de agentes-batería NO entran (murieron sin
        dejar deriva); tampoco el feedback ligado a ellas.
        """
        out = []
        cur = self._db.execute(
            "SELECT arch_id, metricas, timestamp FROM experiencias"
            " WHERE clase = ? ORDER BY timestamp",
            (clase,),
        )
        for fila in cur.fetchall():
            try:
                m = json.loads(fila["metricas"])
                r = m.get("reward")
            except (ValueError, TypeError):
                r = None
                m = {}
            if r is None:
                continue
            if isinstance(m, dict) and m.get("modo_agente") == "bateria":
                continue
            out.append((fila["arch_id"], float(r), float(fila["timestamp"])))
        # feedback explícito: pesa como experiencia más (se suma al final)
        cur = self._db.execute(
            "SELECT e.arch_id, e.metricas, f.reward, f.timestamp"
            " FROM feedback f"
            " JOIN experiencias e ON e.id = f.experiencia_id"
            " WHERE e.clase = ? ORDER BY f.timestamp",
            (clase,),
        )
        for fila in cur.fetchall():
            try:
                m = json.loads(fila["metricas"])
            except (ValueError, TypeError):
                m = {}
            if isinstance(m, dict) and m.get("modo_agente") == "bateria":
                continue
            out.append((fila["arch_id"], float(fila["reward"]),
                        float(fila["timestamp"])))
        return out

    def contar(self):
        return self._db.execute("SELECT COUNT(*) c FROM experiencias").fetchone()["c"]

    def clases(self):
        cur = self._db.execute("SELECT DISTINCT clase FROM experiencias")
        return sorted(f["clase"] for f in cur.fetchall())

    def ultima(self):
        cur = self._db.execute(
            "SELECT * FROM experiencias ORDER BY id DESC LIMIT 1"
        )
        fila = cur.fetchone()
        return dict(fila) if fila else None

    def por_id(self, exp_id):
        cur = self._db.execute(
            "SELECT * FROM experiencias WHERE id = ?", (exp_id,)
        )
        fila = cur.fetchone()
        return dict(fila) if fila else None

    # -- integridad --------------------------------------------------------
    def verify_chain(self):
        prev = "GENESIS"
        cur = self._db.execute(
            "SELECT problema_id, clase, arch_id, config, features, respuesta,"
            " traza, metricas, costo_usd, fase, origen, timestamp,"
            " prev_hash, hash FROM experiencias ORDER BY id"
        )
        for fila in cur.fetchall():
            body = {
                "problema_id": fila["problema_id"],
                "clase": fila["clase"],
                "arch_id": fila["arch_id"],
                "config": json.loads(fila["config"]),
                "features": json.loads(fila["features"]),
                "respuesta": fila["respuesta"],
                "traza": fila["traza"],
                "metricas": json.loads(fila["metricas"]),
                "costo_usd": fila["costo_usd"],
                "fase": fila["fase"],
                "origen": fila["origen"],
                "timestamp": fila["timestamp"],
                "schema": SCHEMA_VERSION,
            }
            if fila["prev_hash"] != prev:
                return False
            if fila["hash"] != _hash_row(body, prev):
                return False
            prev = fila["hash"]
        return True

    # -- migración ----------------------------------------------------------
    def migrar_jsonl(self, path_jsonl, origen="migracion-exp"):
        """Trae filas del JSONL viejo (resultados/experiencias.jsonl).
        Idempotente por (problema_id, arch_id, fase): no duplica."""
        n = 0
        with open(path_jsonl, "r", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                vieja = json.loads(linea)
                clave = (vieja.get("problema_id"), vieja.get("arch_id"),
                         vieja.get("fase", ""))
                if clave in _MIGRADOS:
                    continue
                ya = self._db.execute(
                    "SELECT 1 FROM experiencias WHERE problema_id = ?"
                    " AND arch_id = ? AND fase = ? LIMIT 1",
                    (vieja.get("problema_id"), vieja.get("arch_id"),
                     vieja.get("fase", "")),
                ).fetchone()
                if ya:
                    _MIGRADOS.add(clave)
                    continue
                self.append_experiencia({
                    "problema_id": vieja.get("problema_id", "?"),
                    "clase": vieja.get("clase", "desconocida"),
                    "arch_id": vieja.get("arch_id", "?"),
                    "config": vieja.get("config", {}),
                    "features": vieja.get("features", {}),
                    "respuesta": str(vieja.get("respuesta", ""))[:4000],
                    "traza": str(vieja.get("traza", ""))[:1000],
                    "metricas": vieja.get("metricas", {}),
                    "costo_usd": vieja.get("costo_usd", 0.0),
                    "fase": vieja.get("fase", ""),
                    "origen": origen,
                    "timestamp": vieja.get("timestamp", time.time()),
                })
                _MIGRADOS.add(clave)
                n += 1
        return n

    def close(self):
        self._db.close()
