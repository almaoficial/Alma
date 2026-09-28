#!/usr/bin/env python3
"""Unit tests del mecanismo E3 (mock, US$0, sin tocar el servicio vivo).

Cada test es una función test_* con asserts planos. Salida: conteo y
lista de fallos (vacía = todo verde).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import puerta_e3 as E  # noqa: E402
from alma_service.gate import aceptar as aceptar_vivo  # noqa: E402

FALLOS = []


def check(nombre, cond, detalle=""):
    if cond:
        print(f"  ok: {nombre}")
    else:
        FALLOS.append(nombre)
        print(f"  FALLO: {nombre} {detalle}")


def t01_dos_splits_suficientes():
    # Parámetro con margen cómodo: E3 no exigido, acepta sin delta_e3.
    r = E.decidir(5.0, 6.0, delta_e3=None, superficie="parametro")
    check("t01 aceptado", r["aceptado"] is True, r)
    check("t01 e3 no exigido", r["e3_exigido"] is False, r)
    check("t01 e3 no evaluado", r["e3_evaluado"] is False, r)


def t02_margen_fino_exige_e3():
    exigido, motivo = E.exigir_e3(0.5, 6.0, superficie="parametro",
                                 margen_min=2.0)
    check("t02 exigido por margen fino", exigido is True, motivo)


def t03_e3_requerido_y_pasa():
    r = E.decidir(0.5, 6.0, delta_e3=1.5, superficie="parametro")
    check("t03 aceptado con E3", r["aceptado"] is True, r)
    check("t03 e3 evaluado", r["e3_evaluado"] is True, r)


def t04_e3_veta_ante_regresion():
    # E1/E2 pasan, pero el E3 regresa -> rechazo con veto del E3.
    r = E.decidir(0.5, 6.0, delta_e3=-0.5, superficie="parametro")
    check("t04 rechazado", r["aceptado"] is False, r)
    check("t04 motivo menciona E3", "E3" in r["motivo"], r["motivo"])


def t05_dos_splits_fallan_e3_no_consultado():
    # Regresión en E2: rechazo aunque el E3 sería bueno.
    r = E.decidir(5.0, -1.0, delta_e3=10.0, superficie="parametro")
    check("t05 rechazado", r["aceptado"] is False, r)
    check("t05 e3 no evaluado", r["e3_evaluado"] is False, r)


def t06_e3_sin_datos_falla_cerrado():
    # E3 exigido (margen fino) pero sin delta_e3 -> ValueError, no adopción.
    try:
        E.decidir(0.5, 6.0, delta_e3=None, superficie="parametro")
        check("t06 fail-closed", False, "no lanzó ValueError")
    except ValueError as e:
        check("t06 fail-closed", "fail-closed" in str(e), str(e))


def t07_blast_radius_alto_exige_e3():
    # Maquinaria con márgenes cómodos igual exige E3.
    exigido, motivo = E.exigir_e3(8.0, 9.0, superficie="maquinaria")
    check("t07 maquinaria exige E3", exigido is True, motivo)
    exigido2, _ = E.exigir_e3(8.0, 9.0, superficie="nucleo")
    check("t07 nucleo exige E3", exigido2 is True)


def t08_forzar_e3():
    exigido, motivo = E.exigir_e3(8.0, 9.0, superficie="parametro",
                                 forzar_e3=True)
    check("t08 forzado exige E3", exigido is True, motivo)


def t09_mejora_solo_en_e3_acepta():
    # (0, 0, +5): sin regresión en ningún split, mejora estricta en
    # al menos uno de los tres -> acepta (generalización de la regla).
    ok, motivo = E.aceptar_e3(0.0, 0.0, 5.0)
    check("t09 acepta mejora solo en E3", ok is True, motivo)


def t10_sin_mejora_en_ninguno_rechaza():
    ok, motivo = E.aceptar_e3(0.0, 0.0, 0.0)
    check("t10 rechaza (0,0,0)", ok is False, motivo)


def t11_e3_cero_exact_con_mejora_acepta():
    # Δ_e3 = 0.0 exacto no es regresión: acepta si hay mejora en E1/E2.
    ok, motivo = E.aceptar_e3(3.0, 4.0, 0.0)
    check("t11 acepta con E3=0", ok is True, motivo)


def t12_determinismo():
    kw = dict(delta_in=0.5, delta_ho=6.0, delta_e3=1.5,
              superficie="parametro")
    r1 = E.decidir(**kw)
    r2 = E.decidir(**kw)
    check("t12 determinista", r1 == r2)


def t13_superficie_desconocida_error():
    try:
        E.exigir_e3(5.0, 6.0, superficie="inexistente")
        check("t13 superficie inválida", False, "no lanzó ValueError")
    except ValueError:
        check("t13 superficie inválida", True)


def t14_audit_record_campos():
    rec = E.audit_record_e3("subir n0", 0.5, 6.0, 1.5, "parametro",
                            True, "ok", True, True)
    check("t14 tipo", rec["tipo"] == "audit_propuesta_e3", rec)
    for campo in ("delta_in", "delta_ho", "delta_e3", "e3_exigido",
                  "e3_evaluado", "aceptado", "motivo", "regla_e3"):
        check(f"t14 campo {campo}", campo in rec, rec)


def t15_contrato_con_puerta_viva():
    # Sin E3 exigido, decidir() coincide con la puerta viva en (d_in,d_ho).
    casos = [(5.0, 6.0), (0.0, 3.0), (-1.0, 5.0), (0.0, 0.0), (2.5, 2.5)]
    ok = True
    for di, dh in casos:
        vivo_ok, _ = aceptar_vivo(di, dh)
        r = E.decidir(di, dh, superficie="parametro",
                      margen_min=0.0)  # margen 0 -> nunca exige por margen
        # con margen_min=0.0 y deltas >= 0, E3 no exigido salvo forzar
        if r["aceptado"] != vivo_ok:
            ok = False
    check("t15 contrato con puerta viva", ok)


def t16_margen_en_el_borde():
    # min(delta) == margen_min -> NO es fino (se exige solo si < ).
    exigido, _ = E.exigir_e3(2.0, 9.0, superficie="parametro",
                             margen_min=2.0)
    check("t16 borde no exige", exigido is False)


def main():
    tests = sorted([v for k, v in globals().items()
                    if k.startswith("t") and callable(v)],
                   key=lambda f: f.__name__)
    print(f"E3: {len(tests)} tests (mock, US$0)")
    for t in tests:
        t()
    print(f"\n{len(tests) - len(FALLOS)}/{len(tests)} en verde")
    if FALLOS:
        print("FALLOS:", FALLOS)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
