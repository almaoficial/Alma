"""Problem Featurizer + Classifier — taxonomía FIJA v2 para ALMA-EXP2.

EXP2 es una replicación hostil de EXP1: mismo protocolo, misma hipótesis,
mismo criterio pre-registrado, pero distribución NUEVA de problemas
(5 clases distintas) y clasificador nuevo. La taxonomía v1 de EXP1 queda
congelada e intacta en featurizer.py.

Las 5 clases nuevas:
  - logica: deducción (silogismos, modus ponens/tollens, falacias).
  - traduccion: traducción léxica EN<->ES de una palabra (unívoca).
  - resumen: identificar el proceso/fenómeno que describe un texto.
  - depuracion: localizar la línea con el bug en un snippet.
  - conocimiento: pregunta factual de cultura general (un hop).

Features = substrings estructurales sobre el enunciado normalizado
(minúsculas, sin tildes). "cultura general" es un marcador estructural
del dataset (categoría del quiz), documentado como tal: la taxonomía es
infraestructura humana y auditable, no algo que el sistema descubre.
"""

import re
import unicodedata

TAXONOMY_VERSION = "tax-v2-exp2"
CLASES = ["logica", "traduccion", "resumen", "depuracion", "conocimiento"]
DESCONOCIDA = "desconocida"

UMBRAL_CONFIANZA = 0.35  # bajo esto → "desconocida" (igual que v1)

CUES = [
    "se deduce",
    "si o no",
    "traduc",
    "describe el texto",
    "una sola palabra",
    "linea",
    "error",
    "cultura general",
]


def _norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s


def featurize(enunciado):
    t = _norm(enunciado)
    return {cue: (cue in t) for cue in CUES}


# Reglas de scoring por clase: (cue, peso). Pesos a mano, como en v1.
REGLAS = {
    "logica": [
        ("se deduce", 4.0),
        ("si o no", 2.0),
    ],
    "traduccion": [
        ("traduc", 4.0),
    ],
    "resumen": [
        ("describe el texto", 4.0),
        ("una sola palabra", 1.5),
    ],
    "depuracion": [
        ("linea", 2.5),
        ("error", 1.5),
    ],
    "conocimiento": [
        ("cultura general", 4.0),
    ],
}


def _scores(feats, candidatas):
    return {
        c: round(sum(w for cue, w in REGLAS[c] if feats.get(cue, False)), 3)
        for c in candidatas
    }


def classify(enunciado, candidatas=None):
    """Devuelve (clase, confianza, scores). Misma interfaz que v1."""
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
