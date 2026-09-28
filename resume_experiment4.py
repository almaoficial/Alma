#!/usr/bin/env python3
"""Retoma ALMA-EXP4 desde donde quedó.

- Salta los pares (fase, problema_id, arch_id) ya registrados en el store.
- Reintenta cada llamada a la API hasta 3 veces con backoff.
- El estado online (bandits, repertorio) se reconstruye deterministamente
  desde el store: replay en orden + RNG por (clase, problema).

Uso:
    python3 resume_experiment4.py --out resultados/exp4-20260925
"""
import json
import os
import sys
import time

import run_experiment as rx1      # su namespace ejecuta las fases
import run_experiment4 as rx4    # noqa: F401 — solo define, no corre main


def main():
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    if not out:
        print("uso: resume_experiment4.py --out <dir>", file=sys.stderr)
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

    sys.argv = ["run_experiment4.py", "--api", "--seed", "789",
                "--out", out, "--append"]
    rx4.main()


if __name__ == "__main__":
    main()
