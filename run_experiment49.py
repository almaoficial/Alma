#!/usr/bin/env python3
"""ALMA-EXP49: umbral de soporte que se endurece con el horizonte (mock, US$0).

ÚLTIMO MOCK de la línea de skills (EXP45→48), con criterio de CIERRE
pre-registrado. Prueba la variante (b) descartada en EXP48: a más
recurrencias/bloques vistos por la firma, más victorias de soporte exige la
skill para disparar el skip del probe.

- Control: el tratamiento "skip" de EXP47 VERBATIM (misma función
  run_experiment47.correr_replica con politica="skip", importada), mismo
  stream de 24 bloques bit-idéntico, réplicas pareadas con RNG común.
- Tratamiento ("skip-endurecido"): idéntico al control, salvo que el umbral
  de soporte se endurece con K = nº de bloques pasados no-saltados con la
  misma firma que aportaron comparación pareada:
      umbral(K) = 2 + floor(K/3)
  (K=0,1,2 → 2, idéntico al control; K=3,4,5 → 3; K=6,7 → 4).
  Un solo moving part respecto al control: el umbral de soporte.

Criterio PRE-REGISTRADO:
  pasa_1: media sobre réplicas pareadas de regret(trat)-regret(ctrl) < 0
  pasa_2: tasa de misfires del tratamiento < 0.30 (con n_skips_trat > 0)
  PASS ssi pasa_1 Y pasa_2. Definición operativa de misfire idéntica a EXP47.

CRITERIO DE CIERRE DE LA LÍNEA (pre-registrado): la línea de skills se
CIERRA ssi se cumplen las tres a la vez:
  (c1) efecto medio >= -1.5   (no hay efecto fuerte)
  (c2) tasa de misfires del tratamiento >= 0.30 (o sin skips: no evaluable)
  (c3) el efecto sigue cargado por una sola réplica:
       sin la mejor réplica (la más negativa), la media sería >= 0
Si la línea se cierra: el techo es del mundo, no del mecanismo.

Uso:
    python3 run_experiment49.py [--out DIR] [--replicas N]
"""

import argparse
import json
import os
import random
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_experiment47 as e47  # noqa: E402  (control verbatim + maquinaria)

BASE = os.path.dirname(os.path.abspath(__file__))
EXP47_REPORT = os.path.join(BASE, "resultados", "exp47-20260927",
                            "report.json")

TASA_MISFIRE_OBJETIVO = 0.30   # la vara que EXP48 no alcanzó (0.333)
EFECTO_FUERTE = -1.5           # vara de cierre (más exigente que PASS < 0)


def umbral_endurecido(K):
    """Umbral de soporte que se endurece con el horizonte (variante (b)).

    K = nº de bloques pasados no-saltados con la misma firma que aportaron
    comparación pareada (el denominador de la evidencia de la skill).
    Regla pre-registrada: 2 + floor(K/3).
      K=0,1,2 → 2 (idéntico al control: temprano no cambia nada)
      K=3,4,5 → 3
      K=6,7   → 4 (tardío: solo skills con evidencia sostenida saltan)
    """
    return 2 + K // 3


def soporte_endurecido(brazos, probe_obs, block_sig, b, sig, skill_arm):
    """Conteo de victorias idéntico a e47.soporte_fuerte; el umbral se
    endurece con K. Retorna (fuerte, wins, K, umbral)."""
    wins = 0
    K = 0
    for b2 in range(b):
        if block_sig.get(b2) != sig:
            continue
        obs = probe_obs.get(b2)
        if not obs:
            continue  # bloque saltado: sin comparación pareada
        K += 1
        m_s = sum(obs[skill_arm]) / len(obs[skill_arm])
        if all(m_s > sum(obs[a]) / len(obs[a])
               for a in brazos if a != skill_arm):
            wins += 1
    umbral = umbral_endurecido(K)
    return wins >= umbral, wins, K, umbral


def correr_replica_endurecido(rep_id, items, tasas):
    """Tratamiento skip-endurecido de EXP49.

    COPIA VERBATIM del camino "skip" de e47.correr_replica (misma lógica,
    mismos seeds de RNG, mismo orden de sorteos). El ÚNICO moving part:
    soporte_fuerte (umbral fijo 2) → soporte_endurecido (umbral 2+floor(K/3)).
    El diagnóstico ex post de misfires es idéntico al de EXP47.
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
        wins = 0
        K = None
        umbral = None
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            skill_arm = e47.skill_arm_actual(brazos, rep_hist, block_sig,
                                             b, sig)
            # ÚNICO MOVING PART respecto al control:
            fuerte, wins, K, umbral = soporte_endurecido(
                brazos, probe_obs, block_sig, b, sig, skill_arm)
            saltar = fuerte

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
            # no lo usa para decidir).
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

        # --- Camino con probe: idéntico al tratamiento de EXP45/46/47 ---
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
            "probe_saltado": False, "soporte_wins": wins,
            "K_oportunidades": K, "umbral_exigido": umbral,
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
    return {"politica": "skip-endurecido", "reg_pol": reg_pol,
            "reg_pol_bloques": reg_pol_bloques,
            "reg_fijas": reg_fijas,
            "mejor_fija": mejor, "reg_mejor_fija": reg_fijas[mejor],
            "skills_usadas": skills_usadas, "probes_saltados": probes_saltados,
            "saltados_det": saltados_det, "n_bloques": n_bloques,
            "diag": diag, "n": H}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--replicas", type=int, default=e47.N_REPLICAS)
    args = ap.parse_args()
    t0 = time.time()

    out = args.out or os.path.join(BASE, "resultados", "exp49-20260927")
    os.makedirs(out, exist_ok=True)

    items = e47.construir_stream()  # bit-idéntico al stream de EXP47/48
    H = len(items)
    n_bloques = H // e47.BLOQUE
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))

    # --- pre-registro ANTES de correr ---
    prereg = {
        "experimento": "ALMA-EXP49: umbral de soporte que se endurece con el "
                       "horizonte — ÚLTIMO mock de la línea de skills "
                       "(EXP45→48), con criterio de CIERRE pre-registrado",
        "fase": "mock",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "hipotesis": "(1) Endurecer el umbral de soporte con el horizonte "
                     "baja la tasa de misfires del skip por debajo del 30% "
                     "(EXP47: 14/38 ≈ 37%; EXP48: 9/27 ≈ 33%), porque las "
                     "victorias ruidosas ya no alcanzan para disparar el "
                     "salto cuando la firma acumuló muchas oportunidades de "
                     "comparación. (2) El tratamiento reduce el regret "
                     "frente al skip de umbral fijo: media sobre réplicas "
                     "pareadas de regret(skip-endurecido) - regret(skip) < 0.",
        "variante_elegida": "(b) umbral endurecido con el horizonte "
                            "(descartada en EXP48 a favor de la "
                            "re-validación barata). Regla pre-registrada: "
                            "umbral(K) = 2 + floor(K/3), con K = nº de "
                            "bloques pasados no-saltados con la misma firma "
                            "que aportaron comparación pareada. Un solo "
                            "moving part respecto al control: el umbral.",
        "nota_refutacion": "El endurecimiento ataca las victorias ruidosas, "
                           "no la staleness (el brazo deja de matchear el "
                           "bloque actual): advertencia ya registrada en "
                           "EXP48. Si los misfires no bajan del 30% o el "
                           "efecto no aparece, el problema no era el umbral "
                           "fijo: era la calidad de la evidencia (firmas "
                           "ruidosas con 2/10 de ruido por bloque) o la "
                           "staleness. En ese caso la línea se cierra: el "
                           "techo es del mundo, no del mecanismo.",
        "regla_cierre_linea": "La línea de skills se CIERRA ssi se cumplen "
            "las tres condiciones a la vez: (c1) efecto medio "
            f"(reg_trat - reg_ctrl) >= {EFECTO_FUERTE}; (c2) tasa de misfires "
            f"del tratamiento >= {TASA_MISFIRE_OBJETIVO} (o sin skips: no "
            "evaluable → cuenta como no-bajada); (c3) el efecto sigue "
            "cargado por una sola réplica, i.e. sin la mejor réplica (la más "
            "negativa) la media del efecto sería >= 0. La vara de cierre "
            "(-1.5) es deliberadamente más exigente que la de PASS (< 0): "
            "un PASS débil con misfires altos y fragilidad entre réplicas "
            "no justifica seguir puliendo el gate; solo un efecto fuerte, "
            "o misfires bajos, o un efecto distribuido entre réplicas "
            "mantienen la línea abierta.",
        "condicion_alcance": e47.CONDICION_ALCANCE,
        "stream": {
            "fuente": "IDÉNTICO al de EXP47/48 (misma función "
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
                       "politica='skip', importada sin copiar): skills "
                       "condicionan el prior; con soporte fuerte (umbral "
                       "fijo >= 2 victorias) se salta el probe y se juega "
                       "el brazo de la skill en los 10 items.",
            "skip-endurecido": "Idéntica al control, salvo el umbral de "
                "soporte: umbral(K) = 2 + floor(K/3), con K = nº de bloques "
                "pasados no-saltados con la misma firma que aportaron "
                "comparación pareada. K=0,1,2 → 2 (idéntico al control); "
                "K=3,4,5 → 3; K=6,7 → 4. Todo lo demás (firma, skill_arm, "
                "conteo de victorias, definición de misfire, diagnóstico ex "
                "post, seeds de RNG, contabilidad honesta del probe "
                "saltado) es idéntico al control.",
        },
        "mecanismo_skill": {
            "firma": "idéntica a EXP47 (grupo mayoritario de los primeros 3 "
                     "items del bloque)",
            "skill_arm": "idéntico a EXP47 (argmax de la media del prior "
                         "condicionado a la firma, warm olvido 0.5^d)",
            "soporte": "conteo de victorias idéntico a EXP47 (>=2 victorias "
                       "pareadas del skill_arm en bloques pasados "
                       "no-saltados con la misma firma; victoria = media en "
                       "los 5 items de probe estrictamente mayor que cada "
                       "otro brazo); el UMBRAL se endurece: 2 + floor(K/3)",
            "misfire_definicion": "IDÉNTICA a EXP47: en un bloque saltado, "
                "el brazo de la skill no es el mejor ex post (accuracy "
                "sobre los 10 items con RNG común, contrafactual). Tasa de "
                "misfires = misfires / skips.",
            "bloque_saltado": "idéntico a EXP47 (sin probe Q1/Q2 ni bandit; "
                              "rewards observados agregados a la skill; no "
                              "aporta comparación pareada)",
        },
        "rng": "namespace del oráculo idéntico a EXP45/46/47/48 "
               "('exp45-r{rep}-b{b}-q{q}-{a}'). Control y tratamiento ven "
               "el mismo oráculo. Pareado por réplica.",
        "criterio": {
            "efecto": "regret(skip-endurecido) - regret(skip) sobre 24 "
                      "bloques, media sobre réplicas (pareadas, RNG común)",
            "pasa_1": "media(efecto) < 0  [misma vara que EXP46/47/48]",
            "pasa_2": f"tasa_misfires_tratamiento < {TASA_MISFIRE_OBJETIVO} "
                      "con n_skips_tratamiento > 0 [la vara que EXP48 no "
                      "alcanzó: 0.333]",
            "pass": "pasa_1 Y pasa_2",
            "cierre_linea": "cierra ssi (c1) media(efecto) >= -1.5 Y (c2) "
                "tasa_misfires_trat >= 0.30 (o sin skips) Y (c3) sin la "
                "mejor réplica la media del efecto sería >= 0 "
                "[regla pre-registrada: ver regla_cierre_linea]",
            "diagnostico_auxiliar": "tasa de misfires del control (debe "
                "reproducir ~37% de EXP47 — chequeo de sanidad); "
                "reproducibilidad bit-idéntica del control vs EXP47; "
                "distribución de skips por umbral exigido (¿el "
                "endurecimiento muerde?); efecto sin la mejor réplica; "
                "distancia a la mejor fija.",
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
        trt = correr_replica_endurecido(r, items, tasas)
        ef = trt["reg_pol"] - ctrl["reg_pol"]
        efectos.append(ef)
        mis_c = sum(1 for s in ctrl["saltados_det"] if s["misfire"])
        mis_t = sum(1 for s in trt["saltados_det"] if s["misfire"])
        umbrales = Counter(s["umbral_exigido"] for s in trt["saltados_det"])
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
            "skips_trat_por_umbral": {str(k): umbrales[k]
                                      for k in sorted(umbrales)},
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
    skips_por_umbral = Counter()
    for d in det:
        for k, v in d["skips_trat_por_umbral"].items():
            skips_por_umbral[int(k)] += v

    n_skips_t = sum(d["skips_tratamiento"] for d in det)
    n_mis_t = sum(d["misfires_tratamiento"] for d in det)
    tasa_t = n_mis_t / n_skips_t if n_skips_t else None
    n_skips_c = sum(d["skips_control"] for d in det)
    n_mis_c = sum(d["misfires_control"] for d in det)
    tasa_c = n_mis_c / n_skips_c if n_skips_c else None

    pasa_1 = bool(media_ef < 0)
    pasa_2 = bool(n_skips_t > 0 and tasa_t < TASA_MISFIRE_OBJETIVO)
    pasa = pasa_1 and pasa_2

    # --- criterio de CIERRE (pre-registrado) ---
    c1 = bool(media_ef >= EFECTO_FUERTE)
    c2 = bool(tasa_t is None or tasa_t >= TASA_MISFIRE_OBJETIVO)
    c3 = cargado_una_replica
    cierra = bool(c1 and c2 and c3)

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
        f"(tasa {tasa_t:.3f}) vs objetivo < {TASA_MISFIRE_OBJETIVO} "
        f"(EXP47: 14/38 ≈ 0.368; EXP48: 9/27 ≈ 0.333)"
        if tasa_t is not None
        else "tratamiento sin skips: pasa_2 no evaluable",
        f"misfires control (sanidad, debe dar ~37%): {n_mis_c}/{n_skips_c} "
        f"(tasa {tasa_c:.3f})" if tasa_c is not None else "control sin skips",
        f"skips del tratamiento por umbral exigido: "
        f"{dict(sorted(skips_por_umbral.items()))} "
        f"(¿el endurecimiento muerde en el segmento tardío?)",
        f"(1) media(efecto) < 0: {'SÍ' if pasa_1 else 'NO'} | "
        f"(2) misfires < 30%: {'SÍ' if pasa_2 else 'NO'}",
        f"cierre: (c1) efecto >= -1.5: {'SÍ' if c1 else 'NO'} | "
        f"(c2) misfires >= 30%: {'SÍ' if c2 else 'NO'} | "
        f"(c3) cargado por una sola réplica "
        f"(media sin la mejor = {media_sin_mejor:+.2f}): "
        f"{'SÍ' if c3 else 'NO'} → "
        f"{'CIERRE DE LA LÍNEA' if cierra else 'la línea sigue abierta'}",
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
        "efecto_por_replica": [round(e, 3) for e in efectos],
        "media_efecto_sin_mejor_replica": round(media_sin_mejor, 3),
        "cargado_por_una_sola_replica": cargado_una_replica,
        "tasa_misfire_tratamiento": round(tasa_t, 4)
        if tasa_t is not None else None,
        "tasa_misfire_control": round(tasa_c, 4)
        if tasa_c is not None else None,
        "tasa_misfire_objetivo": TASA_MISFIRE_OBJETIVO,
        "skips_tratamiento_por_umbral": {str(k): skips_por_umbral[k]
                                        for k in sorted(skips_por_umbral)},
        "saltados_det_rep0": salt_rep0,
        "diagnostico_bloques_rep0": diag_rep0,
        "reproducibilidad_exp47": repro_ok,
        "costo_total_usd": 0.0,
        "veredicto": {
            "pasa_1_efecto": pasa_1, "pasa_2_misfires": pasa_2,
            "pass": pasa,
            "cierre": {"c1_efecto_debil": c1,
                       "c2_misfires_altos": c2,
                       "c3_una_replica": c3,
                       "cierra_linea_skills": cierra},
            "criterio": prereg["criterio"], "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP49 ================")
    for m in motivos:
        print("  " + m)
    print("  costo: $0.0000 USD (mock) | "
          f"{report['duracion_s']}s")
    print("  RESULTADO:",
          "PASS" if pasa else "FAIL",
          "+",
          "CIERRE DE LÍNEA" if cierra else "LÍNEA ABIERTA")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
