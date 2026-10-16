"""Problem Featurizer + Classifier — taxonomía FIJA v1 (sección 9 del informe).

La taxonomía de clases es humana, explícita y auditable. El sistema NO
descubre clases por clustering (problema abierto, no implementado):
clasifica dentro de estas 5 con reglas legibles. Si ninguna regla alcanza
el umbral, la clase es "desconocida" → el experimentador la reporta.

Reglas = features estructurales del enunciado (sin ML pesado):
  - tiene_codigo, pregunta_cuantitativa, pregunta_factual, menciona_fuente,
    menciona_24, n_numeros, es_pregunta, es_imperativo, menciona_artefacto.
"""

import re

TAXONOMY_VERSION = "tax-v1"
CLASES = ["calculo", "codigo", "qa_multihop", "herramientas", "puzzles"]
DESCONOCIDA = "desconocida"

UMBRAL_CONFIANZA = 0.35  # bajo esto → "desconocida"


def featurize(enunciado):
    t = enunciado.lower()
    numeros = re.findall(r"\d+(?:[.,]\d+)?", t)
    return {
        "longitud": len(t),
        "n_numeros": len(numeros),
        "tiene_codigo": bool(
            re.search(r"```|def |función|escribí una función|código|programa", t)
        ),
        "pregunta_cuantitativa": bool(
            re.search(
                r"cuánt[oa]s?|total|suma|promedio|porcentaje|km/h|área|perímetro"
                r"|reparto|descuento|kilómetros|litros|cuadrado|rectángulo",
                t,
            )
        ),
        "pregunta_factual": bool(
            re.search(
                r"país|planeta|elemento|océano|siglo|continente|idioma|capital"
                r"|nació|director|autor|químico|fotosíntesis|jugadores",
                t,
            )
        ),
        "menciona_fuente": bool(
            re.search(
                r"según|informe|documento|guía|ficha|folleto|mapa|anuncio|reseña|perfil",
                t,
            )
        ),
        "menciona_24": bool(re.search(r"\b24\b", t)),
        "menciona_operaciones": bool(re.search(r"operaciones|\+|\*|/", t)),
        "es_pregunta": t.rstrip().endswith("?"),
        "es_imperativo": bool(
            re.match(r"\s*(indicá|mencioná|escribí|buscá|usando)", t)
        )
        and not t.rstrip().endswith("?"),
        "menciona_artefacto": bool(
            re.search(r"informe|documento|guía|ficha|función|tabla|programa", t)
        ),
    }


# Reglas de scoring por clase: (condición sobre features, peso).
# Pesos elegidos a mano para que cada clase gane en sus problemas típicos
# y haya similitudes débiles entre clases vecinas (calculo↔qa,
# codigo↔herramientas), que es lo que permite transferencia en el
# experimento leave-one-class-out.
REGLAS = {
    "codigo": [
        ("tiene_codigo", 3.0),
        ("menciona_artefacto", 0.5),
    ],
    "calculo": [
        ("pregunta_cuantitativa", 2.0),
        ("n_numeros>=2", 0.5),
        ("es_pregunta", 0.8),
    ],
    "qa_multihop": [
        ("pregunta_factual", 2.0),
        ("es_pregunta", 0.8),
    ],
    "herramientas": [
        ("menciona_fuente", 3.0),
        ("es_imperativo", 0.7),
        ("menciona_artefacto", 0.5),
    ],
    "puzzles": [
        ("menciona_24", 4.0),
        ("n_numeros==4&menciona_operaciones", 2.0),
        ("n_numeros>=1", 0.6),
    ],
}


def _condicionCumple(cond, feats):
    if cond == "n_numeros>=2":
        return feats["n_numeros"] >= 2
    if cond == "n_numeros>=1":
        return feats["n_numeros"] >= 1
    if cond == "n_numeros==4&menciona_operaciones":
        return feats["n_numeros"] == 4 and feats["menciona_operaciones"]
    return bool(feats.get(cond, False))


def _scores(feats, candidatas):
    return {
        c: round(sum(w for cond, w in REGLAS[c] if _condicionCumple(cond, feats)), 3)
        for c in candidatas
    }


def classify(enunciado, candidatas=None):
    """Devuelve (clase, confianza, scores).

    confianza = mejor_score / suma_scores. Si el mejor score es 0 o la
    confianza < UMBRAL_CONFIANZA → clase "desconocida".
    `candidatas` restringe a un subconjunto (usado en leave-one-class-out:
    solo clases ya entrenadas).
    """
    candidatas = candidatas or CLASES
    feats = featurize(enunciado)
    scores = _scores(feats, candidatas)
    mejor = max(candidatas, key=lambda c: scores[c])
    total = sum(scores.values())
    if scores[mejor] <= 0 or total <= 0:
        return DESCONOCIDA, 0.0, scores
    confianza = scores[mejor] / total
    if confianza < UMBRAL_CONFIANZA:
        return DESCONOCIDA, round(confianza, 3), scores
    return mejor, round(confianza, 3), scores
