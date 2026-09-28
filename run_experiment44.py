#!/usr/bin/env python3
"""ALMA-EXP44: el loop sobre un stream REAL no estacionario — noticias del feed.

Tarea: clasificar cada noticia del feed de Muse en su categoría.
Oráculo: la etiqueta publicada por el feed (verdad barata y real).

Fase mock (esta): brazos = estrategias de clasificación SIMULADAS con tasas
plausibles diferenciadas por categoría (data_exp44/tasas.json). Lo que se
testea es la maquinaria de SELECCIÓN sobre un stream real no estacionario,
no la clasificación en sí.

Política ALMA: probe continuo + re-probe + Thompson con prior con olvido
(maquinaria EXP7/EXP9), CON contabilidad honesta del probe (lección EXP43:
los items de probe se puntúan con el favorito del prior —lo que se jugaría
sin la info del probe—, jamás con el ganador ex-post).

Criterio PRE-REGISTRADO: media sobre réplicas de
    regret(ALMA) - regret(mejor brazo fijo)  <  0

Uso:
    python3 run_experiment44.py [--out DIR] [--replicas N]
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
DATA = os.path.join(BASE, "data_exp44", "feed_units.json")
TASAS_PATH = os.path.join(BASE, "data_exp44", "tasas.json")

BLOQUE = 10
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (6, 7)
THOMPSON_Q = tuple(q for q in range(BLOQUE)
                   if q not in PROBE_Q1 + PROBE_Q2)
assert len(THOMPSON_Q) == 5
N_REPLICAS = 5
N0 = 2            # fuerza del prior (convención EXP9)
DECAY = 0.5       # olvido exponencial por bloque (EXP9)
MIN_ITEMS = 40

SESGO_SELECCION = (
    "El feed es curado: contiene solo noticias que le interesan al usuario. "
    "No es 'todas las noticias' ni una muestra aleatoria de la agenda "
    "noticiosa; es un stream filtrado por interés personal. Implicancias: "
    "(1) la distribución de categorías refleja SUS intereses, no la agenda "
    "general; (2) la no-estacionariedad medida = rotación de SUS intereses "
    "en el tiempo; (3) los resultados NO generalizan a 'clasificación de "
    "noticias' en general."
)


def cargar_stream():
    if not os.path.exists(DATA):
        print(f"FALTA {DATA}: el parent debe exportar las unidades del feed "
              f"(ver data_exp44/README.md).")
        return None
    raw = json.load(open(DATA, encoding="utf-8"))
    items = []
    for u in raw:
        cat = (u.get("category") or "").strip().lower()
        if not cat:
            continue
        items.append({
            "id": str(u.get("id", len(items))),
            "ts": u.get("published_at", ""),
            "title": u.get("title", ""),
            "text": u.get("text", ""),
            "category": cat,
        })
    items.sort(key=lambda x: x["ts"])
    return items


class MockClasificador:
    """Brazos simulados. predecir() no tiene efectos laterales; registrar()
    se llama UNA vez por item (después de medir todos los brazos), así
    'mayoria' ve cada categoría una sola vez."""

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


def bandit_warm_olvido(brazos, rep_hist, b):
    bandit = BanditPorClase(brazos)
    for a in brazos:
        obs = rep_hist[a]
        if obs:
            ws = [DECAY ** ((b * BLOQUE - 1 - hh) // BLOQUE) for hh, _ in obs]
            sw = sum(ws)
            m = sum(r * w for (_, r), w in zip(obs, ws)) / sw if sw else 0.5
        else:
            m = 0.5
        bandit.alpha[a] = 1.0 + N0 * m
        bandit.beta[a] = 1.0 + N0 * (1.0 - m)
        bandit.pulls[a] = N0
    return bandit


def correr_replica(rep_id, items, tasas, n_bloques):
    brazos = tasas["brazos"]
    H = n_bloques * BLOQUE
    rep_hist = {a: [] for a in brazos}   # [(h, reward)] observado por el bandit
    rew_alma = [0.0] * H
    rew_fija = {a: [0.0] * H for a in brazos}
    diag_bloques = []

    for b in range(n_bloques):
        base = b * BLOQUE
        bandit = bandit_warm_olvido(brazos, rep_hist, b)
        prior_means = {a: bandit.mean(a) for a in brazos}
        fav = max(brazos, key=lambda a: prior_means[a])

        clf = MockClasificador(tasas)
        for hh in range(base):
            clf.registrar(items[hh])

        probe_acc = {a: [] for a in brazos}

        def medir_probe(qs):
            for q in qs:
                h = base + q
                it = items[h]
                rng = random.Random(f"exp44-r{rep_id}-b{b}-q{q}")
                rs = {a: clf.acierto(a, it, rng) for a in brazos}
                for a in brazos:
                    bandit.update(a, rs[a])
                    rep_hist[a].append((h, rs[a]))
                    rew_fija[a][h] = rs[a]
                    probe_acc[a].append(rs[a])
                # Contabilidad honesta (EXP43): el item de probe se puntúa
                # con el favorito del prior — lo que se jugaría sin la info
                # del probe — jamás con el ganador ex-post.
                rew_alma[h] = rs[fav]
                clf.registrar(it)

        def jugar_thompson(qs):
            for q in qs:
                h = base + q
                it = items[h]
                rng = random.Random(f"exp44-r{rep_id}-b{b}-q{q}")
                a_sel = bandit.select(rng)
                r_sel = clf.acierto(a_sel, it, rng)
                bandit.update(a_sel, r_sel)
                rep_hist[a_sel].append((h, r_sel))
                rew_alma[h] = r_sel
                # medición mock gratuita para el diagnóstico de fijas
                # (no toca el bandit)
                for a in brazos:
                    rew_fija[a][h] = clf.acierto(a, it, rng)
                clf.registrar(it)

        medir_probe(PROBE_Q1)
        m1 = {a: sum(probe_acc[a]) / len(probe_acc[a]) for a in brazos}
        e1 = max(brazos, key=lambda a: (m1[a], prior_means[a]))
        jugar_thompson(tuple(q for q in THOMPSON_Q if q < PROBE_Q2[0]))
        medir_probe(PROBE_Q2)
        m2 = {a: sum(probe_acc[a]) / len(probe_acc[a]) for a in brazos}
        e2 = max(brazos, key=lambda a: (m2[a], prior_means[a]))
        jugar_thompson(tuple(q for q in THOMPSON_Q if q > PROBE_Q2[-1]))

        diag_bloques.append({
            "bloque": b,
            "ts_ini": items[base]["ts"],
            "dist_categorias": dict(Counter(
                it["category"] for it in items[base:base + BLOQUE])),
            "elegido_probe1": e1, "elegido_probe2": e2,
            "acc_alma": round(sum(rew_alma[base:base + BLOQUE]) / BLOQUE, 4),
            "acc_fijas": {a: round(sum(rew_fija[a][base:base + BLOQUE]) / BLOQUE, 4)
                          for a in brazos},
        })

    reg_alma = H - sum(rew_alma)
    reg_fijas = {a: H - sum(rew_fija[a]) for a in brazos}
    mejor = min(brazos, key=lambda a: reg_fijas[a])
    return {"reg_alma": reg_alma, "reg_fijas": reg_fijas,
            "mejor_fija": mejor, "efecto": reg_alma - reg_fijas[mejor],
            "diag": diag_bloques, "n": H}


def rotacion_intereses(items, n_bloques):
    """Diagnóstico: ¿rotan los intereses con el tiempo? Dominante por bloque
    y cambios de dominante entre bloques consecutivos."""
    doms = []
    for b in range(n_bloques):
        c = Counter(it["category"] for it in items[b * BLOQUE:(b + 1) * BLOQUE])
        doms.append(c.most_common(1)[0][0] if c else None)
    cambios = sum(1 for i in range(1, len(doms)) if doms[i] != doms[i - 1])
    return {"dominante_por_bloque": doms, "cambios": cambios,
            "n_bloques": n_bloques}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--replicas", type=int, default=N_REPLICAS)
    args = ap.parse_args()
    t0 = time.time()

    out = args.out or os.path.join(BASE, "resultados", "exp44-20260927")
    os.makedirs(out, exist_ok=True)

    items = cargar_stream()
    if items is None:
        return 2
    if len(items) < MIN_ITEMS:
        print(f"STREAM INSUFICIENTE: {len(items)} items con etiqueta usable "
              f"(< {MIN_ITEMS}). No se corre el experimento; no se inventan datos.")
        return 2
    n_bloques = len(items) // BLOQUE
    H = n_bloques * BLOQUE
    items = items[:H]

    tasas = json.load(open(TASAS_PATH, encoding="utf-8"))
    cats = sorted(set(it["category"] for it in items))
    con_default = [c for c in cats if c not in tasas["por_categoria"]]
    if con_default:
        print(f"  ADVERTENCIA: categorías sin tasa específica (usan "
              f"por_defecto, documentado): {con_default}")

    # --- pre-registro ANTES de correr ---
    prereg = {
        "experimento": "ALMA-EXP44: loop sobre stream real no estacionario "
                       "(noticias del feed de Muse)",
        "fase": "mock",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stream": {
            "fuente": "unidades publicadas del feed de Muse "
                      "(data_exp44/feed_units.json)",
            "n_items": H, "bloques": n_bloques, "tam_bloque": BLOQUE,
            "orden": "cronológico por published_at",
            "categorias": cats,
            "oraculo": "la etiqueta publicada (categoría del feed)",
            "sesgo_seleccion": SESGO_SELECCION,
        },
        "brazos_mock": {
            brazo: ({"descripcion": tasas["descripcion_brazos"][brazo],
                     "nota": "determinista, sin tasas"}
                    if brazo == "mayoria" else
                    {"descripcion": tasas["descripcion_brazos"][brazo],
                     "tasas": {c: tasas["por_categoria"].get(c, {}).get(
                         brazo, tasas["por_defecto"][brazo]) for c in cats}})
            for brazo in tasas["brazos"]},
        "nota_mayoria": "brazo determinista sin tasa: predice la categoría más "
                        "frecuente vista hasta el momento",
        "politica": "probe q=0,1,2 + re-probe q=6,7 (mide los 4 brazos) + "
                    "Thompson resto; prior warm con olvido 0.5^d (EXP9); "
                    "CONTABILIDAD HONESTA DEL PROBE (EXP43): items de probe se "
                    "puntúan con el favorito del prior, nunca con el ganador "
                    "ex-post",
        "criterio": {"efecto": "regret(ALMA) - regret(mejor brazo fijo), "
                               "media sobre réplicas",
                     "pass": "media(efecto) < 0"},
        "replicas": args.replicas,
        "modo": "mock, US$0",
    }
    with open(os.path.join(out, "preregistro.json"), "w", encoding="utf-8") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito ({H} items, {n_bloques} bloques, "
          f"{args.replicas} réplicas).")

    reps = [correr_replica(r, items, tasas, n_bloques)
            for r in range(args.replicas)]
    efectos = [rp["efecto"] for rp in reps]
    media_ef = sum(efectos) / len(efectos)
    pasa = bool(media_ef < 0)

    rot = rotacion_intereses(items, n_bloques)
    motivos = [
        f"items={H}, bloques={n_bloques}, categorías={cats}",
        f"efecto medio (reg_alma - reg_mejor_fija) = {media_ef:+.3f} "
        f"en {args.replicas} réplicas "
        f"(por réplica: {', '.join(f'{e:+.2f}' for e in efectos)})",
        f"mejor fija por réplica: {[rp['mejor_fija'] for rp in reps]}",
        "ROTACIÓN DE INTERESES (diagnóstico): dominante por bloque = "
        f"{rot['dominante_por_bloque']}; cambios de dominante: "
        f"{rot['cambios']}/{rot['n_bloques'] - 1} transiciones",
        ("PASS" if pasa else "FAIL") + " (vara intacta)",
    ]
    report = {
        "preregistro": "preregistro.json (mismo directorio)",
        "n_items": H, "n_bloques": n_bloques,
        "efectos_por_replica": [round(e, 3) for e in efectos],
        "efecto_medio": round(media_ef, 3),
        "rotacion_intereses": rot,
        "diagnostico_bloques_rep0": reps[0]["diag"],
        "costo_total_usd": 0.0,
        "veredicto": {"pasa": pasa, "criterio": prereg["criterio"],
                       "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP44 ================")
    for m in motivos:
        print("  " + m)
    print("  costo: $0.0000 USD (mock) | "
          f"{report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
