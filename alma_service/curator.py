"""Curator — ciclo de vida determinista de skills, fase 0.

Diseño §1.1.2 (robado de Hermes, §1.2C del estudio): transiciones
deterministas por inactividad, SIN LLM en fase 0:

    active → stale     (14 días sin uso)
    stale  → archived   (30 días sin uso)

Reglas duras:
- Nunca borra: archivar es la acción máxima.
- Solo toca skills con created_by == "agent". Las instaladas de terceros
  (created_by == "externo") y las bundled son intocables por el Curator.
- Ledger append-only con hash encadenado (mismo patrón que alma/store.py):
  toda transición queda auditada y es verificable.

Lo que NO hace en fase 0 (opt-in de fase 2+, requiere aprobación
explícita): consolidación LLM de skills (fusiones/reescrituras amplias).
"""

import hashlib
import json
import os
import time

DIAS_STALE = 14
DIAS_ARCHIVED = 30

# Cherny (d): una skill se queda solo si hay REGISTRO de que evitó un
# fallo repetido. Umbral de "fallo repetido": falló al menos 2 veces en
# la misma firma y la skill lo corrigió. Ventana de evidencia y gracia
# para skills recién creadas (aún no tuvieron chance de demostrar).
UMBRAL_EVIDENCIA = 2
VENTANA_EVIDENCIA_DIAS = 90
GRACIA_CREACION_DIAS = 30

ESTADO_ACTIVE = "active"
ESTADO_STALE = "stale"
ESTADO_ARCHIVED = "archived"

# Solo las creadas por el agente son curables. Las externas/bundled no.
CURABLES = ("agent", "background_review")


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


class LedgerCurator:
    """Ledger append-only con hash encadenado para las transiciones."""

    def __init__(self, path):
        self.path = path
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("")

    def _ultimo_hash(self):
        prev = "GENESIS"
        with open(self.path, "r", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    prev = json.loads(linea)["hash"]
        return prev

    def append(self, evento):
        prev = self._ultimo_hash()
        h = hashlib.sha256()
        h.update(prev.encode("utf-8"))
        h.update(_canonical(evento).encode("utf-8"))
        fila = {"prev_hash": prev, "hash": h.hexdigest(), "evento": evento}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(_canonical(fila) + "\n")
        return fila

    def verificar(self):
        prev = "GENESIS"
        with open(self.path, "r", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                fila = json.loads(linea)
                if fila["prev_hash"] != prev:
                    return False
                h = hashlib.sha256()
                h.update(prev.encode("utf-8"))
                h.update(_canonical(fila["evento"]).encode("utf-8"))
                if fila["hash"] != h.hexdigest():
                    return False
                prev = fila["hash"]
        return True

    def leer(self):
        out = []
        with open(self.path, "r", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    out.append(json.loads(linea))
        return out


class Curator:
    """Barrido determinista del ciclo de vida de skills."""

    def __init__(self, skill_index, ledger_path=None,
                 dias_stale=DIAS_STALE, dias_archived=DIAS_ARCHIVED):
        self.index = skill_index
        self.dias_stale = dias_stale
        self.dias_archived = dias_archived
        self.ledger = LedgerCurator(
            ledger_path or os.path.join(
                os.path.dirname(os.path.abspath(skill_index.path)),
                "curator_ledger.jsonl"))
        # Cherny (d): registro de evitaciones. Tabla aditiva, IF NOT
        # EXISTS. Cada vez que una skill evita un fallo que antes se
        # repitió en la misma firma, queda asentado acá.
        self.index._db.execute("""CREATE TABLE IF NOT EXISTS
            evitaciones_skill (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_path TEXT NOT NULL,
            firma TEXT NOT NULL,
            fallos_previos INTEGER NOT NULL,
            timestamp REAL NOT NULL)""")
        self.index._db.commit()
        # Fase 2.2: event log unificado (lo cablea server.py). None =
        # no emite; el barrido no cambia su comportamiento.
        self.event_log = None

    def barrer(self, ahora=None):
        """Aplica transiciones deterministas. Retorna la lista de
        transiciones aplicadas (dicts)."""
        ahora = ahora if ahora is not None else time.time()
        aplicadas = []
        for fila in self.index.listar(estado=ESTADO_ACTIVE):
            if fila["created_by"] not in CURABLES:
                continue
            dias = self.index.antiguedad_uso(fila["path"], ahora)
            if dias is not None and dias > self.dias_stale:
                aplicadas.append(self._transicionar(
                    fila, ESTADO_ACTIVE, ESTADO_STALE, dias, ahora))
        for fila in self.index.listar(estado=ESTADO_STALE):
            if fila["created_by"] not in CURABLES:
                continue
            dias = self.index.antiguedad_uso(fila["path"], ahora)
            if dias is not None and dias > self.dias_archived:
                aplicadas.append(self._transicionar(
                    fila, ESTADO_STALE, ESTADO_ARCHIVED, dias, ahora))
        return aplicadas

    def _transicionar(self, fila, desde, hacia, dias_sin_uso, ahora):
        self.index.transicionar(fila["path"], hacia)
        evento = {
            "skill": fila["path"],
            "name": fila["name"],
            "desde": desde,
            "hacia": hacia,
            "dias_sin_uso": round(dias_sin_uso, 2),
            "timestamp": ahora,
        }
        self.ledger.append(evento)
        self._emitir_ciclo("curator_transicion",
                           {"skill": fila["path"], "desde": desde,
                            "hacia": hacia,
                            "dias_sin_uso": round(dias_sin_uso, 2)})
        return evento

    def _emitir_ciclo(self, tipo, detalle):
        """Evento del Curator al event log unificado (fase 2.2).

        Fail-safe: el log nunca rompe el barrido."""
        if self.event_log is not None:
            try:
                self.event_log.asentar_ciclo(tipo=tipo, actor="curator",
                                             detalle=detalle)
            except Exception:
                pass

    def correr_ciclo(self, ahora=None):
        """Entrypoint para el schedule semanal: barrido determinista +
        ablación por evidencia. Retorna la lista de transiciones (como
        antes — compatibilidad); las archivadas por ablación quedan en
        el ledger. Para el detalle, usar `ciclo_con_ablacion`.

        La consolidación LLM NO corre acá: es opt-in explícito (ver
        `consolidar_llm`) y requiere aprobación del usuario caso por caso.
        """
        return self.ciclo_con_ablacion(ahora=ahora)["transiciones"]

    def ciclo_con_ablacion(self, ahora=None):
        """Como correr_ciclo, pero retorna también el detalle de la
        ablación: {"transiciones": [...], "ablacion": [...]}."""
        ahora = ahora if ahora is not None else time.time()
        transiciones = self.barrer(ahora=ahora)
        # Cherny (d): ablación por evidencia — una skill se queda solo si
        # hay registro de que evitó un fallo repetido; si no, se archiva.
        archivadas = self.ablacion_por_evidencia(ahora=ahora)
        return {"transiciones": transiciones, "ablacion": archivadas}

    # -- ablación por evidencia (Cherny d) -----------------------------------
    def registrar_evitacion(self, skill_path, firma, fallos_previos,
                            ahora=None):
        """Asienta que una skill evitó un fallo que se había repetido
        `fallos_previos` veces en la misma firma. Va al ledger."""
        ahora = ahora if ahora is not None else time.time()
        self.index._db.execute(
            "INSERT INTO evitaciones_skill (skill_path, firma,"
            " fallos_previos, timestamp) VALUES (?,?,?,?)",
            (skill_path, firma, fallos_previos, ahora))
        self.index._db.commit()
        self.ledger.append({"tipo": "evitacion_registrada",
                            "skill": skill_path, "firma": firma,
                            "fallos_previos": fallos_previos,
                            "timestamp": ahora})
        return True

    def notificar_uso_exitoso(self, skill_path, firma, fallos_previos_fn,
                              umbral=UMBRAL_EVIDENCIA, ahora=None):
        """Llamar cuando una skill se usa con éxito. `fallos_previos_fn`
        recibe la firma y retorna cuántas veces falló antes sin la skill.
        Si >= umbral: se registra la evitación (evidencia para no ser
        ablada). Retorna True si se registró."""
        n = fallos_previos_fn(firma)
        if n is not None and n >= umbral:
            return self.registrar_evitacion(skill_path, firma, n,
                                           ahora=ahora)
        return False

    def _tiene_evidencia(self, skill_path, ahora, ventana_dias):
        corte = ahora - ventana_dias * 86400
        fila = self.index._db.execute(
            "SELECT COUNT(*) FROM evitaciones_skill"
            " WHERE skill_path=? AND timestamp>=?",
            (skill_path, corte)).fetchone()
        return (fila[0] if fila else 0) > 0

    def _creada_reciente(self, skill_path, ahora, gracia_dias):
        fila = self.index._db.execute(
            "SELECT created_at FROM skills WHERE path=?",
            (skill_path,)).fetchone()
        if not fila or fila[0] is None:
            return True  # sin fecha: no ablar por precaución
        return (ahora - fila[0]) < gracia_dias * 86400

    def ablacion_por_evidencia(self, ahora=None,
                               ventana_dias=VENTANA_EVIDENCIA_DIAS,
                               gracia_dias=GRACIA_CREACION_DIAS):
        """Cherny (d): la habilidad de escribir no es licencia para
        quedarse. Para cada skill curable activa: se queda si hay
        registro de haber evitado un fallo repetido en la ventana, o si
        es recién creada (aún no tuvo chance). Si no: se archiva, con el
        motivo en el ledger. Retorna la lista de archivadas."""
        ahora = ahora if ahora is not None else time.time()
        archivadas = []
        for fila in self.index.listar(estado=ESTADO_ACTIVE):
            if fila["created_by"] not in CURABLES:
                continue
            path = fila["path"]
            if self._tiene_evidencia(path, ahora, ventana_dias):
                continue
            if self._creada_reciente(path, ahora, gracia_dias):
                continue
            self.index.transicionar(path, ESTADO_ARCHIVED)
            evento = {"tipo": "ablacion_archivada",
                      "skill": path, "name": fila["name"],
                      "motivo": ("sin registro de haber evitado un fallo"
                                 f" repetido en {ventana_dias} días"),
                      "timestamp": ahora}
            self.ledger.append(evento)
            self._emitir_ciclo("curator_transicion",
                               {"skill": path, "desde": ESTADO_ACTIVE,
                                "hacia": ESTADO_ARCHIVED,
                                "motivo": evento["motivo"]})
            archivadas.append(evento)
        return archivadas


class ConsolidacionNoHabilitada(Exception):
    """La consolidación LLM del Curator está apagada por default."""


def consolidar_llm(curator, proveedor=None, habilitada=None):
    """Consolidación de skills con LLM (fusiones/reescrituras amplias).

    OPT-IN APAGADA POR DEFAULT. Solo corre si:
      1. `habilitada=True` explícito en el llamado, o
      2. variable de entorno ALMA_CURATOR_LLM=1,
    Y el usuario la aprobó (diseño §4.4: es decisión explícita suya).

    Sin eso, corta con ConsolidacionNoHabilitada. Cuando corre, cada
    fusión propuesta pasa por el ledger como evento 'consolidacion_llm'
    con el diff completo, y es reversible vía re-archivo manual.
    """
    if habilitada is None:
        import os as _os
        habilitada = _os.environ.get("ALMA_CURATOR_LLM", "0") == "1"
    if not habilitada:
        raise ConsolidacionNoHabilitada(
            "la consolidación LLM del Curator está apagada por default; "
            "requiere opt-in explícito (ALMA_CURATOR_LLM=1) y aprobación "
            "del usuario (diseño §4.4).")
    if proveedor is None:
        raise ConsolidacionNoHabilitada(
            "sin proveedor LLM configurado: nada que consolidar.")
    # El proveedor propone fusiones; el Curator solo aplica las que el
    # usuario apruebe. Esta función retorna las propuestas SIN aplicar.
    propuestas = proveedor.proponer_fusiones(curator.index)
    curator.ledger.append({"tipo": "consolidacion_llm_propuestas",
                           "n": len(propuestas)})
    return propuestas
