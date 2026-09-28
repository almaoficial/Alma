"""Las 4 reglas ACI de SWE-agent (Yao et al. 2024) como checklist de herramientas.

Del informe §1.4: "los LM agents son una nueva categoría de end users" —
las interfaces se diseñan PARA EL MODELO, no para el humano. Las 4
decisiones de diseño (+10.7pp en SWE-bench Lite vs shell default):

1. Suprimir verbosidad: topes y resúmenes en las salidas.
2. Guardrails en edición: validar ANTES de escribir; lo inválido se
   descarta con motivo y el estado anterior nunca se corrompe (el mal
   estado nunca existe).
3. Feedback conciso y explícito en cada operación, incluso vacío
   ("sin resultados" en vez de silencio).
4. Curación activa del contexto: dropear errores viejos salvo el primero;
   colapsar observaciones antiguas a una línea.

Aplicación en este sistema (las "herramientas del harness" acá son las
operaciones del servicio: admisión de skills, versionado, revisión):
- Regla 1 → `resumir`: la evidencia adjunta en admisión se recorta.
- Regla 2 → `editar_con_guardrails`: el commit de admisión escribe el
  SKILL.md en tmp, lo valida (parsea), y recién ahí lo mueve atómico.
- Regla 3 → `resultado` / `sin_resultados`: convención de retorno de
  `evaluar` (politicas.py) y de estas utilidades.
- Regla 4 → `curar_contexto`: el paquete de evidencia del minero colapsa
  clusters viejos (debilidades.py).

Todo determinista, US$0, sin LLM.
"""

import os
import tempfile

# -- regla 1: suprimir verbosidad -------------------------------------------
MARCA_RECORTE = "…[recortado]"


def resumir(texto, tope=2000):
    """Recorta texto largo con marca explícita. Lo corto pasa intacto."""
    t = str(texto or "")
    if len(t) <= tope:
        return t
    return t[:tope] + f"{MARCA_RECORTE}({len(t)}→{tope})"


# -- regla 2: guardrails en edición ------------------------------------------
def editar_con_guardrails(path, nuevo_texto, validar, nombre_tmp=None):
    """Escribe nuevo_texto en path solo si pasa la validación.

    validar(tmp_path) -> (ok: bool, motivo: str): corre sobre el archivo
    ya escrito en tmp. Si falla, el original queda INTACTO y se retorna
    el motivo (el mal estado nunca existe). Escritura atómica vía rename.
    `nombre_tmp`: nombre del archivo temporal (p. ej. "SKILL.md" cuando
    el validador exige un nombre concreto).
    Retorna dict {ok, motivo, escrito}.
    """
    path = os.path.abspath(path)
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix=".alma_edit_", dir=d)
    tmp = os.path.join(tmpdir, nombre_tmp or "tmp")

    def _limpiar():
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
            os.rmdir(tmpdir)
        except OSError:
            pass

    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(nuevo_texto)
        ok, motivo = validar(tmp)
        if not ok:
            _limpiar()
            return {"ok": False, "motivo": motivo, "escrito": False,
                    "path": path}
        os.replace(tmp, path)  # atómico en el mismo filesystem
        _limpiar()
        return {"ok": True, "motivo": motivo or "validación ok",
                "escrito": True, "path": path}
    except Exception as e:  # noqa: BLE001 - el guardrail reporta, no rompe
        _limpiar()
        return {"ok": False, "motivo": f"excepción en edición: {e}"[:200],
                "escrito": False, "path": path}


# -- regla 3: feedback explícito ----------------------------------------------
def resultado(ok, resumen, **detalle):
    """Convención de retorno: siempre {ok, resumen, ...}. Incluso vacío."""
    r = {"ok": bool(ok), "resumen": str(resumen)}
    r.update(detalle)
    return r


def sin_resultados(que):
    """Feedback explícito cuando no hay nada: nunca silencio."""
    return resultado(True, f"sin {que}", n=0)


# -- regla 4: curación de contexto ----------------------------------------------
def curar_contexto(items, max_items=20):
    """items: [{"tipo": "error"|"obs", "texto": str}].

    - Errores: se conserva el PRIMERO (el más informativo), el resto se
      dropea (SWE-agent: "dropear todos los errores viejos salvo el
      primero").
    - Observaciones: se conservan hasta max_items; las más viejas se
      colapsan a una línea.
    Retorna la lista curada (puede incluir una entrada sintética de
    colapso con tipo "colapso").
    """
    items = list(items or [])
    errores = [it for it in items if it.get("tipo") == "error"]
    obs = [it for it in items if it.get("tipo") != "error"]
    out = []
    if errores:
        out.append(errores[0])
    if len(obs) > max_items:
        colapsadas = len(obs) - max_items
        out.append({"tipo": "colapso",
                    "texto": f"…[{colapsadas} observaciones antiguas"
                             f" colapsadas]"})
        out.extend(obs[-max_items:])
    else:
        out.extend(obs)
    return out
