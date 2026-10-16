"""Monitor de drift en vivo — fase 2.5 (cableado al servicio vivo).

Lee los veredictos de probe MEDIDOS del event log unificado (fase 2.2)
y corre el DetectorDrift sobre ellos en operación. Cuando detecta un
cambio de régimen, REGISTRA el evento (ledger `drift-ledger.jsonl` +
evento de ciclo en el event log) y lo EXPONE (estado para
`/drift/estado`).

Es infraestructura de OBSERVABILIDAD, no un cambio de política:
- no toca `resolver`, `presupuesto` ni topes (no edita `motor.py`:
  solo lee las trazas que el motor ya asienta);
- no fuerza re-probes ni re-ancla solo: informa; el consumidor (la
  capa de crons/chat) decide y re-ancla por `/drift/anclar`.

Mapeo veredicto — lección de calibración del EXP68 (`veredicto.md`):
el veredicto es el probe MEDIDO (argmax estricto de lo que la
política efectivamente midió), NUNCA el brazo del posterior. En el
servicio vivo cada decisión en modo probe es un problema (no un
bloque de 12): un veredicto = una decisión con veredicto_probe y
gap > 0 en extras. Un empate (gap <= 0 o sin gap) no es veredicto:
no ancla ni alimenta (misma convención que el harness EXP68: los
bloques sin probe no extienden ni diluyen). El detector recibe como
"bloque" el id del evento de decisión (monótono, ordenado).

Anclaje: el baseline se ancla con el PRIMER veredicto medido que el
monitor observa (el régimen vigente al empezar a observar). El
operador puede re-anclar por `/drift/anclar`: con el último
veredicto medido (default) o con un ganador explícito (origen
"manual", registrado en el ledger).

Calibración — caveat honesto: VENTANA_DRIFT=6/CONTRADICCIONES_DRIFT=2
se eligieron por razonamiento para bloques del harness, no para
decisiones sueltas (DRIFT.md §4: "recalibrar antes de integrar").
Este cableado los conserva y documenta: hasta validar contra trazas
reales de operación con flips, la sensibilidad es provisional.

Fail-safe (mismo patrón que `detector_heterogeneidad` en
motor_fase1): cualquier excepción desactiva el monitor para la
sesión — el servicio sigue igual y el monitor informa
{"activo": False}. Puro el núcleo (`drift.py`); este módulo es solo
la envoltura con I/O.

US$0: sin key, sin red, sin LLM.
"""

import json
import os
import threading
import time
from datetime import datetime, timezone

from alma_service.drift import (
    DetectorDrift, VENTANA_DRIFT, CONTRADICCIONES_DRIFT,
)

LEDGER_DRIFT = "drift-ledger.jsonl"

# Cuántas entradas recientes del ledger expone estado().
LEDGER_COLA = 5


class MonitorDriftVivo:
    """Corre DetectorDrift sobre las trazas del servicio en operación.

    event_log: instancia de EventLog (fase 2.2) que el monitor LEE.
    dir_base: directorio donde vive `drift-ledger.jsonl` (default: el
        directorio del event log; en el servicio vivo es el dir de la
        DB, misma convención que curator-ledger.jsonl).
    """

    def __init__(self, event_log, dir_base=None, ventana=None,
                 contradicciones=None):
        self.trazas = event_log
        self.detector = DetectorDrift(
            ventana=ventana if ventana is not None else VENTANA_DRIFT,
            contradicciones=(contradicciones
                             if contradicciones is not None
                             else CONTRADICCIONES_DRIFT))
        base = dir_base or os.path.dirname(os.path.abspath(
            getattr(event_log, "db_path", ".")))
        os.makedirs(base, exist_ok=True)
        self.ledger_path = os.path.join(base, LEDGER_DRIFT)
        self._lock = threading.Lock()
        self._ultimo_id = 0
        self._ultimo_veredicto = None  # (evento_id, ganador)
        self._drift_notificado = False
        self._roto = False
        self._motivo_roto = ""

    # -- escaneo ---------------------------------------------------------

    def _veredicto_medida(self, decision):
        """Extrae el veredicto MEDIDO de una decisión, o None.

        Exige: modo probe con veredicto_probe asentado Y gap > 0 en
        extras (ganador estricto). Un gap <= 0 es empate: sin
        veredicto (convención EXP68).
        """
        if decision.get("veredicto_probe") is None:
            return None
        extras = decision.get("extras") or {}
        gap = extras.get("gap")
        if gap is None or gap <= 0:
            return None
        return str(decision["veredicto_probe"])

    def _escanear_locked(self):
        """Lee decisiones nuevas del event log y alimenta al detector.

        Retorna resumen del escaneo. Fail-closed: sin baseline anclada
        no hay señal; el primer veredicto medido ancla el baseline.
        """
        decisiones = self.trazas.decisiones(limite=100000)
        nuevas = [d for d in decisiones if d["id"] > self._ultimo_id]
        nuevos = 0
        drift_nuevo = False
        for d in nuevas:
            self._ultimo_id = max(self._ultimo_id, d["id"])
            ganador = self._veredicto_medida(d)
            if ganador is None:
                continue
            nuevos += 1
            self._ultimo_veredicto = (d["id"], ganador)
            if self.detector.baseline is None:
                self.detector.anclar_baseline(d["id"], ganador)
                self._asentar_ledger("anclaje", {
                    "evento_id": d["id"], "ganador": ganador,
                    "origen": "primer_veredicto_observado"})
                continue
            if self.detector.registrar(d["id"], ganador):
                drift_nuevo = True
        if drift_nuevo and not self._drift_notificado:
            self._drift_notificado = True
            self._asentar_ledger("drift", {
                "evento_id": self._ultimo_id,
                "senial": self.detector.senial()})
            self._asentar_ciclo("drift_detectado")
        return {"activo": True, "decisiones_nuevas": len(nuevas),
                "veredictos_nuevos": nuevos,
                "drift": self.detector.hay_drift(),
                "drift_nuevo": drift_nuevo}

    def escanear(self):
        """Escaneo fail-safe: nunca levanta excepción al llamador."""
        with self._lock:
            if self._roto:
                return {"activo": False, "motivo": self._motivo_roto}
            try:
                return self._escanear_locked()
            except Exception as e:  # noqa: BLE001
                self._roto = True
                self._motivo_roto = str(e)[:200]
                return {"activo": False, "motivo": self._motivo_roto}

    # -- re-anclaje --------------------------------------------------------

    def anclar(self, ganador=None, origen="manual"):
        """Re-ancla el baseline y libera la señal enclavada.

        ganador=None → re-ancla con el último veredicto medido
        observado (el régimen que el operador confirma tras
        investigar). ganador explícito → se registra con origen
        "manual". Fail-closed: sin veredicto medido no hay anclaje.
        """
        with self._lock:
            if self._roto:
                return {"ok": False, "motivo": self._motivo_roto}
            try:
                if ganador is None:
                    if self._ultimo_veredicto is None:
                        return {"ok": False, "error":
                                "sin veredicto medido para anclar: "
                                "el monitor aún no observó ningún probe"}
                    bloque, ganador = self._ultimo_veredicto
                else:
                    bloque = self._ultimo_id
                self.detector.anclar_baseline(bloque, str(ganador))
                self._drift_notificado = False
                self._asentar_ledger("anclaje", {
                    "evento_id": bloque, "ganador": str(ganador),
                    "origen": origen})
                try:
                    if self.trazas is not None:
                        self.trazas.asentar_ciclo(
                            "drift_reanclaje", actor="detector_drift",
                            detalle={"ganador": str(ganador),
                                     "origen": origen})
                except Exception:
                    pass
                return {"ok": True, "ganador": str(ganador),
                        "origen": origen}
            except Exception as e:  # noqa: BLE001
                self._roto = True
                self._motivo_roto = str(e)[:200]
                return {"ok": False, "motivo": self._motivo_roto}

    # -- estado --------------------------------------------------------------

    def estado(self):
        """Estado para /drift/estado y /fase2/estado. No escanea: solo
        informa (el escaneo lo dispara /drift/estado o
        /drift/escanear)."""
        with self._lock:
            senial = self.detector.senial()
            return {
                "activo": not self._roto,
                "motivo": self._motivo_roto if self._roto else "",
                "anclado": self.detector.baseline is not None,
                "ultimo_evento_visto": self._ultimo_id,
                "ultimo_veredicto": (
                    {"evento_id": self._ultimo_veredicto[0],
                     "ganador": self._ultimo_veredicto[1]}
                    if self._ultimo_veredicto else None),
                "detector": senial,
                "ledger": self.ledger_path,
                "ultimos_eventos": self._cola_ledger(),
            }

    def estado_vivo(self):
        """Escanea y después informa: lo que sirve /drift/estado."""
        self.escanear()
        return self.estado()

    # -- ledger ---------------------------------------------------------------

    def _asentar_ledger(self, tipo, detalle):
        """Agrega una entrada al ledger de drift. Fail-safe por
        dentro: si el ledger falla, no rompe el escaneo."""
        try:
            entrada = {"ts": datetime.now(timezone.utc).isoformat(),
                       "tipo": tipo}
            entrada.update(detalle)
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _asentar_ciclo(self, tipo):
        """Asienta el evento en el event log 2.2 (misma convención que
        el detector de heterogeneidad). Fail-safe por dentro."""
        try:
            if self.trazas is not None:
                self.trazas.asentar_ciclo(
                    tipo, actor="detector_drift",
                    detalle=self.detector.senial())
        except Exception:
            pass

    def _cola_ledger(self, n=LEDGER_COLA):
        """Últimas n entradas del ledger (para el endpoint)."""
        try:
            with open(self.ledger_path, encoding="utf-8") as f:
                lineas = f.readlines()
        except (OSError, IOError):
            return []
        out = []
        for linea in lineas[-n:]:
            try:
                out.append(json.loads(linea))
            except ValueError:
                continue
        return out

    # -- introspección ---------------------------------------------------------

    @property
    def roto(self):
        return self._roto
