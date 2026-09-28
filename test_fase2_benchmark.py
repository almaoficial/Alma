"""Tests fase 2: benchmark propio (puerta de calidad, mock US$0).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase2_benchmark.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.benchmark import Benchmark
from alma_service.presupuesto import PresupuestoFase2
from alma_service.scaffold import DEFAULT_SCAFFOLD

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def main():
    d = tempfile.mkdtemp(prefix="alma_fase2_bench_")
    db = os.path.join(d, "bench.db")
    pres = PresupuestoFase2(db, tope_mensual_usd=0.0)

    # Scaffold vigente = baseline: mejora esperada ~0.
    b = Benchmark(db, presupuesto=pres,
                  obtener_scaffold_vigente=lambda: dict(DEFAULT_SCAFFOLD))
    r = b.correr(bloqueante=True)
    check("corrida aceptada", r.get("aceptado") is True)
    ult = r["resultado"]
    check("resultado con mejora",
          ult is not None and "mejora" in ult)
    check("baseline vs sí mismo ~ 0",
          abs(ult["mejora"]) < 1e-9)
    check("n_replicas = 5", ult["n_replicas"] == 5)

    # Tendencia expone la serie.
    t = b.tendencia()
    check("tendencia con 1 corrida", len(t) == 1)

    # Segunda corrida: la serie crece.
    b.correr(bloqueante=True)
    check("tendencia con 2 corridas", len(b.tendencia()) == 2)

    # Estado no rompe.
    est = b.estado()
    check("estado ok", est["en_curso"] is False and est["ultimo"] is not None)

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
