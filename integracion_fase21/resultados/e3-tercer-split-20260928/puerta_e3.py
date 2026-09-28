"""Tercer split ciego (E3) — extensión opcional de la puerta de dos splits.

Trabajo futuro documentado en alma_service/gate.py:
"un tercer split ciego queda como trabajo futuro."

Este módulo NO modifica el servicio vivo: importa la regla de dos splits
del módulo vivo (solo lectura) y agrega la capa E3 encima. Puro,
determinista, sin LLM — misma filosofía que gate.py.

Regla E3 (generalización directa de la regla viva):
    aceptar ssi min(Δ_in, Δ_ho, Δ_e3) ≥ 0  ∧  max(Δ_in, Δ_ho, Δ_e3) > 0
donde Δ = mejora = (métrica_base − métrica_candidata) en regret
(menor es mejor). Sin regresión en NINGÚN split (el E3 veta aunque
E1/E2 pasen) y mejora estricta en al menos uno de los tres.

El E3 NO es un tercer obstáculo de mejora: es un veto contra la
suerte de split y contra la presión de selección sobre el gate a lo
largo de rondas (caveat documentado en gate.py). Por eso la mejora
estricta se exige en al menos uno de los tres, no en los tres.
"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))  # alma-prototype/
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from alma_service.gate import aceptar as aceptar_dos_splits  # noqa: E402
from alma_service.gate import REGLA as REGLA_DOS_SPLITS  # noqa: E402

REGLA_E3 = "min(d_in,d_ho,d_e3)>=0 & max(d_in,d_ho,d_e3)>0"

SUPERFICIES = ("parametro", "maquinaria", "nucleo")
SUPERFICIES_ALTO_IMPACTO = ("maquinaria", "nucleo")


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
