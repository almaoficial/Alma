#!/usr/bin/env python3
"""Variante pass^k del tratamiento EXP56 — de Shunyu Yao (τ-bench).

Doctrina (informe §1.2): en τ-bench el éxito se mide como pass^k —
fracción de tareas que salen bien en k intentos independientes — no
como media de un intento. "Lo que se mide se optimiza."

Aplicación: el Thompson del probe se alimenta con puntaje de
consistencia pass^k (k=3): para cada celda (brazo, item) se sortean k
muestras independientes del oráculo; el bandit recibe 1.0 si las k
salen bien, 0.0 si alguna falla. Lo único que cambia es la SEÑAL DE
APRENDIZAJE (bandit.update / rep_hist → prior de Thompson).

La CONTABILIDAD DE REGRET queda intacta: rew_pol, rew_fija y probe_obs
usan el sorteo único crudo, con las mismas seeds que el control — la
comparación tratamiento↔control es pareada y honesta.

Modo k=None: puntaje crudo → bit-idéntico al tratamiento de EXP51
(verificación de que el puerto es verbatim; EXP51_TRAT_TOTALES).

US$0, mock, sin API keys.
"""

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # alma-prototype/
sys.path.insert(0, os.path.join(os.path.dirname(HERE),
                               "exp56_rso"))  # run_experiment56
sys.path.insert(0, HERE)
import run_experiment47 as e47  # noqa: E402
import run_experiment56 as e56  # noqa: E402

K_PASS = 3
EXP51_TRAT_TOTALES = e56.EXP51_TRAT_TOTALES


def puntaje_passk(clf, brazo, it, rep_id, b, q, k=K_PASS):
    """1.0 si el brazo acierta las k muestras independientes; 0.0 si
    alguna falla. Sorteos con seeds propias (no tocan el stream crudo)."""
    for j in range(k):
        r = clf.acierto(
            brazo, it,
            random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{brazo}-pk{j}"))
        if r < 1.0:
            return 0.0
    return 1.0


def correr_replica_passk(rep_id, items, tasas, sc, k=K_PASS):
    """COPIA VERBATIM de e56.correr_replica_param salvo los 4 call sites
    de la señal de aprendizaje (marcados PASSK). Con k=None es
    bit-idéntica al control (mismo regret que EXP51_TRAT_TOTALES)."""
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

    def score(clf, brazo, it, b, q, crudo):
        # PASSK: la única divergencia respecto del control.
        if k is None:
            return crudo
        return puntaje_passk(clf, brazo, it, rep_id, b, q, k)

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
            fuerte, _, _, _ = e56.soporte_param(
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
                rep_hist[skill_arm].append(
                    (h, score(clf, skill_arm, it, b, q, r), b))  # PASSK
                rew_pol[h] = r
                clf.registrar(it)
            reg_pol_bloques.append(
                e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))
            continue

        # --- Camino con probe: idéntico a EXP51 ---
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
                s = score(clf, a, it, b, q, rs[a])  # PASSK
                bandit.update(a, s)
                rep_hist[a].append((h, s, b))
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
            bandit = e56.nuevo_bandit_param(
                brazos, e56.prior_params_param(brazos, rep_hist, block_sig,
                                              b, sig, n0, decay), n0)
            for q in e47.PROBE_Q1:
                for a in brazos:
                    it = items[base + q]
                    bandit.update(  # PASSK
                        a, score(clf, a, it, b, q, rs_q1[q][a]))

        # Gate adaptativo (parametrizado por el margen).
        gate = (skill_arm is not None and usa_skill and
                e56.q1_decisivo_param(brazos, rs_q1, skill_arm, gm))

        def thompson(qs):
            for q in qs:
                h = base + q
                it = items[h]
                a_sel = bandit.select(
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-sel"))
                r_sel = clf.acierto(
                    a_sel, it,
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a_sel}"))
                s = score(clf, a_sel, it, b, q, r_sel)  # PASSK
                bandit.update(a_sel, s)
                rep_hist[a_sel].append((h, s, b))
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


def verificar_copia_verbatim():
    """El puerto con k=None debe reproducir EXP51 bit-idéntico."""
    items = e47.construir_stream()
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
    sc = dict(e56.SC_INIT)
    for r in range(5):
        got = correr_replica_passk(r, items, tasas, sc, k=None)["reg_pol"]
        exp = EXP51_TRAT_TOTALES[r]
        assert abs(got - exp) < 1e-9, (
            f"réplica {r}: puerto={got} vs EXP51={exp}")
    return True


if __name__ == "__main__":
    verificar_copia_verbatim()
    print("OK: puerto verbatim (k=None) bit-idéntico a EXP51 en 5/5.")
