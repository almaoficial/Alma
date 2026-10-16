"""Schema único de traces — patrón Forge/Agent Lens #1 (EXP78).

La disciplina que Weave/Arya (demo de W&B, estudio Forge 1/10/2026)
exhibe como precondición de todo lo demás: el trace de producción y el
de offline comparten formato. Sin schema único no hay flywheel: cada
corrida habla otro idioma y nada es comparable.

Este módulo define el schema JSON fijo TRACE_SCHEMA v1 que TODA corrida
del loop emite — offline, mock o producción:

    schema      "trace_unificado/v1" (siempre)
    ts          epoch float
    origen      metaloop | handoff | benchmark | torneo | auditoria
    entorno     mock | offline | produccion
    propuesta   {id, descripcion, tipo}
    split       {nombre, seed}  (qué datos/semilla la validaron)
    metricas    {nombre: float} (mayor-mejor salvo que se indique)
    costo_usd   float >= 0
    veredicto   {decision: aceptado|rechazado, motivo, regla}
    lineage     {producido_por, version, padre}

Puro y determinista: validar/emitir no tocan disco. TraceLog persiste
en SQLite (tabla traces_unificados). Los conversores desde_handoff() y
desde_adopcion() formalizan el logging existente (handoff.
audit_record_handoff, promotor.adopciones) al schema sin modificar esos
módulos: el núcleo protegido no se toca.

Mock-first US$0: nada acá gasta ni llama a modelos.
"""

import json
import os
import sqlite3
import threading
import time

TRACE_SCHEMA_VERSION = 1
TRACE_SCHEMA_ID = "trace_unificado/v1"

ORIGENES = ("metaloop", "handoff", "benchmark", "torneo", "auditoria")
ENTORNOS = ("mock", "offline", "produccion")
DECISIONES = ("aceptado", "rechazado")

CAMPOS_REQUERIDOS = (
    "schema", "ts", "origen", "entorno", "propuesta", "split",
    "metricas", "costo_usd", "veredicto", "lineage",
)


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def validar_trace(t):
    """Valida un dict contra TRACE_SCHEMA v1. Retorna lista de errores
    (vacía = válido). No levanta: el llamante decide."""
    errores = []
    if not isinstance(t, dict):
        return ["no es un dict"]
    for campo in CAMPOS_REQUERIDOS:
        if campo not in t:
            errores.append(f"falta campo requerido: {campo}")
    if errores:
        return errores
    if t.get("schema") != TRACE_SCHEMA_ID:
        errores.append(f"schema != {TRACE_SCHEMA_ID!r}")
    if t.get("origen") not in ORIGENES:
        errores.append(f"origen inválido: {t.get('origen')!r}")
    if t.get("entorno") not in ENTORNOS:
        errores.append(f"entorno inválido: {t.get('entorno')!r}")
    for sub, claves in (("propuesta", ("id", "descripcion", "tipo")),
                        ("split", ("nombre", "seed")),
                        ("veredicto", ("decision", "motivo", "regla")),
                        ("lineage", ("producido_por", "version",
                                     "padre"))):
        v = t.get(sub)
        if not isinstance(v, dict):
            errores.append(f"{sub} no es un dict")
            continue
        for k in claves:
            if k not in v:
                errores.append(f"falta {sub}.{k}")
    v = t.get("veredicto")
    if isinstance(v, dict) and v.get("decision") not in DECISIONES:
        errores.append(f"veredicto.decision inválida: {v.get('decision')!r}")
    m = t.get("metricas")
    if not isinstance(m, dict):
        errores.append("metricas no es un dict")
    else:
        for k, val in m.items():
            if not isinstance(val, (int, float)):
                errores.append(f"metrica {k!r} no numérica")
                break
    c = t.get("costo_usd")
    if not isinstance(c, (int, float)) or c < 0:
        errores.append("costo_usd debe ser número >= 0")
    return errores


def nueva_traza(origen, propuesta, split, metricas, veredicto, lineage,
                entorno="mock", costo_usd=0.0, ts=None):
    """Construye y valida una traza. Levanta ValueError si no valida
    (fail-closed: una traza malformada no se emite)."""
    t = {
        "schema": TRACE_SCHEMA_ID,
        "ts": float(ts) if ts is not None else time.time(),
        "origen": origen,
        "entorno": entorno,
        "propuesta": dict(propuesta),
        "split": dict(split),
        "metricas": {k: float(v) for k, v in dict(metricas).items()},
        "costo_usd": float(costo_usd),
        "veredicto": dict(veredicto),
        "lineage": dict(lineage),
    }
    errores = validar_trace(t)
    if errores:
        raise ValueError("traza inválida: " + "; ".join(errores))
    return t


# -- conversores: formalizan el logging existente al schema ---------------
def desde_handoff(record, entorno="mock"):
    """Convierte un audit_record_handoff (handoff.py) a traza unificada.
    No modifica handoff.py: lee el record que evaluar_skill_para_adopcion
    ya produce."""
    propuesta = record.get("propuesta") or {}
    return nueva_traza(
        origen="handoff",
        propuesta={"id": str(propuesta.get("skill", "?")),
                   "descripcion": "skill candidata (puerta de handoff)",
                   "tipo": "skill"},
        split={"nombre": "downstream+referencia",
               "seed": (record.get("seed_tareas") or {})},
        metricas={"delta_down": float(record.get("delta_down") or 0.0),
                  "delta_ref": float(record.get("delta_ref") or 0.0),
                  "q_interfaz": float(
                      record.get("q_interfaz") or 0.0)},
        veredicto={"decision": ("aceptado" if record.get("aceptado")
                                else "rechazado"),
                   "motivo": str(record.get("motivo") or ""),
                   "regla": str(record.get("regla") or "")},
        lineage={"producido_por": "exp76_puerta_handoff",
                 "version": TRACE_SCHEMA_VERSION,
                 "padre": None},
        entorno=entorno,
        costo_usd=0.0,
    )


def desde_adopcion(adopcion, motivo_puerta="", regla="", entorno="mock"):
    """Convierte un resultado de Promotor.auto_adoptar a traza unificada."""
    diff = adopcion.get("diff") or {}
    return nueva_traza(
        origen="metaloop",
        propuesta={"id": f"adopcion-{adopcion.get('id', '?')}",
                   "descripcion": "auto-adopción del meta-loop",
                   "tipo": "scaffold"},
        split={"nombre": "heldout+train (puerta de dos splits)",
               "seed": None},
        metricas={"delta_ho": float(
            (adopcion.get("efecto_medido") or {}).get("delta_ho", 0.0)),
                  "delta_in": float(
            (adopcion.get("efecto_medido") or {}).get("delta_in", 0.0))},
        veredicto={"decision": ("aceptado" if adopcion.get("adoptada")
                                else "rechazado"),
                   "motivo": str(adopcion.get("motivo") or motivo_puerta),
                   "regla": str(regla)},
        lineage={"producido_por": "promotor.auto_adoptar",
                 "version": TRACE_SCHEMA_VERSION,
                 "padre": diff},
        entorno=entorno,
        costo_usd=float(adopcion.get("costo_usd", 0.0)),
    )


# -- persistencia ----------------------------------------------------------
class TraceLog:
    """Log de trazas unificadas. Hilo-seguro, SQLite + WAL.

    Tabla traces_unificados: el mismo formato para corridas offline y
    de producción (la disciplina de Weave). Los lectores filtran por
    origen/entorno; el minero futuro lee de acá.
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.expanduser(
            "~/workspace/alma-prototype/alma_traces.db")
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
                """CREATE TABLE IF NOT EXISTS traces_unificados (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       ts REAL NOT NULL,
                       origen TEXT NOT NULL,
                       entorno TEXT NOT NULL,
                       schema_version INTEGER NOT NULL,
                       trace_json TEXT NOT NULL
                   )""")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_traces_origen"
                " ON traces_unificados(origen)")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_traces_ts"
                " ON traces_unificados(ts)")

    def emitir(self, trace):
        """Valida (fail-closed) y persiste. Retorna el id."""
        errores = validar_trace(trace)
        if errores:
            raise ValueError("traza inválida: " + "; ".join(errores))
        with self._lock, self._con() as con:
            cur = con.execute(
                """INSERT INTO traces_unificados
                   (ts, origen, entorno, schema_version, trace_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (float(trace["ts"]), str(trace["origen"]),
                 str(trace["entorno"]), TRACE_SCHEMA_VERSION,
                 _canonical(trace)))
            return cur.lastrowid

    def leer(self, origen=None, entorno=None, limite=1000):
        q = ("SELECT id, ts, origen, entorno, trace_json"
             " FROM traces_unificados")
        conds, args = [], []
        if origen is not None:
            conds.append("origen=?")
            args.append(str(origen))
        if entorno is not None:
            conds.append("entorno=?")
            args.append(str(entorno))
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY id LIMIT ?"
        args.append(int(limite))
        with self._lock, self._con() as con:
            filas = con.execute(q, args).fetchall()
        out = []
        for f in filas:
            d = dict(f)
            d["trace"] = json.loads(d.pop("trace_json"))
            out.append(d)
        return out

    def estado(self):
        with self._lock, self._con() as con:
            n = con.execute(
                "SELECT COUNT(*) FROM traces_unificados").fetchone()[0]
            por_origen = con.execute(
                "SELECT origen, COUNT(*) FROM traces_unificados"
                " GROUP BY origen").fetchall()
        return {"db": self.db_path,
                "schema_version": TRACE_SCHEMA_VERSION,
                "trazas": n,
                "por_origen": {o: c for o, c in por_origen}}
