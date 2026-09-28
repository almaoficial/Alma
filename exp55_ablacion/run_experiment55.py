#!/usr/bin/env python3
"""ALMA-EXP55: ablación TTRL — ¿el valor está en el voto o en el commit?
(mock, US$0).

Continuación pre-registrada de EXP54 (PASS frágil, efecto −2,20 cargado por
una réplica; el voto acierta 48,7% y su accuracy no predice el efecto).
Dos variantes contra el mismo control (EXP51 verbatim):

- Variante A ("consenso-sin-commit"): consenso round-robin en 3,4,5
  idéntico a EXP54 (mismos candidatos, mismos sorteos, bandit informado),
  pero el ganador se IGNORA; el juego posterior es idéntico al control.
- Variante B ("commit-sin-consenso"): sin rollouts de consenso; commit
  greedy inmediato al top-1 post-probe en los items que el control juega
  con Thompson.

Mismo stream de 24 bloques bit-idéntico, 5 réplicas pareadas, RNG común.
Pre-registro: exp55_ablacion/preregistro.md (ANTES de correr).

Uso:
    python3 run_experiment55.py [--out DIR] [--replicas N]
"""

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
import run_experiment47 as e47  # noqa: E402  (maquinaria base)
import run_experiment49 as e49  # noqa: E402  (soporte_endurecido)
import run_experiment51 as e51  # noqa: E402  (control verbatim)

BASE = os.path.dirname(os.path.abspath(__file__))
PADRE = os.path.dirname(BASE)  # alma-prototype/ (convención de resultados)
EXP51_REPORT = os.path.join(PADRE, "resultados", "exp51-20260927",
                            "report.json")
EXP54_REPORT = os.path.join(PADRE, "resultados", "exp54-20260927",
                            "report.json")


def _camino_probe_comun(rep_id, items, tasas):
    """Devuelve el estado compartido hasta el juego post-probe, idéntico a
    EXP51/EXP54: skip, Q1, recondicionamiento por skill, gate.

    Retorna dict con brazos, H, n_bloques, rep_hist, block_sig, probe_obs,
    rew_pol, rew_fija, reg_pol_bloques, diag, skills_usadas, probes_saltados,
    saltados_det, q2_saltados, bandit, clf, fav, rs_q1, gate, usa_skill,
    skill_arm, wins, K, umbral, sig, b, base + helpers medir/thompson/jugar.

    NOTA: por claridad cada variante implementa su propio loop; esta función
    no se usa directamente. Se documenta el contrato que ambas cumplen.
    """
    raise NotImplementedError("contrato documentado; ver variantes")


def correr_replica_A(rep_id, items, tasas):
    """Variante A: consenso idéntico a EXP54 en 3,4,5, ganador IGNORADO,
    juego posterior idéntico al control (gate + Thompson / re-probe + T)."""
    brazos = tasas["brazos"]
    H = len(items)
    n_bloques = H // e47.BLOQUE
    rep_hist = {a: [] for a in brazos}
    block_sig = {}
    probe_obs = {}
    rew_pol = [0.0] * H
    rew_fija = {a: [0.0] * H for a in brazos}
    reg_pol_bloques = []
    diag = []
    skills_usadas = 0
    probes_saltados = 0
    saltados_det = []
    q2_saltados = 0

    for b in range(n_bloques):
        base = b * e47.BLOQUE
        sig = e47.firma_grupo([items[base + q]["grupo"]
                               for q in e47.PROBE_Q1])
        block_sig[b] = sig

        saltar = False
        skill_arm = None
        wins = 0
        K = None
        umbral = None
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            skill_arm = e47.skill_arm_actual(brazos, rep_hist, block_sig,
                                             b, sig)
            fuerte, wins, K, umbral = e49.soporte_endurecido(
                brazos, probe_obs, block_sig, b, sig, skill_arm)
            saltar = fuerte

        clf = e47.MockClasificador(tasas)
        for hh in range(base):
            clf.registrar(items[hh])

        if saltar:
            # PROBE SALTADO: idéntico al control.
            probes_saltados += 1
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
            acc = {a: sum(rew_fija[a][base:base + e47.BLOQUE]) / e47.BLOQUE
                   for a in brazos}
            mejor = max(brazos, key=lambda a: acc[a])
            saltados_det.append({
                "bloque": b, "firma": sig, "brazo_skill": skill_arm,
                "soporte_wins": wins, "K_oportunidades": K,
                "umbral_exigido": umbral,
                "acc_skill": round(acc[skill_arm], 4),
                "mejor_expost": mejor, "acc_mejor": round(acc[mejor], 4),
                "misfire": bool(mejor != skill_arm),
            })
            reg_pol_bloques.append(
                e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))
            diag.append({
                "bloque": b, "regimen": items[base]["regimen"], "firma": sig,
                "probe_saltado": True, "soporte_wins": wins,
                "K_oportunidades": K, "umbral_exigido": umbral,
                "brazo_skill": skill_arm,
                "acc_pol": round(
                    sum(rew_pol[base:base + e47.BLOQUE]) / e47.BLOQUE, 4),
                "acc_fijas": {
                    a: round(sum(rew_fija[a][base:base + e47.BLOQUE]) /
                             e47.BLOQUE, 4)
                    for a in brazos},
            })
            continue

        bandit = e47.nuevo_bandit(
            brazos, e47.prior_params(brazos, rep_hist, block_sig, b, None))
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
            rs_q1[q] = medir(q)
            rew_pol[base + q] = rs_q1[q][fav]

        usa_skill = False
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            usa_skill = True
            skills_usadas += 1
            bandit = e47.nuevo_bandit(
                brazos, e47.prior_params(brazos, rep_hist, block_sig, b, sig))
            for q in e47.PROBE_Q1:
                for a in brazos:
                    bandit.update(a, rs_q1[q][a])

        gate = (skill_arm is not None and usa_skill and
                e51.q1_decisivo(brazos, rs_q1, skill_arm))

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

        def jugar(q, a):
            h = base + q
            it = items[h]
            r = clf.acierto(
                a, it, random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
            bandit.update(a, r)
            rep_hist[a].append((h, r, b))
            rew_pol[h] = r
            for a2 in brazos:
                rew_fija[a2][h] = clf.acierto(
                    a2, it,
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a2}"))
            clf.registrar(it)
            return r

        # Consenso idéntico a EXP54 (información SÍ, commit NO).
        medias_post = {a: bandit.mean(a) for a in brazos}
        cands = sorted(brazos,
                       key=lambda a: (-medias_post[a], brazos.index(a)))
        c1, c2 = cands[0], cands[1]
        obs = {c1: [], c2: []}
        for q, a in zip((3, 4, 5), (c1, c2, c1)):
            obs[a].append(jugar(q, a))
        m1 = sum(obs[c1]) / len(obs[c1])
        m2 = sum(obs[c2]) / len(obs[c2])
        ganador_ignorado = c1 if m1 > m2 else (c2 if m2 > m1 else None)

        # ============ MOVING PART A: se ignora el ganador ============
        # Juego posterior IDÉNTICO al control.
        if gate:
            q2_saltados += 1
            thompson((6, 7, 8, 9))
            commit_hubiera = (6, 7, 8, 9)
        else:
            rs_q2 = {}
            for q in e47.PROBE_Q2:
                rs_q2[q] = medir(q)
                rew_pol[base + q] = rs_q2[q][fav]
            thompson((8, 9))
            commit_hubiera = (8, 9)
        # ==============================================================

        # Diagnóstico: ¿el voto identificaba bien aunque no se usara?
        ganador_hubiera_sido_mejor = None
        if ganador_ignorado is not None:
            acc_commit = {
                a: sum(rew_fija[a][base + q] for q in commit_hubiera) /
                len(commit_hubiera) for a in brazos}
            mejor_commit = max(brazos, key=lambda a: acc_commit[a])
            ganador_hubiera_sido_mejor = bool(
                ganador_ignorado == mejor_commit)

        if gate:
            probe_obs[b] = {a: [rs_q1[q][a] for q in e47.PROBE_Q1]
                            for a in brazos}
        else:
            probe_obs[b] = {a: [rs_q1[q][a] for q in e47.PROBE_Q1] +
                               [rs_q2[q][a] for q in e47.PROBE_Q2]
                            for a in brazos}
        reg_pol_bloques.append(
            e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))

        diag.append({
            "bloque": b, "regimen": items[base]["regimen"], "firma": sig,
            "probe_saltado": False, "soporte_wins": wins,
            "K_oportunidades": K, "umbral_exigido": umbral,
            "skill_usada": usa_skill,
            "q1_decisivo": bool(gate),
            "q2_saltado": bool(gate),
            "ttrl_candidatos": [c1, c2],
            "ttrl_ganador_ignorado": ganador_ignorado,
            "ttrl_ganador_hubiera_sido_mejor": ganador_hubiera_sido_mejor,
            "acc_pol": round(
                sum(rew_pol[base:base + e47.BLOQUE]) / e47.BLOQUE, 4),
            "acc_fijas": {
                a: round(sum(rew_fija[a][base:base + e47.BLOQUE]) /
                         e47.BLOQUE, 4)
                for a in brazos},
        })

    total_aciertos = sum(1 for d in diag
                         if d.get("ttrl_ganador_hubiera_sido_mejor") is True)
    total_votos = sum(1 for d in diag
                      if d.get("ttrl_ganador_ignorado") is not None)

    reg_pol = H - sum(rew_pol)
    reg_fijas = {a: H - sum(rew_fija[a]) for a in brazos}
    mejor = min(brazos, key=lambda a: reg_fijas[a])
    return {"politica": "A_consenso_sin_commit", "reg_pol": reg_pol,
            "reg_pol_bloques": reg_pol_bloques,
            "reg_fijas": reg_fijas,
            "mejor_fija": mejor, "reg_mejor_fija": reg_fijas[mejor],
            "skills_usadas": skills_usadas, "probes_saltados": probes_saltados,
            "q2_saltados": q2_saltados,
            "a_votos": total_votos,
            "a_ganador_aciertos_expost": total_aciertos,
            "saltados_det": saltados_det, "n_bloques": n_bloques,
            "diag": diag, "n": H}


def correr_replica_B(rep_id, items, tasas):
    """Variante B: sin consenso; commit greedy inmediato al top-1 post-probe
    en todos los items que el control juega con Thompson."""
    brazos = tasas["brazos"]
    H = len(items)
    n_bloques = H // e47.BLOQUE
    rep_hist = {a: [] for a in brazos}
    block_sig = {}
    probe_obs = {}
    rew_pol = [0.0] * H
    rew_fija = {a: [0.0] * H for a in brazos}
    reg_pol_bloques = []
    diag = []
    skills_usadas = 0
    probes_saltados = 0
    saltados_det = []
    q2_saltados = 0
    commits = 0

    for b in range(n_bloques):
        base = b * e47.BLOQUE
        sig = e47.firma_grupo([items[base + q]["grupo"]
                               for q in e47.PROBE_Q1])
        block_sig[b] = sig

        saltar = False
        skill_arm = None
        wins = 0
        K = None
        umbral = None
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            skill_arm = e47.skill_arm_actual(brazos, rep_hist, block_sig,
                                             b, sig)
            fuerte, wins, K, umbral = e49.soporte_endurecido(
                brazos, probe_obs, block_sig, b, sig, skill_arm)
            saltar = fuerte

        clf = e47.MockClasificador(tasas)
        for hh in range(base):
            clf.registrar(items[hh])

        if saltar:
            probes_saltados += 1
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
            acc = {a: sum(rew_fija[a][base:base + e47.BLOQUE]) / e47.BLOQUE
                   for a in brazos}
            mejor = max(brazos, key=lambda a: acc[a])
            saltados_det.append({
                "bloque": b, "firma": sig, "brazo_skill": skill_arm,
                "soporte_wins": wins, "K_oportunidades": K,
                "umbral_exigido": umbral,
                "acc_skill": round(acc[skill_arm], 4),
                "mejor_expost": mejor, "acc_mejor": round(acc[mejor], 4),
                "misfire": bool(mejor != skill_arm),
            })
            reg_pol_bloques.append(
                e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))
            diag.append({
                "bloque": b, "regimen": items[base]["regimen"], "firma": sig,
                "probe_saltado": True, "soporte_wins": wins,
                "K_oportunidades": K, "umbral_exigido": umbral,
                "brazo_skill": skill_arm,
                "acc_pol": round(
                    sum(rew_pol[base:base + e47.BLOQUE]) / e47.BLOQUE, 4),
                "acc_fijas": {
                    a: round(sum(rew_fija[a][base:base + e47.BLOQUE]) /
                             e47.BLOQUE, 4)
                    for a in brazos},
            })
            continue

        bandit = e47.nuevo_bandit(
            brazos, e47.prior_params(brazos, rep_hist, block_sig, b, None))
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
            rs_q1[q] = medir(q)
            rew_pol[base + q] = rs_q1[q][fav]

        usa_skill = False
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            usa_skill = True
            skills_usadas += 1
            bandit = e47.nuevo_bandit(
                brazos, e47.prior_params(brazos, rep_hist, block_sig, b, sig))
            for q in e47.PROBE_Q1:
                for a in brazos:
                    bandit.update(a, rs_q1[q][a])

        gate = (skill_arm is not None and usa_skill and
                e51.q1_decisivo(brazos, rs_q1, skill_arm))

        def jugar(q, a):
            h = base + q
            it = items[h]
            r = clf.acierto(
                a, it, random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
            bandit.update(a, r)
            rep_hist[a].append((h, r, b))
            rew_pol[h] = r
            for a2 in brazos:
                rew_fija[a2][h] = clf.acierto(
                    a2, it,
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a2}"))
            clf.registrar(it)
            return r

        # ============ ÚNICO MOVING PART B: commit greedy al top-1 ============
        # post-probe, SIN rollouts de consenso. c1 = el candidato #1 que
        # EXP54 habría elegido (misma ordenación).
        medias_post = {a: bandit.mean(a) for a in brazos}
        c1 = sorted(brazos,
                    key=lambda a: (-medias_post[a], brazos.index(a)))[0]
        commits += 1
        for q in (3, 4, 5):
            jugar(q, c1)
        if gate:
            q2_saltados += 1
            for q in (6, 7, 8, 9):
                jugar(q, c1)
            commit_items = (3, 4, 5, 6, 7, 8, 9)
        else:
            rs_q2 = {}
            for q in e47.PROBE_Q2:
                rs_q2[q] = medir(q)
                rew_pol[base + q] = rs_q2[q][fav]
            for q in (8, 9):
                jugar(q, c1)
            commit_items = (3, 4, 5, 8, 9)
        # =====================================================================

        c1_fue_mejor = None
        acc_commit = {
            a: sum(rew_fija[a][base + q] for q in commit_items) /
            len(commit_items) for a in brazos}
        mejor_commit = max(brazos, key=lambda a: acc_commit[a])
        c1_fue_mejor = bool(c1 == mejor_commit)

        if gate:
            probe_obs[b] = {a: [rs_q1[q][a] for q in e47.PROBE_Q1]
                            for a in brazos}
        else:
            probe_obs[b] = {a: [rs_q1[q][a] for q in e47.PROBE_Q1] +
                               [rs_q2[q][a] for q in e47.PROBE_Q2]
                            for a in brazos}
        reg_pol_bloques.append(
            e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))

        diag.append({
            "bloque": b, "regimen": items[base]["regimen"], "firma": sig,
            "probe_saltado": False, "soporte_wins": wins,
            "K_oportunidades": K, "umbral_exigido": umbral,
            "skill_usada": usa_skill,
            "q1_decisivo": bool(gate),
            "q2_saltado": bool(gate),
            "b_commit_arm": c1,
            "b_commit_fue_mejor_expost": c1_fue_mejor,
            "acc_pol": round(
                sum(rew_pol[base:base + e47.BLOQUE]) / e47.BLOQUE, 4),
            "acc_fijas": {
                a: round(sum(rew_fija[a][base:base + e47.BLOQUE]) /
                         e47.BLOQUE, 4)
                for a in brazos},
        })

    total_aciertos = sum(1 for d in diag
                         if d.get("b_commit_fue_mejor_expost") is True)
    n_commit_bloques = sum(1 for d in diag if "b_commit_arm" in d)

    reg_pol = H - sum(rew_pol)
    reg_fijas = {a: H - sum(rew_fija[a]) for a in brazos}
    mejor = min(brazos, key=lambda a: reg_fijas[a])
    return {"politica": "B_commit_sin_consenso", "reg_pol": reg_pol,
            "reg_pol_bloques": reg_pol_bloques,
            "reg_fijas": reg_fijas,
            "mejor_fija": mejor, "reg_mejor_fija": reg_fijas[mejor],
            "skills_usadas": skills_usadas, "probes_saltados": probes_saltados,
            "q2_saltados": q2_saltados,
            "b_commit_bloques": n_commit_bloques,
            "b_commit_aciertos_expost": total_aciertos,
            "saltados_det": saltados_det, "n_bloques": n_bloques,
            "diag": diag, "n": H}


def _resumen_variante(nombre, det):
    n = len(det)
    efectos = [d["efecto"] for d in det]
    media_ef = sum(efectos) / n
    mejor = min(efectos)
    sin_mejor = (sum(efectos) - mejor) / (n - 1) if n > 1 else media_ef
    cargado = bool(sin_mejor >= 0) if n > 1 else False
    reg_var = sum(d["reg_variante"] for d in det) / n
    reg_ctrl = sum(d["reg_control"] for d in det) / n
    reg_fija = sum(d["reg_mejor_fija"] for d in det) / n
    return {
        "variante": nombre,
        "efecto_medio": round(media_ef, 3),
        "efecto_por_replica": [round(e, 3) for e in efectos],
        "media_efecto_sin_mejor_replica": round(sin_mejor, 3),
        "cargado_por_una_sola_replica": cargado,
        "reg_variante_medio": round(reg_var, 3),
        "reg_control_medio": round(reg_ctrl, 3),
        "reg_mejor_fija_medio": round(reg_fija, 3),
        "distancia_variante_a_mejor_fija": round(reg_var - reg_fija, 3),
        "pass": bool(media_ef < 0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--replicas", type=int, default=e47.N_REPLICAS)
    args = ap.parse_args()
    t0 = time.time()

    out = args.out or os.path.join(PADRE, "resultados", "exp55-20260927")
    os.makedirs(out, exist_ok=True)

    items = e47.construir_stream()  # bit-idéntico al stream de EXP47-55
    H = len(items)
    n_bloques = H // e47.BLOQUE
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))

    with open(os.path.join(BASE, "preregistro.md"), encoding="utf-8") as f:
        prereg_md = f.read()
    with open(os.path.join(out, "preregistro.json"), "w",
              encoding="utf-8") as f:
        json.dump({
            "experimento": "ALMA-EXP55: ablación TTRL (mock, US$0)",
            "preregistro_md": "exp55_ablacion/preregistro.md (pre-registro "
                              "vinculante, escrito antes de correr)",
            "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "criterio": "PASS_X ⟺ media(regret(X) − regret(control)) < 0, "
                        "5 réplicas pareadas",
            "regla_interpretacion": "A PASS+B FAIL→voto; B PASS+A FAIL→"
                "commit; ambos PASS→comparar magnitudes vs EXP54(−2,20); "
                "ambos FAIL→EXP54 fue ruido",
        }, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro verificado ({H} items, {n_bloques} bloques, "
          f"{args.replicas} réplicas pareadas).")

    detA, detB = [], []
    for r in range(args.replicas):
        ctrl = e51.correr_replica_probe_barato(r, items, tasas)
        va = correr_replica_A(r, items, tasas)
        vb = correr_replica_B(r, items, tasas)
        detA.append({
            "replica": r,
            "efecto": round(va["reg_pol"] - ctrl["reg_pol"], 3),
            "reg_control": round(ctrl["reg_pol"], 3),
            "reg_variante": round(va["reg_pol"], 3),
            "reg_control_bloques": [round(x, 3)
                                    for x in ctrl["reg_pol_bloques"]],
            "reg_mejor_fija": round(ctrl["reg_mejor_fija"], 3),
            "mejor_fija": ctrl["mejor_fija"],
            "q2_saltados_var": va["q2_saltados"],
            "q2_saltados_control": ctrl["q2_saltados"],
            "skips_var": va["probes_saltados"],
            "skips_control": ctrl["probes_saltados"],
            "a_votos": va["a_votos"],
            "a_ganador_aciertos_expost": va["a_ganador_aciertos_expost"],
        })
        detB.append({
            "replica": r,
            "efecto": round(vb["reg_pol"] - ctrl["reg_pol"], 3),
            "reg_control": round(ctrl["reg_pol"], 3),
            "reg_variante": round(vb["reg_pol"], 3),
            "reg_mejor_fija": round(ctrl["reg_mejor_fija"], 3),
            "mejor_fija": ctrl["mejor_fija"],
            "q2_saltados_var": vb["q2_saltados"],
            "skips_var": vb["probes_saltados"],
            "b_commit_bloques": vb["b_commit_bloques"],
            "b_commit_aciertos_expost": vb["b_commit_aciertos_expost"],
        })
        if r == 0:
            diag_rep0 = {"control": ctrl["diag"][:3],
                         "varianteA": va["diag"][:3],
                         "varianteB": vb["diag"][:3]}

    resA = _resumen_variante("A_consenso_sin_commit", detA)
    resB = _resumen_variante("B_commit_sin_consenso", detB)

    # Referencia EXP54 (no re-corrido; mismo RNG/stream por construcción).
    ref54 = None
    try:
        r54 = json.load(open(EXP54_REPORT, encoding="utf-8"))
        ref54 = {"efecto_medio": r54["efecto_medio"],
                 "efecto_por_replica": r54["efecto_por_replica"],
                 "reg_tratamiento_medio": r54["reg_tratamiento_medio"],
                 "reg_control_medio": r54["reg_control_medio"],
                 "reg_mejor_fija_medio": r54["reg_mejor_fija_medio"]}
    except Exception as e:  # noqa: BLE001
        ref54 = f"no verificable: {e}"

    # Reproducibilidad: el control debe ser bit-idéntico al TRATAMIENTO de
    # EXP51 (columna reg_trat_bloques).
    repro_ok = None
    try:
        rep51 = json.load(open(EXP51_REPORT, encoding="utf-8"))
        d51 = {d["replica"]: (d["reg_trat_bloques"], d["q2_saltados_trat"])
               for d in rep51["detalle_replicas"]}
        repro_ok = all(
            [round(x, 3) for x in detA[r]["reg_control_bloques"]] ==
            [round(x, 3) for x in d51[r][0]]
            for r in range(args.replicas))
    except Exception as e:  # noqa: BLE001
        repro_ok = f"no verificable: {e}"

    # Regla de interpretación pre-registrada.
    pA, pB = resA["pass"], resB["pass"]
    if pA and not pB:
        interp = ("A PASS + B FAIL → el valor está en el VOTO "
                  "(identificación), no en el commit greedy.")
    elif pB and not pA:
        interp = ("B PASS + A FAIL → el valor está en el COMMIT temprano; "
                  "el consenso es lastre.")
    elif pA and pB:
        interp = ("Ambos PASS → ambos componentes aportan; comparar "
                  "magnitudes contra EXP54 (−2,20).")
    else:
        interp = ("Ambos FAIL → EXP54 no era un mecanismo: fue fragilidad "
                  "entre réplicas. TTRL se archiva como refutado.")

    motivos = [
        f"items={H}, bloques={n_bloques}, réplicas pareadas={args.replicas}",
        f"Variante A (consenso sin commit): efecto medio "
        f"{resA['efecto_medio']:+.3f} (por réplica: "
        f"{', '.join(f'{e:+.2f}' for e in resA['efecto_por_replica'])}) → "
        f"{'PASS' if pA else 'FAIL'}",
        f"Variante B (commit sin consenso): efecto medio "
        f"{resB['efecto_medio']:+.3f} (por réplica: "
        f"{', '.join(f'{e:+.2f}' for e in resB['efecto_por_replica'])}) → "
        f"{'PASS' if pB else 'FAIL'}",
        f"A sin mejor réplica: {resA['media_efecto_sin_mejor_replica']:+.2f} "
        f"(¿cargado? {'SÍ' if resA['cargado_por_una_sola_replica'] else 'NO'})",
        f"B sin mejor réplica: {resB['media_efecto_sin_mejor_replica']:+.2f} "
        f"(¿cargado? {'SÍ' if resB['cargado_por_una_sola_replica'] else 'NO'})",
        f"distancia a mejor fija — A: "
        f"{resA['distancia_variante_a_mejor_fija']:.2f} | B: "
        f"{resB['distancia_variante_a_mejor_fija']:.2f} "
        f"(control ~2,20; EXP54 0,00)",
        f"A: ganador ignorado = mejor ex-post en "
        f"{sum(d['a_ganador_aciertos_expost'] for d in detA)}/"
        f"{sum(d['a_votos'] for d in detA)} votos",
        f"B: c1 = mejor ex-post en "
        f"{sum(d['b_commit_aciertos_expost'] for d in detB)}/"
        f"{sum(d['b_commit_bloques'] for d in detB)} bloques con probe",
        f"referencia EXP54: efecto {ref54['efecto_medio'] if isinstance(ref54, dict) else ref54}",
        f"reproducibilidad control vs EXP51 (bit-idéntico): {repro_ok}",
        f"INTERPRETACIÓN PRE-REGISTRADA: {interp}",
    ]
    report = {
        "preregistro": "preregistro.json + exp55_ablacion/preregistro.md",
        "n_items": H, "n_bloques": n_bloques,
        "varianteA": {**resA, "detalle_replicas": detA},
        "varianteB": {**resB, "detalle_replicas": detB},
        "referencia_exp54": ref54,
        "diagnostico_bloques_rep0": diag_rep0,
        "reproducibilidad_exp51": repro_ok,
        "interpretacion": interp,
        "costo_total_usd": 0.0,
        "veredicto": {
            "pass_A": pA, "pass_B": pB,
            "criterio": "PASS_X ⟺ media(efecto_X) < 0",
            "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP55 ================")
    for m in motivos:
        print("  " + m)
    print("  costo: $0.0000 USD (mock) | "
          f"{report['duracion_s']}s")
    print("  RESULTADO: A " + ("PASS" if pA else "FAIL") +
          " | B " + ("PASS" if pB else "FAIL"))
    print("==================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
