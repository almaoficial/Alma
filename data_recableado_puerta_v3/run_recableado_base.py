"""Evaluación del scaffold base sobre el panel nuevo de la puerta.

Recableado 16/10/2026 tras la recalibración de δ v3 (pre-registro
preregistro-recalibracion-delta-v3-2026-10-16.md §5.5: «antes de
evaluar cualquier candidato con el panel nuevo, el scaffold base
debe ser evaluado sobre ese panel (parte del recableado)»).

Qué hace, en orden:
  1. Verifica el cableado vivo importando los módulos: panel 18/12
     (train [400..417], held-out [600..611]) en metaloop,
     PISO_RUIDO_DELTA = 5,4781 (totales) en gate, E3 [500,501].
  2. Ancla de identidad: evalúa el scaffold base (DEFAULT_SCAFFOLD)
     sobre el panel histórico [0,1,2]+[3,4] y verifica los reg_pol
     del Paso 0 de las calibraciones v1/v2/v3 (71/83/90/84/81) —
     prueba de que es el mismo scaffold y el mismo validador.
  3. Evalúa el scaffold base sobre el panel nuevo COMPLETO, dos
     veces con cachés frescos (determinismo por réplica).
  4. Δ base contra base por la ruta real de la puerta
     (PuertaDosSplits.decidir + decidir_auto_adopcion): debe dar
     Δ = 0 en ambos splits (bajo el piso nuevo, sin anomalía).
  5. Contexto: media base sobre E3 [500,501] (panel sin cambio).

NO evalúa ningún candidato. NO corre el meta-loop. Solo lectura del
validador congelado (e47/e56 vía MetaLoop._evaluar). US$0.

Salida: data_recableado_puerta_v3/resultados_base.json
"""

import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from alma_service.metaloop import MetaLoop, TRAIN_REPS, HELDOUT_REPS  # noqa: E402
from alma_service.gate import (  # noqa: E402
    PuertaDosSplits, decidir_auto_adopcion, PISO_RUIDO_DELTA)
from alma_service.puerta_e3 import E3_REPS  # noqa: E402
from alma_service.scaffold import DEFAULT_SCAFFOLD  # noqa: E402

BASE = dict(DEFAULT_SCAFFOLD)
REGS_PASO0 = [71.0, 83.0, 90.0, 84.0, 81.0]  # v1/v2/v3, reps [0..4]


def main():
    t0 = time.time()
    salida = {"tipo": "evaluacion_base_recableado_puerta_v3",
              "fecha": "2026-10-16"}

    # 1. Cableado vivo.
    salida["cableado"] = {
        "train_reps": TRAIN_REPS,
        "heldout_reps": HELDOUT_REPS,
        "e3_reps": list(E3_REPS),
        "piso_ruido_delta": PISO_RUIDO_DELTA,
        "piso_escala": "totales (equivale a 0,2283 en escala delta)",
    }
    assert TRAIN_REPS == list(range(400, 418)), "train no es [400..417]"
    assert HELDOUT_REPS == list(range(600, 612)), "held-out no es [600..611]"
    assert list(E3_REPS) == [500, 501], "E3 cambió"
    assert PISO_RUIDO_DELTA == 5.4781, "el piso cableado no es 5,4781"
    print("[1] cableado verificado: panel 18/12, E3 [500,501], "
          "piso 5,4781 totales", flush=True)

    # 2. Ancla de identidad sobre el panel histórico.
    _, regs_hist = MetaLoop._evaluar(BASE, [0, 1, 2, 3, 4], {})
    salida["ancla_panel_historico"] = {
        "reps": [0, 1, 2, 3, 4], "reg_pol": regs_hist,
        "esperado_paso0_calibraciones": REGS_PASO0,
        "identico": regs_hist == REGS_PASO0,
    }
    assert regs_hist == REGS_PASO0, (
        f"ancla FALLA: {regs_hist} != {REGS_PASO0} — el scaffold o el "
        "validador no son los de la calibración; DETENER")
    print(f"[2] ancla OK: reg_pol [0..4] = {regs_hist} "
          "(idénticos al Paso 0 de v1/v2/v3)", flush=True)

    # 3. Evaluación base sobre el panel nuevo, dos veces (cachés frescos).
    media_tr1, regs_tr1 = MetaLoop._evaluar(BASE, TRAIN_REPS, {})
    media_ho1, regs_ho1 = MetaLoop._evaluar(BASE, HELDOUT_REPS, {})
    media_tr2, regs_tr2 = MetaLoop._evaluar(BASE, TRAIN_REPS, {})
    media_ho2, regs_ho2 = MetaLoop._evaluar(BASE, HELDOUT_REPS, {})
    determinismo = (regs_tr1 == regs_tr2 and regs_ho1 == regs_ho2
                    and media_tr1 == media_tr2 and media_ho1 == media_ho2)
    salida["panel_nuevo"] = {
        "train": {"reps": TRAIN_REPS, "reg_pol": regs_tr1,
                  "media": media_tr1},
        "heldout": {"reps": HELDOUT_REPS, "reg_pol": regs_ho1,
                    "media": media_ho1},
        "segunda_evaluacion_identica": determinismo,
    }
    assert determinismo, "NO determinismo en el panel nuevo; DETENER"
    print(f"[3] base en panel nuevo: media train = {media_tr1:.4f} "
          f"(18 reps), media held-out = {media_ho1:.4f} (12 reps); "
          "segunda evaluación idéntica", flush=True)

    # 4. Δ base contra base por la ruta real de la puerta.
    puerta = PuertaDosSplits.decidir(media_tr1, media_ho1,
                                     media_tr1, media_ho1)
    auto, motivo_auto, req_si = decidir_auto_adopcion(
        puerta["delta_in"], puerta["delta_ho"])
    salida["delta_base_contra_base"] = {
        "delta_in": puerta["delta_in"], "delta_ho": puerta["delta_ho"],
        "puerta_aceptado": puerta["aceptado"], "puerta_motivo": puerta["motivo"],
        "auto_adopcion": {"auto": auto, "motivo": motivo_auto,
                          "requiere_si": req_si},
        "bajo_el_piso_nuevo": max(puerta["delta_in"],
                                  puerta["delta_ho"]) <= PISO_RUIDO_DELTA,
    }
    assert puerta["delta_in"] == 0.0 and puerta["delta_ho"] == 0.0, (
        "Δ base/base != 0 — anomalía; DETENER")
    print(f"[4] Δ base/base: delta_in = {puerta['delta_in']}, "
          f"delta_ho = {puerta['delta_ho']} (bajo el piso nuevo; "
          f"puerta: {puerta['motivo']})", flush=True)

    # 5. Contexto E3 (panel sin cambio): media base.
    media_e3, regs_e3 = MetaLoop._evaluar(BASE, list(E3_REPS), {})
    salida["e3_contexto"] = {"reps": list(E3_REPS), "reg_pol": regs_e3,
                             "media": media_e3}
    print(f"[5] E3 [500,501] (sin cambio): reg_pol base = {regs_e3}, "
          f"media = {media_e3:.4f}", flush=True)

    salida["duracion_s"] = round(time.time() - t0, 3)
    salida["costo_usd"] = 0
    destino = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "resultados_base.json")
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    print(f"[ok] resultados en {destino} "
          f"({salida['duracion_s']} s, US$0)", flush=True)


if __name__ == "__main__":
    main()
