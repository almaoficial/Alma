#!/usr/bin/env python3
"""Retoma el experimento ALMA-EXP1 desde donde quedó.

- Salta los pares (fase, problema_id, arch_id) ya registrados en el store.
- Reintenta cada llamada a la API hasta 3 veces con backoff (un error
  transitorio no debe matar una corrida de 30 minutos).
- No toca la metodología: fase_a/fase_b/fase_c leen el store completo,
  así que el oráculo y el veredicto se calculan sobre los 60 problemas.

Uso:
    python3 resume_experiment.py --out resultados/api-real-20260925-reintento
"""
import json
import os
import sys
import time

import run_experiment as rx


def main():
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    if not out:
        print("uso: resume_experiment.py --out <dir>", file=sys.stderr)
        sys.exit(2)

    hechos = set()
    store_path = os.path.join(out, "experiencias.jsonl")
    if os.path.exists(store_path):
        for line in open(store_path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            hechos.add((d.get("fase"), d.get("problema_id"), d.get("arch_id")))
    print(f"Pares ya registrados: {len(hechos)} (se saltan)")

    original = rx.ejecutar_y_evaluar

    def robusto(problema, arch_id, backend, evaluator, store, budget, fase):
        clave = (fase, problema["id"], arch_id)
        if clave in hechos:
            return None, None
        ultimo_error = None
        for intento in range(3):
            try:
                res, met = original(problema, arch_id, backend, evaluator,
                                    store, budget, fase)
                hechos.add(clave)
                return res, met
            except Exception as e:  # noqa: BLE001 - reintento ante fallos transitorios
                ultimo_error = e
                espera = 5 * (intento + 1)
                print(f"   !! fallo {problema['id']}/{arch_id} "
                      f"(intento {intento + 1}/3): {e}; reintento en {espera}s")
                time.sleep(espera)
        raise RuntimeError(f"falló 3 veces {clave}: {ultimo_error}")

    rx.ejecutar_y_evaluar = robusto

    sys.argv = ["run_experiment.py", "--api", "--seed", "42",
                "--out", out, "--append"]
    rx.main()


if __name__ == "__main__":
    main()
