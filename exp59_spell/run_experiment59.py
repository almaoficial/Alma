#!/usr/bin/env python3
"""ALMA-EXP59: SPELL multi-rol aplicado al probe (mock, US$0).

Cuarta idea oriental de la serie. Un solo moving part sobre el scaffold
evolucionado (SC_EVO = defaults validados EXP56/57): el probe gana tres
roles estilo SPELL — questioner (Q1 propone ganador), challenger (el
runner-up recibe 1 item focalizado de verificación, q=3) y verifier
(decide entre ganador-Q1 y challenger con la evidencia combinada).
La única consecuencia de juego: en el camino sin gate, Q2 se juega con el
brazo elegido por el verifier en vez de `fav`.

Con spell_on=False el puerto debe ser bit-idéntico a
run_experiment56.correr_replica_param(SC_EVO) (chequeo pre-registrado).

Uso:
    python3 run_experiment59.py
"""

import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
AP = os.path.dirname(HERE)  # alma-prototype/
sys.path.insert(0, AP)
sys.path.insert(0, os.path.join(AP, "exp56_rso"))
import run_experiment47 as e47  # noqa: E402
import run_experiment56 as e56  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = BASE  # el script ya vive en exp59_spell/

# Defaults validados EXP56/57 (dos seeds) = alma_service/scaffold.py
SC_EVO = {"umbral_base": 1, "umbral_divisor": 3, "gate_margin": 0.0,
          "n0": 4, "decay": 0.5}

REPLICAS = [0, 1, 2, 3, 4]


def correr_replica_spell(rep_id, items, tasas, sc, spell_on=True):
    """Puerto de e56.correr_replica_param + módulo SPELL (pre-registrado).

    Con spell_on=False es verbatim (salvo el helper medir_y_jugar, que
    replica exactamente la secuencia de operaciones de medir + jugada).
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
    verif_log = []

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

        # --- Camino con probe ---
        bandit = e56.nuevo_bandit_param(
            brazos, e56.prior_params_param(brazos, rep_hist, block_sig, b,
                                           None, n0, decay), n0)
        prior_means = {a: bandit.mean(a) for a in brazos}
        fav = max(brazos, key=lambda a: prior_means[a])

        def medir_y_jugar(q, brazo_jugado):
            """Mide todos los brazos (scoring honesto) y juega brazo_jugado.
            Con brazo_jugado=fav replica verbatim a e56.medir + jugada."""
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
            rew_pol[h] = rs[brazo_jugado]
            return rs

        # PROBE Q1: idéntico al control (se juega fav).
        rs_q1 = {}
        for q in e47.PROBE_Q1:
            rs_q1[q] = medir_y_jugar(q, fav)

        # === SPELL rol 1: QUESTIONER (Q1 propone) ===
        mean_q1 = {a: sum(rs_q1[q][a] for q in e47.PROBE_Q1)
                   / len(e47.PROBE_Q1) for a in brazos}
        orden = sorted(brazos,
                       key=lambda a: (-mean_q1[a], -prior_means[a], a))
        winner_q1, runner_up = orden[0], orden[1]

        usa_skill = False
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            usa_skill = True
            bandit = e56.nuevo_bandit_param(
                brazos, e56.prior_params_param(brazos, rep_hist, block_sig,
                                               b, sig, n0, decay), n0)
            for q in e47.PROBE_Q1:
                for a in brazos:
                    bandit.update(a, rs_q1[q][a])

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
                bandit.update(a_sel, r_sel)
                rep_hist[a_sel].append((h, r_sel, b))
                rew_pol[h] = r_sel
                for a in brazos:
                    rew_fija[a][h] = clf.acierto(
                        a, it, random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                clf.registrar(it)

        qs_pre = tuple(q for q in e47.THOMPSON_Q if q < e47.PROBE_Q2[0])
        elegido_q2 = fav
        rec = None
        if spell_on and qs_pre:
            # === SPELL rol 2: CHALLENGER (re-pregunta focalizada en q=3) ===
            q_ch = qs_pre[0]
            rs_ch = medir_y_jugar(q_ch, runner_up)
            # === SPELL rol 3: VERIFIER (evidencia combinada) ===
            r3_w = rs_ch[winner_q1]
            r3_c = rs_ch[runner_up]
            q1_wins_w = sum(1 for q in e47.PROBE_Q1
                            if rs_q1[q][winner_q1] > rs_q1[q][runner_up])
            cambia = bool((r3_c > r3_w) and (q1_wins_w <= 1))
            elegido_q2 = runner_up if cambia else winner_q1
            rec = {"rep": rep_id, "b": b, "sig": sig, "gate": bool(gate),
                   "winner_q1": winner_q1, "runner_up": runner_up,
                   "r3_w": r3_w, "r3_c": r3_c, "q1_wins_w": q1_wins_w,
                   "cambia": cambia, "q2_w": None, "q2_c": None}
            thompson(qs_pre[1:])
        else:
            thompson(qs_pre)

        rs_q2 = {}
        if gate:
            thompson(e47.PROBE_Q2)
        else:
            for q in e47.PROBE_Q2:
                rs_q2[q] = medir_y_jugar(q, elegido_q2)
            if rec is not None:
                rec["q2_w"] = sum(rs_q2[q][winner_q1]
                                  for q in e47.PROBE_Q2)
                rec["q2_c"] = sum(rs_q2[q][runner_up]
                                  for q in e47.PROBE_Q2)
        if rec is not None:
            verif_log.append(rec)

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
            "reg_mejor_fija": reg_fijas[mejor], "n": H,
            "verif_log": verif_log}


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    items = e47.construir_stream()
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))

    # --- 1. Chequeo de sanidad bit-idéntica (pre-registrado) ---
    print("Chequeo de sanidad: puerto spell_on=False vs "
          "e56.correr_replica_param(SC_EVO)...")
    for r in REPLICAS:
        ref = e56.correr_replica_param(r, items, tasas, dict(SC_EVO))
        got = correr_replica_spell(r, items, tasas, dict(SC_EVO),
                                   spell_on=False)
        assert abs(ref["reg_pol"] - got["reg_pol"]) < 1e-9, (
            f"réplica {r}: ref={ref['reg_pol']} vs puerto={got['reg_pol']} "
            f"— el puerto NO es bit-idéntico, no se corre el experimento")
        assert got["verif_log"] == [], "spell_on=False no debe loguear"
    print("  OK: bit-idéntico en las 5 réplicas.")

    # --- 2. Corrida pareada control vs tratamiento ---
    ctrl_regs, trat_regs, trat_mejor, logs = [], [], [], []
    for r in REPLICAS:
        c = e56.correr_replica_param(r, items, tasas, dict(SC_EVO))
        t = correr_replica_spell(r, items, tasas, dict(SC_EVO),
                                 spell_on=True)
        ctrl_regs.append(c["reg_pol"])
        trat_regs.append(t["reg_pol"])
        trat_mejor.append(t["reg_mejor_fija"])
        logs.extend(t["verif_log"])
        print(f"  rep {r}: ctrl={c['reg_pol']:.1f} trat={t['reg_pol']:.1f} "
              f"efecto={t['reg_pol'] - c['reg_pol']:+.1f} "
              f"cambios_verif={sum(1 for x in t['verif_log'] if x['cambia'])}"
              f"/{len(t['verif_log'])}")

    efectos = [t - c for t, c in zip(trat_regs, ctrl_regs)]
    efecto_medio = sum(efectos) / len(efectos)

    # --- 3. Diagnóstico del verifier (pre-registrado) ---
    n_probe = len(logs)
    cambios = [x for x in logs if x["cambia"]]
    nogate = [x for x in logs if not x["gate"]]
    cambios_nogate = [x for x in cambios if not x["gate"]]
    aciertos = sum(1 for x in cambios_nogate if x["q2_c"] > x["q2_w"])
    empates = sum(1 for x in cambios_nogate if x["q2_c"] == x["q2_w"])
    q1_ok = sum(1 for x in nogate if x["q2_w"] > x["q2_c"])
    q1_mal = sum(1 for x in nogate if x["q2_c"] > x["q2_w"])
    q1_emp = sum(1 for x in nogate if x["q2_c"] == x["q2_w"])

    pasa = bool(efecto_medio < 0)
    report = {
        "experimento": "ALMA-EXP59: SPELL multi-rol en el probe (mock, US$0)",
        "preregistro": "preregistro.md (mismo directorio)",
        "scaffold_control": SC_EVO,
        "sanidad_bit_identica": True,
        "replicas": REPLICAS,
        "por_replica": [
            {"rep": r, "reg_ctrl": round(c, 3), "reg_trat": round(t, 3),
             "efecto": round(t - c, 3),
             "reg_mejor_fija": round(m, 3)}
            for r, c, t, m in zip(REPLICAS, ctrl_regs, trat_regs,
                                  trat_mejor)],
        "efecto_medio": round(efecto_medio, 4),
        "reg_ctrl_medio": round(sum(ctrl_regs) / len(ctrl_regs), 4),
        "reg_trat_medio": round(sum(trat_regs) / len(trat_regs), 4),
        "reg_mejor_fija_media": round(sum(trat_mejor) / len(trat_mejor), 4),
        "verifier": {
            "bloques_con_probe": n_probe,
            "tasa_cambio": round(len(cambios) / n_probe, 4) if n_probe else 0,
            "cambios": len(cambios),
            "cambios_nogate": len(cambios_nogate),
            "acierto_verifier": (round(aciertos / len(cambios_nogate), 4)
                                 if cambios_nogate else None),
            "aciertos": aciertos, "empates": empates,
            "n_cambios_nogate": len(cambios_nogate),
            "baseline_q1": {
                "nogate": len(nogate),
                "q1_mejor_en_q2": q1_ok, "q1_peor_en_q2": q1_mal,
                "empates": q1_emp,
            },
        },
        "criterio": "PASS ssi media(reg_trat - reg_ctrl) < 0",
        "veredicto": "PASS" if pasa else "FAIL",
        "costo_total_usd": 0.0,
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP59 ================")
    print(f"  efecto medio: {efecto_medio:+.3f} "
          f"(trat {report['reg_trat_medio']:.2f} vs "
          f"ctrl {report['reg_ctrl_medio']:.2f}, "
          f"mejor fija {report['reg_mejor_fija_media']:.2f})")
    v = report["verifier"]
    print(f"  verifier: {v['cambios']}/{v['bloques_con_probe']} cambios "
          f"(tasa {v['tasa_cambio']:.1%}); acierto en no-gate: "
          f"{v['aciertos']}/{v['n_cambios_nogate']} "
          f"({v['acierto_verifier']})")
    print(f"  baseline Q1 en Q2 (no-gate): mejor {q1_ok}, peor {q1_mal}, "
          f"empates {q1_emp} de {len(nogate)}")
    print("  RESULTADO:", "PASS" if pasa else "FAIL")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
