"""Promotor — staging + freno humano (fase 2.3, DISENO_PAQUETE_UNICO.md §6)
y auto-adopción gobernada (decisión del usuario, 27/9 ~22:50).

CAMBIO DE GOBERNANZA (27/9 ~22:50, refino "pero no peor"): la fase 2.3
queda SUPERADA para el meta-loop. Un PASS de la puerta de dos splits se
AUTO-ADOPTA sin esperar el "sí" humano, pero SOLO ante mejora medida:

    Δ_ho > 0   (mejora estricta en la métrica primaria: held-out)
    Δ_in ≥ 0   (sin regresión en train)
    frenos ok  (costo dentro de presupuesto, sin violaciones de frenos)

Lo que mida igual o peor NO se adopta: se registra el rechazo con los
números y se sigue. Nada de cambios laterales ni "evolución" sin mejora.
(Este criterio es más estricto que la puerta —que acepta mejora solo en
train— y vive acá, sin tocar gate.py: la puerta está en el núcleo
protegido y su definición no se cambia.)

Toda adopción es REVERSIBLE (queda registrado cómo revertirla) y se
NOTIFICA al usuario (cola de notificaciones; un job periódico reporta
lo no-reportado y lo marca).

NÚCLEO PROTEGIDO (fuera del alcance del loop): topes de gasto,
definición de la puerta de dos splits y mecanismo de notificación.
Cualquier adopción que toque esa superficie se RECHAZA (raise +
event log + notificación) y no se aplica.

El camino manual de fase 2.3 (proponer → staging → aprobar/rechazar
con allowlist "humano") SIGUE EXISTIENDO para promociones manuales;
el meta-loop ya no lo usa.

Pipeline del meta-loop (nuevo):
    proponente → validador (congelado) → puerta de dos splits
    → PASS + mejora medida + frenos ok: auto-adopción (reversible,
      notificada)
    → PASS sin mejora estricta / frenos mal: rechazo registrado
      con números, sin cambios
    → FAIL: se descarta (como antes)
    → intento de tocar el núcleo: BLOQUEO (raise + log + aviso)

Línea roja intacta: el loop propone PARÁMETROS del espacio acotado,
nunca código (anti-DGM).
"""

import json
import sqlite3
import threading
import time

# Espeja politicas.APROBADORES_PERMITIDOS (fix A3b, red-team): el único
# aprobador válido por default es el humano. Un label arbitrario
# ("loop", "metaloop", "") NO aprueba.
APROBADORES = ("humano",)

ESTADO_ESPERA = "en_espera"
ESTADO_APROBADA = "aprobada"
ESTADO_RECHAZADA = "rechazada"


class NucleoProtegidoError(Exception):
    """Se intentó adoptar un cambio que toca el núcleo protegido."""


# NÚCLEO PROTEGIDO — fuera del alcance del loop (decisión del usuario,
# 27/9 ~22:50). Si el loop pudiera tocar estas tres piezas, podría subir
# sus propios topes, redefinir qué cuenta como "mejora" o silenciar sus
# avisos — y el "avísame" no valdría nada. El promotor RECHAZA (raise +
# event log + notificación al usuario) cualquier adopción que toque esta
# superficie, en el camino automático Y en el manual.
NUCLEO_PROTEGIDO = [
    # (path, qué protege, por qué está fuera del alcance del loop)
    ("alma_service/presupuesto.py",
     "topes de gasto y presupuesto",
     "el loop no puede subir su propio presupuesto"),
    ("alma_service/gate.py",
     "definición de la puerta de dos splits",
     "el loop no puede redefinir qué cuenta como mejora"),
    ("alma_service/promotor.py :: tabla notificaciones",
     "mecanismo de notificación al usuario",
     "el loop no puede silenciar sus propios avisos"),
]


# Claves que NUNCA pueden aparecer en un diff adoptado, en ningún camino
# (auto o manual). Defensa en profundidad sobre el chequeo de superficie:
# aunque claves_permitidas no se pase, estas se bloquean igual.
CLAVES_NUCLEO_EXACTAS = frozenset({
    "tope_mensual_usd", "reparto", "presupuesto", "bucket",
    "regla_puerta", "puerta_dos_splits",
    "notificaciones", "notificador", "reportada",
})


# Dimensiones protegidas del criterio "pero no peor" (refinamiento del
# usuario, 27/9): además de la métrica primaria, la adopción no puede
# regresar en costo ni violar frenos.
DIMENSIONES_PROTEGIDAS = ("costo_usd", "frenos_ok")


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def _diff_scaffold(antes, despues):
    """Qué cambia: {clave: [valor_antes, valor_despues]} solo lo distinto."""
    diff = {}
    for k in sorted(set(antes) | set(despues)):
        va, vd = antes.get(k), despues.get(k)
        if va != vd:
            diff[k] = [va, vd]
    return diff


class Promotor:
    """Staging de promociones (camino manual, fase 2.3) + auto-adopción
    gobernada del meta-loop (27/9 ~22:50).

    aplicar_fn: callable(scaffold, origen) que hace el commit real
      (en el servicio: MetaLoop._asentar_scaffold). Solo se invoca
      desde aprobar() con aprobador autorizado o desde auto_adoptar()
      cuando pasa el criterio "pero no peor".
    revertir_fn: callable(scaffold, origen) para deshacer una
      auto-adopción (en el servicio: re-asienta el scaffold previo).
      Si es None, revertir_adopcion() falla explícito en vez de
      inventar un camino.
    ledger_fn: callable(evento_dict) -> hash, para el audit trail
      (en el servicio: MetaLoop._ledger_append).
    event_log: EventLog de 2.2 (opcional; fail-safe si es None).
    """

    def __init__(self, db_path, aplicar_fn=None, ledger_fn=None,
                 event_log=None, revertir_fn=None):
        self.db_path = db_path
        self.aplicar_fn = aplicar_fn
        self.ledger_fn = ledger_fn
        self.revertir_fn = revertir_fn
        self.event_log = None
        self._lock = threading.Lock()
        self._init_db()
        if event_log is not None:
            self.event_log = event_log

    # -- persistencia --------------------------------------------------
    def _con(self):
        con = sqlite3.connect(self.db_path, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self):
        with self._lock, self._con() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS staging_promociones (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       ts_creada REAL NOT NULL,
                       estado TEXT NOT NULL DEFAULT 'en_espera',
                       scaffold_antes_json TEXT NOT NULL,
                       scaffold_despues_json TEXT NOT NULL,
                       diff_json TEXT NOT NULL DEFAULT '{}',
                       delta_in REAL,
                       delta_ho REAL,
                       motivo_puerta TEXT NOT NULL DEFAULT '',
                       regla TEXT NOT NULL DEFAULT '',
                       evidencia_json TEXT NOT NULL DEFAULT '{}',
                       ts_resuelta REAL,
                       aprobador TEXT,
                       motivo_rechazo TEXT
                   )""")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_staging_estado"
                " ON staging_promociones(estado)")
            # Gobernanza 27/9 ~22:50: adopciones del camino automático
            # (adoptadas o rechazadas) + cola de notificaciones al usuario.
            con.execute(
                """CREATE TABLE IF NOT EXISTS adopciones (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       ts REAL NOT NULL,
                       modo TEXT NOT NULL DEFAULT 'auto',
                       estado TEXT NOT NULL DEFAULT 'adoptada',
                       scaffold_antes_json TEXT NOT NULL,
                       scaffold_despues_json TEXT NOT NULL,
                       diff_json TEXT NOT NULL DEFAULT '{}',
                       delta_in REAL,
                       delta_ho REAL,
                       motivo_puerta TEXT NOT NULL DEFAULT '',
                       regla TEXT NOT NULL DEFAULT '',
                       efecto_medido_json TEXT NOT NULL DEFAULT '{}',
                       evidencia_json TEXT NOT NULL DEFAULT '{}',
                       revertir_json TEXT NOT NULL DEFAULT '{}',
                       motivo_rechazo TEXT NOT NULL DEFAULT '',
                       notificacion_id INTEGER
                   )""")
            con.execute(
                """CREATE TABLE IF NOT EXISTS notificaciones (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       ts REAL NOT NULL,
                       tipo TEXT NOT NULL,
                       titulo TEXT NOT NULL,
                       detalle_json TEXT NOT NULL DEFAULT '{}',
                       reportada INTEGER NOT NULL DEFAULT 0,
                       ts_reportada REAL
                   )""")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_notif_pendiente"
                " ON notificaciones(reportada, id)")

    def _emitir(self, tipo, actor, detalle):
        if self.event_log is None:
            return
        try:
            self.event_log.asentar_ciclo(tipo=tipo, actor=actor,
                                         detalle=detalle)
        except Exception:
            pass  # fail-safe: el log nunca rompe el ciclo

    def _asentar_ledger(self, evento):
        if self.ledger_fn is None:
            return None
        try:
            return self.ledger_fn(evento)
        except Exception:
            return None

    # -- núcleo protegido ------------------------------------------------
    @staticmethod
    def _verificar_nucleo(diff, claves_permitidas=None):
        """Fail-closed: el diff solo puede tocar la superficie mutable
        declarada. Cualquier otra clave se trata como intento de tocar
        el núcleo protegido → NucleoProtegidoError.

        claves_permitidas: set de claves mutables (el meta-loop pasa las
        5 del SPACES). Si es None, solo se bloquean las claves exactas
        del núcleo (camino manual).
        """
        permitidas = (set(claves_permitidas)
                      if claves_permitidas is not None else None)
        for clave in diff:
            if clave in CLAVES_NUCLEO_EXACTAS:
                raise NucleoProtegidoError(
                    f"la clave {clave!r} pertenece al núcleo protegido"
                    f" ({[p[1] for p in NUCLEO_PROTEGIDO]})")
            if permitidas is not None and clave not in permitidas:
                raise NucleoProtegidoError(
                    f"la clave {clave!r} está fuera de la superficie"
                    f" mutable declarada {sorted(permitidas)}")

    def _bloquear_nucleo(self, motivo, contexto):
        """Respuesta al intento de tocar el núcleo: log + aviso y raise.
        No se aplica nada."""
        detalle = {"motivo": motivo, **contexto}
        self._emitir("nucleo_bloqueado", "promotor", detalle)
        self._asentar_ledger({"tipo": "nucleo_bloqueado", **detalle})
        self._notificar(
            "nucleo_bloqueado",
            "Bloqueado: intento de tocar el núcleo protegido",
            detalle)
        raise NucleoProtegidoError(motivo)

    # -- notificaciones ----------------------------------------------------
    # El mecanismo de notificación es PARTE DEL NÚCLEO PROTEGIDO: las
    # adopciones solo ENCOLAN; solo el job periódico de reporte MARCA
    # como reportadas. El loop nunca puede silenciar sus avisos.
    def _notificar(self, tipo, titulo, detalle):
        """Encola un aviso al usuario. Retorna el id. Fail-safe."""
        try:
            with self._lock, self._con() as con:
                cur = con.execute(
                    """INSERT INTO notificaciones
                       (ts, tipo, titulo, detalle_json)
                       VALUES (?, ?, ?, ?)""",
                    (time.time(), str(tipo), str(titulo),
                     _canonical(detalle or {})))
                return cur.lastrowid
        except Exception:
            return None

    def notificaciones_pendientes(self, limite=50):
        """Avisos no reportados (lo que el job periódico lleva al chat).
        Cada uno trae qué cambió, efecto medido y cómo revertirlo."""
        with self._lock, self._con() as con:
            filas = con.execute(
                "SELECT id, ts, tipo, titulo, detalle_json"
                " FROM notificaciones WHERE reportada=0"
                " ORDER BY id LIMIT ?", (int(limite),)).fetchall()
        out = []
        for f in filas:
            d = dict(f)
            d["detalle"] = json.loads(d.pop("detalle_json") or "{}")
            out.append(d)
        return out

    def marcar_notificadas(self, ids):
        """El job de reporte marca lo ya llevado al chat. Idempotente."""
        ids = [int(i) for i in ids or []]
        if not ids:
            return {"marcadas": 0}
        ahora = time.time()
        with self._lock, self._con() as con:
            cur = con.execute(
                "UPDATE notificaciones SET reportada=1, ts_reportada=?"
                " WHERE id IN (%s) AND reportada=0"
                % ",".join("?" * len(ids)),
                (ahora, *ids))
        return {"marcadas": cur.rowcount}

    # -- dimensiones protegidas ("pero no peor") -----------------------------
    @staticmethod
    def _chequeo_protegidas(costo_usd, presupuesto, bucket):
        """Costo dentro de presupuesto y frenos sanos. En mock (US$0)
        el chequeo pasa trivialmente; el plumbing es real para cuando
        el loop use modelos reales. Sin referencia de presupuesto:
        fail-closed (no se puede verificar → no se adopta)."""
        if presupuesto is None:
            return (False, "sin referencia de presupuesto: dimensiones"
                           " protegidas no verificables (fail-closed)")
        try:
            ok = bool(presupuesto.autorizar(bucket, costo_usd))
        except Exception as e:  # noqa: BLE001
            return False, f"chequeo de presupuesto falló: {e}"
        if not ok:
            return (False, f"freno de presupuesto: el bucket {bucket!r}"
                           f" no autoriza US${float(costo_usd):.4f}")
        return True, "costo dentro de presupuesto, frenos sanos"

    # -- auto-adopción -------------------------------------------------------
    def auto_adoptar(self, scaffold_antes, scaffold_despues,
                     delta_in, delta_ho, motivo_puerta, regla,
                     evidencia=None, claves_permitidas=None,
                     costo_usd=0.0, presupuesto=None,
                     bucket="metaloop"):
        """Auto-adopción gobernada (27/9 ~22:50, refino "pero no peor").

        Solo se adopta ante MEJORA MEDIDA:
          Δ_ho > 0   — mejora estricta en la métrica primaria (held-out)
          Δ_in ≥ 0   — sin regresión en train
          frenos ok  — costo dentro de presupuesto, sin violaciones
        (Más estricto que la puerta, que acepta mejora solo en train.
        La puerta no se toca: está en el núcleo protegido.)

        Lo que mida igual o peor NO se adopta: se registra el rechazo
        con los números y se sigue. Toda adopción es reversible y se
        notifica al usuario.
        """
        antes = dict(scaffold_antes)
        despues = dict(scaffold_despues)
        diff = _diff_scaffold(antes, despues)
        base = {
            "diff": diff,
            "delta_in": round(float(delta_in), 4),
            "delta_ho": round(float(delta_ho), 4),
            "motivo_puerta": motivo_puerta,
            "regla": regla,
            "costo_usd": float(costo_usd or 0.0),
        }
        # 1. Núcleo protegido: raise + log + aviso, nada se aplica.
        try:
            self._verificar_nucleo(diff, claves_permitidas)
        except NucleoProtegidoError as e:
            self._bloquear_nucleo(str(e), {**base,
                                           "scaffold_despues": despues})
        # 2. "Pero no peor": mejora estricta en la métrica primaria.
        d_in, d_ho = float(delta_in), float(delta_ho)
        if not (d_ho > 0):
            return self._rechazar_auto(
                base, antes, despues, evidencia,
                f"sin mejora estricta en held-out: Δ_ho={d_ho:.4f}"
                f" (igual o peor no se adopta)")
        if not (d_in >= 0):
            return self._rechazar_auto(
                base, antes, despues, evidencia,
                f"regresión en train: Δ_in={d_in:.4f}")
        # 3. Dimensiones protegidas: costo y frenos.
        frenos_ok, motivo_frenos = self._chequeo_protegidas(
            float(costo_usd or 0.0), presupuesto, bucket)
        if not frenos_ok:
            return self._rechazar_auto(
                base, antes, despues, evidencia, motivo_frenos)
        # 4. Commit: el único otro lugar donde el scaffold vigente cambia
        #    (además de aprobar() manual y revertir_adopcion()).
        if self.aplicar_fn is None:
            return self._rechazar_auto(
                base, antes, despues, evidencia,
                "sin aplicar_fn: el commit no está cableado")
        try:
            self.aplicar_fn(
                despues,
                origen="auto_adopcion gobernada (mejora medida)")
        except Exception as e:  # noqa: BLE001
            return self._rechazar_auto(
                base, antes, despues, evidencia,
                f"falló el commit: {e}")
        # 5. Registro reversible + notificación.
        efecto = {"delta_ho": round(d_ho, 4), "delta_in": round(d_in, 4),
                  "metrica": "regret (menor es mejor)",
                  "frenos": motivo_frenos}
        revertir = {
            "instruccion": ("revertir_adopcion(id): re-asienta el"
                            " scaffold previo"),
            "scaffold_previo": antes,
        }
        notif_id = self._notificar(
            "auto_adopcion",
            f"ALMA mejoró sola: {self._resumen_diff(diff)}",
            {**base, "efecto_medido": efecto,
             "evidencia": evidencia or {},
             "revertir": ("revertir_adopcion con el scaffold previo"
                          " registrado en la adopción")})
        with self._lock, self._con() as con:
            cur = con.execute(
                """INSERT INTO adopciones
                   (ts, modo, estado, scaffold_antes_json,
                    scaffold_despues_json, diff_json, delta_in, delta_ho,
                    motivo_puerta, regla, efecto_medido_json,
                    evidencia_json, revertir_json, notificacion_id)
                   VALUES (?, 'auto', 'adoptada', ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?)""",
                (time.time(), _canonical(antes), _canonical(despues),
                 _canonical(diff), d_in, d_ho,
                 str(motivo_puerta or ""), str(regla or ""),
                 _canonical(efecto), _canonical(evidencia or {}),
                 _canonical(revertir), notif_id))
            adop_id = cur.lastrowid
        detalle = {**base, "adopcion_id": adop_id,
                   "efecto_medido": efecto,
                   "revertir": "revertir_adopcion(%d)" % adop_id}
        self._emitir("auto_adopcion", "promotor", detalle)
        self._asentar_ledger({"tipo": "auto_adopcion", **detalle})
        return {"adoptada": True, "id": adop_id, "diff": diff,
                "efecto_medido": efecto,
                "revertir": f"revertir_adopcion({adop_id})",
                "notificacion_id": notif_id}

    def _rechazar_auto(self, base, antes, despues, evidencia, motivo):
        """Igual o peor: no se adopta, se registra el rechazo con los
        números y se sigue. (No notifica al chat: es rutina; el digest
        dominical lo cubre.)"""
        with self._lock, self._con() as con:
            cur = con.execute(
                """INSERT INTO adopciones
                   (ts, modo, estado, scaffold_antes_json,
                    scaffold_despues_json, diff_json, delta_in, delta_ho,
                    motivo_puerta, regla, evidencia_json, motivo_rechazo)
                   VALUES (?, 'auto', 'rechazada', ?, ?, ?, ?, ?, ?, ?, ?,
                           ?)""",
                (time.time(), _canonical(antes), _canonical(despues),
                 _canonical(base["diff"]), base["delta_in"],
                 base["delta_ho"], str(base["motivo_puerta"] or ""),
                 str(base["regla"] or ""), _canonical(evidencia or {}),
                 str(motivo)))
            rid = cur.lastrowid
        detalle = {**base, "rechazo_id": rid, "motivo_rechazo": motivo}
        self._emitir("auto_adopcion_rechazada", "promotor", detalle)
        self._asentar_ledger({"tipo": "auto_adopcion_rechazada", **detalle})
        return {"adoptada": False, "id": rid, "motivo": motivo,
                "diff": base["diff"]}

    @staticmethod
    def _resumen_diff(diff):
        piezas = [f"{k}: {v[0]}→{v[1]}" for k, v in sorted(diff.items())]
        return ", ".join(piezas) if piezas else "sin cambios"

    def revertir_adopcion(self, adopcion_id):
        """Deshace una auto-adopción: re-asienta el scaffold previo
        registrado. Toda adopción es reversible por construcción."""
        if self.revertir_fn is None:
            return {"revertida": False,
                    "motivo": "sin revertir_fn cableado"}
        with self._lock, self._con() as con:
            fila = con.execute(
                "SELECT * FROM adopciones WHERE id=? AND modo='auto'"
                " AND estado='adoptada'",
                (int(adopcion_id),)).fetchone()
        if fila is None:
            return {"revertida": False,
                    "motivo": f"adopción inexistente o no adoptada:"
                              f" {adopcion_id}"}
        previo = json.loads(fila["scaffold_antes_json"])
        try:
            self.revertir_fn(
                previo,
                origen=f"revertir_adopcion id={fila['id']}")
        except Exception as e:  # noqa: BLE001
            return {"revertida": False, "motivo": f"falló: {e}"}
        detalle = {"adopcion_id": int(fila["id"]),
                   "restaurado": previo}
        self._emitir("auto_adopcion_revertida", "promotor", detalle)
        self._asentar_ledger({"tipo": "auto_adopcion_revertida",
                              **detalle})
        self._notificar("auto_adopcion_revertida",
                        "Se revirtió una mejora auto-adoptada", detalle)
        return {"revertida": True, "id": int(fila["id"]),
                "scaffold": previo}

    def adopciones_recientes(self, n=10):
        """Historial de adopciones y rechazos del camino automático."""
        with self._lock, self._con() as con:
            filas = con.execute(
                "SELECT id, ts, modo, estado, diff_json, delta_in,"
                " delta_ho, motivo_rechazo, notificacion_id"
                " FROM adopciones ORDER BY id DESC LIMIT ?",
                (int(n),)).fetchall()
        out = []
        for f in filas:
            d = dict(f)
            d["diff"] = json.loads(d.pop("diff_json") or "{}")
            out.append(d)
        return out

    # -- pipeline -------------------------------------------------------
    def proponer(self, scaffold_antes, scaffold_despues, delta_in,
                 delta_ho, motivo_puerta, regla, evidencia=None):
        """Un PASS de la puerta entra a staging. Solo uno en espera.

        evidencia: dict libre y auditable (seed, rondas, preregistro,
        keeps, heldout_anterior/candidato, origen de la corrida...).
        Retorna {"propuesto": bool, ...}.
        """
        antes = dict(scaffold_antes)
        despues = dict(scaffold_despues)
        with self._lock, self._con() as con:
            fila = con.execute(
                "SELECT id FROM staging_promociones WHERE estado=?"
                " LIMIT 1", (ESTADO_ESPERA,)).fetchone()
            if fila:
                return {"propuesto": False,
                        "motivo": ("ya hay una promoción en espera"
                                   f" (id={fila['id']}); una línea de"
                                   " evolución por vez"),
                        "pendiente_id": fila["id"]}
            cur = con.execute(
                """INSERT INTO staging_promociones
                   (ts_creada, estado, scaffold_antes_json,
                    scaffold_despues_json, diff_json, delta_in, delta_ho,
                    motivo_puerta, regla, evidencia_json)
                   VALUES (?, 'en_espera', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (time.time(), _canonical(antes), _canonical(despues),
                 _canonical(_diff_scaffold(antes, despues)),
                 float(delta_in), float(delta_ho),
                 str(motivo_puerta or ""), str(regla or ""),
                 _canonical(evidencia or {})))
            pid = cur.lastrowid
        detalle = {"promo_id": pid, "diff": _diff_scaffold(antes, despues),
                   "delta_in": round(float(delta_in), 4),
                   "delta_ho": round(float(delta_ho), 4),
                   "motivo_puerta": motivo_puerta}
        self._emitir("promocion_staging", "promotor", detalle)
        self._asentar_ledger({"tipo": "promocion_staging", **detalle})
        return {"propuesto": True, "id": pid, **detalle}

    def pendiente(self):
        """La promoción en espera, o None. Es lo que él inspecciona."""
        with self._lock, self._con() as con:
            fila = con.execute(
                "SELECT * FROM staging_promociones WHERE estado=?"
                " ORDER BY id DESC LIMIT 1",
                (ESTADO_ESPERA,)).fetchone()
        return self._fila(fila) if fila else None

    def inspeccionar(self, promo_id):
        """Detalle completo e inspeccionable de una promoción.

        Qué cambia (diff), qué Δ medido la justifica (deltas + motivo
        de la puerta), en qué splits pasó (evidencia con heldout y
        train), y el lineage (preregistro, seed, rondas).
        """
        with self._lock, self._con() as con:
            fila = con.execute(
                "SELECT * FROM staging_promociones WHERE id=?",
                (int(promo_id),)).fetchone()
        if fila is None:
            return None
        return self._fila(fila)

    @staticmethod
    def _fila(f):
        d = dict(f)
        return {
            "id": d["id"],
            "ts_creada": d["ts_creada"],
            "estado": d["estado"],
            "scaffold_antes": json.loads(d["scaffold_antes_json"]),
            "scaffold_despues": json.loads(d["scaffold_despues_json"]),
            "diff": json.loads(d["diff_json"]),
            "delta_in": d["delta_in"],
            "delta_ho": d["delta_ho"],
            "motivo_puerta": d["motivo_puerta"],
            "regla": d["regla"],
            "evidencia": json.loads(d["evidencia_json"]),
            "ts_resuelta": d["ts_resuelta"],
            "aprobador": d["aprobador"],
            "motivo_rechazo": d["motivo_rechazo"],
        }

    def aprobar(self, promo_id, aprobador="humano"):
        """Gate humano explícito. Solo un aprobador de la allowlist
        aprueba; solo entonces se hace el commit vía aplicar_fn."""
        if aprobador not in APROBADORES:
            return {"aprobada": False,
                    "motivo": f"aprobador no autorizado: {aprobador!r}"
                              f" (allowlist: {list(APROBADORES)})"}
        with self._lock, self._con() as con:
            fila = con.execute(
                "SELECT * FROM staging_promociones WHERE id=?",
                (int(promo_id),)).fetchone()
            if fila is None:
                return {"aprobada": False,
                        "motivo": f"promoción inexistente: {promo_id}"}
            if fila["estado"] != ESTADO_ESPERA:
                return {"aprobada": False,
                        "motivo": (f"la promoción {promo_id} ya está"
                                   f" {fila['estado']}; no se aprueba"
                                   " dos veces")}
            despues = json.loads(fila["scaffold_despues_json"])
            diff = json.loads(fila["diff_json"])
            # Núcleo protegido (defensa en profundidad): también el camino
            # manual rechaza un diff que toque el núcleo. Sin superficie
            # declarada, solo bloquea las claves exactas del núcleo.
            try:
                self._verificar_nucleo(diff, claves_permitidas=None)
            except NucleoProtegidoError as e:
                self._bloquear_nucleo(
                    str(e), {"promo_id": int(promo_id), "diff": diff,
                             "camino": "manual"})
            # El commit: SOLO acá se toca el scaffold vigente.
            if self.aplicar_fn is None:
                return {"aprobada": False,
                        "motivo": "sin aplicar_fn: el commit no está"
                                  " cableado (no se aprueba en el vacío)"}
            try:
                self.aplicar_fn(
                    despues,
                    origen=(f"promocion_aprobada id={fila['id']}"
                            f" aprobador={aprobador}"))
            except Exception as e:  # noqa: BLE001 - el staging no
                # debe quedar en un estado ambiguo si el commit falla
                return {"aprobada": False,
                        "motivo": f"falló el commit: {e}"}
            ahora = time.time()
            con.execute(
                "UPDATE staging_promociones SET estado='aprobada',"
                " ts_resuelta=?, aprobador=? WHERE id=?",
                (ahora, str(aprobador), int(promo_id)))
        detalle = {"promo_id": int(promo_id), "aprobador": aprobador,
                   "diff": diff, "scaffold_despues": despues}
        self._emitir("promocion_aprobada", aprobador, detalle)
        self._asentar_ledger({"tipo": "promocion_aprobada", **detalle})
        return {"aprobada": True, "id": int(promo_id),
                "aprobador": aprobador, "diff": diff}

    def rechazar(self, promo_id, motivo, aprobador="humano"):
        """Archiva la promoción con su motivo. El sistema sigue con el
        scaffold vigente: el rechazo no rompe nada."""
        if aprobador not in APROBADORES:
            return {"rechazada": False,
                    "motivo": f"aprobador no autorizado: {aprobador!r}"
                              f" (allowlist: {list(APROBADORES)})"}
        if not (motivo or "").strip():
            return {"rechazada": False,
                    "motivo": "el rechazo exige un motivo (trazabilidad)"}
        with self._lock, self._con() as con:
            fila = con.execute(
                "SELECT * FROM staging_promociones WHERE id=?",
                (int(promo_id),)).fetchone()
            if fila is None:
                return {"rechazada": False,
                        "motivo": f"promoción inexistente: {promo_id}"}
            if fila["estado"] != ESTADO_ESPERA:
                return {"rechazada": False,
                        "motivo": (f"la promoción {promo_id} ya está"
                                   f" {fila['estado']}")}
            ahora = time.time()
            con.execute(
                "UPDATE staging_promociones SET estado='rechazada',"
                " ts_resuelta=?, aprobador=?, motivo_rechazo=?"
                " WHERE id=?",
                (ahora, str(aprobador), str(motivo), int(promo_id)))
        detalle = {"promo_id": int(promo_id), "aprobador": aprobador,
                   "motivo_rechazo": motivo}
        self._emitir("promocion_rechazada", aprobador, detalle)
        self._asentar_ledger({"tipo": "promocion_rechazada", **detalle})
        return {"rechazada": True, "id": int(promo_id),
                "aprobador": aprobador, "motivo": motivo}

    def historial(self, n=20):
        """Promociones resueltas y en espera (las rechazadas se archivan
        acá con su motivo: evidencia, no basura)."""
        with self._lock, self._con() as con:
            filas = con.execute(
                "SELECT * FROM staging_promociones ORDER BY id DESC"
                " LIMIT ?", (int(n),)).fetchall()
        return [self._fila(f) for f in filas]
