#!/usr/bin/env python3
"""ALMA-EXP57: ablación del scaffold evolucionado + replicación RSO con otro seed.

Parte A: evaluar EVO con cada keep revertido individualmente (V1/V2/V3) en
train [0,1,2] y held-out [3,4]. Medición, no optimización.

Parte B: re-correr el loop RSO completo con seed de propuestas 57 (mismo
protocolo: 24 rondas, keep estricto en train, held-out no visto).
Antes, chequeo de validez: el loop con seed 56 debe reproducir la trayectoria
de EXP56 bit-idéntica.

Toda la maquinaria se IMPORTA de exp56_rso/run_experiment56.py (no se copia,
no se toca). Regla de oro: el validador queda congelado.

Uso: python3 run_experiment57.py
"""

import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP56_DIR = os.path.join(os.path.dirname(HERE), "exp56_rso")
sys.path.insert(0, EXP56_DIR)
sys.path.insert(0, os.path.dirname(HERE))  # alma-prototype/ (run_experiment47)
import run_experiment56 as e56  # noqa: E402

OUT = HERE
EXP56_REPORT = os.path.join(EXP56_DIR, "report.json")

EVO = {"umbral_base": 1, "umbral_divisor": 2, "gate_margin": 0.0,
       "n0": 4, "decay": 0.5}
VARIANTES_A = {
    "INIT": dict(e56.SC_INIT),
    "EVO": dict(EVO),
    "V1_revert_n0": {"umbral_base": 1, "umbral_divisor": 2,
                     "gate_margin": 0.0, "n0": 2, "decay": 0.5},
    "V2_revert_ub": {"umbral_base": 2, "umbral_divisor": 2,
                     "gate_margin": 0.0, "n0": 4, "decay": 0.5},
    "V3_revert_ud": {"umbral_base": 1, "umbral_divisor": 3,
                     "gate_margin": 0.0, "n0": 4, "decay": 0.5},
}
PROP_SEED_B = 57


def correr_loop(prop_seed, n_rondas, items, tasas):
    """Loop RSO fiel al de EXP56 (usa e56.proponer/e56.evaluar)."""
    prop_rng = random.Random(prop_seed)
    actual = dict(e56.SC_INIT)
    cache = {}
    metrica_actual, _ = e56.evaluar(actual, items, tasas,
                                    e56.TRAIN_REPS, cache)
    trayectoria = []
    n_keeps = 0
    for ronda in range(1, n_rondas + 1):
        dim, nuevo_val = e56.proponer(prop_rng, actual)
        mutante = dict(actual)
        mutante[dim] = nuevo_val
        metrica_mut, _ = e56.evaluar(mutante, items, tasas,
                                     e56.TRAIN_REPS, cache)
        keep = bool(metrica_mut < metrica_actual)
        trayectoria.append({
            "ronda": ronda, "dim": dim,
            "de": actual[dim], "a": nuevo_val,
            "metrica_antes": round(metrica_actual, 4),
            "metrica_despues": round(metrica_mut, 4),
            "keep": keep,
        })
        if keep:
            actual = mutante
            metrica_actual = metrica_mut
            n_keeps += 1
    return actual, trayectoria, n_keeps, cache


def main():
    t0 = time.time()
    items = e56.e47.construir_stream()
    tasas = json.load(open(e56.e47.TASAS_PATH, encoding="utf-8"))

    # --- 0. Sanidad bit-idéntica del puerto (heredada de EXP56) ---
    print("Sanidad: puerto parametrizado con SC_INIT vs EXP51...")
    for r in range(5):
        got = e56.correr_replica_param(
            r, items, tasas, dict(e56.SC_INIT))["reg_pol"]
        exp = e56.EXP51_TRAT_TOTALES[r]
        assert abs(got - exp) < 1e-9, f"rep {r}: {got} vs {exp}"
    print("  OK: bit-idéntico en las 5 réplicas.")

    # --- Parte A: ablación ---
    print("\nParte A: ablación (INIT, EVO, V1, V2, V3)...")
    cache_a = {}
    res_a = {}
    for nombre, sc in VARIANTES_A.items():
        m_tr, regs_tr = e56.evaluar(sc, items, tasas, e56.TRAIN_REPS,
                                   cache_a)
        m_ho, regs_ho = e56.evaluar(sc, items, tasas, e56.HELDOUT_REPS,
                                    cache_a)
        res_a[nombre] = {
            "scaffold": sc,
            "train_media": round(m_tr, 4),
            "train_por_replica": [round(x, 3) for x in regs_tr],
            "heldout_media": round(m_ho, 4),
            "heldout_por_replica": [round(x, 3) for x in regs_ho],
        }
        print(f"  {nombre:12s} train {m_tr:7.3f}  held-out {m_ho:7.3f} "
              f"(ho por réplica {[round(x,1) for x in regs_ho]})")
    # Chequeo de consistencia con EXP56
    assert abs(res_a["EVO"]["heldout_media"] - 83.00) < 1e-6, \
        "EVO held-out no coincide con EXP56"
    assert abs(res_a["INIT"]["heldout_media"] - 87.50) < 1e-6, \
        "INIT held-out no coincide con EXP56"

    mejora_evo = res_a["INIT"]["heldout_media"] - res_a["EVO"]["heldout_media"]
    deltas = {}
    for v in ["V1_revert_n0", "V2_revert_ub", "V3_revert_ud"]:
        mejora_v = (res_a["INIT"]["heldout_media"]
                    - res_a[v]["heldout_media"])
        deltas[v] = {
            "mejora_heldout": round(mejora_v, 4),
            "delta_vs_evo": round(mejora_evo - mejora_v, 4),
        }

    # --- Parte B: validez (seed 56 reproduce EXP56) ---
    print("\nParte B0: validez — loop con seed 56 vs trayectoria EXP56...")
    rep56 = json.load(open(EXP56_REPORT, encoding="utf-8"))
    evo56, tray56, keeps56, cache56 = correr_loop(
        56, e56.N_RONDAS, items, tasas)
    assert keeps56 == rep56["n_keeps"] == 3, \
        f"keeps {keeps56} vs {rep56['n_keeps']}"
    assert evo56 == rep56["scaffold_final"], \
        f"scaffold {evo56} vs {rep56['scaffold_final']}"
    for t_new, t_old in zip(tray56, rep56["trayectoria"]):
        assert (t_new["ronda"], t_new["dim"], t_new["de"], t_new["a"],
                t_new["keep"]) == \
               (t_old["ronda"], t_old["dim"], t_old["de"], t_old["a"],
                t_old["keep"]), f"trayectoria difiere en ronda {t_new['ronda']}"
    m_tr56, _ = e56.evaluar(evo56, items, tasas, e56.TRAIN_REPS, cache56)
    m_ho56, _ = e56.evaluar(evo56, items, tasas, e56.HELDOUT_REPS, cache56)
    assert abs(m_tr56 - 79.3333) < 1e-3 and abs(m_ho56 - 83.00) < 1e-6
    print("  OK: trayectoria, scaffold, train y held-out bit-idénticos a "
          "EXP56. Harness válido.")

    # --- Parte B: loop con seed 57 ---
    print("\nParte B: loop RSO con seed de propuestas 57...")
    evo57, tray57, keeps57, cache57 = correr_loop(
        PROP_SEED_B, e56.N_RONDAS, items, tasas)
    m_init_tr, regs_init_tr = e56.evaluar(dict(e56.SC_INIT), items, tasas,
                                         e56.TRAIN_REPS, cache57)
    m_evo_tr, regs_evo_tr = e56.evaluar(evo57, items, tasas,
                                       e56.TRAIN_REPS, cache57)
    m_init_ho, regs_init_ho = e56.evaluar(dict(e56.SC_INIT), items, tasas,
                                         e56.HELDOUT_REPS, cache57)
    m_evo_ho, regs_evo_ho = e56.evaluar(evo57, items, tasas,
                                       e56.HELDOUT_REPS, cache57)
    mejora_tr_b = m_init_tr - m_evo_tr
    mejora_ho_b = m_init_ho - m_evo_ho
    pasa_b = bool(mejora_ho_b > 0)

    print(f"  keeps: {keeps57}/{e56.N_RONDAS}")
    print(f"  scaffold final B: {evo57}")
    print(f"  train [0,1,2]: {m_init_tr:.3f} -> {m_evo_tr:.3f} "
          f"({mejora_tr_b:+.3f})")
    print(f"  held-out [3,4]: {m_init_ho:.3f} -> {m_evo_ho:.3f} "
          f"({mejora_ho_b:+.3f})")
    for t in tray57:
        print(f"    r{t['ronda']:02d}: {t['dim']} {t['de']}->{t['a']} "
              f"{'KEEP' if t['keep'] else '....'} "
              f"({t['metrica_antes']:.2f}->{t['metrica_despues']:.2f})")
    print("  PASS_B:" , pasa_b)

    report = {
        "experimento": "ALMA-EXP57: ablación RSO + replicación seed 57 "
                       "(mock, US$0)",
        "preregistro": "preregistro.md (mismo directorio)",
        "validez_seed56_reproduce_exp56": True,
        "parte_a_ablacion": {"variantes": res_a,
                             "mejora_heldout_evo": round(mejora_evo, 4),
                             "deltas": deltas},
        "parte_b": {
            "prop_seed": PROP_SEED_B, "n_rondas": e56.N_RONDAS,
            "n_keeps": keeps57, "scaffold_final": evo57,
            "trayectoria": tray57,
            "train": {"init_media": round(m_init_tr, 4),
                      "init_por_replica": [round(x, 3)
                                           for x in regs_init_tr],
                      "evo_media": round(m_evo_tr, 4),
                      "evo_por_replica": [round(x, 3)
                                          for x in regs_evo_tr],
                      "mejora": round(mejora_tr_b, 4)},
            "heldout": {"init_media": round(m_init_ho, 4),
                        "init_por_replica": [round(x, 3)
                                             for x in regs_init_ho],
                        "evo_media": round(m_evo_ho, 4),
                        "evo_por_replica": [round(x, 3)
                                            for x in regs_evo_ho],
                        "mejora": round(mejora_ho_b, 4)},
            "criterio": "PASS_B ssi media_heldout(evo_B) < "
                        "media_heldout(INIT)",
            "veredicto": "PASS" if pasa_b else "FAIL",
            "mismo_scaffold_que_exp56": bool(evo57 == EVO),
        },
        "costo_total_usd": 0.0,
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nreport.json escrito. Duración: {report['duracion_s']}s. "
          "Costo: US$0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
