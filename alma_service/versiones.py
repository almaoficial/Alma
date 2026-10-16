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

    @staticmethod
    def _cuerpo_version(skill_path, version, tipo, padre_path,
                        descripcion, evidencia, ahora):
        return {"skill_path": skill_path, "version": version,
                "tipo": tipo, "padre_path": padre_path,
                "descripcion": descripcion,
                "evidencia": evidencia or {}, "timestamp": ahora}

    def _init_lineage(self, con):
        # EXP78 (patrón Forge #4): lineage explícito por versión
        # aceptada — qué split la validó, con qué Δ, qué regla, cuándo.
        # Los informes ya lo traían parcial; acá vive en código, con
        # la versión del DAG como clave (atómico con el asentamiento).
        # El lineage de scaffolds vive en promotor.adopciones; este
        # formaliza el lado de las skills. Sin duplicación.
        con.execute(
            """CREATE TABLE IF NOT EXISTS skill_lineage (
                   skill_path TEXT NOT NULL,
                   version INTEGER NOT NULL,
                   split_nombre TEXT NOT NULL,
                   split_seed_json TEXT NOT NULL DEFAULT '{}',
                   delta_down REAL NOT NULL,
                   delta_ref REAL NOT NULL,
                   regla TEXT NOT NULL,
                   fuente TEXT NOT NULL DEFAULT '',
                   ts REAL NOT NULL,
                   PRIMARY KEY (skill_path, version)
               )""")

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
        cuerpo = self._cuerpo_version(skill_path, version, tipo,
                                      padre_path, descripcion,
                                      evidencia, ahora)
        h = hashlib.sha256(
            (prev + _canonical(cuerpo)).encode("utf-8")).hexdigest()
        with self._con() as con:
            self._init_lineage(con)
            con.execute(
                """INSERT INTO skill_versiones
                   (skill_path, version, tipo, padre_path, descripcion,
                    evidencia_json, timestamp, prev_hash, hash)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (skill_path, version, tipo, padre_path, descripcion,
                 _canonical(evidencia or {}), ahora, prev, h))
        return {"skill_path": skill_path, "version": version, "tipo": tipo,
                "padre_path": padre_path, "hash": h, "prev_hash": prev}

    # -- lineage (EXP78, patrón Forge #4) ---------------------------------
    @staticmethod
    def _validar_lineage(lineage):
        if not isinstance(lineage, dict):
            raise ValueError("lineage debe ser un dict")
        for req in ("split_nombre", "delta_down", "delta_ref", "regla"):
            if req not in lineage:
                raise ValueError(
                    f"lineage sin {req!r} requerido")
        return {
            "split_nombre": str(lineage["split_nombre"]),
            "split_seed": lineage.get("split_seed"),
            "delta_down": float(lineage["delta_down"]),
            "delta_ref": float(lineage["delta_ref"]),
            "regla": str(lineage["regla"]),
            "fuente": str(lineage.get("fuente") or ""),
        }

    def asentar_con_linaje(self, skill_path, tipo, padre_path,
                           descripcion, evidencia, lineage):
        """Asienta la versión Y su lineage en una sola transacción.

        lineage: {split_nombre, split_seed (opcional), delta_down,
                  delta_ref, regla, fuente (opcional)}.
        Misma validación de tipos que _asentar; el lineage incompleto
        corta con ValueError (fail-closed: versión sin lineage no se
        asienta por este camino).
        """
        if tipo not in TIPOS:
            raise ValueError(f"tipo inválido: {tipo!r} (usar {TIPOS})")
        if tipo == TIPO_CAPTURED and padre_path:
            raise ValueError("CAPTURED no lleva padre")
        if tipo == TIPO_DERIVED and not padre_path:
            raise ValueError("DERIVED requiere padre_path")
        lin = self._validar_lineage(lineage)
        version = self._ultima_version(skill_path) + 1
        ahora = time.time()
        prev = self._ultimo_hash(skill_path)
        cuerpo = self._cuerpo_version(skill_path, version, tipo,
                                      padre_path, descripcion,
                                      evidencia, ahora)
        h = hashlib.sha256(
            (prev + _canonical(cuerpo)).encode("utf-8")).hexdigest()
        with self._con() as con:
            self._init_lineage(con)
            con.execute(
                """INSERT INTO skill_versiones
                   (skill_path, version, tipo, padre_path, descripcion,
                    evidencia_json, timestamp, prev_hash, hash)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (skill_path, version, tipo, padre_path, descripcion,
                 _canonical(evidencia or {}), ahora, prev, h))
            con.execute(
                """INSERT INTO skill_lineage
                   (skill_path, version, split_nombre, split_seed_json,
                    delta_down, delta_ref, regla, fuente, ts)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (skill_path, version, lin["split_nombre"],
                 _canonical(lin["split_seed"] or {}),
                 lin["delta_down"], lin["delta_ref"], lin["regla"],
                 lin["fuente"], ahora))
        return {"skill_path": skill_path, "version": version, "tipo": tipo,
                "padre_path": padre_path, "hash": h, "prev_hash": prev,
                "lineage": lin}

    def linaje(self, skill_path, version=None):
        """Lineage explícito: qué split validó cada versión aceptada,
        con qué Δ, qué regla, cuándo y desde qué fuente. version=None:
        toda la cadena."""
        q = ("SELECT skill_path, version, split_nombre,"
             " split_seed_json, delta_down, delta_ref, regla, fuente, ts"
             " FROM skill_lineage WHERE skill_path=?")
        args = [skill_path]
        if version is not None:
            q += " AND version=?"
            args.append(int(version))
        q += " ORDER BY version"
        with self._con() as con:
            self._init_lineage(con)
            filas = con.execute(q, args).fetchall()
        return [{"skill_path": f[0], "version": f[1],
                 "split_nombre": f[2],
                 "split_seed": json.loads(f[3] or "{}"),
                 "delta_down": f[4], "delta_ref": f[5],
                 "regla": f[6], "fuente": f[7], "ts": f[8]}
                for f in filas]

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


def linaje_desde_handoff(registro):
    """Extrae el lineage de un record de la puerta de handoff para
    asentar_con_linaje. Acepta el dict de audit_record_handoff o el
    veredicto completo de evaluar_skill_para_adopcion (usa
    evidencia.handoff). Puro: no importa handoff.py."""
    ev = (registro or {}).get("evidencia") or {}
    rec = ev.get("handoff") or registro or {}
    seed = rec.get("seed_tareas") or {}
    return {
        "split_nombre": "handoff:downstream+referencia",
        "split_seed": {"down": seed.get("down"),
                       "ref": seed.get("ref")},
        "delta_down": float(rec.get("delta_down") or 0.0),
        "delta_ref": float(rec.get("delta_ref") or 0.0),
        "regla": str(rec.get("regla") or ""),
        "fuente": "exp76_puerta_handoff",
    }
