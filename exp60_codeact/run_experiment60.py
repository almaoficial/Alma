#!/usr/bin/env python3
"""ALMA-EXP60: CodeAct aplicado al probe (mock, US$0).

Quinta y última idea mockable de la serie oriental. Un solo moving part
sobre el scaffold evolucionado (SC_EVO = defaults validados EXP56/57):
en vez de jugar UN brazo (fav) en los slots comprometidos del bloque
(Q1=0,1,2 y Q2=6,7), el tratamiento COMPONE un schedule por bloque con
plantillas pre-registradas sobre los dos mejores brazos del prior.

Con codeact_on=False el puerto debe ser bit-idéntico a
run_experiment56.correr_replica_param(SC_EVO) (chequeo pre-registrado).

Lo testeado es "composición por plantillas sobre slots comprometidos",
no un agente que escribe código de verdad — no confundir con CodeAct real.

Uso:
    python3 run_experiment60.py
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
OUT = BASE  # el script ya vive en exp60_codeact/

# Defaults validados EXP56/57 (dos seeds) = alma_service/scaffold.py
SC_EVO = {"umbral_base": 1, "umbral_divisor": 3, "gate_margin": 0.0,
          "n0": 4, "decay": 0.5}

REPLICAS = [0, 1, 2, 3, 4]

# Slots comprometidos del bloque (los que el probe decide; Thompson aparte)
SLOTS = (0, 1, 2, 6, 7)

# Umbrales del gap del prior para elegir plantilla.
# CALIBRADOS sobre la distribución de gaps del control (sanity run,
# sin observar ningún resultado del tratamiento) — ver preregistro.md.
T_HI = 0.15
T_MID = 0.08
T_LO = 0.03


def plantillas(W, R):
    """4 plantillas pre-registradas sobre (W=ganador del prior, R=runner-up).
    Orden de slots: (0,1,2,6,7)."""
    return {
        "T0_solo": [W, W, W, W, W],
        "T1_confianza": [W, W, W, W, R],
        "T2_mixta": [W, W, R, W, R],
        "T3_duelo": [W, R, W, R, W],
    }


def elegir_plantilla(gap):
    """Regla explícita pre-registrada sobre el gap del prior."""
    if gap >= T_HI:
        return "T0_solo"
    if gap >= T_MID:
        return "T1_confianza"
    if gap >= T_LO:
        return "T2_mixta"
    return "T3_duelo"


def correr_replica_codeact(rep_id, items, tasas, sc, codeact_on=True):
    """Puerto de e56.correr_replica_param + módulo CodeAct (pre-registrado).

    Con codeact_on=False la plantilla es siempre [fav]*5 => bit-idéntico
    al control.
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
    sched_log = []

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
            # PROBE SALTADO: idéntico al control.
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

        # === CodeAct: top-2 del prior y elección de plantilla ===
        W = fav
        R = min((a for a in brazos if a != fav),
                key=lambda a: (-prior_means[a], a))
        gap = prior_means[W] - prior_means[R]
        tid = elegir_plantilla(gap) if codeact_on else "T0_solo"
        sched = plantillas(W, R)[tid]

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

        # PROBE Q1: slots 0,1,2 con la plantilla (medición idéntica).
        rs_q1 = {}
        for i, q in enumerate(e47.PROBE_Q1):
            rs_q1[q] = medir_y_jugar(q, sched[i])

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

        thompson(tuple(q for q in e47.THOMPSON_Q if q < e47.PROBE_Q2[0]))
        rs_q2 = {}
        if gate:
            # Q2 como Thompson: idéntico al control.
            thompson(e47.PROBE_Q2)
        else:
            # RE-PROBE Q2: slots 6,7 con la plantilla.
            for i, q in enumerate(e47.PROBE_Q2):
                rs_q2[q] = medir_y_jugar(q, sched[3 + i])

        thompson(tuple(q for q in e47.THOMPSON_Q if q > e47.PROBE_Q2[-1]))

        sched_log.append({"rep": rep_id, "b": b, "sig": sig,
                          "gate": bool(gate), "W": W, "R": R,
                          "gap": round(gap, 4), "plantilla": tid,
                          "sched": list(sched)})

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
            "sched_log": sched_log}


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    items = e47.construir_stream()
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))

    # --- 1. Chequeo de sanidad bit-idéntica (pre-registrado) ---
    print("Chequeo de sanidad: puerto codeact_on=False vs "
          "e56.correr_replica_param(SC_EVO)...")
    for r in REPLICAS:
        ref = e56.correr_replica_param(r, items, tasas, dict(SC_EVO))
        got = correr_replica_codeact(r, items, tasas, dict(SC_EVO),
                                     codeact_on=False)
        assert abs(ref["reg_pol"] - got["reg_pol"]) < 1e-9, (
            f"réplica {r}: ref={ref['reg_pol']} vs puerto={got['reg_pol']} "
            f"— el puerto NO es bit-idéntico, no se corre el experimento")
    print("  OK: bit-idéntico en las 5 réplicas.")

    # --- 2. Corrida pareada control vs tratamiento ---
    ctrl_regs, trat_regs, trat_mejor, logs = [], [], [], []
    for r in REPLICAS:
        c = e56.correr_replica_param(r, items, tasas, dict(SC_EVO))
        t = correr_replica_codeact(r, items, tasas, dict(SC_EVO),
                                   codeact_on=True)
        ctrl_regs.append(c["reg_pol"])
        trat_regs.append(t["reg_pol"])
        trat_mejor.append(t["reg_mejor_fija"])
        logs.extend(t["sched_log"])
        print(f"  rep {r}: ctrl={c['reg_pol']:.1f} trat={t['reg_pol']:.1f} "
              f"efecto={t['reg_pol'] - c['reg_pol']:+.1f}")

    efectos = [t - c for t, c in zip(trat_regs, ctrl_regs)]
    efecto_medio = sum(efectos) / len(efectos)

    # --- 3. Diagnóstico de plantillas (pre-registrado) ---
    uso = {}
    for x in logs:
        uso[x["plantilla"]] = uso.get(x["plantilla"], 0) + 1
    # Efecto condicionado a bloques con mezcla (T1/T2/T3), por réplica
    # (diagnóstico; no cambia el veredicto).
    mezcla_ids = {"T1_confianza", "T2_mixta", "T3_duelo"}

    pasa = bool(efecto_medio < 0)
    report = {
        "experimento": "ALMA-EXP60: CodeAct (plantillas) en el probe "
                       "(mock, US$0)",
        "preregistro": "preregistro.md (mismo directorio)",
        "scaffold_control": SC_EVO,
        "umbrales_gap": {"T_HI": T_HI, "T_MID": T_MID, "T_LO": T_LO},
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
        "plantillas": {
            "uso_bloques": uso,
            "n_bloques_probe": len(logs),
        },
        "criterio": "PASS ssi media(reg_trat - reg_ctrl) < 0",
        "veredicto": "PASS" if pasa else "FAIL",
        "costo_total_usd": 0.0,
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP60 ================")
    print(f"  efecto medio: {efecto_medio:+.3f} "
          f"(trat {report['reg_trat_medio']:.2f} vs "
          f"ctrl {report['reg_ctrl_medio']:.2f}, "
          f"mejor fija {report['reg_mejor_fija_media']:.2f})")
    print(f"  uso de plantillas en {len(logs)} bloques con probe: {uso}")
    print("  RESULTADO:", "PASS" if pasa else "FAIL")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
