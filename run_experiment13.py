#!/usr/bin/env python3
"""ALMA-EXP13: ¿los fixes corrigen los patrones sistemáticos del FAIL de EXP12?

Motivación (veredicto EXP12, 26/9): dos patrones sistemáticos.
  (1) El default-single del probe pisó un prior correcto en bloques-cot:
      la regla "default single, cambio si alternativo supera por > 0.05"
      eligió single en bloques donde el prior warm ya sabía que cot era
      mejor.
  (2) Thompson desperdició 18 pulls en reflexion, un brazo muerto que nunca
      fue el mejor en ningún bloque de ningún experimento.

Diseño (aprobado por el usuario 26/9 ~09:27):
  - Reutiliza data_exp12/ (120 problemas), el oráculo 3 brazos x 2 intentos
    de EXP12 (copiado al store nuevo con fases 13A-*, SIN medir de nuevo) y
    el mismo stream de 10 bloques x 12 con flip real (orden verificado
    idéntico al de EXP12).
  - Tres políticas sobre el mismo stream:
      a. ALMA v1 (control): réplica exacta de la política de EXP12
         (probe q=0,1,2 + re-probe q=10,11; Thompson; prior warm con olvido
         0.5^d; default single, cambio si mejor alt. supera por > 0.05).
      b. ALMA v2: mismo stack con DOS fixes:
           fix1: default = brazo con mejor media del prior; el probe solo
                 cambia si un alternativo supera AL PRIOR-BEST por > 0.05.
           fix2: poda de brazos: si la media empírica de un brazo queda por
                 debajo de la del mejor brazo por > 0.10 durante 2 bloques
                 consecutivos, se elimina del Thompson por el resto del
                 stream (nunca podar por debajo de 2 brazos activos).
      c. Mejor brazo fijo entre los 3 según el oráculo (replay).
  - Seed 1313 para el RNG de las políticas (draws frescos de Thompson, no
    repiten los de EXP12).

Criterio PRE-REGISTRADO (PASS):
  - regret(v2) < regret(v1) AND regret(v2) < regret(mejor fija)

El pre-registro se escribe ANTES de correr las políticas (no hay oráculo
nuevo; el stream ya está fijado por EXP12).

Restricciones duras:
  - Solo gpt-4o-mini. Si la proyección de costo supera US$1,00: detener
    (exit 2) y reportar.
  - La API key nunca se imprime ni se guarda (VaultBackend).

Uso:
    python3 run_experiment13.py --mock [--out /tmp/exp13-mock]
    python3 run_experiment13.py --api
"""
import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_experiment as rx
import run_experiment5 as rx5
import run_experiment12 as rx12

NOMBRE = "ALMA-EXP13: fixes contra los patrones sistemáticos de EXP12"
ARMS3 = ["single", "cot", "reflexion"]
SEED = 1313
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
FASE_OR1, FASE_OR2 = "13A-oracle-r1", "13A-oracle-r2"
FASE_V1_PROBE, FASE_V1_FULL = "13B-v1-probe", "13B-v1-full"
FASE_V1 = (FASE_OR1, FASE_OR2, FASE_V1_PROBE, FASE_V1_FULL)
FASE_V2_PROBE, FASE_V2_FULL = "13B-v2-probe", "13B-v2-full"
FASE_V2 = (FASE_OR1, FASE_OR2, FASE_V2_PROBE, FASE_V2_FULL)
DECAY = 0.5          # olvido exponencial (maquinaria EXP9)
N0 = rx5.N0_PSEUDO   # fuerza del prior warm (EXP4)
MARGEN = rx5.PROBE_MARGEN  # 0.05
PODA_GAP = 0.10      # fix2: gap de media empírica para podar
PODA_BLOQUES = 2     # fix2: bloques consecutivos con gap
COSTO_STOP = 1.00    # freno duro de costo total proyectado (USD)

CRITERIO_EXP13 = {"v2_gana_a_v1_y_a_mejor_fija": True}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def copiar_oraculo_exp12(store, base):
    """Copia las 720 mediciones del oráculo de EXP12 al store nuevo con
    fases 13A-*. Sin llamadas a la API. Devuelve {(pid, arm): media}."""
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


def repertorio_ponderado_fases(store, stream, pos_limite, decay, fases):
    """Como rx12.repertorio_ponderado pero con fases parametrizadas."""
    pos_de_pid = {p["id"]: i for i, (_c, p) in enumerate(stream)}
    rep = {a: [] for a in ARMS3}
    for r in store.read_all():
        if r.get("fase") not in fases:
            continue
        if r.get("arch_id") not in ARMS3:
            continue
        pos = pos_de_pid.get(r.get("problema_id", ""), 10 ** 9)
        if pos < pos_limite:
            d = (pos_limite - 1 - pos) // BLOQUE
            rep[r["arch_id"]].append((r["metricas"]["reward"], decay ** d))
    return rep


def bandit_warm_ponderado_arms(rep_w, arms):
    """Prior warm con olvido sobre un subconjunto de brazos."""
    b = rx.BanditPorClase(list(arms))
    for a in arms:
        obs = rep_w.get(a, [])
        if obs:
            sw = sum(w for _, w in obs)
            m = sum(r * w for r, w in obs) / sw if sw else 0.5
        else:
            m = 0.5
        b.alpha[a] = 1.0 + N0 * m
        b.beta[a] = 1.0 + N0 * (1.0 - m)
        b.pulls[a] = N0
    return b


def regla_v1(probe_means):
    """Réplica exacta EXP12: default single; cambio si el mejor alternativo
    lo supera por el margen."""
    mejor_alt = max([a for a in ARMS3 if a != "single"],
                    key=lambda a: probe_means[a])
    return (mejor_alt
            if probe_means[mejor_alt] - probe_means["single"] > MARGEN
            else "single")


def regla_v2(probe_means, prior_means, activas):
    """Fix1: default = prior-best (entre brazos activos); cambio solo si un
    alternativo supera AL PRIOR-BEST por el margen."""
    default = max(activas, key=lambda a: prior_means[a])
    cands = [a for a in activas if a != default]
    mejor_alt = max(cands, key=lambda a: probe_means[a]) if cands else default
    return (mejor_alt
            if probe_means[mejor_alt] - probe_means[default] > MARGEN
            else default)


def main():
    ap = argparse.ArgumentParser(description="ALMA-EXP13: fixes vs EXP12")
    ap.add_argument("--mock", action="store_true", default=True)
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    t0 = time.time()
    base = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(base, "resultados", "exp13-20260926")
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
        backend = rx.MockBackend(index, tasas=rx12.TASAS12, seed=args.seed)
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
    # Verificar idéntico a EXP12.
    pre12 = json.load(open(os.path.join(
        base, "resultados", "exp12-20260926", "preregistro.json"),
        encoding="utf-8"))
    ord12 = [(b["bloque"], b["mejor_oraculo"])
             for b in pre12["orden_bloques"]]
    ord13 = [(b["bloque"], b["mejor_oraculo"]) for b in orden_bloques]
    assert ord13 == ord12, f"¡el stream difiere de EXP12! {ord13} vs {ord12}"
    print(f"   stream verificado idéntico a EXP12 "
          f"({[b + ':' + m for b, m in ord13]})")

    oracle_reward = {pos: max(oracle_mean[(p["id"], a)] for a in ARMS3)
                     for pos, (_c, p) in enumerate(stream)}

    # --- Freno de costo (proyección ANTES de las políticas) ---
    # Referencia EXP12: costo_total / experiencias_nuevas.
    rep12 = json.load(open(os.path.join(
        base, "resultados", "exp12-20260926", "report.json"),
        encoding="utf-8"))
    avg_pull = (rep12["costo_total_usd"] / rep12["experiencias_nuevas"]
                if rep12["experiencias_nuevas"] else 0.0)
    n_policy_pulls = (N_BLOQUES * (len(PROBE_Q1) + len(PROBE_Q2)) * 3
                      + N_BLOQUES * len(THOMPSON_Q))
    policy_est = avg_pull * n_policy_pulls * 2 * 1.5  # 2 políticas + margen
    proyeccion = policy_est  # oráculo copiado: $0
    print(f"   proyección de costo total: ${proyeccion:.4f} "
          f"({n_policy_pulls * 2} pulls x ~${avg_pull:.6f} x 1.5)")
    detenido = False
    if args.api and proyeccion > COSTO_STOP:
        detenido = True
        print(f"   ¡FRENO! proyección ${proyeccion:.4f} > ${COSTO_STOP:.2f}.")

    # --- Pre-registro (ANTES de las políticas; criterio fijo) ---
    diseno = {
        "oraculo": "COPIADO de EXP12 (3 brazos x 2 intentos, 720 mediciones, "
                   "fases 13A-*); sin medir de nuevo",
        "stream": "10 bloques x 12 idéntico a EXP12 (verificado), flip real "
                  "8/9 alternancias, brazos en juego: cot/single",
        "politica_v1_control": "réplica exacta de EXP12 (probe q=0,1,2 + "
                               "re-probe q=10,11; Thompson; prior warm con "
                               "olvido 0.5^d; default single, cambio si "
                               "mejor alt. supera por > 0.05)",
        "politica_v2": "mismo stack + fix1 (default = prior-best; cambio "
                       "solo si alternativo supera AL PRIOR-BEST por > 0.05) "
                       "+ fix2 (poda: media empírica < mejor - 0.10 durante "
                       "2 bloques consecutivos -> fuera del Thompson; "
                       "mínimo 2 brazos activos)",
        "comparacion": "mejor brazo fijo entre los 3 (replay del oráculo)",
        "rng": f"pareado por (politica,bloque,q), seed {args.seed}",
        "freno_costo": "si proyección > US$1,00: detener (exit 2)",
    }
    if os.path.exists(prereg_path):
        with open(prereg_path, encoding="utf-8") as f:
            prereg = json.load(f)
        assert prereg["criterio_exito"] == CRITERIO_EXP13, \
            "¡criterio pre-registrado cambiado! abortar."
        print(f"Pre-registro existente verificado. Criterio: {CRITERIO_EXP13}")
    else:
        prereg = {
            "experimento": NOMBRE,
            "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "criterio_exito": CRITERIO_EXP13,
            "diseno": diseno,
            "orden_bloques": orden_bloques,
            "seed": args.seed,
            "modo": "api" if args.api else "mock",
        }
        with open(prereg_path, "w", encoding="utf-8") as f:
            json.dump(prereg, f, indent=2, ensure_ascii=False)
        print(f"Pre-registro escrito (políticas aún no corridas). "
              f"Criterio: {CRITERIO_EXP13}")

    resultados = {}
    if not detenido:
        for tag, fases, es_v2 in (("v1", FASE_V1, False),
                                  ("v2", FASE_V2, True)):
            f_probe, f_full = fases[2], fases[3]
            print(f"Política alma {tag} "
                  f"({'con fixes' if es_v2 else 'control EXP12'})...")
            rewards = {}
            diag = []
            n_switch = 0
            thompson_arms = defaultdict(int)
            obs = {a: [] for a in ARMS3}   # medias empíricas (fix2)
            activas = list(ARMS3)
            podas = []
            cnt_gap = {a: 0 for a in ARMS3}
            desacuerdos = 0
            desacuerdo_bien_v2 = 0

            def fila_full(pid):
                for a in activas:
                    if (f_full, pid, a) in hechos:
                        return a, hechos[(f_full, pid, a)]
                return None

            for nb in range(N_BLOQUES):
                base_pos = nb * BLOQUE
                bandit = bandit_warm_ponderado_arms(
                    repertorio_ponderado_fases(store, stream, base_pos,
                                              DECAY, fases), activas)
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
                                f"{args.seed}-exp13-{tag}-{nb}-{q}")
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
                c_v1 = regla_v1(pm1)
                c_v2 = regla_v2(pm1, prior_means, activas)
                e1 = c_v2 if es_v2 else c_v1
                if c_v1 != c_v2:
                    desacuerdos += 1
                    verdad = orden_bloques[nb]["mejor_oraculo"]
                    if (c_v2 == verdad) != (c_v1 == verdad):
                        if c_v2 == verdad:
                            desacuerdo_bien_v2 += 1
                        else:
                            desacuerdo_bien_v2 -= 1
                for q in PROBE_Q1:
                    rewards[base_pos + q] = prs[(q, e1)]

                thompson_q(tuple(q for q in THOMPSON_Q if q < PROBE_Q2[0]))

                prs2 = probe_q(PROBE_Q2)
                todo = dict(prs)
                todo.update(prs2)
                qs_all = PROBE_Q1 + PROBE_Q2
                pm2 = {a: mean([todo[(q, a)] for q in qs_all])
                       for a in ARMS3}
                c_v1b = regla_v1(pm2)
                c_v2b = regla_v2(pm2, prior_means, activas)
                e2 = c_v2b if es_v2 else c_v1b
                if c_v1b != c_v2b:
                    desacuerdos += 1
                    verdad = orden_bloques[nb]["mejor_oraculo"]
                    if (c_v2b == verdad) != (c_v1b == verdad):
                        if c_v2b == verdad:
                            desacuerdo_bien_v2 += 1
                        else:
                            desacuerdo_bien_v2 -= 1
                if e1 != e2:
                    n_switch += 1
                for q in PROBE_Q2:
                    rewards[base_pos + q] = todo[(q, e2)]

                thompson_q(tuple(q for q in THOMPSON_Q if q > PROBE_Q2[-1]))

                # Fix2: poda por media empírica (solo v2).
                if es_v2:
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
                             "prior_means": prior_means,
                             "brazos_activos": list(activas),
                             "eleccion_regla_v1": c_v1,
                             "eleccion_regla_v2": c_v2,
                             "inicial": e1, "final": e2,
                             "cambio": e1 != e2})
            assert len(rewards) == N_PROB, \
                f"rewards {tag} incompletos: {len(rewards)}"
            reg = sum(oracle_reward[pos] - rewards[pos]
                      for pos in range(N_PROB))
            resultados[tag] = {
                "regret": round(reg, 4),
                "diagnostico": diag,
                "cambios_reprobe": n_switch,
                "thompson_arms": dict(thompson_arms),
                "podas": podas,
                "brazos_activos_final": list(activas),
                "desacuerdos_reglas": desacuerdos,
                "desacuerdo_saldo_v2": desacuerdo_bien_v2,
            }
            print(f"   {tag}: regret={reg:.4f}, podas={podas}, "
                  f"thompson={dict(thompson_arms)}")

    # --- Veredicto ---
    reg_fijas = {}
    for a in ARMS3:
        reg_fijas[a] = sum(
            oracle_reward[pos] - oracle_mean[(stream[pos][1]["id"], a)]
            for pos in range(N_PROB))
    mejor_fija = min(reg_fijas, key=lambda a: reg_fijas[a])

    verdad_bloque = []
    for nb in range(N_BLOQUES):
        s = {a: sum(oracle_mean[(stream[nb * BLOQUE + q][1]["id"], a)]
                    for q in range(BLOQUE)) for a in ARMS3}
        verdad_bloque.append(max(s, key=lambda a: s[a]))

    if detenido:
        pasa = None
        motivos = [
            f"DETENIDO por freno de costo: proyección ${proyeccion:.4f} > "
            f"${COSTO_STOP:.2f}",
            "No se corrieron las políticas; no hay veredicto PASS/FAIL.",
        ]
    else:
        r1 = resultados["v1"]["regret"]
        r2 = resultados["v2"]["regret"]
        rf = reg_fijas[mejor_fija]
        pasa = bool(r2 < r1 and r2 < rf)
        motivos = [
            f"regret v2={r2:.4f} vs v1={r1:.4f} (diff={r2 - r1:+.4f}) "
            f"vs mejor fija ({mejor_fija})={rf:.4f} (diff={r2 - rf:+.4f})",
            f"regret fijas: "
            f"{', '.join(f'{a}={reg_fijas[a]:.2f}' for a in ARMS3)}",
            f"verdad por bloque: {verdad_bloque}",
            f"decisión final v1 por bloque: "
            f"{[d['final'] for d in resultados['v1']['diagnostico']]}",
            f"decisión final v2 por bloque: "
            f"{[d['final'] for d in resultados['v2']['diagnostico']]}",
            f"podas v2: {resultados['v2']['podas'] or 'ninguna'}",
            f"brazos Thompson v1: {resultados['v1']['thompson_arms']} | "
            f"v2: {resultados['v2']['thompson_arms']}",
            f"desacuerdos entre reglas (probe+reprobe): "
            f"{resultados['v2']['desacuerdos_reglas']}, saldo a favor de "
            f"la regla v2: {resultados['v2']['desacuerdo_saldo_v2']:+d} "
            f"(+1 cuando solo v2 acertó la verdad, -1 cuando solo v1)",
        ]

    costo_total = sum(budget.gastado.values())
    report = {
        "preregistro": prereg,
        "regret_total": {
            **({f"alma_{t}": v["regret"]
                for t, v in resultados.items()} if resultados else {}),
            **{f"fija_{a}": round(v, 4) for a, v in reg_fijas.items()},
        },
        "verdad_bloque": verdad_bloque,
        "politicas": resultados,
        "costo_total_usd": round(costo_total, 4),
        "proyeccion_usd": round(proyeccion, 4),
        "detenido_por_costo": detenido,
        "experiencias_nuevas": len(store),
        "store_chain_ok": store.verify_chain(),
        "veredicto": {"pasa": pasa, "criterio": CRITERIO_EXP13,
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
    else:
        print("  RESULTADO:", "PASS — v2 gana a v1 y a la mejor fija"
              if pasa else "FAIL — v2 no supera a v1 y a la mejor fija")
    print("===========================================")
    return 0 if pasa else (2 if detenido else 1)


if __name__ == "__main__":
    sys.exit(main())
