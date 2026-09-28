#!/usr/bin/env python3
"""ALMA-EXP67 oraculo (fase de ground truth).

Mide el reward real de cada brazo {single, cot, reflexion} sobre los 180
problemas del stream pre-registrado (9 bloques x 20, orden del manifiesto):
180 x 3 x 2 = 1080 llamadas a deepseek-flash.

Reutiliza de pilot.py: cargar_problemas (seccion="stream"), scorers,
chequeo_scorers y la clase Piloto (idempotente, con freno duro).
La fase "oraculo" escribe en oracle_pulls.jsonl (archivo distinto al del
piloto) y cada registro lleva "fase": "oraculo": las keys de idempotencia
(pid, arm, intento) no colisionan con pilot_pulls.jsonl.

La key viaja SOLO por DEEPSEEK_API_KEY (variable de entorno). Este script
nunca la escribe en disco ni en logs.

Freno duro: US$0,55 TOTAL (default, sobreescribible con --tope). Al
alcanzarlo aborta limpio: deja el parcial en oracle_pulls.jsonl (el resume
retoma donde quedo) y sale con codigo 2, sin resumen.

Al completar: guarda oracle_summary.json con la media de reward por brazo
y slice, costo total, llamadas y duracion. NO calcula el veredicto
PASS/FAIL del experimento: la fase de politicas (alma-full vs fijas) va
despues, con aprobacion separada.

Uso:
    DEEPSEEK_API_KEY=... ~/workspace/venvs/exp67/bin/python oracle.py --out <dir>
    ... oracle.py --out <dir> --dry-run   # sin API: valida carga+scorers
    ... oracle.py --out <dir> --tope 0.80  # freno distinto
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pilot
from pilot import (ARMS, N_INTENTOS, Piloto, cargar_problemas,
                   chequeo_scorers)

# pilot.py ya agrego ~/workspace/alma-prototype/exp62_deepseek al path
from run_exp62 import DeepSeekBackend, ejecutar


def resumen_oraculo(pulls, llamadas_api, gastado, tope, duracion_s):
    """Media de reward por brazo y slice. Sin veredicto PASS/FAIL."""
    por_slice = {}
    for r in pulls:
        por_slice.setdefault(r["slice"], {}).setdefault(
            r["arm"], []).append(r["reward"])
    slices = {}
    for sl, arms in por_slice.items():
        n_prob = len({r["pid"] for r in pulls if r["slice"] == sl})
        slices[sl] = {
            "n_problemas": n_prob,
            "n_pulls": sum(len(v) for v in arms.values()),
            "media_reward": {a: round(sum(v) / len(v), 4)
                             for a, v in arms.items()},
        }
    return {
        "fase": "oraculo",
        "meta": {
            "experimento": "ALMA-EXP67 oraculo (ground truth)",
            "problemas": len({r["pid"] for r in pulls}),
            "pulls": len(pulls),
            "llamadas_api": llamadas_api,
            "costo_total_usd": round(gastado, 4),
            "freno_usd": tope,
            "duracion_s": round(duracion_s, 1),
        },
        "slices": slices,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--tope", type=float, default=0.55,
                    help="freno duro en USD (default 0.55)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)

    print("== EXP67 oraculo: carga de problemas (stream) ==")
    problemas = cargar_problemas(dry=args.dry_run, seccion="stream")
    por_slice = {sl: sum(1 for p in problemas if p["slice"] == sl)
                 for sl in ("gsm8k", "mmlu", "mbpp")}
    print(f"   {len(problemas)} problemas {por_slice}")
    assert len(problemas) == 180, \
        f"el stream debe tener 180 problemas, hay {len(problemas)}"
    assert all(n == 60 for n in por_slice.values()), \
        f"cada slice debe tener 60 problemas: {por_slice}"

    if args.dry_run:
        ok = chequeo_scorers()
        print("   dry-run:", "VERDE" if ok else "ROJO — revisar scorers")
        return 0 if ok else 1

    backend = DeepSeekBackend()
    modelos = backend.ping()
    assert "deepseek-flash" in modelos, "deepseek-flash no visible en /models"
    print("   ping /models OK (gratis)")

    ora = Piloto(args.out, fase="oraculo",
                 pulls_fname="oracle_pulls.jsonl", tope_usd=args.tope)
    total = len(problemas) * len(ARMS) * N_INTENTOS
    hechos_nuevos = 0

    print(f"== oraculo: {total} pulls "
          f"(3 brazos x 2 intentos x 180, freno US${args.tope:.2f}) ==")
    try:
        for p in problemas:
            for arm in ARMS:
                for i in range(N_INTENTOS):
                    r, nuevo = ora.pull(p, arm, i, backend, ejecutar)
                    if nuevo:
                        hechos_nuevos += 1
            if hechos_nuevos and hechos_nuevos % 60 == 0:
                print(f"   {len(ora.hechos)}/{total} pulls | "
                      f"gastado ${ora.gastado:.4f} | {time.time()-t0:.0f}s",
                      flush=True)
    except RuntimeError as e:
        print(f"\nABORTO POR FRENO: {e}")
        print(f"   parcial: {len(ora.hechos)} pulls, "
              f"gastado ${ora.gastado:.4f} — sin resumen "
              f"(resume retoma en oracle_pulls.jsonl)")
        return 2

    pulls = list(ora.hechos.values())
    resumen = resumen_oraculo(pulls, backend.llamadas, ora.gastado,
                              args.tope, time.time() - t0)
    with open(os.path.join(args.out, "oracle_summary.json"), "w") as f:
        json.dump(resumen, f, indent=2, ensure_ascii=False)

    print("\n================ RESUMEN ORACULO ================")
    for sl, inf in resumen["slices"].items():
        print(f"  {sl}: n={inf['n_problemas']} "
              f"media_reward={inf['media_reward']}")
    print(f"  costo total: ${ora.gastado:.4f} | "
          f"llamadas API: {backend.llamadas} | "
          f"{resumen['meta']['duracion_s']}s")
    print("  (sin veredicto: la fase de politicas va con aprobacion "
          "separada)")
    print("==================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
