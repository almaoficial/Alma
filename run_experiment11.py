#!/usr/bin/env python3
"""ALMA-EXP11: el motor en problemas duros reales (benchmarks públicos).

EXP1-10 corrieron sobre streams de juguete (problemas sintéticos del
prototipo, 12 por clase). EXP11 pone la misma maquinaria —probe continuo
+ re-probe + Thompson con prior con olvido— sobre 200 problemas REALES:
100 de GSM8K (matemática, test split) y 100 de MMLU difícil (test split,
10 materias duras). Si el loop no rinde acá, no rinde en serio.

Diseño (aprobado por el usuario):
  - Stream no estacionario por construcción: bloques 0-4 = GSM8K,
    bloques 5-9 = MMLU (flip de distribución a la mitad, estilo EXP9).
    10 bloques x 20 problemas = 200. Datos en data_exp11/ (selección
    determinista seed 999, documentada en seleccion.json).
  - Graders: GSM8K -> número tras "####"; MMLU -> letra A-D. Ambos por
    exact-match (evaluator existente, verificador "exact").
  - Oráculo: 3 brazos x 2 intentos por problema (fases 11A-oracle-r1/r2;
    precedente EXP8/EXP10).
  - Política alma: probe q=0,1,2 + re-probe q=10,11 (los 3 brazos),
    Thompson en el resto (q=3..9, 12..19), prior warm con olvido
    (decaimiento 0.5^d, maquinaria EXP9), regla de decisión EXP10
    (default single; cambio si el mejor alternativo supera por > 0.05).
  - Comparación: mejor brazo FIJO entre los 3 (replay del oráculo).

Criterio PRE-REGISTRADO (PASS):
  - regret(alma) < regret(mejor fija entre los 3)

Restricciones duras:
  - Solo gpt-4o-mini. Si la proyección de costo tras el oráculo supera
    US$1,00, el run se DETIENE (exit 2) y se reporta.
  - La API key nunca se imprime ni se guarda (VaultBackend).

Uso:
    python3 run_experiment11.py --mock [--out /tmp/exp11-mock]
    python3 run_experiment11.py --api
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

NOMBRE = "ALMA-EXP11: motor en benchmarks reales (GSM8K + MMLU)"
ARMS3 = ["single", "cot", "reflexion"]
SEED = 999
BLOQUE = 20
N_BLOQUES = 10
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (10, 11)
THOMPSON_Q = tuple(q for q in range(BLOQUE)
                   if q not in PROBE_Q1 + PROBE_Q2)
assert len(THOMPSON_Q) == 15
FASE_OR1 = "11A-oracle-r1"
FASE_OR2 = "11A-oracle-r2"
FASE_PROBE = "11B-alma-probe"
FASE_FULL = "11B-alma-full"
FASES_REPERTORIO = (FASE_OR1, FASE_OR2, FASE_PROBE, FASE_FULL)
DECAY = 0.5          # olvido exponencial (maquinaria EXP9)
N0 = rx5.N0_PSEUDO   # fuerza del prior warm (EXP4)
MARGEN = rx5.PROBE_MARGEN  # 0.05 (regla EXP3/EXP10)
COSTO_STOP = 1.00    # freno duro de costo total proyectado (USD)

CRITERIO_EXP11 = {"alma_gana_a_mejor_fija": True}

# Mundo sintético para --mock (solo smoke test del pipeline).
TASAS11 = {
    "gsm8k": {"single": 0.50, "cot": 0.78, "reflexion": 0.80},
    "mmlu": {"single": 0.72, "cot": 0.70, "reflexion": 0.74},
}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def cargar_problemas(base):
    with open(os.path.join(base, "data_exp11", "gsm8k_sample.json"),
              encoding="utf-8") as f:
        gsm = json.load(f)
    with open(os.path.join(base, "data_exp11", "mmlu_sample.json"),
              encoding="utf-8") as f:
        mmlu = json.load(f)
    assert len(gsm) == 100 and len(mmlu) == 100
    return gsm, mmlu


def construir_stream(gsm, mmlu):
    """Bloques 0-4: GSM8K; bloques 5-9: MMLU. Flip a la mitad."""
    stream = []
    for b in range(5):
        for p in gsm[b * BLOQUE:(b + 1) * BLOQUE]:
            stream.append(("gsm8k", p))
    for b in range(5):
        for p in mmlu[b * BLOQUE:(b + 1) * BLOQUE]:
            stream.append(("mmlu", p))
    assert len(stream) == N_BLOQUES * BLOQUE == 200
    return stream


def probe_choice_3(probe_rs):
    """Default single; se cambia al mejor alternativo solo si lo supera
    por el margen (regla EXP10, generalización de EXP3)."""
    m = {a: mean(rs) for a, rs in probe_rs.items()}
    mejor_alt = max([a for a in ARMS3 if a != "single"], key=lambda a: m[a])
    return mejor_alt if m[mejor_alt] - m["single"] > MARGEN else "single"


def repertorio_ponderado(store, stream, pos_limite, decay):
    """{arm: [(reward, peso)]} de observaciones con pos < pos_limite.
    peso = decay^distancia_en_bloques. Solo experiencia real de este
    experimento (fases 11A/11B)."""
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
    """Prior warm con olvido (maquinaria EXP9): la media es ponderada por
    decaimiento, la fuerza del prior (N0) se mantiene constante."""
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
    ap = argparse.ArgumentParser(description="ALMA-EXP11: benchmarks reales")
    ap.add_argument("--mock", action="store_true", default=True)
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    t0 = time.time()
    base = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(base, "resultados", "exp11-20260926")
    os.makedirs(out, exist_ok=True)

    # Pre-registro: si ya existe (escrito antes del run --api), se verifica
    # que el criterio esté intacto; si no, se escribe ahora.
    prereg_path = os.path.join(out, "preregistro.json")
    diseno = {
        "problemas": "100 GSM8K test + 100 MMLU test (10 materias duras); "
                     "selección seed 999 en data_exp11/seleccion.json",
        "stream": "10 bloques x 20; bloques 0-4 GSM8K, 5-9 MMLU "
                  "(flip de distribución a la mitad)",
        "oraculo": "3 brazos x 2 intentos por problema (fases 11A-oracle-r1/r2)",
        "politica": "probe q=0,1,2 + re-probe q=10,11 (3 brazos) + "
                    "Thompson resto; prior warm con olvido 0.5^d; "
                    "regla: default single, cambio si mejor alt. supera por > 0.05",
        "comparacion": "mejor brazo fijo entre los 3 (replay del oráculo)",
        "rng": "pareado por (bloque,q), seed 999",
        "freno_costo": "si proyección tras oráculo > US$1,00: detener (exit 2)",
    }
    if os.path.exists(prereg_path):
        with open(prereg_path, encoding="utf-8") as f:
            prereg = json.load(f)
        assert prereg["criterio_exito"] == CRITERIO_EXP11, \
            "¡criterio pre-registrado cambiado! abortar."
        print(f"Pre-registro existente verificado. Criterio: {CRITERIO_EXP11}")
    else:
        prereg = {
            "experimento": NOMBRE,
            "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "criterio_exito": CRITERIO_EXP11,
            "diseno": diseno,
            "seed": args.seed,
            "modo": "api" if args.api else "mock",
        }
        with open(prereg_path, "w", encoding="utf-8") as f:
            json.dump(prereg, f, indent=2, ensure_ascii=False)
        print(f"Pre-registro escrito. Criterio: {CRITERIO_EXP11}")

    gsm, mmlu = cargar_problemas(base)
    stream = construir_stream(gsm, mmlu)
    print(f"Stream: {len(stream)} problemas "
          f"({sum(1 for c, _ in stream if c == 'gsm8k')} GSM8K + "
          f"{sum(1 for c, _ in stream if c == 'mmlu')} MMLU)")

    if args.api:
        backend = rx.VaultBackend()
        print(f"Backend real (vault): {backend.model} vía skill openai")
        limites = {rx.RESOLUCION: 50.0, rx.SELECCION: 1.0,
                   rx.EXPERIMENTACION: 5.0}
    else:
        index = {p["id"]: p for _c, p in stream}
        backend = rx.MockBackend(index, tasas=TASAS11, seed=args.seed)
        print("Backend mock (tasas sintéticas gsm8k/mmlu)")
        limites = {rx.RESOLUCION: 10.0, rx.SELECCION: 1.0,
                   rx.EXPERIMENTACION: 5.0}

    evaluator = rx.Evaluator(judge=rx.StubJudge())
    store = rx.ExperienceStore(os.path.join(out, "experiencias.jsonl"))
    budget = rx.BudgetManager(limites)
    pull, hechos = rx5.make_puller(store, backend, evaluator, budget)

    # --- Fase 11A: oráculo (3 brazos x 2 intentos, idempotente) ---
    print("Fase 11A: oráculo 3 brazos x 2 intentos (idempotente)...")
    t_or = time.time()
    for fase in (FASE_OR1, FASE_OR2):
        for _c, p in stream:
            for a in ARMS3:
                pull(p, a, fase)
    gastado_or = sum(budget.gastado.values())
    print(f"   oráculo completo ({time.time() - t_or:.0f}s, "
          f"${gastado_or:.4f} gastados)")

    acc = defaultdict(list)
    for (f, pid, a), rw in hechos.items():
        if f in (FASE_OR1, FASE_OR2) and a in ARMS3:
            acc[(pid, a)].append(rw)
    assert len(acc) == 200 * 3, f"oráculo incompleto: {len(acc)}/600 celdas"
    oracle_mean = {k: sum(v) / len(v) for k, v in acc.items()}
    oracle_reward = {pos: max(oracle_mean[(p["id"], a)] for a in ARMS3)
                     for pos, (_c, p) in enumerate(stream)}

    # --- Freno de costo: proyección antes de la política ---
    n_oracle_pulls = 200 * 3 * 2
    avg_pull = gastado_or / n_oracle_pulls if n_oracle_pulls else 0.0
    n_policy_pulls = N_BLOQUES * ((len(PROBE_Q1) + len(PROBE_Q2)) * 3
                                  + len(THOMPSON_Q))
    policy_est = avg_pull * n_policy_pulls * 1.5  # factor de seguridad
    proyeccion = gastado_or + policy_est
    print(f"   proyección de costo total: ${proyeccion:.4f} "
          f"(oráculo ${gastado_or:.4f} + política ~${policy_est:.4f})")
    detenido = False
    if args.api and proyeccion > COSTO_STOP:
        detenido = True
        print(f"   ¡FRENO! proyección ${proyeccion:.4f} > ${COSTO_STOP:.2f}: "
              "deteniendo antes de la política.")

    # --- Política alma ---
    rewards = {}
    diag = []
    n_switch = 0
    thompson_arms = defaultdict(int)
    if not detenido:
        print("Política alma (probe continuo + re-probe + Thompson con olvido)...")
        pos_de_pid = {p["id"]: i for i, (_c, p) in enumerate(stream)}

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
                        rng = random.Random(f"{args.seed}-exp11-{nb}-{q}")
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
                         "prior_means": prior_means,
                         "inicial": e1, "final": e2,
                         "cambio": e1 != e2})
        assert len(rewards) == 200, f"rewards incompletos: {len(rewards)}"

    # --- Veredicto ---
    reg_fijas = {}
    for a in ARMS3:
        reg_fijas[a] = sum(
            oracle_reward[pos] - oracle_mean[(stream[pos][1]["id"], a)]
            for pos in range(200))
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
        reg_alma = sum(oracle_reward[pos] - rewards[pos] for pos in range(200))
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
        "veredicto": {"pasa": pasa, "criterio": CRITERIO_EXP11,
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
        print("  RESULTADO:", "PASS — el motor rinde en problemas duros reales"
              if pasa else "FAIL — en problemas duros, mejor un brazo fijo")
    print("===========================================")
    return 0 if pasa else (2 if detenido else 1)


if __name__ == "__main__":
    sys.exit(main())
