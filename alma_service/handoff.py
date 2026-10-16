"""Puerta de handoff — EXP76 (inspirado en LibraryDesignBench, Snorkel AI,
paper del 29/9/2026).

Mide lo que el meta-loop hoy no mide: si una skill propuesta deja MEJOR
infraestructura para el agente que viene, no si "existe", "parsea" o
"pasa los checks estáticos".

Mecanismo (fiel al paper):
  diseñador      -> propone la skill (interfaz + interna)
  implementador  -> agente fresco que SOLO ve la interfaz
                    (nombre, descripción, firma del frontmatter),
                    nunca el cuerpo/interna; la usa en tareas reservadas
  score downstream con skill vs baseline sin skill en las mismas tareas
  (comparación pareada, mismas semillas)

Regla ("pero no peor" aplicada al handoff, espeja la gobernanza 27/9):

    Δ_down > 0  ∧  Δ_ref ≥ 0

donde Δ_down es la mejora del score downstream (mayor es mejor) y Δ_ref
la no-regresión en un split de referencia. Igual o peor NO se adopta:
se registra el rechazo con los números. El caso "peor que nada"
(Δ_down < 0: la skill resta) se rechaza explícito.

NÚCLEO PROTEGIDO: este módulo NO importa ni modifica gate.py (puerta de
dos splits), presupuesto.py ni el mecanismo de notificaciones de
promotor.py. Es una puerta ADICIONAL para propuestas de tipo skill; sus
deltas alimentan Promotor.auto_adoptar como evidencia, por el mismo
criterio "pero no peor" — el criterio de adopción no cambia, solo se
mide el handoff donde antes no se medía.

Mock (US$0): el implementador es determinista con semilla fija. El
modelo es un instrumento calibrado, no una simulación de LLMs: la
honestidad está en el diseño pareado, las semillas fijas y que el
implementador solo recibe la interfaz (test que lo prueba variando la
interna sin cambiar el resultado).
"""

import math
import os
import random
import tempfile

from .skills import cargar_skill, parse_frontmatter

REGLA_HANDOFF = "delta_down>0 & delta_ref>=0"

# Instrumento mock: tareas reservadas y splits. Fijos por diseño para
# que el experimento sea reproducible; el seed los baraja.
N_TAREAS_DOWN = 40
N_TAREAS_REF = 40
N_IMPLEMENTADORES = 3          # como los 3 implementadores del paper
LAMBDA_PASOS = 0.04            # peso del término de simplicidad
SEED_TAREAS_DOWN = 7601
SEED_TAREAS_REF = 7602
SEED_BASE_IMPLEMENTADORES = 7610


def _r(x):
    return round(float(x), 4) if x is not None else None


# -- interfaz: lo único que el implementador ve ---------------------------
def interfaz_de_skill(contenido_md):
    """Extrae del SKILL.md solo lo visible para el implementador: nombre,
    descripción y firma declarada en el frontmatter. El cuerpo (la
    "interna") se parsea para validar pero SE DESCARTA: el implementador
    nunca lo ve."""
    fm, _cuerpo = parse_frontmatter(contenido_md)
    # cargar_skill valida el formato real (nombre+descripción requeridos,
    # cuerpo no vacío). Si no parsea, la skill ni llega al handoff.
    tmpdir = tempfile.mkdtemp(prefix="alma_handoff_if_")
    tmp = os.path.join(tmpdir, "SKILL.md")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(contenido_md)
        meta = cargar_skill(tmp)
    finally:
        try:
            os.unlink(tmp)
            os.rmdir(tmpdir)
        except OSError:
            pass
    return {"nombre": meta.nombre,
            "descripcion": meta.descripcion,
            "firma": str(fm.get("firma", "")).strip()}


def claridad_interfaz(interfaz):
    """q en [0,1]: calidad de la interfaz, determinista y SOLO de lo
    visible (nombre/descripción/firma). Instrumento mock documentado:
    descripción con ejemplo concreto y firma simple -> alta; vaga o con
    muchos parámetros -> baja."""
    q = 0.50
    desc = (interfaz.get("descripcion") or "")
    dl = desc.lower()
    if "ejemplo:" in dl or "p. ej." in dl:
        q += 0.20
    firma = (interfaz.get("firma") or "").strip().strip("()")
    params = [p for p in firma.split(",") if p.strip()] if firma else []
    n = len(params)
    if n <= 2:
        q += 0.20
    elif n >= 5:
        q -= 0.20
    if 20 <= len(desc) <= 140:
        q += 0.10
    else:
        q -= 0.10
    return round(min(1.0, max(0.0, q)), 4)


# -- implementador mock (determinista, solo ve la interfaz) -----------------
def _tareas(n, seed):
    rng = random.Random(seed)
    return [rng.random() for _ in range(n)]  # dificultades en [0,1)


def _score_implementador(dificultades, q, ayuda, rigidez, seed):
    """Un implementador fresco resuelve las tareas. Sin skill equivale a
    q=0, ayuda=0, rigidez=0 (el baseline se recupera exacto).

    Modelo (instrumento, no simulación de LLM):
      p_éxito = p0 + ayuda*q - rigidez*(1-q)
      pasos   = pasos0*(1 - 0.25*ayuda*q) + 3*rigidez*(1-q)
    Con interfaz clara (q->1) la ayuda llega y la rigidez no muerde;
    con interfaz rígida/confusa (q->0) la ayuda no aterriza y la rigidez
    suma reimplementación y pasos extra — el hallazgo del paper: los
    implementadores subusan la librería y reescriben lo que ya existe.
    Score por tarea = éxito - LAMBDA_PASOS*pasos (compuesto estilo
    LibraryDesignBench: correctitud + simplicidad).
    """
    rng = random.Random(seed)
    scores = []
    for d in dificultades:
        p0 = min(0.97, max(0.05, 0.92 - 0.75 * d))
        pasos0 = 3.0 + 5.0 * d
        p = min(0.99, max(0.02, p0 + ayuda * q - rigidez * (1.0 - q)))
        pasos = pasos0 * (1.0 - 0.25 * ayuda * q) + 3.0 * rigidez * (1.0 - q)
        exito = 1.0 if rng.random() < p else 0.0
        scores.append(exito - LAMBDA_PASOS * pasos)
    return scores


def probar_handoff(interfaz, ayuda, rigidez, seed_tareas_down=SEED_TAREAS_DOWN,
                   seed_tareas_ref=SEED_TAREAS_REF,
                   n_implementadores=N_IMPLEMENTADORES):
    """Corre el test de handoff en mock.

    interfaz: dict de interfaz_de_skill (lo único visible).
    ayuda/rigidez: propiedades reales de la skill tal como se
        experimentan en uso (la ayuda solo actúa a través de la
        interfaz: ayuda*q). La "interna" (cuerpo del SKILL.md) no entra
        por ningún lado: por construcción el implementador no la ve.

    Retorna scores medios con/sin skill en downstream y referencia,
    más el detalle por implementador. Comparación pareada: mismos
    seeds en ambos brazos.
    """
    q = claridad_interfaz(interfaz)
    tareas_down = _tareas(N_TAREAS_DOWN, seed_tareas_down)
    tareas_ref = _tareas(N_TAREAS_REF, seed_tareas_ref)
    det = {"q_interfaz": q, "implementadores": []}
    sum_down_con = sum_down_sin = 0.0
    sum_ref_con = sum_ref_sin = 0.0
    for k in range(n_implementadores):
        s = SEED_BASE_IMPLEMENTADORES + k
        sc_down_con = _score_implementador(tareas_down, q, ayuda, rigidez, s)
        sc_down_sin = _score_implementador(tareas_down, 0.0, 0.0, 0.0, s)
        sc_ref_con = _score_implementador(tareas_ref, q, ayuda, rigidez, s)
        sc_ref_sin = _score_implementador(tareas_ref, 0.0, 0.0, 0.0, s)
        m_down_con = sum(sc_down_con) / len(sc_down_con)
        m_down_sin = sum(sc_down_sin) / len(sc_down_sin)
        m_ref_con = sum(sc_ref_con) / len(sc_ref_con)
        m_ref_sin = sum(sc_ref_sin) / len(sc_ref_sin)
        sum_down_con += m_down_con
        sum_down_sin += m_down_sin
        sum_ref_con += m_ref_con
        sum_ref_sin += m_ref_sin
        det["implementadores"].append({
            "k": k,
            "down_con": _r(m_down_con), "down_sin": _r(m_down_sin),
            "ref_con": _r(m_ref_con), "ref_sin": _r(m_ref_sin)})
    n = float(n_implementadores)
    return {
        "score_down_con": _r(sum_down_con / n),
        "score_down_sin": _r(sum_down_sin / n),
        "score_ref_con": _r(sum_ref_con / n),
        "score_ref_sin": _r(sum_ref_sin / n),
        "detalle": det,
    }


# -- la puerta ---------------------------------------------------------------
class PuertaHandoff:
    """La puerta como objeto (espeja PuertaDosSplits de gate.py, sin
    tocarlo). No evalúa nada: recibe los scores que probar_handoff ya
    produjo. Pura, determinista, sin LLM."""

    REGLA = REGLA_HANDOFF

    @staticmethod
    def decidir(score_down_base, score_down_cand,
                 score_ref_base=None, score_ref_cand=None):
        """Decide con scores downstream (mayor es mejor).

        Δ_down = cand - base (mejora del handoff).
        Δ_ref  = cand - base en el split de referencia (no-regresión);
                 si no se pasa, se asume 0.0 (no medido = no regresa,
                 documentado en el motivo).
        """
        d_down = float(score_down_cand) - float(score_down_base)
        if score_ref_base is None or score_ref_cand is None:
            d_ref = 0.0
            ref_nota = " (ref no medido)"
        else:
            d_ref = float(score_ref_cand) - float(score_ref_base)
            ref_nota = ""
        if d_down <= 0:
            if d_down < 0:
                motivo = (f"peor que nada: la skill RESTA en downstream"
                          f" (Δ_down={d_down:.4f})")
            else:
                motivo = (f"sin mejora estricta en downstream"
                          f" (Δ_down={d_down:.4f})")
            return {"aceptado": False, "motivo": motivo + ref_nota,
                    "delta_down": round(d_down, 4),
                    "delta_ref": round(d_ref, 4), "regla": REGLA_HANDOFF}
        if d_ref < 0:
            return {"aceptado": False,
                    "motivo": (f"regresión en referencia:"
                               f" Δ_ref={d_ref:.4f}{ref_nota}"),
                    "delta_down": round(d_down, 4),
                    "delta_ref": round(d_ref, 4), "regla": REGLA_HANDOFF}
        return {"aceptado": True,
                "motivo": (f"handoff mejora: Δ_down={d_down:.4f},"
                           f" Δ_ref={d_ref:.4f}{ref_nota}"),
                "delta_down": round(d_down, 4),
                "delta_ref": round(d_ref, 4), "regla": REGLA_HANDOFF}


def audit_record_handoff(propuesta, delta_down, delta_ref, aceptado, motivo,
                         superficie=None, q_interfaz=None,
                         scores=None, seed=None):
    """Audit record del handoff (espeja gate.audit_record): qué skill se
    propuso, qué midió el implementador fresco, qué decidió la puerta y
    por qué. Para el ledger / evidencia de auto_adoptar."""
    return {
        "tipo": "audit_handoff",
        "propuesta": propuesta,
        "superficie_editada": superficie,
        "q_interfaz": q_interfaz,
        "delta_down": _r(delta_down),
        "delta_ref": _r(delta_ref),
        "regla": REGLA_HANDOFF,
        "aceptado": bool(aceptado),
        "motivo": motivo,
        "scores": scores or {},
        "seed_tareas": seed,
    }


def evaluar_skill_para_adopcion(nombre, contenido_md, ayuda, rigidez,
                                adoptar_fn=None, seed_down=SEED_TAREAS_DOWN,
                                seed_ref=SEED_TAREAS_REF):
    """Pipeline completo de la puerta para una skill propuesta.

    1. Extrae la interfaz (lo único que el implementador ve).
    2. Corre el handoff en mock (implementadores frescos, tareas
       reservadas, comparación pareada).
    3. Decide con PuertaHandoff.
    4. Si acepta y hay adoptar_fn, la invoca con los deltas y la
       evidencia (en el servicio: un parcial a
       Promotor.auto_adoptar con delta_in=Δ_ref, delta_ho=Δ_down).
       Si rechaza, adoptar_fn NO se invoca: el rechazo trae números.

    La "interna" (cuerpo del SKILL.md) nunca llega al implementador:
    solo se usa para validar el formato vía interfaz_de_skill.

    Retorna el veredicto + evidencia lista para auditar.
    """
    interfaz = interfaz_de_skill(contenido_md)
    res = probar_handoff(interfaz, ayuda, rigidez,
                         seed_tareas_down=seed_down,
                         seed_tareas_ref=seed_ref)
    dec = PuertaHandoff.decidir(res["score_down_sin"], res["score_down_con"],
                                res["score_ref_sin"], res["score_ref_con"])
    propuesta = {"skill": nombre, "interfaz": interfaz,
                 "ayuda": ayuda, "rigidez": rigidez}
    record = audit_record_handoff(
        propuesta, dec["delta_down"], dec["delta_ref"], dec["aceptado"],
        dec["motivo"], superficie=f"skill:{nombre}",
        q_interfaz=res["detalle"]["q_interfaz"], scores=res,
        seed={"down": seed_down, "ref": seed_ref})
    evidencia = {"handoff": record, "origen": "exp76_puerta_handoff"}
    adoptada = False
    adopcion = None
    if dec["aceptado"] and adoptar_fn is not None:
        adopcion = adoptar_fn(
            {"delta_in": dec["delta_ref"], "delta_ho": dec["delta_down"]},
            evidencia)
        adoptada = bool(adopcion and adopcion.get("adoptada"))
    return {"skill": nombre, "aceptada": dec["aceptado"],
            "adoptada_via_fn": adoptada, "adopcion": adopcion,
            "delta_down": dec["delta_down"], "delta_ref": dec["delta_ref"],
            "motivo": dec["motivo"], "regla": REGLA_HANDOFF,
            "evidencia": evidencia}
