#!/usr/bin/env python3
"""ALMA-EXP65: RSO sobre el prior con memoria (mock, US$0).

Aplicación directa del veredicto de EXP64: el prior con memoria vale
+21,60 (más del doble que todo el probe junto). Se evoluciona SOLO el
genoma del prior (n0, decay, granularidad del condicionamiento); el
probe y el resto del scaffold quedan FIJOS en los valores validados
(EXP56/57).

Puerta de dos splits (alma_service/gate.py): cada candidato se evalúa
en held-in [0,1,2] y held-out [3,4]; se adopta ssi
Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(Δ_in,Δ_ho) > 0.

Pre-registro: preregistro.md (mismo directorio). Escrito ANTES de correr.
"""

import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ALMA_PROTO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
# ~/workspace/alma-prototype
sys.path.insert(0, ALMA_PROTO)
sys.path.insert(0, os.path.join(ALMA_PROTO, "exp56_rso"))
import run_experiment56 as e56  # noqa: E402
import run_experiment47 as e47  # noqa: E402
from alma_service.gate import (  # noqa: E402
    PuertaDosSplits, audit_record)
from alma_service.scaffold import DEFAULT_SCAFFOLD  # noqa: E402

nuevo_bandit_param = e56.nuevo_bandit_param
soporte_param = e56.soporte_param
q1_decisivo_param = e56.q1_decisivo_param

OUT = HERE
SPACES = {
    "n0": [2, 4, 6, 8],
    "decay": [0.3, 0.5, 0.7, 0.9, 1.0],  # 1.0 = sin decaimiento
    "cond": ["completa", "gruesa", "ninguna"],
}
GEN_INIT = {"n0": 4, "decay": 0.5, "cond": "completa"}
N_RONDAS = 24
PROP_SEED = 65
HELD_IN = [0, 1, 2]
HELD_OUT = [3, 4]
T_CRIT = 2.776  # t pareado, gl=4, 95%


def prior_params_exp65(brazos, rep_hist, block_sig, b, sig, n0, decay,
                       cond):
    """Prior con granularidad de condicionamiento parametrizada.

    cond="completa": verbatim de prior_params_param (EXP45-51).
    cond="gruesa": pooling jerárquico — toda la historia pasada con
        peso 1.0 si misma firma, 0.3 si firma distinta (factor fijo,
        pre-registrado).
    cond="ninguna": prior siempre ciego (sig forzado a None).
    """
    if cond == "ninguna":
        sig = None
    params = {}
    for a in brazos:
        if cond == "gruesa":
            obs_w = []
            for (h, r, blk) in rep_hist[a]:
                if blk >= b:
                    continue
                w_sig = (1.0 if (sig is None or
                                 block_sig.get(blk) == sig) else 0.3)
                obs_w.append((r, (decay ** (b - 1 - blk)) * w_sig))
            if obs_w:
                sw = sum(w for _, w in obs_w)
                m = sum(r * w for r, w in obs_w) / sw
            else:
                m = 0.5
        else:  # completa: verbatim de prior_params_param
            if sig is None:
                obs = [(r, blk) for (h, r, blk) in rep_hist[a] if blk < b]
            else:
                obs = [(r, blk) for (h, r, blk) in rep_hist[a]
                       if blk < b and block_sig.get(blk) == sig]
                if not obs:
                    obs = [(r, blk) for (h, r, blk) in rep_hist[a]
                           if blk < b]
            if obs:
                ws = [decay ** (b - 1 - blk) for (_, blk) in obs]
                sw = sum(ws)
                m = sum(r * w for (r, _), w in zip(obs, ws)) / sw
            else:
                m = 0.5
        params[a] = (1.0 + n0 * m, 1.0 + n0 * (1.0 - m))
    return params


def correr_replica_prior(rep_id, items, tasas, sc, cond):
    """Puerto de correr_replica_param con el prior parametrizado.

    Idéntico salvo los dos call sites del prior, que usan
    prior_params_exp65(..., cond). Con cond="completa" debe ser
    bit-idéntico a correr_replica_param.
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

    for b in range(n_bloques):
        base = b * e47.BLOQUE
        sig = e47.firma_grupo([items[base + q]["grupo"]
                               for q in e47.PROBE_Q1])
        block_sig[b] = sig

        saltar = False
        skill_arm = None
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            skill_arm = e47.skill_arm_actual(brazos, rep_hist, block_sig,
                                             b, sig)
            fuerte, _, _, _ = soporte_param(
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

        bandit = nuevo_bandit_param(
            brazos, prior_params_exp65(brazos, rep_hist, block_sig, b,
                                       None, n0, decay, cond), n0)
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

        usa_skill = False
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            usa_skill = True
            bandit = nuevo_bandit_param(
                brazos, prior_params_exp65(brazos, rep_hist, block_sig, b,
                                           sig, n0, decay, cond), n0)
            for q in e47.PROBE_Q1:
                for a in brazos:
                    bandit.update(a, rs_q1[q][a])

        gate = (skill_arm is not None and usa_skill and
                q1_decisivo_param(brazos, rs_q1, skill_arm, gm))

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
                        a, it,
                        random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
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
    reg_fijas = {a: H - sum(rew_fija[a]) for a in brazos}
    mejor = min(brazos, key=lambda a: reg_fijas[a])
    return {"reg_pol": reg_pol, "reg_pol_bloques": reg_pol_bloques,
            "reg_fijas": reg_fijas, "mejor_fija": mejor,
            "reg_mejor_fija": reg_fijas[mejor], "n": H}


def gen_key(gen):
    return (gen["n0"], gen["decay"], gen["cond"])


def evaluar(gen, items, tasas, replicas, cache):
    k = (gen_key(gen), tuple(replicas))
    if k not in cache:
        sc = dict(DEFAULT_SCAFFOLD)
        sc["n0"] = gen["n0"]
        sc["decay"] = gen["decay"]
        regs = [correr_replica_prior(r, items, tasas, sc, gen["cond"])
                ["reg_pol"] for r in replicas]
        cache[k] = (sum(regs) / len(regs), regs)
    return cache[k]


def proponer(prop_rng, actual):
    dim = prop_rng.choice(sorted(SPACES.keys()))
    opciones = [v for v in SPACES[dim] if v != actual[dim]]
    return dim, prop_rng.choice(opciones)


def main():
    t0 = time.time()
    items = e47.construir_stream()
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
    cache = {}

    # --- 1. Sanidad bit-idéntica (bloqueante) ---
    print("Sanidad: puerto con genoma inicial vs correr_replica_param...")
    sc0 = dict(DEFAULT_SCAFFOLD)
    for r in range(5):
        got = correr_replica_prior(r, items, tasas, sc0, "completa")[
            "reg_pol"]
        exp = e56.correr_replica_param(r, items, tasas, sc0)["reg_pol"]
        assert abs(got - exp) < 1e-9, (
            f"réplica {r}: puerto={got} vs referencia={exp}")
    # determinismo
    a = correr_replica_prior(0, items, tasas, sc0, "completa")["reg_pol"]
    b = correr_replica_prior(0, items, tasas, sc0, "completa")["reg_pol"]
    assert a == b
    print("  OK: bit-idéntico en 5/5 réplicas, determinista.")

    # --- 2. Loop RSO con puerta de dos splits ---
    prop_rng = random.Random(PROP_SEED)
    actual = dict(GEN_INIT)
    m_in_act, regs_in_act = evaluar(actual, items, tasas, HELD_IN, cache)
    m_ho_act, regs_ho_act = evaluar(actual, items, tasas, HELD_OUT, cache)
    trayectoria = []
    n_keeps = 0
    for ronda in range(1, N_RONDAS + 1):
        dim, nuevo_val = proponer(prop_rng, actual)
        mut = dict(actual)
        mut[dim] = nuevo_val
        m_in_mut, _ = evaluar(mut, items, tasas, HELD_IN, cache)
        m_ho_mut, _ = evaluar(mut, items, tasas, HELD_OUT, cache)
        puerta = PuertaDosSplits.decidir(m_in_act, m_ho_act,
                                         m_in_mut, m_ho_mut)
        keep = bool(puerta["aceptado"])
        aud = audit_record(
            propuesta=f"{dim}: {actual[dim]} -> {nuevo_val}",
            delta_in=puerta["delta_in"], delta_ho=puerta["delta_ho"],
            aceptado=keep, motivo=puerta["motivo"],
            debilidad="prior con memoria (EXP64: +21,60)",
            superficie="genoma del prior",
            efecto_esperado="menos regret",
            riesgo_regresion="presión de selección sobre el gate")
        trayectoria.append({"ronda": ronda, "dim": dim,
                            "de": actual[dim], "a": nuevo_val,
                            "delta_in": puerta["delta_in"],
                            "delta_ho": puerta["delta_ho"],
                            "keep": keep, "motivo": puerta["motivo"]})
        if keep:
            actual = mut
            m_in_act, m_ho_act = m_in_mut, m_ho_mut
            n_keeps += 1

    # --- 3. Medición final pareada (5 réplicas) ---
    _, regs_init = evaluar(dict(GEN_INIT), items, tasas,
                           HELD_IN + HELD_OUT, cache)
    _, regs_fin = evaluar(actual, items, tasas, HELD_IN + HELD_OUT, cache)
    ds = [f - i for f, i in zip(regs_fin, regs_init)]
    d_media = sum(ds) / len(ds)
    var = sum((d - d_media) ** 2 for d in ds) / (len(ds) - 1)
    se = (var / len(ds)) ** 0.5
    ic = (d_media - T_CRIT * se, d_media + T_CRIT * se)
    pasa = bool(d_media < 0 and ic[1] < 0)

    report = {
        "experimento": "ALMA-EXP65: RSO sobre el prior con memoria",
        "preregistro": "preregistro.md (mismo directorio)",
        "n_rondas": N_RONDAS, "prop_seed": PROP_SEED,
        "espacio": SPACES, "genoma_inicial": GEN_INIT,
        "genoma_final": actual,
        "cambio_neto": {d: [GEN_INIT[d], actual[d]] for d in SPACES
                        if GEN_INIT[d] != actual[d]},
        "n_keeps": n_keeps, "trayectoria": trayectoria,
        "held_in": HELD_IN, "held_out": HELD_OUT,
        "regs_init_5": [round(x, 3) for x in regs_init],
        "regs_fin_5": [round(x, 3) for x in regs_fin],
        "efecto_por_replica": [round(d, 3) for d in ds],
        "efecto_medio": round(d_media, 3),
        "ic95": [round(ic[0], 3), round(ic[1], 3)],
        "criterio": "PASS ssi efecto_medio < 0 e IC95 sin cruzar 0",
        "veredicto": "PASS" if pasa else "FAIL",
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w",
              encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps({k: report[k] for k in
                      ("genoma_final", "n_keeps", "efecto_medio", "ic95",
                       "veredicto", "duracion_s")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
