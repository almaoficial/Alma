"""Tests gobernanza 27/9 ~22:50: auto-adopción ante mejora medida.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_gobernanza_auto_adopcion.py

Cubre el cambio de gobernanza (decisión del usuario): el meta-loop
AUTO-ADOPTA sin esperar el "sí" humano, pero SOLO ante mejora medida
("pero no peor": Δ_ho > 0 estricto, Δ_in ≥ 0, frenos sanos). Lo igual o
peor se registra como rechazo con números y no se adopta. El núcleo
protegido (presupuesto, puerta, notificaciones) bloquea con raise + log
+ aviso. Toda adopción es reversible y notificada. Cero gasto de API.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.promotor import (
    Promotor, NucleoProtegidoError, NUCLEO_PROTEGIDO,
    CLAVES_NUCLEO_EXACTAS, DIMENSIONES_PROTEGIDAS)
from alma_service.metaloop import MetaLoop
from alma_service.presupuesto import PresupuestoFase2, BUCKET_METALOOP
from alma_service.scaffold import DEFAULT_SCAFFOLD
from alma_service.trazas import EventLog

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


CLAVES = {"umbral_base", "umbral_divisor", "gate_margin", "n0", "decay"}

ANTES = dict(DEFAULT_SCAFFOLD)
DESPUES = dict(DEFAULT_SCAFFOLD)
DESPUES["n0"] = 2  # mejora hipotética: 4 -> 2


def _promotor_temp(aplicados):
    d = tempfile.mkdtemp(prefix="alma_gob_p_")
    el = EventLog(os.path.join(d, "eventos.db"))
    aplicados_lista = aplicados
    prom = Promotor(
        os.path.join(d, "p.db"),
        aplicar_fn=lambda sc, origen="": aplicados_lista.append(
            (dict(sc), origen)),
        ledger_fn=lambda e: "hash",
        event_log=el,
        revertir_fn=lambda sc, origen="": aplicados_lista.append(
            (dict(sc), "REVERT:" + origen)))
    return prom, el


def _presupuesto_ok(d):
    return PresupuestoFase2(os.path.join(d, "pres.db"),
                            tope_mensual_usd=0.0)


def main():
    # 0. El núcleo protegido está listado explícitamente y visible.
    check("núcleo: 3 superficies listadas", len(NUCLEO_PROTEGIDO) == 3)
    check("núcleo: presupuesto",
          any("presupuesto" in p[0] for p in NUCLEO_PROTEGIDO))
    check("núcleo: puerta de dos splits",
          any("gate" in p[0] for p in NUCLEO_PROTEGIDO))
    check("núcleo: notificaciones",
          any("notific" in p[0] for p in NUCLEO_PROTEGIDO))
    check("dimensiones protegidas declaradas",
          tuple(DIMENSIONES_PROTEGIDAS) == ("costo_usd", "frenos_ok"))

    # 1. Auto-adopción ante mejora estricta en held-out.
    aplicados = []
    prom, el = _promotor_temp(aplicados)
    d = tempfile.mkdtemp(prefix="alma_gob_pre_")
    r = prom.auto_adoptar(
        scaffold_antes=ANTES, scaffold_despues=DESPUES,
        delta_in=5.0, delta_ho=3.0,
        motivo_puerta="aceptada: ...", regla="delta_in>=0 & ...",
        evidencia={"seed": 7}, claves_permitidas=CLAVES,
        costo_usd=0.0, presupuesto=_presupuesto_ok(d),
        bucket=BUCKET_METALOOP)
    check("mejora medida -> adoptada", r.get("adoptada") is True)
    check("commit ejecutado",
          len(aplicados) == 1 and aplicados[0][0] == DESPUES)
    tipos = [e["tipo"] for e in el.ciclo()]
    check("event log: auto_adopcion asentada",
          "auto_adopcion" in tipos)
    ev = [e for e in el.ciclo() if e["tipo"] == "auto_adopcion"][0]
    det = ev["detalle"]
    check("event log trae antes/después/puerta/efecto/revertir",
          det["diff"] == {"n0": [4, 2]}
          and det["efecto_medido"]["delta_ho"] == 3.0
          and "revertir" in det)
    pend = prom.notificaciones_pendientes()
    check("notificación encolada sin reportar",
          len(pend) == 1 and pend[0]["tipo"] == "auto_adopcion"
          and not pend[0].get("reportada"))
    check("adopción visible en historial",
          any(a["estado"] == "adoptada"
              for a in prom.adopciones_recientes()))

    # 2. Igual (Δ_ho == 0): NO se adopta, rechazo con números.
    aplicados2 = []
    prom2, el2 = _promotor_temp(aplicados2)
    d2 = tempfile.mkdtemp(prefix="alma_gob_pre2_")
    r2 = prom2.auto_adoptar(
        scaffold_antes=ANTES, scaffold_despues=DESPUES,
        delta_in=5.0, delta_ho=0.0,
        motivo_puerta="aceptada: ...", regla="r",
        claves_permitidas=CLAVES, costo_usd=0.0,
        presupuesto=_presupuesto_ok(d2), bucket=BUCKET_METALOOP)
    check("igual no se adopta", r2.get("adoptada") is False)
    check("igual no toca producción", aplicados2 == [])
    check("rechazo trae los números",
          "0.0000" in r2.get("motivo", ""))
    tipos2 = [e["tipo"] for e in el2.ciclo()]
    check("event log: rechazo registrado",
          "auto_adopcion_rechazada" in tipos2)

    # 3. Peor (Δ_ho < 0): NO se adopta.
    aplicados3 = []
    prom3, _ = _promotor_temp(aplicados3)
    d3 = tempfile.mkdtemp(prefix="alma_gob_pre3_")
    r3 = prom3.auto_adoptar(
        scaffold_antes=ANTES, scaffold_despues=DESPUES,
        delta_in=1.0, delta_ho=-2.5,
        motivo_puerta="aceptada: ...", regla="r",
        claves_permitidas=CLAVES, costo_usd=0.0,
        presupuesto=_presupuesto_ok(d3), bucket=BUCKET_METALOOP)
    check("peor no se adopta",
          r3.get("adoptada") is False and aplicados3 == [])

    # 4. Regresión en train aunque held-out mejore: NO se adopta.
    aplicados4 = []
    prom4, _ = _promotor_temp(aplicados4)
    d4 = tempfile.mkdtemp(prefix="alma_gob_pre4_")
    r4 = prom4.auto_adoptar(
        scaffold_antes=ANTES, scaffold_despues=DESPUES,
        delta_in=-1.0, delta_ho=4.0,
        motivo_puerta="aceptada: ...", regla="r",
        claves_permitidas=CLAVES, costo_usd=0.0,
        presupuesto=_presupuesto_ok(d4), bucket=BUCKET_METALOOP)
    check("regresión en train no se adopta",
          r4.get("adoptada") is False and aplicados4 == [])

    # 5. Núcleo protegido: los 3 casos hacen raise + log + aviso.
    for nombre_caso, clave_mala in [
            ("presupuesto", "tope_mensual_usd"),
            ("puerta", "regla_puerta"),
            ("notificaciones", "notificaciones")]:
        aplicados5 = []
        prom5, el5 = _promotor_temp(aplicados5)
        d5 = tempfile.mkdtemp(prefix="alma_gob_nuc_")
        despues_malo = dict(ANTES)
        despues_malo[clave_mala] = 999
        levanto = False
        try:
            prom5.auto_adoptar(
                scaffold_antes=ANTES, scaffold_despues=despues_malo,
                delta_in=5.0, delta_ho=3.0,
                motivo_puerta="x", regla="r",
                claves_permitidas=CLAVES, costo_usd=0.0,
                presupuesto=_presupuesto_ok(d5),
                bucket=BUCKET_METALOOP)
        except NucleoProtegidoError:
            levanto = True
        check(f"núcleo ({nombre_caso}): raise", levanto)
        check(f"núcleo ({nombre_caso}): nada aplicado",
              aplicados5 == [])
        tipos5 = [e["tipo"] for e in el5.ciclo()]
        check(f"núcleo ({nombre_caso}): logueado",
              "nucleo_bloqueado" in tipos5)
        avisos = [n for n in prom5.notificaciones_pendientes()
                  if n["tipo"] == "nucleo_bloqueado"]
        check(f"núcleo ({nombre_caso}): aviso encolado",
              len(avisos) == 1)
    check("claves exactas del núcleo declaradas",
          {"tope_mensual_usd", "regla_puerta",
           "notificaciones"} <= set(CLAVES_NUCLEO_EXACTAS))

    # 6. Cola de notificaciones: encolar, leer, marcar.
    aplicados6 = []
    prom6, _ = _promotor_temp(aplicados6)
    d6 = tempfile.mkdtemp(prefix="alma_gob_not_")
    prom6.auto_adoptar(
        scaffold_antes=ANTES, scaffold_despues=DESPUES,
        delta_in=5.0, delta_ho=3.0, motivo_puerta="x", regla="r",
        claves_permitidas=CLAVES, costo_usd=0.0,
        presupuesto=_presupuesto_ok(d6), bucket=BUCKET_METALOOP)
    p6 = prom6.notificaciones_pendientes()
    check("pendiente visible", len(p6) == 1)
    m6 = prom6.marcar_notificadas([p6[0]["id"]])
    check("marcar reportada", m6["marcadas"] == 1)
    check("ya no hay pendientes",
          prom6.notificaciones_pendientes() == [])
    m6b = prom6.marcar_notificadas([p6[0]["id"]])
    check("marcar idempotente", m6b["marcadas"] == 0)

    # 7. Reversibilidad: deshacer una adopción restaura el previo.
    aplicados7 = []
    prom7, el7 = _promotor_temp(aplicados7)
    d7 = tempfile.mkdtemp(prefix="alma_gob_rev_")
    r7 = prom7.auto_adoptar(
        scaffold_antes=ANTES, scaffold_despues=DESPUES,
        delta_in=5.0, delta_ho=3.0, motivo_puerta="x", regla="r",
        claves_permitidas=CLAVES, costo_usd=0.0,
        presupuesto=_presupuesto_ok(d7), bucket=BUCKET_METALOOP)
    rev = prom7.revertir_adopcion(r7["id"])
    check("revertida", rev.get("revertida") is True)
    check("scaffold previo restaurado",
          rev.get("scaffold") == ANTES
          and aplicados7[-1][0] == ANTES)
    tipos7 = [e["tipo"] for e in el7.ciclo()]
    check("event log: reversión asentada",
          "auto_adopcion_revertida" in tipos7)
    check("reversión notificada",
          any(n["tipo"] == "auto_adopcion_revertida"
              for n in prom7.notificaciones_pendientes()))
    rev_mala = prom7.revertir_adopcion(99999)
    check("revertir inexistente falla explícito",
          rev_mala.get("revertida") is False)

    # 8. Freno de presupuesto: costo no autorizado -> no se adopta.
    aplicados8 = []
    prom8, _ = _promotor_temp(aplicados8)
    d8 = tempfile.mkdtemp(prefix="alma_gob_fre_")
    r8 = prom8.auto_adoptar(
        scaffold_antes=ANTES, scaffold_despues=DESPUES,
        delta_in=5.0, delta_ho=3.0, motivo_puerta="x", regla="r",
        claves_permitidas=CLAVES, costo_usd=10.0,
        presupuesto=_presupuesto_ok(d8), bucket=BUCKET_METALOOP)
    check("freno de presupuesto bloquea",
          r8.get("adoptada") is False and aplicados8 == []
          and "presupuesto" in r8.get("motivo", ""))

    # 9. Sin referencia de presupuesto: fail-closed.
    aplicados9 = []
    prom9, _ = _promotor_temp(aplicados9)
    r9 = prom9.auto_adoptar(
        scaffold_antes=ANTES, scaffold_despues=DESPUES,
        delta_in=5.0, delta_ho=3.0, motivo_puerta="x", regla="r",
        claves_permitidas=CLAVES, costo_usd=0.0,
        presupuesto=None, bucket=BUCKET_METALOOP)
    check("sin presupuesto: fail-closed",
          r9.get("adoptada") is False and aplicados9 == [])

    # 10. Integración MetaLoop: PASS + mejora estricta -> auto-adopción.
    d10 = tempfile.mkdtemp(prefix="alma_gob_ml_")
    db10 = os.path.join(d10, "ml.db")
    ml = MetaLoop(db10, presupuesto=PresupuestoFase2(
        db10, tope_mensual_usd=0.0), rondas=2)
    el10 = EventLog(os.path.join(d10, "eventos.db"))
    ml.event_log = el10
    vigente10 = ml.scaffold_vigente()
    orig_evaluar = MetaLoop._evaluar

    def fake_mejora(scaffold, replicas, cache):
        es_train = tuple(replicas) == (0, 1, 2)
        if scaffold == vigente10:
            return ((90.0, [90.0] * 3) if es_train
                    else (95.0, [95.0] * 2))
        return ((85.0, [85.0] * 3) if es_train
                else (90.0, [90.0] * 2))  # Δ_in=5, Δ_ho=5

    MetaLoop._evaluar = staticmethod(fake_mejora)
    try:
        rr = ml.correr(seed=21, rondas=2, bloqueante=True)
    finally:
        MetaLoop._evaluar = orig_evaluar
    check("corrida aceptada", rr.get("aceptado") is True)
    check("auto-adoptó: scaffold vigente cambió",
          ml.scaffold_vigente() != vigente10)
    check("sin staging pendiente (no espera al humano)",
          ml.promotor.pendiente() is None)
    check("notificación de la adopción encolada",
          any(n["tipo"] == "auto_adopcion"
              for n in ml.promotor.notificaciones_pendientes()))
    tipos10 = [e["tipo"] for e in el10.ciclo()]
    check("event log: auto_adopcion del ciclo",
          "auto_adopcion" in tipos10)

    # 11. Integración MetaLoop: mejora lateral (Δ_ho=0) -> no adopta.
    d11 = tempfile.mkdtemp(prefix="alma_gob_ml2_")
    db11 = os.path.join(d11, "ml.db")
    ml11 = MetaLoop(db11, presupuesto=PresupuestoFase2(
        db11, tope_mensual_usd=0.0), rondas=2)
    vigente11 = ml11.scaffold_vigente()

    def fake_lateral(scaffold, replicas, cache):
        es_train = tuple(replicas) == (0, 1, 2)
        if scaffold == vigente11:
            return ((90.0, [90.0] * 3) if es_train
                    else (95.0, [95.0] * 2))
        return ((85.0, [85.0] * 3) if es_train
                else (95.0, [95.0] * 2))  # Δ_in=5, Δ_ho=0

    MetaLoop._evaluar = staticmethod(fake_lateral)
    try:
        ml11.correr(seed=22, rondas=2, bloqueante=True)
    finally:
        MetaLoop._evaluar = orig_evaluar
    check("lateral no adopta: scaffold intacto",
          ml11.scaffold_vigente() == vigente11)
    check("lateral registrado como rechazo",
          any(a["estado"] == "rechazada"
              for a in ml11.promotor.adopciones_recientes()))

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
