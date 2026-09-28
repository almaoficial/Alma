#!/usr/bin/env python3
"""ALMA-EXP58: RSO con proponente que analiza fallos (mock, US$0).

Mismo scaffold de 5 hiperparametros y mismo protocolo keep/revert de EXP56
(splits train/held-out, validador congelado, 24 rondas, regla de oro). La UNICA
diferencia: el proponente NO es aleatorio. Despues de cada ronda analiza
atribucion de regret por bloque en train y propone la mutacion direccional que
habria ayudado en los peores bloques, segun la heuristica documentada en
preregistro.md (reglas R1/R2/R3 + memoria tabu). El "analisis" es algoritmico,
no un LLM: sigue siendo mock US$0.

Uso:
    python3 run_experiment58.py [--rondas N]
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
OUT = BASE  # report.json va directo en exp58_proposer/

# --- Espacio de mutacion (identico a EXP56, pre-registrado) ---
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
# Totales de regret del TRATAMIENTO de EXP51 por replica (sanidad bit-identica)
EXP51_TRAT_TOTALES = [78.0, 86.0, 93.0, 95.0, 80.0]
# Referencias para el criterio (mismo held-out [3,4])
REF_EXP56_EVO = 83.00   # scaffold evolucionado de EXP56
REF_INIT = 87.50        # scaffold manual (EXP51)
REF_EXP57B = 84.50      # scaffold evolucionado seed 57

# Umbrales de la heuristica (pre-registrados, juicio del analista)
EPS_SKIP = 2.0
EPS_PROBE = 4.0
TABU_VENTANA = 3  # rondas durante las que una mutacion rechazada no se re-propone


# ---------------------------------------------------------------------------
# Piezas parametrizadas (copias fieles de run_experiment56.py).
# ---------------------------------------------------------------------------
def prior_params_param(brazos, rep_hist, block_sig, b, sig, n0, decay):
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
    bandit = BanditPorClase(brazos)
    for a in brazos:
        bandit.alpha[a], bandit.beta[a] = params[a]
        bandit.pulls[a] = n0
    return bandit


def soporte_param(brazos, probe_obs, block_sig, b, sig, skill_arm,
                  umbral_base, umbral_divisor):
    wins = 0
    K = 0
    for b2 in range(b):
        if block_sig.get(b2) != sig:
            continue
        obs = probe_obs.get(b2)
        if not obs:
            continue
        K += 1
        m_s = sum(obs[skill_arm]) / len(obs[skill_arm])
        if all(m_s > sum(obs[a]) / len(obs[a])
               for a in brazos if a != skill_arm):
            wins += 1
    umbral = umbral_base + K // umbral_divisor
    return wins >= umbral, wins, K, umbral


def q1_decisivo_param(brazos, rs_q1, skill_arm, margin):
    m_s = sum(rs_q1[q][skill_arm] for q in e47.PROBE_Q1) / len(e47.PROBE_Q1)
    return all(m_s > sum(rs_q1[q][a] for q in e47.PROBE_Q1) /
               len(e47.PROBE_Q1) + margin
               for a in brazos if a != skill_arm)


def fav_de_prior(brazos, rep_hist, block_sig, b, n0, decay):
    """Brazo favorito del prior no condicionado (misma cuenta que el fav de
    la politica en el camino con probe). Solo diagnostico: no toca RNG."""
    bandit = nuevo_bandit_param(
        brazos, prior_params_param(brazos, rep_hist, block_sig, b, None,
                                   n0, decay), n0)
    return max(brazos, key=lambda a: bandit.mean(a))


# ---------------------------------------------------------------------------
# Politica probe-barato de EXP51, parametrizada + instrumentada con
# diagnosticos por bloque. El computo de la politica es identico al de
# run_experiment56.correr_replica_param (el hoist de skill_existe es
# equivalente porque es pura). Con SC_INIT debe dar EXP51 bit-identico.
# ---------------------------------------------------------------------------
def correr_replica_diag(rep_id, items, tasas, sc):
    brazos = tasas["brazos"]
    H = len(items)
    n_bloques = H // e47.BLOQUE
    rep_hist = {a: [] for a in brazos}
    block_sig = {}
    probe_obs = {}
    rew_pol = [0.0] * H
    rew_fija = {a: [0.0] * H for a in brazos}
    reg_pol_bloques = []
    diag_bloques = []

    ub, ud = sc["umbral_base"], sc["umbral_divisor"]
    gm, n0, decay = sc["gate_margin"], sc["n0"], sc["decay"]

    for b in range(n_bloques):
        base = b * e47.BLOQUE
        sig = e47.firma_grupo([items[base + q]["grupo"]
                               for q in e47.PROBE_Q1])
        block_sig[b] = sig

        # Hoist equivalente: skill_existe es pura (sin RNG).
        skill_ok = e47.skill_existe(rep_hist, block_sig, b, sig)
        skill_arm = None
        saltar = False
        gate = False
        fav_b = None
        if skill_ok:
            skill_arm = e47.skill_arm_actual(brazos, rep_hist, block_sig,
                                             b, sig)
            fuerte, _, _, _ = soporte_param(
                brazos, probe_obs, block_sig, b, sig, skill_arm, ub, ud)
            saltar = fuerte

        clf = e47.MockClasificador(tasas)
        for hh in range(base):
            clf.registrar(items[hh])

        if saltar:
            fav_b = fav_de_prior(brazos, rep_hist, block_sig, b, n0, decay)
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
            reg_b = e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE])
            reg_pol_bloques.append(reg_b)
            diag_bloques.append(diag_de_bloque(
                b, base, brazos, rew_pol, rew_fija, True, skill_ok,
                skill_arm, gate, fav_b))
            continue

        # --- Camino con probe: identico a EXP51 ---
        bandit = nuevo_bandit_param(
            brazos, prior_params_param(brazos, rep_hist, block_sig, b, None,
                                       n0, decay), n0)
        prior_means = {a: bandit.mean(a) for a in brazos}
        fav = max(brazos, key=lambda a: prior_means[a])
        fav_b = fav

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
        if skill_ok:
            usa_skill = True
            bandit = nuevo_bandit_param(
                brazos, prior_params_param(brazos, rep_hist, block_sig, b,
                                           sig, n0, decay), n0)
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
        reg_b = e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE])
        reg_pol_bloques.append(reg_b)
        diag_bloques.append(diag_de_bloque(
            b, base, brazos, rew_pol, rew_fija, False, skill_ok,
            skill_arm, gate, fav_b))

    reg_pol = H - sum(rew_pol)
    reg_fijas = {a: H - sum(rew_fija[a]) for a in brazos}
    mejor = min(brazos, key=lambda a: reg_fijas[a])
    return {"reg_pol": reg_pol, "reg_pol_bloques": reg_pol_bloques,
            "reg_fijas": reg_fijas, "mejor_fija": mejor,
            "reg_mejor_fija": reg_fijas[mejor], "n": H,
            "bloques": diag_bloques}


def diag_de_bloque(b, base, brazos, rew_pol, rew_fija, saltar, skill_ok,
                   skill_arm, gate, fav):
    """Diagnostico por bloque. Referencias: cada item se evaluo en todos los
    brazos, asi que los contrafactuales por bloque son exactos."""
    fija_reg = {a: e47.BLOQUE - sum(rew_fija[a][base:base + e47.BLOQUE])
                for a in brazos}
    best_arm = min(brazos, key=lambda a: fija_reg[a])
    return {
        "b": b,
        "reg": e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]),
        "saltar": saltar,
        "skill_ok": skill_ok,
        "skill_arm": skill_arm,
        "gate": gate,
        "fav": fav,
        "best_arm": best_arm,
        "best_reg": fija_reg[best_arm],
        "skill_reg": fija_reg[skill_arm] if skill_ok else None,
    }


# ---------------------------------------------------------------------------
# Evaluacion (totales) y diagnostico (senales) con cache
# ---------------------------------------------------------------------------
def sc_key(sc):
    return tuple(sorted(sc.items()))


def evaluar(sc, items, tasas, replicas, cache):
    k = (sc_key(sc), tuple(replicas))
    if k not in cache:
        regs = [correr_replica_diag(r, items, tasas, sc)["reg_pol"]
                for r in replicas]
        cache[k] = (sum(regs) / len(regs), regs)
    return cache[k]


def diagnosticar(sc, items, tasas, cache_d):
    """Senales de atribucion de fallos del scaffold en train [0,1,2]."""
    k = sc_key(sc)
    if k not in cache_d:
        s = {"misfire_cost": 0.0, "oportunidad": 0.0, "probe_cost": 0.0,
             "prior_bien": 0.0, "prior_mal": 0.0,
             "n_saltados": 0, "n_con_skill": 0, "n_bloques": 0}
        for r in TRAIN_REPS:
            res = correr_replica_diag(r, items, tasas, sc)
            for bd in res["bloques"]:
                s["n_bloques"] += 1
                if bd["saltar"]:
                    s["n_saltados"] += 1
                    if bd["skill_reg"] > bd["best_reg"]:
                        s["misfire_cost"] += bd["skill_reg"] - bd["best_reg"]
                else:
                    if bd["skill_ok"]:
                        s["n_con_skill"] += 1
                        s["oportunidad"] += max(
                            0.0, bd["reg"] - bd["skill_reg"])
                    err = max(0.0, bd["reg"] - bd["best_reg"])
                    s["probe_cost"] += err
                    if bd["fav"] == bd["best_arm"]:
                        s["prior_bien"] += err
                    else:
                        s["prior_mal"] += err
        cache_d[k] = s
    return cache_d[k]


# ---------------------------------------------------------------------------
# Proponente analitico (pre-registrado en preregistro.md)
# ---------------------------------------------------------------------------
def paso_en(vals, actual, direccion):
    i = vals.index(actual)
    j = i + direccion
    return vals[j] if 0 <= j < len(vals) else None


def candidatos(regla, actual, dir_n0="up"):
    """Dimensiones candidatas en orden de preferencia para cada regla."""
    if regla == "R1":  # endurecer skip
        c = []
        v = paso_en(SPACES["umbral_base"], actual["umbral_base"], +1)
        if v is not None:
            c.append(("umbral_base", v))
        v = paso_en(SPACES["umbral_divisor"], actual["umbral_divisor"], -1)
        if v is not None:
            c.append(("umbral_divisor", v))
        return c
    if regla == "R2":  # ablandar skip
        c = []
        v = paso_en(SPACES["umbral_base"], actual["umbral_base"], -1)
        if v is not None:
            c.append(("umbral_base", v))
        v = paso_en(SPACES["umbral_divisor"], actual["umbral_divisor"], +1)
        if v is not None:
            c.append(("umbral_divisor", v))
        return c
    if regla == "R3":  # ajustar prior
        v = paso_en(SPACES["n0"], actual["n0"],
                    +1 if dir_n0 == "up" else -1)
        return [("n0", v)] if v is not None else []
    return []


def proponer(sig, actual, ronda, tabu):
    """Devuelve (regla, dim, nuevo_val) o (None, None, None) si se abstiene."""
    mf, op, pc = sig["misfire_cost"], sig["oportunidad"], sig["probe_cost"]
    reglas = []
    if mf > op and mf > EPS_SKIP:
        reglas.append(("R1", "up"))
    elif op > mf and op > EPS_SKIP:
        reglas.append(("R2", "up"))
    if pc > (mf + op) and pc > EPS_PROBE:
        dir_n0 = "up" if sig["prior_bien"] >= sig["prior_mal"] else "down"
        reglas.append(("R3", dir_n0))
    for regla, dir_n0 in reglas:
        for (dim, val) in candidatos(regla, actual, dir_n0):
            vetado = any(d == dim and v == val and ronda - rr <= TABU_VENTANA
                         for (d, v, rr) in tabu)
            if not vetado:
                return regla, dim, val
    return None, None, None


# ---------------------------------------------------------------------------
# Loop RSO con proponente analitico
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rondas", type=int, default=N_RONDAS)
    args = ap.parse_args()
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)

    items = e47.construir_stream()
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
    H = len(items)
    n_bloques = H // e47.BLOQUE

    # --- 1. Chequeo de sanidad bit-identica (pre-registrado) ---
    print("Chequeo de sanidad: puerto instrumentado con SC_INIT vs "
          "tratamiento de EXP51...")
    cache = {}
    for r in range(5):
        got = correr_replica_diag(r, items, tasas, dict(SC_INIT))["reg_pol"]
        exp = EXP51_TRAT_TOTALES[r]
        assert abs(got - exp) < 1e-9, (
            f"replica {r}: puerto={got} vs EXP51={exp} — el puerto NO es "
            f"bit-identico, no se corre el loop")
    print("  OK: bit-identico en las 5 replicas "
          f"({EXP51_TRAT_TOTALES}).")

    # --- 2. Loop RSO con proponente analitico ---
    cache_d = {}
    actual = dict(SC_INIT)
    metrica_actual, _ = evaluar(actual, items, tasas, TRAIN_REPS, cache)
    tabu = []  # (dim, val, ronda_rechazo)
    trayectoria = []
    n_keeps = 0
    n_abst = 0
    reglas_usadas = {}
    for ronda in range(1, args.rondas + 1):
        sig = diagnosticar(actual, items, tasas, cache_d)
        regla, dim, nuevo_val = proponer(sig, actual, ronda, tabu)
        if dim is None:
            n_abst += 1
            trayectoria.append({
                "ronda": ronda, "regla": None,
                "senales": {k: round(v, 3) for k, v in sig.items()
                            if isinstance(v, float)},
                "propuesta": None, "abstencion": True,
                "metrica": round(metrica_actual, 4), "keep": False,
            })
            continue
        reglas_usadas[regla] = reglas_usadas.get(regla, 0) + 1
        mutante = dict(actual)
        mutante[dim] = nuevo_val
        metrica_mut, _ = evaluar(mutante, items, tasas, TRAIN_REPS, cache)
        keep = bool(metrica_mut < metrica_actual)
        trayectoria.append({
            "ronda": ronda, "regla": regla,
            "senales": {k: round(v, 3) for k, v in sig.items()
                        if isinstance(v, float)},
            "propuesta": {"dim": dim, "de": actual[dim], "a": nuevo_val},
            "abstencion": False,
            "metrica_antes": round(metrica_actual, 4),
            "metrica_despues": round(metrica_mut, 4),
            "keep": keep,
        })
        if keep:
            actual = mutante
            metrica_actual = metrica_mut
            n_keeps += 1
            tabu = []
        else:
            tabu.append((dim, nuevo_val, ronda))
    evolucionado = actual

    # --- 3. Medicion final en held-out (el loop nunca vio [3,4]) ---
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
    pasa = bool(media_evo_ho < REF_EXP56_EVO)

    report = {
        "experimento": "ALMA-EXP58: RSO con proponente que analiza fallos "
                       "(mock, US$0)",
        "preregistro": "preregistro.md (mismo directorio)",
        "n_items": H, "n_bloques": n_bloques,
        "espacio_mutacion": SPACES,
        "scaffold_inicial": SC_INIT,
        "scaffold_final": evolucionado,
        "cambio_neto": {d: [SC_INIT[d], evolucionado[d]]
                        for d in SPACES if SC_INIT[d] != evolucionado[d]},
        "n_rondas": args.rondas,
        "train_replicas": TRAIN_REPS, "heldout_replicas": HELDOUT_REPS,
        "sanidad_bit_identica_exp51": True,
        "n_keeps": n_keeps, "n_abstenciones": n_abst,
        "reglas_usadas": reglas_usadas,
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
                    "mejora_vs_init": round(mejora_heldout, 4)},
        "referencias": {"exp56_evo": REF_EXP56_EVO, "init": REF_INIT,
                        "exp57b": REF_EXP57B},
        "criterio": "PASS ssi media_heldout(scaffold_EXP58) < 83.00 "
                    "(scaffold evolucionado de EXP56, mismo held-out)",
        "veredicto": "PASS" if pasa else "FAIL",
        "costo_total_usd": 0.0,
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP58 ================")
    print(f"  rondas: {args.rondas} | keeps: {n_keeps}/{args.rondas} | "
          f"abstenciones: {n_abst} | reglas: {reglas_usadas}")
    print(f"  scaffold inicial: {SC_INIT}")
    print(f"  scaffold final:   {evolucionado}")
    print(f"  train [0,1,2]: init {media_init_tr:.3f} -> "
          f"evo {media_evo_tr:.3f} (mejora {mejora_train:+.3f})")
    print(f"  held-out [3,4]: init {media_init_ho:.3f} -> "
          f"evo {media_evo_ho:.3f} (mejora vs init {mejora_heldout:+.3f})")
    print(f"  refs held-out: EXP56-evo {REF_EXP56_EVO:.2f} | "
          f"EXP57-B {REF_EXP57B:.2f} | INIT {REF_INIT:.2f}")
    print("  trayectoria (ronda: regla dim de->a keep metrica):")
    for t in trayectoria:
        if t.get("abstencion"):
            print(f"    r{t['ronda']:02d}: ABSTIENE "
                  f"(mf={t['senales']['misfire_cost']:.1f} "
                  f"op={t['senales']['oportunidad']:.1f} "
                  f"pc={t['senales']['probe_cost']:.1f})")
        else:
            p = t["propuesta"]
            print(f"    r{t['ronda']:02d}: {t['regla']} {p['dim']} "
                  f"{p['de']}->{p['a']} "
                  f"{'KEEP' if t['keep'] else '....'} "
                  f"({t['metrica_antes']:.2f}->{t['metrica_despues']:.2f})")
    print(f"  costo: $0.0000 USD (mock) | {report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL",
          f"(held-out {media_evo_ho:.2f} vs EXP56 {REF_EXP56_EVO:.2f})")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
