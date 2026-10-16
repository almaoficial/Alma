"""Presupuesto fase 2 — topes duros por bucket, modo barato por default.

Diseño §4.3/§4.4: ningún componente gasta sin bucket asignado; si un bucket
se agota, el componente se degrada a modo barato, no pide más.

Regla dura: SIN presupuesto mensual configurado (ALMA_PRESUPUESTO_MENSUAL=0,
el default), TODO corre en modo barato: la key arranca APAGADA. Los llamados
a `autorizar()` con costo estimado > 0 devuelven False y el llamador usa el
camino demo/mock. Esto no es una sugerencia: es el gate que separa "puede
gastar" de "no puede gastar".

Buckets (diseño §4.2/§4.3):
  servicio_diario  — resoluciones con modelos reales del servicio
  metaloop         — el loop RSO (en mock US$0 siempre autorizado)
  curator          — consolidación LLM opt-in (apagada por default)
  revision_bg      — revisión de background (heurística US$0 por default)

Persistencia: tabla `gasto_mensual` (bucket, mes, gastado), aditiva,
CREATE TABLE IF NOT EXISTS. Nunca se borra ni se migra: el gasto pasado
es evidencia.
"""

import os
import sqlite3
import threading
import time

BUCKET_SERVICIO = "servicio_diario"
BUCKET_METALOOP = "metaloop"
BUCKET_CURATOR = "curator"
BUCKET_REVISION = "revision_bg"

BUCKETS = (BUCKET_SERVICIO, BUCKET_METALOOP, BUCKET_CURATOR,
           BUCKET_REVISION)

# Reparto default del tope mensual por bucket (fracciones que suman 1).
REPARTO_DEFAULT = {
    BUCKET_SERVICIO: 0.70,
    BUCKET_METALOOP: 0.20,
    BUCKET_CURATOR: 0.05,
    BUCKET_REVISION: 0.05,
}

MODO_BARATO = "barato"
MODO_NORMAL = "normal"


def _mes_actual(ts=None):
    return time.strftime("%Y-%m", time.localtime(ts or time.time()))


class PresupuestoFase2:
    """Topes mensuales duros por bucket, con degradación a modo barato."""

    def __init__(self, db_path, tope_mensual_usd=None, reparto=None):
        if tope_mensual_usd is None:
            tope_mensual_usd = float(
                os.environ.get("ALMA_PRESUPUESTO_MENSUAL", "0.0"))
        self.tope_mensual = max(0.0, float(tope_mensual_usd))
        self.reparto = dict(reparto or REPARTO_DEFAULT)
        for b in self.reparto:
            if b not in BUCKETS:
                raise ValueError(f"bucket desconocido: {b!r}")
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    # -- persistencia (aditiva) -------------------------------------------
    def _con(self):
        con = sqlite3.connect(self._db_path, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init_db(self):
        with self._con() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS gasto_mensual (
                       bucket TEXT NOT NULL,
                       mes TEXT NOT NULL,
                       gastado REAL NOT NULL DEFAULT 0,
                       PRIMARY KEY (bucket, mes)
                   )""")

    # -- lectura ------------------------------------------------------------
    def modo(self):
        """barato si no hay tope mensual configurado; normal si lo hay."""
        return MODO_NORMAL if self.tope_mensual > 0 else MODO_BARATO

    def limite(self, bucket):
        self._validar_bucket(bucket)
        return self.tope_mensual * self.reparto.get(bucket, 0.0)

    def gastado(self, bucket, mes=None):
        self._validar_bucket(bucket)
        mes = mes or _mes_actual()
        with self._con() as con:
            fila = con.execute(
                "SELECT gastado FROM gasto_mensual WHERE bucket=? AND mes=?",
                (bucket, mes)).fetchone()
        return float(fila[0]) if fila else 0.0

    def disponible(self, bucket):
        return max(0.0, self.limite(bucket) - self.gastado(bucket))

    # -- gate de gasto -------------------------------------------------------
    def autorizar(self, bucket, costo_estimado_usd):
        """True ssi el bucket puede cubrir el costo estimado este mes.

        Nunca corta con excepción: el llamador se degrada a modo barato.
        Un costo estimado de 0 (mock/demo) siempre se autoriza.
        """
        self._validar_bucket(bucket)
        costo = max(0.0, float(costo_estimado_usd))
        if costo == 0.0:
            return True
        with self._lock:
            return self.disponible(bucket) >= costo

    def cargar(self, bucket, monto_usd, mes=None):
        """Registra gasto real. Aditivo; no valida (la validación es previa,
        en autorizar). Devuelve lo gastado acumulado del mes."""
        self._validar_bucket(bucket)
        monto = max(0.0, float(monto_usd))
        mes = mes or _mes_actual()
        with self._lock, self._con() as con:
            con.execute(
                """INSERT INTO gasto_mensual (bucket, mes, gastado)
                   VALUES (?, ?, ?)
                   ON CONFLICT (bucket, mes)
                   DO UPDATE SET gastado = gastado + excluded.gastado""",
                (bucket, mes, monto))
            fila = con.execute(
                "SELECT gastado FROM gasto_mensual WHERE bucket=? AND mes=?",
                (bucket, mes)).fetchone()
        return float(fila[0])

    def estado(self):
        return {
            "modo": self.modo(),
            "tope_mensual_usd": self.tope_mensual,
            "mes": _mes_actual(),
            "buckets": {
                b: {"limite": round(self.limite(b), 4),
                    "gastado": round(self.gastado(b), 4),
                    "disponible": round(self.disponible(b), 4)}
                for b in BUCKETS
            },
        }

    @staticmethod
    def _validar_bucket(bucket):
        if bucket not in BUCKETS:
            raise ValueError(f"bucket desconocido: {bucket!r}")
