#!/usr/bin/env python3
"""ALMA-EXP54: TTRL — adaptación online intra-bloque (mock, US$0).

Segunda idea de la serie "ideas orientales" (EXP53 refutó el banco de skills
versionado/SkillRL con efecto +5,20). La línea EXP45–52 sigue cerrada.

Idea: TTRL (idea 6 del catálogo oriental) — test-time learning: la política
sigue aprendiendo durante la inferencia. Aquí, adaptación intra-bloque:
después del probe, la política gasta los items 3,4,5 en rollouts de consenso
round-robin entre los dos brazos candidatos (top-2 por media del bandit
post-probe) y puede cambiar de brazo a mitad de bloque por voto de consenso,
jugando greedy el ganador en los items Thompson restantes.

Diseño:
- Control: la política de EXP51 VERBATIM
  (run_experiment51.correr_replica_probe_barato, importada).
- Tratamiento ("ttrl"): COPIA VERBATIM del control, salvo UN moving part:
  el juego post-probe en bloques CON probe. Los bloques saltados son
  idénticos al control. probe_obs, Q1, Q2, gate y skip: idénticos.
- Mismo stream de 24 bloques bit-idéntico, 5 réplicas pareadas, RNG común.

Criterio PRE-REGISTRADO:
  pasa_1: media sobre réplicas pareadas de regret(trat)-regret(ctrl) < 0.

Uso:
    python3 run_experiment54.py [--out DIR] [--replicas N]
"""

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_experiment47 as e47  # noqa: E402  (maquinaria base)
import run_experiment49 as e49  # noqa: E402  (soporte_endurecido)
import run_experiment51 as e51  # noqa: E402  (control verbatim)

BASE = os.path.dirname(os.path.abspath(__file__))
PADRE = os.path.dirname(BASE)  # alma-prototype/ (convención de resultados)
EXP51_REPORT = os.path.join(PADRE, "resultados", "exp51-20260927",
                            "report.json")


def correr_replica_ttrl(rep_id, items, tasas):
    """Tratamiento TTRL de EXP54.

    COPIA VERBATIM del probe-barato de EXP51
    (e51.correr_replica_probe_barato): misma lógica, mismos seeds de RNG,
    mismo orden de sorteos, misma contabilidad honesta, mismo diagnóstico.
    El ÚNICO moving part: en el camino con probe, el juego post-probe deja
    de ser Thompson puro:
      1. candidatos = top-2 brazos por media del bandit post-probe
         (desempate determinista: menor índice);
      2. consenso: items 3,4,5 en round-robin c1, c2, c1 (cada jugada
         observa solo el brazo jugado; sorteos del oráculo pareados);
      3. voto: ganador = media estrictamente mayor (m_c1 sobre {3,5} vs
         m_c2 sobre {4}); empate -> sin ganador;
      4. commit: si hay ganador, greedy en los items Thompson restantes
         (gate: 6,7,8,9; sin gate: 8,9); si no, Thompson idéntico al
         control.
    probe_obs, Q1, Q2, gate, skip: idénticos al control por construcción.
    """
    brazos = tasas["brazos"]
    H = len(items)
    n_bloques = H // e47.BLOQUE
    rep_hist = {a: [] for a in brazos}  # (h, reward, bloque)
    block_sig = {}
    probe_obs = {}  # b -> {brazo: [rewards en items de probe]} | None
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
            # PROBE SALTADO: idéntico a EXP51 (sin probe, sin gate, sin TTRL).
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

        # --- Camino con probe: idéntico a EXP51 hasta el juego post-probe ---
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

        # PROBE Q1: bit-idéntico al control.
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

        # Gate adaptativo: idéntico a EXP51.
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
            """Una jugada determinista del brazo a en el item q (consenso o
            commit greedy). Observa solo el brazo jugado; el accounting
            ex-post de todos los brazos sigue la convención del control."""
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

        # ============ ÚNICO MOVING PART: módulo TTRL ============
        # Candidatos: top-2 por media del bandit post-probe (desempate
        # determinista por índice). Estado del bandit: prior + Q1 +
        # recondicionamiento por skill — igual que el control al empezar
        # el Thompson de 3,4,5.
        medias_post = {a: bandit.mean(a) for a in brazos}
        cands = sorted(brazos,
                       key=lambda a: (-medias_post[a], brazos.index(a)))
        c1, c2 = cands[0], cands[1]
        # Consenso round-robin en 3,4,5 (reemplaza al Thompson del control).
        obs = {c1: [], c2: []}
        for q, a in zip((3, 4, 5), (c1, c2, c1)):
            obs[a].append(jugar(q, a))
        m1 = sum(obs[c1]) / len(obs[c1])
        m2 = sum(obs[c2]) / len(obs[c2])
        ganador = c1 if m1 > m2 else (c2 if m2 > m1 else None)
        # =========================================================

        resto_gate = tuple(q for q in e47.PROBE_Q2)  # (6,7)
        resto_fin = tuple(q for q in e47.THOMPSON_Q
                          if q > e47.PROBE_Q2[-1])  # (8,9)
        if gate:
            q2_saltados += 1
            commit_items = resto_gate + resto_fin
            if ganador is not None:
                for q in commit_items:
                    jugar(q, ganador)
            else:
                thompson(commit_items)
        else:
            # RE-PROBE Q2: idéntico al control, scoring honesto con fav ciego.
            rs_q2 = {}
            for q in e47.PROBE_Q2:
                rs_q2[q] = medir(q)
                rew_pol[base + q] = rs_q2[q][fav]
            if ganador is not None:
                for q in resto_fin:
                    jugar(q, ganador)
                commit_items = resto_fin
            else:
                thompson(resto_fin)
                commit_items = ()

        # Diagnóstico del voto: ¿el ganador fue el mejor ex-post en los
        # items de commit? (solo informativo, no cambia el veredicto)
        ganador_fue_mejor = None
        if ganador is not None and commit_items:
            acc_commit = {
                a: sum(rew_fija[a][base + q] for q in commit_items) /
                len(commit_items) for a in brazos}
            mejor_commit = max(brazos, key=lambda a: acc_commit[a])
            ganador_fue_mejor = bool(ganador == mejor_commit)

        # probe_obs: idéntico al control (sin jugadas de consenso).
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
            "ttrl_ganador": ganador,
            "ttrl_commit": ganador is not None,
            "ttrl_ganador_fue_mejor_expost": ganador_fue_mejor,
            "acc_pol": round(
                sum(rew_pol[base:base + e47.BLOQUE]) / e47.BLOQUE, 4),
            "acc_fijas": {
                a: round(sum(rew_fija[a][base:base + e47.BLOQUE]) /
                         e47.BLOQUE, 4)
                for a in brazos},
        })

    # acumular el diagnóstico del voto (definido por bloque arriba)
    total_aciertos = sum(1 for d in diag
                         if d.get("ttrl_ganador_fue_mejor_expost") is True)
    total_commits = sum(1 for d in diag if d.get("ttrl_commit") is True)
    n_probados = sum(1 for d in diag if "ttrl_commit" in d)

    reg_pol = H - sum(rew_pol)
    reg_fijas = {a: H - sum(rew_fija[a]) for a in brazos}
    mejor = min(brazos, key=lambda a: reg_fijas[a])
    return {"politica": "ttrl", "reg_pol": reg_pol,
            "reg_pol_bloques": reg_pol_bloques,
            "reg_fijas": reg_fijas,
            "mejor_fija": mejor, "reg_mejor_fija": reg_fijas[mejor],
            "skills_usadas": skills_usadas, "probes_saltados": probes_saltados,
            "q2_saltados": q2_saltados,
            "ttrl_consenso_bloques": n_probados,
            "ttrl_commits": total_commits,
            "ttrl_fallbacks": n_probados - total_commits,
            "ttrl_ganador_aciertos_expost": total_aciertos,
            "saltados_det": saltados_det, "n_bloques": n_bloques,
            "diag": diag, "n": H}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--replicas", type=int, default=e47.N_REPLICAS)
    args = ap.parse_args()
    t0 = time.time()

    out = args.out or os.path.join(PADRE, "resultados", "exp54-20260927")
    os.makedirs(out, exist_ok=True)

    items = e47.construir_stream()  # bit-idéntico al stream de EXP47-53
    H = len(items)
    n_bloques = H // e47.BLOQUE
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))

    # --- pre-registro ANTES de correr ---
    prereg = {
        "experimento": "ALMA-EXP54: TTRL — adaptación online intra-bloque "
                       "(mock, US$0)",
        "fase": "mock",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "hipotesis": "En los bloques con probe, gastar los items 3,4,5 en "
                     "rollouts de consenso round-robin entre los dos brazos "
                     "con mayor media del bandit post-probe y jugar greedy "
                     "el ganador del consenso en los items Thompson "
                     "restantes reduce el regret frente al Thompson "
                     "post-probe de EXP51, porque el consenso compra "
                     "identificación barata a mitad de bloque.",
        "nota_refutacion": "Riesgo doble: (1) 3 rollouts son ruidosos "
                           "(~2/10 de ruido por bloque) y pueden coronar al "
                           "brazo equivocado; (2) el commit greedy abandona "
                           "la exploración de Thompson y amplifica el error "
                           "en 2-4 items si el consenso se equivoca. Si el "
                           "efecto >= 0, la adaptación intra-bloque no "
                           "compra nada en este mundo.",
        "condicion_alcance": e47.CONDICION_ALCANCE,
        "stream": {
            "fuente": "IDÉNTICO al de EXP47/48/49/50/51/53 (misma función "
                      "run_experiment47.construir_stream, bit-idéntico): 240 "
                      "items, 24 bloques x 10, 3 regímenes x 8 recurrencias.",
            "n_items": H, "bloques": n_bloques,
            "tam_bloque": e47.BLOQUE,
            "regimenes": e47.REGIMENES,
            "oraculo": "tasas mock calibradas por categoría "
                       "(data_exp44/tasas.json)",
            "sesgo_seleccion": e47.SESGO_SELECCION,
        },
        "politicas": {
            "control": "La política de EXP51 VERBATIM "
                       "(run_experiment51.correr_replica_probe_barato, "
                       "importada sin copiar).",
            "ttrl": "COPIA VERBATIM del control, salvo UN moving part en "
                "bloques CON probe: (1) candidatos = top-2 brazos por media "
                "del bandit post-probe (desempate: menor índice); "
                "(2) consenso round-robin c1,c2,c1 en los items 3,4,5 "
                "(reemplaza al Thompson del control; cada jugada observa "
                "solo el brazo jugado; sorteos pareados); (3) voto: ganador "
                "= media estrictamente mayor, empate -> sin ganador; "
                "(4) commit: greedy del ganador en los Thompson restantes "
                "(gate: 6,7,8,9; sin gate: 8,9; el re-probe Q2 6,7 sin gate "
                "es idéntico al control); sin ganador -> Thompson idéntico "
                "al control. probe_obs, Q1, Q2, gate y skip idénticos al "
                "control por construcción.",
        },
        "rng": "namespaces del oráculo idénticos a EXP45-53 "
               "('exp45-r{rep}-b{b}-q{q}-{a}'). Fallback a Thompson usa el "
               "namespace '-sel' por (b,q) igual que el control. Pareado "
               "por réplica.",
        "criterio": {
            "efecto": "regret(ttrl) - regret(control-EXP51) sobre 24 "
                      "bloques, media sobre réplicas (pareadas, RNG común)",
            "pasa_1": "media(efecto) < 0  [misma vara de refutación]",
            "pass": "pasa_1",
            "diagnostico_auxiliar": "tasa de commit (bloques con ganador / "
                "bloques con probe); accuracy del ganador del consenso vs "
                "mejor brazo ex-post en items de commit; efecto sin la "
                "mejor réplica; distancia de ambas políticas a la mejor "
                "fija; reproducibilidad bit-idéntica del control vs "
                "tratamiento de EXP51 (columna reg_trat_bloques).",
        },
        "replicas": args.replicas,
        "modo": "mock, US$0",
    }
    with open(os.path.join(out, "preregistro.json"), "w",
              encoding="utf-8") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito ({H} items, {n_bloques} bloques, "
          f"{args.replicas} réplicas pareadas).")

    efectos, det = [], []
    for r in range(args.replicas):
        ctrl = e51.correr_replica_probe_barato(r, items, tasas)
        trt = correr_replica_ttrl(r, items, tasas)
        ef = trt["reg_pol"] - ctrl["reg_pol"]
        efectos.append(ef)
        det.append({
            "replica": r,
            "efecto": round(ef, 3),
            "reg_control": round(ctrl["reg_pol"], 3),
            "reg_tratamiento": round(trt["reg_pol"], 3),
            "reg_control_bloques": [round(x, 3)
                                    for x in ctrl["reg_pol_bloques"]],
            "reg_trat_bloques": [round(x, 3)
                                 for x in trt["reg_pol_bloques"]],
            "reg_mejor_fija": round(ctrl["reg_mejor_fija"], 3),
            "mejor_fija": ctrl["mejor_fija"],
            "q2_saltados_trat": trt["q2_saltados"],
            "q2_saltados_control": ctrl["q2_saltados"],
            "skips_trat": trt["probes_saltados"],
            "skips_control": ctrl["probes_saltados"],
            "ttrl_consenso_bloques": trt["ttrl_consenso_bloques"],
            "ttrl_commits": trt["ttrl_commits"],
            "ttrl_fallbacks": trt["ttrl_fallbacks"],
            "ttrl_ganador_aciertos_expost":
                trt["ttrl_ganador_aciertos_expost"],
        })
        if r == 0:
            diag_rep0 = {"control": ctrl["diag"],
                         "tratamiento": trt["diag"]}

    n = len(efectos)
    media_ef = sum(efectos) / n
    mejor = min(efectos)
    media_sin_mejor = (sum(efectos) - mejor) / (n - 1) if n > 1 else media_ef
    cargado_una_replica = bool(media_sin_mejor >= 0) if n > 1 else False

    reg_trat_medio = sum(d["reg_tratamiento"] for d in det) / n
    reg_ctrl_medio = sum(d["reg_control"] for d in det) / n
    reg_fija_medio = sum(d["reg_mejor_fija"] for d in det) / n
    d_trat = reg_trat_medio - reg_fija_medio
    d_ctrl = reg_ctrl_medio - reg_fija_medio

    tot_consenso = sum(d["ttrl_consenso_bloques"] for d in det)
    tot_commits = sum(d["ttrl_commits"] for d in det)
    tot_aciertos = sum(d["ttrl_ganador_aciertos_expost"] for d in det)
    tasa_commit = tot_commits / tot_consenso if tot_consenso else 0.0
    acc_ganador = tot_aciertos / tot_commits if tot_commits else 0.0

    pasa_1 = bool(media_ef < 0)
    pasa = pasa_1

    # --- chequeo de reproducibilidad: el control debe ser bit-idéntico al
    # TRATAMIENTO de EXP51 (política probe-barato), columna reg_trat_bloques
    # (lección de EXP53: no comparar contra reg_control_bloques) ---
    repro_ok = None
    try:
        rep51 = json.load(open(EXP51_REPORT, encoding="utf-8"))
        d51 = {d["replica"]: (d["reg_trat_bloques"], d["q2_saltados_trat"])
               for d in rep51["detalle_replicas"]}
        repro_ok = all(
            [round(x, 3) for x in det[r]["reg_control_bloques"]] ==
            [round(x, 3) for x in d51[r][0]] and
            det[r]["q2_saltados_control"] == d51[r][1]
            for r in range(args.replicas))
    except Exception as e:  # noqa: BLE001
        repro_ok = f"no verificable: {e}"

    motivos = [
        f"items={H}, bloques={n_bloques} (3 regímenes x 8 recurrencias), "
        f"réplicas pareadas={args.replicas} (RNG común, oráculo idéntico)",
        f"efecto medio (reg_trat - reg_ctrl) = {media_ef:+.3f} "
        f"(por réplica: {', '.join(f'{e:+.2f}' for e in efectos)})",
        f"TTRL: consenso en {tot_consenso} bloques con probe; commits "
        f"{tot_commits} (tasa {tasa_commit:.1%}), fallbacks a Thompson "
        f"{tot_consenso - tot_commits}",
        f"ganador del consenso = mejor ex-post en items de commit: "
        f"{tot_aciertos}/{tot_commits} ({acc_ganador:.1%})",
        f"regret medio control: {reg_ctrl_medio:.2f} | tratamiento: "
        f"{reg_trat_medio:.2f} | mejor fija: {reg_fija_medio:.2f}",
        f"distancia a la mejor fija — control: {d_ctrl:.2f} | tratamiento: "
        f"{d_trat:.2f}",
        f"media del efecto sin la mejor réplica: {media_sin_mejor:+.2f} "
        f"(¿cargado por una sola réplica? {'SÍ' if cargado_una_replica else 'NO'})",
        f"(1) media(efecto) < 0: {'SÍ → PASS' if pasa_1 else 'NO → FAIL'}",
        f"reproducibilidad del control vs tratamiento de EXP51 "
        f"(bit-idéntico): {repro_ok}",
    ]
    report = {
        "preregistro": "preregistro.json (mismo directorio)",
        "n_items": H, "n_bloques": n_bloques,
        "detalle_replicas": det,
        "efecto_medio": round(media_ef, 3),
        "efecto_por_replica": [round(e, 3) for e in efectos],
        "media_efecto_sin_mejor_replica": round(media_sin_mejor, 3),
        "cargado_por_una_sola_replica": cargado_una_replica,
        "reg_tratamiento_medio": round(reg_trat_medio, 3),
        "reg_control_medio": round(reg_ctrl_medio, 3),
        "reg_mejor_fija_medio": round(reg_fija_medio, 3),
        "distancia_trat_a_mejor_fija": round(d_trat, 3),
        "distancia_ctrl_a_mejor_fija": round(d_ctrl, 3),
        "ttrl_tasa_commit": round(tasa_commit, 4),
        "ttrl_acc_ganador_expost": round(acc_ganador, 4),
        "diagnostico_bloques_rep0": diag_rep0,
        "reproducibilidad_exp51": repro_ok,
        "costo_total_usd": 0.0,
        "veredicto": {
            "pasa_1_efecto": pasa_1, "pass": pasa,
            "criterio": prereg["criterio"], "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP54 ================")
    for m in motivos:
        print("  " + m)
    print("  costo: $0.0000 USD (mock) | "
          f"{report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL",
          f"(efecto medio {media_ef:+.3f})")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
