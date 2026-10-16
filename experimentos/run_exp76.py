"""EXP76 — puerta de handoff para el meta-loop (LibraryDesignBench -> ALMA).

Corre: python3 run_exp76.py
Pre-registro obligatorio: metaloop_preregistro_exp76.json (fail-closed:
sin pre-registro no corre). Mock US$0, semillas fijas.

El experimento evalúa 4 skills mock calibradas contra la puerta de
handoff y reporta números honestos + veredicto PASS/FAIL según el
pre-registro.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.handoff import (
    REGLA_HANDOFF, PuertaHandoff, interfaz_de_skill,
    probar_handoff, audit_record_handoff)

BASE = os.path.dirname(os.path.abspath(__file__))
PREREG_PATH = os.path.join(BASE, "metaloop_preregistro_exp76.json")
OUT_DIR = os.path.join(BASE, "data_exp76")


def skill_md(nombre, descripcion, firma, cuerpo):
    return (f"---\nname: {nombre}\ndescription: {descripcion}\n"
            f"firma: {firma}\n---\n{cuerpo}\n")


SKILLS = [
    # (nombre, ayuda, rigidez, rama esperada según pre-registro)
    ("resume_claro", skill_md(
        "resume_claro",
        "Resume un texto en N frases. Ejemplo: resume_claro('texto', 3)"
        " -> ['f1', 'f2', 'f3'].",
        "(texto, n)",
        "Interna: partir en oraciones, rankear por similitud, top N."),
     0.55, 0.08, "adopta"),
    ("envuelve_rigido", skill_md(
        "envuelve_rigido",
        "Esta skill provee una envoltura genérica y comprehensiva para"
        " diversos tipos de transformaciones de contenido textual y"
        " estructurado considerando múltiples dimensiones de configuración"
        " opcional y extensible para casos de uso variados y heterogéneos.",
        "(a, b, c, d, e, f)",
        "Interna: llamar al transformador con seis parámetros en orden."),
     0.45, 0.55, "rechaza_peor_que_nada"),
    ("adorno", skill_md(
        "adorno",
        "Agrega un encabezado decorativo. Ejemplo: adorno('hola')"
        " -> '# hola'.",
        "(texto,)",
        "Interna: concatenar '# ' + texto."),
     0.0, 0.0, "rechaza_lateral"),
    ("motor_brillante", skill_md(
        "motor_brillante",
        "Motor de razonamiento avanzado con capacidades extendidas de"
        " planificación multi-paso y optimización de secuencias de acciones"
        " en entornos complejos con restricciones temporales variables.",
        "(estado, objetivo, horizonte, restricciones, pesos)",
        "Interna: A* con heurística admisible, poda alfa-beta,"
        " memoización agresiva."),
     0.8, 0.5, "rechaza_interfaz_manda"),
]


def main():
    if not os.path.exists(PREREG_PATH):
        print("FAIL: sin pre-registro no se corre "
              f"({PREREG_PATH} inexistente)")
        sys.exit(1)
    with open(PREREG_PATH, encoding="utf-8") as f:
        prereg = json.load(f)
    print(f"EXP76 :: pre-registro {PREREG_PATH} OK "
          f"(seed={prereg.get('seed')}, costo US${prereg.get('costo_usd')})")
    print(f"Regla: {REGLA_HANDOFF}\n")

    resultados = []
    for nombre, md, ayuda, rigidez, esperada in SKILLS:
        interfaz = interfaz_de_skill(md)
        res = probar_handoff(interfaz, ayuda, rigidez)
        dec = PuertaHandoff.decidir(
            res["score_down_sin"], res["score_down_con"],
            res["score_ref_sin"], res["score_ref_con"])
        record = audit_record_handoff(
            {"skill": nombre, "ayuda": ayuda, "rigidez": rigidez},
            dec["delta_down"], dec["delta_ref"], dec["aceptado"],
            dec["motivo"], superficie=f"skill:{nombre}",
            q_interfaz=res["detalle"]["q_interfaz"], scores=res)
        ok_rama = ((esperada == "adopta" and dec["aceptado"])
                   or (esperada.startswith("rechaza")
                       and not dec["aceptado"]))
        print(f"--- {nombre} (q={res['detalle']['q_interfaz']}, "
              f"ayuda={ayuda}, rigidez={rigidez})")
        print(f"    down: {res['score_down_sin']:.4f} -> "
              f"{res['score_down_con']:.4f} "
              f"(Δ={dec['delta_down']:+.4f})")
        print(f"    ref:  {res['score_ref_sin']:.4f} -> "
              f"{res['score_ref_con']:.4f} "
              f"(Δ={dec['delta_ref']:+.4f})")
        print(f"    puerta: {'ADOPTA' if dec['aceptado'] else 'RECHAZA'}"
              f" — {dec['motivo']}")
        print(f"    rama esperada '{esperada}': {'OK' if ok_rama else 'FALLA'}")
        resultados.append({"skill": nombre, "ayuda": ayuda,
                           "rigidez": rigidez,
                           "rama_esperada": esperada,
                           "rama_ok": bool(ok_rama),
                           "audit_record": record})

    # Propiedad "solo ve la interfaz": la interna no mueve los números.
    itf = interfaz_de_skill(SKILLS[0][1])
    alt = SKILLS[0][1].replace("rankear por similitud",
                               "criterio interno distinto y más largo")
    r_a = probar_handoff(itf, 0.55, 0.08)
    r_b = probar_handoff(interfaz_de_skill(alt), 0.55, 0.08)
    solo_interfaz = (r_a["score_down_con"] == r_b["score_down_con"]
                     and r_a["score_down_sin"] == r_b["score_down_sin"])
    print(f"\nsolo-ve-la-interfaz: {'OK' if solo_interfaz else 'FALLA'}")

    veredicto = (all(r["rama_ok"] for r in resultados) and solo_interfaz)
    print(f"\nEXP76: {'PASS' if veredicto else 'FAIL'} "
          f"({sum(r['rama_ok'] for r in resultados)}/{len(resultados)}"
          " ramas + interfaz)")

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "resultados_exp76.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "experimento": "exp76_puerta_handoff",
            "timestamp": time.time(),
            "preregistro": PREREG_PATH,
            "regla": REGLA_HANDOFF,
            "costo_usd": 0.0,
            "veredicto": "PASS" if veredicto else "FAIL",
            "solo_ve_la_interfaz": solo_interfaz,
            "resultados": resultados,
        }, f, indent=2, ensure_ascii=False)
    print(f"resultados en {out_path}")
    sys.exit(0 if veredicto else 1)


if __name__ == "__main__":
    main()
