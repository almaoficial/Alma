#!/usr/bin/env python3
"""ALMA-EXP63: ¿optimizar pass^k (consistencia) en vez de media de un intento?

De Shunyu Yao (τ-bench): el éxito se mide como pass^k — fracción de
tareas que salen bien en k intentos — no como media de un intento.

Diseño:
- Control: tratamiento EXP51 verbatim (k=None en passk.py — señal de
  aprendizaje cruda).
- Tratamiento: idéntico salvo la señal de aprendizaje del Thompson,
  que pasa a puntaje pass^k (k=3). Contabilidad de regret intacta
  (sorteo único crudo, mismas seeds) → comparación pareada honesta.
- 5 réplicas (rep_id 0..4), scaffold = DEFAULT_SCAFFOLD (n0=4,
  umbral_base=1 — política vigente validada).

Hipótesis pre-registrada (H): el Thompson alimentado con consistencia
elige brazos estables y baja el regret: efecto_medio < 0, donde efecto
= reg_trat − reg_ctrl por réplica.

Criterio: PASS ssi efecto_medio < 0 (con IC95). Si FAIL o no medible
limpio, se CONSERVA el objetivo anterior (media de un intento) y se
documenta — no se cambia la vara.

Secundario: tasa de bloques consistentes — por réplica se corren 3
seeds extra (rep_id, +1000, +2000) por brazo; bloque consistente ssi
reg_bloque == 0 en las 3. Reporta tasas; no decide el veredicto.

US$0, mock, sin API keys.
"""

import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # alma-prototype/
sys.path.insert(0, HERE)
import run_experiment47 as e47  # noqa: E402
from alma_service.scaffold import DEFAULT_SCAFFOLD  # noqa: E402
from passk import correr_replica_passk, K_PASS  # noqa: E402

OUT = os.path.join(HERE, "resultados", "exp63-passk-20260927")
N_REPLICAS = 5
SEEDS_EXTRA = (0, 1000, 2000)


def ic95(xs):
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, m, m
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    d = 1.96 * sd / math.sqrt(n)
    return m, m - d, m + d


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)

    # --- 1. PRE-REGISTRO (antes de cualquier réplica) ---
    prereg = {
        "experimento": "ALMA-EXP63 pass^k (Yao τ-bench)",
        "fecha": "2026-09-27",
        "hipotesis": ("el Thompson alimentado con consistencia pass^k"
                      " (k=3) baja el regret vs la señal cruda"),
        "diseno": {
            "control": "tratamiento EXP51 verbatim (passk k=None)",
            "tratamiento": "idéntico salvo señal de aprendizaje pass^3",
            "replicas": N_REPLICAS, "rep_ids": list(range(N_REPLICAS)),
            "scaffold": dict(DEFAULT_SCAFFOLD),
            "contabilidad": ("regret con sorteo único crudo, mismas"
                             " seeds — comparación pareada honesta"),
        },
        "criterio_veredicto": ("PASS ssi efecto_medio < 0, donde efecto ="
                               " reg_trat − reg_ctrl por réplica (con IC95)."
                               " Si FAIL o no medible limpio, se conserva"
                               " el objetivo anterior y se documenta."),
        "secundario": ("tasa de bloques consistentes (reg_bloque==0 en"
                       " 3 seeds por réplica); reporta, no decide"),
        "timestamp": time.time(),
    }
    with open(os.path.join(OUT, "preregistro.json"), "w",
              encoding="utf-8") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)

    items = e47.construir_stream()
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
    sc = dict(DEFAULT_SCAFFOLD)

    # --- 2. Corridas pareadas ---
    efectos = []
    por_replica = []
    consist_ctrl = []
    consist_trat = []
    for r in range(N_REPLICAS):
        ctrl = correr_replica_passk(r, items, tasas, sc, k=None)
        trat = correr_replica_passk(r, items, tasas, sc, k=K_PASS)
        efecto = trat["reg_pol"] - ctrl["reg_pol"]
        efectos.append(efecto)
        por_replica.append({"rep": r, "reg_ctrl": ctrl["reg_pol"],
                            "reg_trat": trat["reg_pol"],
                            "efecto": efecto})
        # Secundario: bloques consistentes (3 seeds por réplica).
        for brazo, acum in (("ctrl", consist_ctrl),
                            ("trat", consist_trat)):
            kk = None if brazo == "ctrl" else K_PASS
            n_bloques = len(ctrl["reg_pol_bloques"])
            for bi in range(n_bloques):
                regs = [correr_replica_passk(r + s, items, tasas, sc,
                                             k=kk)["reg_pol_bloques"][bi]
                        for s in SEEDS_EXTRA]
                acum.append(1.0 if all(x == 0 for x in regs) else 0.0)

    m, lo, hi = ic95(efectos)
    pasa = m < 0
    tasa_ctrl = (sum(consist_ctrl) / len(consist_ctrl)
                 if consist_ctrl else 0.0)
    tasa_trat = (sum(consist_trat) / len(consist_trat)
                 if consist_trat else 0.0)

    veredicto = {
        "experimento": "ALMA-EXP63",
        "veredicto": "PASS" if pasa else "FAIL",
        "efecto_medio": round(m, 4),
        "ic95": [round(lo, 4), round(hi, 4)],
        "efectos_por_replica": [round(e, 2) for e in efectos],
        "tasa_bloques_consistentes_ctrl": round(tasa_ctrl, 4),
        "tasa_bloques_consistentes_trat": round(tasa_trat, 4),
        "regla": ("PASS ssi efecto_medio < 0. " +
                  ("se cumple" if pasa else
                   "NO se cumple: se conserva el objetivo anterior"
                   " (media de un intento) y se documenta")),
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "veredicto.json"), "w",
              encoding="utf-8") as f:
        json.dump(veredicto, f, indent=2, ensure_ascii=False)
    with open(os.path.join(OUT, "por_replica.json"), "w",
              encoding="utf-8") as f:
        json.dump(por_replica, f, indent=2, ensure_ascii=False)
    return veredicto


if __name__ == "__main__":
    v = main()
    print(f"EXP63: {v['veredicto']} — efecto_medio={v['efecto_medio']}"
          f" IC95={v['ic95']}")
