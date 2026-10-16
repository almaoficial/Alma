"""EXP-JUEZ-001: mide el JuezLLM (modelo gratis) contra el JuezHeuristico.

Pre-registro: 30 salidas etiquetadas (dataset_juez_30.py), modelo
inclusionai/ling-3.1-flash (:free, US$0), presupuesto US$0,05, ~10 min.
Pregunta abierta: ¿el juez con modelo le gana al baseline heurístico de
forma medida? Métricas: acuerdo total, falsos rechazos (escalan de más),
falsos aprobados (dejan pasar basura), abstenciones del LLM.

Correr: python3 alma_service/medir_juez_llm.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alma_service.juez_barato import (JuezHeuristico, JuezLLM,
                                      backend_openrouter)
from alma_service.evaluador_barato import EvaluadorBarato, medir
from alma_service.dataset_juez_30 import PARES

MODEL = os.environ.get("JUEZ_MODEL", "mistralai/mistral-nemo")
PRESUPUESTO_USD = 0.05
backend_or = backend_openrouter(MODEL, max_tokens=20)


def main():
    jh = JuezHeuristico()
    jl = JuezLLM(backend=backend_or, presupuesto_usd=PRESUPUESTO_USD, aprobado=True)

    filas = []
    for i, p in enumerate(PARES):
        salida, contexto = p["salida"], {"pregunta": p["pregunta"]}
        vh = bool(jh(salida, contexto))
        try:
            vl = bool(jl(salida, contexto))
            abst = False
        except Exception as e:
            vl, abst = None, str(e)[:80]
        filas.append({"i": i, "tipo": p["tipo"], "label": p["label"],
                      "heur": vh, "llm": vl, "abstencion": abst})

    def acuerdo(filas, clave):
        validas = [f for f in filas if f[clave] is not None]
        ok = sum(1 for f in validas if f[clave] == f["label"])
        return ok, len(validas)

    ok_h, n_h = acuerdo(filas, "heur")
    ok_l, n_l = acuerdo(filas, "llm")
    abstenciones = sum(1 for f in filas if f["abstencion"])

    # pipeline completo (evaluador + juez), con ternas
    ternas = [(p["salida"], {"pregunta": p["pregunta"]}, p["label"]) for p in PARES]
    m_h = medir(EvaluadorBarato(juez=JuezHeuristico()), ternas)
    jl2 = JuezLLM(backend=backend_or, presupuesto_usd=PRESUPUESTO_USD, aprobado=True)
    m_l = medir(EvaluadorBarato(juez=jl2), ternas)

    print(f"EXP-JUEZ-001 | n=30 | modelo={MODEL} | presupuesto US${PRESUPUESTO_USD}")
    print(f"heurístico: acuerdo {ok_h}/{n_h} = {ok_h/n_h:.3f}")
    acuerdo_l = f"{ok_l}/{n_l} = {ok_l/n_l:.3f}" if n_l else "sin veredictos"
    print(f"llm:        acuerdo {acuerdo_l} (abstenciones: {abstenciones})")
    print(f"pipeline heur: {m_h}")
    print(f"pipeline llm:  {m_l}")
    print(f"costo real: US${jl.gastado_usd:.6f} + US${jl2.gastado_usd:.6f} "
          f"= US${jl.gastado_usd + jl2.gastado_usd:.6f}")

    print("\ndesacuerdos del LLM (tipo | label | veredicto):")
    for f in filas:
        if f["llm"] is not None and f["llm"] != f["label"]:
            print(f"  #{f['i']:02d} {f['tipo']:13s} label={int(f['label'])} "
                  f"llm={int(f['llm'])}")
    if abstenciones:
        print("abstenciones del LLM:")
        for f in filas:
            if f["abstencion"]:
                print(f"  #{f['i']:02d} {f['tipo']:13s} {f['abstencion']}")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "exp_juez_001_resultados.json")
    with open(out, "w") as fh:
        json.dump({"modelo": MODEL, "filas": filas,
                   "pipeline_heur": m_h, "pipeline_llm": m_l,
                   "costo_usd": jl.gastado_usd + jl2.gastado_usd}, fh,
                  ensure_ascii=False, indent=1)
    print(f"\nresultados en {out}")


if __name__ == "__main__":
    main()
