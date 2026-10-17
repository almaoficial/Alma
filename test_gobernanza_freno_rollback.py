"""Tests del arreglo de gobernanza 2026-10-16: desbloqueo del freno
con token humano y rollback que camina adopciones.

Origen: dos hallazgos de una auditoría externa (ChatGPT), verificados
en el código antes de arreglarlos:

1. desbloquear_freno(origen="humano") no comprobaba autorización: la
   etiqueta venía «humano» por defecto y cualquier llamador levantaba
   el freno que existe para esperar revisión humana. Ahora hace falta
   el token de la variable de entorno ALMA_TOKEN_HUMANO (fail-closed:
   sin token configurado, todo se rechaza) y `origen` es solo una
   etiqueta de auditoría.

2. revertir() tomaba las dos últimas filas del historial; como el
   propio rollback se asentaba como versión nueva, el segundo
   rollback restauraba la versión que el primero acababa de sacar.
   Ahora deshace la última adopción EN EFECTO (pila de adopciones):
   el segundo rollback deshace la adopción anterior, nunca resucita
   la revertida.

La semántica completa está declarada en
arreglo-freno-rollback-2026-10-16.md.

Las adopciones de estos tests se asientan por el camino real de
commit del Promotor (MetaLoop._aplicar_promocion con el origen exacto
de auto_adoptar, y MetaLoop._revertir_adopcion con el origen exacto
de Promotor.revertir_adopcion): revertir() lee scaffold_activo, que
es lo único que esos caminos escriben.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_gobernanza_freno_rollback.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.metaloop import MetaLoop
from alma_service.presupuesto import PresupuestoFase2
from alma_service.scaffold import DEFAULT_SCAFFOLD

PASSOS = []
ORIGEN_AUTO = "auto_adopcion gobernada (mejora medida)"
TOKEN_ENV = "ALMA_TOKEN_HUMANO"
SECRETO = "token-fixture-gobernanza"


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def nuevo_loop():
    d = tempfile.mkdtemp(prefix="alma_gob_fr_")
    db = os.path.join(d, "ml.db")
    pres = PresupuestoFase2(db, tope_mensual_usd=0.0)  # mock: costo 0
    return MetaLoop(db, presupuesto=pres, rondas=2)


def tipos_ledger(ml):
    return [e["evento"]["tipo"] for e in ml.ledger_leer()]


def eventos(ml, tipo):
    return [e["evento"] for e in ml.ledger_leer()
            if e["evento"]["tipo"] == tipo]


def adoptar(ml, cfg):
    """Asienta una adopción por el camino real de commit."""
    ml._aplicar_promocion(dict(cfg), origen=ORIGEN_AUTO)


def variante(**cambios):
    cfg = dict(DEFAULT_SCAFFOLD)
    cfg.update(cambios)
    return cfg


def activar_freno(ml):
    for _ in range(3):
        ml.registrar_corrida(adoptado=False)
    assert ml.estado_freno()["freno_activo"] is True


def main():
    token_previo = os.environ.get(TOKEN_ENV)

    # ============ 1. Desbloqueo del freno: token o nada ============
    ml = nuevo_loop()
    activar_freno(ml)

    # 1a. Sin token configurado en el entorno: fail-closed. Ni
    #     presentando un token ni con la etiqueta «humano» de siempre.
    os.environ.pop(TOKEN_ENV, None)
    r = ml.desbloquear_freno(origen="humano", token="cualquiera")
    check("sin token configurado -> rechazado",
          r["desbloqueado"] is False)
    check("motivo: token_no_configurado",
          r["motivo"] == "token_no_configurado")
    check("el freno sigue activo tras el rechazo",
          ml.estado_freno()["freno_activo"] is True)
    check("la racha no se tocó", ml.estado_freno()["racha_planas"] == 3)
    check("el rechazo quedó asentado en el ledger",
          "metaloop_freno_desbloqueo_rechazado" in tipos_ledger(ml))
    ev = eventos(ml, "metaloop_freno_desbloqueo_rechazado")[-1]
    check("el rechazo asienta su motivo",
          ev["motivo"] == "token_no_configurado")

    # 1b. Con token configurado: la llamada VIEJA (solo la etiqueta
    #     origen="humano", sin token) ya no autoriza nada.
    os.environ[TOKEN_ENV] = SECRETO
    r = ml.desbloquear_freno(origen="humano")
    check("la etiqueta origen sola ya no desbloquea",
          r["desbloqueado"] is False and r["motivo"] == "token_invalido")
    check("el freno sigue activo", ml.estado_freno()["freno_activo"])

    # 1c. Token incorrecto -> rechazado y asentado.
    r = ml.desbloquear_freno(origen="humano", token="no-es-este")
    check("token incorrecto -> rechazado",
          r["desbloqueado"] is False and r["motivo"] == "token_invalido")
    check("racha intacta tras token incorrecto",
          ml.estado_freno()["racha_planas"] == 3)
    n_rechazos = len(eventos(ml, "metaloop_freno_desbloqueo_rechazado"))
    check("los 3 rechazos quedaron asentados", n_rechazos == 3)
    check("ningún desbloqueo asentado todavía",
          "metaloop_freno_desbloqueado" not in tipos_ledger(ml))

    # 1d. Token correcto -> desbloquea, con la etiqueta asentada como
    #     auditoría (no como autorización).
    r = ml.desbloquear_freno(origen="humano", token=SECRETO)
    check("token correcto -> desbloquea", r["desbloqueado"] is True)
    check("freno limpio", r["freno_activo"] is False)
    check("racha en 0", r["racha_planas"] == 0)
    check("desbloqueo asentado en el ledger",
          "metaloop_freno_desbloqueado" in tipos_ledger(ml))
    check("el estado confirma el desbloqueo",
          ml.estado_freno()["freno_activo"] is False)

    # ============ 2. Rollback que camina adopciones ================
    cfg_a = variante(umbral_base=2)
    cfg_b = variante(umbral_base=3)
    cfg_c = variante(n0=6)
    base = dict(DEFAULT_SCAFFOLD)

    # 2a. Secuencia completa: base -> A -> B -> rollback -> rollback
    #     -> tercer intento. El segundo rollback deshace A; NUNCA
    #     restaura B (la que el primero sacó).
    ml2 = nuevo_loop()
    check("vigente inicial = base", ml2.scaffold_vigente() == base)
    adoptar(ml2, cfg_a)
    adoptar(ml2, cfg_b)
    check("vigente = B tras dos adopciones",
          ml2.scaffold_vigente() == cfg_b)
    r1 = ml2.revertir()
    check("1er rollback revierte", r1["revertido"] is True)
    check("1er rollback vuelve a A", r1["scaffold"] == cfg_a)
    check("vigente = A", ml2.scaffold_vigente() == cfg_a)
    r2 = ml2.revertir()
    check("2do rollback revierte (deshace A)", r2["revertido"] is True)
    check("2do rollback vuelve a la base (NO restaura B)",
          r2["scaffold"] == base)
    check("vigente = base", ml2.scaffold_vigente() == base)
    r3 = ml2.revertir()
    check("3er rollback: nada más que deshacer",
          r3["revertido"] is False)
    check("3er rollback trae motivo",
          "adopción" in r3.get("motivo", ""))
    check("la base sigue vigente", ml2.scaffold_vigente() == base)
    rbs = eventos(ml2, "rollback")
    check("el ledger registra los 2 rollbacks", len(rbs) == 2)
    check("restaurados en orden: A, base",
          [e["restaurado"] for e in rbs] == [cfg_a, base])
    check("cada rollback identifica la adopción deshecha",
          all(e.get("adopcion_deshecha_origen") == ORIGEN_AUTO
              for e in rbs))

    # 2b. Intercalado: adoptar A -> rollback -> adoptar C -> rollback
    #     deshace C y vuelve a la base; A no resucita en ningún paso.
    ml3 = nuevo_loop()
    adoptar(ml3, cfg_a)
    r = ml3.revertir()
    check("rollback de A vuelve a la base",
          r["revertido"] is True and ml3.scaffold_vigente() == base)
    adoptar(ml3, cfg_c)
    check("vigente = C", ml3.scaffold_vigente() == cfg_c)
    r = ml3.revertir()
    check("rollback deshace C y vuelve a la base",
          r["revertido"] is True and ml3.scaffold_vigente() == base)
    r = ml3.revertir()
    check("sin adopciones en efecto -> False", r["revertido"] is False)

    # 2c. El deshacer del Promotor en el medio: A y B adoptadas; el
    #     Promotor revierte A (restaura la base por el camino real
    #     _revertir_adopcion) -> ya no queda adopción en efecto y
    #     revertir() se niega con motivo.
    ml4 = nuevo_loop()
    adoptar(ml4, cfg_a)
    adoptar(ml4, cfg_b)
    ml4._revertir_adopcion(dict(base), origen="revertir_adopcion id=1")
    check("vigente = base tras el revert del Promotor",
          ml4.scaffold_vigente() == base)
    r = ml4.revertir()
    check("revertir() tras revert del Promotor -> False",
          r["revertido"] is False)
    check("la base no se tocó", ml4.scaffold_vigente() == base)

    # 2d. Sin adopciones (loop fresco): False con motivo.
    ml5 = nuevo_loop()
    r = ml5.revertir()
    check("sin adopciones -> False", r["revertido"] is False)
    check("motivo presente", bool(r.get("motivo")))

    # Restaurar el entorno tal como estaba.
    if token_previo is None:
        os.environ.pop(TOKEN_ENV, None)
    else:
        os.environ[TOKEN_ENV] = token_previo

    print()
    print(f"{sum(PASSOS)}/{len(PASSOS)} PASS")
    if not all(PASSOS):
        sys.exit(1)


if __name__ == "__main__":
    main()
