"""Tests fase 2.3: promotor (staging + camino manual) y gobernanza
(auto-adopción ante mejora medida, 27/9 ~22:50).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase23_freno_humano.py

Cubre el camino manual original de la fase 2.3 (proponer → staging →
aprobar/rechazar con allowlist "humano") más el cambio de gobernanza
(decisión del usuario, 27/9 ~22:50, refino "pero no peor"): la fase 2.3
queda SUPERADA para el meta-loop — un PASS de la puerta con mejora
medida (Δ_ho > 0, Δ_in ≥ 0, frenos sanos) se AUTO-ADOPTA sin esperar el
"sí" humano; lo igual o peor se rechaza con números y no se adopta.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.promotor import (
    Promotor, APROBADORES, ESTADO_ESPERA, ESTADO_APROBADA,
    ESTADO_RECHAZADA)
from alma_service.metaloop import MetaLoop, TRAIN_REPS
from alma_service.presupuesto import PresupuestoFase2
from alma_service.scaffold import DEFAULT_SCAFFOLD
from alma_service.trazas import EventLog

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def _promotor_temp(aplicados):
    d = tempfile.mkdtemp(prefix="alma_fase23_p_")
    return Promotor(os.path.join(d, "p.db"),
                    aplicar_fn=lambda sc, origen="": aplicados.append(
                        (dict(sc), origen)),
                    ledger_fn=lambda e: "hash"), d


ANTES = dict(DEFAULT_SCAFFOLD)
DESPUES = dict(DEFAULT_SCAFFOLD)
DESPUES["n0"] = 8  # fuera del espacio válido: el promotor no valida
# valores, solo transporta lo que la puerta ya aprobó (el validador
# congelado es quien decide; el promotor no re-evalúa).


def main():
    # 1. Allowlist de aprobadores: solo "humano".
    check("allowlist = ('humano',)", tuple(APROBADORES) == ("humano",))

    # 2. Proponer: staging inspeccionable (diff, deltas, evidencia).
    aplicados = []
    prom, _ = _promotor_temp(aplicados)
    r = prom.proponer(scaffold_antes=ANTES, scaffold_despues=DESPUES,
                      delta_in=5.0, delta_ho=3.0,
                      motivo_puerta="aceptada: ...",
                      regla="delta_in>=0 & delta_ho>=0 & max>0",
                      evidencia={"seed": 7, "rondas": 2,
                                 "preregistro": "/tmp/pr.json"})
    check("proponer acepta", r.get("propuesto") is True)
    pend = prom.pendiente()
    check("pendiente visible", pend is not None
          and pend["estado"] == ESTADO_ESPERA)
    check("diff muestra qué cambia",
          pend["diff"] == {"n0": [ANTES["n0"], 8]})
    check("deltas justifican la promoción",
          pend["delta_in"] == 5.0 and pend["delta_ho"] == 3.0)
    check("evidencia con lineage",
          pend["evidencia"].get("preregistro") == "/tmp/pr.json"
          and pend["evidencia"].get("seed") == 7)
    insp = prom.inspeccionar(pend["id"])
    check("inspeccionar trae scaffold completo",
          insp["scaffold_despues"] == DESPUES
          and insp["scaffold_antes"] == ANTES)

    # 3. Sin aprobación no hay commit: aplicar_fn no se invocó.
    check("staging no toca producción", aplicados == [])

    # 4. Un solo pendiente por vez.
    r2 = prom.proponer(scaffold_antes=ANTES, scaffold_despues=DESPUES,
                       delta_in=1.0, delta_ho=1.0,
                       motivo_puerta="x", regla="r")
    check("segundo pendiente rechazado",
          r2.get("propuesto") is False)

    # 5. Aprobar con aprobador no autorizado: se frena, sin commit.
    mal = prom.aprobar(pend["id"], aprobador="loop")
    check("aprobador 'loop' rechazado",
          mal.get("aprobada") is False and aplicados == [])
    check("sigue en espera tras intento inválido",
          prom.pendiente()["estado"] == ESTADO_ESPERA)

    # 6. Aprobar con "humano": commit + trazabilidad.
    ok = prom.aprobar(pend["id"], aprobador="humano")
    check("aprobada por humano", ok.get("aprobada") is True)
    check("commit ejecutado con lineage",
          len(aplicados) == 1 and aplicados[0][0] == DESPUES
          and "aprobador=humano" in aplicados[0][1])
    check("estado aprobada",
          prom.inspeccionar(pend["id"])["estado"] == ESTADO_APROBADA)
    check("ya no hay pendiente", prom.pendiente() is None)

    # 7. Doble aprobación: la segunda falla.
    otra = prom.aprobar(pend["id"], aprobador="humano")
    check("no se aprueba dos veces",
          otra.get("aprobada") is False and len(aplicados) == 1)

    # 8. Rechazo: se archiva con motivo, producción intacta.
    aplicados2 = []
    prom2, _ = _promotor_temp(aplicados2)
    p2 = prom2.proponer(scaffold_antes=ANTES, scaffold_despues=DESPUES,
                        delta_in=2.0, delta_ho=2.0,
                        motivo_puerta="x", regla="r")
    sin_motivo = prom2.rechazar(p2["id"], "", aprobador="humano")
    check("rechazo sin motivo exige motivo",
          sin_motivo.get("rechazada") is False)
    rej = prom2.rechazar(p2["id"], "no me convence el Δ en held-out",
                         aprobador="humano")
    check("rechazada con motivo", rej.get("rechazada") is True)
    check("rechazo no toca producción", aplicados2 == [])
    arch = prom2.inspeccionar(p2["id"])
    check("archivada con motivo",
          arch["estado"] == ESTADO_RECHAZADA
          and arch["motivo_rechazo"] == "no me convence el Δ en held-out")
    check("historial conserva la rechazada",
          any(h["estado"] == ESTADO_RECHAZADA
              for h in prom2.historial()))

    # 9. GOBERNANZA 27/9 ~22:50 (decisión del usuario): la fase 2.3 queda
    # SUPERADA para el meta-loop. Un PASS de la puerta con mejora medida
    # (Δ_ho > 0 estricto, Δ_in ≥ 0, frenos sanos) se AUTO-ADOPTA sin
    # esperar al humano; lo igual o peor se rechaza con números. El
    # camino manual (proponer/aprobar) sigue existiendo para promociones
    # manuales.
    d = tempfile.mkdtemp(prefix="alma_fase23_ml_")
    db = os.path.join(d, "ml.db")
    pres = PresupuestoFase2(db, tope_mensual_usd=0.0)
    ml = MetaLoop(db, presupuesto=pres, rondas=2)
    el = EventLog(os.path.join(d, "eventos.db"))
    ml.event_log = el  # el setter propaga al promotor
    check("event_log propagado al promotor",
          ml.promotor.event_log is el)
    vigente0 = ml.scaffold_vigente()
    orig_evaluar = MetaLoop._evaluar

    def fake_pass(scaffold, replicas, cache):
        # Panel cableado (recableado 16/10/2026, recalibración δ v3):
        # train = TRAIN_REPS del metaloop. Δ = 6 en ambos splits, sobre
        # el piso nuevo de auto-adopción (5,4781 totales).
        es_train = tuple(replicas) == tuple(TRAIN_REPS)
        v = (90.0 if es_train else 95.0) if scaffold == vigente0 else (
            84.0 if es_train else 89.0)
        return (v, [v] * len(replicas))

    MetaLoop._evaluar = staticmethod(fake_pass)
    try:
        rr = ml.correr(seed=11, rondas=2, bloqueante=True)
    finally:
        MetaLoop._evaluar = orig_evaluar
    check("corrida aceptada", rr.get("aceptado") is True)
    check("mejora medida -> auto-adopción (sin esperar al humano)",
          ml.scaffold_vigente() != vigente0)
    check("sin staging pendiente", ml.promotor.pendiente() is None)
    check("notificación encolada para el usuario",
          any(n["tipo"] == "auto_adopcion"
              for n in ml.promotor.notificaciones_pendientes()))
    # Camino manual: sigue vivo para promociones manuales.
    p9 = ml.promotor.proponer(scaffold_antes=ml.scaffold_vigente(),
                              scaffold_despues=vigente0,
                              delta_in=0.0, delta_ho=0.0,
                              motivo_puerta="manual", regla="manual")
    check("camino manual sigue existiendo", p9.get("id") is not None)
    ap = ml.promotor.aprobar(p9["id"], aprobador="humano")
    check("el humano aprueba -> commit",
          ap.get("aprobada") is True
          and ml.scaffold_vigente() == vigente0)
    tipos = [e["tipo"] for e in el.ciclo()]
    check("event log: auto_adopcion asentada",
          "auto_adopcion" in tipos)
    check("event log: aprobación manual con actor humano",
          any(e["tipo"] == "promocion_aprobada"
              and e["actor"] == "humano" for e in el.ciclo()))

    # 10. Integración MetaLoop: gate FAIL -> ni staging ni auto-adopción.
    d4 = tempfile.mkdtemp(prefix="alma_fase23_mlf_")
    db4 = os.path.join(d4, "ml.db")
    ml4 = MetaLoop(db4, presupuesto=PresupuestoFase2(
        db4, tope_mensual_usd=0.0), rondas=2)
    vigente4 = ml4.scaffold_vigente()

    def fake_fail(scaffold, replicas, cache):
        es_train = tuple(replicas) == tuple(TRAIN_REPS)
        v = (90.0 if es_train else 95.0) if scaffold == vigente4 else (
            95.0 if es_train else 96.0)  # regresión en ambos
        return (v, [v] * len(replicas))

    MetaLoop._evaluar = staticmethod(fake_fail)
    try:
        ml4.correr(seed=12, rondas=2, bloqueante=True)
    finally:
        MetaLoop._evaluar = orig_evaluar
    check("FAIL de la puerta no crea staging",
          ml4.promotor.pendiente() is None)
    check("FAIL no toca el scaffold",
          ml4.scaffold_vigente() == vigente4)
    check("FAIL no adopta ni encola aviso",
          ml4.promotor.notificaciones_pendientes() == [])

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
