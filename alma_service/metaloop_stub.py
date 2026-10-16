"""Meta-loop — STUB documentado, fase 0.

El diseño §3.1 contempla el Meta-loop (decide por tipo de problema qué
familia de arquitectura del registry, qué estrategia de selección y
cuánto presupuesto de probe), pero su activación es fase 2+. En fase 0
este módulo existe solo como interfaz documentada: cualquier intento de
uso corta con MetaLoopNoDisponible.

Interfaz futura (fase 2):
    proponer(contexto_problema) -> list[PropuestaPolitica]
    PropuestaPolitica: {estrategia_seleccion, presupuesto_probe,
                        familia_arquitectura}
Toda propuesta pasa por: sandbox → harness → pre-registro falsable →
A/B pareado → veredicto. Sin PASS no se adopta (diseño §3.2).

Guardarraíles (diseño §3.3, contra el incidente DGM):
- separación proposer/verifier; reward anclado a ground truth;
- núcleo fijo no modificable por el propio sistema;
- lineage auditable + rollback; presupuesto por bucket.
"""


class MetaLoopNoDisponible(Exception):
    """El Meta-loop es fase 2+. En fase 0 no propone nada."""


def proponer(*args, **kwargs):
    """Stub: siempre corta. La firma documenta la interfaz futura."""
    raise MetaLoopNoDisponible(
        "el Meta-loop se activa en fase 2 con harness como puerta; "
        "en fase 0 la política es fija (la validada por los mocks)."
    )


def evaluar_propuesta(propuesta, harness, pre_registro):
    """Stub del protocolo de adopción (diseño §3.2)."""
    raise MetaLoopNoDisponible(
        "la evaluación de propuestas requiere el harness de fase 2+."
    )
