#!/usr/bin/env python3
"""Retoma ALMA-EXP2 desde donde quedó.

- Salta los pares (fase, problema_id, arch_id) ya registrados en el store.
- Reintenta cada llamada a la API hasta 3 veces con backoff.
- No toca la metodología: las fases leen el store completo.

Uso:
    python3 resume_experiment2.py --out resultados/exp2-20260925
"""
import json
import os
import sys
import time

import run_experiment as rx1      # su namespace ejecuta las fases
import run_experiment2 as rx2    # aplica los parches de EXP2 al importarse


def main():
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    if not out:
        print("uso: resume_experiment2.py --out <dir>", file=sys.stderr)
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

    original = rx1.ejecutar_y_evaluar

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

    rx1.ejecutar_y_evaluar = robusto

    sys.argv = ["run_experiment2.py", "--api", "--seed", "123",
                "--out", out, "--append"]
    rx2.main()


if __name__ == "__main__":
    main()
