"""Evaluator Harness — núcleo FIJO (sección 9 del informe).

Jerarquía de evaluación (sección 5.1 del informe):
  1. Verificadores externos (exact-match normalizado, tests de código
     ejecutados en subprocess con timeout) = ground truth, no hackeables
     por el que aprende.
  2. Juez LLM *calibrado* contra los verificadores, solo donde no hay
     verificador externo. En este prototipo el juez es un stub honesto:
     en modo mock se deshabilita (λ=1, todo el peso al verificador);
     con backend real hace un llamado de sí/no y se registra el acuerdo
     juez-vs-verificador para auditarlo.

Cada evaluación se firma con EVALUATOR_VERSION. Si el evaluador cambiara,
las filas viejas del store quedan marcadas con su versión y el drift es
detectable. El que aprende NO puede modificar el evaluador (ver gates.py).

Reward (diseño fijo, documentado):
    reward = 0.75 * exito + 0.25 * (1 - costo_relativo / MAX_COSTO_RELATIVO)
Combina rendimiento (verificador) y eficiencia. El componente de costo usa
el costo *relativo de la arquitectura* (registry), no USD, para que el
reward sea comparable entre proveedores.
"""

import re
import subprocess
import sys
import tempfile
import os
import unicodedata

from .registry import get_arch, MAX_COSTO_RELATIVO

EVALUATOR_VERSION = "eval-v1"

W_EXITO = 0.75
W_COSTO = 0.25


def normalize_text(s):
    """Normaliza para exact-match: minúsculas, sin tildes, sin puntuación,
    espacios colapsados."""
    s = unicodedata.normalize("NFKD", s.lower().strip())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _as_float_strict(s):
    """Float solo si TODO el string es un número (no extrae sub-números)."""
    try:
        return float(str(s).strip().replace(",", "."))
    except (ValueError, AttributeError):
        return None


def exact_match(respuesta, esperado):
    """True si coinciden tras normalizar; tolera equivalencia numérica
    ('200' == '200.0'), pero '8+8' != '8-8'."""
    fr, fe = _as_float_strict(respuesta), _as_float_strict(esperado)
    if fr is not None and fe is not None:
        return abs(fr - fe) < 1e-6
    r, e = normalize_text(str(respuesta)), normalize_text(str(esperado))
    return r == e


def extract_code(respuesta):
    """Extrae el primer bloque ```python ... ```; si no hay, devuelve el texto."""
    m = re.search(r"```(?:python)?\s*\n(.*?)```", respuesta, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)
    return respuesta


def run_code_tests(codigo, tests, timeout=10):
    """Ejecuta `tests` ( asserts ) contra `codigo` en un subprocess con timeout.

    Devuelve (paso: bool, detalle: str). Sin red disponible para el hijo
    más allá de la del proceso (limitación documentada: no es un sandbox
    real; ver README).
    """
    codigo = extract_code(codigo)
    with tempfile.TemporaryDirectory() as tmp:
        sol_path = os.path.join(tmp, "solucion.py")
        run_path = os.path.join(tmp, "run_tests.py")
        with open(sol_path, "w", encoding="utf-8") as f:
            f.write(codigo)
        with open(run_path, "w", encoding="utf-8") as f:
            f.write("from solucion import *\n" + tests + "\n")
        try:
            proc = subprocess.run(
                [sys.executable, run_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
            )
        except subprocess.TimeoutExpired:
            return False, f"timeout tras {timeout}s (posible loop infinito)"
        if proc.returncode == 0:
            return True, "todos los tests pasaron"
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, " | ".join(err[-3:]) if err else f"exit {proc.returncode}"


class StubJudge:
    """Juez deshabilitado (modo mock / datasets con verificador total).

    score() devuelve None → λ=1: todo el peso va al verificador externo.
    """

    def score(self, problema, respuesta):
        return None


class LLMJudge:
    """Juez LLM real: un llamado sí/no con rúbrica. Calibrado contra
    verificadores vía agreement() — si el acuerdo cae, el meta-loop debe
    congelar el aprendizaje del selector (freno anti-colapso, sec. 5.1).
    """

    def __init__(self, backend):
        self.backend = backend
        self._acuerdos = []  # (juez_ok, verificador_ok)

    def score(self, problema, respuesta):
        prompt = (
            "Sos un evaluador estricto. Respondé con un solo caracter: 1 si la "
            "respuesta resuelve correctamente el problema, 0 si no.\n\n"
            f"Problema: {problema['enunciado']}\n"
            f"Respuesta a evaluar: {respuesta}\n"
            "Tu veredicto (1 o 0):"
        )
        texto, _uso = self.backend.complete(prompt, system="Sos un juez binario.")
        m = re.search(r"[01]", texto)
        return int(m.group(0)) if m else 0

    def registrar_acuerdo(self, juez_ok, verificador_ok):
        self._acuerdos.append((bool(juez_ok), bool(verificador_ok)))

    def agreement(self):
        """Fracción de acuerdo juez-vs-verificador. None si no hay datos."""
        if not self._acuerdos:
            return None
        return sum(1 for j, v in self._acuerdos if j == v) / len(self._acuerdos)


class Evaluator:
    """Harness de evaluación. Fijo: su versión firma cada evaluación."""

    def __init__(self, judge=None, timeout_tests=10):
        self.judge = judge or StubJudge()
        self.timeout_tests = timeout_tests

    def score(self, problema, respuesta, arch_id, traza=""):
        """Evalúa una respuesta. Devuelve dict de métricas + reward.

        - verificador 'exact': exact-match contra problema['esperado'].
        - verificador 'codigo': run_code_tests contra problema['tests'].
        """
        verificador = problema.get("verificador", "exact")
        if verificador == "codigo":
            exito, detalle = run_code_tests(
                respuesta, problema["tests"], timeout=self.timeout_tests
            )
            detalle_ver = f"tests: {detalle}"
        else:
            ok = exact_match(respuesta, problema["esperado"])
            exito, detalle_ver = ok, f"exact-match: {'ok' if ok else 'fallo'}"

        exito_f = 1.0 if exito else 0.0

        # Juez (si está habilitado): solo pesa donde no hay verificador duro.
        # En este prototipo todos los problemas tienen verificador → λ=1.
        juez_ok = self.judge.score(problema, respuesta)
        if juez_ok is None:
            lam, combinado = 1.0, exito_f
            acuerdo = None
        else:
            lam = 0.7
            combinado = lam * exito_f + (1 - lam) * float(juez_ok)
            acuerdo = bool(juez_ok) == bool(exito)
            if hasattr(self.judge, "registrar_acuerdo"):
                self.judge.registrar_acuerdo(juez_ok, exito)

        costo_rel = get_arch(arch_id)["costo_relativo"]
        reward = (
            W_EXITO * combinado
            + W_COSTO * (1.0 - costo_rel / MAX_COSTO_RELATIVO)
        )
        return {
            "exito": exito_f,
            "reward": round(reward, 4),
            "detalle_verificador": detalle_ver,
            "lambda_verificador": lam,
            "juez_ok": juez_ok,
            "acuerdo_juez_verificador": acuerdo,
            "evaluator_version": EVALUATOR_VERSION,
            "traza": traza,
        }
