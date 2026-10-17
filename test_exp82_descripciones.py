"""Tests EXP82 — réplica de EXP76 sobre descripciones de tools (C04).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_exp82_descripciones.py

Cubre: el pre-registro existe y es la única fuente de las descripciones;
la descripción vieja de cada tool es la REAL (primera línea del
docstring del módulo, vía AST); la tarjeta parsea y el implementador
solo ve la interfaz; los q recomputados coinciden con los declarados en
el pre-registro; la batería es determinista y pareada; y la puerta
decide por tool lo pre-registrado, con Δ reportados.
Cero gasto de API (mock determinista).
"""

import ast
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.handoff import (
    REGLA_HANDOFF, interfaz_de_skill, claridad_interfaz, probar_handoff)
from run_exp82 import tarjeta, correr_tool, SEED_DOWN, SEED_REF

BASE = os.path.dirname(os.path.abspath(__file__))
PREREG_PATH = os.path.join(BASE, "metaloop_preregistro_exp82.json")

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def primera_linea_docstring(modulo):
    ruta = os.path.join(BASE, "alma_service", modulo + ".py")
    with open(ruta, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    return ast.get_docstring(tree).split("\n")[0].strip()


def main():
    # 1. Pre-registro: existe, US$0, 3 tools, regla la de EXP76.
    check("pre-registro existe", os.path.exists(PREREG_PATH))
    with open(PREREG_PATH, encoding="utf-8") as f:
        prereg = json.load(f)
    check("pre-registro: costo US$0", prereg["costo_usd"] == 0.0)
    check("pre-registro: 3 tools", len(prereg["tools"]) == 3)
    check("regla es la de EXP76",
          REGLA_HANDOFF == "delta_down>0 & delta_ref>=0")

    for tool in prereg["tools"]:
        nombre = tool["nombre"]
        # 2. Procedencia: la descripción vieja es la real del código.
        check(f"{nombre}: descripción vieja == docstring real (AST)",
              tool["descripcion_vieja"] == primera_linea_docstring(nombre))

        # 3. La tarjeta parsea y la interfaz no filtra la interna.
        md_nueva = tarjeta(nombre, tool["descripcion_nueva"],
                           tool["firma"], tool["cuerpo"])
        itf = interfaz_de_skill(md_nueva)
        check(f"{nombre}: interfaz trae la descripción nueva exacta",
              itf["descripcion"] == tool["descripcion_nueva"])
        check(f"{nombre}: interfaz sin interna",
              "Interna" not in str(itf) and tool["cuerpo"] not in str(itf))

        # 4. Los q recomputados coinciden con los pre-registrados.
        itf_vieja = interfaz_de_skill(tarjeta(
            nombre, tool["descripcion_vieja"], tool["firma"],
            tool["cuerpo"]))
        check(f"{nombre}: q_vieja recomputada == declarada",
              claridad_interfaz(itf_vieja) == tool["q_vieja"])
        check(f"{nombre}: q_nueva recomputada == declarada",
              claridad_interfaz(itf) == tool["q_nueva"])
        check(f"{nombre}: q_nueva > q_vieja",
              tool["q_nueva"] > tool["q_vieja"])

        # 5. Determinismo y batería pareada.
        r1 = probar_handoff(itf, tool["ayuda"], tool["rigidez"],
                            seed_tareas_down=SEED_DOWN,
                            seed_tareas_ref=SEED_REF)
        r2 = probar_handoff(itf, tool["ayuda"], tool["rigidez"],
                            seed_tareas_down=SEED_DOWN,
                            seed_tareas_ref=SEED_REF)
        check(f"{nombre}: determinista con mismas semillas",
              r1["score_down_con"] == r2["score_down_con"]
              and r1["score_ref_con"] == r2["score_ref_con"])
        r_vieja = probar_handoff(itf_vieja, tool["ayuda"],
                                 tool["rigidez"],
                                 seed_tareas_down=SEED_DOWN,
                                 seed_tareas_ref=SEED_REF)
        check(f"{nombre}: baseline idéntico entre brazos",
              r_vieja["score_down_sin"] == r1["score_down_sin"]
              and r_vieja["score_ref_sin"] == r1["score_ref_sin"])

        # 6. Solo ve la interfaz: cambiar la interna no mueve nada.
        itf_alt = interfaz_de_skill(tarjeta(
            nombre, tool["descripcion_nueva"], tool["firma"],
            "Interna alternativa: implementación distinta, texto distinto."))
        r_alt = probar_handoff(itf_alt, tool["ayuda"], tool["rigidez"],
                               seed_tareas_down=SEED_DOWN,
                               seed_tareas_ref=SEED_REF)
        check(f"{nombre}: interna distinta -> scores idénticos",
              r_alt["score_down_con"] == r1["score_down_con"]
              and r_alt["score_ref_con"] == r1["score_ref_con"])

        # 7. La puerta decide lo pre-registrado, con números.
        res, dec, _rv, _rn = correr_tool(tool)
        esperada_adopta = tool["rama_esperada"] == "adopta_nueva"
        check(f"{nombre}: puerta decide la rama esperada",
              dec["aceptado"] is esperada_adopta and res["rama_ok"])
        if esperada_adopta:
            check(f"{nombre}: Δ_down>0 y Δ_ref>=0 al adoptar",
                  dec["delta_down"] > 0 and dec["delta_ref"] >= 0)
        check(f"{nombre}: Δ no empeora (Δ_down>=0)",
              dec["delta_down"] >= 0)

        # 8. Audit record con superficie de tool.
        rec = res["audit_record"]
        check(f"{nombre}: audit record tool/handoff",
              rec["tipo"] == "audit_handoff"
              and rec["superficie_editada"] == "tool:" + nombre
              and rec["regla"] == REGLA_HANDOFF
              and rec["delta_down"] == dec["delta_down"])

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
