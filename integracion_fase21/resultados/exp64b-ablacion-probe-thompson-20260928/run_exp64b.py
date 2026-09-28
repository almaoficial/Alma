#!/usr/bin/env python3
"""ALMA-EXP64b: ablación probe-vs-Thompson con n=20 réplicas held-out.

Tratamientos: (a) control (referencia e56), (b) sin_probe (flag EXISTENTE
de r64.correr_replica_ablacion), (c) sin_thompson (flag NUEVO).

El flag sin_thompson NO existe en run_exp64.py; se implementa en una
copia VERBATIM de correr_replica_ablacion dentro de este script
(correr_replica_ablacion_b). run_exp64.py NO se modifica. Con el flag
apagado la copia es bit-idéntica al original (sanidad pre-registrada).

Semántica de sin_thompson (ver preregistro.md): probe intacto (Q1 siempre
medido; Q2 medido ssi gate=False; skip sin cambios; rewards de política
en items medidos = fav del prior); en los slots donde el control corre
Thompson sampling se explota al ganador del probe (mayor reward medio
observado en las mediciones del bloque hasta ese punto). Desempate
determinista por orden de brazos. rep_hist se actualiza para el ganador.

Ver preregistro.md (escrito ANTES de correr). Mock, US$0.
"""

import json
import math
import os
import random
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
REPLICAS = list(range(200, 220))  # 20 held-out
T_CRIT = 2.093  # t_{0.975, gl=19}


def correr_replica_ablacion_b(rep_id, items, tasas, sc, flags):
    """Copia verbatim de r64.correr_replica_ablacion + flag sin_thompson.

    flags: sin_prior_cond, sin_skip, sin_gate, sin_probe, prior_uniforme,
    sin_thompson (NUEVO, solo en esta copia).
    Con sin_thompson apagado es bit-idéntica a r64.correr_replica_ablacion.
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

        def ganador_probe(obs_qs):
            # Ganador del probe: brazo con mayor reward medio observado.
            # Desempate determinista por orden de brazos (max -> primero).
            medias = {a: sum(obs_qs[q][a] for q in obs_qs) / len(obs_qs)
                      for a in brazos}
            return max(brazos, key=lambda a: medias[a])

        def explotar(qs, obs_qs):
            # Sin Thompson: explota al ganador del probe en cada slot.
            for q in qs:
                h = base + q
                it = items[h]
                w = ganador_probe(obs_qs)
                r_sel = clf.acierto(
                    w, it,
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{w}"))
                rep_hist[w].append((h, r_sel, b))
                rew_pol[h] = r_sel
                for a in brazos:
                    rew_fija[a][h] = clf.acierto(
                        a, it, random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                clf.registrar(it)

        pre_q2 = tuple(q for q in e47.THOMPSON_Q if q < e47.PROBE_Q2[0])
        post_q2 = tuple(q for q in e47.THOMPSON_Q if q > e47.PROBE_Q2[-1])

        if flags.get("sin_thompson"):
            explotar(pre_q2, rs_q1)
            if gate:
                explotar(e47.PROBE_Q2, rs_q1)
            else:
                rs_q2 = {}
                for q in e47.PROBE_Q2:
                    h = base + q
                    rs_q2[q] = medir(q)
                    rew_pol[h] = rs_q2[q][fav]
                explotar(post_q2, {**rs_q1, **rs_q2})
        else:
            thompson(pre_q2)
            if gate:
                thompson(e47.PROBE_Q2)
            else:
                rs_q2 = {}
                for q in e47.PROBE_Q2:
                    h = base + q
                    rs_q2[q] = medir(q)
                    rew_pol[h] = rs_q2[q][fav]
            thompson(post_q2)

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
    "control": None,            # e56.correr_replica_param (referencia)
    "sin_probe": {"sin_probe": True},      # r64, flag existente
    "sin_thompson": {"sin_thompson": True},  # copia local, flag nuevo
}


def analizar(nombre, vals, ctrl):
    diffs = [v - c for v, c in zip(vals, ctrl)]
    n = len(diffs)
    media = sum(diffs) / n
    sd = math.sqrt(sum((d - media) ** 2 for d in diffs) / (n - 1))
    se = sd / math.sqrt(n)
    lo, hi = media - T_CRIT * se, media + T_CRIT * se
    n_pos = sum(1 for d in diffs if d > 0)
    n_neg = sum(1 for d in diffs if d < 0)
    return {
        "reg_por_replica": [round(v, 3) for v in vals],
        "diffs_vs_control": [round(d, 3) for d in diffs],
        "efecto_medio": round(media, 3),
        "ic95": [round(lo, 3), round(hi, 3)],
        "ic95_ancho": round(hi - lo, 3),
        "replicas_peor": n_pos,
        "replicas_mejor": n_neg,
        "replicas_empate": n - n_pos - n_neg,
        "load_bearing": bool(media > 0 and lo > 0 and n_pos >= 14),
        "nocivo": bool(media < 0 and hi < 0 and n_neg >= 14),
    }


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    items = e47.construir_stream()
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
    sc = dict(DEFAULT_SCAFFOLD)

    # --- Sanidad 1: determinismo del control en réplicas nuevas ---
    print("Sanidad 1: determinismo (rep 200)...")
    a = e56.correr_replica_param(200, items, tasas, sc)["reg_pol"]
    b = e56.correr_replica_param(200, items, tasas, sc)["reg_pol"]
    assert a == b, f"{a} vs {b}"
    print("  OK.")

    # --- Sanidad 2: copia extendida bit-idéntica con flags apagados ---
    print("Sanidad 2: bit-identidad copia vs r64 en réplicas nuevas...")
    for r in (200, 207, 219):
        ref = r64.correr_replica_ablacion(r, items, tasas, sc,
                                          {})["reg_pol"]
        got = correr_replica_ablacion_b(r, items, tasas, sc,
                                        {})["reg_pol"]
        assert abs(got - ref) < 1e-9, f"réplica {r}: {got} vs {ref}"
    print("  OK: bit-idéntica en 200/207/219.")

    # --- Corrida pareada: 3 tratamientos ---
    regs = {"control": [], "sin_probe": [], "sin_thompson": []}
    for r in REPLICAS:
        t1 = time.time()
        rc = e56.correr_replica_param(r, items, tasas, sc)["reg_pol"]
        rp = r64.correr_replica_ablacion(
            r, items, tasas, sc, {"sin_probe": True})["reg_pol"]
        rt = correr_replica_ablacion_b(
            r, items, tasas, sc, {"sin_thompson": True})["reg_pol"]
        regs["control"].append(rc)
        regs["sin_probe"].append(rp)
        regs["sin_thompson"].append(rt)
        print(f"  rep {r}: control={rc:.3f} sin_probe={rp:.3f} "
              f"sin_thompson={rt:.3f} ({time.time() - t1:.1f}s)", flush=True)

    ctrl = regs["control"]
    analisis = {k: analizar(k, regs[k], ctrl)
                for k in ("sin_probe", "sin_thompson")}

    report = {
        "experimento": "ALMA-EXP64b: ablación probe-vs-Thompson, n=20 held-out",
        "preregistro": "preregistro.md (mismo directorio, previo a la corrida)",
        "scaffold_control": sc,
        "replicas": REPLICAS,
        "replicas_held_out": True,
        "sanidad_determinismo": True,
        "sanidad_bit_identica": True,
        "t_crit": T_CRIT,
        "gl": len(REPLICAS) - 1,
        "control_reg_medio": round(sum(ctrl) / len(ctrl), 3),
        "control_reg_por_replica": [round(v, 3) for v in ctrl],
        "tratamientos": {k: v for k, v in TRATAMIENTOS.items()},
        "analisis": analisis,
        "criterio_load_bearing": "media>0, IC95 sin cruzar 0, peor en >=14/20",
        "criterio_nocivo": "media<0, IC95 sin cruzar 0, mejor en >=14/20",
        "costo_total_usd": 0.0,
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ EXP64b: efectos vs control ================")
    print(f"  control medio: {report['control_reg_medio']:.3f}")
    for nombre, a in analisis.items():
        print(f"  {nombre}: efecto {a['efecto_medio']:+.3f} "
              f"IC95 [{a['ic95'][0]:+.3f}, {a['ic95'][1]:+.3f}] "
              f"peor-en {a['replicas_peor']}/20 "
              f"{'LOAD-BEARING' if a['load_bearing'] else ''}"
              f"{'NOCIVO' if a['nocivo'] else ''}")
    print(f"  costo: $0.0000 USD (mock) | {report['duracion_s']}s")
    print("=============================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
