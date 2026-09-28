"""Evals de ALMA — la vara externa.

El evaluador del experimento (alma/evaluator.py) mide si el sistema
resuelve problemas sintéticos. ESTE módulo mide si ALMA acierta sobre
el mundo real del usuario: sus gastos, su rutina, sus patrones.

Regla de oro: la verdad (ground truth) siempre viene de datos reales
— transacciones de Plaid, rutina reportada — nunca del modelo. El que
aprende no puede modificar ni las etiquetas ni las métricas (la versión
EVALS_VERSION firma cada resultado; cambiar el evaluador invalida la
comparación con el historial).

Cada eval tiene:
  - un baseline heurístico (corre HOY, sin API key ni LLM),
  - un punto de entrada `predict_fn` opcional para enchufar un método
    nuevo (LLM, DSPy, lo que sea) y compararlo contra el baseline
    con la MISMA vara. Ese es el loop "ALMA aprende de ALMA".

Uso:
    python -m alma.evals.run            # corre todo y guarda historial
    python -m alma.evals.run --eval categorizar_gastos
"""

EVALS_VERSION = "evals-v1"

from .base import EvalResult, EvalSuite, evaluar_suite  # noqa: F401
