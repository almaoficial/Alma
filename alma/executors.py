"""Executors — los 6 runners con interfaz común.

    ejecutar(arch_id, problema, backend) -> dict con:
        respuesta  : respuesta final (texto; código en bruto para 'codigo')
        traza      : resumen legible de los pasos
        costo_usd  : suma de los llamados
        llamados   : cantidad de llamados al backend

Cada runner usa el backend de forma distinta (esa es la "arquitectura"),
pero todos exponen lo mismo. El backend decide si hay un modelo real o el
mock detrás: los runners no lo saben.
"""

import re

from .evaluator import normalize_text, run_code_tests


def _call(backend, prompt, problema, arch_id, system=None, **kw):
    texto, uso = backend.complete(
        prompt, system=system,
        problem_id=problema["id"], arch_id=arch_id, **kw,
    )
    return texto, backend.costo(uso)


def _extraer_respuesta_marcada(texto):
    m = re.search(r"Respuesta:\s*(.+)", texto, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else texto.strip()


def _prompt_base(problema):
    return f"Problema: {problema['enunciado']}"


def _run_single(problema, backend):
    prompt = (
        "Respondé de forma concisa, solo con la respuesta final, sin explicación.\n\n"
        + _prompt_base(problema)
    )
    if problema.get("verificador") == "codigo":
        prompt = (
            "Escribí solo el código Python pedido, dentro de un bloque ```python.\n\n"
            + _prompt_base(problema)
        )
    texto, costo = _call(backend, prompt, problema, "single",
                         system="Sos un asistente conciso.")
    return {"respuesta": texto.strip(), "traza": "single: 1 llamado",
            "costo_usd": costo, "llamados": 1}


def _run_cot(problema, backend):
    prompt = (
        "Pensá paso a paso y al final escribí exactamente una línea con el "
        "formato: Respuesta: <tu respuesta final>\n\n" + _prompt_base(problema)
    )
    if problema.get("verificador") == "codigo":
        prompt = (
            "Pensá paso a paso el algoritmo y al final escribí solo el código "
            "Python dentro de un bloque ```python.\n\n" + _prompt_base(problema)
        )
    texto, costo = _call(backend, prompt, problema, "cot",
                         system="Sos un asistente que razona paso a paso.",
                         formato="respuesta_marcada")
    return {"respuesta": _extraer_respuesta_marcada(texto),
            "traza": "cot: 1 llamado con razonamiento",
            "costo_usd": costo, "llamados": 1}


def _run_self_consistency(problema, backend, n=5):
    prompt = (
        "Pensá paso a paso y al final escribí exactamente una línea con el "
        "formato: Respuesta: <tu respuesta final>\n\n" + _prompt_base(problema)
    )
    respuestas, costo, llamados = [], 0.0, 0
    for i in range(n):
        texto, c = _call(backend, prompt, problema, "self_consistency",
                         system="Sos un asistente que razona paso a paso.",
                         intento=i, formato="respuesta_marcada")
        respuestas.append(_extraer_respuesta_marcada(texto))
        costo += c
        llamados += 1
    votos = {}
    for r in respuestas:
        k = normalize_text(r)
        votos[k] = votos.get(k, 0) + 1
    ganador = max(votos, key=lambda k: votos[k])
    final = next(r for r in respuestas if normalize_text(r) == ganador)
    return {"respuesta": final,
            "traza": f"self_consistency: {n} muestras, voto {votos[ganador]}/{n}",
            "costo_usd": costo, "llamados": llamados}


def _run_reflexion(problema, backend, max_reintentos=2):
    es_codigo = problema.get("verificador") == "codigo"
    prompt_actor = (
        "Pensá paso a paso y al final escribí exactamente una línea con el "
        "formato: Respuesta: <tu respuesta final>\n\n" + _prompt_base(problema)
    )
    if es_codigo:
        prompt_actor = (
            "Escribí el código Python pedido dentro de un bloque ```python.\n\n"
            + _prompt_base(problema)
        )
    costo, llamados, pasos = 0.0, 0, []
    intento = 0
    texto, c = _call(backend, prompt_actor, problema, "reflexion",
                     system="Sos un agente que resuelve problemas.",
                     intento=intento,
                     formato=None if es_codigo else "respuesta_marcada")
    costo += c
    llamados += 1
    for _ in range(max_reintentos):
        critica, c = _call(backend, "Evaluá si la respuesta anterior es correcta.",
                           problema, "reflexion",
                           system="Sos un crítico estricto.",
                           modo="critica", intento=intento)
        costo += c
        llamados += 1
        pasos.append("ok" if "incorrecta" not in critica.lower() else "fallo")
        if "incorrecta" not in critica.lower():
            break
        intento += 1
        prompt_reintento = (
            f"Tu intento anterior falló. Crítica recibida: {critica}\n"
            "Corregí el error y " +
            ("reescribí el código.\n\n" if es_codigo
             else "al final escribí: Respuesta: <tu respuesta final>\n\n")
            + _prompt_base(problema)
        )
        texto, c = _call(backend, prompt_reintento, problema, "reflexion",
                         system="Sos un agente que corrige sus errores.",
                         intento=intento,
                         formato=None if es_codigo else "respuesta_marcada")
        costo += c
        llamados += 1
    respuesta = texto if es_codigo else _extraer_respuesta_marcada(texto)
    return {"respuesta": respuesta,
            "traza": f"reflexion: {llamados} llamados, críticas={pasos}",
            "costo_usd": costo, "llamados": llamados}


def _run_debate(problema, backend, n_agentes=3):
    propuestas, costo, llamados = [], 0.0, 0
    for i in range(n_agentes):
        prompt = (
            f"Sos el agente {i + 1} de {n_agentes}. Proponé tu solución de forma "
            "independiente, concisa.\n\n" + _prompt_base(problema)
        )
        texto, c = _call(backend, prompt, problema, "debate",
                         system=f"Sos el agente {i + 1} de un panel.",
                         modo="agente", idx=i)
        propuestas.append(texto.strip())
        costo += c
        llamados += 1
    texto, c = _call(backend, "Elegí la mejor propuesta por mayoría.",
                     problema, "debate",
                     system="Sos el agregador del panel.",
                     modo="agrega")
    costo += c
    llamados += 1
    return {"respuesta": texto.strip(),
            "traza": f"debate: {n_agentes} agentes + agregador",
            "costo_usd": costo, "llamados": llamados}


def _run_plan_tools_verify(problema, backend):
    costo, llamados, pasos = 0.0, 0, []
    plan, c = _call(backend,
                    "Planificá en 2-3 pasos cómo resolver este problema y qué "
                    "herramienta usarías.\n\n" + _prompt_base(problema),
                    problema, "plan_tools_verify",
                    system="Sos un planificador.")
    costo += c
    llamados += 1
    pasos.append("plan")

    es_codigo = problema.get("verificador") == "codigo"
    if es_codigo:
        # Herramienta real: escribir código y correr los tests del problema.
        codigo, c = _call(backend,
                          "Escribí el código Python pedido dentro de un bloque "
                          "```python.\n\n" + _prompt_base(problema),
                          problema, "plan_tools_verify",
                          system="Sos un programador.", intento=0)
        costo += c
        llamados += 1
        ok, detalle = run_code_tests(codigo, problema["tests"])
        pasos.append(f"tests({'ok' if ok else 'fallo'})")
        if not ok:
            fix, c = _call(backend,
                           f"Tu código falló los tests: {detalle}\nCorregilo y "
                           "reescribí el bloque ```python completo.\n\n"
                           + _prompt_base(problema),
                           problema, "plan_tools_verify",
                           system="Sos un programador que corrige con tests.",
                           intento=1)
            costo += c
            llamados += 1
            codigo = fix
            pasos.append("fix")
        return {"respuesta": codigo,
                "traza": "plan_tools_verify: " + "→".join(pasos),
                "costo_usd": costo, "llamados": llamados}

    # Herramienta simulada: contexto recuperado (en producción: búsqueda).
    contexto = problema.get("contexto")
    herramienta_out = (
        f"[herramienta:contexto] {contexto}" if contexto
        else "[herramienta:contexto] sin resultados"
    )
    pasos.append("tool:contexto")
    final, c = _call(backend,
                     f"Plan: {plan}\n{herramienta_out}\n\n"
                     "Con el plan y la herramienta, respondé de forma concisa, "
                     "solo la respuesta final.\n\n" + _prompt_base(problema),
                     problema, "plan_tools_verify",
                     system="Sos un agente que usa herramientas y verifica.")
    costo += c
    llamados += 1
    pasos.append("verify")
    return {"respuesta": final.strip(),
            "traza": "plan_tools_verify: " + "→".join(pasos),
            "costo_usd": costo, "llamados": llamados}


RUNNERS = {
    "single": _run_single,
    "cot": _run_cot,
    "self_consistency": _run_self_consistency,
    "reflexion": _run_reflexion,
    "debate": _run_debate,
    "plan_tools_verify": _run_plan_tools_verify,
}


def ejecutar(arch_id, problema, backend):
    """Corre una arquitectura sobre un problema. Interfaz común del sistema."""
    if arch_id not in RUNNERS:
        raise KeyError(f"runner desconocido: {arch_id!r}")
    return RUNNERS[arch_id](problema, backend)
