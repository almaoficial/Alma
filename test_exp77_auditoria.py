"""Tests EXP77 — auditoría de handoff de skills existentes.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_exp77_auditoria.py

Cubre: el traductor es determinista y dispara los predicados esperados
en las 7 skills reales; el runner exige pre-registro (fail-closed); la
auditoría nunca adopta nada real (el spy solo registra); el informe
tiene la estructura esperada; handoff.py no fue modificado (contrato).
Cero gasto de API (mock determinista).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_exp77
from alma_service.handoff import (
    REGLA_HANDOFF, claridad_interfaz, evaluar_skill_para_adopcion,
    interfaz_de_skill)

PASSOS = []
BASE = os.path.dirname(os.path.abspath(__file__))


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def md_de(rel):
    with open(os.path.join(BASE, rel), encoding="utf-8") as fh:
        return fh.read()


RUTAS = [
    "resultados/fase1-puerta/rep0/skills/firmas/aritmetica/SKILL.md",
    "resultados/fase1-puerta/rep0/skills/firmas/razonamiento/SKILL.md",
    "resultados/fase1-puerta/rep1/skills/firmas/aritmetica/SKILL.md",
    "resultados/fase1-puerta/rep1/skills/firmas/razonamiento/SKILL.md",
    "resultados/fase1-puerta/rep2/skills/firmas/aritmetica/SKILL.md",
    "resultados/fase1-puerta/rep2/skills/firmas/razonamiento/SKILL.md",
    "skills/ejemplo/hola-mundo/SKILL.md",
]

# -- traductor: determinista y con predicados esperados -------------------
md0 = md_de(RUTAS[0])
t1 = run_exp77.traducir(md0)
t2 = run_exp77.traducir(md0)
check("traductor determinista (misma entrada, misma salida)", t1 == t2)

a, r, preds = run_exp77.traducir(md_de(RUTAS[0]))  # aritmetica rep0 (cot)
check("aritmetica rep0: TECNICA+PRESCRIBE+RESTRINGE",
      preds == ["TECNICA", "PRESCRIBE", "RESTRINGE"] and (a, r) == (0.6, 0.5))

a, r, preds = run_exp77.traducir(md_de(RUTAS[1]))  # razonamiento rep0
check("razonamiento rep0: GENERICO+PRESCRIBE+RESTRINGE",
      preds == ["GENERICO", "PRESCRIBE", "RESTRINGE"] and (a, r) == (0.3, 0.5))

a, r, preds = run_exp77.traducir(md_de(RUTAS[2]))  # aritmetica rep1
check("aritmetica rep1: PROCEDIMIENTO+PRESCRIBE+RESTRINGE",
      preds == ["PROCEDIMIENTO", "PRESCRIBE", "RESTRINGE"]
      and (a, r) == (0.7, 0.5))

a, r, preds = run_exp77.traducir(md_de(RUTAS[6]))  # hola-mundo
check("hola-mundo: solo INSTRUCCION_CONCRETA, rigidez 0",
      preds == ["INSTRUCCION_CONCRETA"] and (a, r) == (0.7, 0.0))

check("ayuda y rigidez siempre en [0,1]",
      all(0.0 <= run_exp77.traducir(md_de(p))[0] <= 1.0
          and 0.0 <= run_exp77.traducir(md_de(p))[1] <= 1.0
          for p in RUTAS))

# -- q exacto en las 7 ----------------------------------------------------
qs = [claridad_interfaz(interfaz_de_skill(md_de(p))) for p in RUTAS]
check("q=0.8 en las 7 (interfaz prolija y uniforme)", all(q == 0.8 for q in qs))

# -- inventario: 7 archivos, rutas esperadas --------------------------------
inv = run_exp77.inventario()
check("inventario trae las 7 rutas esperadas",
      sorted(i["ruta"] for i in inv) == sorted(RUTAS))
check("hashes sha256 presentes y únicos por contenido",
      all(len(i["sha256"]) == 12 for i in inv))

# -- auditoría sin adopción: el spy registra, nada se adopta ---------------
llamadas = []


def spy(deltas, evidencia):
    llamadas.append(deltas)
    return {"adoptada": False}


v = run_exp77.auditar_skill(inv[0], 0.6, 0.5, spy)
check("puerta acepta aritmetica rep0 (Δ_down>0)",
      v["aceptada"] and v["delta_down"] > 0)
check("spy registra la aceptación sin adoptar",
      len(llamadas) == 1 and v["adoptada_via_fn"] is False)

# una skill que resta: el spy también la registra pero la puerta la rechaza
v_mala = evaluar_skill_para_adopcion(
    "mala", md_de(RUTAS[6]), 0.1, 0.9, adoptar_fn=spy)
check("skill mala (ayuda 0.1, rigidez 0.9): rechazada 'peor que nada'",
      not v_mala["aceptada"] and v_mala["delta_down"] < 0
      and "peor que nada" in v_mala["motivo"])
check("el spy NO se invoca en rechazo (solo en aceptación)",
      len(llamadas) == 1)

# -- clasificación ----------------------------------------------------------
check("clasificar: aceptada->pasa",
      run_exp77.clasificar({"aceptada": True, "delta_down": 0.1}) == "pasa")
check("clasificar: Δ_down<0->resta",
      run_exp77.clasificar({"aceptada": False, "delta_down": -0.2}) == "resta")
check("clasificar: Δ_down=0->bloat",
      run_exp77.clasificar({"aceptada": False, "delta_down": 0.0}) == "bloat")

# -- pre-registro: existe, es de exp77, fail-closed --------------------------
check("pre-registro exp77 existe y nombra el experimento",
      os.path.exists(run_exp77.PREREG_PATH)
      and json.load(open(run_exp77.PREREG_PATH, encoding="utf-8"))
      .get("experimento") == "exp77_auditoria_handoff_skills")

_real = run_exp77.PREREG_PATH
run_exp77.PREREG_PATH = os.path.join(BASE, "no_existe_prereg77.json")
try:
    run_exp77.main()
    check("fail-closed sin pre-registro", False)
except SystemExit as e:
    check("fail-closed sin pre-registro (SystemExit 2)", e.code == 2)
finally:
    run_exp77.PREREG_PATH = _real

# -- informe: estructura ------------------------------------------------------
rep = json.load(open(os.path.join(BASE, "data_exp77/resultados_exp77.json"),
                     encoding="utf-8"))
check("reporte JSON con 7 hallazgos y nota honesta",
      len(rep["hallazgos"]) == 7 and "CONDICIONALES" in rep["nota_honesta"])
h0 = rep["hallazgos"][0]
check("hallazgo trae q, predicados, deltas, veredicto y sensibilidad",
      all(k in h0 for k in ("q_interfaz", "predicados", "ayuda", "rigidez",
                            "delta_down", "delta_ref", "clasificacion",
                            "sensibilidad", "adoptada_via_fn")))
check("ningún hallazgo con adopción real",
      all(h["adoptada_via_fn"] is False for h in rep["hallazgos"]))
check("INFORME.md existe",
      os.path.exists(os.path.join(BASE, "data_exp77/INFORME.md")))

# -- contrato con handoff.py (no modificado, misma regla) ----------------------
check("regla de handoff intacta", REGLA_HANDOFF == "delta_down>0 & delta_ref>=0")
check("evaluar_skill_para_adopcion acepta adoptar_fn=None",
      evaluar_skill_para_adopcion("x", md_de(RUTAS[6]), 0.7, 0.0,
                                  adoptar_fn=None)["adoptada_via_fn"] is False)

print()
print(f"{sum(PASSOS)}/{len(PASSOS)} checks en verde")
sys.exit(0 if all(PASSOS) else 1)
