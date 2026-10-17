#!/usr/bin/env python3
"""ALMA-EXP56: RSO estilo MiniMax — auto-optimización recursiva del scaffold (mock, US$0).

El "scaffold" a evolucionar = los hiperparámetros de la política de probe de
EXP51. Loop greedy de linaje único: en cada ronda se propone UNA mutación
(un parámetro -> otro valor de su espacio), se evalúa en el split de
entrenamiento (réplicas [0,1,2]) y se hace keep si mejora estrictamente,
revert si no. N=24 rondas. La medición final es en réplicas held-out [3,4]
que el loop nunca ve (anti-Goodhart).

REGLA DE ORO: el loop NUNCA edita al validador. El oráculo, el stream, el
cómputo de regret, las held-out y el evaluador están congelados; solo los 5
hiperparámetros mutan.

Uso:
    python3 run_experiment56.py [--rondas N] [--seed PROP_SEED]
"""

import argparse
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # alma-prototype/ (run_experiment47)
sys.path.insert(0, HERE)
import run_experiment47 as e47  # noqa: E402  (maquinaria base)
from alma.selector import BanditPorClase  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "exp56_rso")
EXP51_REPORT = os.path.join(BASE, "resultados", "exp51-20260927",
                            "report.json")

# --- Espacio de mutación (pre-registrado, explícito y acotado) ---
SPACES = {
    "umbral_base": [1, 2, 3],
    "umbral_divisor": [2, 3, 4, 6],
    "gate_margin": [0.0, 0.05, 0.10],
    "n0": [1, 2, 4],
    "decay": [0.25, 0.5, 0.75],
}
SC_INIT = {"umbral_base": 2, "umbral_divisor": 3, "gate_margin": 0.0,
           "n0": 2, "decay": 0.5}

TRAIN_REPS = [0, 1, 2]
HELDOUT_REPS = [3, 4]
N_RONDAS = 24
PROP_SEED = 56
# Totales de regret del TRATAMIENTO de EXP51 por réplica (sanidad bit-idéntica)
EXP51_TRAT_TOTALES = [78.0, 86.0, 93.0, 95.0, 80.0]


# ---------------------------------------------------------------------------
# Piezas parametrizadas (copias fieles de e47/e49 con los hiperparámetros
# como argumentos en vez de constantes de módulo).
# ---------------------------------------------------------------------------
def prior_params_param(brazos, rep_hist, block_sig, b, sig, n0, decay):
    """Copia verbatim de e47.prior_params con N0->n0, DECAY->decay."""
    params = {}
    for a in brazos:
        if sig is None:
            obs = [(r, blk) for (h, r, blk) in rep_hist[a] if blk < b]
        else:
            obs = [(r, blk) for (h, r, blk) in rep_hist[a]
                   if blk < b and block_sig.get(blk) == sig]
            if not obs:
                obs = [(r, blk) for (h, r, blk) in rep_hist[a] if blk < b]
        if obs:
            ws = [decay ** (b - 1 - blk) for (_, blk) in obs]
            sw = sum(ws)
            m = sum(r * w for (r, _), w in zip(obs, ws)) / sw
        else:
            m = 0.5
        params[a] = (1.0 + n0 * m, 1.0 + n0 * (1.0 - m))
    return params


def nuevo_bandit_param(brazos, params, n0):
    """Copia verbatim de e47.nuevo_bandit con N0->n0."""
    bandit = BanditPorClase(brazos)
    for a in brazos:
        bandit.alpha[a], bandit.beta[a] = params[a]
        bandit.pulls[a] = n0
    return bandit


def soporte_param(brazos, probe_obs, block_sig, b, sig, skill_arm,
                  umbral_base, umbral_divisor):
    """Copia verbatim de e49.soporte_endurecido salvo la fórmula del umbral:
    umbral(K) = umbral_base + floor(K / umbral_divisor)."""
    wins = 0
    K = 0
    for b2 in range(b):
        if block_sig.get(b2) != sig:
            continue
        obs = probe_obs.get(b2)
        if not obs:
            continue  # bloque saltado: sin comparación pareada
        K += 1
        m_s = sum(obs[skill_arm]) / len(obs[skill_arm])
        if all(m_s > sum(obs[a]) / len(obs[a])
               for a in brazos if a != skill_arm):
            wins += 1
    umbral = umbral_base + K // umbral_divisor
    return wins >= umbral, wins, K, umbral


def q1_decisivo_param(brazos, rs_q1, skill_arm, margin):
    """Copia de run_experiment51.q1_decisivo con margen: m_s > m_a + margin.
    Con margin=0.0 es bit-idéntico al original."""
    m_s = sum(rs_q1[q][skill_arm] for q in e47.PROBE_Q1) / len(e47.PROBE_Q1)
    return all(m_s > sum(rs_q1[q][a] for q in e47.PROBE_Q1) /
               len(e47.PROBE_Q1) + margin
               for a in brazos if a != skill_arm)


# ---------------------------------------------------------------------------
# Política probe-barato de EXP51, parametrizada por el scaffold.
# COPIA VERBATIM de run_experiment51.correr_replica_probe_barato salvo los 4
# call sites parametrizados. Con SC_INIT debe reproducir EXP51 bit-idéntico.
# ---------------------------------------------------------------------------
def correr_replica_param(rep_id, items, tasas, sc):
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
            # PROBE SALTADO: idéntico a EXP51.
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

        # --- Camino con probe: idéntico a EXP51 ---
        bandit = nuevo_bandit_param(
            brazos, prior_params_param(brazos, rep_hist, block_sig, b, None,
                                       n0, decay), n0)
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

        # PROBE Q1: bit-idéntico al control (mismos sorteos, scoring ciego).
        rs_q1 = {}
        for q in e47.PROBE_Q1:
            h = base + q
            rs_q1[q] = medir(q)
            rew_pol[h] = rs_q1[q][fav]

        usa_skill = False
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            usa_skill = True
            bandit = nuevo_bandit_param(
                brazos, prior_params_param(brazos, rep_hist, block_sig, b,
                                           sig, n0, decay), n0)
            for q in e47.PROBE_Q1:
                for a in brazos:
                    bandit.update(a, rs_q1[q][a])

        # Gate adaptativo (parametrizado por el margen).
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
                        a, it, random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                clf.registrar(it)

        thompson(tuple(q for q in e47.THOMPSON_Q if q < e47.PROBE_Q2[0]))
        if gate:
            # Q2 SALTADO: items 6,7 como jugadas de Thompson.
            thompson(e47.PROBE_Q2)
        else:
            # RE-PROBE Q2: scoring honesto con fav ciego.
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


# ---------------------------------------------------------------------------
# Loop RSO
# ---------------------------------------------------------------------------
def sc_key(sc):
    return tuple(sorted(sc.items()))


def evaluar(sc, items, tasas, replicas, cache):
    """Regret medio del scaffold en las réplicas dadas (con caché)."""
    k = (sc_key(sc), tuple(replicas))
    if k not in cache:
        regs = [correr_replica_param(r, items, tasas, sc)["reg_pol"]
                for r in replicas]
        cache[k] = (sum(regs) / len(regs), regs)
    return cache[k]


def proponer(prop_rng, actual):
    dim = prop_rng.choice(sorted(SPACES.keys()))
    opciones = [v for v in SPACES[dim] if v != actual[dim]]
    return dim, prop_rng.choice(opciones)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rondas", type=int, default=N_RONDAS)
    ap.add_argument("--seed", type=int, default=PROP_SEED)
    args = ap.parse_args()
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)

    items = e47.construir_stream()
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
    H = len(items)
    n_bloques = H // e47.BLOQUE

    # --- 1. Chequeo de sanidad bit-idéntica (pre-registrado) ---
    print("Chequeo de sanidad: puerto parametrizado con SC_INIT vs "
          "tratamiento de EXP51...")
    cache = {}
    for r in range(5):
        got = correr_replica_param(r, items, tasas, dict(SC_INIT))["reg_pol"]
        exp = EXP51_TRAT_TOTALES[r]
        assert abs(got - exp) < 1e-9, (
            f"réplica {r}: puerto={got} vs EXP51={exp} — el puerto NO es "
            f"bit-idéntico, no se corre el loop")
    print("  OK: bit-idéntico en las 5 réplicas "
          f"({EXP51_TRAT_TOTALES}).")

    # --- 2. Loop RSO greedy ---
    prop_rng = random.Random(args.seed)
    actual = dict(SC_INIT)
    metrica_actual, _ = evaluar(actual, items, tasas, TRAIN_REPS, cache)
    trayectoria = []
    n_keeps = 0
    for ronda in range(1, args.rondas + 1):
        dim, nuevo_val = proponer(prop_rng, actual)
        mutante = dict(actual)
        mutante[dim] = nuevo_val
        metrica_mut, _ = evaluar(mutante, items, tasas, TRAIN_REPS, cache)
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
    evolucionado = actual

    # --- 3. Medición final en held-out (el loop nunca vio [3,4]) ---
    media_init_tr, regs_init_tr = evaluar(dict(SC_INIT), items, tasas,
                                          TRAIN_REPS, cache)
    media_evo_tr, regs_evo_tr = evaluar(evolucionado, items, tasas,
                                        TRAIN_REPS, cache)
    media_init_ho, regs_init_ho = evaluar(dict(SC_INIT), items, tasas,
                                          HELDOUT_REPS, cache)
    media_evo_ho, regs_evo_ho = evaluar(evolucionado, items, tasas,
                                        HELDOUT_REPS, cache)

    mejora_train = media_init_tr - media_evo_tr
    mejora_heldout = media_init_ho - media_evo_ho
    pasa = bool(mejora_heldout > 0)

    report = {
        "experimento": "ALMA-EXP56: RSO estilo MiniMax (mock, US$0)",
        "preregistro": "preregistro.md (mismo directorio)",
        "n_items": H, "n_bloques": n_bloques,
        "espacio_mutacion": SPACES,
        "scaffold_inicial": SC_INIT,
        "scaffold_final": evolucionado,
        "cambio_neto": {d: [SC_INIT[d], evolucionado[d]]
                        for d in SPACES if SC_INIT[d] != evolucionado[d]},
        "n_rondas": args.rondas, "prop_seed": args.seed,
        "train_replicas": TRAIN_REPS, "heldout_replicas": HELDOUT_REPS,
        "sanidad_bit_identica_exp51": True,
        "n_keeps": n_keeps,
        "trayectoria": trayectoria,
        "train": {"init_media": round(media_init_tr, 4),
                  "init_por_replica": [round(x, 3) for x in regs_init_tr],
                  "evo_media": round(media_evo_tr, 4),
                  "evo_por_replica": [round(x, 3) for x in regs_evo_tr],
                  "mejora": round(mejora_train, 4)},
        "heldout": {"init_media": round(media_init_ho, 4),
                    "init_por_replica": [round(x, 3) for x in regs_init_ho],
                    "evo_media": round(media_evo_ho, 4),
                    "evo_por_replica": [round(x, 3) for x in regs_evo_ho],
                    "mejora": round(mejora_heldout, 4)},
        "criterio": "PASS ssi media_heldout(evolucionado) < "
                    "media_heldout(inicial)",
        "veredicto": "PASS" if pasa else "FAIL",
        "costo_total_usd": 0.0,
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP56 ================")
    print(f"  rondas: {args.rondas} | keeps: {n_keeps}/{args.rondas}")
    print(f"  scaffold inicial: {SC_INIT}")
    print(f"  scaffold final:   {evolucionado}")
    print(f"  train [0,1,2]: init {media_init_tr:.3f} -> "
          f"evo {media_evo_tr:.3f} (mejora {mejora_train:+.3f})")
    print(f"  held-out [3,4]: init {media_init_ho:.3f} -> "
          f"evo {media_evo_ho:.3f} (mejora {mejora_heldout:+.3f})")
    print("  trayectoria (ronda: dim de->a keep metrica):")
    for t in trayectoria:
        print(f"    r{t['ronda']:02d}: {t['dim']} {t['de']}->{t['a']} "
              f"{'KEEP' if t['keep'] else '....'} "
              f"({t['metrica_antes']:.2f}->{t['metrica_despues']:.2f})")
    print(f"  costo: $0.0000 USD (mock) | {report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL",
          f"(mejora held-out {mejora_heldout:+.3f})")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
