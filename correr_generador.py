"""Corrida pre-registrada del generador de candidatos (16/10/2026).

Pre-registro: preregistro-generador-sakana-2026-10-16.md — leerlo
ANTES de correr cualquiera de los dos pasos. Este script ES el
procedimiento declarado en ese documento:

  Paso 1 — generar y congelar la tanda (US$0, tier :free):
      python3 correr_generador.py --generar
      Pide la tanda al modelo declarado, la valida mecánicamente y
      la escribe a tanda_generador_<ts>.json. NO evalúa a nadie.

  Paso 2 — la corrida (requiere el «corré» de Alejandro):
      python3 correr_generador.py --tanda tanda_generador_<ts>.json
      Alimenta los candidatos válidos al camino normal del meta-loop
      (correr(candidatos=...)): train → held-out → E3 → puerta, con
      el piso y el panel vigentes. Es UNA corrida a efectos del
      freno de estancamiento. Sin segunda tanda bajo este
      pre-registro: lo que salga, queda asentado.

Sin flags, no hace nada.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service import generador_candidatos as g  # noqa: E402
from alma_service.metaloop import MetaLoop  # noqa: E402
from alma_service.presupuesto import PresupuestoFase2  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(AQUI, "alma_store.db")
LEDGER = os.path.join(AQUI, "metaloop_ledger.jsonl")


def paso_generar(modelo, n_objetivo):
    ml = MetaLoop(DB, presupuesto=PresupuestoFase2(DB))
    base = ml.scaffold_vigente()
    historial = g.historial_desde_ledger(LEDGER)
    backend = g.backend_openrouter(modelo=modelo)
    res = g.generar_tanda(backend, base, historial,
                          n_objetivo=n_objetivo, modelo=modelo)
    ruta = os.path.join(AQUI, f"tanda_generador_{int(time.time())}.json")
    g.guardar_tanda(res, ruta, base, ledger_path=LEDGER)
    print(f"tanda congelada: {ruta}")
    print(f"válidos: {len(res['candidatos'])}/{n_objetivo} "
          f"(llamados: {res['llamados']}, "
          f"descartados: {len(res['descartados'])})")
    if len(res["candidatos"]) < g.N_MINIMO_TANDA:
        print(f"OJO: bajo el mínimo declarado ({g.N_MINIMO_TANDA}): "
              "la corrida NO se lanza con esta tanda "
              "(pre-registro, tanda insuficiente).")
    return ruta


def paso_correr(ruta_tanda):
    with open(ruta_tanda, encoding="utf-8") as f:
        doc = json.load(f)
    configs = [c["config"] for c in doc["candidatos"]]
    if len(configs) < g.N_MINIMO_TANDA:
        print(f"tanda insuficiente ({len(configs)} < "
              f"{g.N_MINIMO_TANDA}): la corrida no se lanza.")
        return 1
    ml = MetaLoop(DB, presupuesto=PresupuestoFase2(DB))
    r = ml.correr(candidatos=configs, bloqueante=True)
    print("corrida:", r)
    est = ml.estado()
    print("scaffold vigente:", est["scaffold_vigente"])
    print("freno:", est["freno_estancamiento"])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--generar", action="store_true",
                    help="paso 1: generar y congelar la tanda")
    ap.add_argument("--tanda", metavar="RUTA",
                    help="paso 2: correr la tanda congelada")
    ap.add_argument("--modelo", default=g.MODELO_DEFAULT,
                    help="modelo OpenRouter (default: el declarado)")
    ap.add_argument("--n", type=int, default=g.N_TANDA_DEFAULT,
                    help="candidatos objetivo de la tanda")
    args = ap.parse_args()
    if args.generar:
        paso_generar(args.modelo, args.n)
        return 0
    if args.tanda:
        return paso_correr(args.tanda)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
