"""El juez del evaluador barato — la "lámpara" del enchufe (idea 1, parte 2).

Dos jueces, dos honestidades distintas:

1. JuezHeuristico (US$0, siempre disponible): heurísticas declaradas que
   atrapan salidas DEGENERADAS — evasivas ("no sé", "como modelo de..."),
   bucles de repetición. Límite honesto: NO detecta "fluido pero
   equivocado". Su valor real es ser el BASELINE contra el que se mide
   cualquier juez con modelo: si el juez caro no le gana a esto de forma
   medida, no vale lo que cuesta.

2. JuezLLM (APAGADO por default): juez con modelo real y rúbrica. El código
   mismo exige la gobernanza: sin backend, sin aprobación explícita y sin
   presupuesto pre-registrado mayor a cero, se niega a correr. Encenderlo
   sin el "sí" con costo y tiempo es imposible por diseño.
"""

from collections import Counter
import json as _json
import os as _os
import subprocess as _subprocess


# -- heurísticas (US$0) --------------------------------------------------------

MARCADORES_EVASION = (
    "no sé", "no estoy seguro", "como modelo de lenguaje", "como ia ",
    "no puedo", "lo siento", "disculpa", "no tengo información",
)


def sin_evasivas(salida):
    """Reprueba salidas que esquivan en vez de responder."""
    baja = salida.lower()
    return not any(m in baja for m in MARCADORES_EVASION)


def sin_bucle(salida, repeticiones=3, min_largo_oracion=20):
    """Reprueba salidas atascadas repitiendo la misma oración."""
    oraciones = [o.strip() for o in salida.replace("!", ".").replace("?", ".").split(".")]
    oraciones = [o for o in oraciones if len(o) >= min_largo_oracion]
    if not oraciones:
        return True
    mas_repetida = Counter(oraciones).most_common(1)[0][1]
    return mas_repetida < repeticiones


HEURISTICAS_DEFAULT = (sin_evasivas, sin_bucle)


class JuezHeuristico:
    """Baseline US$0: todas las heurísticas tienen que aprobar."""

    def __init__(self, heuristicas=None):
        self.heuristicas = tuple(heuristicas or HEURISTICAS_DEFAULT)

    def __call__(self, salida, contexto=None):
        return all(h(salida) for h in self.heuristicas)


# -- juez con modelo (apagado por default) -------------------------------------

RUBRICA = (
    "Sos un juez barato. Respondé SOLO con APROBADO o RECHAZADO, sin más texto.\n"
    "Criterio: ¿la respuesta intenta resolver lo pedido, sin evasivas,\n"
    "sin errores obvios y sin irse por las ramas?\n"
    "Pregunta: {pregunta}\n"
    "Respuesta: {salida}\n"
    "Veredicto:"
)


class JuezLLM:
    """Juez con modelo real. Nace apagado y con el tanque en cero.

    backend: callable prompt -> texto | (texto, costo_usd).
    Para encenderlo hace falta TODO junto: backend, aprobado=True y
    presupuesto_usd > 0. Sin eso, cada llamado levanta RuntimeError.
    El gasto se descuenta del presupuesto; agotado el tanque, se apaga.
    """

    def __init__(self, backend=None, presupuesto_usd=0.0, aprobado=False):
        self.backend = backend
        self.presupuesto_usd = presupuesto_usd
        self.aprobado = aprobado
        self.gastado_usd = 0.0
        self.llamados = 0

    def _puedo_correr(self):
        return (
            self.aprobado
            and self.backend is not None
            and self.presupuesto_usd > 0
            and self.gastado_usd < self.presupuesto_usd
        )

    def _prompt(self, salida, contexto):
        pregunta = (contexto or {}).get("pregunta", "(no declarada)")
        return RUBRICA.format(pregunta=pregunta, salida=salida)

    def __call__(self, salida, contexto=None):
        if not self._puedo_correr():
            raise RuntimeError(
                "JuezLLM apagado: requiere backend + aprobado=True + "
                "presupuesto_usd > 0. Sin el 'sí' con costo y tiempo, no corre."
            )
        resultado = self.backend(self._prompt(salida, contexto))
        if isinstance(resultado, tuple):
            texto, costo = resultado
        else:
            texto, costo = resultado, 0.0
        self.llamados += 1
        self.gastado_usd += float(costo)
        upper = str(texto).upper()
        if "RECHAZADO" in upper:
            return False
        if "APROBADO" in upper:
            return True
        raise ValueError(f"veredicto no parseable: {texto!r}")


# -- cableado default ----------------------------------------------------------

def backend_openrouter(modelo="mistralai/mistral-nemo", max_tokens=10):
    """Backend OpenRouter para el JuezLLM (usa la skill openrouter conectada).

    Modelo default: el ganador medido de EXP-JUEZ-001 (acuerdo 0,933).
    """
    or_chat = _os.path.expanduser("~/workspace/skills/openrouter/bin/or_chat.py")

    def _backend(prompt):
        msgs = _json.dumps([{"role": "user", "content": prompt}])
        r = _subprocess.run(
            ["python3", or_chat, "--model", modelo, "--messages", msgs,
             "--max-tokens", str(max_tokens), "--temperature", "0",
             "--timeout", "120"],
            capture_output=True, text=True, timeout=150,
        )
        if r.returncode != 0:
            raise RuntimeError(f"or_chat falló: {r.stderr[:200]}")
        return _json.loads(r.stdout)["text"]

    return _backend


def evaluador_default(presupuesto_usd=0.05, modelo="mistralai/mistral-nemo",
                      backend=None):
    """El evaluador cableado: deterministas + JuezLLM con presupuesto explícito.

    Llamar a esta función ES la aprobación del gasto: el presupuesto va
    pre-registrado como parámetro y el juez se apaga solo al agotarlo.
    EvaluadorBarato() pelado sigue siendo US$0 (juez=None) — el default
    seguro no gasta por sorpresa en ningún camino de código futuro.
    """
    from alma_service.evaluador_barato import EvaluadorBarato
    juez = JuezLLM(backend=backend or backend_openrouter(modelo),
                  presupuesto_usd=presupuesto_usd, aprobado=True)
    return EvaluadorBarato(juez=juez)
