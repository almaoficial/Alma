"""EXP82 — réplica de EXP76 sobre descripciones de TOOLS (C04, idea 3).

Corre: python3 run_exp82.py
Pre-registro obligatorio: metaloop_preregistro_exp82.json (fail-closed:
sin pre-registro no corre). Mock US$0, semillas fijas.

EXP76 midió que la interfaz de una SKILL manda sobre su interna
(Δ_down +0,3636 clara / -0,4145 rígida) con un implementador fresco que
solo ve nombre/descripción/firma. EXP82 aplica el MISMO protocolo a
descripciones de tools del prototipo: por cada tool, brazo base =
descripción VIEJA real (primera línea del docstring del módulo) y brazo
candidato = descripción NUEVA reescrita con la doctrina de claridad.
ayuda/rigidez (propiedades de la tool) constantes entre brazos: solo
cambia el texto de la interfaz. La puerta es la misma PuertaHandoff,
sin tocar handoff.py, gate.py ni metaloop.py.
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
PREREG_PATH = os.path.join(BASE, "metaloop_preregistro_exp82.json")
OUT_DIR = os.path.join(BASE, "data_exp82")

SEED_DOWN = 8201
SEED_REF = 8202


def tarjeta(nombre, descripcion, firma, cuerpo):
    """La tool como tarjeta de interfaz: mismo formato de frontmatter
    que una SKILL.md — es lo que interfaz_de_skill sabe extraer y lo
    único que el implementador ve (el cuerpo/interna se descarta)."""
    return (f"---\nname: {nombre}\ndescription: {descripcion}\n"
            f"firma: {firma}\n---\n{cuerpo}\n")


def correr_tool(tool):
    """Corre los dos brazos pareados de una tool y decide con la puerta.
    Retorna (resultado_dict, dec, res_vieja, res_nueva)."""
    md_vieja = tarjeta(tool["nombre"], tool["descripcion_vieja"],
                       tool["firma"], tool["cuerpo"])
    md_nueva = tarjeta(tool["nombre"], tool["descripcion_nueva"],
                       tool["firma"], tool["cuerpo"])
    itf_vieja = interfaz_de_skill(md_vieja)
    itf_nueva = interfaz_de_skill(md_nueva)
    ayuda, rigidez = tool["ayuda"], tool["rigidez"]
    res_vieja = probar_handoff(itf_vieja, ayuda, rigidez,
                               seed_tareas_down=SEED_DOWN,
                               seed_tareas_ref=SEED_REF)
    res_nueva = probar_handoff(itf_nueva, ayuda, rigidez,
                               seed_tareas_down=SEED_DOWN,
                               seed_tareas_ref=SEED_REF)
    # Chequeo de batería pareada: el baseline (sin tool) tiene que ser
    # idéntico en ambas llamadas — mismas tareas, mismas semillas.
    baseline_ok = (
        res_vieja["score_down_sin"] == res_nueva["score_down_sin"]
        and res_vieja["score_ref_sin"] == res_nueva["score_ref_sin"])
    dec = PuertaHandoff.decidir(
        res_vieja["score_down_con"], res_nueva["score_down_con"],
        res_vieja["score_ref_con"], res_nueva["score_ref_con"])
    record = audit_record_handoff(
        {"tool": tool["nombre"], "ayuda": ayuda, "rigidez": rigidez,
         "descripcion_vieja": tool["descripcion_vieja"],
         "descripcion_nueva": tool["descripcion_nueva"]},
        dec["delta_down"], dec["delta_ref"], dec["aceptado"],
        dec["motivo"], superficie="tool:" + tool["nombre"],
        q_interfaz=res_nueva["detalle"]["q_interfaz"],
        scores={"vieja": res_vieja, "nueva": res_nueva},
        seed={"down": SEED_DOWN, "ref": SEED_REF})
    esperada = tool["rama_esperada"]
    rama_ok = ((esperada == "adopta_nueva" and dec["aceptado"])
               or (esperada == "rechaza_nueva" and not dec["aceptado"]))
    resultado = {
        "tool": tool["nombre"], "ayuda": ayuda, "rigidez": rigidez,
        "q_vieja": res_vieja["detalle"]["q_interfaz"],
        "q_nueva": res_nueva["detalle"]["q_interfaz"],
        "q_vieja_declarada": tool["q_vieja"],
        "q_nueva_declarada": tool["q_nueva"],
        "delta_down": dec["delta_down"], "delta_ref": dec["delta_ref"],
        "aceptada_nueva": dec["aceptado"], "motivo": dec["motivo"],
        "rama_esperada": esperada, "rama_ok": bool(rama_ok),
        "baseline_pareado_ok": bool(baseline_ok),
        "audit_record": record}
    return resultado, dec, res_vieja, res_nueva


def main():
    if not os.path.exists(PREREG_PATH):
        print("FAIL: sin pre-registro no se corre "
              f"({PREREG_PATH} inexistente)")
        sys.exit(1)
    with open(PREREG_PATH, encoding="utf-8") as f:
        prereg = json.load(f)
    print(f"EXP82 :: pre-registro {PREREG_PATH} OK "
          f"(seed={prereg.get('seed')}, costo US${prereg.get('costo_usd')})")
    print(f"Regla: {REGLA_HANDOFF}\n")

    resultados = []
    for tool in prereg["tools"]:
        r, dec, res_vieja, res_nueva = correr_tool(tool)
        puerta_txt = ("ADOPTA descripción nueva" if dec["aceptado"]
                      else "RECHAZA descripción nueva")
        print(f"--- {tool['nombre']} (q: {r['q_vieja']} -> {r['q_nueva']}, "
              f"ayuda={tool['ayuda']}, rigidez={tool['rigidez']})")
        print(f"    down: {res_vieja['score_down_con']:.4f} -> "
              f"{res_nueva['score_down_con']:.4f} "
              f"(Δ={dec['delta_down']:+.4f})")
        print(f"    ref:  {res_vieja['score_ref_con']:.4f} -> "
              f"{res_nueva['score_ref_con']:.4f} "
              f"(Δ={dec['delta_ref']:+.4f})")
        print(f"    puerta: {puerta_txt} — {dec['motivo']}")
        print(f"    rama esperada '{r['rama_esperada']}': "
              f"{'OK' if r['rama_ok'] else 'FALLA'}; "
              f"baseline pareado: "
              f"{'OK' if r['baseline_pareado_ok'] else 'FALLA'}")
        resultados.append(r)

    # Propiedad "solo ve la interfaz": variar la interna de la tarjeta
    # nueva de la primera tool no mueve los números (espeja EXP76).
    t0 = prereg["tools"][0]
    itf_nueva = interfaz_de_skill(tarjeta(
        t0["nombre"], t0["descripcion_nueva"], t0["firma"], t0["cuerpo"]))
    itf_alt = interfaz_de_skill(tarjeta(
        t0["nombre"], t0["descripcion_nueva"], t0["firma"],
        "Interna completamente distinta: otra implementación, otro texto."))
    r_a = probar_handoff(itf_nueva, t0["ayuda"], t0["rigidez"],
                         seed_tareas_down=SEED_DOWN, seed_tareas_ref=SEED_REF)
    r_b = probar_handoff(itf_alt, t0["ayuda"], t0["rigidez"],
                         seed_tareas_down=SEED_DOWN, seed_tareas_ref=SEED_REF)
    solo_interfaz = (r_a["score_down_con"] == r_b["score_down_con"]
                     and r_a["score_ref_con"] == r_b["score_ref_con"])
    print(f"\nsolo-ve-la-interfaz: {'OK' if solo_interfaz else 'FALLA'}")

    adoptadas = sum(1 for r in resultados if r["aceptada_nueva"])
    ninguna_empeora = all(r["delta_down"] >= 0 for r in resultados)
    qs_ok = all(r["q_nueva"] > r["q_vieja"]
                and r["q_nueva"] == r["q_nueva_declarada"]
                and r["q_vieja"] == r["q_vieja_declarada"]
                for r in resultados)
    baselines_ok = all(r["baseline_pareado_ok"] for r in resultados)
    veredicto = (adoptadas >= 2 and ninguna_empeora and qs_ok
                 and baselines_ok and solo_interfaz)
    print(f"\nEXP82: {'PASS' if veredicto else 'FAIL'} "
          f"({adoptadas}/{len(resultados)} descripciones nuevas adoptadas, "
          f"ninguna empeora: {ninguna_empeora}, "
          f"q según lo declarado: {qs_ok})")

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "resultados_exp82.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "experimento": "exp82_descripciones_tools",
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
