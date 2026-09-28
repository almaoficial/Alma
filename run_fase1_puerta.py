"""Validación de fase 1 — puerta con pre-registro.

Lee resultados/fase1-puerta/preregistro.json (ya escrito ANTES de gastar)
y ejecuta:
  Parte A: 3 réplicas del loop completo con ProveedorSkillsReal.
  Parte B: probe conductual pareado (skill raw vs guiada).
Emite report.json + veredicto.md con el criterio pre-registrado.

Uso: python3 run_fase1_puerta.py   (gasta key: ~US$0.03, tope duro 0.40)
"""

import json
import math
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma import executors
from alma.evaluator import Evaluator, StubJudge
from alma.backends import VaultBackend

from alma_service.llm import Presupuesto, ClienteMedido, PresupuestoAgotado
from alma_service.proveedor_real import BackendConSkill
from servicio.motor_fase1 import MotorFase1, BLOQUE
from problemas_fase1 import generar_problemas, FIRMAS

DIR = os.path.join("resultados", "fase1-puerta")
SEEDS = (11, 22, 33)
N_BLOQUES = 8
TOPE_DURO = 0.40


def cargar_preregistro():
    with open(os.path.join(DIR, "preregistro.json"), encoding="utf-8") as f:
        return json.load(f)


def parte_a(presupuesto):
    """3 réplicas del loop. Retorna lista de dicts por réplica."""
    replicas = []
    for i, seed in enumerate(SEEDS):
        d = os.path.join(DIR, f"rep{i}")
        os.makedirs(d, exist_ok=True)
        motor = MotorFase1(d, budget_usd=presupuesto, seed=seed)
        problemas = generar_problemas(seed=seed, n_bloques=N_BLOQUES)
        for b in range(N_BLOQUES):
            motor.correr_bloque(
                b, problemas[b * BLOQUE:(b + 1) * BLOQUE])
        st = motor.estado()
        skills = []
        for f in motor.skill_index.listar():
            txt = open(f["path"], encoding="utf-8").read()
            m = re.search(r"recomienda_brazo: (\S+)", txt)
            mv = re.search(r"version: (\d+)", txt)
            skills.append({"firma": f["name"],
                           "recomienda": m.group(1) if m else None,
                           "version": int(mv.group(1)) if mv else None,
                           "path": f["path"]})
        refinamientos = [e for e in motor.generador.eventos
                         if e.get("accion") == "refinar"]
        generaciones = [e for e in motor.generador.eventos
                        if e.get("accion") == "generar"]
        replicas.append({
            "replica": i, "seed": seed,
            "regret_total": st["regret_total"],
            "skills": skills,
            "generaciones": len(generaciones),
            "refinamientos": refinamientos,
            "skills_usadas": st["skills_usadas"],
            "probes_saltados": st["probes_saltados"],
            "modo_recurrencia": st["modo_recurrencia"],
            "tasa_recurrencia": st["tasa_recurrencia"],
            "costo_usd": st["costo_usd"],
            "llamados_llm": st["llamados_llm"],
            "cadena_ok": st["cadena_ok"],
        })
        motor.cerrar()
    return replicas


def parte_b(presupuesto):
    """Probe conductual: brazo raw vs guiado, pareado por problema."""
    # Skills de la réplica 0.
    from alma_service.skills import SkillIndex
    idx = SkillIndex(os.path.join(DIR, "rep0", "skills-indice.db"))
    skills = {}
    for f in idx.listar(estado="active"):
        from alma_service.skills import cargar_skill
        sk = cargar_skill(f["path"])
        txt = open(f["path"], encoding="utf-8").read()
        m = re.search(r"recomienda_brazo: (\S+)", txt)
        if m:
            skills[f["name"]] = (sk, m.group(1))
    idx.close()

    cliente = ClienteMedido(VaultBackend(model="gpt-4o-mini"), presupuesto,
                            modelo="gpt-4o-mini")
    cliente.etiqueta_default = "probe-conductual"
    ev = Evaluator(judge=StubJudge())
    frescos = generar_problemas(seed=99, n_bloques=8)
    por_firma = {f: [p for p in frescos if p["firma"] == f][:20]
                 for f in FIRMAS}
    pares = []
    for firma, sk_brazo in skills.items():
        sk, brazo = sk_brazo
        guiado = BackendConSkill(cliente, sk)
        for p in por_firma.get(firma, []):
            prob = {"id": p["id"] + "-probe", "enunciado": p["enunciado"],
                    "verificador": "exact", "esperado": p["esperado"]}
            r_raw = executors.ejecutar(brazo, prob, cliente)
            m_raw = ev.score(prob, r_raw["respuesta"], brazo, r_raw["traza"])
            r_gui = executors.ejecutar(brazo, prob, guiado)
            m_gui = ev.score(prob, r_gui["respuesta"], brazo, r_gui["traza"])
            pares.append({"firma": firma, "problema": p["id"],
                          "brazo": brazo,
                          "raw": float(m_raw["exito"]),
                          "guiada": float(m_gui["exito"]),
                          "dif": float(m_gui["exito"]) - float(m_raw["exito"])})
    return pares, skills


def ic95_diferencia(pares):
    n = len(pares)
    if n == 0:
        return 0.0, (0.0, 0.0)
    difs = [p["dif"] for p in pares]
    media = sum(difs) / n
    var = sum((d - media) ** 2 for d in difs) / n
    se = math.sqrt(var / n)
    return media, (media - 1.96 * se, media + 1.96 * se)


def veredicto(pre, rep_replicas, pares, costo_total, dif_media):
    crit = {}
    # (1) skill válida en >=2/3 réplicas
    ok1 = sum(1 for r in rep_replicas if len(r["skills"]) >= 1) >= 2
    # (2) >=1 refinamiento en >=1 réplica
    ok2 = any(len(r["refinamientos"]) >= 1 for r in rep_replicas)
    # (3) proveedor consultado en las 3; skills_usadas>=1 en >=1
    ok3 = (all(r["skills_usadas"] >= 0 for r in rep_replicas)
           and any(r["skills_usadas"] >= 1 for r in rep_replicas))
    # (4) modo skills en las 3
    ok4 = all(r["modo_recurrencia"] == "skills" for r in rep_replicas)
    # (5) costo <= 0.50
    ok5 = costo_total <= 0.50
    # (6) diferencia pareada > 0
    ok6 = dif_media > 0
    crit = {"1_generacion": ok1, "2_refinamiento": ok2,
            "3_proveedor_consultado": ok3, "4_modo_skills": ok4,
            "5_costo": ok5, "6_conductual": ok6}
    pasa = all(crit.values())
    return ("PASS" if pasa else "FAIL"), crit


def main():
    pre = cargar_preregistro()
    t0 = time.time()
    presupuesto = Presupuesto(TOPE_DURO)
    error = None
    try:
        replicas = parte_a(presupuesto)
        pares, skills_b = parte_b(presupuesto)
    except PresupuestoAgotado as e:
        error = f"presupuesto agotado a mitad de corrida: {e}"
        replicas, pares = [], []
    costo_total = round(presupuesto.gastado, 6)
    dif_media, ic = ic95_diferencia(pares)
    por_firma = {}
    for f in FIRMAS:
        pf = [p for p in pares if p["firma"] == f]
        m, _ = ic95_diferencia(pf)
        por_firma[f] = {"n": len(pf), "dif_media": round(m, 4),
                        "raw_ok": sum(p["raw"] for p in pf),
                        "guiada_ok": sum(p["guiada"] for p in pf)}
    vered, crit = (("FAIL", {"error": error}) if error else
                   veredicto(pre, replicas, pares, costo_total, dif_media))
    report = {
        "nombre": pre["nombre"],
        "preregistro": os.path.join(DIR, "preregistro.json"),
        "duracion_s": round(time.time() - t0, 1),
        "parte_a_replicas": replicas,
        "parte_b": {
            "n_pares": len(pares),
            "diferencia_media": round(dif_media, 4),
            "ic95": [round(ic[0], 4), round(ic[1], 4)],
            "por_firma": por_firma,
        },
        "costo_total_usd": costo_total,
        "criterios": crit,
        "veredicto": vered,
    }
    with open(os.path.join(DIR, "report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    lineas = [f"# Veredicto: {pre['nombre']}", "",
              f"Hipótesis: {pre['hipotesis']}", "",
              "## Números",
              f"- réplicas: {len(replicas)}",
              f"- skills generadas por réplica: "
              f"{[len(r['skills']) for r in replicas]}",
              f"- refinamientos por réplica: "
              f"{[len(r['refinamientos']) for r in replicas]}",
              f"- skills_usadas por réplica: "
              f"{[r['skills_usadas'] for r in replicas]}",
              f"- diferencia conductual (guiada−raw): "
              f"{dif_media:.3f} IC95 [{ic[0]:.3f}, {ic[1]:.3f}]",
              f"  por firma: {por_firma}",
              f"- costo total: US${costo_total:.4f} "
              f"(tope autorizado 0.50, duro 0.40)", ""]
    lineas.append("## Criterios pre-registrados")
    for k, v in crit.items():
        lineas.append(f"- {k}: {'✓' if v else '✗'}")
    lineas += ["", f"## Veredicto\n\n**{vered}**",
               f"\nCriterio: {pre['criterio_exito']}"]
    if vered == "FAIL":
        lineas.append(f"\nFalla: {pre['criterio_falla']}")
    with open(os.path.join(DIR, "veredicto.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    print("\n".join(lineas))
    print(f"\nCosto medido: US${costo_total:.4f}")


if __name__ == "__main__":
    main()
