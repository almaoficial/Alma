#!/usr/bin/env python3
"""Verifica que el mundo sintético respete el diseño documentado.

El mock es un laboratorio controlado: su ground truth efectivo tiene que
coincidir con TASAS_MOCK (a ±0.06) y producir los oráculos y la mejor fija
global diseñados. Si este test falla, el experimento estaría midiendo un
mundo distinto del que dice medir.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alma.backends import MockBackend, TASAS_MOCK
from alma.evaluator import Evaluator
from alma.executors import ejecutar
from alma.featurizer import CLASES
from alma.registry import list_archs

ORACULOS_DISENADOS = {
    "calculo": "cot",
    "codigo": "plan_tools_verify",
    "qa_multihop": "cot",
    "herramientas": "plan_tools_verify",
    "puzzles": "debate",
}
MEJOR_FIJA_DISENADA = "reflexion"


def cargar():
    base = os.path.join(os.path.dirname(__file__), "..", "data")
    index, por_clase = {}, {}
    for clase in CLASES:
        with open(os.path.join(base, f"{clase}.json"), encoding="utf-8") as f:
            probs = json.load(f)
        por_clase[clase] = probs
        for p in probs:
            index[p["id"]] = p
    return index, por_clase


def main():
    index, por_clase = cargar()
    backend = MockBackend(index, seed=42)
    evaluator = Evaluator()
    fails = []

    for clase in CLASES:
        rewards = {}
        for arch in list_archs():
            exitos = 0
            for problema in por_clase[clase]:
                res = ejecutar(arch, problema, backend)
                exitos += evaluator.score(problema, res["respuesta"], arch)["exito"]
            tasa = exitos / len(por_clase[clase])
            objetivo = TASAS_MOCK[clase][arch]
            rewards[arch] = tasa
            if abs(tasa - objetivo) > 0.06:
                fails.append(
                    f"tasa {clase}/{arch}: medida {tasa:.3f} vs diseñada {objetivo:.3f}"
                )
        oraculo = max(rewards, key=lambda a: rewards[a])
        if oraculo != ORACULOS_DISENADOS[clase]:
            fails.append(
                f"oráculo {clase}: medido {oraculo} vs diseñado "
                f"{ORACULOS_DISENADOS[clase]} (tasas: "
                + ", ".join(f"{a}={r:.2f}" for a, r in sorted(rewards.items()))
                + ")"
            )

    # Mejor fija global: promedio de tasas por arquitectura.
    medias = {
        arch: sum(
            sum(
                1 for p in por_clase[c]
                if evaluator.score(p, ejecutar(arch, p, backend)["respuesta"], arch)["exito"]
            ) / len(por_clase[c])
            for c in CLASES
        ) / len(CLASES)
        for arch in list_archs()
    }
    mejor = max(medias, key=lambda a: medias[a])
    if mejor != MEJOR_FIJA_DISENADA:
        fails.append(
            f"mejor fija global: medida {mejor} vs diseñada {MEJOR_FIJA_DISENADA}"
        )

    if fails:
        print("GROUND TRUTH: FAIL")
        for f in fails:
            print("  -", f)
        return 1
    print("test_mock_ground_truth: OK (oráculos y mejor fija = diseño)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
