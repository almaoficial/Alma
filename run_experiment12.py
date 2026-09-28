#!/usr/bin/env python3
"""ALMA-EXP12: el flip real — ¿el loop le gana al mejor brazo fijo cuando el
mejor brazo SI cambia entre bloques?

Motivación (veredicto EXP11): en EXP11 cot fue el mejor brazo en los 10
bloques (GSM8K+MMLU) -> el brazo fijo ganó por el impuesto de exploración.
EXP12 prueba si ALMA le gana al mejor brazo fijo cuando el mejor brazo
cambia entre bloques de verdad.

Diseño (aprobado por el usuario 26/9 ~08:10):
  - 120 problemas: 72 sintéticos (6 clases x 12: codigo, herramientas,
    puzzles, calculo, qa_multihop, logica) + 24 GSM8K frescos + 24 MMLU
    frescos (índices NO medidos en el oráculo de EXP11; seed 1212,
    documentado en data_exp12/seleccion.json).
  - Fase A: oráculo 3 brazos (single/cot/reflexion) x 2 intentos.
  - Fase B: stream de 10 bloques x 12, cada bloque clase-puro, ORDENADO
    tras el oráculo (greedy determinista) para alternar el mejor brazo
    por bloque según el oráculo medido.
  - Política alma: stack completo de EXP11 (probe q=0,1,2 + re-probe
    q=10,11, 3 brazos; Thompson resto con prior warm y olvido 0.5^d;
    regla default-single, cambio si el mejor alternativo supera por > 0.05).
    Seed 1212, rng pareado por (bloque,q).
  - Comparación: mejor brazo FIJO entre los 3 (replay del oráculo).

Criterio PRE-REGISTRADO (PASS):
  - regret(alma) < regret(mejor fija entre los 3)

El pre-registro se escribe DESPUÉS del oráculo y del freno de costo pero
ANTES de correr la política (el orden del stream depende del oráculo;
el criterio es fijo e independiente).

Restricciones duras:
  - Solo gpt-4o-mini. Si la proyección de costo tras el oráculo supera
    US$1,00, el run se DETIENE (exit 2) y se reporta.
  - La API key nunca se imprime ni se guarda (VaultBackend).

Uso:
    python3 run_experiment12.py --mock [--out /tmp/exp12-mock]
    python3 run_experiment12.py --api
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

NOMBRE = "ALMA-EXP12: el flip real (mejor brazo alterna por bloque)"
ARMS3 = ["single", "cot", "reflexion"]
SEED = 1212
BLOQUE = 12
N_BLOQUES = 10
N_PROB = N_BLOQUES * BLOQUE  # 120
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (10, 11)
THOMPSON_Q = tuple(q for q in range(BLOQUE)
                   if q not in PROBE_Q1 + PROBE_Q2)
assert len(THOMPSON_Q) == 7
FASE_OR1 = "12A-oracle-r1"
FASE_OR2 = "12A-oracle-r2"
FASE_PROBE = "12B-alma-probe"
FASE_FULL = "12B-alma-full"
FASES_REPERTORIO = (FASE_OR1, FASE_OR2, FASE_PROBE, FASE_FULL)
DECAY = 0.5          # olvido exponencial (maquinaria EXP9)
N0 = rx5.N0_PSEUDO   # fuerza del prior warm (EXP4)
MARGEN = rx5.PROBE_MARGEN  # 0.05 (regla EXP3/EXP10)
COSTO_STOP = 1.00    # freno duro de costo total proyectado (USD)

CRITERIO_EXP12 = {"alma_gana_a_mejor_fija": True}

CLASES_SINT = ["codigo", "herramientas", "puzzles",
               "calculo", "qa_multihop", "logica"]

# Mundo sintético para --mock (tasas que alternan el mejor brazo).
TASAS12 = {
    "codigo": {"single": 0.75, "cot": 0.55, "reflexion": 0.60},
    "herramientas": {"single": 0.72, "cot": 0.58, "reflexion": 0.62},
    "puzzles": {"single": 0.68, "cot": 0.60, "reflexion": 0.78},
    "calculo": {"single": 0.55, "cot": 0.78, "reflexion": 0.60},
    "qa_multihop": {"single": 0.58, "cot": 0.75, "reflexion": 0.62},
    "logica": {"single": 0.60, "cot": 0.72, "reflexion": 0.65},
    "gsm8k": {"single": 0.50, "cot": 0.78, "reflexion": 0.70},
    "mmlu": {"single": 0.55, "cot": 0.70, "reflexion": 0.68},
}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def cargar_problemas(base):
    """Lista candidata determinista de 120: 72 sintéticos + 24 gsm8k + 24 mmlu."""
    cands = []
    for clase in CLASES_SINT:
        subdir = "data" if clase in ("calculo", "codigo", "herramientas",
                                     "puzzles", "qa_multihop") else "data_exp2"
        with open(os.path.join(base, subdir, f"{clase}.json"),
                  encoding="utf-8") as f:
            ps = json.load(f)
        assert len(ps) == 12, f"{clase}: {len(ps)}"
        cands.extend(ps)
    with open(os.path.join(base, "data_exp12", "gsm8k_sample.json"),
              encoding="utf-8") as f:
        cands.extend(json.load(f))
    with open(os.path.join(base, "data_exp12", "mmlu_sample.json"),
              encoding="utf-8") as f:
        cands.extend(json.load(f))
    assert len(cands) == N_PROB == 120, f"candidatos: {len(cands)}"
    return cands


def bloques_clase_pura(cands):
    """10 bloques x 12, cada uno clase-puro: 6 sintéticos + 2 gsm8k + 2 mmlu."""
    por_clase = defaultdict(list)
    for p in cands:
        por_clase[p["clase"]].append(p)
    bloques = []
    for clase in CLASES_SINT:
        assert len(por_clase[clase]) == 12
        bloques.append((clase, por_clase[clase]))
    assert len(por_clase["gsm8k"]) == 24 and len(por_clase["mmlu"]) == 24
    bloques.append(("gsm8k-a", por_clase["gsm8k"][:12]))
    bloques.append(("gsm8k-b", por_clase["gsm8k"][12:]))
    bloques.append(("mmlu-a", por_clase["mmlu"][:12]))
    bloques.append(("mmlu-b", por_clase["mmlu"][12:]))
    assert len(bloques) == N_BLOQUES
    return bloques


def mejor_brazo_bloque(problemas, oracle_mean):
    """(mejor brazo, {brazo: media}, margen sobre el segundo)."""
    m = {a: mean([oracle_mean[(p["id"], a)] for p in problemas])
         for a in ARMS3}
    orden = sorted(m, key=lambda a: (-m[a], a))
    return orden[0], m, m[orden[0]] - m[orden[1]]


def ordenar_alternado(bloques_info):
    """Greedy determinista: alterna el mejor brazo por bloque tanto como
    se pueda. bloques_info: [(nombre, mejor_brazo, problemas)]."""
    restantes = list(range(len(bloques_info)))
    orden = []
    while restantes:
        if not orden:
            from collections import Counter
            conteo = Counter(bloques_info[i][1] for i in restantes)
            arm0 = sorted(conteo.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            cand = [i for i in restantes if bloques_info[i][1] == arm0]
        else:
            ultimo = bloques_info[orden[-1]][1]
            otros = [i for i in restantes if bloques_info[i][1] != ultimo]
            if otros:
                from collections import Counter
                conteo = Counter(bloques_info[i][1] for i in otros)
                arm_e = sorted(conteo.items(),
                               key=lambda kv: (-kv[1], kv[0]))[0][0]
                cand = [i for i in otros if bloques_info[i][1] == arm_e]
            else:
                cand = restantes
        elegido = cand[0]  # determinista: primero en orden original
        orden.append(elegido)
        restantes.remove(elegido)
    return [bloques_info[i] for i in orden]


def probe_choice_3(probe_rs):
    """Default single; se cambia al mejor alternativo solo si lo supera
    por el margen (regla EXP10)."""
    m = {a: mean(rs) for a, rs in probe_rs.items()}
    mejor_alt = max([a for a in ARMS3 if a != "single"], key=lambda a: m[a])
    return mejor_alt if m[mejor_alt] - m["single"] > MARGEN else "single"


def repertorio_ponderado(store, stream, pos_limite, decay):
    """{arm: [(reward, peso)]} de observaciones con pos < pos_limite.
    peso = decay^distancia_en_bloques. Solo experiencia real de este
    experimento (fases 12A/12B)."""
    pos_de_pid = {p["id"]: i for i, (_c, p) in enumerate(stream)}
    rep = {a: [] for a in ARMS3}
    for r in store.read_all():
        if r.get("fase") not in FASES_REPERTORIO:
            continue
        if r.get("arch_id") not in ARMS3:
            continue
        pos = pos_de_pid.get(r.get("problema_id", ""), 10 ** 9)
        if pos < pos_limite:
            d = (pos_limite - 1 - pos) // BLOQUE
            rep[r["arch_id"]].append((r["metricas"]["reward"], decay ** d))
    return rep


def bandit_warm_ponderado(rep_w):
    """Prior warm con olvido (maquinaria EXP9)."""
    b = rx.BanditPorClase(ARMS3)
    for a in ARMS3:
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


def main():
    ap = argparse.ArgumentParser(description="ALMA-EXP12: el flip real")
    ap.add_argument("--mock", action="store_true", default=True)
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    t0 = time.time()
    base = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(base, "resultados", "exp12-20260926")
    os.makedirs(out, exist_ok=True)
    prereg_path = os.path.join(out, "preregistro.json")

    cands = cargar_problemas(base)
    print(f"Candidatos: {len(cands)} problemas (72 sint + 24 gsm8k + 24 mmlu)")

    if args.api:
        backend = rx.VaultBackend()
        print(f"Backend real (vault): {backend.model} vía skill openai")
        limites = {rx.RESOLUCION: 50.0, rx.SELECCION: 1.0,
                   rx.EXPERIMENTACION: 5.0}
    else:
        index = {p["id"]: p for p in cands}
        backend = rx.MockBackend(index, tasas=TASAS12, seed=args.seed)
        print("Backend mock (tasas con flip real por diseño)")
        limites = {rx.RESOLUCION: 10.0, rx.SELECCION: 1.0,
                   rx.EXPERIMENTACION: 5.0}

    evaluator = rx.Evaluator(judge=rx.StubJudge())
    store = rx.ExperienceStore(os.path.join(out, "experiencias.jsonl"))
    budget = rx.BudgetManager(limites)
    pull, hechos = rx5.make_puller(store, backend, evaluator, budget)

    # --- Fase 12A: oráculo (3 brazos x 2 intentos, idempotente) ---
    print("Fase 12A: oráculo 3 brazos x 2 intentos (idempotente)...")
    t_or = time.time()
    for fase in (FASE_OR1, FASE_OR2):
        for p in cands:
            for a in ARMS3:
                pull(p, a, fase)
    gastado_or = sum(budget.gastado.values())
    print(f"   oráculo completo ({time.time() - t_or:.0f}s, "
          f"${gastado_or:.4f} gastados)")

    acc = defaultdict(list)
    for (f, pid, a), rw in hechos.items():
        if f in (FASE_OR1, FASE_OR2) and a in ARMS3:
            acc[(pid, a)].append(rw)
    assert len(acc) == N_PROB * 3, f"oráculo incompleto: {len(acc)}/360 celdas"
    oracle_mean = {k: sum(v) / len(v) for k, v in acc.items()}

    # --- Construcción del stream: bloques clase-puros, orden alternado ---
    bloques = bloques_clase_pura(cands)
    info = []
    for nombre, probs in bloques:
        mejor, medias, margen = mejor_brazo_bloque(probs, oracle_mean)
        info.append((nombre, mejor, probs, medias, margen))
    ordenado = ordenar_alternado([(n, m, p) for n, m, p, _, _ in info])
    # re-adjuntar medias/márgenes en el orden final
    por_nombre = {n: (m, md, mg) for n, m, _, md, mg in info}
    stream = []
    orden_bloques = []
    for nombre, mejor, probs in ordenado:
        medias, margen = por_nombre[nombre][1], por_nombre[nombre][2]
        for p in probs:
            stream.append((nombre, p))
        orden_bloques.append({"bloque": nombre, "mejor_oraculo": mejor,
                              "margen": round(margen, 4),
                              "medias": {a: round(medias[a], 4)
                                         for a in ARMS3}})
    assert len(stream) == N_PROB
    altern = sum(1 for i in range(1, N_BLOQUES)
                 if orden_bloques[i]["mejor_oraculo"]
                 != orden_bloques[i - 1]["mejor_oraculo"])
    brazos_en_juego = sorted(set(b["mejor_oraculo"] for b in orden_bloques))
    print(f"   orden de bloques: "
          f"{[b['bloque'] + ':' + b['mejor_oraculo'] for b in orden_bloques]}")
    print(f"   alternancias: {altern}/{N_BLOQUES - 1}; "
          f"brazos en juego: {brazos_en_juego}")

    oracle_reward = {pos: max(oracle_mean[(p["id"], a)] for a in ARMS3)
                     for pos, (_c, p) in enumerate(stream)}

    # --- Freno de costo: proyección antes de la política ---
    n_oracle_pulls = N_PROB * 3 * 2
    avg_pull = gastado_or / n_oracle_pulls if n_oracle_pulls else 0.0
    n_policy_pulls = (N_BLOQUES * (len(PROBE_Q1) + len(PROBE_Q2)) * 3
                      + N_BLOQUES * len(THOMPSON_Q))
    policy_est = avg_pull * n_policy_pulls * 1.5  # factor de seguridad
    proyeccion = gastado_or + policy_est
    print(f"   proyección de costo total: ${proyeccion:.4f} "
          f"(oráculo ${gastado_or:.4f} + política ~${policy_est:.4f})")
    detenido = False
    if args.api and proyeccion > COSTO_STOP:
        detenido = True
        print(f"   ¡FRENO! proyección ${proyeccion:.4f} > ${COSTO_STOP:.2f}: "
              "deteniendo antes de la política.")

    # --- Pre-registro (ANTES de la fase B; el criterio es fijo) ---
    diseno = {
        "problemas": "72 sintéticos (6 clases x 12) + 24 GSM8K frescos + "
                     "24 MMLU frescos (0 reutilizados del oráculo de EXP11); "
                     "selección seed 1212 en data_exp12/seleccion.json",
        "stream": "10 bloques x 12, clase-puros; ordenados tras el oráculo "
                  "(greedy determinista) para alternar el mejor brazo",
        "oraculo": "3 brazos x 2 intentos por problema (fases 12A-oracle-r1/r2)",
        "politica": "probe q=0,1,2 + re-probe q=10,11 (3 brazos) + "
                    "Thompson resto; prior warm con olvido 0.5^d; "
                    "regla: default single, cambio si mejor alt. supera por > 0.05",
        "comparacion": "mejor brazo fijo entre los 3 (replay del oráculo)",
        "rng": "pareado por (bloque,q), seed 1212",
        "freno_costo": "si proyección tras oráculo > US$1,00: detener (exit 2)",
    }
    if os.path.exists(prereg_path):
        with open(prereg_path, encoding="utf-8") as f:
            prereg = json.load(f)
        assert prereg["criterio_exito"] == CRITERIO_EXP12, \
            "¡criterio pre-registrado cambiado! abortar."
        print(f"Pre-registro existente verificado. Criterio: {CRITERIO_EXP12}")
    else:
        prereg = {
            "experimento": NOMBRE,
            "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "criterio_exito": CRITERIO_EXP12,
            "diseno": diseno,
            "orden_bloques": orden_bloques,
            "alternancias": f"{altern}/{N_BLOQUES - 1}",
            "brazos_en_juego": brazos_en_juego,
            "seed": args.seed,
            "modo": "api" if args.api else "mock",
        }
        with open(prereg_path, "w", encoding="utf-8") as f:
            json.dump(prereg, f, indent=2, ensure_ascii=False)
        print(f"Pre-registro escrito (fase B aún no corrida). "
              f"Criterio: {CRITERIO_EXP12}")

    # --- Política alma ---
    rewards = {}
    diag = []
    n_switch = 0
    thompson_arms = defaultdict(int)
    if not detenido:
        print("Política alma (probe continuo + re-probe + Thompson con olvido)...")

        def fila_full(pid):
            for a in ARMS3:
                if (FASE_FULL, pid, a) in hechos:
                    return a, hechos[(FASE_FULL, pid, a)]
            return None

        for nb in range(N_BLOQUES):
            base_pos = nb * BLOQUE
            bandit = bandit_warm_ponderado(
                repertorio_ponderado(store, stream, base_pos, DECAY))
            prior_means = bandit.means()

            def probe_q(qs):
                prs = {}
                for q in qs:
                    p = stream[base_pos + q][1]
                    for a in ARMS3:
                        key = (FASE_PROBE, p["id"], a)
                        if key in hechos:
                            r, nuevo = hechos[key], False
                        else:
                            r, nuevo = pull(p, a, FASE_PROBE)
                        prs[(q, a)] = r
                        if nuevo:
                            bandit.update(a, r)
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
                        rng = random.Random(f"{args.seed}-exp12-{nb}-{q}")
                        arch = bandit.select(rng)
                        r, nuevo = pull(p, arch, FASE_FULL)
                        if nuevo:
                            bandit.update(arch, r)
                    thompson_arms[arch] += 1
                    rewards[pos] = r

            prs = probe_q(PROBE_Q1)
            e1 = probe_choice_3(
                {a: [prs[(q, a)] for q in PROBE_Q1] for a in ARMS3})
            for q in PROBE_Q1:
                rewards[base_pos + q] = prs[(q, e1)]

            thompson_q(tuple(q for q in THOMPSON_Q if q < PROBE_Q2[0]))

            prs2 = probe_q(PROBE_Q2)
            todo = dict(prs)
            todo.update(prs2)
            qs_all = PROBE_Q1 + PROBE_Q2
            e2 = probe_choice_3(
                {a: [todo[(q, a)] for q in qs_all] for a in ARMS3})
            if e1 != e2:
                n_switch += 1
            for q in PROBE_Q2:
                rewards[base_pos + q] = todo[(q, e2)]

            thompson_q(tuple(q for q in THOMPSON_Q if q > PROBE_Q2[-1]))

            diag.append({"bloque": nb,
                         "clase": stream[base_pos][0],
                         "mejor_oraculo": orden_bloques[nb]["mejor_oraculo"],
                         "medias_oraculo": orden_bloques[nb]["medias"],
                         "prior_means": prior_means,
                         "inicial": e1, "final": e2,
                         "cambio": e1 != e2})
        assert len(rewards) == N_PROB, f"rewards incompletos: {len(rewards)}"

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
        pasa, reg_alma = None, None
        motivos = [
            f"DETENIDO por freno de costo: proyección ${proyeccion:.4f} > "
            f"${COSTO_STOP:.2f} (oráculo real gastado: ${gastado_or:.4f})",
            "No se corrió la política; no hay veredicto PASS/FAIL.",
        ]
    else:
        reg_alma = sum(oracle_reward[pos] - rewards[pos]
                       for pos in range(N_PROB))
        pasa = bool(reg_alma < reg_fijas[mejor_fija])
        motivos = [
            f"regret alma={reg_alma:.4f} vs mejor fija ({mejor_fija})="
            f"{reg_fijas[mejor_fija]:.4f} "
            f"(diff={reg_alma - reg_fijas[mejor_fija]:+.4f})",
            f"regret fijas: "
            f"{', '.join(f'{a}={reg_fijas[a]:.2f}' for a in ARMS3)}",
            f"verdad por bloque: {verdad_bloque}",
            f"decisión final por bloque: {[d['final'] for d in diag]}",
            f"cambios tras re-probe: {n_switch}/{N_BLOQUES}",
            f"brazos usados en Thompson: {dict(thompson_arms)}",
            f"alternancias reales del stream: {altern}/{N_BLOQUES - 1} "
            f"(brazos en juego: {brazos_en_juego})",
        ]

    costo_total = sum(budget.gastado.values())
    report = {
        "preregistro": prereg,
        "regret_total": (
            {"alma": round(reg_alma, 4),
             **{f"fija_{a}": round(v, 4) for a, v in reg_fijas.items()}}
            if reg_alma is not None else
            {f"fija_{a}": round(v, 4) for a, v in reg_fijas.items()}),
        "verdad_bloque": verdad_bloque,
        "diagnostico_bloques": diag,
        "costo_total_usd": round(costo_total, 4),
        "proyeccion_usd": round(proyeccion, 4),
        "detenido_por_costo": detenido,
        "experiencias_nuevas": len(store),
        "store_chain_ok": store.verify_chain(),
        "veredicto": {"pasa": pasa, "criterio": CRITERIO_EXP12,
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
        print("  RESULTADO:", "PASS — el loop gana cuando el mundo se mueve"
              if pasa else "FAIL — no le gana a la mejor fija ni con flip real")
    print("===========================================")
    return 0 if pasa else (2 if detenido else 1)


if __name__ == "__main__":
    sys.exit(main())
