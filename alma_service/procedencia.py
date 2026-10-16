"""Procedencia y cuarentena para memoria y skills — de Dawn Song.

Vectores documentados (informe §3.1): AgentPoison (backdoor persistente
vía memoria/RAG — la memoria es superficie de ataque) y ClawHavoc
(11.9% de skills maliciosas en un marketplace — las skills de terceros
no son confiables por default).

Reglas:
- Cada entrada de memoria y cada skill registra su ORIGEN:
    propio     — generado por este sistema / el usuario
    tercero    — vino de un tercero identificado
    importado  — ingesta masiva o fuente no verificada
- Lo no-propio nace en CUARENTENA y NO alimenta decisiones (priors,
  soporte, generación de skills, inyección en prompts) hasta graduación
  EXPLÍCITA (`graduar`).
- El olvido/evicción cuenta como higiene de seguridad: la evicción
  archiva primero lo en cuarentena (persistencia para el atacante si
  queda).

Compatibilidad: las filas sin registro de procedencia (legado anterior
a este módulo) se tratan como `propio` no en cuarentena — documentado,
no silencioso: ver `origen_de`.

Tablas propias, aditivas (IF NOT EXISTS), en las DBs existentes:
- memoria_procedencia (en la DB del servicio / memoria)
- skill_procedencia (en la DB de confianza de skills)
"""

import sqlite3
import time

ORIGEN_PROPIO = "propio"
ORIGEN_TERCERO = "tercero"
ORIGEN_IMPORTADO = "importado"
ORIGENES = (ORIGEN_PROPIO, ORIGEN_TERCERO, ORIGEN_IMPORTADO)

_TABLA_MEMORIA = """CREATE TABLE IF NOT EXISTS memoria_procedencia (
    experiencia_id INTEGER PRIMARY KEY,
    origen TEXT NOT NULL DEFAULT 'propio',
    cuarentena INTEGER NOT NULL DEFAULT 0,
    timestamp REAL NOT NULL
)"""

_TABLA_SKILLS = """CREATE TABLE IF NOT EXISTS skill_procedencia (
    path TEXT PRIMARY KEY,
    origen TEXT NOT NULL DEFAULT 'propio',
    cuarentena INTEGER NOT NULL DEFAULT 0,
    timestamp REAL NOT NULL
)"""


def crear_tabla_memoria(con):
    """Crea memoria_procedencia en una conexión existente (IF NOT
    EXISTS). Para que memoria.py la cree sobre su propia conexión."""
    con.execute(_TABLA_MEMORIA)


def crear_tabla_skills(con):
    """Crea skill_procedencia en una conexión existente."""
    con.execute(_TABLA_SKILLS)


def registrar_en_con(con, tabla, col_id, id_, origen, ahora=None):
    """Registra procedencia sobre una conexión EXISTENTE.

    Para write paths que ya tienen su conexión abierta (p. ej. DBs
    `:memory:`, donde una segunda conexión vería otra DB vacía, o para
    escribir en la misma transacción). Misma semántica que
    `_Base.registrar`: tercero/importado → cuarentena.
    """
    _origen_valido(origen)
    ahora = ahora if ahora is not None else time.time()
    cuarentena = 0 if origen == ORIGEN_PROPIO else 1
    con.execute(
        f"INSERT INTO {tabla} ({col_id}, origen, cuarentena, timestamp)"
        f" VALUES (?, ?, ?, ?)"
        f" ON CONFLICT({col_id}) DO UPDATE SET"
        f" origen=excluded.origen, cuarentena=excluded.cuarentena,"
        f" timestamp=excluded.timestamp",
        (id_, origen, cuarentena, ahora))
    return {"origen": origen, "cuarentena": bool(cuarentena)}


def _origen_valido(origen):
    if origen not in ORIGENES:
        raise ValueError(f"origen inválido: {origen!r} (usar {ORIGENES})")
    return origen


class _Base:
    tabla_sql = ""
    tabla = ""
    col_id = ""

    def __init__(self, db_path):
        self.db_path = db_path
        with self._con() as con:
            con.execute(self.tabla_sql)

    def _con(self):
        con = sqlite3.connect(self.db_path, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def registrar(self, id_, origen, ahora=None):
        """Registra la procedencia. tercero/importado → cuarentena."""
        with self._con() as con:
            return registrar_en_con(con, self.tabla, self.col_id, id_,
                                    origen, ahora=ahora)

    def graduar(self, id_, ahora=None):
        """Graduación EXPLÍCITA: sale de cuarentena. Solo a mano."""
        ahora = ahora if ahora is not None else time.time()
        with self._con() as con:
            cur = con.execute(
                f"UPDATE {self.tabla} SET cuarentena=0, timestamp=?"
                f" WHERE {self.col_id}=?", (ahora, id_))
            return {"graduada": cur.rowcount > 0}

    def en_cuarentena(self, id_):
        """True ssi está en cuarentena. Sin registro (legado) → False."""
        with self._con() as con:
            fila = con.execute(
                f"SELECT cuarentena FROM {self.tabla}"
                f" WHERE {self.col_id}=?", (id_,)).fetchone()
        return bool(fila and fila[0])

    def origen_de(self, id_):
        """Origen registrado; sin registro (legado) → 'propio'."""
        with self._con() as con:
            fila = con.execute(
                f"SELECT origen FROM {self.tabla}"
                f" WHERE {self.col_id}=?", (id_,)).fetchone()
        return fila[0] if fila else ORIGEN_PROPIO


class ProcedenciaMemoria(_Base):
    """Procedencia de experiencias (DB del servicio)."""
    tabla_sql = _TABLA_MEMORIA
    tabla = "memoria_procedencia"
    col_id = "experiencia_id"

    def ids_en_cuarentena(self):
        with self._con() as con:
            filas = con.execute(
                "SELECT experiencia_id FROM memoria_procedencia"
                " WHERE cuarentena=1").fetchall()
        return [f[0] for f in filas]


class ProcedenciaSkills(_Base):
    """Procedencia de skills (DB de confianza)."""
    tabla_sql = _TABLA_SKILLS
    tabla = "skill_procedencia"
    col_id = "path"

    def habilitadas(self, paths):
        """Filtra paths: saca los en cuarentena. Para el camino de
        decisión (inyección en prompts): lo en cuarentena no decide."""
        return [p for p in paths if not self.en_cuarentena(p)]
