#!/usr/bin/env python3
"""ALMA-EXP50: el mock dirimente de la línea de skills (EXP45→49). Mock US$0.

Pregunta abierta de EXP49: la baja de misfires (2/14 vs 14/38) vino de
SALTAR MUCHO MENOS (14 vs 38 skips), no de saltar mejor. ¿El efecto medio
(-1,80) viene de elegir bien los saltos (la skill aporta) o simplemente de
saltar menos?

- Tratamiento: skip con umbral endurecido de EXP49, importado VERBATIM
  (misma función run_experiment49.correr_replica_endurecido).
- Control ("skip-aleatorio"): salta la MISMA cantidad de bloques por réplica
  que el tratamiento (N_t(r) matcheado), pero eligiendo QUÉ bloques saltear
  al azar entre los elegibles (bloques donde la skill existe: misma
  firma-disponibilidad). En los bloques saltados juega el brazo de la skill
  con la misma contabilidad honesta y el mismo diagnóstico ex post de
  misfires; en los no saltados sigue el camino con probe idéntico al del
  tratamiento. RNG común y pareado por réplica.
  El ÚNICO moving part respecto al tratamiento: la regla de selección de
  qué bloques saltear (skill vs azar). Si el azar empata, la selectividad no
  aporta nada que la abstención no aporte.

Mismo stream de 24 bloques bit-idéntico (construir_stream de EXP47), 5
réplicas pareadas.

Criterio PRE-REGISTRADO (efecto = regret(tratamiento) - regret(azar)):
  - |efecto_medio| < 1.0  → EMPATE: la selectividad aleatoria empata con la
    skill → CIERRE de la línea: el valor estaba en saltar menos, no en la
    maquinaria de skills.
  - efecto_medio <= -1.0  → la skill supera al azar con margen → CONTINÚA:
    la selectividad aporta valor real.
  - efecto_medio >= +1.0  → el azar supera a la skill con margen → CIERRE:
    la selectividad no aporta (o es contraproducente).
  El umbral 1.0 ≈ 1 error estándar de la media entre réplicas observado en
  EXP49 (efectos +0,+1,-4,-5,-1 → sd muestral 2.55 → SE 1.14): "dentro del
  ruido entre réplicas". Las tres regiones son exhaustivas y mutuamente
  excluyentes; el dictamen no tiene ambigüedad.

Uso:
    python3 run_experiment50.py [--out DIR] [--replicas N]
"""

import argparse
import json
import os
import random
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_experiment47 as e47  # noqa: E402  (maquinaria base)
import run_experiment49 as e49  # noqa: E402  (tratamiento verbatim)

BASE = os.path.dirname(os.path.abspath(__file__))
EXP49_REPORT = os.path.join(BASE, "resultados", "exp49-20260927",
                            "report.json")

UMBRAL_EMPATE = 1.0  # |efecto| < 1.0 → empate (ruido entre réplicas)


def bloques_elegibles(items):
    """Bloques donde una skill PUEDE existir: hay un bloque pasado con la
    misma firma. El conjunto es política-independiente: block_sig se calcula
    solo del stream (firma de los primeros 3 items) y todo bloque agrega
    entradas a rep_hist en cualquier política (con probe o saltado), así que
    skill_existe(b) se reduce a esta condición determinista."""
    n_bloques = len(items) // e47.BLOQUE
    sigs = {}
    for b in range(n_bloques):
        base = b * e47.BLOQUE
        sigs[b] = e47.firma_grupo([items[base + q]["grupo"]
                                  for q in e47.PROBE_Q1])
    elegibles = [b for b in range(n_bloques)
                 if any(sigs[b2] == sigs[b] for b2 in range(b))]
    return elegibles, sigs


def sorteo_aleatorio(rep_id, elegibles, n):
    """N_t(r) bloques elegidos al azar (sin reposición). Namespace de RNG
    propio: no toca el oráculo ni el bandit."""
    rng = random.Random(f"exp50-r{rep_id}-randomskip")
    return sorted(rng.sample(elegibles, n))


def correr_replica_random(rep_id, items, tasas, skip_set):
    """Control skip-aleatorio de EXP50.

    COPIA VERBATIM del tratamiento de EXP49 (correr_replica_endurecido):
    misma lógica, mismos seeds de RNG, mismo orden de sorteos, misma
    contabilidad honesta, mismo diagnóstico ex post de misfires. El ÚNICO
    moving part: la decisión de salto no usa el soporte de la skill —
    salta exactamente los bloques de skip_set (sorteados al azar entre los
    elegibles, tasa matcheada a la del tratamiento en esta réplica).
    En los bloques saltados juega el brazo de la skill (igual que el
    tratamiento): el azar elige QUÉ bloques, no QUÉ brazo.
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
    saltados_det = []

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
            # ÚNICO MOVING PART respecto al tratamiento: sorteo al azar
            # (tasa matcheada) en vez de umbral de soporte de la skill.
            saltar = b in skip_set

        clf = e47.MockClasificador(tasas)
        for hh in range(base):
            clf.registrar(items[hh])

        if saltar:
            # PROBE SALTADO: se juega el brazo de la skill en los 10 items.
            # Sin bandit, sin probe Q1/Q2. Contabilidad honesta: cuesta 0.
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
            # Diagnóstico ex post (contrafactual con RNG común; la política
            # no lo usa para decidir). Definición de misfire IDÉNTICA a
            # EXP47/48/49.
            acc = {a: sum(rew_fija[a][base:base + e47.BLOQUE]) / e47.BLOQUE
                   for a in brazos}
            mejor = max(brazos, key=lambda a: acc[a])
            saltados_det.append({
                "bloque": b, "firma": sig, "brazo_skill": skill_arm,
                "sorteo_aleatorio": True,
                "acc_skill": round(acc[skill_arm], 4),
                "mejor_expost": mejor, "acc_mejor": round(acc[mejor], 4),
                "misfire": bool(mejor != skill_arm),
            })
            reg_pol_bloques.append(
                e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))
            diag.append({
                "bloque": b, "regimen": items[base]["regimen"], "firma": sig,
                "probe_saltado": True, "sorteo_aleatorio": True,
                "brazo_skill": skill_arm,
                "acc_pol": round(
                    sum(rew_pol[base:base + e47.BLOQUE]) / e47.BLOQUE, 4),
                "acc_fijas": {
                    a: round(sum(rew_fija[a][base:base + e47.BLOQUE]) /
                             e47.BLOQUE, 4)
                    for a in brazos},
            })
            continue

        # --- Camino con probe: idéntico al tratamiento de EXP49 ---
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

        # PROBE Q1: mide todos los brazos; scoring honesto con fav ciego
        rs_q1 = {}
        for q in e47.PROBE_Q1:
            h = base + q
            rs_q1[q] = medir(q, "q1")
            rew_pol[h] = rs_q1[q][fav]

        usa_skill = False
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            usa_skill = True
            skills_usadas += 1
            # Reconstruye el prior condicionado a la firma (skill) y
            # re-aplica las updates del probe Q1 (sin re-sortear).
            bandit = e47.nuevo_bandit(
                brazos, e47.prior_params(brazos, rep_hist, block_sig, b, sig))
            for q in e47.PROBE_Q1:
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
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a_sel}"))
                bandit.update(a_sel, r_sel)
                rep_hist[a_sel].append((h, r_sel, b))
                rew_pol[h] = r_sel
                for a in brazos:
                    rew_fija[a][h] = clf.acierto(
                        a, it, random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                clf.registrar(it)

        thompson(tuple(q for q in e47.THOMPSON_Q if q < e47.PROBE_Q2[0]))
        # RE-PROBE Q2: scoring honesto con fav ciego en AMBAS políticas
        rs_q2 = {}
        for q in e47.PROBE_Q2:
            h = base + q
            rs_q2[q] = medir(q, "q2")
            rew_pol[h] = rs_q2[q][fav]
        thompson(tuple(q for q in e47.THOMPSON_Q if q > e47.PROBE_Q2[-1]))

        probe_obs[b] = {a: [rs_q1[q][a] for q in e47.PROBE_Q1] +
                           [rs_q2[q][a] for q in e47.PROBE_Q2]
                        for a in brazos}
        reg_pol_bloques.append(
            e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))

        diag.append({
            "bloque": b, "regimen": items[base]["regimen"], "firma": sig,
            "probe_saltado": False, "sorteo_aleatorio": False,
            "skill_usada": usa_skill,
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
    return {"politica": "skip-aleatorio", "reg_pol": reg_pol,
            "reg_pol_bloques": reg_pol_bloques,
            "reg_fijas": reg_fijas,
            "mejor_fija": mejor, "reg_mejor_fija": reg_fijas[mejor],
            "skills_usadas": skills_usadas, "probes_saltados": probes_saltados,
            "saltados_det": saltados_det, "n_bloques": n_bloques,
            "skip_set": skip_set,
            "diag": diag, "n": H}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--replicas", type=int, default=e47.N_REPLICAS)
    args = ap.parse_args()
    t0 = time.time()

    out = args.out or os.path.join(BASE, "resultados", "exp50-20260927")
    os.makedirs(out, exist_ok=True)

    items = e47.construir_stream()  # bit-idéntico al stream de EXP47/48/49
    H = len(items)
    n_bloques = H // e47.BLOQUE
    elegibles, sigs = bloques_elegibles(items)
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))

    # --- pre-registro ANTES de correr ---
    prereg = {
        "experimento": "ALMA-EXP50: el mock dirimente de la línea de skills "
                       "(EXP45→49) — ¿el efecto viene de elegir bien los "
                       "saltos o de saltar menos?",
        "fase": "mock",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "hipotesis": "Si el efecto medio de EXP49 (-1,80) viene de ELEGIR "
                     "BIEN los saltos (la skill selecciona bloques donde el "
                     "brazo de la skill es realmente el mejor), entonces un "
                     "control que salta la misma cantidad de bloques pero "
                     "elegidos al azar entre los elegibles tiene más "
                     "misfires y peor regret: media sobre réplicas pareadas "
                     "de regret(tratamiento) - regret(azar) <= -1.0 "
                     "(CONTINÚA). Si el efecto viene simplemente de SALTAR "
                     "MENOS (abstención), el azar empata: |media| < 1.0 "
                     "(CIERRE: el valor estaba en saltar menos, no en la "
                     "maquinaria de skills).",
        "nota_refutacion": "El control skip-aleatorio es un adversario "
                           "generoso con la skill: elige entre bloques "
                           "elegibles (la skill existe: misma "
                           "firma-disponibilidad) y en los bloques saltados "
                           "juega el brazo de la skill — el azar decide QUÉ "
                           "bloques, no QUÉ brazo. Si ni así la skill supera "
                           "al azar con margen, la selectividad no aporta "
                           "nada que la abstención no aporte. Nota: la "
                           "pregunta dirime el ORIGEN del efecto de EXP49; "
                           "no re-abre el diagnóstico estructural (ambas "
                           "políticas siguen medidas contra la mejor fija).",
        "condicion_alcance": e47.CONDICION_ALCANCE,
        "stream": {
            "fuente": "IDÉNTICO al de EXP47/48/49 (misma función "
                      "run_experiment47.construir_stream, bit-idéntico): 240 "
                      "items, 24 bloques x 10, 3 regímenes x 8 recurrencias, "
                      "seeds 45/47, namespace de RNG del oráculo 'exp45-...'.",
            "n_items": H, "bloques": n_bloques,
            "tam_bloque": e47.BLOQUE,
            "regimenes": e47.REGIMENES,
            "oraculo": "tasas mock calibradas por categoría "
                       "(data_exp44/tasas.json)",
            "sesgo_seleccion": e47.SESGO_SELECCION,
            "bloques_elegibles": elegibles,
            "n_elegibles": len(elegibles),
        },
        "politicas": {
            "tratamiento": "El skip-endurecido de EXP49 VERBATIM (misma "
                           "función run_experiment49.correr_replica_"
                           "endurecido, importada sin copiar): skills "
                           "condicionan el prior; con soporte fuerte bajo "
                           "umbral endurecido umbral(K) = 2 + floor(K/3) se "
                           "salta el probe y se juega el brazo de la skill.",
            "skip-aleatorio": "COPIA VERBATIM del tratamiento, salvo UN "
                "moving part: la decisión de salto no usa el soporte de la "
                "skill. Por réplica r, salta exactamente N_t(r) bloques — la "
                "misma cantidad que el tratamiento saltó en esa réplica — "
                "elegidos al azar (sin reposición) entre los bloques "
                "elegibles (la skill existe: misma firma-disponibilidad). "
                "En los bloques saltados juega el brazo de la skill con la "
                "misma contabilidad honesta y el mismo diagnóstico ex post "
                "de misfires (definición idéntica a EXP47/48/49). En los no "
                "saltados sigue el camino con probe idéntico. Sorteo con "
                "random.Random('exp50-r{rep}-randomskip'): namespace propio, "
                "no toca el oráculo ni el bandit.",
        },
        "mecanismo_skill": {
            "elegibilidad": "bloque b es elegible ssi existe un bloque "
                            "pasado con la misma firma (política-"
                            "independiente: block_sig es determinista del "
                            "stream y todo bloque agrega entradas a "
                            "rep_hist en cualquier política)",
            "misfire_definicion": "IDÉNTICA a EXP47/48/49: en un bloque "
                "saltado, el brazo de la skill no es el mejor ex post "
                "(accuracy sobre los 10 items con RNG común, "
                "contrafactual). Tasa = misfires / skips.",
        },
        "rng": "namespace del oráculo idéntico a EXP45-49 "
               "('exp45-r{rep}-b{b}-q{q}-{a}'). Tratamiento y control ven el "
               "mismo oráculo. Pareado por réplica. Sorteo de bloques del "
               "control en namespace separado 'exp50-r{rep}-randomskip'.",
        "criterio": {
            "efecto": "regret(tratamiento) - regret(skip-aleatorio) sobre "
                      "24 bloques, media sobre réplicas (pareadas, RNG "
                      "común)",
            "umbral_empate": UMBRAL_EMPATE,
            "justificacion_umbral": "UMBRAL_EMPATE = 1.0 ≈ 1 error estándar "
                "de la media entre réplicas observado en EXP49: efectos por "
                "réplica +0.00, +1.00, -4.00, -5.00, -1.00 → sd muestral "
                "2.55 → SE = 2.55/sqrt(5) ≈ 1.14. '|media| < 1.0' = 'dentro "
                "del ruido entre réplicas'. Fijado ANTES de correr EXP50, "
                "derivado solo de EXP49.",
            "empate": f"|media(efecto)| < {UMBRAL_EMPATE} → la selectividad "
                      "aleatoria empata con la skill → CIERRE de la línea: "
                      "el valor estaba en saltar menos, no en la maquinaria "
                      "de skills",
            "gana_skill": f"media(efecto) <= -{UMBRAL_EMPATE} → la skill "
                          "supera al azar con margen → CONTINÚA: la "
                          "selectividad aporta valor real",
            "gana_azar": f"media(efecto) >= +{UMBRAL_EMPATE} → el azar "
                         "supera a la skill con margen → CIERRE: la "
                         "selectividad no aporta (o es contraproducente)",
            "regiones": "exhaustivas y mutuamente excluyentes; el dictamen "
                        "no tiene ambigüedad",
            "diagnostico_auxiliar": "tasa de misfires del control "
                "skip-aleatorio vs la del tratamiento (2/14 = 0.143 en "
                "EXP49): si la skill elige bien, el azar debe tener más "
                "misfires; tasa de saltos matcheada por construcción "
                "(verificación); reproducibilidad bit-idéntica del "
                "tratamiento vs EXP49; efecto sin la mejor réplica "
                "(distribución); distancia de ambas políticas a la mejor "
                "fija.",
        },
        "replicas": args.replicas,
        "modo": "mock, US$0",
    }
    with open(os.path.join(out, "preregistro.json"), "w",
              encoding="utf-8") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito ({H} items, {n_bloques} bloques, "
          f"{args.replicas} réplicas pareadas, {len(elegibles)} elegibles).")

    efectos, det = [], []
    for r in range(args.replicas):
        trt = e49.correr_replica_endurecido(r, items, tasas)
        n_t = trt["probes_saltados"]
        skip_set = sorteo_aleatorio(r, elegibles, n_t)
        rnd = correr_replica_random(r, items, tasas, skip_set)
        assert rnd["probes_saltados"] == n_t, (
            f"réplica {r}: el control debía saltar {n_t}, saltó "
            f"{rnd['probes_saltados']}")
        ef = trt["reg_pol"] - rnd["reg_pol"]
        efectos.append(ef)
        mis_t = sum(1 for s in trt["saltados_det"] if s["misfire"])
        mis_r = sum(1 for s in rnd["saltados_det"] if s["misfire"])
        det.append({
            "replica": r,
            "efecto": round(ef, 3),
            "reg_tratamiento": round(trt["reg_pol"], 3),
            "reg_azar": round(rnd["reg_pol"], 3),
            "reg_trat_bloques": [round(x, 3)
                                 for x in trt["reg_pol_bloques"]],
            "reg_azar_bloques": [round(x, 3)
                                 for x in rnd["reg_pol_bloques"]],
            "reg_mejor_fija": round(trt["reg_mejor_fija"], 3),
            "mejor_fija": trt["mejor_fija"],
            "skips_tratamiento": trt["probes_saltados"],
            "misfires_tratamiento": mis_t,
            "tasa_misfire_tratamiento": round(
                mis_t / trt["probes_saltados"], 4)
            if trt["probes_saltados"] else None,
            "skips_azar": rnd["probes_saltados"],
            "skip_set_azar": skip_set,
            "misfires_azar": mis_r,
            "tasa_misfire_azar": round(
                mis_r / rnd["probes_saltados"], 4)
            if rnd["probes_saltados"] else None,
        })
        if r == 0:
            diag_rep0 = {"tratamiento": trt["diag"],
                         "azar": rnd["diag"]}
            salt_rep0 = {"tratamiento": trt["saltados_det"],
                         "azar": rnd["saltados_det"]}

    n = len(efectos)
    media_ef = sum(efectos) / n
    mejor = min(efectos)
    media_sin_mejor = (sum(efectos) - mejor) / (n - 1)
    cargado_una_replica = bool(media_sin_mejor >= 0)

    n_skips_t = sum(d["skips_tratamiento"] for d in det)
    n_mis_t = sum(d["misfires_tratamiento"] for d in det)
    tasa_t = n_mis_t / n_skips_t if n_skips_t else None
    n_skips_r = sum(d["skips_azar"] for d in det)
    n_mis_r = sum(d["misfires_azar"] for d in det)
    tasa_r = n_mis_r / n_skips_r if n_skips_r else None

    empate = bool(abs(media_ef) < UMBRAL_EMPATE)
    gana_skill = bool(media_ef <= -UMBRAL_EMPATE)
    gana_azar = bool(media_ef >= UMBRAL_EMPATE)
    dictamen = "CONTINÚA" if gana_skill else "CIERRE"

    # --- chequeo de reproducibilidad: el tratamiento debe ser bit-idéntico
    # al skip-endurecido de EXP49 (misma función, mismo stream) ---
    repro_ok = None
    try:
        rep49 = json.load(open(EXP49_REPORT, encoding="utf-8"))
        d49 = {d["replica"]: (d["reg_trat_bloques"], d["skips_tratamiento"])
               for d in rep49["detalle_replicas"]}
        repro_ok = all(
            [round(x, 3) for x in det[r]["reg_trat_bloques"]] ==
            [round(x, 3) for x in d49[r][0]] and
            det[r]["skips_tratamiento"] == d49[r][1]
            for r in range(args.replicas))
    except Exception as e:  # noqa: BLE001
        repro_ok = f"no verificable: {e}"

    motivos = [
        f"items={H}, bloques={n_bloques} (3 regímenes x 8 recurrencias), "
        f"réplicas pareadas={args.replicas} (RNG común, oráculo idéntico), "
        f"bloques elegibles={len(elegibles)}",
        f"efecto medio (reg_trat - reg_azar) = {media_ef:+.3f} "
        f"(por réplica: {', '.join(f'{e:+.2f}' for e in efectos)})",
        f"umbral de empate pre-registrado: ±{UMBRAL_EMPATE} "
        f"(≈1 SE del ruido entre réplicas de EXP49)",
        f"misfires tratamiento: {n_mis_t}/{n_skips_t} "
        f"(tasa {tasa_t:.3f}) vs skip-aleatorio: {n_mis_r}/{n_skips_r} "
        f"(tasa {tasa_r:.3f})"
        if tasa_t is not None and tasa_r is not None
        else "sin skips en alguna política: tasas no comparables",
        f"tasa de saltos matcheada por réplica (verificación): "
        f"{[(d['skips_tratamiento'], d['skips_azar']) for d in det]}",
        f"regret medio tratamiento: "
        f"{sum(d['reg_tratamiento'] for d in det) / len(det):.2f} | "
        f"skip-aleatorio: "
        f"{sum(d['reg_azar'] for d in det) / len(det):.2f} | "
        f"mejor fija: "
        f"{sum(d['reg_mejor_fija'] for d in det) / len(det):.2f}",
        f"media del efecto sin la mejor réplica: {media_sin_mejor:+.2f} "
        f"(¿cargado por una sola réplica? {'SÍ' if cargado_una_replica else 'NO'})",
        f"EMPATE (|media| < {UMBRAL_EMPATE}): {'SÍ' if empate else 'NO'} | "
        f"GANA SKILL (media <= -{UMBRAL_EMPATE}): "
        f"{'SÍ' if gana_skill else 'NO'} | "
        f"GANA AZAR (media >= +{UMBRAL_EMPATE}): "
        f"{'SÍ' if gana_azar else 'NO'} → DICTAMEN: {dictamen} DE LA LÍNEA",
        f"reproducibilidad del tratamiento vs EXP49 (bit-idéntico): "
        f"{repro_ok}",
    ]
    report = {
        "preregistro": "preregistro.json (mismo directorio)",
        "n_items": H, "n_bloques": n_bloques,
        "bloques_elegibles": elegibles,
        "detalle_replicas": det,
        "efecto_medio": round(media_ef, 3),
        "efecto_por_replica": [round(e, 3) for e in efectos],
        "media_efecto_sin_mejor_replica": round(media_sin_mejor, 3),
        "cargado_por_una_sola_replica": cargado_una_replica,
        "tasa_misfire_tratamiento": round(tasa_t, 4)
        if tasa_t is not None else None,
        "tasa_misfire_azar": round(tasa_r, 4)
        if tasa_r is not None else None,
        "umbral_empate": UMBRAL_EMPATE,
        "saltados_det_rep0": salt_rep0,
        "diagnostico_bloques_rep0": diag_rep0,
        "reproducibilidad_exp49": repro_ok,
        "costo_total_usd": 0.0,
        "veredicto": {
            "empate": empate, "gana_skill": gana_skill,
            "gana_azar": gana_azar, "dictamen": dictamen,
            "criterio": prereg["criterio"], "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP50 ================")
    for m in motivos:
        print("  " + m)
    print("  costo: $0.0000 USD (mock) | "
          f"{report['duracion_s']}s")
    print(f"  RESULTADO: {dictamen} DE LA LÍNEA DE SKILLS "
          f"(efecto medio {media_ef:+.3f})")
    print("==================================================")
    return 0 if gana_skill else 1


if __name__ == "__main__":
    sys.exit(main())
