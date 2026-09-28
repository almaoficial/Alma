#!/usr/bin/env python3
"""ALMA-EXP64: ablación del scaffold estilo Cherny (mock, US$0).

Pela el scaffold evolucionado componente por componente y mide qué se
rompe. Ver preregistro.md (escrito ANTES de correr).

Control = exp56_rso.run_experiment56.correr_replica_param con
DEFAULT_SCAFFOLD (la implementación de referencia misma, no una copia).
Ablaciones = correr_replica_ablacion con flags; con todos los flags
apagados debe ser bit-idéntica al control (chequeo de sanidad).
"""

import json
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))  # alma-prototype/
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "exp56_rso"))

import run_experiment47 as e47  # noqa: E402
import run_experiment56 as e56  # noqa: E402
from alma_service.scaffold import DEFAULT_SCAFFOLD  # noqa: E402

OUT = HERE
REPLICAS = [0, 1, 2, 3, 4]
T_CRIT = 2.776  # t_{0.975, gl=4}


def correr_replica_ablacion(rep_id, items, tasas, sc, flags):
    """Copia de e56.correr_replica_param con flags de ablación.

    flags: sin_prior_cond, sin_skip, sin_gate, sin_probe, prior_uniforme.
    Con todos apagados es bit-idéntica a e56.correr_replica_param.
    """
    brazos = tasas["brazos"]
    H = len(items)
    n_bloques = H // e47.BLOQUE
    rep_hist = {a: [] for a in brazos}
    block_sig = {}
    probe_obs = {}
    rew_pol = [0.0] * H
    rew_fija = {a: [0.0] * H for a in brazos}
    reg_pol_bloques = []

    ub, ud = sc["umbral_base"], sc["umbral_divisor"]
    gm, n0, decay = sc["gate_margin"], sc["n0"], sc["decay"]
    if flags.get("prior_uniforme"):
        n0 = 0  # prior Beta(1,1) puro, sin historia

    for b in range(n_bloques):
        base = b * e47.BLOQUE
        sig = e47.firma_grupo([items[base + q]["grupo"]
                               for q in e47.PROBE_Q1])
        block_sig[b] = sig

        # --- Camino sin probe: Thompson pelado en los 10 items ---
        if flags.get("sin_probe"):
            bandit = e56.nuevo_bandit_param(
                brazos, e56.prior_params_param(brazos, rep_hist, block_sig,
                                              b, None, n0, decay), n0)
            clf = e47.MockClasificador(tasas)
            for hh in range(base):
                clf.registrar(items[hh])
            probe_obs[b] = None
            for q in range(e47.BLOQUE):
                h = base + q
                it = items[h]
                a_sel = bandit.select(
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-sel"))
                r_sel = clf.acierto(
                    a_sel, it,
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a_sel}"))
                bandit.update(a_sel, r_sel)
                rep_hist[a_sel].append((h, r_sel, b))
                rew_pol[h] = r_sel
                for a in brazos:
                    rew_fija[a][h] = clf.acierto(
                        a, it,
                        random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                clf.registrar(it)
            reg_pol_bloques.append(
                e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))
            continue

        # --- Camino con probe ---
        saltar = False
        skill_arm = None
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            skill_arm = e47.skill_arm_actual(brazos, rep_hist, block_sig,
                                             b, sig)
            if not flags.get("sin_skip"):
                fuerte, _, _, _ = e56.soporte_param(
                    brazos, probe_obs, block_sig, b, sig, skill_arm, ub, ud)
                saltar = fuerte

        clf = e47.MockClasificador(tasas)
        for hh in range(base):
            clf.registrar(items[hh])

        if saltar:
            probe_obs[b] = None
            for q in range(e47.BLOQUE):
                h = base + q
                it = items[h]
                rs = {a: clf.acierto(
                    a, it, random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                    for a in brazos}
                for a in brazos:
                    rew_fija[a][h] = rs[a]
                r = rs[skill_arm]
                rep_hist[skill_arm].append((h, r, b))
                rew_pol[h] = r
                clf.registrar(it)
            reg_pol_bloques.append(
                e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))
            continue

        bandit = e56.nuevo_bandit_param(
            brazos, e56.prior_params_param(brazos, rep_hist, block_sig, b,
                                          None, n0, decay), n0)
        prior_means = {a: bandit.mean(a) for a in brazos}
        fav = max(brazos, key=lambda a: prior_means[a])

        def medir(q):
            h = base + q
            it = items[h]
            rs = {a: clf.acierto(
                a, it, random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                for a in brazos}
            for a in brazos:
                bandit.update(a, rs[a])
                rep_hist[a].append((h, rs[a], b))
                rew_fija[a][h] = rs[a]
            clf.registrar(it)
            return rs

        rs_q1 = {}
        for q in e47.PROBE_Q1:
            h = base + q
            rs_q1[q] = medir(q)
            rew_pol[h] = rs_q1[q][fav]

        if ((not flags.get("sin_prior_cond"))
                and e47.skill_existe(rep_hist, block_sig, b, sig)):
            bandit = e56.nuevo_bandit_param(
                brazos, e56.prior_params_param(brazos, rep_hist, block_sig,
                                              b, sig, n0, decay), n0)
            for q in e47.PROBE_Q1:
                for a in brazos:
                    bandit.update(a, rs_q1[q][a])

        gate = ((not flags.get("sin_gate")) and skill_arm is not None
                and e56.q1_decisivo_param(brazos, rs_q1, skill_arm, gm))

        def thompson(qs):
            for q in qs:
                h = base + q
                it = items[h]
                a_sel = bandit.select(
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-sel"))
                r_sel = clf.acierto(
                    a_sel, it,
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a_sel}"))
                bandit.update(a_sel, r_sel)
                rep_hist[a_sel].append((h, r_sel, b))
                rew_pol[h] = r_sel
                for a in brazos:
                    rew_fija[a][h] = clf.acierto(
                        a, it, random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                clf.registrar(it)

        thompson(tuple(q for q in e47.THOMPSON_Q if q < e47.PROBE_Q2[0]))
        if gate:
            thompson(e47.PROBE_Q2)
        else:
            rs_q2 = {}
            for q in e47.PROBE_Q2:
                h = base + q
                rs_q2[q] = medir(q)
                rew_pol[h] = rs_q2[q][fav]
        thompson(tuple(q for q in e47.THOMPSON_Q if q > e47.PROBE_Q2[-1]))

        if gate:
            probe_obs[b] = {a: [rs_q1[q][a] for q in e47.PROBE_Q1]
                            for a in brazos}
        else:
            probe_obs[b] = {a: [rs_q1[q][a] for q in e47.PROBE_Q1] +
                               [rs_q2[q][a] for q in e47.PROBE_Q2]
                            for a in brazos}
        reg_pol_bloques.append(
            e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))

    reg_pol = H - sum(rew_pol)
    return {"reg_pol": reg_pol, "reg_pol_bloques": reg_pol_bloques,
            "n": H}


TRATAMIENTOS = {
    "a_control": {},
    "b_sin_prior_cond": {"sin_prior_cond": True},
    "c_sin_skip": {"sin_skip": True},
    "d_sin_gate": {"sin_gate": True},
    "e_sin_probe": {"sin_probe": True},
    "f_minimo_total": {"sin_probe": True, "prior_uniforme": True},
}


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    items = e47.construir_stream()
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
    sc = dict(DEFAULT_SCAFFOLD)

    # --- Sanidad 1: ablación con flags apagados == referencia ---
    print("Sanidad 1: flags apagados vs correr_replica_param...")
    for r in REPLICAS:
        ref = e56.correr_replica_param(r, items, tasas, sc)["reg_pol"]
        got = correr_replica_ablacion(r, items, tasas, sc, {})["reg_pol"]
        assert abs(got - ref) < 1e-9, f"réplica {r}: {got} vs {ref}"
    print("  OK: bit-idéntica en las 5 réplicas.")

    # --- Sanidad 2: determinismo del control ---
    print("Sanidad 2: determinismo...")
    r0a = e56.correr_replica_param(0, items, tasas, sc)["reg_pol"]
    r0b = e56.correr_replica_param(0, items, tasas, sc)["reg_pol"]
    assert r0a == r0b
    print("  OK.")

    # --- Corrida ---
    regs = {}
    for nombre, flags in TRATAMIENTOS.items():
        t1 = time.time()
        if nombre == "a_control":
            vals = [e56.correr_replica_param(r, items, tasas, sc)["reg_pol"]
                    for r in REPLICAS]
        else:
            vals = [correr_replica_ablacion(r, items, tasas, sc, flags)
                    ["reg_pol"] for r in REPLICAS]
        regs[nombre] = vals
        print(f"  {nombre}: {[round(v, 2) for v in vals]} "
              f"({time.time() - t1:.1f}s)")

    # --- Análisis pareado vs control ---
    ctrl = regs["a_control"]
    analisis = {}
    for nombre, vals in regs.items():
        if nombre == "a_control":
            continue
        diffs = [v - c for v, c in zip(vals, ctrl)]
        n = len(diffs)
        media = sum(diffs) / n
        sd = math.sqrt(sum((d - media) ** 2 for d in diffs) / (n - 1)) \
            if n > 1 else 0.0
        se = sd / math.sqrt(n)
        lo, hi = media - T_CRIT * se, media + T_CRIT * se
        n_pos = sum(1 for d in diffs if d > 0)
        ci_sin_cero = (lo > 0) or (hi < 0)
        load_bearing = bool(media > 0 and lo > 0 and n_pos >= 4)
        nociva = bool(media < 0 and hi < 0 and (n - n_pos) >= 4)
        analisis[nombre] = {
            "reg_por_replica": [round(v, 3) for v in vals],
            "diffs_vs_control": [round(d, 3) for d in diffs],
            "efecto_medio": round(media, 3),
            "ic95": [round(lo, 3), round(hi, 3)],
            "ic95_sin_cero": ci_sin_cero,
            "replicas_peor": n_pos,
            "load_bearing": load_bearing,
            "nociva": nociva,
        }

    report = {
        "experimento": "ALMA-EXP64: ablación del scaffold estilo Cherny",
        "preregistro": "preregistro.md (mismo directorio, previo a la corrida)",
        "scaffold_control": sc,
        "replicas": REPLICAS,
        "sanidad_bit_identica": True,
        "sanidad_determinismo": True,
        "control_reg_por_replica": [round(v, 3) for v in ctrl],
        "control_reg_medio": round(sum(ctrl) / len(ctrl), 3),
        "tratamientos": TRATAMIENTOS,
        "analisis": analisis,
        "costo_total_usd": 0.0,
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ EXP64: efectos vs control ================")
    print(f"  control medio: {report['control_reg_medio']:.3f}")
    for nombre, a in analisis.items():
        print(f"  {nombre}: efecto {a['efecto_medio']:+.3f} "
              f"IC95 [{a['ic95'][0]:+.3f}, {a['ic95'][1]:+.3f}] "
              f"peor-en {a['replicas_peor']}/5 "
              f"{'LOAD-BEARING' if a['load_bearing'] else ''}"
              f"{'NOCIVA' if a['nociva'] else ''}")
    print(f"  costo: $0.0000 USD (mock) | {report['duracion_s']}s")
    print("===========================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
