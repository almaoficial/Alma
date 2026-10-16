"""Revisión de background — fase 2.

Diseño §1.1.3 (robado de Hermes, corregido): cada N interacciones se
bifurca una revisión liviana que detecta qué guardar o parchear, SIN
tocar el camino crítico. Con GATE DE CONSENTIMIENTO: las escrituras
propuestas quedan en `revisiones_pendientes` y solo se aplican con
aprobación explícita (aprobar/rechazar). Nada se escribe solo.

En fase 2 la revisión es HEURÍSTICA (US$0, sin LLM): reglas explícitas
sobre las experiencias recientes. Fase 2.1: la detección clusteriza
fallos por FIRMA EXACTA (clase, arch_id, tramo) — Self-Harness §3.2:
coincidencia exacta verificador-anclada, deliberadamente sin agrupación
difusa por LLM. La revisión con LLM queda cableada pero apagada hasta
que el usuario configure presupuesto y la apruebe (mismo gate que el
resto de la fase 2).
"""

import json
import os
import sqlite3
import threading
import time

from .debilidades import MineroDebilidades, firma_feedback
from .procedencia import crear_tabla_memoria, registrar_en_con, ORIGEN_PROPIO

ESTADO_PENDIENTE = "pendiente"
ESTADO_APROBADA = "aprobada"
ESTADO_RECHAZADA = "rechazada"

TIPO_NOTA = "nota_memoria"
TIPO_SUGERENCIA = "sugerencia"


class RevisionBackground:
    """Contador de interacciones + revisión en hilo separado."""

    def __init__(self, db_path, cada_n=None):
        self.db_path = db_path
        self.cada_n = int(cada_n if cada_n is not None
                          else os.environ.get("ALMA_REVISION_CADA", "50"))
        self._contador = 0
        self._lock = threading.Lock()
        self._en_curso = False
        # Fase 2.2: event log unificado (lo cablea server.py vía
        # motor.revision_bg). None = no emite; no cambia el comportamiento.
        self.event_log = None
        self._init_db()

    # -- persistencia (aditiva) -------------------------------------------
    def _con(self):
        con = sqlite3.connect(self.db_path, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init_db(self):
        with self._con() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS revisiones_pendientes (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       tipo TEXT NOT NULL,
                       contenido_json TEXT NOT NULL,
                       estado TEXT NOT NULL DEFAULT 'pendiente',
                       timestamp REAL NOT NULL,
                       resuelta_ts REAL
                   )""")
            crear_tabla_memoria(con)
        # Fix A2 (red-team): la revisión también escribe experiencias
        # (aprobar TIPO_NOTA); su procedencia queda registrada como propia
        # (heurísticas del propio sistema), no como legado sin registro.
        # (El registro se hace dentro de la transacción de aprobar, sobre
        # la misma conexión.)

    # -- camino crítico: solo cuenta ---------------------------------------
    def registrar_interaccion(self):
        """Llamar tras cada resolución. No bloquea; dispara la revisión
        en background cada N interacciones."""
        disparar = False
        with self._lock:
            self._contador += 1
            if self._contador >= self.cada_n and not self._en_curso:
                self._contador = 0
                self._en_curso = True
                disparar = True
        if disparar:
            t = threading.Thread(target=self._ejecutar_bg, daemon=True)
            t.start()

    # -- revisión (background, heurística, US$0) ------------------------------
    def _ejecutar_bg(self):
        try:
            propuestas = self._detectar()
            for tipo, contenido in propuestas:
                self._proponer(tipo, contenido)
        finally:
            with self._lock:
                self._en_curso = False

    def _detectar(self):
        """Detección por firmas exactas (fase 2.1, Self-Harness §3.2).

        Clusteriza feedbacks negativos por firma (clase, arch_id, tramo)
        con coincidencia exacta — determinista, US$0, sin LLM. Solo los
        clusters con soporte >= 3 generan notas candidatas; todas pasan
        por el gate de aprobación humano.
        """
        propuestas = []
        try:
            with self._con() as con:
                filas = con.execute(
                    """SELECT e.clase, e.arch_id, f.reward, f.timestamp
                       FROM feedback f JOIN experiencias e
                         ON e.id = f.experiencia_id
                       ORDER BY f.timestamp DESC LIMIT 200""").fetchall()
        except Exception:
            return propuestas  # tablas ausentes: no proponer nada
        minero = MineroDebilidades()
        for clase, arch_id, reward, _ts in filas:
            firma = firma_feedback(clase, arch_id, reward)
            if firma[2] == "fallo":
                minero.alimentar(firma)
        for c in minero.clusters(n=3, minimo_soporte=3):
            clase, arch_id, _tramo = c["firma"]
            propuestas.append(
                (TIPO_NOTA,
                 {"texto": f"Firma de fallo recurrente: clase '{clase}',"
                           f" arch '{arch_id}' ({c['n']} feedbacks"
                           f" negativos). Candidata a revisar estrategia"
                           f" de selección.",
                  "clase": clase, "arch_id": arch_id,
                  "n_negativos": c["n"], "firma": c["firma"],
                  "origen": "revision_background_heu"}))
        return propuestas

    def _proponer(self, tipo, contenido):
        with self._con() as con:
            cur = con.execute(
                "INSERT INTO revisiones_pendientes (tipo, contenido_json,"
                " estado, timestamp) VALUES (?, ?, ?, ?)",
                (tipo, json.dumps(contenido, ensure_ascii=False),
                 ESTADO_PENDIENTE, time.time()))
            rev_id = cur.lastrowid
        self._emitir_ciclo("revision_propuesta",
                           {"id": rev_id, "tipo": tipo})
        return rev_id

    def _emitir_ciclo(self, tipo, detalle):
        """Evento de la revisión al event log unificado (fase 2.2).

        Fail-safe: el log nunca rompe la revisión."""
        if self.event_log is not None:
            try:
                self.event_log.asentar_ciclo(tipo=tipo,
                                             actor="revision_background",
                                             detalle=detalle)
            except Exception:
                pass

    # -- gate de aprobación ----------------------------------------------------
    def pendientes(self):
        with self._con() as con:
            filas = con.execute(
                "SELECT id, tipo, contenido_json, timestamp FROM"
                " revisiones_pendientes WHERE estado='pendiente'"
                " ORDER BY id").fetchall()
        return [{"id": f[0], "tipo": f[1],
                 "contenido": json.loads(f[2]), "timestamp": f[3]}
                for f in filas]

    def aprobar(self, rev_id):
        """Aplica la propuesta: la marca aprobada. Las notas de memoria se
        registran como experiencia de origen 'revision_background' para
        que el olvido y la auditoría las traten como todo lo demás."""
        exp_id = None
        with self._con() as con:
            fila = con.execute(
                "SELECT tipo, contenido_json, estado FROM"
                " revisiones_pendientes WHERE id=?", (rev_id,)).fetchone()
            if not fila or fila[2] != ESTADO_PENDIENTE:
                return {"ok": False, "motivo": "no pendiente"}
            tipo, contenido = fila[0], json.loads(fila[1])
            if tipo == TIPO_NOTA:
                try:
                    cur = con.execute(
                        """INSERT INTO experiencias
                           (problema_id, clase, arch_id, config, features,
                            respuesta, traza, metricas, costo_usd, fase,
                            origen, timestamp, prev_hash, hash)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (f"revision-{rev_id}", "nota", "nota",
                         "{}", "{}", contenido.get("texto", ""), "",
                         json.dumps({"tipo": "nota_memoria",
                                     "origen": "revision_background"}),
                         0.0, "servicio", "revision_background", time.time(),
                         "NA", f"rev-{rev_id}"))
                    exp_id = cur.lastrowid
                except Exception as e:  # p. ej. tabla ausente: no romper
                    return {"ok": False,
                            "motivo": f"no se pudo aplicar: {e}"[:200]}
            con.execute(
                "UPDATE revisiones_pendientes SET estado='aprobada',"
                " resuelta_ts=? WHERE id=?", (time.time(), rev_id))
        # Fix A2: procedencia en la misma transacción y conexión.
        if exp_id is not None:
            registrar_en_con(con, "memoria_procedencia",
                             "experiencia_id", exp_id, ORIGEN_PROPIO)
        self._emitir_ciclo("revision_aprobada",
                           {"id": rev_id, "tipo": tipo})
        return {"ok": True, "id": rev_id, "tipo": tipo}

    def rechazar(self, rev_id):
        with self._con() as con:
            cur = con.execute(
                "UPDATE revisiones_pendientes SET estado='rechazada',"
                " resuelta_ts=? WHERE id=? AND estado='pendiente'",
                (time.time(), rev_id))
            ok = cur.rowcount > 0
        if ok:
            self._emitir_ciclo("revision_rechazada", {"id": rev_id})
        return {"ok": ok, "id": rev_id}

    def estado(self):
        with self._con() as con:
            n_pend = con.execute(
                "SELECT COUNT(*) FROM revisiones_pendientes"
                " WHERE estado='pendiente'").fetchone()[0]
        with self._lock:
            return {"cada_n": self.cada_n,
                    "contador": self._contador,
                    "en_curso": self._en_curso,
                    "pendientes": n_pend}
