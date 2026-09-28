#!/usr/bin/env python3
"""ALMA-EXP64-skip: follow-up de la ablación del skip con n=20 réplicas held-out.

Reutiliza correr_replica_ablacion de ../exp64-ablacion-20260927/run_exp64.py
SIN modificarla. Tratamientos: control (con skip) vs sin_skip, pareados por
rep_id, réplicas 100..119 (held-out: EXP64 usó 0..4).

Ver preregistro.md (escrito ANTES de correr). Mock, US$0.
"""

import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))  # alma-prototype/
EXP64DIR = os.path.join(os.path.dirname(HERE), "exp64-ablacion-20260927")
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "exp56_rso"))
sys.path.insert(0, EXP64DIR)

import run_exp64 as r64  # noqa: E402
import run_experiment47 as e47  # noqa: E402
import run_experiment56 as e56  # noqa: E402
from alma_service.scaffold import DEFAULT_SCAFFOLD  # noqa: E402

OUT = HERE
REPLICAS = list(range(100, 120))  # 20 held-out
T_CRIT = 2.093  # t_{0.975, gl=19}


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    items = e47.construir_stream()
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
    sc = dict(DEFAULT_SCAFFOLD)

    # --- Sanidad 1: determinismo del control en réplicas nuevas ---
    print("Sanidad 1: determinismo (rep 100)...")
    a = e56.correr_replica_param(100, items, tasas, sc)["reg_pol"]
    b = e56.correr_replica_param(100, items, tasas, sc)["reg_pol"]
    assert a == b, f"{a} vs {b}"
    print("  OK.")

    # --- Sanidad 2: bit-identidad flags-apagados vs referencia (3 réplicas) ---
    print("Sanidad 2: bit-identidad en réplicas nuevas...")
    for r in (100, 107, 119):
        ref = e56.correr_replica_param(r, items, tasas, sc)["reg_pol"]
        got = r64.correr_replica_ablacion(r, items, tasas, sc, {})["reg_pol"]
        assert abs(got - ref) < 1e-9, f"réplica {r}: {got} vs {ref}"
    print("  OK: bit-idéntica en 100/107/119.")

    # --- Corrida pareada ---
    regs_control, regs_sinskip = [], []
    for r in REPLICAS:
        t1 = time.time()
        rc = r64.correr_replica_ablacion(r, items, tasas, sc, {})["reg_pol"]
        rs = r64.correr_replica_ablacion(r, items, tasas, sc,
                                         {"sin_skip": True})["reg_pol"]
        regs_control.append(rc)
        regs_sinskip.append(rs)
        print(f"  rep {r}: control={rc:.3f} sin_skip={rs:.3f} "
              f"d={rs - rc:+.3f} ({time.time() - t1:.1f}s)", flush=True)

    # --- Análisis pareado ---
    diffs = [s - c for s, c in zip(regs_sinskip, regs_control)]
    n = len(diffs)
    media = sum(diffs) / n
    sd = math.sqrt(sum((d - media) ** 2 for d in diffs) / (n - 1))
    se = sd / math.sqrt(n)
    lo, hi = media - T_CRIT * se, media + T_CRIT * se
    n_pos = sum(1 for d in diffs if d > 0)
    n_neg = sum(1 for d in diffs if d < 0)
    load_bearing = bool(media > 0 and lo > 0 and n_pos >= 14)
    nocivo = bool(media < 0 and hi < 0 and n_neg >= 14)

    report = {
        "experimento": "ALMA-EXP64-skip: ablación del skip, n=20 held-out",
        "preregistro": "preregistro.md (mismo directorio, previo a la corrida)",
        "scaffold_control": sc,
        "replicas": REPLICAS,
        "replicas_held_out": True,
        "sanidad_determinismo": True,
        "sanidad_bit_identica": True,
        "t_crit": T_CRIT,
        "gl": n - 1,
        "reg_control_por_replica": [round(v, 3) for v in regs_control],
        "reg_sin_skip_por_replica": [round(v, 3) for v in regs_sinskip],
        "diffs_sin_skip_menos_control": [round(d, 3) for d in diffs],
        "efecto_medio": round(media, 3),
        "ic95": [round(lo, 3), round(hi, 3)],
        "ic95_ancho": round(hi - lo, 3),
        "replicas_peor_sin_skip": n_pos,
        "replicas_mejor_sin_skip": n_neg,
        "criterio_load_bearing": "media>0, IC95 sin cruzar 0, peor en >=14/20",
        "criterio_nocivo": "media<0, IC95 sin cruzar 0, mejor en >=14/20",
        "load_bearing": load_bearing,
        "nocivo": nocivo,
        "costo_total_usd": 0.0,
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ EXP64-skip ================")
    print(f"  control medio: {sum(regs_control)/n:.3f}")
    print(f"  sin_skip medio: {sum(regs_sinskip)/n:.3f}")
    print(f"  efecto (quitar skip): {media:+.3f} "
          f"IC95 [{lo:+.3f}, {hi:+.3f}]")
    print(f"  peor sin skip: {n_pos}/20 | mejor sin skip: {n_neg}/20")
    print(f"  load_bearing={load_bearing} nocivo={nocivo}")
    print(f"  costo: $0.0000 USD (mock) | {report['duracion_s']}s")
    print("===========================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
