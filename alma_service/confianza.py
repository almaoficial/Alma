"""Ciclo de confianza provisional→trusted — de OpenSpace (HKUDS).

OpenSpace: toda skill nueva/evolucionada nace `provisional`; el uso
exitoso *independiente* la promueve a `trusted`; un fallo *atribuible*
la degrada (reversible). Los candidatos inciertos quedan audit-only.

Adaptación a ALMA: la confianza es una dimensión ORTOGONAL al ciclo
active→stale→archived del Curator (que no se toca y sigue siendo el
mecanismo primario contra el bloat). Tabla propia `skill_confianza`;
el schema de `skills.py` no se modifica.

Reglas deterministas, sin LLM:
- Nace provisional (`registrar`).
- Promoción a trusted: exitos_verificados >= UMBRAL_EXITOS (3). Los
  éxitos los certifica una FUENTE INDEPENDIENTE
  (`certificar_exito(path, fuente)` con fuente en FUENTES_VERIFICADORAS);
  el auto-reporte (`marcar_uso(exito=True)`) cuenta como telemetría pero
  NUNCA promueve (Fix A5b, red-team: el éxito lo declara quien lo
  reporta). "auto" no está en la allowlist por diseño.
- Degradación: solo ante fallo ATRIBUIBLE explícito
  (`marcar_fallo(path, atribuible=True)`); vuelve a provisional y puede
  re-ganar la confianza (reversible). Un fallo no atribuible no degrada
  (caveat del informe: la atribución es ruidosa; por default no se
  asume).
- Métricas con intervalo de Wilson (crítica OMNEX: "una skill usada dos
  veces puntúa igual que una con 200 usos" — acá no).

Nunca se hereda trust de terceros: `importar_externa` siempre nace
provisional (fail closed, como el upload trust-gated de OpenSpace).
"""

import math
import sqlite3
import time

CONFIANZA_PROVISIONAL = "provisional"
CONFIANZA_TRUSTED = "trusted"

UMBRAL_EXITOS = 3  # éxitos VERIFICADOS para graduarse
Z_95 = 1.96

# Fix A5b (red-team): fuentes habilitadas a certificar un éxito. El
# éxito lo confirma una fuente distinta de quien reporta el uso:
# "auto" (auto-reporte) NO está en la lista por diseño. Alcance honesto:
# dentro del proceso no se autentica al llamante (código confiable);
# la amenaza cubierta es contenido malicioso (skills/memoria), no un
# atacante con acceso al proceso Python.
FUENTES_VERIFICADORAS = ("validador", "harness", "benchmark", "humano",
                         "revision")


def intervalo_wilson(exitos, n, z=Z_95):
    """Intervalo de Wilson para una proporción. None si n == 0."""
    if n <= 0:
        return None
    p = exitos / n
    den = 1 + z * z / n
    centro = p + z * z / (2 * n)
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centro - margen) / den),
            min(1.0, (centro + margen) / den))


class ConfianzaSkills:
    """Ciclo de confianza por skill, con métricas y degradación reversible."""

    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _con(self):
        con = sqlite3.connect(self.db_path, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init_db(self):
        with self._con() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS skill_confianza (
                       path TEXT PRIMARY KEY,
                       confianza TEXT NOT NULL DEFAULT 'provisional',
                       usos INTEGER NOT NULL DEFAULT 0,
                       exitos INTEGER NOT NULL DEFAULT 0,
                       fallos_atribuibles INTEGER NOT NULL DEFAULT 0,
                       degradaciones INTEGER NOT NULL DEFAULT 0,
                       ultima_transicion REAL NOT NULL
                   )""")
            # Fix A5b: éxitos verificados por fuente independiente.
            # Migración aditiva para DBs ya creadas.
            try:
                con.execute("ALTER TABLE skill_confianza ADD COLUMN"
                            " exitos_verificados INTEGER NOT NULL"
                            " DEFAULT 0")
            except Exception:
                pass  # la columna ya existe

    def registrar(self, path, ahora=None):
        """Nace provisional. Idempotente: si ya existe, no la toca."""
        ahora = ahora if ahora is not None else time.time()
        with self._con() as con:
            con.execute(
                """INSERT INTO skill_confianza
                   (path, confianza, ultima_transicion)
                   VALUES (?, 'provisional', ?)
                   ON CONFLICT(path) DO NOTHING""",
                (path, ahora))

    def importar_externa(self, path, ahora=None, procedencia=None):
        """Skill de terceros: SIEMPRE nace provisional (fail closed).

        El trust nunca se hereda (agujero documentado del hub de
        OpenSpace: evidencia auto-atestiguada). Cuarentena local hasta
        que la propia evidencia la promueva.

        Song (h): si se pasa `procedencia` (ProcedenciaSkills), además
        se registra como origen 'tercero' → cuarentena de procedencia
        (no alimenta decisiones hasta graduación explícita).
        """
        self.registrar(path, ahora=ahora)
        if procedencia is not None:
            procedencia.registrar(path, "tercero", ahora=ahora)
        return {"path": path, "confianza": CONFIANZA_PROVISIONAL,
                "origen": "externa_cuarentena"}

    def marcar_uso(self, path, exito=None, ahora=None):
        """Registra un uso reportado. exito True/False/None (sin veredicto).

        Fix A5b: el auto-reporte es telemetría, NUNCA promueve. La
        promoción a trusted requiere éxitos VERIFICADOS
        (`certificar_exito` con fuente en FUENTES_VERIFICADORAS).
        Retorna la confianza resultante (puede haber promoción si ya hay
        verificados suficientes).
        """
        ahora = ahora if ahora is not None else time.time()
        self.registrar(path, ahora=ahora)
        with self._con() as con:
            if exito is True:
                con.execute(
                    "UPDATE skill_confianza SET usos=usos+1, exitos=exitos+1"
                    " WHERE path=?", (path,))
            elif exito is False:
                con.execute(
                    "UPDATE skill_confianza SET usos=usos+1 WHERE path=?",
                    (path,))
            fila = con.execute(
                "SELECT confianza, exitos_verificados FROM skill_confianza"
                " WHERE path=?", (path,)).fetchone()
            confianza, verif = fila[0], fila[1]
            if (confianza == CONFIANZA_PROVISIONAL
                    and verif >= UMBRAL_EXITOS):
                con.execute(
                    "UPDATE skill_confianza SET confianza='trusted',"
                    " ultima_transicion=? WHERE path=?", (ahora, path))
                confianza = CONFIANZA_TRUSTED
        return {"path": path, "confianza": confianza}

    def certificar_exito(self, path, fuente, ahora=None):
        """Un éxito confirmado por una FUENTE INDEPENDIENTE.

        `fuente` debe estar en FUENTES_VERIFICADORAS ("auto" no vale:
        el auto-reporte no certifica). Solo los éxitos certificados
        cuentan para la promoción a trusted. Retorna {"ok", ...} con la
        confianza resultante.
        """
        ahora = ahora if ahora is not None else time.time()
        if fuente not in FUENTES_VERIFICADORAS:
            return {"ok": False, "path": path,
                    "motivo": f"fuente no verificadora: {fuente!r}"
                              f" (usar {FUENTES_VERIFICADORAS})",
                    "confianza": self.confianza_de(path)}
        self.registrar(path, ahora=ahora)
        with self._con() as con:
            con.execute(
                "UPDATE skill_confianza SET usos=usos+1, exitos=exitos+1,"
                " exitos_verificados=exitos_verificados+1 WHERE path=?",
                (path,))
            fila = con.execute(
                "SELECT confianza, exitos_verificados FROM skill_confianza"
                " WHERE path=?", (path,)).fetchone()
            confianza, verif = fila[0], fila[1]
            if (confianza == CONFIANZA_PROVISIONAL
                    and verif >= UMBRAL_EXITOS):
                con.execute(
                    "UPDATE skill_confianza SET confianza='trusted',"
                    " ultima_transicion=? WHERE path=?", (ahora, path))
                confianza = CONFIANZA_TRUSTED
        return {"ok": True, "path": path, "fuente": fuente,
                "confianza": confianza,
                "exitos_verificados": verif}

    def marcar_fallo(self, path, atribuible=False, ahora=None):
        """Fallo atribuible a la skill → degrada a provisional.

        Solo si atribuible=True explícito (la atribución es ruidosa;
        por default un fallo NO degrada). Reversible: puede re-ganarse.
        """
        ahora = ahora if ahora is not None else time.time()
        self.registrar(path, ahora=ahora)
        with self._con() as con:
            if atribuible:
                con.execute(
                    """UPDATE skill_confianza
                       SET fallos_atribuibles=fallos_atribuibles+1,
                           degradaciones=degradaciones+1,
                           confianza='provisional', ultima_transicion=?
                       WHERE path=?""", (ahora, path))
                degradada = True
            else:
                degradada = False
            fila = con.execute(
                "SELECT confianza FROM skill_confianza WHERE path=?",
                (path,)).fetchone()
        return {"path": path, "confianza": fila[0], "degradada": degradada}

    def confianza_de(self, path):
        with self._con() as con:
            fila = con.execute(
                "SELECT confianza FROM skill_confianza WHERE path=?",
                (path,)).fetchone()
        return fila[0] if fila else CONFIANZA_PROVISIONAL

    def metricas(self, path):
        """Métricas con intervalo de confianza (Wilson)."""
        with self._con() as con:
            fila = con.execute(
                "SELECT confianza, usos, exitos, fallos_atribuibles,"
                " degradaciones, exitos_verificados FROM skill_confianza"
                " WHERE path=?", (path,)).fetchone()
        if not fila:
            return {"path": path, "confianza": CONFIANZA_PROVISIONAL,
                    "usos": 0, "exitos": 0, "tasa_exito": None,
                    "ic95": None, "fallos_atribuibles": 0,
                    "degradaciones": 0, "exitos_verificados": 0}
        usos, exitos = fila[1], fila[2]
        ic = intervalo_wilson(exitos, usos)
        return {
            "path": path,
            "confianza": fila[0],
            "usos": usos,
            "exitos": exitos,
            "exitos_verificados": fila[5],
            "tasa_exito": round(exitos / usos, 4) if usos else None,
            "ic95": ([round(ic[0], 4), round(ic[1], 4)]
                     if ic else None),
            "fallos_atribuibles": fila[3],
            "degradaciones": fila[4],
        }

    def resumen(self):
        with self._con() as con:
            filas = con.execute(
                "SELECT confianza, COUNT(*) FROM skill_confianza"
                " GROUP BY confianza").fetchall()
        return {f[0]: f[1] for f in filas}
