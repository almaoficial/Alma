"""Puerta de dos splits — de Self-Harness §3.4 (arXiv:2606.09498).

Regla de aceptación para promover una edición del scaffold/harness:

    Δ_in ≥ 0  ∧  Δ_ho ≥ 0  ∧  max(Δ_in, Δ_ho) > 0

donde Δ = mejora = (métrica_base − métrica_candidata) en regret
(menor es mejor). La edición se acepta solo si NO REGRESA en ningún
split y mejora estrictamente en al menos uno. Los trade-offs entre
splits se rechazan aunque el total suba.

La puerta NO evalúa nada: recibe números que el validador (congelado)
ya produjo. Es pura, determinista y sin LLM.

Caveat documentado (del informe): el split held-out participa en la
puerta, así que hay presión de selección sobre el gate a lo largo de
rondas. El informe independiente lo da benchmark.py (mundo congelado);
un tercer split ciego queda como trabajo futuro.
"""

REGLA = "delta_in>=0 & delta_ho>=0 & max(delta_in,delta_ho)>0"


def aceptar(delta_in, delta_ho):
    """Aplica la regla de aceptación. Retorna (aceptado: bool, motivo)."""
    d_in = float(delta_in)
    d_ho = float(delta_ho)
    if d_in < 0 or d_ho < 0:
        return False, (f"regresión: delta_in={d_in:.4f},"
                       f" delta_ho={d_ho:.4f}")
    if max(d_in, d_ho) <= 0:
        return False, (f"sin mejora estricta: delta_in={d_in:.4f},"
                       f" delta_ho={d_ho:.4f}")
    return True, (f"aceptada: delta_in={d_in:.4f},"
                   f" delta_ho={d_ho:.4f}")


def _r(x):
    return round(float(x), 4) if x is not None else None


def audit_record(propuesta, delta_in, delta_ho, aceptado, motivo,
                 debilidad=None, superficie=None, efecto_esperado=None,
                 riesgo_regresion=None):
    """Audit record por propuesta (Self-Harness §3.3): qué se propuso,
    contra qué evidencia, qué decidió la puerta y por qué.

    delta_ho puede ser None en propuestas de búsqueda (ronda): ahí la
    puerta de dos splits aún no aplica; el veredicto es keep/revert en
    train. En la adopción final ambos deltas están presentes.
    """
    return {
        "tipo": "audit_propuesta",
        "propuesta": propuesta,
        "debilidad_objetivo": debilidad,
        "superficie_editada": superficie,
        "efecto_esperado": efecto_esperado,
        "riesgo_regresion": riesgo_regresion,
        "delta_in": _r(delta_in),
        "delta_ho": _r(delta_ho),
        "regla": REGLA,
        "aceptado": bool(aceptado),
        "motivo": motivo,
    }


class PuertaDosSplits:
    """Wrapper con nombre: la puerta como objeto para el metaloop."""

    REGLA = REGLA

    @staticmethod
    def decidir(metrica_in_base, metrica_ho_base,
                metrica_in_cand, metrica_ho_cand):
        """Decide con métricas (regret: menor es mejor)."""
        d_in = float(metrica_in_base) - float(metrica_in_cand)
        d_ho = float(metrica_ho_base) - float(metrica_ho_cand)
        ok, motivo = aceptar(d_in, d_ho)
        return {"aceptado": ok, "motivo": motivo,
                "delta_in": round(d_in, 4), "delta_ho": round(d_ho, 4),
                "regla": REGLA}
