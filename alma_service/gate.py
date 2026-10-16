"""Puerta de dos splits — de Self-Harness §3.4 (arXiv:2606.09498).

Regla de aceptación para promover una edición del scaffold/harness:

    Δ_in ≥ 0  ∧  Δ_ho ≥ 0  ∧  max(Δ_in, Δ_ho) > 0

donde Δ = mejora = (métrica_base − métrica_candidata) en regret
(menor es mejor). La edición se acepta solo si NO REGRESA en ningún
split y mejora estrictamente en al menos uno. Los trade-offs entre
splits se rechazan aunque el total suba.

La puerta NO evalúa nada: recibe números que el validador (congelado)
ya produjo. Es pura, determinista y sin LLM.

Capa de auto-adopción (cableada 11/10/2026, pre-registro
metaloop_preregistro_piso_ruido_puerta.json): la puerta pura decide la
ELEGIBILIDAD; la AUTO-ADOPCIÓN exige además superar el piso de ruido:
max(Δ_in, Δ_ho) > 0.53. Solo endurece: lo que la puerta rechaza sigue
rechazado; lo que cae en banda (0 < max ≤ 0.53) queda asentado con flag
"bajo piso de ruido" y requiere el «sí» explícito del operador
(mecanismo manual existente). Ver decidir_auto_adopcion().

Caveat documentado (del informe): el split held-out participa en la
puerta, así que hay presión de selección sobre el gate a lo largo de
rondas. El informe independiente lo da benchmark.py (mundo congelado).
El tercer split ciego no es trabajo futuro: se implementa en la capa
E3 (alma_service/puerta_e3.py, exigido siempre desde metaloop.py)
desde el 28/9/2026. Esta puerta sigue siendo de dos splits; la capa
E3 solo la endurece.
"""

REGLA = "delta_in>=0 & delta_ho>=0 & max(delta_in,delta_ho)>0"

# Piso de ruido δ calibrado en EXP-piso-ruido (30/9/2026, método RRSI
# adaptado: bootstrap B=2000 sobre bloques, z=2.0 → δ=0.5331, redondeado
# a 0.53). SOLO observabilidad: la puerta NO lo usa como criterio.
# Sirve para decidir con datos si algún día la puerta empieza a aceptar
# mejoras marginales. Ver ~/workspace/research_notes/estudio-rrsi-20260930/report.md
# y ~/workspace/alma-prototype/data_exppisorruido/PRE-REGISTRO.md.
PISO_RUIDO_DELTA = 0.53


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


# Regla de AUTO-ADOPCIÓN (capa de gobernanza sobre la puerta pura,
# cableada 11/10/2026 — pre-registro
# metaloop_preregistro_piso_ruido_puerta.json). Adapta la
# "stability-aware acceptance" de RRSI: la mejora tiene que superar el
# piso de ruido medido para adoptarse sola. La puerta pura (aceptar)
# sigue intacta: decide elegibilidad, no adopción.
REGLA_AUTO_ADOPCION = ("delta_in>=0 & delta_ho>=0 & "
                       "max(delta_in,delta_ho)>0.53")


def decidir_auto_adopcion(delta_in, delta_ho):
    """Capa de gobernanza: ¿se AUTO-ADOPTA este candidato?

    Retorna (auto_adoptar: bool, motivo: str, requiere_si: bool).

    - Si la puerta pura rechaza (regresión o sin mejora): no hay
      auto-adopción, requiere_si=False (rechazo normal, como siempre).
    - Si la puerta acepta pero max(Δ_in,Δ_ho) ≤ PISO_RUIDO_DELTA:
      NO auto-adopción, requiere_si=True. Queda asentado con flag
      "bajo piso de ruido"; la adopción necesita el «sí» explícito
      del operador por el camino manual existente.
    - Si max(Δ_in,Δ_ho) > PISO_RUIDO_DELTA: auto-adopción, como antes.

    Solo endurece: ningún caso que antes se rechazaba pasa a
    adoptarse. Pura, determinista, sin LLM, sin tocar presupuesto
    ni notificaciones.
    """
    ok, motivo = aceptar(delta_in, delta_ho)
    if not ok:
        return False, motivo, False
    d_max = max(float(delta_in), float(delta_ho))
    if d_max <= PISO_RUIDO_DELTA:
        return (False,
                (f"bajo piso de ruido: max(delta)={d_max:.4f} <="
                 f" {PISO_RUIDO_DELTA} (no auto-adopción; requiere"
                 " «sí» explícito)"),
                True)
    return True, motivo, False


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

    Campos de observabilidad del piso de ruido (EXP-piso-ruido, 30/9/2026):
    delta_max, piso_ruido_delta y sobre_piso_ruido se registran en cada
    audit record para poder decidir con datos si la puerta algún día
    empieza a aceptar mejoras marginales. NO cambian la regla.
    """
    d_in = float(delta_in) if delta_in is not None else None
    d_ho = float(delta_ho) if delta_ho is not None else None
    d_max = round(max(d_in, d_ho), 4) if d_in is not None and d_ho is not None else None
    return {
        "tipo": "audit_propuesta",
        "propuesta": propuesta,
        "debilidad_objetivo": debilidad,
        "superficie_editada": superficie,
        "efecto_esperado": efecto_esperado,
        "riesgo_regresion": riesgo_regresion,
        "delta_in": _r(delta_in),
        "delta_ho": _r(delta_ho),
        "delta_max": d_max,
        "piso_ruido_delta": PISO_RUIDO_DELTA,
        "sobre_piso_ruido": (d_max > PISO_RUIDO_DELTA) if d_max is not None else None,
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
