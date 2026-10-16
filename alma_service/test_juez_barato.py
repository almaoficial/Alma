"""Tests del juez barato — idea 1, parte 2 (la "lámpara").

Convención del repo: funciones planas, sin pytest. Correr:
    python3 alma_service/test_juez_barato.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alma_service.juez_barato import (
    JuezHeuristico, JuezLLM, evaluador_default, sin_evasivas, sin_bucle,
)
from alma_service.evaluador_barato import EvaluadorBarato, medir


def check(nombre, cond):
    print(("PASS" if cond else "FAIL") + " - " + nombre)
    if not cond:
        raise AssertionError(nombre)


# -- heurísticas sueltas ----------------------------------------------------------
check("evasiva se detecta",
      sin_evasivas("No sé la respuesta a eso") is False)
check("el 'como modelo' se detecta",
      sin_evasivas("Como modelo de lenguaje, no puedo") is False)
check("respuesta normal pasa", sin_evasivas("La respuesta es 42.") is True)

bucle = "El cielo de la mañana es completamente azul. " * 3 + "Fin."
check("bucle de 3 se detecta", sin_bucle(bucle) is False)
check("repetición de 2 pasa",
      sin_bucle("El cielo de la mañana es completamente azul. " * 2) is True)
check("texto normal pasa", sin_bucle("Una respuesta completa y variada.") is True)

# -- JuezHeuristico ---------------------------------------------------------------
jh = JuezHeuristico()
check("juez heurístico aprueba salida sana",
      jh("La capital de Francia es París.") is True)
check("juez heurístico reprueba evasiva",
      jh("No estoy seguro, disculpa.") is False)
check("juez acepta contexto sin usarlo",
      jh("texto ok", {"pregunta": "x"}) is True)

# -- JuezLLM: nace apagado ----------------------------------------------------------
def backend_mock(prompt):
    return ("APROBADO", 0.0001)


def _niega(juez):
    try:
        juez("salida", None)
        return False
    except RuntimeError:
        return True


check("sin backend se niega", _niega(JuezLLM()))
check("con backend pero sin aprobado se niega",
      _niega(JuezLLM(backend=backend_mock)))
check("con aprobado pero sin presupuesto se niega",
      _niega(JuezLLM(backend=backend_mock, aprobado=True)))


# -- JuezLLM: encendido con llave ----------------------------------------------------
jl = JuezLLM(backend=backend_mock, presupuesto_usd=0.001, aprobado=True)
check("encendido aprueba cuando el modelo dice APROBADO",
      jl("salida válida", {"pregunta": "p"}) is True)
check("descuenta el gasto", abs(jl.gastado_usd - 0.0001) < 1e-9)
check("cuenta los llamados", jl.llamados == 1)


def backend_duro(prompt):
    return "RECHAZADO"

jl2 = JuezLLM(backend=backend_duro, presupuesto_usd=1.0, aprobado=True)
check("encendido reprueba cuando el modelo dice RECHAZADO",
      jl2("salida floja") is False)
check("backend que devuelve solo texto no rompe el costo",
      jl2.gastado_usd == 0.0)

jl3 = JuezLLM(backend=backend_mock, presupuesto_usd=0.0001, aprobado=True)
jl3("una")
check("tanque agotado apaga el juez", _niega(jl3))

# -- integración con el evaluador ------------------------------------------------------
ev = EvaluadorBarato(juez=JuezHeuristico())
check("evaluador+juez: evasiva que pasa lo determinista igual se rechaza",
      ev("No sé, disculpa, no tengo información sobre eso.") is False)
check("evaluador+juez: salida sana se aprueba",
      ev("La capital de Francia es París, con detalle.") is True)

pares = [
    ("La capital de Francia es París.", True),
    ("No sé la respuesta, lo siento.", False),
    ("El cielo de la mañana es completamente azul. " * 3, False),
]
m = medir(EvaluadorBarato(juez=JuezHeuristico()), pares)
check("medir: el juez heurístico acuerda 3/3 en set diseñado",
      m["acuerdo"] == 1.0)

# -- cableado default ---------------------------------------------------------------
check("EvaluadorBarato pelado sigue US$0 (sin juez)",
      EvaluadorBarato().juez is None)


def backend_falso(prompt):
    return "RECHAZADO" if "no sé" in prompt.lower() else "APROBADO"


ev_def = evaluador_default(presupuesto_usd=0.05, backend=backend_falso)
check("evaluador_default trae juez LLM aprobado",
      isinstance(ev_def.juez, JuezLLM) and ev_def.juez.aprobado is True)
check("evaluador_default respeta el presupuesto dado",
      ev_def.juez.presupuesto_usd == 0.05)
check("evaluador_default funciona end-to-end con backend mock",
      ev_def("una salida válida y completa") is True)
check("evaluador_default rechaza evasiva end-to-end",
      ev_def("No sé, disculpa, no tengo información.") is False)

print("\n25/25 checks en verde")
