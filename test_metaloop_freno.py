"""Tests del freno de estancamiento del meta-loop (idea 2, revisión 7/10).

El freno se detiene solo y avisa si el meta-loop propone 3 corridas
seguidas sin mejora medida (sin adopción). Solo un humano lo reanuda.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_metaloop_freno.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.metaloop import MetaLoop, RACHA_MAX_PLANA
from alma_service.presupuesto import PresupuestoFase2

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def nuevo_loop():
    d = tempfile.mkdtemp(prefix="alma_freno_")
    db = os.path.join(d, "ml.db")
    pres = PresupuestoFase2(db, tope_mensual_usd=0.0)  # mock: costo 0
    return MetaLoop(db, presupuesto=pres, rondas=2)


def tipos_ledger(ml):
    return [e["evento"]["tipo"] for e in ml.ledger_leer()]


def main():
    check("racha máxima = 3", RACHA_MAX_PLANA == 3)

    # 1. Estado inicial: freno inactivo, racha 0.
    ml = nuevo_loop()
    f = ml.estado_freno()
    check("arranca sin freno", f["freno_activo"] is False)
    check("arranca con racha 0", f["racha_planas"] == 0)

    # 2. Una y dos planas: el freno no se activa, correr sigue permitido.
    r1 = ml.registrar_corrida(adoptado=False)
    check("1ra plana: racha 1", r1["racha_planas"] == 1)
    check("1ra plana: sin freno", r1["freno_activo"] is False)
    r2 = ml.registrar_corrida(adoptado=False)
    check("2da plana: racha 2", r2["racha_planas"] == 2)
    check("2da plana: sin freno", r2["freno_activo"] is False)
    check("sin evento de freno en el ledger",
          "metaloop_freno_estancamiento" not in tipos_ledger(ml))

    # 3. La 3ra plana: PARA. Freno activo + aviso en el ledger.
    r3 = ml.registrar_corrida(adoptado=False)
    check("3ra plana: racha 3", r3["racha_planas"] == 3)
    check("3ra plana: freno activo", r3["freno_activo"] is True)
    check("aviso asentado en el ledger",
          "metaloop_freno_estancamiento" in tipos_ledger(ml))
    ev = next(e["evento"] for e in ml.ledger_leer()
              if e["evento"]["tipo"] == "metaloop_freno_estancamiento")
    check("el aviso dice la racha", ev["racha_planas"] == 3)

    # 4. Con el freno activo, correr() se niega (no arranca hilo).
    r = ml.correr(seed=1)
    check("correr() rechazado con freno activo",
          r.get("aceptado") is False
          and "estancamiento" in r.get("motivo", ""))

    # 5. Idempotencia: más planas no duplican el aviso ni rompen nada.
    ml.registrar_corrida(adoptado=False)
    n = sum(1 for e in ml.ledger_leer()
            if e["evento"]["tipo"] == "metaloop_freno_estancamiento")
    check("el aviso se emite una sola vez", n == 1)
    check("el freno sigue activo",
          ml.estado_freno()["freno_activo"] is True)

    # 6. Una adopción resetea la racha (loop sano).
    ml2 = nuevo_loop()
    ml2.registrar_corrida(adoptado=False)
    ml2.registrar_corrida(adoptado=False)
    ra = ml2.registrar_corrida(adoptado=True)
    check("adopción resetea la racha", ra["racha_planas"] == 0)
    check("adopción no activa el freno", ra["freno_activo"] is False)

    # 7. Solo el humano desbloquea: freno limpio + evento auditado.
    d = ml.desbloquear_freno(origen="humano")
    check("desbloquear limpia el freno", d["freno_activo"] is False)
    check("desbloquear resetea la racha", d["racha_planas"] == 0)
    check("desbloqueo auditado en el ledger",
          "metaloop_freno_desbloqueado" in tipos_ledger(ml))
    r = ml.correr(seed=1)
    check("tras desbloquear, correr() vuelve a aceptar",
          r.get("aceptado") is True)
    # (la corrida queda en background con costo 0; no se joinea: el
    # freno ya demostró lo suyo y el test no necesita su resultado)

    # 8. El freno persiste en la DB (sobrevive reinicios).
    ml3 = nuevo_loop()
    ml3.registrar_corrida(adoptado=False)
    ml3.registrar_corrida(adoptado=False)
    ml3.registrar_corrida(adoptado=False)
    ml3b = MetaLoop(ml3.db_path,
                    presupuesto=PresupuestoFase2(ml3.db_path,
                                                 tope_mensual_usd=0.0),
                    rondas=2)
    check("el freno sobrevive al reinicio",
          ml3b.estado_freno()["freno_activo"] is True)
    check("estado() expone el freno",
          ml3b.estado()["freno_estancamiento"]["freno_activo"] is True)

    print()
    print(f"{sum(PASSOS)}/{len(PASSOS)} PASS")
    if not all(PASSOS):
        sys.exit(1)


if __name__ == "__main__":
    main()
