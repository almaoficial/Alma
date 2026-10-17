"""Tests del cableado del piso de ruido en la puerta (11/10/2026).

Pre-registro: ~/workspace/alma-prototype/metaloop_preregistro_piso_ruido_puerta.json

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_piso_ruido_puerta.py

Cubre: decidir_auto_adopcion (gate.py) — la capa de gobernanza que
exige max(Δ_in,Δ_ho) > piso para auto-adoptar. La puerta pura
(aceptar/PuertaDosSplits) queda intacta: decide elegibilidad, no
adopción.

Actualizado en el recableado del 16/10/2026 (recalibración de δ v3,
adopción primaria §8, commit b834e3d): el piso vigente es 5,4781 en
TOTALES — la escala en que la ruta de evaluación produce los Δ —
equivalente a δ = 0,2283 en escala δ (media por bloque). Los casos
de esta suite usan Δ en totales, la escala real de la comparación
(antes del recableado usaban la escala δ del 0.53 histórico).

Actualizado en el recableado del ciclo L1 (16/10/2026,
pre-registro preregistro-L1-panel-grande-2026-10-16.md; evento
recalibracion_delta_L1 del ledger): el piso vigente es 2,7391 en
TOTALES ≡ δ = 0,1141 en escala δ, medido a panel 72/48. El caso
de banda usa Δ=2,0 (con el piso nuevo, el Δ=3,0 de la versión v3
ya auto-adoptaría); el borde es 2,7391.
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
    #    flag de «sí» explícito. (Δ en totales, la escala de la puerta.)
    auto, motivo, req_si = decidir_auto_adopcion(2.0, 1.0)
    check("banda: no auto-adopta",
          auto is False and req_si is True
          and "piso de ruido" in motivo)

    # 2. El borde: max == 2.7391 NO supera (es <=) -> requiere sí.
    auto, motivo, req_si = decidir_auto_adopcion(2.7391, 0.0)
    check("borde: max==2.7391 (totales) requiere sí explícito",
          auto is False and req_si is True)

    # 3. Sobre la banda: comportamiento anterior intacto.
    auto, motivo, req_si = decidir_auto_adopcion(6.0, 1.0)
    check("sobre la banda: auto-adopta como antes",
          auto is True and req_si is False)
    auto, _, req_si = decidir_auto_adopcion(0.0, 9.0)
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
    #    Par congelado L1: (0,1141 escala δ ; 2,7391 totales); el
    #    cableado es el miembro en totales, la escala de la comparación.
    check("PISO_RUIDO_DELTA == 2.7391 (totales)",
          PISO_RUIDO_DELTA == 2.7391)
    check("REGLA_AUTO_ADOPCION exige >2.7391",
          "2.7391" in REGLA_AUTO_ADOPCION
          and "max(delta_in,delta_ho)>2.7391" in REGLA_AUTO_ADOPCION)

    # 8. Solo endurece: ningún caso que la puerta pura rechaza pasa a
    #    auto-adoptarse (barrido de grilla en totales, cubriendo la
    #    banda completa y casos sobre el piso nuevo).
    solo_endurece = True
    d = -1.0
    while d <= 9.0:
        e = -1.0
        while e <= 9.0:
            ok_pura, _ = aceptar(round(d, 2), round(e, 2))
            auto, _, _ = decidir_auto_adopcion(round(d, 2), round(e, 2))
            if auto and not ok_pura:
                solo_endurece = False
            e += 0.25
        d += 0.25
    check("solo endurece: auto=True implica puerta pura True",
          solo_endurece)

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
