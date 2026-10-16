"""Cableado Forge -> servicio en vivo (EXP78).

Aprobado por el usuario el 1/10/2026: los 4 patrones Forge dejan de ser
infraestructura suelta y se conectan al flujo real del servicio.

Todo acá es ADITIVO y fail-safe:
- handoff.py, gate.py, presupuesto.py y promotor.py NO se tocan.
- Si el cableado falla (traza malformada, DB no disponible), el
  veredicto de la puerta sigue intacto: el error se registra en el
  resultado bajo "cableado" y nunca se propaga.

1. evaluar_skill_para_adopcion_con_traza(): wrapper de
   handoff.evaluar_skill_para_adopcion que, tras el veredicto,
   - emite la traza unificada (esquema_traza.desde_handoff),
   - archiva el fallo en BibliotecaFallos si fue rechazo,
   - asienta lineage vía asentar_con_linaje si fue aceptada+adoptada.
   Es el entrypoint canónico para futuras propuestas del loop: la
   puerta de handoff espera su primer llamador real, y este wrapper es
   ese llamador con instrumentación (la decisión de la puerta no
   cambia: el wrapper solo observa y registra).

2. correr_torneo_semanal(): campeón (metaloop.scaffold_vigente) vs
   candidatas acumuladas (promoción en staging del promotor), con el
   validador congelado. Pensado para el cron semanal; también expuesto
   como POST /fase2/torneo/semanal en servicio/server.py. Emite traza
   unificada de origen "torneo" con el resultado.

Mock-first US$0: nada acá gasta ni llama a modelos. Las DBs default
son las del servicio en vivo; en tests se pasan rutas de /tmp.
"""

import os

from alma_service import handoff as _handoff
from alma_service.handoff import (
    evaluar_skill_para_adopcion,
    SEED_TAREAS_DOWN,
    SEED_TAREAS_REF,
)
from alma_service.esquema_traza import (
    TraceLog,
    desde_handoff,
    nueva_traza,
)
from alma_service.casos_fallo import BibliotecaFallos
from alma_service.torneo import Torneo
from alma_service.versiones import (
    VersionadorSkills,
    TIPO_CAPTURED,
    linaje_desde_handoff,
)

_DIR = os.path.expanduser("~/workspace/alma-prototype")
DB_TRACES_DEF = os.path.join(_DIR, "alma_traces.db")
DB_FALLOS_DEF = os.path.join(_DIR, "alma_casos_fallo.db")
DB_TORNEO_DEF = os.path.join(_DIR, "alma_torneo.db")
DB_VERSIONES_DEF = os.path.join(_DIR, "skills-versiones.db")


def _cableado_vacio():
    return {"traza_emitida": False, "fallo_archivado": False,
            "lineage_asentado": False, "errores": []}


def evaluar_skill_para_adopcion_con_traza(
        nombre, contenido_md, ayuda, rigidez,
        adoptar_fn=None, seed_down=None, seed_ref=None,
        tracelog=None, biblioteca=None, registro=None,
        skill_path=None, entorno="mock"):
    """Puerta de handoff + instrumentación Forge (EXP78).

    Misma firma y misma decisión que
    handoff.evaluar_skill_para_adopcion (no se toca): el cableado solo
    observa y registra, en este orden:

    1. Se evalúa la skill (veredicto intacto, venga de donde venga).
    2. Se emite la traza unificada de la corrida (origen=handoff).
    3. Si fue RECHAZO: se archiva en la BibliotecaFallos (regresión).
    4. Si fue ACEPTADA y adoptada vía adoptar_fn: se asienta la versión
       con lineage (split que la validó, Δ, regla).

    tracelog/biblioteca/registro: instancias o None (None = ese paso se
    saltea; útil en tests o cuando el servicio corre sin ese módulo).
    Cada paso es best-effort: un fallo se anota en
    resultado["cableado"]["errores"] sin alterar el veredicto.
    """
    cableado = _cableado_vacio()
    veredicto = evaluar_skill_para_adopcion(
        nombre, contenido_md, ayuda, rigidez,
        adoptar_fn=adoptar_fn,
        seed_down=(SEED_TAREAS_DOWN if seed_down is None else seed_down),
        seed_ref=(SEED_TAREAS_REF if seed_ref is None else seed_ref))
    rec = (veredicto.get("evidencia") or {}).get("handoff") or {}

    # 1. traza unificada de la corrida
    if tracelog is not None:
        try:
            tid = tracelog.emitir(desde_handoff(rec, entorno=entorno))
            cableado["traza_emitida"] = tid
        except Exception as e:  # noqa: BLE001 - fail-safe
            cableado["errores"].append(f"traza: {e!r}"[:200])

    # 2. rechazo -> biblioteca de fallos (regresión futura)
    if not veredicto.get("aceptada") and biblioteca is not None:
        try:
            fid = biblioteca.archivar_fallo(veredicto)
            cableado["fallo_archivado"] = fid
        except Exception as e:  # noqa: BLE001 - fail-safe
            cableado["errores"].append(f"biblioteca: {e!r}"[:200])

    # 3. aceptada + adoptada -> versión con lineage
    if (veredicto.get("aceptada") and veredicto.get("adoptada_via_fn")
            and registro is not None):
        try:
            sp = skill_path or f"skills/{nombre}.md"
            asent = registro.asentar_con_linaje(
                sp, TIPO_CAPTURED, None,
                "skill aceptada por la puerta de handoff (EXP76)",
                {"handoff": rec},
                linaje_desde_handoff(veredicto))
            cableado["lineage_asentado"] = {
                "skill_path": asent["skill_path"],
                "version": asent["version"]}
        except Exception as e:  # noqa: BLE001 - fail-safe
            cableado["errores"].append(f"lineage: {e!r}"[:200])

    veredicto["cableado"] = cableado
    return veredicto


def _candidatas_desde_staging(promotor, campeon):
    """Candidatas acumuladas: la promoción en staging del promotor
    (una línea de evolución por vez, por diseño)."""
    cands = []
    try:
        pend = promotor.pendiente()
    except Exception:  # noqa: BLE001 - fail-safe
        return cands
    if not pend:
        return cands
    sc = pend.get("scaffold_despues")
    if isinstance(sc, dict) and sc != campeon:
        cands.append((f"staging-{pend.get('id')}", sc))
    return cands


def correr_torneo_semanal(metaloop, promotor=None, torneo=None,
                          tracelog=None, bloqueante=True,
                          entorno="mock"):
    """Torneo semanal: campeón vs candidatas acumuladas (EXP78 #3).

    - Campeón: metaloop.scaffold_vigente().
    - Candidatas: promoción en staging del promotor (si hay).
    - Validador congelado (torneo.py); no redefine qué es mejora.
    - bloqueante=False: corre en background (para el endpoint HTTP).

    Retorna dict con el resumen. Si no hay campeón o no hay
    candidatas, no corre y lo dice (no es un error: el torneo espera).
    Emite traza unificada origen="torneo" cuando corre en modo
    bloqueante (en background la traza la emite el hilo al terminar).
    """
    resultado = {"corrio": False}
    try:
        campeon = metaloop.scaffold_vigente()
    except Exception as e:  # noqa: BLE001
        resultado["motivo"] = f"no se pudo leer el campeón: {e!r}"[:200]
        return resultado
    if not isinstance(campeon, dict):
        resultado["motivo"] = "sin scaffold vigente"
        return resultado

    prom = promotor if promotor is not None else getattr(
        metaloop, "promotor", None)
    candidatas = _candidatas_desde_staging(prom, campeon) if prom else []
    if not candidatas:
        resultado["motivo"] = "sin candidatas en staging"
        return resultado

    tor = torneo if torneo is not None else Torneo()

    def _emitir_traza(resultados):
        if tracelog is None or not resultados:
            return None
        mejor = max((r.get("mejora", 0.0) for r in resultados),
                    default=0.0)
        trace = nueva_traza(
            origen="torneo",
            propuesta={"id": "torneo-semanal",
                       "descripcion": "campeón vs candidatas"
                                      " (validador congelado)",
                       "tipo": "scaffold"},
            split={"nombre": "e56-validador-congelado", "seed": None},
            metricas={"mejora_max": float(mejor),
                      "n_candidatas": float(len(candidatas))},
            veredicto={"decision": ("aceptado" if mejor > 0
                                    else "rechazado"),
                       "motivo": f"mejor mejora={mejor:.2f}",
                       "regla": ("mejora = reg_campeon - reg_candidata"
                                 " > 0")},
            lineage={"producido_por": "correr_torneo_semanal",
                     "version": 1, "padre": None},
            entorno=entorno, costo_usd=0.0)
        return tracelog.emitir(trace)

    if bloqueante:
        corrida = tor.correr(campeon, candidatas, bloqueante=True)
        resultado.update({"corrio": True,
                          "candidatas": [n for n, _ in candidatas],
                          "resultados": corrida["resultados"]})
        try:
            tid = _emitir_traza(corrida["resultados"])
            if tid is not None:
                resultado["traza_id"] = tid
        except Exception as e:  # noqa: BLE001 - fail-safe
            resultado["traza_error"] = f"{e!r}"[:200]
        return resultado

    # background: el hilo emite la traza al terminar
    def _bg():
        res = tor.correr(campeon, candidatas, bloqueante=True)
        try:
            _emitir_traza(res["resultados"])
        except Exception:  # noqa: BLE001 - fail-safe
            pass

    import threading
    threading.Thread(target=_bg, daemon=True).start()
    return {"corrio": True, "modo": "background",
            "candidatas": [n for n, _ in candidatas]}
