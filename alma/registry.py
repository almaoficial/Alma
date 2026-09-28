"""Architecture Registry — núcleo FIJO (sección 9 del informe).

Las familias arquitectónicas son *datos versionados*, no código generado
libremente. El selector y el experimentador solo pueden elegir dentro de
este repertorio; ampliarlo es un acto versionado, auditable y reversible.

Cada familia declara: id, nombre, descripción, parámetros, costo relativo
esperado (1.0 = un llamado simple), precondiciones y para qué clases está
recomendada a priori (prior manual, no aprendido).
"""

REGISTRY_VERSION = "1.0.0"

# Costo relativo esperado. Se usa en el reward para no depender de precios
# USD, que cambian según el proveedor y el modelo.
ARCHITECTURES = [
    {
        "id": "single",
        "nombre": "Llamado directo",
        "descripcion": "Un solo llamado al modelo, sin razonamiento explícito ni herramientas.",
        "parametros": {"max_llamados": 1},
        "costo_relativo": 1.0,
        "precondiciones": ["respuesta corta esperada", "problema de un paso"],
        "recomendada_para": ["qa_multihop"],
    },
    {
        "id": "cot",
        "nombre": "Chain-of-thought",
        "descripcion": "Un llamado con razonamiento paso a paso; la respuesta final va tras 'Respuesta:'.",
        "parametros": {"max_llamados": 1, "formato_respuesta": "Respuesta: <valor>"},
        "costo_relativo": 1.2,
        "precondiciones": ["problema multi-paso descomponible"],
        "recomendada_para": ["calculo", "qa_multihop"],
    },
    {
        "id": "self_consistency",
        "nombre": "Self-consistency",
        "descripcion": "5 muestras independientes con CoT y voto por mayoría sobre la respuesta normalizada.",
        "parametros": {"max_llamados": 5, "n_muestras": 5},
        "costo_relativo": 5.0,
        "precondiciones": ["respuesta con forma canónica que permite votar"],
        "recomendada_para": ["qa_multihop", "puzzles"],
    },
    {
        "id": "reflexion",
        "nombre": "Reflexion",
        "descripcion": "Actor + crítico + hasta 2 reintentos con la crítica en contexto (memoria episódica intra-tarea).",
        "parametros": {"max_llamados": 4, "max_reintentos": 2},
        "costo_relativo": 4.0,
        "precondiciones": ["el error es detectable por el propio modelo"],
        "recomendada_para": ["codigo"],
    },
    {
        "id": "debate",
        "nombre": "Debate multi-agente",
        "descripcion": "3 agentes proponen en paralelo y un agregador elige por mayoría.",
        "parametros": {"max_llamados": 4, "n_agentes": 3},
        "costo_relativo": 5.0,
        "precondiciones": ["problema donde la diversidad de intentos ayuda"],
        "recomendada_para": ["puzzles"],
    },
    {
        "id": "plan_tools_verify",
        "nombre": "Plan + herramientas + verificación",
        "descripcion": "Planifica, usa herramientas (contexto recuperado, ejecución de tests) y verifica antes de responder.",
        "parametros": {"max_llamados": 4, "herramientas": ["contexto", "tests"]},
        "costo_relativo": 4.0,
        "precondiciones": ["hay herramientas disponibles para la clase de problema"],
        "recomendada_para": ["codigo", "herramientas"],
    },
]

MAX_COSTO_RELATIVO = max(a["costo_relativo"] for a in ARCHITECTURES)


def get_arch(arch_id):
    """Devuelve la ficha de una familia. KeyError si no existe en el repertorio."""
    for a in ARCHITECTURES:
        if a["id"] == arch_id:
            return a
    raise KeyError(f"arquitectura desconocida: {arch_id!r} (repertorio v{REGISTRY_VERSION})")


def list_archs():
    """IDs de las familias del repertorio, en orden fijo."""
    return [a["id"] for a in ARCHITECTURES]


def recomendada_para(clase):
    """Prior manual clase → arquitectura (diseño humano, NO aprendido).

    Se usa solo como baseline 'sin memoria' en la fase C. El selector
    aprende sus propias preferencias desde cero (priors uniformes).
    """
    for a in ARCHITECTURES:
        if clase in a["recomendada_para"]:
            return a["id"]
    return "single"
