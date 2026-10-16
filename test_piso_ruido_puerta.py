"""Tests del cableado del piso de ruido en la puerta (11/10/2026).

Pre-registro: ~/workspace/alma-prototype/metaloop_preregistro_piso_ruido_puerta.json

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_piso_ruido_puerta.py

Cubre: decidir_auto_adopcion (gate.py) — la capa de gobernanza que
exige max(Δ_in,Δ_ho) > 0.53 para auto-adoptar. La puerta pura
(aceptar/PuertaDosSplits) queda intacta: decide elegibilidad, no
adopción.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.gate import (
    aceptar, decidir_auto_adopcion, PISO_RUIDO_DELTA,
    REGLA, REGLA_AUTO_ADOPCION)

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def main():
    # 1. La banda: mejora real pero bajo el piso -> no auto-adopción,
    #    flag de «sí» explícito.
    auto, motivo, req_si = decidir_auto_adopcion(0.3, 0.2)
    check("banda: no auto-adopta",
          auto is False and req_si is True
          and "piso de ruido" in motivo)

    # 2. El borde: max == 0.53 NO supera (es <=) -> requiere sí.
    auto, motivo, req_si = decidir_auto_adopcion(0.53, 0.0)
    check("borde: max==0.53 requiere sí explícito",
          auto is False and req_si is True)

    # 3. Sobre la banda: comportamiento anterior intacto.
    auto, motivo, req_si = decidir_auto_adopcion(0.6, 0.1)
    check("sobre la banda: auto-adopta como antes",
          auto is True and req_si is False)
    auto, _, req_si = decidir_auto_adopcion(0.0, 5.0)
    check("sobre la banda solo en held-out: auto-adopta",
          auto is True and req_si is False)

    # 4. Regresión: rechazo normal, sin flag de sí (como siempre).
    auto, motivo, req_si = decidir_auto_adopcion(-0.1, 0.9)
    check("regresión: rechaza sin flag de sí",
          auto is False and req_si is False
          and "regresión" in motivo)

    # 5. Sin mejora estricta: rechazo normal, sin flag de sí.
    auto, _, req_si = decidir_auto_adopcion(0.0, 0.0)
    check("deltas cero: rechaza sin flag de sí",
          auto is False and req_si is False)

    # 6. La puerta pura NO cambió: decide elegibilidad, no adopción.
    ok, _ = aceptar(0.3, 0.2)
    check("puerta pura intacta: aceptar(0.3, 0.2) sigue True",
          ok is True)
    check("REGLA de la puerta pura intacta",
          REGLA == "delta_in>=0 & delta_ho>=0 & max(delta_in,delta_ho)>0")

    # 7. Constantes: el piso y la regla de auto-adopción.
    check("PISO_RUIDO_DELTA == 0.53", PISO_RUIDO_DELTA == 0.53)
    check("REGLA_AUTO_ADOPCION exige >0.53",
          "0.53" in REGLA_AUTO_ADOPCION
          and "max(delta_in,delta_ho)>0.53" in REGLA_AUTO_ADOPCION)

    # 8. Solo endurece: ningún caso que la puerta pura rechaza pasa a
    #    auto-adoptarse (barrido de grilla).
    solo_endurece = True
    d = -0.5
    while d <= 1.0:
        e = -0.5
        while e <= 1.0:
            ok_pura, _ = aceptar(round(d, 2), round(e, 2))
            auto, _, _ = decidir_auto_adopcion(round(d, 2), round(e, 2))
            if auto and not ok_pura:
                solo_endurece = False
            e += 0.05
        d += 0.05
    check("solo endurece: auto=True implica puerta pura True",
          solo_endurece)

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
