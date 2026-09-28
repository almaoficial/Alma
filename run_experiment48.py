#!/usr/bin/env python3
"""ALMA-EXP48: anti-misfire — re-validación barata del brazo de la skill antes de saltar el probe (mock, US$0).

Ataca el problema que dejó EXP47: los misfires del skip escalaron a ~37%
(14/38). El umbral fijo de soporte (>=2 victorias) se alcanza con victorias
ruidosas y el brazo de la skill se vuelve stale.

VARIANTE ELEGIDA: (a) re-validación barata. Descartada (b) umbral endurecido:
endurecer el umbral ataca las victorias ruidosas pero no la staleness (el
brazo deja de matchear el bloque actual); la re-validación mide evidencia
fresca del bloque en curso, el antídoto directo contra un brazo stale.
Un solo moving part respecto al tratamiento "skip" de EXP47: el gate de
confirmación.

- Control: el tratamiento "skip" de EXP47 VERBATIM (misma función, importada
  de run_experiment47), mismo stream de 24 bloques bit-idéntico, réplicas
  pareadas con RNG común.
- Tratamiento ("skip-confirm"): idéntico al control, salvo que antes de
  saltar se gasta 1 item (q=0) en re-validación: se miden los 4 brazos, la
  política juega el brazo de la skill (costo honesto = 1 item). Se confirma
  ssi reward(skill_arm) == 1.0 en el item de confirmación. Si confirma: skip
  en items 1-9 (sin probe). Si no confirma: camino de probe completo en
  items 1-9 (Q1'=(1,2,3), Q2=(6,7), Thompson en el resto), con la observación
  del item 0 ya incorporada a la historia de todos los brazos.

Criterio PRE-REGISTRADO (dos partes):
  (1) tasa de misfires del tratamiento < 14/38 (~0.368, la de EXP47)
  (2) media sobre réplicas pareadas de regret(skip-confirm)-regret(skip) < 0
PASS ssi (1) y (2). Definición operativa de misfire idéntica a EXP47.

Uso:
    python3 run_experiment48.py [--out DIR] [--replicas N]
"""

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_experiment47 as e47  # noqa: E402  (control verbatim + maquinaria)

BASE = os.path.dirname(os.path.abspath(__file__))
EXP47_REPORT = os.path.join(BASE, "resultados", "exp47-20260927",
                            "report.json")

Q1_FALLBACK = (1, 2, 3)  # Q1 cuando el item 0 se usó para confirmar
MISFIRES_EXP47 = 14
SKIPS_EXP47 = 38
TASA_MISFIRE_EXP47 = MISFIRES_EXP47 / SKIPS_EXP47  # ~0.368


def correr_replica_confirm(rep_id, items, tasas):
    """Tratamiento skip-confirm de EXP48.

    Reutiliza toda la maquinaria de EXP47 (helpers importados). El único
    moving part: el gate de confirmación antes de saltar.
    """
    brazos = tasas["brazos"]
    H = len(items)
    n_bloques = H // e47.BLOQUE
    rep_hist = {a: [] for a in brazos}  # (h, reward, bloque)
    block_sig = {}
    probe_obs = {}  # b -> {brazo: [rewards en 5 items de probe]} | None
    rew_pol = [0.0] * H
    rew_fija = {a: [0.0] * H for a in brazos}
    reg_pol_bloques = []
    diag = []
    skills_usadas = 0
    probes_saltados = 0
    confirm_intentos = 0
    confirm_ok = 0
    confirm_no = 0
    saltados_det = []

    for b in range(n_bloques):
        base = b * e47.BLOQUE
        sig = e47.firma_grupo([items[base + q]["grupo"]
                               for q in e47.PROBE_Q1])
        block_sig[b] = sig

        saltar = False
        skill_arm = None
        wins = 0
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            skill_arm = e47.skill_arm_actual(brazos, rep_hist, block_sig,
                                             b, sig)
            fuerte, wins = e47.soporte_fuerte(brazos, probe_obs, block_sig,
                                              b, sig, skill_arm)
            saltar = fuerte

        clf = e47.MockClasificador(tasas)
        for hh in range(base):
            clf.registrar(items[hh])

        def camino_probe(q1_items, pre_rs):
            """Camino con probe. pre_rs: {q: {a: r}} ya medidos (full-info)
            e incorporados a rep_hist; se aplican al bandit recién construido.
            Con q1_items=PROBE_Q1 y pre_rs={} es idéntico al camino con probe
            de EXP47 (mismo orden de sorteos, mismos seeds)."""
            nonlocal skills_usadas
            bandit = e47.nuevo_bandit(
                brazos,
                e47.prior_params(brazos, rep_hist, block_sig, b, None))
            for q, rs in pre_rs.items():
                for a in brazos:
                    bandit.update(a, rs[a])
            # fav ciego: se calcula tras aplicar pre_rs (decisión documentada)
            prior_means = {a: bandit.mean(a) for a in brazos}
            fav = max(brazos, key=lambda a: prior_means[a])

            def medir(q):
                h = base + q
                it = items[h]
                rs = {a: clf.acierto(
                    a, it,
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                    for a in brazos}
                for a in brazos:
                    bandit.update(a, rs[a])
                    rep_hist[a].append((h, rs[a], b))
                    rew_fija[a][h] = rs[a]
                clf.registrar(it)
                return rs

            rs_q1 = {}
            for q in q1_items:
                rs_q1[q] = medir(q)
                rew_pol[base + q] = rs_q1[q][fav]

            usa_skill = False
            if e47.skill_existe(rep_hist, block_sig, b, sig):
                usa_skill = True
                skills_usadas += 1
                bandit = e47.nuevo_bandit(
                    brazos,
                    e47.prior_params(brazos, rep_hist, block_sig, b, sig))
                for q, rs in pre_rs.items():
                    for a in brazos:
                        bandit.update(a, rs[a])
                for q in q1_items:
                    for a in brazos:
                        bandit.update(a, rs_q1[q][a])

            def thompson(qs):
                for q in qs:
                    h = base + q
                    it = items[h]
                    a_sel = bandit.select(
                        random.Random(f"exp45-r{rep_id}-b{b}-q{q}-sel"))
                    r_sel = clf.acierto(
                        a_sel, it,
                        random.Random(
                            f"exp45-r{rep_id}-b{b}-q{q}-{a_sel}"))
                    bandit.update(a_sel, r_sel)
                    rep_hist[a_sel].append((h, r_sel, b))
                    rew_pol[h] = r_sel
                    for a in brazos:
                        rew_fija[a][h] = clf.acierto(
                            a, it,
                            random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                    clf.registrar(it)

            q2 = e47.PROBE_Q2
            pre_qs = tuple(q for q in range(e47.BLOQUE)
                           if q not in pre_rs and q not in q1_items
                           and q < q2[0])
            post_qs = tuple(q for q in range(e47.BLOQUE)
                            if q not in pre_rs and q not in q1_items
                            and q > q2[-1])
            thompson(pre_qs)
            rs_q2 = {}
            for q in q2:
                rs_q2[q] = medir(q)
                rew_pol[base + q] = rs_q2[q][fav]
            thompson(post_qs)

            # Victorias para soporte: 5 items de probe canónicos (idéntico
            # cómputo que EXP47; en fallback son los items 1,2,3,6,7).
            probe_obs[b] = {a: [rs_q1[q][a] for q in q1_items] +
                               [rs_q2[q][a] for q in q2]
                            for a in brazos}
            reg_pol_bloques.append(
                e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))
            diag.append({
                "bloque": b, "regimen": items[base]["regimen"],
                "firma": sig, "probe_saltado": False,
                "soporte_wins": wins,
                "confirmacion_rechazada": bool(pre_rs),
                "skill_usada": usa_skill,
                "acc_pol": round(
                    sum(rew_pol[base:base + e47.BLOQUE]) / e47.BLOQUE, 4),
                "acc_fijas": {
                    a: round(sum(rew_fija[a][base:base + e47.BLOQUE]) /
                             e47.BLOQUE, 4)
                    for a in brazos},
            })

        def ejecutar_skip(qs, via_confirmacion):
            """Juega skill_arm en los items qs. Diagnóstico ex post idéntico
            a EXP47 (misfire = brazo_skill != mejor ex post)."""
            nonlocal probes_saltados
            for q in qs:
                h = base + q
                it = items[h]
                rs = {a: clf.acierto(
                    a, it,
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                    for a in brazos}
                for a in brazos:
                    rew_fija[a][h] = rs[a]
                r = rs[skill_arm]
                rep_hist[skill_arm].append((h, r, b))
                rew_pol[h] = r
                clf.registrar(it)
            probes_saltados += 1
            probe_obs[b] = None
            acc = {a: sum(rew_fija[a][base:base + e47.BLOQUE]) / e47.BLOQUE
                   for a in brazos}
            mejor = max(brazos, key=lambda a: acc[a])
            saltados_det.append({
                "bloque": b, "firma": sig, "brazo_skill": skill_arm,
                "soporte_wins": wins,
                "confirmacion": via_confirmacion,
                "acc_skill": round(acc[skill_arm], 4),
                "mejor_expost": mejor, "acc_mejor": round(acc[mejor], 4),
                "misfire": bool(mejor != skill_arm),
            })
            reg_pol_bloques.append(
                e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))
            diag.append({
                "bloque": b, "regimen": items[base]["regimen"],
                "firma": sig, "probe_saltado": True,
                "soporte_wins": wins,
                "confirmacion": via_confirmacion,
                "brazo_skill": skill_arm,
                "acc_pol": round(
                    sum(rew_pol[base:base + e47.BLOQUE]) / e47.BLOQUE, 4),
                "acc_fijas": {
                    a: round(sum(rew_fija[a][base:base + e47.BLOQUE]) /
                             e47.BLOQUE, 4)
                    for a in brazos},
            })

        if saltar:
            # --- RE-VALIDACIÓN BARATA (EXP48, único moving part) ---
            h0 = base
            it0 = items[h0]
            rs0 = {a: clf.acierto(
                a, it0, random.Random(f"exp45-r{rep_id}-b{b}-q0-{a}"))
                for a in brazos}
            for a in brazos:
                rep_hist[a].append((h0, rs0[a], b))
                rew_fija[a][h0] = rs0[a]
            clf.registrar(it0)
            # La política juega el brazo de la skill: costo honesto = 1 item.
            rew_pol[h0] = rs0[skill_arm]
            confirm_intentos += 1
            if rs0[skill_arm] == 1.0:
                # Confirma: skip en los items 1-9, sin probe.
                confirm_ok += 1
                ejecutar_skip(range(1, e47.BLOQUE), via_confirmacion=True)
            else:
                # No confirma: probe completo en items 1-9.
                confirm_no += 1
                camino_probe(Q1_FALLBACK, {0: rs0})
            continue

        # Camino con probe estándar: idéntico al de EXP47.
        camino_probe(e47.PROBE_Q1, {})

    reg_pol = H - sum(rew_pol)
    reg_fijas = {a: H - sum(rew_fija[a]) for a in brazos}
    mejor = min(brazos, key=lambda a: reg_fijas[a])
    return {"politica": "skip-confirm", "reg_pol": reg_pol,
            "reg_pol_bloques": reg_pol_bloques,
            "reg_fijas": reg_fijas,
            "mejor_fija": mejor, "reg_mejor_fija": reg_fijas[mejor],
            "skills_usadas": skills_usadas,
            "probes_saltados": probes_saltados,
            "confirm_intentos": confirm_intentos,
            "confirm_ok": confirm_ok, "confirm_no": confirm_no,
            "saltados_det": saltados_det, "n_bloques": n_bloques,
            "diag": diag, "n": H}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--replicas", type=int, default=e47.N_REPLICAS)
    args = ap.parse_args()
    t0 = time.time()

    out = args.out or os.path.join(BASE, "resultados", "exp48-20260927")
    os.makedirs(out, exist_ok=True)

    items = e47.construir_stream()  # bit-idéntico al stream de EXP47
    H = len(items)
    n_bloques = H // e47.BLOQUE
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))

    # --- pre-registro ANTES de correr ---
    prereg = {
        "experimento": "ALMA-EXP48: anti-misfire — re-validación barata del "
                       "brazo de la skill antes de saltar el probe (mock)",
        "fase": "mock",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "hipotesis": "(1) La re-validación barata (1 item) baja la tasa de "
                     "misfires del skip respecto al ~37% (14/38) de EXP47, "
                     "porque filtra skills cuyo brazo se volvió stale antes "
                     "de comprometer 10 items. (2) El tratamiento reduce el "
                     "regret frente al skip sin confirmación: media sobre "
                     "réplicas pareadas de regret(skip-confirm) - "
                     "regret(skip) < 0.",
        "variante_elegida": "(a) re-validación barata. Descartada (b) umbral "
                            "endurecido con el horizonte: endurecer el umbral "
                            "ataca las victorias ruidosas pero no la "
                            "staleness (el brazo deja de matchear el bloque "
                            "actual); la re-validación mide evidencia fresca "
                            "del bloque en curso, el antídoto directo contra "
                            "un brazo stale. Un solo moving part: el gate de "
                            "confirmación en el tratamiento.",
        "nota_refutacion": "Si la confirmación no baja los misfires o no "
                           "reduce el regret, el gate barato no alcanza: el "
                           "problema está en la calidad de la evidencia "
                           "acumulada (victorias ruidosas), no solo en la "
                           "staleness. El próximo paso sería entonces la "
                           "variante (b) o cerrar la línea de skills.",
        "condicion_alcance": e47.CONDICION_ALCANCE,
        "stream": {
            "fuente": "IDÉNTICO al de EXP47 (misma función "
                      "run_experiment47.construir_stream, bit-idéntico): 240 "
                      "items, 24 bloques x 10, 3 regímenes x 8 recurrencias, "
                      "seeds 45/47, namespace de RNG del oráculo 'exp45-...'.",
            "n_items": H, "bloques": n_bloques,
            "tam_bloque": e47.BLOQUE,
            "regimenes": e47.REGIMENES,
            "oraculo": "tasas mock calibradas por categoría "
                       "(data_exp44/tasas.json)",
            "sesgo_seleccion": e47.SESGO_SELECCION,
        },
        "politicas": {
            "control": "El tratamiento 'skip' de EXP47 VERBATIM (misma "
                       "función run_experiment47.correr_replica con "
                       "politica='skip', importada): skills condicionan el "
                       "prior; con soporte fuerte (>=2 victorias) se salta "
                       "el probe y se juega el brazo de la skill en los 10 "
                       "items.",
            "skip-confirm": "Idéntica al control, salvo el gate de "
                            "confirmación: antes de saltar se gasta 1 item "
                            "(q=0) en re-validación — se miden los 4 brazos "
                            "(full-information, seeds de oráculo idénticas), "
                            "la política juega el brazo de la skill (costo "
                            "honesto = 1 item). Se confirma ssi "
                            "reward(skill_arm) == 1.0. Si confirma: skip en "
                            "items 1-9 sin probe. Si no confirma: camino de "
                            "probe completo en items 1-9 (Q1'=(1,2,3), "
                            "Q2=(6,7), Thompson en el resto), con la "
                            "observación del item 0 ya incorporada a la "
                            "historia de todos los brazos (no se re-sortea).",
        },
        "mecanismo_skill": {
            "firma": "idéntica a EXP47 (grupo mayoritario de los primeros 3 "
                     "items del bloque)",
            "skill_arm": "idéntico a EXP47 (argmax de la media del prior "
                         "condicionado a la firma, warm olvido 0.5^d)",
            "soporte_fuerte": "idéntico a EXP47 (>=2 victorias pareadas del "
                              "skill_arm en bloques pasados no-saltados con "
                              "la misma firma; victoria = media en los 5 "
                              "items de probe estrictamente mayor que cada "
                              "otro brazo)",
            "victoria_para_soporte_en_fallback": "el cómputo de victorias "
                "usa los 5 items de probe canónicos; en bloques con "
                "confirmación rechazada son los items 1,2,3,6,7 (el item 0 "
                "de confirmación no cuenta como probe para el cómputo de "
                "victorias, pero sí queda en la historia observada)",
            "misfire_definicion": "IDÉNTICA a EXP47: en un bloque saltado "
                "(confirmado), el brazo de la skill no es el mejor ex post "
                "(accuracy sobre los 10 items con RNG común, contrafactual). "
                "Tasa de misfires = misfires / skips confirmados.",
            "bloque_saltado": "idéntico a EXP47 (sin probe Q1/Q2 ni bandit; "
                              "rewards observados agregados a la skill; no "
                              "aporta comparación pareada)",
        },
        "rng": "namespace del oráculo idéntico a EXP45/46/47 "
               "('exp45-r{rep}-b{b}-q{q}-{a}'); el item de confirmación usa "
               "los mismos seeds que el Q1 del control para q=0 (pareado). "
               "Control y tratamiento ven el mismo oráculo. Pareado por "
               "réplica.",
        "criterio": {
            "efecto": "regret(skip-confirm) - regret(skip) sobre 24 "
                      "bloques, media sobre réplicas (pareadas, RNG común)",
            "pasa_1": f"tasa_misfires_tratamiento < {MISFIRES_EXP47}/"
                      f"{SKIPS_EXP47} (~{TASA_MISFIRE_EXP47:.3f}, EXP47), "
                      "con n_skips_tratamiento > 0 "
                      "[comparación contra número fijo de otro experimento, "
                      "documentada como tal]",
            "pasa_2": "media(efecto) < 0  [misma vara que EXP46/47]",
            "pass": "pasa_1 Y pasa_2",
            "diagnostico_auxiliar": "tasa de misfires del control (debe "
                                    "reproducir ~37% de EXP47 — chequeo de "
                                    "sanidad); confirmaciones por réplica "
                                    "(intentos / confirmadas / rechazadas); "
                                    "reproducibilidad bit-idéntica del "
                                    "control vs EXP47",
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
        ctrl = e47.correr_replica(r, items, tasas, "skip")
        trt = correr_replica_confirm(r, items, tasas)
        ef = trt["reg_pol"] - ctrl["reg_pol"]
        efectos.append(ef)
        mis_c = sum(1 for s in ctrl["saltados_det"] if s["misfire"])
        mis_t = sum(1 for s in trt["saltados_det"] if s["misfire"])
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
            "skips_control": ctrl["probes_saltados"],
            "misfires_control": mis_c,
            "tasa_misfire_control": round(
                mis_c / ctrl["probes_saltados"], 4)
            if ctrl["probes_saltados"] else None,
            "skips_tratamiento": trt["probes_saltados"],
            "misfires_tratamiento": mis_t,
            "tasa_misfire_tratamiento": round(
                mis_t / trt["probes_saltados"], 4)
            if trt["probes_saltados"] else None,
            "confirm_intentos": trt["confirm_intentos"],
            "confirm_ok": trt["confirm_ok"],
            "confirm_no": trt["confirm_no"],
        })
        if r == 0:
            diag_rep0 = {"control": ctrl["diag"],
                         "tratamiento": trt["diag"]}
            salt_rep0 = {"control": ctrl["saltados_det"],
                         "tratamiento": trt["saltados_det"]}

    media_ef = sum(efectos) / len(efectos)
    n_skips_t = sum(d["skips_tratamiento"] for d in det)
    n_mis_t = sum(d["misfires_tratamiento"] for d in det)
    tasa_t = n_mis_t / n_skips_t if n_skips_t else None
    n_skips_c = sum(d["skips_control"] for d in det)
    n_mis_c = sum(d["misfires_control"] for d in det)
    tasa_c = n_mis_c / n_skips_c if n_skips_c else None
    pasa_1 = bool(n_skips_t > 0 and tasa_t < TASA_MISFIRE_EXP47)
    pasa_2 = bool(media_ef < 0)
    pasa = pasa_1 and pasa_2

    # --- chequeo de reproducibilidad: el control debe ser bit-idéntico al
    # tratamiento "skip" de EXP47 (misma función, mismo stream) ---
    repro_ok = None
    try:
        rep47 = json.load(open(EXP47_REPORT, encoding="utf-8"))
        d47 = {d["replica"]: d["reg_skip_bloques"]
               for d in rep47["detalle_replicas"]}
        repro_ok = all(
            [round(x, 3) for x in det[r]["reg_control_bloques"]] ==
            [round(x, 3) for x in d47[r]]
            for r in range(args.replicas))
    except Exception as e:  # noqa: BLE001
        repro_ok = f"no verificable: {e}"

    motivos = [
        f"items={H}, bloques={n_bloques} (3 regímenes x 8 recurrencias), "
        f"réplicas pareadas={args.replicas} (RNG común, oráculo idéntico)",
        f"efecto medio (reg_trat - reg_ctrl) = {media_ef:+.3f} "
        f"(por réplica: {', '.join(f'{e:+.2f}' for e in efectos)})",
        f"misfires tratamiento: {n_mis_t}/{n_skips_t} "
        f"(tasa {tasa_t:.3f}) vs EXP47 {MISFIRES_EXP47}/{SKIPS_EXP47} "
        f"(tasa {TASA_MISFIRE_EXP47:.3f})" if tasa_t is not None
        else "tratamiento sin skips: (1) no evaluable",
        f"misfires control (sanidad, debe dar ~37%): {n_mis_c}/{n_skips_c} "
        f"(tasa {tasa_c:.3f})" if tasa_c is not None else "control sin skips",
        f"confirmaciones: intentos "
        f"{sum(d['confirm_intentos'] for d in det)} / ok "
        f"{sum(d['confirm_ok'] for d in det)} / rechazadas "
        f"{sum(d['confirm_no'] for d in det)}",
        f"(1) misfires < 37%: {'SÍ' if pasa_1 else 'NO'} | "
        f"(2) media(efecto) < 0: {'SÍ' if pasa_2 else 'NO'}",
        f"regret medio control: "
        f"{sum(d['reg_control'] for d in det) / len(det):.2f} | "
        f"tratamiento: "
        f"{sum(d['reg_tratamiento'] for d in det) / len(det):.2f} | "
        f"mejor fija: "
        f"{sum(d['reg_mejor_fija'] for d in det) / len(det):.2f}",
        f"reproducibilidad del control vs EXP47 (bit-idéntico): {repro_ok}",
    ]
    report = {
        "preregistro": "preregistro.json (mismo directorio)",
        "n_items": H, "n_bloques": n_bloques,
        "detalle_replicas": det,
        "efecto_medio": round(media_ef, 3),
        "tasa_misfire_tratamiento": round(tasa_t, 4)
        if tasa_t is not None else None,
        "tasa_misfire_control": round(tasa_c, 4)
        if tasa_c is not None else None,
        "tasa_misfire_exp47_ref": round(TASA_MISFIRE_EXP47, 4),
        "saltados_det_rep0": salt_rep0,
        "diagnostico_bloques_rep0": diag_rep0,
        "reproducibilidad_exp47": repro_ok,
        "costo_total_usd": 0.0,
        "veredicto": {
            "pasa_1_misfires": pasa_1, "pasa_2_efecto": pasa_2,
            "pass": pasa,
            "criterio": prereg["criterio"], "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP48 ================")
    for m in motivos:
        print("  " + m)
    print("  costo: $0.0000 USD (mock) | "
          f"{report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
