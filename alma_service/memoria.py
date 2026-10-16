"""Memoria de experiencias con olvido — fase 0.

Extiende (no duplica) servicio/store_sqlite.py: el ledger append-only con
hash encadenado se hereda intacto. Esta capa agrega lo que el diseño §1.2
exige y Hermes no tiene:

- Toda memoria lleva timestamp; el retrieval pondera por decaimiento
  temporal 0.5^días (EXP9: el prior decaído gana al uniforme tras un flip).
- Capacidad acotada con evicción: la memoria no crece sin límite. Evictar
  es lógico (estado='archivada'), nunca DELETE: el ledger queda intacto y
  verify_chain() sigue pasando.

Utilidad de una experiencia (para evicción):
    utilidad = peso_temporal(ts) * (1 + max(reward, 0)) * (1 + log1p(usos))
Lo que no se usa y no rinde, se archiva. Lo archivado no entra al prior.
"""

import json
import math
import time

from servicio.store_sqlite import SQLiteStore

from alma_service.procedencia import crear_tabla_memoria

# Song (h): lo en cuarentena NO alimenta decisiones. Legado sin registro
# de procedencia se trata como propio (ver procedencia.py).
_EXCLUYE_CUARENTENA = (
    "AND NOT EXISTS (SELECT 1 FROM memoria_procedencia p"
    " WHERE p.experiencia_id = e.id AND p.cuarentena = 1)"
)


class MemoriaExperiencias(SQLiteStore):
    """SQLiteStore + olvido + evicción acotada."""

    def __init__(self, path, tasa_olvido=0.5):
        super().__init__(path)
        self.tasa_olvido = float(tasa_olvido)
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS memoria_estado (
                   experiencia_id INTEGER PRIMARY KEY,
                   estado TEXT NOT NULL DEFAULT 'activa',
                   usos INTEGER NOT NULL DEFAULT 0,
                   ultimo_uso REAL,
                   utilidad REAL NOT NULL DEFAULT 0.0
               )"""
        )
        # Resumen de probes por bloque: lo que el ProveedorSkills real
        # necesita para computar soporte pareado (wins) sin releer cada
        # experiencia. (bloque, firma, brazo) -> n mediciones, suma rewards.
        # Solo probes "limpios" (Q1/Q2, brazos medidos sin skill) se
        # registran acá; la explotación con skill no contamina el soporte.
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS probe_bloques (
                   bloque INTEGER NOT NULL,
                   firma TEXT NOT NULL,
                   brazo TEXT NOT NULL,
                   n INTEGER NOT NULL,
                   suma REAL NOT NULL,
                   PRIMARY KEY (bloque, firma, brazo)
               )"""
        )
        # Song (h): procedencia de experiencias. Lo en cuarentena no
        # alimenta decisiones (ver recuperar_con_decaimiento y la
        # evicción, que archiva primero lo en cuarentena).
        crear_tabla_memoria(self._db)
        self._db.commit()

    # -- olvido ---------------------------------------------------------
    def peso_temporal(self, timestamp, ahora=None):
        """0.5^días desde el timestamp (EXP9). Lo nuevo pesa más."""
        ahora = ahora if ahora is not None else time.time()
        dias = max(0.0, (ahora - float(timestamp)) / 86400.0)
        return self.tasa_olvido ** dias

    def _estado(self, exp_id):
        fila = self._db.execute(
            "SELECT estado, usos, utilidad FROM memoria_estado"
            " WHERE experiencia_id = ?",
            (exp_id,),
        ).fetchone()
        if fila:
            return fila["estado"], fila["usos"], fila["utilidad"]
        return "activa", 0, 0.0

    def recuperar_con_decaimiento(self, clase, ahora=None,
                                  incluir_archivadas=False):
        """Como recompensas_por_clase, pero cada experiencia pesa
        0.5^días. Retorna [(arch_id, reward, peso)]. Las archivadas no
        entran salvo pedido explícito."""
        ahora = ahora if ahora is not None else time.time()
        out = []
        cur = self._db.execute(
            """SELECT e.id, e.arch_id, e.metricas, e.timestamp,
                      COALESCE(m.estado, 'activa') AS estado
               FROM experiencias e
               LEFT JOIN memoria_estado m ON m.experiencia_id = e.id
               WHERE e.clase = ? """ + _EXCLUYE_CUARENTENA + """
               ORDER BY e.timestamp""",
            (clase,),
        )
        for fila in cur.fetchall():
            if fila["estado"] != "activa" and not incluir_archivadas:
                continue
            try:
                met = json.loads(fila["metricas"])
                r = met.get("reward")
            except (ValueError, TypeError):
                continue
            if r is None:
                continue
            if isinstance(met, dict) and met.get("modo_agente") == "bateria":
                continue
            out.append((fila["arch_id"], float(r),
                        self.peso_temporal(fila["timestamp"], ahora)))
        # feedback explícito, con el mismo join de estado
        cur = self._db.execute(
            """SELECT e.arch_id, f.reward, f.timestamp,
                      COALESCE(m.estado, 'activa') AS estado
               FROM feedback f
               JOIN experiencias e ON e.id = f.experiencia_id
               LEFT JOIN memoria_estado m ON m.experiencia_id = e.id
               WHERE e.clase = ? """ + _EXCLUYE_CUARENTENA + """
               ORDER BY f.timestamp""",
            (clase,),
        )
        for fila in cur.fetchall():
            if fila["estado"] != "activa" and not incluir_archivadas:
                continue
            out.append((fila["arch_id"], float(fila["reward"]),
                        self.peso_temporal(fila["timestamp"], ahora)))
        return out

    # -- uso y utilidad ---------------------------------------------------
    def registrar_uso(self, experiencia_id, reward, ahora=None):
        """Una experiencia usada suma a su utilidad (para evicción)."""
        ahora = ahora if ahora is not None else time.time()
        fila = self._db.execute(
            "SELECT usos FROM memoria_estado WHERE experiencia_id = ?",
            (experiencia_id,),
        ).fetchone()
        usos = (fila["usos"] if fila else 0) + 1
        fila_exp = self._db.execute(
            "SELECT timestamp FROM experiencias WHERE id = ?",
            (experiencia_id,),
        ).fetchone()
        ts = fila_exp["timestamp"] if fila_exp else ahora
        utilidad = (self.peso_temporal(ts, ahora)
                    * (1.0 + max(0.0, float(reward)))
                    * (1.0 + math.log1p(usos)))
        self._db.execute(
            """INSERT INTO memoria_estado
                   (experiencia_id, estado, usos, ultimo_uso, utilidad)
               VALUES (?, 'activa', ?, ?, ?)
               ON CONFLICT(experiencia_id) DO UPDATE SET
                   usos = excluded.usos,
                   ultimo_uso = excluded.ultimo_uso,
                   utilidad = excluded.utilidad""",
            (experiencia_id, usos, ahora, utilidad),
        )
        self._db.commit()
        return utilidad

    # -- evicción acotada (lógica, nunca DELETE) ---------------------------
    def contar_activas(self):
        n_total = self.contar()
        n_arch = self._db.execute(
            "SELECT COUNT(*) c FROM memoria_estado WHERE estado='archivada'"
        ).fetchone()["c"]
        return n_total - n_arch

    def aplicar_eviccion(self, max_activas, ahora=None):
        """Si hay más de max_activas experiencias activas, archiva las de
        menor utilidad hasta quedar en el tope. Retorna los ids archivados.
        El ledger no se toca: verify_chain() sigue pasando."""
        ahora = ahora if ahora is not None else time.time()
        archivadas = []
        while self.contar_activas() > max_activas:
            fila = self._db.execute(
                """SELECT e.id, e.timestamp,
                          COALESCE(m.utilidad, -1.0) AS utilidad
                   FROM experiencias e
                   LEFT JOIN memoria_estado m
                     ON m.experiencia_id = e.id
                   LEFT JOIN memoria_procedencia p
                     ON p.experiencia_id = e.id
                   WHERE COALESCE(m.estado, 'activa') = 'activa'
                   ORDER BY COALESCE(p.cuarentena, 0) DESC,
                            utilidad ASC, e.timestamp ASC
                   LIMIT 1"""
            ).fetchone()
            if not fila:
                break
            if fila["utilidad"] < 0:
                # sin utilidad registrada: la estima por recencia pura
                util = self.peso_temporal(fila["timestamp"], ahora)
            else:
                util = fila["utilidad"]
            self._db.execute(
                """INSERT INTO memoria_estado (experiencia_id, estado,
                                               utilidad)
                   VALUES (?, 'archivada', ?)
                   ON CONFLICT(experiencia_id) DO UPDATE SET
                       estado = 'archivada'""",
                (fila["id"], util),
            )
            self._db.commit()
            archivadas.append(fila["id"])
        return archivadas

    # -- resumen de probes por bloque (soporte pareado del proveedor) -----
    def registrar_bloque_probe(self, bloque, firma, obs):
        """Guarda el resumen de un probe.

        obs: dict brazo -> [rewards] con lo medido (Q1 siempre; Q2 solo
        si no hubo gate — igual que el mock EXP51, donde los bloques con
        gate dejan probe_obs más ruidoso). Solo mediciones raw (sin
        skill): la explotación guiada no contamina el soporte.
        Sobrescribe si el bloque ya estaba (idempotente)."""
        for brazo, rewards in obs.items():
            if not rewards:
                continue
            self._db.execute(
                """INSERT INTO probe_bloques
                       (bloque, firma, brazo, n, suma)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(bloque, firma, brazo) DO UPDATE SET
                       n = excluded.n, suma = excluded.suma""",
                (int(bloque), str(firma), str(brazo), len(rewards),
                 float(sum(rewards))),
            )
        self._db.commit()

    def soporte_firma(self, firma, hasta_bloque, brazo_skill):
        """Soporte pareado estilo EXP49 sobre probes reales.

        Para cada bloque < hasta_bloque con la misma firma y probe
        completo: win si media(brazo_skill) > media(cada otro brazo)
        en forma estricta. Retorna (wins, K) con K = #bloques comparables.
        """
        cur = self._db.execute(
            """SELECT bloque, brazo, n, suma FROM probe_bloques
               WHERE firma = ? AND bloque < ? ORDER BY bloque, brazo""",
            (str(firma), int(hasta_bloque)),
        )
        por_bloque = {}
        for fila in cur.fetchall():
            b = por_bloque.setdefault(fila["bloque"], {})
            b[fila["brazo"]] = fila["suma"] / fila["n"] if fila["n"] else 0.0
        wins, K = 0, 0
        for b, medias in por_bloque.items():
            if brazo_skill not in medias or len(medias) < 2:
                continue
            K += 1
            m_skill = medias[brazo_skill]
            if all(m_skill > m for a, m in medias.items()
                   if a != brazo_skill):
                wins += 1
        return wins, K

    # -- detalle de experiencias (para el generador de skills) ------------
    def experiencias_detalle(self, clase, n=12):
        """Últimas n experiencias con reward de una clase, con enunciado.

        Retorna dicts {id, arch_id, reward, enunciado, timestamp}. El
        enunciado se guarda en features['enunciado'] al registrar (lo pone
        el motor de fase 1). Las archivadas se excluyen: la skill se
        genera desde memoria viva.
        """
        cur = self._db.execute(
            """SELECT e.id, e.arch_id, e.metricas, e.features, e.timestamp,
                      COALESCE(m.estado, 'activa') AS estado
               FROM experiencias e
               LEFT JOIN memoria_estado m ON m.experiencia_id = e.id
               WHERE e.clase = ? AND COALESCE(m.estado, 'activa') = 'activa'
               """ + _EXCLUYE_CUARENTENA + """
               ORDER BY e.timestamp DESC LIMIT ?""",
            (str(clase), int(n)),
        )
        out = []
        for fila in cur.fetchall():
            try:
                met = json.loads(fila["metricas"])
                r = met.get("reward")
            except (ValueError, TypeError):
                continue
            if r is None:
                continue
            try:
                feat = json.loads(fila["features"])
                enunciado = feat.get("enunciado", "")
            except (ValueError, TypeError):
                enunciado = ""
            out.append({"id": fila["id"], "arch_id": fila["arch_id"],
                        "reward": float(r), "enunciado": enunciado,
                        "timestamp": fila["timestamp"]})
        return out
