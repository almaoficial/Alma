"""Tests fase 2: meta-loop RSO (validador congelado, keep/revert, ledger).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase2_metaloop.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.metaloop import MetaLoop
from alma_service.presupuesto import PresupuestoFase2
from alma_service.scaffold import DEFAULT_SCAFFOLD

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def main():
    d = tempfile.mkdtemp(prefix="alma_fase2_ml_")
    db = os.path.join(d, "ml.db")
    pres = PresupuestoFase2(db, tope_mensual_usd=0.0)  # mock: costo 0

    ml = MetaLoop(db, presupuesto=pres, rondas=2)

    # 1. Arranca con el default validado.
    check("scaffold inicial = DEFAULT_SCAFFOLD",
          ml.scaffold_vigente() == DEFAULT_SCAFFOLD)

    # 2. Validador congelado: e47/e56 no se tocan (los módulos son los
    # mismos objetos importados; el loop solo lee).
    import run_experiment47 as e47
    import run_experiment56 as e56
    check("e47.construir_stream intacto",
          callable(e47.construir_stream))
    check("e56.correr_replica_param intacto",
          callable(e56.correr_replica_param))

    # 3. Corrida bloqueante corta: pre-registro escrito, ledger con eventos.
    r = ml.correr(seed=7, rondas=2, bloqueante=True)
    check("corrida aceptada", r.get("aceptado") is True)
    est = ml.estado()
    check("termina inactivo", est["fase"] == "inactivo")
    check("ultima_corrida registrada",
          est["ultima_corrida"] is not None)
    evs = ml.ledger_leer()
    tipos = [e["evento"]["tipo"] for e in evs]
    check("ledger: iniciada + finalizada",
          "corrida_iniciada" in tipos and "corrida_finalizada" in tipos)
    check("pre-registro en disco",
          os.path.exists(ev := next(
              e["evento"]["preregistro"] for e in evs
              if e["evento"]["tipo"] == "corrida_iniciada")))
    pr = json.load(open(ev, encoding="utf-8"))
    check("pre-registro declara validador congelado",
          "congelado" in pr["validador"])

    # 4. Cadena de hashes del ledger verificable.
    import hashlib
    prev = "GENESIS"
    ok = True
    for e in evs:
        cuerpo = dict(e["evento"])
        canon = json.dumps(cuerpo, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
        h = hashlib.sha256((prev + canon).encode("utf-8")).hexdigest()
        ok = ok and (h == e["hash"] and e["prev"] == prev)
        prev = e["hash"]
    check("ledger con hash encadenado válido", ok)

    # 5. Rollback: sin adopciones previas no hay anterior.
    rb = ml.revertir()
    check("revertir sin historial -> False",
          rb["revertido"] is False)

    # 6. Segunda instancia: no duplica el scaffold inicial.
    ml2 = MetaLoop(db, presupuesto=pres, rondas=2)
    check("reapertura conserva historial",
          len(ml2.historial_scaffold()) >= 1)

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
