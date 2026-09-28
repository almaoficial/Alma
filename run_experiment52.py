#!/usr/bin/env python3
"""ALMA-EXP52: atacar la interacción gate<->soporte (mock, US$0).

Estado de la línea tras siete experimentos: EXP51 PASS (efecto medio -1,60,
hueco a la mejor fija achicado de 3,8 a 2,2). Pero dos tercios del ahorro
del gate adaptativo se fugan por un efecto colateral: los bloques con gate
dejan probe_obs con 3 items en vez de 5 -> la cuenta de victorias del
soporte se vuelve mas ruidosa -> el tratamiento salta MAS (18 vs 14) y esos
skips extra misfirean (5/18 vs 2/14). El mecanismo que manda ahora es la
interaccion, no el probe.

Diseno:
- Control: el tratamiento de EXP51 ("probe-barato") VERBATIM (misma funcion
  run_experiment51.correr_replica_probe_barato, importada sin copiar).
- Tratamiento ("soporte-puro"): copia verbatim del control, salvo UN moving
  part: los bloques donde el gate adaptativo disparo (probe_obs con solo
  Q1, 3 items) NO aportan victorias al soporte del skip. Solo los probes
  completos (Q1+Q2, 5 items, full-information) cuentan para K y para wins.
  El gate sigue abaratando el probe donde dispara; su ruido ya no alimenta
  la decision de saltar.

Variante elegida: (a) soporte solo de probes completos. Por que es la mas
limpia:
  - (b) exigir margen minimo en Q1 ataca el gate mismo (lo que funciona:
    -24 en bloques no saltados en EXP51) en vez de la interaccion; y un
    margen sobre medias de 3 items es a su vez ruidoso. (a) corta el canal
    colateral sin debilitar el gate: desacopla los dos mecanismos.
  - (a) restaura el significado original del soporte (victorias sobre
    probes full-information de 5 items, como se diseno en EXP45-49): la
    evidencia del skip vuelve a ser la que la vara pre-registro de toda la
    linea.

Mismo stream de 24 bloques bit-identico (construir_stream de EXP47), 5
replicas pareadas con RNG comun.

Criterio PRE-REGISTRADO:
  pasa_1: media sobre replicas pareadas de regret(trat)-regret(ctrl) < 0
          (misma vara de refutacion que toda la linea) -> PASS/FAIL.
  REGLA DE CIERRE DE LA LINEA (pre-registrada, sin ambiguedad):
    La linea de skills CONTINUA solo si se cumplen AMBAS:
      (i)  efecto medio < -2.0  (mejora material vs el -1,60 de EXP51)
      (ii) d_trat = reg_trat_medio - reg_mejor_fija_medio < 1.8
    Si alguna no se cumple, la linea se CIERRA con dictamen explicito:
    el techo ~2 puntos es estructural del mundo (ruido 2/10 por bloque),
    no del mecanismo. El cierre se reporta aunque pasa_1 sea PASS.

Correccion honesta pre-registrada del chequeo de sanidad (leccion de EXP51,
punto 1 de honestidad incomoda): NO se pre-registra que el costo Q1 total
sea bit-identico entre politicas. Lo que es bit-identico por construccion
son los sorteos del oraculo por (rep,b,q,a) cuando el probe ocurre. Los
totales de Q1 pueden divergir porque los caminos de skip divergen (efecto
downstream genuino del tratamiento). La sanidad que si se verifica: el
control reproduce bit-identico al tratamiento de EXP51.

Uso:
    python3 run_experiment52.py [--out DIR] [--replicas N]
"""

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_experiment47 as e47  # noqa: E402  (maquinaria base)
import run_experiment49 as e49  # noqa: E402  (umbral endurecido)
import run_experiment51 as e51  # noqa: E402  (control verbatim)

BASE = os.path.dirname(os.path.abspath(__file__))
EXP51_REPORT = os.path.join(BASE, "resultados", "exp51-20260927",
                            "report.json")

UMBRAL_EFECTO_CIERRE = -2.0   # (i) mejora material vs -1,60 de EXP51
UMBRAL_DISTANCIA_CIERRE = 1.8  # (ii) hueco a la mejor fija


def soporte_solo_completos(brazos, probe_obs, gate_fired, block_sig, b,
                           sig, skill_arm):
    """Soporte endurecido (EXP49) restringido a probes COMPLETOS.

    UNICO cambio vs e49.soporte_endurecido: los bloques donde el gate
    adaptativo disparo (gate_fired[b2] True -> probe_obs con solo Q1,
    3 items) no aportan ni a K ni a wins. K = nº de bloques pasados no
    saltados con la misma firma y probe completo de 5 items.
    Retorna (fuerte, wins, K, umbral).
    """
    wins = 0
    K = 0
    for b2 in range(b):
        if block_sig.get(b2) != sig:
            continue
        if gate_fired.get(b2):
            continue  # MOVING PART: probe incompleto, no es evidencia
        obs = probe_obs.get(b2)
        if not obs:
            continue  # bloque saltado: sin comparacion pareada
        K += 1
        m_s = sum(obs[skill_arm]) / len(obs[skill_arm])
        if all(m_s > sum(obs[a]) / len(obs[a])
               for a in brazos if a != skill_arm):
            wins += 1
    umbral = e49.umbral_endurecido(K)
    return wins >= umbral, wins, K, umbral


def correr_replica_soporte_puro(rep_id, items, tasas):
    """Tratamiento soporte-puro de EXP52.

    COPIA VERBATIM de e51.correr_replica_probe_barato: misma logica, mismos
    seeds de RNG, mismo orden de sorteos, misma contabilidad honesta, mismo
    gate adaptativo, mismo diagnostico de misfires. El UNICO moving part:
    la decision de skip usa soporte_solo_completos (los bloques con gate
    no cuentan para el soporte) en vez de e49.soporte_endurecido.
    """
    brazos = tasas["brazos"]
    H = len(items)
    n_bloques = H // e47.BLOQUE
    rep_hist = {a: [] for a in brazos}  # (h, reward, bloque)
    block_sig = {}
    probe_obs = {}  # b -> {brazo: [rewards en items de probe]} | None
    gate_fired = {}  # b -> True si el gate adapto el probe (solo Q1)
    rew_pol = [0.0] * H
    rew_fija = {a: [0.0] * H for a in brazos}
    reg_pol_bloques = []
    diag = []
    skills_usadas = 0
    probes_saltados = 0
    saltados_det = []
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
            # UNICO MOVING PART: soporte solo de probes completos.
            fuerte, wins, K, umbral = soporte_solo_completos(
                brazos, probe_obs, gate_fired, block_sig, b, sig, skill_arm)
            saltar = fuerte

        clf = e47.MockClasificador(tasas)
        for hh in range(base):
            clf.registrar(items[hh])

        if saltar:
            # PROBE SALTADO: identico a EXP49/51.
            probes_saltados += 1
            probe_obs[b] = None
            gate_fired[b] = False
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

        # --- Camino con probe: identico a EXP51 ---
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

        gate = (skill_arm is not None and usa_skill and
                e51.q1_decisivo(brazos, rs_q1, skill_arm))
        gate_fired[b] = bool(gate)

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
            q2_saltados += 1
            thompson(e47.PROBE_Q2)
        else:
            rs_q2 = {}
            for q in e47.PROBE_Q2:
                h = base + q
                rs_q2[q] = medir(q, "q2")
                rew_pol[h] = rs_q2[q][fav]
        thompson(tuple(q for q in e47.THOMPSON_Q if q > e47.PROBE_Q2[-1]))
        costo_probe_q2_items += len(e47.PROBE_Q2) - sum(
            rew_pol[base + q] for q in e47.PROBE_Q2)

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
    return {"politica": "soporte-puro", "reg_pol": reg_pol,
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

    out = args.out or os.path.join(BASE, "resultados", "exp52-20260927")
    os.makedirs(out, exist_ok=True)

    items = e47.construir_stream()  # bit-identico al stream de EXP47-51
    H = len(items)
    n_bloques = H // e47.BLOQUE
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))

    # --- pre-registro ANTES de correr ---
    prereg = {
        "experimento": "ALMA-EXP52: atacar la interaccion gate<->soporte "
                       "(mock, US$0)",
        "fase": "mock",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "hipotesis": "En EXP51 el gate adaptativo abarato el probe en "
                     "bloques no saltados (-24 en 5 replicas), pero los "
                     "bloques con gate dejan probe_obs con 3 items en vez "
                     "de 5, y esa evidencia ruidosa alimenta la cuenta de "
                     "victorias del soporte: el tratamiento salta MAS "
                     "(18 vs 14) y los skips extra misfirean (5/18 vs "
                     "2/14), devolviendo +16. Si los bloques con gate NO "
                     "aportan victorias al soporte (solo los probes "
                     "completos de 5 items cuentan para K y wins), se corta "
                     "el canal colateral sin debilitar el gate: el ahorro "
                     "del probe se conserva y los skips vuelven a "
                     "dispararse solo con evidencia full-information. "
                     "Resultado esperado: media sobre replicas pareadas de "
                     "regret(soporte-puro) - regret(probe-barato) < 0, con "
                     "menos skips y menor tasa de misfires que el control.",
        "variante_elegida": "(a) soporte solo de probes completos. "
                            "Descartada (b) exigir margen minimo en Q1: "
                            "ataca el gate mismo (lo que funciona) en vez "
                            "de la interaccion, y un margen sobre medias "
                            "de 3 items es a su vez ruidoso.",
        "nota_refutacion": "Riesgos que matarian la hipotesis: (1) al "
                           "excluir bloques con gate, K cae y el umbral "
                           "endurecido se vuelve mas dificil de alcanzar: "
                           "el tratamiento podria saltar MUCHO menos y "
                           "perder el ahorro del skip donde el control lo "
                           "captura; (2) si la evidencia de 3 items era en "
                           "realidad informativa, excluirla empobrece el "
                           "soporte y los misfires no bajan; (3) si el "
                           "efecto neto no mejora de forma material vs el "
                           "-1,60 de EXP51, la interaccion no era la "
                           "restriccion vinculante y el hueco ~2 puntos a "
                           "la mejor fija es estructural del mundo (ruido "
                           "2/10 por bloque) -> la linea se cierra por la "
                           "regla pre-registrada.",
        "chequeo_sanidad_corregido": "Leccion de EXP51 (honestidad "
            "incomoda #1): NO se pre-registra que el costo Q1 total sea "
            "bit-identico entre politicas. Lo bit-identico por "
            "construccion son los sorteos del oraculo por (rep,b,q,a) "
            "cuando el probe ocurre. Los totales de Q1 pueden divergir "
            "porque los caminos de skip divergen (efecto downstream "
            "genuino). Sanidad verificable: el control reproduce "
            "bit-identico al tratamiento de EXP51.",
        "condicion_alcance": e47.CONDICION_ALCANCE,
        "stream": {
            "fuente": "IDENTICO al de EXP47/48/49/50/51 (misma funcion "
                      "run_experiment47.construir_stream, bit-identico): "
                      "240 items, 24 bloques x 10, 3 regimenes x 8 "
                      "recurrencias, seeds 45/47, namespace de RNG del "
                      "oraculo 'exp45-...'.",
            "n_items": H, "bloques": n_bloques,
            "tam_bloque": e47.BLOQUE,
            "regimenes": e47.REGIMENES,
            "oraculo": "tasas mock calibradas por categoria "
                       "(data_exp44/tasas.json)",
            "sesgo_seleccion": e47.SESGO_SELECCION,
        },
        "politicas": {
            "control": "El probe-barato de EXP51 VERBATIM (misma funcion "
                       "run_experiment51.correr_replica_probe_barato, "
                       "importada sin copiar): gate adaptativo que salta "
                       "Q2 si Q1 decide a favor del brazo de la skill; los "
                       "bloques con gate aportan probe_obs de 3 items al "
                       "soporte endurecido.",
            "soporte-puro": "COPIA VERBATIM del control, salvo UN moving "
                "part: la decision de skip usa soporte_solo_completos: "
                "los bloques donde el gate disparo (probe_obs de 3 items) "
                "no aportan ni a K ni a wins. Solo probes completos "
                "(Q1+Q2, 5 items) cuentan. El gate, el bandit, los seeds y "
                "el orden de sorteos son identicos.",
        },
        "rng": "namespace del oraculo identico a EXP45-51 "
               "('exp45-r{rep}-b{b}-q{q}-{a}'). Pareado por replica; las "
               "jugadas extra de Thompson en items 6,7 usan namespace "
               "'-sel' propio por (b,q): no interfieren con ningun sorteo "
               "del control.",
        "criterio": {
            "efecto": "regret(soporte-puro) - regret(probe-barato) sobre "
                      "24 bloques, media sobre replicas (pareadas, RNG "
                      "comun)",
            "pasa_1": "media(efecto) < 0  [misma vara de refutacion que "
                      "toda la linea]",
            "pass": "pasa_1",
            "regla_cierre_linea": "La linea de skills CONTINUA solo si se "
                f"cumplen AMBAS: (i) efecto medio < {UMBRAL_EFECTO_CIERRE} "
                "(mejora material vs el -1,60 de EXP51) Y (ii) d_trat = "
                "reg_trat_medio - reg_mejor_fija_medio < "
                f"{UMBRAL_DISTANCIA_CIERRE}. Si alguna no se cumple, la "
                "linea se CIERRA con dictamen explicito: el techo ~2 "
                "puntos es estructural del mundo (ruido 2/10 por bloque), "
                "no del mecanismo. El cierre se aplica aunque pasa_1 sea "
                "PASS.",
            "diagnostico_auxiliar": "skips y misfires de ambas politicas "
                "(el moving part debe bajar ambos vs el control); tasa de "
                "disparo del gate; reproducibilidad bit-identica del "
                "control vs EXP51; efecto sin la mejor replica; distancia "
                "de ambas politicas a la mejor fija.",
        },
        "replicas": args.replicas,
        "modo": "mock, US$0",
    }
    with open(os.path.join(out, "preregistro.json"), "w",
              encoding="utf-8") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito ({H} items, {n_bloques} bloques, "
          f"{args.replicas} replicas pareadas).")

    efectos, det = [], []
    for r in range(args.replicas):
        ctrl = e51.correr_replica_probe_barato(r, items, tasas)
        trt = correr_replica_soporte_puro(r, items, tasas)
        ef = trt["reg_pol"] - ctrl["reg_pol"]
        efectos.append(ef)

        def misfires(res):
            sk = res["saltados_det"]
            return len(sk), sum(1 for d in sk if d["misfire"])

        sk_c, mis_c = misfires(ctrl)
        sk_t, mis_t = misfires(trt)
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
            "skips_control": sk_c, "misfires_control": mis_c,
            "skips_tratamiento": sk_t, "misfires_tratamiento": mis_t,
            "q2_saltados_control": ctrl["q2_saltados"],
            "q2_saltados_trat": trt["q2_saltados"],
            "costo_q1_control": round(ctrl["costo_probe_q1"], 3),
            "costo_q1_trat": round(trt["costo_probe_q1"], 3),
            "costo_q2_items_control": round(ctrl["costo_probe_q2_items"], 3),
            "costo_q2_items_trat": round(trt["costo_probe_q2_items"], 3),
        })
        if r == 0:
            diag_rep0 = {"control": ctrl["diag"],
                         "tratamiento": trt["diag"]}
            salt_rep0 = {"control": ctrl["saltados_det"],
                         "tratamiento": trt["saltados_det"]}

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

    pasa_1 = bool(media_ef < 0)
    pasa = pasa_1
    mejora_material = bool(media_ef < UMBRAL_EFECTO_CIERRE)
    hueco_chico = bool(d_trat < UMBRAL_DISTANCIA_CIERRE)
    continua = bool(mejora_material and hueco_chico)
    cierre = not continua

    # --- chequeo de reproducibilidad: el control debe ser bit-identico al
    # tratamiento probe-barato de EXP51 (misma funcion, mismo stream) ---
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

    sk_c_tot = sum(d["skips_control"] for d in det)
    mis_c_tot = sum(d["misfires_control"] for d in det)
    sk_t_tot = sum(d["skips_tratamiento"] for d in det)
    mis_t_tot = sum(d["misfires_tratamiento"] for d in det)

    motivos = [
        f"items={H}, bloques={n_bloques} (3 regimenes x 8 recurrencias), "
        f"replicas pareadas={args.replicas} (RNG comun, oraculo identico)",
        f"efecto medio (reg_trat - reg_ctrl) = {media_ef:+.3f} "
        f"(por replica: {', '.join(f'{e:+.2f}' for e in efectos)})",
        f"skips — control: {sk_c_tot} (misfires {mis_c_tot}, "
        f"tasa {mis_c_tot/max(sk_c_tot,1):.1%}) | tratamiento: {sk_t_tot} "
        f"(misfires {mis_t_tot}, tasa {mis_t_tot/max(sk_t_tot,1):.1%})",
        f"gate adaptativo (Q2 saltados) — control: "
        f"{sum(d['q2_saltados_control'] for d in det)} | tratamiento: "
        f"{sum(d['q2_saltados_trat'] for d in det)}",
        f"regret medio control: {reg_ctrl_medio:.2f} | tratamiento: "
        f"{reg_trat_medio:.2f} | mejor fija: {reg_fija_medio:.2f}",
        f"distancia a la mejor fija — control: {d_ctrl:.2f} | tratamiento: "
        f"{d_trat:.2f}",
        f"media del efecto sin la mejor replica: {media_sin_mejor:+.2f} "
        f"(¿cargado por una sola replica? {'SI' if cargado_una_replica else 'NO'})",
        f"(1) media(efecto) < 0: {'SI -> PASS' if pasa_1 else 'NO -> FAIL'}",
        f"regla de cierre — (i) efecto < {UMBRAL_EFECTO_CIERRE}: "
        f"{'SI' if mejora_material else 'NO'} | (ii) d_trat < "
        f"{UMBRAL_DISTANCIA_CIERRE}: {'SI' if hueco_chico else 'NO'} "
        f"-> linea: {'CONTINUA' if continua else 'SE CIERRA'}",
        f"reproducibilidad del control vs EXP51 (bit-identico): {repro_ok}",
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
        "umbrales_cierre": {"efecto": UMBRAL_EFECTO_CIERRE,
                            "distancia": UMBRAL_DISTANCIA_CIERRE},
        "mejora_material": mejora_material,
        "hueco_chico": hueco_chico,
        "linea_continua": continua,
        "linea_se_cierra": cierre,
        "skips_totales": {"control": sk_c_tot, "tratamiento": sk_t_tot},
        "misfires_totales": {"control": mis_c_tot,
                             "tratamiento": mis_t_tot},
        "saltados_det_rep0": salt_rep0,
        "diagnostico_bloques_rep0": diag_rep0,
        "reproducibilidad_exp51": repro_ok,
        "costo_total_usd": 0.0,
        "veredicto": {
            "pasa_1_efecto": pasa_1, "pass": pasa,
            "mejora_material": mejora_material, "hueco_chico": hueco_chico,
            "linea_continua": continua, "linea_se_cierra": cierre,
            "criterio": prereg["criterio"], "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP52 ================")
    for m in motivos:
        print("  " + m)
    print("  costo: $0.0000 USD (mock) | "
          f"{report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL",
          f"(efecto medio {media_ef:+.3f}) | LINEA:",
          "CONTINUA" if continua else "SE CIERRA")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
