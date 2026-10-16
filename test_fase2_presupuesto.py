"""Tests fase 2: presupuesto con topes duros y modo barato por default.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase2_presupuesto.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.presupuesto import (
    PresupuestoFase2, BUCKETS, MODO_BARATO, MODO_NORMAL)

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def main():
    d = tempfile.mkdtemp(prefix="alma_fase2_pres_")

    # 1. Sin tope configurado: modo barato, todo gasto >0 denegado.
    p = PresupuestoFase2(os.path.join(d, "a.db"), tope_mensual_usd=0.0)
    check("default sin tope -> modo barato", p.modo() == MODO_BARATO)
    check("autorizar(0) siempre True",
          p.autorizar(BUCKETS[0], 0.0) is True)
    check("autorizar(costo>0) False en modo barato",
          p.autorizar("servicio_diario", 0.01) is False)
    for b in BUCKETS:
        check(f"limite {b} == 0 sin tope", p.limite(b) == 0.0)

    # 2. Con tope: modo normal, reparto y topes duros.
    p2 = PresupuestoFase2(os.path.join(d, "b.db"), tope_mensual_usd=10.0)
    check("con tope -> modo normal", p2.modo() == MODO_NORMAL)
    check("reparto suma el tope",
          abs(sum(p2.limite(b) for b in BUCKETS) - 10.0) < 1e-9)
    check("autoriza dentro del limite",
          p2.autorizar("servicio_diario", 6.0) is True)
    check("deniega sobre el limite",
          p2.autorizar("servicio_diario", 7.01) is False)
    p2.cargar("servicio_diario", 6.5)
    check("cargar registra gasto", abs(p2.gastado("servicio_diario") - 6.5) < 1e-9)
    check("tras gastar, deniega el resto",
          p2.autorizar("servicio_diario", 0.6) is False)
    check("otros buckets no afectados",
          p2.autorizar("metaloop", 1.0) is True)

    # 3. Bucket desconocido corta con ValueError (fail-closed).
    try:
        p2.autorizar("inexistente", 0.0)
        check("bucket desconocido corta", False)
    except ValueError:
        check("bucket desconocido corta", True)

    # 4. Persistencia entre instancias (misma db).
    p3 = PresupuestoFase2(os.path.join(d, "b.db"), tope_mensual_usd=10.0)
    check("el gasto persiste",
          abs(p3.gastado("servicio_diario") - 6.5) < 1e-9)

    # 5. Env var ALMA_PRESUPUESTO_MENSUAL.
    os.environ["ALMA_PRESUPUESTO_MENSUAL"] = "5.0"
    p4 = PresupuestoFase2(os.path.join(d, "c.db"))
    check("lee tope de env", p4.tope_mensual == 5.0)
    del os.environ["ALMA_PRESUPUESTO_MENSUAL"]
    p5 = PresupuestoFase2(os.path.join(d, "e.db"))
    check("sin env -> 0.0 (barato)", p5.tope_mensual == 0.0)

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
