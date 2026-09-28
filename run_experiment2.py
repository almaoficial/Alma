#!/usr/bin/env python3
"""ALMA-EXP2: replicación hostil de la prueba de selección.

Mismo protocolo que EXP1 (run_experiment.py), misma hipótesis, MISMO
criterio pre-registrado (congelado: no se toca), pero:
  - distribución NUEVA: 5 clases distintas (logica, traduccion, resumen,
    depuracion, conocimiento) en data_exp2/,
  - clasificador NUEVO: taxonomía v2 (alma/featurizer_exp2.py),
  - seed distinta (123),
  - mapa de transferencia propio (decisión de diseño documentada).

La hipótesis a refutar: "el selector elige la arquitectura adecuada por
clase y transfiere a clases no vistas con reward>=90% del oráculo y
costo<=125%, superando a la mejor fija global en >=4/5 clases".
Si EXP2 da FAIL, la afirmación de EXP1 no generaliza.

Uso:
    python3 run_experiment2.py --mock            # validación sin API key
    python3 run_experiment2.py --api             # backend real (Secure Vault)
    python3 resume_experiment2.py --out resultados/exp2-20260925   # retomar
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_experiment as rx
from alma import featurizer_exp2 as f2

# --- Parche: misma maquinaria, otra distribución ---------------------------
rx.NOMBRE_EXPERIMENTO = "ALMA-EXP2: replicación hostil de la selección"
rx.CLASES = f2.CLASES
rx.DESCONOCIDA = f2.DESCONOCIDA
rx.classify = f2.classify
rx.featurizer = f2  # ejecutar_y_evaluar accede a featurizer.featurize()
rx.TAXONOMY_VERSION = f2.TAXONOMY_VERSION

# Transferencia leave-one-class-out para las clases nuevas: la clase VISTA
# más parecida, de la que el selector pide prestada la política.
# (Decisión de diseño documentada, igual que en EXP1.)
# Agrupación por DEMANDA COGNITIVA (lo que determina qué arquitectura
# sirve): analíticas (deducción / inspección de código → requieren
# razonar pasos) vs. búsqueda directa (traducción / recuerdo factual).
# v1 del mapa (logica<->conocimiento, por "preguntas declarativas") se
# descartó en validación mock: la similitud superficial no predice la
# arquitectura adecuada; la demanda cognitiva sí.
rx.MAPEO_TRANSFER = {
    "logica": "depuracion",       # analíticas: hay que razonar pasos
    "depuracion": "logica",
    "traduccion": "conocimiento",  # búsqueda directa: single suele bastar
    "conocimiento": "traduccion",
    "resumen": "conocimiento",     # identificación directa con inferencia leve
}


def cargar_datasets2(data_dir):
    problemas_por_clase, index = {}, {}
    for clase in f2.CLASES:
        path = os.path.join(data_dir, f"{clase}.json")
        with open(path, encoding="utf-8") as f:
            probs = json.load(f)
        problemas_por_clase[clase] = probs
        for p in probs:
            index[p["id"]] = p
    return problemas_por_clase, index


rx.cargar_datasets = cargar_datasets2


def demo_gates2(store, stats, oraculo):
    """demo_gates de EXP1 pero envenenando la clase 'logica'
    (demo_gates original hardcodea 'calculo', que no existe en EXP2)."""
    from alma import registry
    from alma.selector import SelectorArquitecturas, BanditPorClase
    from alma.gates import SafetyGates, ReadOnlyStore, PrivilegeError

    def mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    print("\n== Demo de safety gates ==")
    gates = SafetyGates()
    assert gates.verificar_nucleo(), "el núcleo cambió: abortar"
    print("   núcleo fijo intacto (registry/evaluator/taxonomía)")

    ro = ReadOnlyStore(store)
    try:
        ro.append({"problema_id": "x"})
        raise AssertionError("ReadOnlyStore permitió escribir: ¡fallo!")
    except PrivilegeError:
        print("   separación de privilegios: el selector no puede escribir en el store")
    except AssertionError:
        raise

    sel = SelectorArquitecturas()
    for r in store.read_all():
        if r.get("fase") == "A":
            sel.update(r["clase"], r["arch_id"], r["metricas"]["reward"])

    def regret_por_clase(s):
        out = {}
        for c in f2.CLASES:
            pick = s.select_greedy(c)
            or_rw = mean(stats[c][oraculo[c]]["reward"])
            out[c] = round(or_rw - mean(stats[c][pick]["reward"]), 4)
        return out

    viejo = regret_por_clase(sel)
    snap = sel.snapshot()
    b = sel.bandits["logica"]
    pick = sel.select_greedy("logica")
    b.alpha[pick], b.beta[pick] = 1.0, 100.0
    nuevo = regret_por_clase(sel)
    ok, detalle = gates.auditar_no_regresion(viejo, nuevo, epsilon=0.05)
    print(f"   auditoría tras mala actualización: ok={ok} ({detalle})")
    assert not ok, "la auditoría debería haber detectado la regresión"
    gates.rollback_selector(sel, snap)
    restaurado = regret_por_clase(sel)
    assert restaurado == viejo, "el rollback no restauró la política"
    print("   rollback: política restaurada al snapshot previo")
    return {"nucleo_intacto": True, "privilegios_ok": True,
            "regresion_detectada": True, "rollback_ok": True}


rx.demo_gates = demo_gates2


def main():
    # data_exp2/ por defecto (se puede sobrescribir con --data).
    if "--data" not in sys.argv:
        sys.argv += ["--data",
                     os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "data_exp2")]
    return rx.main()


if __name__ == "__main__":
    sys.exit(main())
