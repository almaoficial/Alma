"""Versionado de skills FIX/DERIVED/CAPTURED + DAG — de OpenSpace (HKUDS).

Taxonomía (del evolver de OpenSpace):
- FIX: repara instrucciones rotas/desactualizadas. In-place: misma
  identidad, versión+1, encadena al padre.
- DERIVED: especializa una skill existente. Nuevo path, coexiste con el
  padre (preserva generalidad), link padre→hija en el DAG.
- CAPTURED: patrón reusable novedoso desde ejecución. Skill nueva, sin
  padre, con evidencia citada.

El DAG vive en `skill_versiones` con hash encadenado POR SKILL
(audit trail completo, diffs descriptos). La generación del contenido
sigue siendo humana/aprobada: este módulo es infraestructura
determinista (el evolver LLM de OpenSpace no se integra — la evidencia
propia lo veta: fase 1 0,000 / EXP61 +0,40).
"""

import hashlib
import json
import sqlite3
import time

TIPO_FIX = "FIX"
TIPO_DERIVED = "DERIVED"
TIPO_CAPTURED = "CAPTURED"
TIPOS = (TIPO_FIX, TIPO_DERIVED, TIPO_CAPTURED)


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


class VersionadorSkills:
    """DAG de versiones de skills con hash encadenado por skill."""

    def __init__(self, db_path, skill_index=None):
        self.db_path = db_path
        self.index = skill_index
        self._init_db()

    def _con(self):
        con = sqlite3.connect(self.db_path, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init_db(self):
        with self._con() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS skill_versiones (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       skill_path TEXT NOT NULL,
                       version INTEGER NOT NULL,
                       tipo TEXT NOT NULL,
                       padre_path TEXT,
                       descripcion TEXT NOT NULL DEFAULT '',
                       evidencia_json TEXT NOT NULL DEFAULT '{}',
                       timestamp REAL NOT NULL,
                       prev_hash TEXT NOT NULL,
                       hash TEXT NOT NULL,
                       UNIQUE(skill_path, version)
                   )""")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_versiones_padre"
                " ON skill_versiones(padre_path)")

    def _ultimo_hash(self, skill_path):
        with self._con() as con:
            fila = con.execute(
                "SELECT hash FROM skill_versiones WHERE skill_path=?"
                " ORDER BY version DESC LIMIT 1",
                (skill_path,)).fetchone()
        return fila[0] if fila else "GENESIS"

    def _ultima_version(self, skill_path):
        with self._con() as con:
            fila = con.execute(
                "SELECT MAX(version) FROM skill_versiones WHERE skill_path=?",
                (skill_path,)).fetchone()
        return fila[0] or 0

    def _asentar(self, skill_path, tipo, padre_path, descripcion,
                 evidencia):
        if tipo not in TIPOS:
            raise ValueError(f"tipo inválido: {tipo!r} (usar {TIPOS})")
        if tipo == TIPO_CAPTURED and padre_path:
            raise ValueError("CAPTURED no lleva padre")
        if tipo == TIPO_DERIVED and not padre_path:
            raise ValueError("DERIVED requiere padre_path")
        version = self._ultima_version(skill_path) + 1
        ahora = time.time()
        prev = self._ultimo_hash(skill_path)
        cuerpo = {"skill_path": skill_path, "version": version,
                  "tipo": tipo, "padre_path": padre_path,
                  "descripcion": descripcion,
                  "evidencia": evidencia or {}, "timestamp": ahora}
        h = hashlib.sha256(
            (prev + _canonical(cuerpo)).encode("utf-8")).hexdigest()
        with self._con() as con:
            con.execute(
                """INSERT INTO skill_versiones
                   (skill_path, version, tipo, padre_path, descripcion,
                    evidencia_json, timestamp, prev_hash, hash)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (skill_path, version, tipo, padre_path, descripcion,
                 _canonical(evidencia or {}), ahora, prev, h))
        return {"skill_path": skill_path, "version": version, "tipo": tipo,
                "padre_path": padre_path, "hash": h, "prev_hash": prev}

    # -- operaciones ------------------------------------------------------
    def fix(self, skill_path, descripcion, evidencia=None):
        """Repara in-place: misma identidad, versión+1, encadena al padre
        (la versión anterior de la misma skill)."""
        return self._asentar(skill_path, TIPO_FIX, None, descripcion,
                             evidencia)

    def derived(self, padre_path, nuevo_path, descripcion, evidencia=None):
        """Especializa: nueva skill con link al padre. El padre coexiste
        (no se toca)."""
        return self._asentar(nuevo_path, TIPO_DERIVED, padre_path,
                             descripcion, evidencia)

    def captured(self, nuevo_path, descripcion, evidencia=None):
        """Patrón novedoso desde ejecución: sin padre, con evidencia.

        La evidencia debe citar observaciones (qué ejecución la produjo);
        sin generalización no verificada (regla de captura exigente).
        """
        return self._asentar(nuevo_path, TIPO_CAPTURED, None, descripcion,
                             evidencia)

    # -- lectura ------------------------------------------------------------
    def historial(self, skill_path):
        with self._con() as con:
            filas = con.execute(
                "SELECT version, tipo, padre_path, descripcion,"
                " evidencia_json, timestamp, hash, prev_hash"
                " FROM skill_versiones WHERE skill_path=?"
                " ORDER BY version", (skill_path,)).fetchall()
        return [{"version": f[0], "tipo": f[1], "padre_path": f[2],
                 "descripcion": f[3], "evidencia": json.loads(f[4]),
                 "timestamp": f[5], "hash": f[6], "prev_hash": f[7]}
                for f in filas]

    def hijas(self, padre_path):
        """Skills DERIVED desde este padre (el árbol de evolución)."""
        with self._con() as con:
            filas = con.execute(
                "SELECT skill_path, version FROM skill_versiones"
                " WHERE padre_path=? AND tipo='DERIVED'",
                (padre_path,)).fetchall()
        return [{"skill_path": f[0], "version": f[1]} for f in filas]

    def verificar_cadena(self, skill_path):
        """Verifica el hash encadenado del DAG de una skill."""
        prev = "GENESIS"
        for v in self.historial(skill_path):
            # reconstrucción canónica idéntica a _asentar
            cuerpo = {"skill_path": skill_path, "version": v["version"],
                      "tipo": v["tipo"], "padre_path": v["padre_path"],
                      "descripcion": v["descripcion"],
                      "evidencia": v["evidencia"],
                      "timestamp": v["timestamp"]}
            h = hashlib.sha256(
                (prev + _canonical(cuerpo)).encode("utf-8")).hexdigest()
            if h != v["hash"] or v["prev_hash"] != prev:
                return False
            prev = v["hash"]
        return True
