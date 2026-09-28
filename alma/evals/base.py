"""Base de los evals: métricas, resultado firmado e historial.

El historial (JSONL) es la memoria de la vara externa: cada fila dice
qué eval, con qué versión del evaluador, qué método y qué puntaje.
Si ALMA mejora de verdad, se ve acá. Si hace trampa con la métrica,
el historial lo delata (los puntajes suben pero la realidad no).
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from . import EVALS_VERSION

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "eval_history.jsonl")


# -- métricas -------------------------------------------------------------
def accuracy(ys_true, ys_pred):
    ys_true, ys_pred = list(ys_true), list(ys_pred)
    if not ys_true:
        return 0.0
    return sum(1 for t, p in zip(ys_true, ys_pred) if t == p) / len(ys_true)


def precision_recall_f1(ys_true, ys_pred, positivo=True):
    tp = sum(1 for t, p in zip(ys_true, ys_pred) if t == positivo and p == positivo)
    fp = sum(1 for t, p in zip(ys_true, ys_pred) if t != positivo and p == positivo)
    fn = sum(1 for t, p in zip(ys_true, ys_pred) if t == positivo and p != positivo)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4)}


def mae(ys_true, ys_pred):
    ys_true, ys_pred = list(ys_true), list(ys_pred)
    if not ys_true:
        return 0.0
    return sum(abs(t - p) for t, p in zip(ys_true, ys_pred)) / len(ys_true)


def mape(y_true, y_pred):
    """Error porcentual absoluto. None si el real es 0 (indefinido)."""
    if y_true == 0:
        return None
    return abs(y_true - y_pred) / abs(y_true)


def brier(probs, outcomes):
    """Brier score para predicciones probabilísticas (menor = mejor)."""
    probs, outcomes = list(probs), list(outcomes)
    if not probs:
        return 0.0
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / len(probs)


# -- resultado e historial -------------------------------------------------
@dataclass
class EvalResult:
    eval_id: str
    score: float                    # métrica principal (mayor = mejor, salvo brier)
    metodo: str = "baseline"        # qué método produjo la predicción
    detalle: dict = field(default_factory=dict)
    version: str = EVALS_VERSION
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        return asdict(self)

    def guardar(self, path=HISTORY_PATH):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(self.to_dict(), ensure_ascii=False) + "\n")


def leer_historial(eval_id=None, path=HISTORY_PATH):
    """Lee el historial, opcionalmente filtrado por eval."""
    if not os.path.exists(path):
        return []
    filas = []
    with open(path, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                fila = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if eval_id is None or fila.get("eval_id") == eval_id:
                filas.append(fila)
    return filas


class EvalSuite:
    """Conjunto de evals. Cada eval es una función () -> EvalResult."""

    def __init__(self):
        self._evals = {}

    def registrar(self, eval_id):
        def deco(fn):
            self._evals[eval_id] = fn
            return fn
        return deco

    def correr(self, eval_id=None, guardar=True):
        resultados = []
        ids = [eval_id] if eval_id else sorted(self._evals)
        for eid in ids:
            if eid not in self._evals:
                raise KeyError(f"eval desconocido: {eid!r} (hay: {sorted(self._evals)})")
            res = self._evals[eid]()
            if not isinstance(res, EvalResult):
                raise TypeError(f"{eid} no devolvió EvalResult")
            if guardar:
                res.guardar()
            resultados.append(res)
        return resultados


def evaluar_suite(suite, eval_id=None, guardar=True):
    resultados = suite.correr(eval_id=eval_id, guardar=guardar)
    print(f"{'eval':<22}{'metodo':<14}{'score':>8}  detalle")
    print("-" * 70)
    for r in resultados:
        det = ", ".join(f"{k}={v}" for k, v in list(r.detalle.items())[:4])
        print(f"{r.eval_id:<22}{r.metodo:<14}{r.score:>8.4f}  {det}")
    return resultados
