"""Runner de los evals de ALMA (la vara externa).

    python -m alma.evals.run                 # corre todo y guarda historial
    python -m alma.evals.run --eval categorizar_gastos
    python -m alma.evals.run --eval rutina_manana --fecha 2026-09-26
        # ^ predice el futuro: muestra la predicción sin puntuar
        #   (no hay ground truth todavía)

Lo pendiente no se guarda en el historial: lo no medido no puntúa.
"""

import argparse

from .base import EvalSuite, evaluar_suite, EVALS_VERSION
from . import finanzas, rutina


def construir_suite(fecha=None):
    suite = EvalSuite()

    @suite.registrar("categorizar_gastos")
    def _c():
        return finanzas.eval_categorizar_gastos()

    @suite.registrar("detectar_anomalia")
    def _d():
        return finanzas.eval_detectar_anomalia()

    @suite.registrar("gasto_semanal")
    def _g():
        return finanzas.eval_gasto_semanal()

    @suite.registrar("rutina_manana")
    def _r():
        return rutina.eval_rutina_manana(fecha_objetivo=fecha)

    @suite.registrar("patron_sostiene")
    def _p():
        return rutina.eval_patron_sostiene()

    return suite


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", default=None, help="un eval puntual")
    ap.add_argument("--fecha", default=None,
                    help="fecha objetivo para rutina_manana")
    ap.add_argument("--no-guardar", action="store_true",
                    help="no escribe en el historial")
    args = ap.parse_args()

    suite = construir_suite(fecha=args.fecha)
    # Se corre sin guardar; lo pendiente no puntúa y no entra al historial.
    resultados = suite.correr(eval_id=args.eval, guardar=False)

    for r in resultados:
        if r.detalle.get("pendiente"):
            print(f"\n[pendiente] {r.eval_id} -> {r.detalle['fecha_objetivo']}:")
            for k, v in r.detalle["prediccion"].items():
                print(f"  {k}: {'sí' if v else 'no'}")
            print("  (sin ground truth: no puntúa, no se guarda)")
        elif not args.no_guardar:
            r.guardar()

    print(f"\n(evals {EVALS_VERSION})")
    evaluar_suite_print(resultados)


def evaluar_suite_print(resultados):
    print(f"\n{'eval':<20}{'metodo':<22}{'score':>8}")
    print("-" * 54)
    for r in resultados:
        if r.detalle.get("pendiente"):
            continue
        print(f"{r.eval_id:<20}{r.metodo:<22}{r.score:>8.4f}")


if __name__ == "__main__":
    main()
