#!/usr/bin/env python3
"""ALMA-EXP51: atacar el residuo — probe ABARATADO en bloques no saltados (mock, US$0).

Estado de la línea tras seis experimentos: la selectividad de la skill quedó
dirimida (EXP50: el valor está en elegir bien, no en saltar menos). Lo que NO
se movió en seis marcas: ~4 puntos bajo la mejor fija, y el residuo está en
el PROBE de los bloques no saltados — ninguna variante lo tocó.

Diseño:
- Control: el tratamiento de EXP49/50 (skip con umbral endurecido) VERBATIM
  (misma función run_experiment49.correr_replica_endurecido, importada).
- Tratamiento ("probe-barato"): idéntico al control, salvo UN moving part:
  el probe se vuelve ADAPTATIVO. En los bloques no saltados, si la firma es
  conocida (la skill existe) y los 3 items del probe Q1 ya deciden a favor
  del brazo de la skill de forma estricta sobre todos los demás brazos, se
  salta el re-probe Q2 (los items 6,7 pasan a ser jugadas de Thompson con la
  información ya recolectada, en vez de scoring ciego con el favorito ciego).

Variante elegida: (a) probe adaptativo que termina temprano cuando Q1 es
decisivo. Por qué es la más limpia:
  - (b) probe corto cuando la firma matchea es un proxy grueso: salta Q2 por
    existir la skill, use la evidencia o no. (a) salta Q2 solo cuando la
    evidencia recolectada (Q1) ya lo decidió — gasta presupuesto de probe
    solo donde compra información.
  - (c) warm-start con el bloque anterior ya quedó dominado por el prior
    warm con olvido 0.5^d que el bandit usa desde EXP9: no es un moving part
    independiente, es re-tunear el olvido.

Contabilidad honesta: Q1 es bit-idéntico en ambas políticas (mismos sorteos
del oráculo, mismo scoring con fav ciego). El ahorro vive solo en los items
6,7: control los anota con scoring ciego; tratamiento los juega con el
bandit cuando el gate dispara.

Mismo stream de 24 bloques bit-idéntico (construir_stream de EXP47), 5
réplicas pareadas con RNG común.

Criterio PRE-REGISTRADO:
  pasa_1: media sobre réplicas pareadas de regret(trat)-regret(ctrl) < 0
          (misma vara de refutación que toda la línea).
  OBJETIVO DE LÍNEA (el residuo): d_trat = reg_trat_medio - reg_mejor_fija_medio
          < 2.5 → el hueco se achicó de forma sustantiva (hoy está en ~3.8).
          Se reporta como SÍ/NO junto al PASS/FAIL; no cambia el veredicto,
          que sigue siendo pasa_1.

Medición del costo del probe (pre-registrada):
  costo_q1 = regret en los 3 items de Q1 (bit-idéntico entre políticas).
  costo_q2_items = regret en los items 6,7: en el control siempre scoring
  ciego; en el tratamiento, jugadas del bandit cuando el gate dispara y
  scoring ciego cuando no. La diferencia es exactamente el ahorro del gate.

Uso:
    python3 run_experiment51.py [--out DIR] [--replicas N]
"""

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_experiment47 as e47  # noqa: E402  (maquinaria base)
import run_experiment49 as e49  # noqa: E402  (control verbatim)

BASE = os.path.dirname(os.path.abspath(__file__))
EXP49_REPORT = os.path.join(BASE, "resultados", "exp49-20260927",
                            "report.json")

UMBRAL_DISTANCIA = 2.5  # objetivo de línea: d_trat < 2.5 (hoy ~3.8)


def q1_decisivo(brazos, rs_q1, skill_arm):
    """¿Q1 decide a favor del brazo de la skill? Media estricta sobre los 3
    items de Q1 contra cada otro brazo. Solo usa evidencia ya recolectada."""
    m_s = sum(rs_q1[q][skill_arm] for q in e47.PROBE_Q1) / len(e47.PROBE_Q1)
    return all(m_s > sum(rs_q1[q][a] for q in e47.PROBE_Q1) /
               len(e47.PROBE_Q1)
               for a in brazos if a != skill_arm)


def correr_replica_probe_barato(rep_id, items, tasas):
    """Tratamiento probe-barato de EXP51.

    COPIA VERBATIM del skip-endurecido de EXP49
    (e49.correr_replica_endurecido): misma lógica, mismos seeds de RNG,
    mismo orden de sorteos, misma contabilidad honesta, mismo diagnóstico
    de misfires. El ÚNICO moving part: en el camino con probe, el re-probe
    Q2 se salta cuando (1) la skill existe y (2) Q1 es decisivo a favor del
    brazo de la skill; los items 6,7 pasan a jugadas de Thompson.
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
    # --- contabilidad del costo del probe (pre-registrada) ---
    q2_saltados = 0
    costo_probe_q1 = 0.0
    costo_probe_q2_items = 0.0

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
            # PROBE SALTADO: idéntico a EXP49 (sin probe, sin gate).
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

        # --- Camino con probe: idéntico a EXP49 hasta el gate adaptativo ---
        bandit = e47.nuevo_bandit(
            brazos, e47.prior_params(brazos, rep_hist, block_sig, b, None))
        prior_means = {a: bandit.mean(a) for a in brazos}
        fav = max(brazos, key=lambda a: prior_means[a])

        def medir(q, rng_tag):
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
            rs_q1[q] = medir(q, "q1")
            rew_pol[h] = rs_q1[q][fav]
        costo_probe_q1 += len(e47.PROBE_Q1) - sum(
            rew_pol[base + q] for q in e47.PROBE_Q1)

        usa_skill = False
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            usa_skill = True
            skills_usadas += 1
            bandit = e47.nuevo_bandit(
                brazos, e47.prior_params(brazos, rep_hist, block_sig, b, sig))
            for q in e47.PROBE_Q1:
                for a in brazos:
                    bandit.update(a, rs_q1[q][a])

        # ÚNICO MOVING PART: gate adaptativo sobre la evidencia de Q1.
        gate = (skill_arm is not None and usa_skill and
                q1_decisivo(brazos, rs_q1, skill_arm))

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
            # Q2 SALTADO: items 6,7 como jugadas de Thompson (sin re-probe).
            q2_saltados += 1
            thompson(e47.PROBE_Q2)
        else:
            # RE-PROBE Q2: idéntico al control, scoring honesto con fav ciego.
            rs_q2 = {}
            for q in e47.PROBE_Q2:
                h = base + q
                rs_q2[q] = medir(q, "q2")
                rew_pol[h] = rs_q2[q][fav]
        thompson(tuple(q for q in e47.THOMPSON_Q if q > e47.PROBE_Q2[-1]))
        costo_probe_q2_items += len(e47.PROBE_Q2) - sum(
            rew_pol[base + q] for q in e47.PROBE_Q2)

        # probe_obs: con gate, solo Q1 (3 items); sin gate, Q1+Q2 (5 items).
        # La cuenta de victorias de la skill usa la media sobre los items
        # disponibles: consistente dentro de la política, documentado.
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
            "acc_pol": round(
                sum(rew_pol[base:base + e47.BLOQUE]) / e47.BLOQUE, 4),
            "acc_fijas": {
                a: round(sum(rew_fija[a][base:base + e47.BLOQUE]) /
                         e47.BLOQUE, 4)
                for a in brazos},
        })

    reg_pol = H - sum(rew_pol)
    reg_fijas = {a: H - sum(rew_fija[a]) for a in brazos}
    mejor = min(brazos, key=lambda a: reg_fijas[a])
    return {"politica": "probe-barato", "reg_pol": reg_pol,
            "reg_pol_bloques": reg_pol_bloques,
            "reg_fijas": reg_fijas,
            "mejor_fija": mejor, "reg_mejor_fija": reg_fijas[mejor],
            "skills_usadas": skills_usadas, "probes_saltados": probes_saltados,
            "q2_saltados": q2_saltados,
            "costo_probe_q1": costo_probe_q1,
            "costo_probe_q2_items": costo_probe_q2_items,
            "saltados_det": saltados_det, "n_bloques": n_bloques,
            "diag": diag, "n": H}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--replicas", type=int, default=e47.N_REPLICAS)
    args = ap.parse_args()
    t0 = time.time()

    out = args.out or os.path.join(BASE, "resultados", "exp51-20260927")
    os.makedirs(out, exist_ok=True)

    items = e47.construir_stream()  # bit-idéntico al stream de EXP47-50
    H = len(items)
    n_bloques = H // e47.BLOQUE
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))

    # --- pre-registro ANTES de correr ---
    prereg = {
        "experimento": "ALMA-EXP51: atacar el residuo — probe abaratado "
                       "en bloques no saltados (mock, US$0)",
        "fase": "mock",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "hipotesis": "En los bloques no saltados con firma conocida, si los "
                     "3 items del probe Q1 ya deciden a favor del brazo de "
                     "la skill de forma estricta sobre todos los demás "
                     "brazos, el re-probe Q2 (2 items con scoring ciego del "
                     "favorito ciego) no compra suficiente información para "
                     "justificar su costo: saltarlo y pasar a Thompson "
                     "reduce el costo del probe sin perder identificación, "
                     "y reduce el regret frente al skip-endurecido: media "
                     "sobre réplicas pareadas de regret(probe-barato) - "
                     "regret(skip-endurecido) < 0.",
        "variante_elegida": "(a) probe adaptativo que termina temprano "
                            "cuando Q1 es decisivo. Descartadas: (b) probe "
                            "corto por firma matcheada — proxy grueso que "
                            "salta Q2 use la evidencia o no; (c) warm-start "
                            "con el bloque anterior — ya dominada por el "
                            "prior warm con olvido 0.5^d (EXP9): no es un "
                            "moving part independiente.",
        "nota_refutacion": "El gate vive y muere con la calidad de Q1: si "
                           "Q1 es decisivo pero ruidoso (el brazo de la "
                           "skill gana los 3 items por azar y Q2 lo habría "
                           "corregido), el tratamiento pierde información "
                           "full-information y la cuenta de victorias de la "
                           "skill se vuelve más ruidosa (medias sobre 3 "
                           "items en vez de 5 en los bloques con gate). Si "
                           "el efecto no aparece o el gate casi nunca "
                           "dispara, el residuo no está en el re-probe Q2: "
                           "está en Q1 o en Thompson, y habría que atacar "
                           "ahí — o aceptar que el hueco a la mejor fija es "
                           "estructural del mundo (regímenes con 2/10 de "
                           "ruido por bloque).",
        "condicion_alcance": e47.CONDICION_ALCANCE,
        "stream": {
            "fuente": "IDÉNTICO al de EXP47/48/49/50 (misma función "
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
            "control": "El skip-endurecido de EXP49/50 VERBATIM (misma "
                       "función run_experiment49.correr_replica_endurecido, "
                       "importada sin copiar): umbral(K) = 2 + floor(K/3).",
            "probe-barato": "COPIA VERBATIM del control, salvo UN moving "
                "part: en el camino con probe, si la skill existe y Q1 es "
                "decisivo a favor del brazo de la skill (media estricta "
                "sobre los 3 items contra cada otro brazo), se salta el "
                "re-probe Q2 y los items 6,7 se juegan con Thompson. "
                "probe_obs[b] queda con 3 items (Q1) en vez de 5 cuando el "
                "gate dispara: la cuenta de victorias usa medias sobre los "
                "items disponibles, consistente dentro de la política.",
        },
        "gate_adaptativo": {
            "condicion": "skill existe (misma firma en bloque pasado) Y "
                         "media_Q1(skill_arm) > media_Q1(a) para todo otro "
                         "brazo a (estricta, sobre los 3 items de Q1)",
            "efecto": "items 6,7: jugadas de Thompson en vez de scoring "
                      "ciego con fav; sin medición full-information en Q2; "
                      "el bandit y rep_hist reciben las jugadas 6,7",
            "no_dispara_si": "no hay skill (skill_arm None) o Q1 no es "
                             "decisivo → camino idéntico al control",
        },
        "costo_probe_medicion": {
            "costo_q1": "regret en los 3 items de Q1 (bit-idéntico entre "
                        "políticas por construcción)",
            "costo_q2_items": "regret en los items 6,7: control siempre "
                              "scoring ciego; tratamiento jugadas del "
                              "bandit si el gate dispara, scoring ciego si "
                              "no. La diferencia es exactamente el ahorro "
                              "del gate.",
        },
        "rng": "namespace del oráculo idéntico a EXP45-50 "
               "('exp45-r{rep}-b{b}-q{q}-{a}'). Q1 bit-idéntico entre "
               "políticas. Las jugadas extra de Thompson del tratamiento "
               "en items 6,7 usan namespace '-sel' propio por (b,q): no "
               "interfieren con ningún sorteo del control. Pareado por "
               "réplica.",
        "criterio": {
            "efecto": "regret(probe-barato) - regret(skip-endurecido) "
                      "sobre 24 bloques, media sobre réplicas (pareadas, "
                      "RNG común)",
            "pasa_1": "media(efecto) < 0  [misma vara de refutación que "
                      "toda la línea]",
            "pass": "pasa_1",
            "objetivo_linea_distancia": f"d_trat = reg_trat_medio - "
                "reg_mejor_fija_medio < 2.5 [el hueco hoy está en ~3.8 "
                "(EXP50: 88.0 vs 84.2); el objetivo de la línea es cerrarlo; "
                "se reporta como SÍ/NO junto al PASS/FAIL sin cambiar el "
                "veredicto]",
            "diagnostico_auxiliar": "tasa de disparo del gate (q2_saltados "
                "/ bloques con probe y skill); costo_q1 (sanidad: debe ser "
                "idéntico entre políticas); ahorro en costo_q2_items; "
                "reproducibilidad bit-idéntica del control vs EXP49; efecto "
                "sin la mejor réplica; distancia de ambas políticas a la "
                "mejor fija.",
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
        ctrl = e49.correr_replica_endurecido(r, items, tasas)
        trt = correr_replica_probe_barato(r, items, tasas)
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
            "skips_control": ctrl["probes_saltados"],
            "costo_q1_trat": round(trt["costo_probe_q1"], 3),
            "costo_q2_items_trat": round(trt["costo_probe_q2_items"], 3),
            # costos del control: los mide medir_costos_control (abajo)
            "costo_q1_control": None,
            "costo_q2_items_control": None,
        })
        # costos Q1/Q2 del control: se miden con una corrida instrumentada
        # idéntica (medir_costos_control, abajo): mismos seeds → mismos
        # números. El costo_q1 del control debe resultar igual al del
        # tratamiento (Q1 bit-idéntico): chequeo de sanidad pre-registrado.
        if r == 0:
            diag_rep0 = {"control": ctrl["diag"],
                         "tratamiento": trt["diag"]}
            salt_rep0 = {"control": ctrl["saltados_det"],
                         "tratamiento": trt["saltados_det"]}

    det = medir_costos_control(det, items, tasas, args.replicas)

    n = len(efectos)
    media_ef = sum(efectos) / n
    mejor = min(efectos)
    media_sin_mejor = (sum(efectos) - mejor) / (n - 1)
    cargado_una_replica = bool(media_sin_mejor >= 0)

    reg_trat_medio = sum(d["reg_tratamiento"] for d in det) / n
    reg_ctrl_medio = sum(d["reg_control"] for d in det) / n
    reg_fija_medio = sum(d["reg_mejor_fija"] for d in det) / n
    d_trat = reg_trat_medio - reg_fija_medio
    d_ctrl = reg_ctrl_medio - reg_fija_medio
    ahorro_q2 = sum(d["costo_q2_items_control"] - d["costo_q2_items_trat"]
                    for d in det)
    q2_tot = sum(d["q2_saltados_trat"] for d in det)

    pasa_1 = bool(media_ef < 0)
    pasa = pasa_1
    achica_hueco = bool(d_trat < UMBRAL_DISTANCIA)

    # --- chequeo de reproducibilidad: el control debe ser bit-idéntico al
    # tratamiento skip-endurecido de EXP49 (misma función, mismo stream) ---
    repro_ok = None
    try:
        rep49 = json.load(open(EXP49_REPORT, encoding="utf-8"))
        d49 = {d["replica"]: (d["reg_trat_bloques"], d["skips_tratamiento"])
               for d in rep49["detalle_replicas"]}
        repro_ok = all(
            [round(x, 3) for x in det[r]["reg_control_bloques"]] ==
            [round(x, 3) for x in d49[r][0]] and
            det[r]["skips_control"] == d49[r][1]
            for r in range(args.replicas))
    except Exception as e:  # noqa: BLE001
        repro_ok = f"no verificable: {e}"

    motivos = [
        f"items={H}, bloques={n_bloques} (3 regímenes x 8 recurrencias), "
        f"réplicas pareadas={args.replicas} (RNG común, oráculo idéntico)",
        f"efecto medio (reg_trat - reg_ctrl) = {media_ef:+.3f} "
        f"(por réplica: {', '.join(f'{e:+.2f}' for e in efectos)})",
        f"gate adaptativo: Q2 saltado en {q2_tot} bloques con probe "
        f"(por réplica: {[d['q2_saltados_trat'] for d in det]})",
        f"costo del probe — Q1 (sanidad, debe ser idéntico): "
        f"ctrl={sum(d['costo_q1_control'] for d in det):.2f} "
        f"trat={sum(d['costo_q1_trat'] for d in det):.2f} | "
        f"Q2-items: ctrl="
        f"{sum(d['costo_q2_items_control'] for d in det):.2f} "
        f"trat={sum(d['costo_q2_items_trat'] for d in det):.2f} "
        f"→ ahorro del gate: {ahorro_q2:+.2f}",
        f"regret medio control: {reg_ctrl_medio:.2f} | tratamiento: "
        f"{reg_trat_medio:.2f} | mejor fija: {reg_fija_medio:.2f}",
        f"distancia a la mejor fija — control: {d_ctrl:.2f} | tratamiento: "
        f"{d_trat:.2f} | objetivo pre-registrado < {UMBRAL_DISTANCIA}: "
        f"{'SÍ' if achica_hueco else 'NO'}",
        f"media del efecto sin la mejor réplica: {media_sin_mejor:+.2f} "
        f"(¿cargado por una sola réplica? {'SÍ' if cargado_una_replica else 'NO'})",
        f"(1) media(efecto) < 0: {'SÍ → PASS' if pasa_1 else 'NO → FAIL'}",
        f"reproducibilidad del control vs EXP49 (bit-idéntico): {repro_ok}",
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
        "umbral_distancia": UMBRAL_DISTANCIA,
        "achica_hueco": achica_hueco,
        "q2_saltados_total": q2_tot,
        "ahorro_costo_q2": round(ahorro_q2, 3),
        "saltados_det_rep0": salt_rep0,
        "diagnostico_bloques_rep0": diag_rep0,
        "reproducibilidad_exp49": repro_ok,
        "costo_total_usd": 0.0,
        "veredicto": {
            "pasa_1_efecto": pasa_1, "pass": pasa,
            "achica_hueco_distancia": achica_hueco,
            "criterio": prereg["criterio"], "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP51 ================")
    for m in motivos:
        print("  " + m)
    print("  costo: $0.0000 USD (mock) | "
          f"{report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL",
          f"(efecto medio {media_ef:+.3f}) + hueco a mejor fija: "
          f"{'ACHICADO' if achica_hueco else 'NO ACHICADO'} "
          f"({d_trat:.2f} vs objetivo < {UMBRAL_DISTANCIA})")
    print("==================================================")
    return 0 if pasa else 1


def medir_costos_control(det, items, tasas, n_replicas):
    """Mide el costo del probe del CONTROL con una corrida instrumentada
    idéntica a e49.correr_replica_endurecido (mismos seeds, mismo probe_obs
    con Q1+Q2, mismo orden de sorteos → mismos números), acumulando costo_q1
    y costo_q2_items. Llena los campos de `det`."""
    brazos = tasas["brazos"]
    H = len(items)
    n_bloques = H // e47.BLOQUE
    for r in range(n_replicas):
        rep_hist = {a: [] for a in brazos}
        block_sig = {}
        probe_obs = {}
        costo_q1 = 0.0
        costo_q2 = 0.0
        for b in range(n_bloques):
            base = b * e47.BLOQUE
            sig = e47.firma_grupo([items[base + q]["grupo"]
                                   for q in e47.PROBE_Q1])
            block_sig[b] = sig
            saltar = False
            skill_arm = None
            if e47.skill_existe(rep_hist, block_sig, b, sig):
                skill_arm = e47.skill_arm_actual(
                    brazos, rep_hist, block_sig, b, sig)
                fuerte, _, _, _ = e49.soporte_endurecido(
                    brazos, probe_obs, block_sig, b, sig, skill_arm)
                saltar = fuerte
            clf = e47.MockClasificador(tasas)
            for hh in range(base):
                clf.registrar(items[hh])
            if saltar:
                probe_obs[b] = None
                for q in range(e47.BLOQUE):
                    h = base + q
                    it = items[h]
                    rwd = clf.acierto(
                        skill_arm, it,
                        random.Random(f"exp45-r{r}-b{b}-q{q}-{skill_arm}"))
                    rep_hist[skill_arm].append((h, rwd, b))
                    clf.registrar(it)
                continue
            bandit = e47.nuevo_bandit(
                brazos, e47.prior_params(brazos, rep_hist, block_sig, b, None))
            prior_means = {a: bandit.mean(a) for a in brazos}
            fav = max(brazos, key=lambda a: prior_means[a])

            def medir(q):
                h = base + q
                it = items[h]
                rs = {a: clf.acierto(
                    a, it, random.Random(f"exp45-r{r}-b{b}-q{q}-{a}"))
                    for a in brazos}
                for a in brazos:
                    bandit.update(a, rs[a])
                    rep_hist[a].append((h, rs[a], b))
                clf.registrar(it)
                return rs

            rs_q1 = {}
            sq1 = 0.0
            for q in e47.PROBE_Q1:
                rs_q1[q] = medir(q)
                sq1 += rs_q1[q][fav]
            costo_q1 += len(e47.PROBE_Q1) - sq1
            if e47.skill_existe(rep_hist, block_sig, b, sig):
                bandit = e47.nuevo_bandit(
                    brazos, e47.prior_params(brazos, rep_hist, block_sig,
                                            b, sig))
                for q in e47.PROBE_Q1:
                    for a in brazos:
                        bandit.update(a, rs_q1[q][a])

            def thompson(qs):
                for q in qs:
                    h = base + q
                    it = items[h]
                    a_sel = bandit.select(
                        random.Random(f"exp45-r{r}-b{b}-q{q}-sel"))
                    r_sel = clf.acierto(
                        a_sel, it,
                        random.Random(f"exp45-r{r}-b{b}-q{q}-{a_sel}"))
                    bandit.update(a_sel, r_sel)
                    rep_hist[a_sel].append((h, r_sel, b))
                    clf.registrar(it)

            thompson(tuple(q for q in e47.THOMPSON_Q if q < e47.PROBE_Q2[0]))
            rs_q2 = {}
            sq2 = 0.0
            for q in e47.PROBE_Q2:
                h = base + q
                rs_q2[q] = medir(q)
                sq2 += rs_q2[q][fav]
            costo_q2 += len(e47.PROBE_Q2) - sq2
            thompson(tuple(q for q in e47.THOMPSON_Q if q > e47.PROBE_Q2[-1]))
            # probe_obs idéntico al original (Q1+Q2, 5 items): si no, el
            # conteo de victorias de la skill difiere y la corrida dejaría
            # de ser idéntica al control.
            probe_obs[b] = {a: [rs_q1[q][a] for q in e47.PROBE_Q1] +
                               [rs_q2[q][a] for q in e47.PROBE_Q2]
                            for a in brazos}
        det[r]["costo_q1_control"] = round(costo_q1, 3)
        det[r]["costo_q2_items_control"] = round(costo_q2, 3)
    return det


if __name__ == "__main__":
    sys.exit(main())
