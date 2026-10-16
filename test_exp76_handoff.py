"""Tests EXP76 — puerta de handoff (LibraryDesignBench -> ALMA).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_exp76_handoff.py

Cubre: la puerta decide por el handoff medido (no por la existencia de
la skill), el implementador solo ve la interfaz, el caso "peor que
nada" se rechaza con números, y la integración con Promotor.auto_adoptar
adopta solo ante mejora medida sin tocar el núcleo protegido.
Cero gasto de API (mock determinista).
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.handoff import (
    REGLA_HANDOFF, PuertaHandoff, interfaz_de_skill, claridad_interfaz,
    probar_handoff, audit_record_handoff, evaluar_skill_para_adopcion)
from alma_service.promotor import Promotor
from alma_service.presupuesto import PresupuestoFase2, BUCKET_METALOOP

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def skill_md(nombre, descripcion, firma, cuerpo):
    return (f"---\nname: {nombre}\ndescription: {descripcion}\n"
            f"firma: {firma}\n---\n{cuerpo}\n")


BUENA_MD = skill_md(
    "resume_claro",
    "Resume un texto en N frases. Ejemplo: resume_claro('texto', 3)"
    " -> ['f1', 'f2', 'f3'].",
    "(texto, n)",
    "Interna: partir en oraciones, rankear por similitud, top N.")
MALA_MD = skill_md(
    "envuelve_rigido",
    "Esta skill provee una envoltura genérica y comprehensiva para"
    " diversos tipos de transformaciones de contenido textual y"
    " estructurado considerando múltiples dimensiones de configuración"
    " opcional y extensible para casos de uso variados y heterogéneos.",
    "(a, b, c, d, e, f)",
    "Interna: llamar al transformador con seis parámetros en orden.")
LATERAL_MD = skill_md(
    "adorno",
    "Agrega un encabezado decorativo. Ejemplo: adorno('hola')"
    " -> '# hola'.",
    "(texto,)",
    "Interna: concatenar '# ' + texto.")
BRILLANTE_MD = skill_md(
    "motor_brillante",
    "Motor de razonamiento avanzado con capacidades extendidas de"
    " planificación multi-paso y optimización de secuencias de acciones"
    " en entornos complejos con restricciones temporales variables.",
    "(estado, objetivo, horizonte, restricciones, pesos)",
    "Interna: A* con heurística admisible, poda alfa-beta,"
    " memoización agresiva.")


def _promotor_temp(aplicados):
    d = tempfile.mkdtemp(prefix="alma_exp76_p_")
    aplicados_lista = aplicados
    prom = Promotor(
        os.path.join(d, "p.db"),
        aplicar_fn=lambda sc, origen="": aplicados_lista.append(
            (dict(sc), origen)),
        ledger_fn=lambda e: "hash",
        revertir_fn=lambda sc, origen="": aplicados_lista.append(
            (dict(sc), "REVERT:" + origen)))
    return prom


def main():
    # 1. La regla está declarada y es la esperada.
    check("regla declarada", REGLA_HANDOFF == "delta_down>0 & delta_ref>=0")
    check("puerta expone la regla", PuertaHandoff.REGLA == REGLA_HANDOFF)

    # 2. La puerta decide por números, no por existencia.
    d = PuertaHandoff.decidir(0.50, 0.86, 0.50, 0.88)
    check("mejora downstream -> acepta",
          d["aceptado"] is True and d["delta_down"] == 0.36)
    d = PuertaHandoff.decidir(0.50, 0.50, 0.50, 0.50)
    check("igual (Δ=0) -> rechaza", d["aceptado"] is False)
    d = PuertaHandoff.decidir(0.86, 0.45, 0.88, 0.44)
    check("peor que nada -> rechaza",
          d["aceptado"] is False and "peor que nada" in d["motivo"]
          and d["delta_down"] < 0)
    d = PuertaHandoff.decidir(0.50, 0.60, 0.88, 0.80)
    check("regresión en referencia -> rechaza",
          d["aceptado"] is False and "referencia" in d["motivo"])
    d = PuertaHandoff.decidir(0.50, 0.60)
    check("sin ref: no-regresión asumida y documentada",
          d["aceptado"] is True and "no medido" in d["motivo"])

    # 3. La interfaz es solo lo visible; el cuerpo no llega al
    #    implementador.
    itf = interfaz_de_skill(BUENA_MD)
    check("interfaz: nombre", itf["nombre"] == "resume_claro")
    check("interfaz: firma", itf["firma"] == "(texto, n)")
    check("interfaz: sin cuerpo",
          "rankear" not in str(itf) and "Interna" not in str(itf))
    check("claridad determinista",
          claridad_interfaz(itf) == claridad_interfaz(itf))
    check("interfaz clara > rígida",
          claridad_interfaz(interfaz_de_skill(BUENA_MD))
          > claridad_interfaz(interfaz_de_skill(MALA_MD)))

    # 4. El handoff es determinista y pareado.
    r1 = probar_handoff(itf, 0.55, 0.08)
    r2 = probar_handoff(itf, 0.55, 0.08)
    check("determinista con misma seed",
          r1["score_down_con"] == r2["score_down_con"])
    check("baseline pareado usa mismas semillas",
          r1["score_down_sin"] == r2["score_down_sin"])
    check("detalle por implementador (3)",
          len(r1["detalle"]["implementadores"]) == 3)

    # 5. EL implementador solo ve la interfaz: cambiar la interna no
    #    cambia nada.
    buena_alt = BUENA_MD.replace(
        "rankear por similitud",
        "ordenar por un criterio interno completamente distinto")
    ra = probar_handoff(interfaz_de_skill(BUENA_MD), 0.55, 0.08)
    rb = probar_handoff(interfaz_de_skill(buena_alt), 0.55, 0.08)
    check("interna distinta -> scores idénticos",
          ra["score_down_con"] == rb["score_down_con"]
          and ra["score_down_sin"] == rb["score_down_sin"])

    # 6. Los cuatro casos del experimento.
    casos = [
        ("buena", BUENA_MD, 0.55, 0.08, True),
        ("mala", MALA_MD, 0.45, 0.55, False),
        ("lateral", LATERAL_MD, 0.0, 0.0, False),
        ("brillante_mala_if", BRILLANTE_MD, 0.8, 0.5, False),
    ]
    for nombre, md, ayuda, rigidez, espera in casos:
        res = probar_handoff(interfaz_de_skill(md), ayuda, rigidez)
        dec = PuertaHandoff.decidir(
            res["score_down_sin"], res["score_down_con"],
            res["score_ref_sin"], res["score_ref_con"])
        check(f"caso {nombre}: puerta decide lo esperado",
              dec["aceptado"] is espera)
    # El lateral es exactamente cero (skill que existe pero no hace
    # nada: el bloat hecho número).
    res_lat = probar_handoff(interfaz_de_skill(LATERAL_MD), 0.0, 0.0)
    dec_lat = PuertaHandoff.decidir(
        res_lat["score_down_sin"], res_lat["score_down_con"])
    check("lateral: Δ_down == 0.0000 exacto",
          dec_lat["delta_down"] == 0.0 and dec_lat["aceptado"] is False)

    # 7. Integración: la buena se auto-adopta por el camino gobernado;
    #    la mala ni llega a auto_adoptar.
    aplicados = []
    prom = _promotor_temp(aplicados)
    d_tmp = tempfile.mkdtemp(prefix="alma_exp76_pre_")
    pres = PresupuestoFase2(os.path.join(d_tmp, "pres.db"),
                            tope_mensual_usd=0.0)
    antes = {"skills": ["base"]}
    despues = {"skills": ["base"], "skill:resume_claro": "propuesta"}

    def adoptar_via_promotor(deltas, evidencia):
        return prom.auto_adoptar(
            scaffold_antes=antes, scaffold_despues=despues,
            delta_in=deltas["delta_in"], delta_ho=deltas["delta_ho"],
            motivo_puerta="puerta de handoff: " + evidencia["handoff"]["motivo"],
            regla=REGLA_HANDOFF, evidencia=evidencia,
            claves_permitidas={"skills", "skill:resume_claro"},
            costo_usd=0.0, presupuesto=pres, bucket=BUCKET_METALOOP)

    v_buena = evaluar_skill_para_adopcion(
        "resume_claro", BUENA_MD, 0.55, 0.08,
        adoptar_fn=adoptar_via_promotor)
    check("buena: puerta acepta", v_buena["aceptada"] is True)
    check("buena: auto-adoptada por el camino gobernado",
          v_buena["adoptada_via_fn"] is True and len(aplicados) == 1
          and aplicados[0][0] == despues)
    check("buena: notificación encolada",
          any(n["tipo"] == "auto_adopcion"
              for n in prom.notificaciones_pendientes()))
    check("buena: evidencia trae audit_handoff",
          v_buena["evidencia"]["handoff"]["tipo"] == "audit_handoff")

    aplicados_m = []
    prom_m = _promotor_temp(aplicados_m)
    llamadas = []

    def adoptar_no_deberia(deltas, evidencia):
        llamadas.append((deltas, evidencia))
        return {"adoptada": True}

    v_mala = evaluar_skill_para_adopcion(
        "envuelve_rigido", MALA_MD, 0.45, 0.55,
        adoptar_fn=adoptar_no_deberia)
    check("mala: puerta rechaza", v_mala["aceptada"] is False)
    check("mala: adoptar_fn ni se invoca",
          llamadas == [] and aplicados_m == [])
    check("mala: motivo 'peor que nada' con números",
          "peor que nada" in v_mala["motivo"]
          and f"{v_mala['delta_down']:.4f}" in v_mala["motivo"])
    check("mala: ni llega al promotor (cero registros)",
          prom_m.adopciones_recientes() == [])

    # 8. audit_record_handoff: espeja gate.audit_record.
    rec = audit_record_handoff({"skill": "x"}, 0.36, 0.38, True, "ok",
                               superficie="skill:x", q_interfaz=1.0)
    check("audit record trae tipo/regla/deltas",
          rec["tipo"] == "audit_handoff" and rec["regla"] == REGLA_HANDOFF
          and rec["delta_down"] == 0.36)

    # 9. Sin adoptar_fn: la puerta decide igual, no adopta en el vacío.
    v = evaluar_skill_para_adopcion("adorno", LATERAL_MD, 0.0, 0.0)
    check("sin adoptar_fn: veredicto sin commit",
          v["aceptada"] is False and v["adoptada_via_fn"] is False
          and v["adopcion"] is None)

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
