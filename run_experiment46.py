#!/usr/bin/env python3
"""ALMA-EXP46: skills que reducen el COSTO DEL PROBE (mock, US$0).

Recomendación del veredicto de EXP45: el costo estructural está en el probe
(5 items/bloque con scoring ciego); las skills de EXP45 mejoraban el Thompson
pero no tocaban ese costo. Acá la skill, cuando tiene soporte fuerte, SALTA
el probe y juega directo su brazo.

Diseño A/B pareado (único moving part):
- Control: el tratamiento de EXP45 (skills condicionan el prior de Thompson;
  probe Q1 + re-probe Q2 siempre). Bit-idéntico al tratamiento de EXP45
  (mismos strings de seed del oráculo, mismo stream seed 45, mismo código)
  → se verifica reproducibilidad contra resultados/exp45-20260927/report.json.
- Tratamiento ("skip"): idéntico al control, salvo que si la skill de la
  firma del bloque tiene soporte fuerte (>=2 victorias pareadas pasadas),
  se salta el probe (Q1 y Q2) y se juega el brazo de la skill en los 10 items.
  Contabilidad honesta: el probe saltado cuesta 0.

Firma: grupo mayoritario entre los grupos de los primeros 3 items del bloque
(observación gratuita; en EXP45 salía de los mismos 3 items del probe Q1).

Soporte fuerte (pre-registrado): skill_arm = argmax de la media con olvido
0.5^d sobre la historia de la skill; "victoria" en un bloque pasado con la
misma firma = media del skill_arm en los 5 items de probe (Q1+Q2,
full-information, pareado) estrictamente mayor que la de cada otro brazo
(margen implícito >= 0.2). Soporte fuerte = >= 2 victorias en bloques
pasados no-saltados con la misma firma.

Stream: idéntico a EXP45 (seed 45, 120 items, 12 bloques, 3 regímenes x 4
recurrencias). RNG común por (réplica, bloque, item, brazo).

Criterio PRE-REGISTRADO: media sobre 5 réplicas pareadas de
    regret(skip) - regret(control)  <  0   → PASS

Condición de alcance (pre-registrada): en mundos sin recurrencia (feed real:
rotación 8/8 en EXP44) las skills nunca alcanzan soporte fuerte — el
mecanismo solo opera donde hay recurrencia.

Uso:
    python3 run_experiment46.py [--out DIR] [--replicas N]
"""

import argparse
import json
import os
import random
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alma.selector import BanditPorClase  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
FEED = os.path.join(BASE, "data_exp44", "feed_units.json")
TASAS_PATH = os.path.join(BASE, "data_exp44", "tasas.json")
EXP45_REPORT = os.path.join(BASE, "resultados", "exp45-20260927",
                            "report.json")

BLOQUE = 10
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (6, 7)
THOMPSON_Q = tuple(q for q in range(BLOQUE)
                   if q not in PROBE_Q1 + PROBE_Q2)
assert len(THOMPSON_Q) == 5
N_REPLICAS = 5
N0 = 2
DECAY = 0.5
SEED_STREAM = 45
SOPORTE_MINIMO_VICTORIAS = 2

GRUPOS = {
    "tech": ["adaptive systems", "agentes de ia", "agentes ia", "ai agents",
             "ai industry", "ai models", "ai platforms", "ai research",
             "auto-mejora de ia", "ia investigación", "ia que se mejora sola",
             "inteligencia artificial", "investigación en ia", "modelos de ia",
             "self-improving ai", "sistemas adaptativos"],
    "dinero": ["dinero con ia", "finances", "finanzas", "ingresos con ia",
               "negocios"],
    "deportes": ["fútbol", "fútbol amateur", "mundial 2026"],
}
GRUPO_DE = {c: g for g, cs in GRUPOS.items() for c in cs}
REGIMENES = ["dinero", "tech", "deportes", "deportes", "tech", "deportes",
             "tech", "tech", "deportes", "dinero", "dinero", "dinero"]
# orden generado con random.Random(45).shuffle sobre 4x cada régimen

SESGO_SELECCION = (
    "Stream CONSTRUIDO (no es el feed crudo): las categorías se sortean con "
    "las frecuencias empíricas del feed real de Muse (22-27/9/2026), pero la "
    "secuencia de regímenes está diseñada (3 regímenes x 4 recurrencias). "
    "Es el mundo mínimo donde una skill PUEDE ayudar: sin recurrencia, el "
    "mecanismo es intestable por definición (lección EXP44: rotación 8/8 "
    "mata cualquier aprendizaje)."
)

CONDICION_ALCANCE = (
    "En mundos sin recurrencia (feed real: rotación 8/8 en EXP44) las skills "
    "nunca alcanzan soporte fuerte (>=2 victorias pareadas): el mecanismo de "
    "salto de probe solo opera donde hay recurrencia. No generalizar a "
    "streams sin recurrencia."
)


def construir_stream():
    """120 items: 12 bloques x 10. Bloque b con régimen R: 8 items del grupo
    R + 2 de ruido (uno de cada otro grupo). Idéntico a EXP45."""
    raw = json.load(open(FEED, encoding="utf-8"))
    freq = Counter((u.get("category") or "").strip().lower() for u in raw)
    rng = random.Random(SEED_STREAM)

    def sortear(grupo):
        cats = GRUPOS[grupo]
        return rng.choices(cats, weights=[freq[c] for c in cats], k=1)[0]

    items = []
    for b, reg in enumerate(REGIMENES):
        mezcla = [sortear(reg) for _ in range(8)]
        for otro in GRUPOS:
            if otro != reg:
                mezcla.append(sortear(otro))
        rng.shuffle(mezcla)
        for q, cat in enumerate(mezcla):
            items.append({
                "id": f"exp45-b{b:02d}-q{q}",
                "ts": f"2026-09-27T{10 + b:02d}:{q * 5:02d}:00",
                "title": "", "text": "",
                "category": cat,
                "grupo": GRUPO_DE[cat],
                "regimen": reg,
            })
    return items


class MockClasificador:
    """Brazos simulados (igual que EXP44/EXP45)."""

    def __init__(self, tasas):
        self.tasas = tasas
        self.brazos = tasas["brazos"]
        self.vistas = []

    def tasa(self, brazo, categoria):
        if brazo == "mayoria":
            return None
        por_cat = self.tasas["por_categoria"].get(categoria, {})
        return por_cat.get(brazo, self.tasas["por_defecto"][brazo])

    def predecir(self, brazo, item, rng):
        if brazo == "mayoria":
            if not self.vistas:
                return "__ninguna__"
            return Counter(self.vistas).most_common(1)[0][0]
        return (item["category"]
                if rng.random() < self.tasa(brazo, item["category"])
                else "__otra__")

    def acierto(self, brazo, item, rng):
        return 1.0 if self.predecir(brazo, item, rng) == item["category"] else 0.0

    def registrar(self, item):
        self.vistas.append(item["category"])


def firma_grupo(grupos_probe):
    """Firma del régimen: grupo mayoritario de los primeros 3 items
    (desempate: primero). Observación gratuita."""
    return Counter(grupos_probe).most_common(1)[0][0]


def prior_params(brazos, rep_hist, block_sig, b, sig):
    """Parámetros del prior warm con olvido. Si sig no es None: solo historia
    de bloques pasados (blk < b) con la misma firma (skill); si no hay,
    fallback al prior ciego (toda la historia). Idéntico a EXP45."""
    params = {}
    for a in brazos:
        if sig is None:
            obs = [(r, blk) for (h, r, blk) in rep_hist[a] if blk < b]
        else:
            obs = [(r, blk) for (h, r, blk) in rep_hist[a]
                   if blk < b and block_sig.get(blk) == sig]
            if not obs:
                obs = [(r, blk) for (h, r, blk) in rep_hist[a] if blk < b]
        if obs:
            ws = [DECAY ** (b - 1 - blk) for (_, blk) in obs]
            sw = sum(ws)
            m = sum(r * w for (r, _), w in zip(obs, ws)) / sw
        else:
            m = 0.5
        params[a] = (1.0 + N0 * m, 1.0 + N0 * (1.0 - m))
    return params


def nuevo_bandit(brazos, params):
    bandit = BanditPorClase(brazos)
    for a in brazos:
        bandit.alpha[a], bandit.beta[a] = params[a]
        bandit.pulls[a] = N0
    return bandit


def skill_existe(rep_hist, block_sig, b, sig):
    return any(blk < b and block_sig.get(blk) == sig
               for a in rep_hist for (_, _, blk) in rep_hist[a])


def skill_arm_actual(brazos, rep_hist, block_sig, b, sig):
    """Brazo de la skill: argmax de la media del prior condicionado a la
    firma (misma cuenta que EXP45). Desempate determinista: primer máximo."""
    params = prior_params(brazos, rep_hist, block_sig, b, sig)
    means = {a: params[a][0] / (params[a][0] + params[a][1]) for a in brazos}
    return max(brazos, key=lambda a: means[a])


def soporte_fuerte(brazos, probe_obs, block_sig, b, sig, skill_arm):
    """Cuenta victorias pareadas del skill_arm en bloques pasados no-saltados
    con la misma firma. Victoria: media en los 5 items de probe (Q1+Q2,
    full-information) estrictamente mayor que la de cada otro brazo
    (margen implícito >= 0.2)."""
    wins = 0
    for b2 in range(b):
        if block_sig.get(b2) != sig:
            continue
        obs = probe_obs.get(b2)
        if not obs:
            continue  # bloque saltado: sin comparación pareada
        m_s = sum(obs[skill_arm]) / len(obs[skill_arm])
        if all(m_s > sum(obs[a]) / len(obs[a])
               for a in brazos if a != skill_arm):
            wins += 1
    return wins >= SOPORTE_MINIMO_VICTORIAS, wins


def correr_replica(rep_id, items, tasas, politica):
    brazos = tasas["brazos"]
    H = len(items)
    n_bloques = H // BLOQUE
    rep_hist = {a: [] for a in brazos}  # (h, reward, bloque)
    block_sig = {}
    probe_obs = {}  # b -> {brazo: [rewards en 5 items de probe]} | None
    rew_pol = [0.0] * H
    rew_fija = {a: [0.0] * H for a in brazos}
    diag = []
    skills_usadas = 0
    probes_saltados = 0
    saltados_det = []

    for b in range(n_bloques):
        base = b * BLOQUE
        sig = firma_grupo([items[base + q]["grupo"] for q in PROBE_Q1])
        block_sig[b] = sig

        saltar = False
        skill_arm = None
        wins = 0
        if politica == "skip" and skill_existe(rep_hist, block_sig, b, sig):
            skill_arm = skill_arm_actual(brazos, rep_hist, block_sig, b, sig)
            fuerte, wins = soporte_fuerte(brazos, probe_obs, block_sig, b,
                                          sig, skill_arm)
            saltar = fuerte

        clf = MockClasificador(tasas)
        for hh in range(base):
            clf.registrar(items[hh])

        if saltar:
            # PROBE SALTADO: se juega el brazo de la skill en los 10 items.
            # Sin bandit, sin probe Q1/Q2. Contabilidad honesta: cuesta 0.
            probes_saltados += 1
            probe_obs[b] = None
            for q in range(BLOQUE):
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
            acc = {a: sum(rew_fija[a][base:base + BLOQUE]) / BLOQUE
                   for a in brazos}
            mejor = max(brazos, key=lambda a: acc[a])
            saltados_det.append({
                "bloque": b, "firma": sig, "brazo_skill": skill_arm,
                "soporte_wins": wins,
                "acc_skill": round(acc[skill_arm], 4),
                "mejor_expost": mejor, "acc_mejor": round(acc[mejor], 4),
                "misfire": bool(mejor != skill_arm),
            })
            diag.append({
                "bloque": b, "regimen": items[base]["regimen"], "firma": sig,
                "probe_saltado": True, "soporte_wins": wins,
                "brazo_skill": skill_arm,
                "acc_pol": round(sum(rew_pol[base:base + BLOQUE]) / BLOQUE, 4),
                "acc_fijas": {
                    a: round(sum(rew_fija[a][base:base + BLOQUE]) / BLOQUE, 4)
                    for a in brazos},
            })
            continue

        # --- Camino con probe: idéntico al tratamiento de EXP45 ---
        bandit = nuevo_bandit(
            brazos, prior_params(brazos, rep_hist, block_sig, b, None))
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
        for q in PROBE_Q1:
            h = base + q
            rs_q1[q] = medir(q, "q1")
            rew_pol[h] = rs_q1[q][fav]

        usa_skill = False
        if skill_existe(rep_hist, block_sig, b, sig):
            usa_skill = True
            skills_usadas += 1
            # Reconstruye el prior condicionado a la firma (skill) y
            # re-aplica las updates del probe Q1 (sin re-sortear).
            bandit = nuevo_bandit(
                brazos, prior_params(brazos, rep_hist, block_sig, b, sig))
            for q in PROBE_Q1:
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

        thompson(tuple(q for q in THOMPSON_Q if q < PROBE_Q2[0]))
        # RE-PROBE Q2: scoring honesto con fav ciego en AMBAS políticas
        rs_q2 = {}
        for q in PROBE_Q2:
            h = base + q
            rs_q2[q] = medir(q, "q2")
            rew_pol[h] = rs_q2[q][fav]
        thompson(tuple(q for q in THOMPSON_Q if q > PROBE_Q2[-1]))

        probe_obs[b] = {a: [rs_q1[q][a] for q in PROBE_Q1] +
                           [rs_q2[q][a] for q in PROBE_Q2]
                        for a in brazos}

        diag.append({
            "bloque": b, "regimen": items[base]["regimen"], "firma": sig,
            "probe_saltado": False, "soporte_wins": wins,
            "skill_usada": usa_skill,
            "acc_pol": round(sum(rew_pol[base:base + BLOQUE]) / BLOQUE, 4),
            "acc_fijas": {
                a: round(sum(rew_fija[a][base:base + BLOQUE]) / BLOQUE, 4)
                for a in brazos},
        })

    reg_pol = H - sum(rew_pol)
    reg_fijas = {a: H - sum(rew_fija[a]) for a in brazos}
    mejor = min(brazos, key=lambda a: reg_fijas[a])
    return {"politica": politica, "reg_pol": reg_pol, "reg_fijas": reg_fijas,
            "mejor_fija": mejor, "reg_mejor_fija": reg_fijas[mejor],
            "skills_usadas": skills_usadas, "probes_saltados": probes_saltados,
            "saltados_det": saltados_det, "n_bloques": n_bloques,
            "diag": diag, "n": H}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--replicas", type=int, default=N_REPLICAS)
    args = ap.parse_args()
    t0 = time.time()

    out = args.out or os.path.join(BASE, "resultados", "exp46-20260927")
    os.makedirs(out, exist_ok=True)

    items = construir_stream()
    H = len(items)
    n_bloques = H // BLOQUE
    tasas = json.load(open(TASAS_PATH, encoding="utf-8"))

    # --- pre-registro ANTES de correr ---
    prereg = {
        "experimento": "ALMA-EXP46: skills que reducen el costo del probe "
                       "(salto de probe con soporte fuerte) — mock",
        "fase": "mock",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "hipotesis": "Si una skill (experiencia pasada del mismo régimen) "
                     "tiene soporte fuerte, saltar el probe y jugar directo "
                     "el brazo de la skill reduce el regret frente a la "
                     "maquinaria con probe siempre (tratamiento de EXP45), "
                     "porque el costo de exploración del probe (5 "
                     "items/bloque con scoring ciego) supera el riesgo de "
                     "misfire cuando la skill ya ganó el régimen 2+ veces.",
        "nota_refutacion": "Si FAIL aun en este mundo con recurrencia "
                           "garantizada (3x4), saltar el probe no paga: el "
                           "riesgo de misfire (firma ruidosa, brazo stale) "
                           "supera el ahorro de exploración.",
        "condicion_alcance": CONDICION_ALCANCE,
        "stream": {
            "fuente": "CONSTRUIDO: idéntico a EXP45 — categorías sorteadas "
                      "con frecuencias empíricas del feed real "
                      "(data_exp44/feed_units.json)",
            "n_items": H, "bloques": n_bloques, "tam_bloque": BLOQUE,
            "regimenes": REGIMENES,
            "semilla_orden": SEED_STREAM,
            "composicion_bloque": "8 items del grupo del régimen + 2 de ruido "
                                  "(uno de cada otro grupo)",
            "grupos": GRUPOS,
            "oraculo": "tasas mock calibradas por categoría "
                       "(data_exp44/tasas.json)",
            "sesgo_seleccion": SESGO_SELECCION,
        },
        "politicas": {
            "control": "El tratamiento de EXP45: probe Q1 (mide 4 brazos) + "
                       "Thompson (5 items) + re-probe Q2 + Thompson; tras Q1 "
                       "el prior se reconstruye condicionado a la firma "
                       "(skill); probe siempre. Bit-idéntico al tratamiento "
                       "de EXP45 (mismos strings de seed del oráculo, mismo "
                       "stream seed 45, mismo código) → se verifica "
                       "reproducibilidad contra "
                       "resultados/exp45-20260927/report.json.",
            "skip": "Idéntica al control, salvo que si la skill de la firma "
                    "del bloque tiene soporte fuerte se SALTA el probe (Q1 y "
                    "Q2) y se juega el brazo de la skill en los 10 items. "
                    "Contabilidad honesta: el probe saltado cuesta 0. Un "
                    "solo moving part.",
        },
        "mecanismo_skill": {
            "firma": "grupo mayoritario entre los grupos de los primeros 3 "
                     "items del bloque (observación gratuita; idéntica a la "
                     "firma de EXP45)",
            "skill_arm": "brazo con mayor media del prior condicionado a la "
                         "firma (warm olvido 0.5^d sobre la historia de la "
                         "skill); desempate determinista: primer máximo",
            "soporte_fuerte": ">=2 victorias pareadas del skill_arm en "
                              "bloques pasados no-saltados con la misma "
                              "firma; victoria = media del skill_arm en los "
                              "5 items de probe (Q1+Q2, full-information) "
                              "estrictamente mayor que la de cada otro brazo "
                              "(margen implícito >= 0.2)",
            "bloque_saltado": "sin probe Q1/Q2 ni bandit: se juega skill_arm "
                              "en los 10 items; sus rewards observados se "
                              "agregan a la historia de la skill (la skill "
                              "sigue mejorándose con el uso); el bloque no "
                              "aporta comparación pareada (no cuenta como "
                              "victoria futura)",
            "fuente_experiencia": "toda la experiencia observada por la "
                                  "política (probe + Thompson + bloques "
                                  "saltados), etiquetada por bloque",
        },
        "rng": "números comunes idénticos a EXP45: cada outcome de brazo se "
               "sortea con seed 'exp45-r{rep}-b{b}-q{q}-{a}' (strings "
               "idénticos a EXP45 a propósito); control y tratamiento ven el "
               "mismo oráculo. Pareado por réplica.",
        "criterio": {"efecto": "regret(skip) - regret(control), media sobre "
                               "réplicas (pareadas, RNG común)",
                     "pass": "media(efecto) < 0"},
        "replicas": args.replicas,
        "modo": "mock, US$0",
    }
    with open(os.path.join(out, "preregistro.json"), "w", encoding="utf-8") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito ({H} items, {n_bloques} bloques, "
          f"{args.replicas} réplicas pareadas).")

    efectos, det = [], []
    for r in range(args.replicas):
        ctrl = correr_replica(r, items, tasas, "control")
        trt = correr_replica(r, items, tasas, "skip")
        ef = trt["reg_pol"] - ctrl["reg_pol"]
        efectos.append(ef)
        det.append({
            "replica": r, "efecto": round(ef, 3),
            "reg_control": round(ctrl["reg_pol"], 3),
            "reg_skip": round(trt["reg_pol"], 3),
            "reg_mejor_fija_ctrl": round(ctrl["reg_mejor_fija"], 3),
            "reg_mejor_fija_skip": round(trt["reg_mejor_fija"], 3),
            "mejor_fija": ctrl["mejor_fija"],
            "skills_usadas_ctrl": f"{ctrl['skills_usadas']}/{n_bloques} bloques",
            "probes_saltados_skip":
                f"{trt['probes_saltados']}/{n_bloques} bloques",
            "misfires_skip": sum(1 for s in trt["saltados_det"]
                                 if s["misfire"]),
        })
        if r == 0:
            diag_rep0 = {"control": ctrl["diag"], "skip": trt["diag"]}
            salt_rep0 = trt["saltados_det"]
    media_ef = sum(efectos) / len(efectos)
    pasa = bool(media_ef < 0)

    # --- chequeo de reproducibilidad: el control debe ser bit-idéntico al
    # tratamiento de EXP45 ---
    repro_ok = None
    try:
        rep45 = json.load(open(EXP45_REPORT, encoding="utf-8"))
        d45 = {d["replica"]: d["reg_skills"]
               for d in rep45["detalle_replicas"]}
        repro_ok = all(
            abs(det[r]["reg_control"] - d45[r]) < 1e-9
            for r in range(args.replicas))
    except Exception as e:  # noqa: BLE001
        repro_ok = f"no verificable: {e}"

    motivos = [
        f"items={H}, bloques={n_bloques}, réplicas pareadas={args.replicas} "
        f"(RNG común)",
        f"efecto medio (reg_skip - reg_control) = {media_ef:+.3f} "
        f"(por réplica: {', '.join(f'{e:+.2f}' for e in efectos)})",
        f"regret medio control: "
        f"{sum(d['reg_control'] for d in det) / len(det):.2f} | "
        f"skip: {sum(d['reg_skip'] for d in det) / len(det):.2f} | "
        f"mejor fija: {sum(d['reg_mejor_fija_ctrl'] for d in det) / len(det):.2f}",
        f"probes saltados (media): "
        f"{sum(int(d['probes_saltados_skip'].split('/')[0]) for d in det) / len(det):.1f} "
        f"bloques/réplica; misfires totales: "
        f"{sum(d['misfires_skip'] for d in det)}",
        f"reproducibilidad vs EXP45 (control == su tratamiento): {repro_ok}",
        ("PASS" if pasa else "FAIL") + " (vara intacta)",
    ]
    report = {
        "preregistro": "preregistro.json (mismo directorio)",
        "n_items": H, "n_bloques": n_bloques,
        "detalle_replicas": det,
        "efecto_medio": round(media_ef, 3),
        "saltados_det_rep0": salt_rep0,
        "diagnostico_bloques_rep0": diag_rep0,
        "reproducibilidad_exp45": repro_ok,
        "costo_total_usd": 0.0,
        "veredicto": {"pasa": pasa, "criterio": prereg["criterio"],
                       "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP46 ================")
    for m in motivos:
        print("  " + m)
    print("  costo: $0.0000 USD (mock) | "
          f"{report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
