#!/usr/bin/env python3
"""ALMA-EXP45: loop de skills estilo Hermes sobre stream con regímenes recurrentes.

Idea (aprobada por el usuario): incorporar el mecanismo de Hermes Agent
(Nous Research) a ALMA — cuando la política acumula experiencia de un
régimen, esa experiencia persiste como "skill" reutilizable: el prior de
Thompson arranca condicionado por régimen en vez de ciego.

Diseño A/B (mock, US$0):
- Control: maquinaria EXP44 (probe Q1 + Thompson + re-probe Q2 + Thompson;
  prior warm con olvido 0.5^d, N0=2; contabilidad honesta del probe EXP43).
- Tratamiento: idéntico, salvo que tras el probe Q1 el prior del bandit se
  reconstruye condicionado a la firma del régimen (skill): warm olvido sobre
  la historia de bloques con la misma firma. El scoring de items de probe
  sigue con el favorito ciego en AMBOS (un solo moving part).

Firma de régimen: grupo mayoritario entre las categorías de los 3 items del
probe Q1 (grupos: tech/dinero/deportes; desempate determinista: primer item).

Stream (construido, documentado): 120 items, 12 bloques x 10, 3 regímenes x 4
recurrencias en orden pseudo-aleatorio (seed 45, no alternante). Por bloque:
8 items del grupo del régimen + 2 de ruido (uno de cada otro grupo),
categorías sorteadas con las frecuencias empíricas del feed real
(data_exp44/feed_units.json). Tasas mock calibradas: data_exp44/tasas.json
(titular gana en tech/deportes, contexto en dinero).

RNG común: cada outcome de brazo se sortea con seed por (réplica, bloque,
item, brazo) → control y tratamiento ven el mismo oráculo; la única
diferencia es la política. Pareado, 5 réplicas.

Criterio PRE-REGISTRADO: media sobre réplicas de
    regret(tratamiento) - regret(control)  <  0   → PASS

Uso:
    python3 run_experiment45.py [--out DIR] [--replicas N]
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


def construir_stream():
    """120 items: 12 bloques x 10. Bloque b con régimen R: 8 items del grupo
    R + 2 de ruido (uno de cada otro grupo)."""
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
    """Brazos simulados (igual que EXP44)."""

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
    """Firma del régimen: grupo mayoritario del probe Q1 (desempate: primero)."""
    return Counter(grupos_probe).most_common(1)[0][0]


def prior_params(brazos, rep_hist, block_sig, b, sig):
    """Parámetros del prior warm con olvido. Si sig no es None: solo historia
    de bloques pasados (blk < b) con la misma firma (skill); si no hay,
    fallback al prior ciego (toda la historia)."""
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


def correr_replica(rep_id, items, tasas, politica):
    brazos = tasas["brazos"]
    H = len(items)
    n_bloques = H // BLOQUE
    rep_hist = {a: [] for a in brazos}  # (h, reward, bloque)
    block_sig = {}
    rew_pol = [0.0] * H
    rew_fija = {a: [0.0] * H for a in brazos}
    diag = []
    skills_usadas = 0

    for b in range(n_bloques):
        base = b * BLOQUE
        bandit = nuevo_bandit(
            brazos, prior_params(brazos, rep_hist, block_sig, b, None))
        prior_means = {a: bandit.mean(a) for a in brazos}
        fav = max(brazos, key=lambda a: prior_means[a])

        clf = MockClasificador(tasas)
        for hh in range(base):
            clf.registrar(items[hh])

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

        sig = firma_grupo([items[base + q]["grupo"] for q in PROBE_Q1])
        block_sig[b] = sig

        if politica == "skills":
            if skill_existe(rep_hist, block_sig, b, sig):
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
        for q in PROBE_Q2:
            h = base + q
            rs = medir(q, "q2")
            rew_pol[h] = rs[fav]
        thompson(tuple(q for q in THOMPSON_Q if q > PROBE_Q2[-1]))

        diag.append({
            "bloque": b, "regimen": items[base]["regimen"], "firma": sig,
            "skill_usada": bool(politica == "skills" and
                                skill_existe(rep_hist, block_sig, b, sig)),
            "acc_pol": round(sum(rew_pol[base:base + BLOQUE]) / BLOQUE, 4),
            "acc_fijas": {a: round(sum(rew_fija[a][base:base + BLOQUE]) / BLOQUE, 4)
                          for a in brazos},
        })

    reg_pol = H - sum(rew_pol)
    reg_fijas = {a: H - sum(rew_fija[a]) for a in brazos}
    mejor = min(brazos, key=lambda a: reg_fijas[a])
    return {"politica": politica, "reg_pol": reg_pol, "reg_fijas": reg_fijas,
            "mejor_fija": mejor, "reg_mejor_fija": reg_fijas[mejor],
            "skills_usadas": skills_usadas, "n_bloques": n_bloques,
            "diag": diag, "n": H}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--replicas", type=int, default=N_REPLICAS)
    args = ap.parse_args()
    t0 = time.time()

    out = args.out or os.path.join(BASE, "resultados", "exp45-20260927")
    os.makedirs(out, exist_ok=True)

    items = construir_stream()
    H = len(items)
    n_bloques = H // BLOQUE
    tasas = json.load(open(TASAS_PATH, encoding="utf-8"))

    # --- pre-registro ANTES de correr ---
    prereg = {
        "experimento": "ALMA-EXP45: loop de skills estilo Hermes sobre stream "
                       "con regímenes recurrentes (mock)",
        "fase": "mock",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "hipotesis": "Un prior Thompson condicionado por régimen (skill: la "
                     "experiencia pasada del mismo régimen persiste y se "
                     "reutiliza, como las skills de Hermes Agent) reduce el "
                     "regret frente al prior ciego al régimen, porque los "
                     "regímenes recurren (3 x 4) y el brazo ganador por "
                     "régimen es estable (titular en tech/deportes, contexto "
                     "en dinero).",
        "nota_refutacion": "Si FAIL aun en este mundo diseñado para que las "
                           "skills puedan ayudar (recurrencia garantizada), "
                           "el loop de skills en esta forma no aporta sobre "
                           "la maquinaria base.",
        "stream": {
            "fuente": "CONSTRUIDO: categorías sorteadas con frecuencias "
                      "empíricas del feed real (data_exp44/feed_units.json)",
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
            "control": "maquinaria EXP44: probe Q1 (mide 4 brazos) + Thompson "
                       "(5 items) + re-probe Q2 + Thompson; prior warm con "
                       "olvido 0.5^d, N0=2; probe con contabilidad honesta "
                       "(fav del prior ciego)",
            "skills": "idéntica, salvo que tras el probe Q1 el prior se "
                      "reconstruye condicionado a la firma del régimen "
                      "(warm olvido solo sobre bloques pasados con la misma "
                      "firma; fallback a ciego si no hay). El scoring de "
                      "probe sigue con fav ciego en ambas: UN solo moving "
                      "part.",
        },
        "mecanismo_skill": {
            "firma": "grupo mayoritario entre las categorías de los 3 items "
                     "del probe Q1 (desempate determinista: primer item)",
            "skill": "para cada firma, la historia (bloque, brazo, reward) "
                     "de bloques pasados con esa firma; el prior usa warm "
                     "olvido 0.5^d sobre esa historia",
            "soporte_minimo": "1 bloque pasado con la firma (si no hay, "
                              "fallback al prior ciego)",
            "fuente_experiencia": "toda la experiencia observada por la "
                                  "política (probe + Thompson), etiquetada "
                                  "por bloque",
        },
        "rng": "números comunes: cada outcome de brazo se sortea con seed por "
               "(réplica, bloque, item, brazo); control y tratamiento ven el "
               "mismo oráculo. Pareado por réplica.",
        "criterio": {"efecto": "regret(skills) - regret(control), media "
                               "sobre réplicas (pareadas, RNG común)",
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
        trt = correr_replica(r, items, tasas, "skills")
        ef = trt["reg_pol"] - ctrl["reg_pol"]
        efectos.append(ef)
        det.append({
            "replica": r, "efecto": round(ef, 3),
            "reg_control": round(ctrl["reg_pol"], 3),
            "reg_skills": round(trt["reg_pol"], 3),
            "reg_mejor_fija_ctrl": round(ctrl["reg_mejor_fija"], 3),
            "reg_mejor_fija_trt": round(trt["reg_mejor_fija"], 3),
            "mejor_fija": ctrl["mejor_fija"],
            "skills_usadas_trt": f"{trt['skills_usadas']}/{n_bloques} bloques",
        })
        if r == 0:
            diag_rep0 = {"control": ctrl["diag"], "skills": trt["diag"]}
    media_ef = sum(efectos) / len(efectos)
    pasa = bool(media_ef < 0)

    motivos = [
        f"items={H}, bloques={n_bloques}, réplicas pareadas={args.replicas} "
        f"(RNG común)",
        f"efecto medio (reg_skills - reg_control) = {media_ef:+.3f} "
        f"(por réplica: {', '.join(f'{e:+.2f}' for e in efectos)})",
        f"regret medio control: "
        f"{sum(d['reg_control'] for d in det) / len(det):.2f} | "
        f"skills: {sum(d['reg_skills'] for d in det) / len(det):.2f} | "
        f"mejor fija: {sum(d['reg_mejor_fija_ctrl'] for d in det) / len(det):.2f}",
        ("PASS" if pasa else "FAIL") + " (vara intacta)",
    ]
    report = {
        "preregistro": "preregistro.json (mismo directorio)",
        "n_items": H, "n_bloques": n_bloques,
        "detalle_replicas": det,
        "efecto_medio": round(media_ef, 3),
        "diagnostico_bloques_rep0": diag_rep0,
        "costo_total_usd": 0.0,
        "veredicto": {"pasa": pasa, "criterio": prereg["criterio"],
                       "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP45 ================")
    for m in motivos:
        print("  " + m)
    print("  costo: $0.0000 USD (mock) | "
          f"{report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
