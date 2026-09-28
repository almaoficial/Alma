#!/usr/bin/env python3
"""ALMA-EXP16: replicación multi-seed de ALMA v2 — ¿cuánto ruido hay?

Motivo (26/9): v2 dio regret 4.615 (EXP13), 7.075 (EXP14) y 8.255
(EXP15) — misma política, distintas seeds. El ruido entre corridas puede
invalidar todos los veredictos de una sola seed. Este experimento ataca
la credibilidad de nuestros propios veredictos: lo más refutación-primero
que podemos hacer ahora.

Diseño (aprobado por el usuario 26/9 ~14:14):
  - Réplica exacta de ALMA v2 de EXP13 (probe q=0,1,2 + re-probe q=10,11;
    Thompson; prior warm con olvido 0.5^d; fix1: default = prior-best warm,
    cambio si alternativo supera por > 0.05; fix2: poda de brazos muertos).
  - Mismo stream no estacionario con flip de EXP12/13/14/15 (10 bloques x
    12, oráculo COPIADO de EXP12 — SIN medir de nuevo).
  - 4 seeds PRE-REGISTRADAS: 1616, 1717, 1818, 1919. Fases de política
    separadas por seed (16B-s{seed}-probe/full) para que cada réplica haga
    sus propios 220 pulls frescos (sin colisión de caché entre seeds).
  - RNG pareado por (seed,bloque,q).

Criterio PRE-REGISTRADO de interpretación:
  - Si rango(max-min) del regret entre seeds > 1.0 → los veredictos de una
    sola seed NO son confiables (nuestros márgenes de decisión fueron 0.5
    en EXP15 y diffs de ~0.45 en EXP14 — menores que el ruido).
  - Si rango < 1.0 → los veredictos se sostienen.

Restricciones duras:
  - Solo gpt-4o-mini. Si la proyección de costo supera US$1,00: detener
    (exit 2) y reportar.
  - La API key nunca se imprime ni se guarda (VaultBackend).

Uso:
    python3 run_experiment16.py --mock [--out /tmp/exp16-mock]
    python3 run_experiment16.py --api
"""
import argparse
import json
import os
import random
import statistics
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_experiment as rx
import run_experiment5 as rx5
import run_experiment12 as rx12
import run_experiment13 as rx13

NOMBRE = ("ALMA-EXP16: replicación multi-seed de ALMA v2 — "
          "¿son confiables los veredictos de una sola seed?")
ARMS3 = ["single", "cot", "reflexion"]
SEEDS = [1616, 1717, 1818, 1919]   # PRE-REGISTRADAS
BLOQUE = 12
N_BLOQUES = 10
N_PROB = N_BLOQUES * BLOQUE  # 120
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (10, 11)
THOMPSON_Q = tuple(q for q in range(BLOQUE)
                   if q not in PROBE_Q1 + PROBE_Q2)
assert len(THOMPSON_Q) == 7
# Fases: el oráculo se COPIA de EXP12 (mismas mediciones, fase renombrada).
FASE_OR1_SRC, FASE_OR2_SRC = "12A-oracle-r1", "12A-oracle-r2"
FASE_OR1, FASE_OR2 = "16A-oracle-r1", "16A-oracle-r2"
PULLS_POR_SEED = N_BLOQUES * (len(PROBE_Q1) + len(PROBE_Q2)) * 3 \
    + N_BLOQUES * len(THOMPSON_Q)   # 220
DECAY = 0.5              # olvido exponencial rápido (maquinaria EXP9)
N0 = rx5.N0_PSEUDO       # fuerza del prior warm (EXP4)
MARGEN = rx5.PROBE_MARGEN  # 0.05 (fix1)
PODA_GAP = 0.10          # fix2: gap de media empírica para podar
PODA_BLOQUES = 2         # fix2: bloques consecutivos con gap
RANGO_MAX = 1.0          # PRE-REGISTRADO: rango > 1.0 => no confiables
COSTO_STOP = 1.00        # freno duro de costo total proyectado (USD)

CRITERIO_EXP16 = {"rango_max_confiable": RANGO_MAX,
                  "interpretacion": ("rango(max-min) del regret entre "
                                     "seeds > 1.0 => veredictos de una "
                                     "sola seed NO confiables; "
                                     "< 1.0 => se sostienen")}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def copiar_oraculo_exp12(store, base):
    """Copia las 720 mediciones del oráculo de EXP12 al store nuevo con
    fases 16A-*. Sin llamadas a la API. Devuelve {(pid, arm): media}."""
    src = os.path.join(base, "resultados", "exp12-20260926",
                       "experiencias.jsonl")
    n = 0
    for line in open(src, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("fase") not in (FASE_OR1_SRC, FASE_OR2_SRC):
            continue
        nueva = {k: v for k, v in row.items()
                 if k not in ("hash", "prev_hash", "timestamp", "schema")}
        nueva["fase"] = (FASE_OR1 if row["fase"] == FASE_OR1_SRC
                         else FASE_OR2)
        store.append(nueva)
        n += 1
    assert n == N_PROB * 3 * 2, f"oráculo copiado incompleto: {n}/720"
    acc = defaultdict(list)
    for r in store.read_all():
        if r.get("fase") in (FASE_OR1, FASE_OR2):
            acc[(r["problema_id"], r["arch_id"])].append(
                r["metricas"]["reward"])
    assert len(acc) == N_PROB * 3, f"celdas: {len(acc)}/360"
    return {k: sum(v) / len(v) for k, v in acc.items()}


def correr_v2(seed, stream, orden_bloques, oracle_reward, pull, hechos,
              store):
    """Réplica exacta de ALMA v2 (EXP13), fases propias por seed.
    Devuelve (regret, diagnostico, selecciones, podas)."""
    f_probe = f"16B-s{seed}-probe"
    f_full = f"16B-s{seed}-full"
    fases = (FASE_OR1, FASE_OR2, f_probe, f_full)
    rewards = {}
    diag = []
    n_switch = 0
    thompson_arms = defaultdict(int)
    obs = {a: [] for a in ARMS3}   # medias empíricas (fix2)
    activas = list(ARMS3)
    podas = []
    cnt_gap = {a: 0 for a in ARMS3}

    def fila_full(pid):
        for a in activas:
            if (f_full, pid, a) in hechos:
                return a, hechos[(f_full, pid, a)]
        return None

    for nb in range(N_BLOQUES):
        base_pos = nb * BLOQUE
        bandit = rx13.bandit_warm_ponderado_arms(
            rx13.repertorio_ponderado_fases(store, stream, base_pos,
                                           rx13.DECAY, fases),
            activas)
        prior_means = bandit.means()

        def probe_q(qs):
            prs = {}
            for q in qs:
                p = stream[base_pos + q][1]
                for a in ARMS3:
                    key = (f_probe, p["id"], a)
                    if key in hechos:
                        r, nuevo = hechos[key], False
                    else:
                        r, nuevo = pull(p, a, f_probe)
                    prs[(q, a)] = r
                    if nuevo:
                        bandit.update(a, r) if a in activas else None
                        obs[a].append(r)
            return prs

        def thompson_q(qs):
            for q in qs:
                pos = base_pos + q
                p = stream[pos][1]
                hit = fila_full(p["id"])
                if hit is not None:
                    arch, r = hit
                    bandit.update(arch, r)
                else:
                    rng = random.Random(
                        f"{seed}-exp16-v2-{nb}-{q}")
                    arch = bandit.select(rng)
                    r, nuevo = pull(p, arch, f_full)
                    if nuevo:
                        bandit.update(arch, r)
                        obs[arch].append(r)
                thompson_arms[arch] += 1
                rewards[pos] = r

        prs = probe_q(PROBE_Q1)
        pm1 = {a: mean([prs[(q, a)] for q in PROBE_Q1])
               for a in ARMS3}
        e1 = rx13.regla_v2(pm1, prior_means, activas)
        for q in PROBE_Q1:
            rewards[base_pos + q] = prs[(q, e1)]

        thompson_q(tuple(q for q in THOMPSON_Q if q < PROBE_Q2[0]))

        prs2 = probe_q(PROBE_Q2)
        todo = dict(prs)
        todo.update(prs2)
        qs_all = PROBE_Q1 + PROBE_Q2
        pm2 = {a: mean([todo[(q, a)] for q in qs_all])
               for a in ARMS3}
        e2 = rx13.regla_v2(pm2, prior_means, activas)
        if e1 != e2:
            n_switch += 1
        for q in PROBE_Q2:
            rewards[base_pos + q] = todo[(q, e2)]

        thompson_q(tuple(q for q in THOMPSON_Q if q > PROBE_Q2[-1]))

        # Fix2: poda por media empírica.
        medias_emp = {a: mean(obs[a]) if obs[a] else 0.5
                      for a in ARMS3}
        mejor_m = max(medias_emp[a] for a in activas)
        for a in list(activas):
            if len(activas) <= 2:
                break
            if mejor_m - medias_emp[a] > PODA_GAP:
                cnt_gap[a] += 1
            else:
                cnt_gap[a] = 0
            if cnt_gap[a] >= PODA_BLOQUES:
                activas.remove(a)
                podas.append({"bloque": nb, "brazo": a,
                              "media_emp": round(medias_emp[a], 4),
                              "mejor_emp": round(mejor_m, 4)})

        diag.append({"bloque": nb,
                     "clase": stream[base_pos][0],
                     "mejor_oraculo": orden_bloques[nb]["mejor_oraculo"],
                     "brazos_activos": list(activas),
                     "inicial": e1, "final": e2,
                     "cambio": e1 != e2})
    assert len(rewards) == N_PROB, \
        f"rewards incompletos seed {seed}: {len(rewards)}"
    reg = sum(oracle_reward[pos] - rewards[pos]
              for pos in range(N_PROB))
    return reg, diag, dict(thompson_arms), podas, n_switch


def main():
    ap = argparse.ArgumentParser(description="ALMA-EXP16: multi-seed")
    ap.add_argument("--mock", action="store_true", default=True)
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    t0 = time.time()
    base = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(base, "resultados", "exp16-20260926")
    os.makedirs(out, exist_ok=True)
    prereg_path = os.path.join(out, "preregistro.json")

    cands = rx12.cargar_problemas(base)
    print(f"Candidatos: {len(cands)} problemas (72 sint + 24 gsm8k + 24 mmlu)")

    if args.api:
        backend = rx.VaultBackend()
        print(f"Backend real (vault): {backend.model} vía skill openai")
        limites = {rx.RESOLUCION: 50.0, rx.SELECCION: 1.0,
                   rx.EXPERIMENTACION: 5.0}
    else:
        index = {p["id"]: p for p in cands}
        backend = rx.MockBackend(index, tasas=rx12.TASAS12, seed=1616)
        print("Backend mock (tasas con flip real por diseño)")
        limites = {rx.RESOLUCION: 10.0, rx.SELECCION: 1.0,
                   rx.EXPERIMENTACION: 5.0}

    evaluator = rx.Evaluator(judge=rx.StubJudge())
    store = rx.ExperienceStore(os.path.join(out, "experiencias.jsonl"))
    budget = rx.BudgetManager(limites)

    # --- Oráculo: COPIA de EXP12 (sin medir de nuevo) ---
    print("Copiando oráculo de EXP12 (720 mediciones, sin API)...")
    oracle_mean = copiar_oraculo_exp12(store, base)
    print(f"   oráculo copiado: {len(oracle_mean)} celdas, $0.0000")

    pull, hechos = rx5.make_puller(store, backend, evaluator, budget)

    # --- Stream: mismo orden que EXP12 (verificado) ---
    bloques = rx12.bloques_clase_pura(cands)
    info = []
    for nombre, probs in bloques:
        mejor, medias, margen = rx12.mejor_brazo_bloque(probs, oracle_mean)
        info.append((nombre, mejor, probs, medias, margen))
    ordenado = rx12.ordenar_alternado([(n, m, p) for n, m, p, _, _ in info])
    por_nombre = {n: (m, md, mg) for n, m, _, md, mg in info}
    stream = []
    orden_bloques = []
    for nombre, mejor, probs in ordenado:
        medias, margen = por_nombre[nombre][1], por_nombre[nombre][2]
        for p in probs:
            stream.append((nombre, p))
        orden_bloques.append({"bloque": nombre, "mejor_oraculo": mejor,
                              "margen": round(margen, 4)})
    assert len(stream) == N_PROB
    pre12 = json.load(open(os.path.join(
        base, "resultados", "exp12-20260926", "preregistro.json"),
        encoding="utf-8"))
    ord12 = [(b["bloque"], b["mejor_oraculo"])
             for b in pre12["orden_bloques"]]
    ord16 = [(b["bloque"], b["mejor_oraculo"]) for b in orden_bloques]
    assert ord16 == ord12, f"¡el stream difiere de EXP12! {ord16} vs {ord12}"
    print(f"   stream verificado idéntico a EXP12 "
          f"({[b + ':' + m for b, m in ord16]})")

    oracle_reward = {pos: max(oracle_mean[(p["id"], a)] for a in ARMS3)
                     for pos, (_c, p) in enumerate(stream)}

    # --- Freno de costo (proyección ANTES de las políticas) ---
    rep12 = json.load(open(os.path.join(
        base, "resultados", "exp12-20260926", "report.json"),
        encoding="utf-8"))
    avg_pull = (rep12["costo_total_usd"] / rep12["experiencias_nuevas"]
                if rep12["experiencias_nuevas"] else 0.0)
    n_policy_pulls = PULLS_POR_SEED * len(SEEDS)
    proyeccion = avg_pull * n_policy_pulls * 1.5  # margen de seguridad
    print(f"   proyección de costo total: ${proyeccion:.4f} "
          f"({n_policy_pulls} pulls x ~${avg_pull:.6f} x 1.5)")
    detenido = False
    if args.api and proyeccion > COSTO_STOP:
        detenido = True
        print(f"   ¡FRENO! proyección ${proyeccion:.4f} > ${COSTO_STOP:.2f}.")

    # --- Pre-registro (ANTES de las políticas; seeds y criterio fijos) ---
    diseno = {
        "oraculo": "COPIADO de EXP12 (3 brazos x 2 intentos, 720 mediciones, "
                   "fases 16A-*); sin medir de nuevo",
        "stream": "10 bloques x 12 idéntico a EXP12 (verificado), flip real "
                  "8/9 alternancias",
        "politica": "réplica exacta de ALMA v2 de EXP13 (probe q=0,1,2 + "
                    "re-probe q=10,11; Thompson; prior warm con olvido "
                    "0.5^d; fix1: default = prior-best warm, cambio si "
                    "alternativo supera por > 0.05; fix2: poda de brazos "
                    "muertos). Fases propias por seed: 16B-s{seed}-probe/"
                    "full (pulls frescos por réplica).",
        "seeds": SEEDS,
        "comparacion": "mejor brazo fijo entre los 3 (replay del oráculo)",
        "rng": "pareado por (seed,bloque,q)",
        "freno_costo": "si proyección > US$1,00: detener (exit 2)",
    }
    if os.path.exists(prereg_path):
        with open(prereg_path, encoding="utf-8") as f:
            prereg = json.load(f)
        assert prereg["criterio_exito"] == CRITERIO_EXP16, \
            "¡criterio pre-registrado cambiado! abortar."
        assert prereg["seed"] == SEEDS, \
            "¡seeds pre-registradas cambiadas! abortar."
        print(f"Pre-registro existente verificado. "
              f"Criterio: {CRITERIO_EXP16}")
    else:
        prereg = {
            "experimento": NOMBRE,
            "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "criterio_exito": CRITERIO_EXP16,
            "diseno": diseno,
            "orden_bloques": orden_bloques,
            "seed": SEEDS,
            "modo": "api" if args.api else "mock",
        }
        with open(prereg_path, "w") as f:
            json.dump(prereg, f, indent=2, ensure_ascii=False)
        print(f"Pre-registro escrito (políticas aún no corridas). "
              f"Seeds: {SEEDS}. Criterio: {CRITERIO_EXP16}")

    resultados = {}
    if not detenido:
        for seed in SEEDS:
            print(f"Réplica v2 seed {seed}...")
            reg, diag, sels, podas, n_switch = correr_v2(
                seed, stream, orden_bloques, oracle_reward, pull,
                hechos, store)
            resultados[str(seed)] = {
                "regret": round(reg, 4),
                "cambios_reprobe": n_switch,
                "selecciones": sels,
                "podas": podas,
                "brazos_activos_final": diag[-1]["brazos_activos"],
            }
            print(f"   seed {seed}: regret={reg:.4f}, podas={podas}")

    # --- Referencia: brazos fijos (replay del oráculo, determinista) ---
    reg_fijas = {}
    for a in ARMS3:
        reg_fijas[a] = sum(
            oracle_reward[pos] - oracle_mean[(stream[pos][1]["id"], a)]
            for pos in range(N_PROB))
    mejor_fija = min(reg_fijas, key=lambda a: reg_fijas[a])

    # --- Estadística multi-seed y veredicto de interpretación ---
    if detenido or not resultados:
        pasa = None
        stats = {}
        motivos = [
            "DETENIDO por freno de costo o sin réplicas: no hay números.",
        ]
    else:
        regs = [resultados[str(s)]["regret"] for s in SEEDS]
        stats = {
            "n": len(regs),
            "media": round(statistics.mean(regs), 4),
            "desv": round(statistics.stdev(regs), 4) if len(regs) > 1
            else 0.0,
            "min": round(min(regs), 4),
            "max": round(max(regs), 4),
            "rango": round(max(regs) - min(regs), 4),
        }
        confiables = bool(stats["rango"] < RANGO_MAX)
        pasa = confiables
        motivos = [
            f"regrets por seed: "
            f"{', '.join(f'{s}={resultados[str(s)]['regret']:.4f}' for s in SEEDS)}",
            f"media={stats['media']:.4f} desv={stats['desv']:.4f} "
            f"min={stats['min']:.4f} max={stats['max']:.4f} "
            f"rango={stats['rango']:.4f} (umbral pre-registrado {RANGO_MAX})",
            f"criterio: rango < {RANGO_MAX} => veredictos de una sola "
            f"seed se sostienen; rango > {RANGO_MAX} => NO confiables",
            f"referencia mejor fija ({mejor_fija})={reg_fijas[mejor_fija]:.4f}",
            f"regret fijas: "
            f"{', '.join(f'{a}={reg_fijas[a]:.2f}' for a in ARMS3)}",
        ]

    costo_total = sum(budget.gastado.values())
    report = {
        "preregistro": prereg,
        "regret_por_seed": ({str(s): resultados[str(s)]["regret"]
                             for s in SEEDS} if resultados else {}),
        "estadistica": stats,
        "regret_fijas": {f"fija_{a}": round(v, 4)
                         for a, v in reg_fijas.items()},
        "politicas": resultados,
        "costo_total_usd": round(costo_total, 4),
        "proyeccion_usd": round(proyeccion, 4),
        "detenido_por_costo": detenido,
        "experiencias_nuevas": len(store),
        "store_chain_ok": store.verify_chain(),
        "veredicto": {"pasa": pasa, "criterio": CRITERIO_EXP16,
                       "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO ================")
    for m in motivos:
        print("  " + m)
    print(f"  costo total: ${costo_total:.4f} USD  |  {len(store)} experiencias  "
          f"|  {report['duracion_s']}s")
    if detenido:
        print("  RESULTADO: DETENIDO — proyección de costo superó el freno")
        sys.exit(2)
    print(f"  RESULTADO: {'CONFIABLES' if pasa else 'NO CONFIABLES'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
