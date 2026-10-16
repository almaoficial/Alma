"""Tercer split ciego (E3) — extensión de la puerta de dos splits.

INTEGRACIÓN AL SERVICIO VIVO (28/9, decisión del usuario "hacelo"):
este módulo es la implementación validada en mock (16/16 tests,
integracion_fase21/resultados/e3-tercer-split-20260928/puerta_e3.py)
con la configuración del servicio. La regla pura NO cambió: lo que se
fijó acá son solo los defaults de política (qué datos, qué margen,
kill switch).

La puerta de dos splits (gate.py) NO se toca: es núcleo protegido.
El E3 solo ENDURECE (veto ante margen fino o superficie de alto
impacto), nunca relaja: si los dos splits rechazan, el E3 ni se
evalúa (short-circuit).

DEFAULTS DEL SERVICIO (documentados, 28/9 — el usuario delegó ambas
decisiones):
1. Qué datos corren el split ciego → E3_REPS = [500, 501]: réplicas
   del stream mock reservadas para auditorías, nunca usadas en E1
   (train [0,1,2]) ni en E2 (held-out [3,4]), ni en el benchmark
   ([0..4]), ni en ningún experimento (EXP64 usó 100-119).
   PROVISIONAL: hasta que el servicio tenga datos de operación real,
   el E3 corre sobre mock held-out reservado.
2. Calibración de margen_min → MARGEN_MIN_DEFAULT = 5.0 puntos de
   regret. El benchmark propio tiene una sola corrida (mejora 0.0:
   el vigente ES el baseline) → sin variación Δ split-a-split
   observable → dato insuficiente → default conservador ("E3 exigido
   ante la duda"). Los efectos ganadores validados en el laboratorio
   son ~5-10 puntos (EXP56: 6.20, EXP64: 6.55); un margen < 5 en algún
   split es duda → E3. Recalibrar cuando el servicio tenga sus propios
   datos split-a-split (operación real o más corridas de benchmark).

E3_HABILITADO = True: kill switch. En False, el servicio vuelve a la
puerta de dos splits sin E3 (revertir = poner False + reiniciar).
"""

from alma_service.gate import aceptar as aceptar_dos_splits  # noqa: F401
from alma_service.gate import REGLA as REGLA_DOS_SPLITS  # noqa: F401

REGLA_E3 = "min(d_in,d_ho,d_e3)>=0 & max(d_in,d_ho,d_e3)>0"

SUPERFICIES = ("parametro", "maquinaria", "nucleo")
SUPERFICIES_ALTO_IMPACTO = ("maquinaria", "nucleo")

# -- configuración del servicio (defaults documentados arriba) ------------
E3_HABILITADO = True
MARGEN_MIN_DEFAULT = 5.0
E3_REPS = [500, 501]
# El meta-loop muta hiperparámetros del scaffold (no la maquinaria
# probe/skip/gate/prior) → superficie "parametro" en la política E3.
SUPERFICIE_METALOOP = "parametro"
E3_DATOS_DESCRIPCION = ("stream mock held-out reservado para auditorías"
                        " (réplicas 500-501, provisionales)")


def resumen_config_e3():
    """Configuración E3 vigente, para /fase2/estado (bloque gobernanza)
    y para el pre-registro de cada corrida del meta-loop."""
    return {
        "habilitado": bool(E3_HABILITADO),
        "margen_min": float(MARGEN_MIN_DEFAULT),
        "e3_reps": list(E3_REPS),
        "superficie_metaloop": SUPERFICIE_METALOOP,
        "regla_e3": REGLA_E3,
        "datos": E3_DATOS_DESCRIPCION,
        "politica": ("Endurecimiento 28/9 (decisión del usuario): E3"
                     " SIEMPRE exigido en el path vivo cuando los dos"
                     " splits aceptan (forzar_e3=True); el E3 veta ante"
                     " regresión, nunca relaja la puerta"),
    }


def aceptar_e3(delta_in, delta_ho, delta_e3):
    """Aplica la regla de tres splits. Retorna (aceptado: bool, motivo)."""
    ds = [float(delta_in), float(delta_ho), float(delta_e3)]
    etiquetas = ["in", "ho", "e3"]
    if min(ds) < 0:
        det = ", ".join(f"Δ_{e}={d:.4f}" for e, d in zip(etiquetas, ds))
        return False, f"regresión (E3 veta): {det}"
    if max(ds) <= 0:
        det = ", ".join(f"Δ_{e}={d:.4f}" for e, d in zip(etiquetas, ds))
        return False, f"sin mejora estricta en ningún split: {det}"
    det = ", ".join(f"Δ_{e}={d:.4f}" for e, d in zip(etiquetas, ds))
    return True, f"aceptada con E3: {det}"


def exigir_e3(delta_in, delta_ho, superficie="parametro",
             margen_min=2.0, forzar_e3=False):
    """¿Se exige el tercer split ciego? Retorna (exigido: bool, motivo).

    Política (documentada en E3.md):
    - forzar_e3=True → siempre (el auditor/usuario puede pedirlo).
    - superficie de alto impacto ("maquinaria", "nucleo") → siempre,
      aunque los márgenes sean cómodos.
    - margen fino: min(Δ_in, Δ_ho) < margen_min → se exige.
    - en otro caso (parámetro con margen cómodo): bastan dos splits.
    """
    if superficie not in SUPERFICIES:
        raise ValueError(f"superficie desconocida: {superficie!r} "
                         f"(válidas: {SUPERFICIES})")
    if forzar_e3:
        return True, "E3 forzado por auditor/usuario"
    if superficie in SUPERFICIES_ALTO_IMPACTO:
        return True, f"superficie de alto impacto: {superficie}"
    m = min(float(delta_in), float(delta_ho))
    if m < float(margen_min):
        return True, (f"margen fino: min(Δ_in,Δ_ho)={m:.4f} "
                      f"< margen_min={float(margen_min):.4f}")
    return False, ("parámetro con margen cómodo en ambos splits: "
                   f"min(Δ_in,Δ_ho)={m:.4f}")


def decidir(delta_in, delta_ho, delta_e3=None, superficie="parametro",
           margen_min=2.0, forzar_e3=False):
    """Flujo completo. Retorna dict con aceptado, motivo y trazabilidad.

    1. Puerta de dos splits (módulo vivo). Si falla → rechazo; el E3 ni
       se consulta.
    2. Si pasa, se evalúa si se exige E3. Si no → aceptado.
    3. Si se exige y delta_e3 es None → ValueError (fail-closed: sin el
       tercer split no hay adopción).
    4. Si se exige y hay datos → regla E3 (el E3 veta ante regresión).
    """
    ok2, motivo2 = aceptar_dos_splits(delta_in, delta_ho)
    base = {"delta_in": round(float(delta_in), 4),
            "delta_ho": round(float(delta_ho), 4),
            "delta_e3": (round(float(delta_e3), 4)
                         if delta_e3 is not None else None),
            "superficie": superficie,
            "regla_dos_splits": REGLA_DOS_SPLITS,
            "regla_e3": REGLA_E3}
    if not ok2:
        return {**base, "aceptado": False, "e3_exigido": False,
                "e3_evaluado": False,
                "motivo": f"dos splits rechazan: {motivo2} (E3 no evaluado)"}
    exigido, motivo_ex = exigir_e3(delta_in, delta_ho, superficie,
                                   margen_min, forzar_e3)
    if not exigido:
        return {**base, "aceptado": True, "e3_exigido": False,
                "e3_evaluado": False,
                "motivo": f"dos splits aceptan: {motivo2} "
                          f"| E3 no exigido: {motivo_ex}"}
    if delta_e3 is None:
        raise ValueError("E3 exigido pero delta_e3=None: fail-closed — "
                         "sin el tercer split no hay adopción")
    ok3, motivo3 = aceptar_e3(delta_in, delta_ho, delta_e3)
    return {**base, "aceptado": ok3, "e3_exigido": True,
            "e3_evaluado": True, "motivo": motivo3}


def audit_record_e3(propuesta, delta_in, delta_ho, delta_e3, superficie,
                    aceptado, motivo, e3_exigido, e3_evaluado,
                    debilidad=None, efecto_esperado=None):
    """Audit record con E3 (extiende el de gate.py sin modificarlo)."""
    r = lambda x: round(float(x), 4) if x is not None else None
    return {
        "tipo": "audit_propuesta_e3",
        "propuesta": propuesta,
        "debilidad_objetivo": debilidad,
        "superficie_editada": superficie,
        "efecto_esperado": efecto_esperado,
        "delta_in": r(delta_in),
        "delta_ho": r(delta_ho),
        "delta_e3": r(delta_e3),
        "regla_dos_splits": REGLA_DOS_SPLITS,
        "regla_e3": REGLA_E3,
        "e3_exigido": bool(e3_exigido),
        "e3_evaluado": bool(e3_evaluado),
        "aceptado": bool(aceptado),
        "motivo": motivo,
    }
