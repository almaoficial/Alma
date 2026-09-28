"""Detector de drift de régimen — fase 2.5 (mock, US$0).

NO INTEGRADO AL SERVICIO VIVO: módulo listo-para-integrar, validado
en mock. No cablear sin decisión explícita del usuario.

Qué hace: compara el régimen actual contra un baseline anclado y
dispara una señal cuando el mundo cambió, para forzar re-probe.

- Régimen actual: ventana deslizante de los últimos W veredictos de
  probe (ganador estricto medido, bloque a bloque).
- Baseline: el veredicto MEDIDO que el loop tomó como vigente
  (típicamente el brazo comprometido al encoger, o el vigente al
  arranque), con sus medias por brazo.
- Señal: si en la ventana hay al menos M veredictos que CONTRADICEN
  al baseline (otro ganador estricto), el mundo cambió → hay_drift()
  es True y senial() recomienda "re_probe".

Histéresis deliberada (en dos direcciones):
- Una sola contradicción no dispara: el ruido de medición (ver lección
  EXP68: una contradicción estricta ocurre por azar) no puede
  forzar un re-probe caro.
- Una vez disparado, la señal SE ENCLAVA hasta que se re-ancla el
  baseline: un flip real sigue señalando aunque los veredictos
  posteriores mezclen ruido.

Lecciones incorporadas:
- EXP68: el veredicto es el probe MEDIDO (argmax estricto de las
  medias que la política efectivamente midió), NUNCA el brazo del
  posterior. El baseline se ancla con ganador medido.
- EXP68 (convención del harness): solo los bloques CON probe
  alimentan la ventana. Un bloque saltado (sin probe) no se
  registra: no extiende ni diluye la ventana. Un empate (ganador
  None) no es contradicción: no hay veredicto.
- EXP44: el oráculo debe calibrarse contra datos reales ANTES del
  pre-registro. Los defaults VENTANA_DRIFT/CONTRADICCIONES_DRIFT
  son provisionales (ver DRIFT.md): no están congelados por
  pre-registro — antes de integrar hay que validarlos contra
  trazas de operación real o un harness mock con flips.

Puro, determinista, sin LLM, sin I/O. No evalúa nada: recibe
veredictos que el loop ya midió.

Relación con el detector de heterogeneidad (EXP68):
- heterogeneidad.py detecta "no hay nada que descubrir" (unanimidad
  sostenida → encoge la exploración, con spot-checks como red de
  seguridad ante flips).
- drift.py detecta "el mundo cambió" (la ventana actual contradice
  el baseline → re-probe).
Son complementarios y no se pisan: el drift vive por encima de ambos
modos (explorar/encogido) porque un flip puede ocurrir en cualquiera.
"""

# Defaults provisionales (ver DRIFT.md §3). NO están congelados por
# pre-registro: se eligen por razonamiento sobre ruido y se documentan
# como "recalibrar antes de integrar".
# - VENTANA_DRIFT=6: ventana de 6 bloques con probe. En el harness
#   mock un bloque son 12 problemas; 6 bloques dan señal estable sin
#   tardar una eternidad en reaccionar.
# - CONTRADICCIONES_DRIFT=2: hacen falta 2 contradicciones estrictas
#   en la ventana. Con p_contradicción~5% por bloque estable (ruido de
#   probe), P(>=2 en 6) ≈ 3%: falso positivo tolerable; un flip real
#   produce contradicciones casi todos los bloques → dispara en 2.
VENTANA_DRIFT = 6
CONTRADICCIONES_DRIFT = 2

ACCION_RE_PROBE = "re_probe"


class DetectorDrift:
    """State machine del detector. Pura: sin RNG, sin I/O, sin LLM."""

    def __init__(self, ventana=VENTANA_DRIFT,
                 contradicciones=CONTRADICCIONES_DRIFT):
        if int(ventana) < 1:
            raise ValueError("ventana debe ser >= 1")
        if int(contradicciones) < 1:
            raise ValueError("contradicciones debe ser >= 1")
        if int(contradicciones) > int(ventana):
            raise ValueError(
                "contradicciones no puede superar a la ventana "
                "(exigiría más evidencia que la disponible)")
        self.ventana = int(ventana)
        self.contradicciones = int(contradicciones)
        self.baseline = None      # {"ganador": str, "medias": dict}
        self._ventana = []        # últimos veredictos (ganadores estrictos)
        self._drift = False       # señal enclavada
        self._bloque_drift = None
        self.historial = []       # auditoría de eventos

    # -- anclaje --------------------------------------------------------------

    def anclar_baseline(self, bloque, ganador, medias=None):
        """Fija (o re-fija) el baseline contra el que se mide el drift.

        ganador: ganador estricto MEDIDO del probe (str), nunca None
        (fail-closed: sin veredicto estricto no hay baseline).
        medias: dict brazo -> media medida (opcional, se guarda copia).
        Limpia la ventana y desenclava la señal de drift.
        """
        if ganador is None:
            raise ValueError("anclar_baseline exige ganador estricto "
                             "medido (None no es veredicto)")
        self.baseline = {"ganador": ganador,
                         "medias": dict(medias) if medias else {}}
        self._ventana = []
        self._drift = False
        self._bloque_drift = None
        self.historial.append({
            "evento": "anclaje", "bloque": int(bloque),
            "ganador": ganador,
            "medias": dict(self.baseline["medias"]),
        })

    # -- alimentación ---------------------------------------------------------

    def registrar(self, bloque, ganador, medias=None):
        """Veredicto de probe de un bloque (solo bloques CON probe).

        ganador: ganador estricto medido (str) o None si hubo empate
        (el empate no es contradicción ni alimenta la ventana).
        Retorna True si ESTE registro dispara la señal de drift
        (transición a enclavado); en otro caso False.
        """
        if self.baseline is None:
            raise RuntimeError("registrar sin baseline anclada: "
                               "anclar_baseline primero (fail-closed)")
        b = int(bloque)
        if ganador is not None:
            self._ventana.append(ganador)
            self._ventana = self._ventana[-self.ventana:]
        n_contra = sum(1 for g in self._ventana
                       if g != self.baseline["ganador"])
        if not self._drift and n_contra >= self.contradicciones:
            self._drift = True
            self._bloque_drift = b
            self.historial.append({
                "evento": "drift", "bloque": b,
                "baseline": self.baseline["ganador"],
                "contradicciones": n_contra,
                "ventana": list(self._ventana),
                "accion": ACCION_RE_PROBE,
            })
            return True
        return False

    # -- consulta --------------------------------------------------------------

    def hay_drift(self):
        """¿La señal de drift está activa? (enclavada hasta re-anclar)."""
        return self._drift

    def contradicciones_en_ventana(self):
        """Cuántas contradicciones al baseline hay en la ventana actual."""
        if self.baseline is None:
            return 0
        return sum(1 for g in self._ventana
                   if g != self.baseline["ganador"])

    def senial(self):
        """Detalle de la señal para el consumidor (y el event log)."""
        return {
            "drift": bool(self._drift),
            "bloque_drift": self._bloque_drift,
            "baseline": (self.baseline["ganador"]
                         if self.baseline else None),
            "ventana": list(self._ventana),
            "contradicciones": self.contradicciones_en_ventana(),
            "umbral": int(self.contradicciones),
            "tamano_ventana": int(self.ventana),
            "accion": ACCION_RE_PROBE if self._drift else None,
        }

    # -- introspección ----------------------------------------------------------

    @property
    def ventana_actual(self):
        return list(self._ventana)
