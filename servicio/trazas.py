#!/usr/bin/env python3
"""Modo observador de ALMA: registro de trazas de estrategias del asistente.

ALMA estudia las trazas (tarea -> estrategia usada -> resultado -> feedback
del usuario) para aprender CUÁNDO conviene cada estrategia (meta-nivel),
no para clonar el modelo. La vara es el feedback del usuario.

Diseño deliberado: NO toca el servicio en ejecución. Usa su propia base
SQLite (trazas.db) y no expone endpoints nuevos en server.py.

US$0, sin API real.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(DIR, "trazas.db")

TIPOS = ("investigacion", "codigo", "analisis", "conversacion", "otro")
RESULTADOS = ("ok", "fallo", "parcial")

SCHEMA = """
CREATE TABLE IF NOT EXISTS trazas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    tarea TEXT NOT NULL,
    tipo_tarea TEXT NOT NULL,
    estrategia TEXT NOT NULL,
    herramientas TEXT NOT NULL DEFAULT '[]',
    resultado TEXT NOT NULL,
    feedback INTEGER,
    nota TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_trazas_tipo ON trazas(tipo_tarea);
"""


def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def registrar(tarea, tipo_tarea, estrategia, herramientas=(), resultado="ok",
              feedback=None, nota=""):
    """Registra una traza. Devuelve el id asignado."""
    if tipo_tarea not in TIPOS:
        raise ValueError(f"tipo_tarea debe ser uno de {TIPOS}")
    if resultado not in RESULTADOS:
        raise ValueError(f"resultado debe ser uno de {RESULTADOS}")
    if feedback is not None:
        feedback = int(feedback)
        if not 1 <= feedback <= 5:
            raise ValueError("feedback debe ser 1-5 o vacío")
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO trazas (ts, tarea, tipo_tarea, estrategia,"
            " herramientas, resultado, feedback, nota)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, tarea, tipo_tarea, estrategia,
             json.dumps(list(herramientas), ensure_ascii=False),
             resultado, feedback, nota or ""))
        return cur.lastrowid


def listar(n=10):
    """Últimas n trazas, más recientes primero."""
    with _conn() as c:
        return c.execute(
            "SELECT * FROM trazas ORDER BY id DESC LIMIT ?", (int(n),)
        ).fetchall()


def contar():
    with _conn() as c:
        return c.execute("SELECT COUNT(*) AS n FROM trazas").fetchone()["n"]


def mapa():
    """Mapa aprendido: por tipo de tarea, estrategias rankeadas.

    Orden: feedback medio descendente (las sin feedback van últimas).
    tasa_ok: ok=1.0, parcial=0.5, fallo=0.0.
    """
    with _conn() as c:
        rows = c.execute(
            "SELECT tipo_tarea, estrategia,"
            " COUNT(*) AS n,"
            " AVG(feedback) AS fb_medio,"
            " SUM(CASE WHEN feedback IS NOT NULL THEN 1 ELSE 0 END)"
            "   AS n_fb,"
            " AVG(CASE WHEN resultado='ok' THEN 1.0"
            "        WHEN resultado='parcial' THEN 0.5"
            "        ELSE 0.0 END) AS tasa_ok"
            " FROM trazas GROUP BY tipo_tarea, estrategia"
        ).fetchall()
    por_tipo = {}
    for r in rows:
        por_tipo.setdefault(r["tipo_tarea"], []).append(dict(r))
    for estrategias in por_tipo.values():
        estrategias.sort(
            key=lambda d: (d["fb_medio"] is None, -(d["fb_medio"] or 0.0)))
    return por_tipo
