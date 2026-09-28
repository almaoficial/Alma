#!/usr/bin/env python3
"""ALMA-EXP5: mundo no estacionario — ¿el loop le gana a lo fijo cuando el
mundo se mueve?

La pregunta H3 honesta. EXP1-EXP4 corrieron en mundos quietos, y ahí una
arquitectura fija bien elegida gana — como debe ser. Pero el loop de ALMA
(medir → aprender → transferir → acumular) no existe para mundos quietos:
existe para mundos que cambian. Este experimento lo pone a prueba donde
tiene que ganar.

Diseño: stream de 120 problemas = 10 clases × 12, en bloques ordenados con
oráculos alternados (single, cot, single, cot...; seed 999). El mejor brazo
cambia a lo largo del stream: no estacionariedad por construcción.

Oráculo: por problema (mejor de {single, cot} medido en fase 5A, 240
llamadas). El regret de cada política se mide contra ese oráculo.

Políticas (mismo stream, mismo orden, draws de Thompson pareados por
posición):
  1. fija-single: siempre single.
  2. fija-cot: siempre cot.
  3. thompson-global: UN bandit Thompson sobre {single, cot} para todo el
     stream, prior uniforme. Adaptación ingenua, sin memoria ni probe.
  4. alma-full: el loop completo —
     - bandit por clase (memoria de la clase),
     - warm-start desde el repertorio hacia adelante (n0=2, medias
       globales; mecanismo de EXP4),
     - probe de 3 problemas × {single, cot} al entrar a cada clase, elige
       cot solo si supera a single por margen > 0.05 (mecanismo de EXP3;
       las observaciones del probe alimentan al bandit y al repertorio).

El repertorio para el warm-start en el bloque k usa SOLO observaciones de
bloques anteriores (hacia adelante, como EXP4): mantiene la semántica de
"territorio nuevo". No usa pulls de otras políticas sobre la misma clase.

Criterio PRE-REGISTRADO (PASS necesita ambas):
  - regret(alma-full) < regret(mejor fija)   [el loop rinde cuando el mundo se mueve]
  - regret(alma-full) < regret(thompson-global) [memoria+probe+warm > adaptación ingenua]
Diagnóstico: bloques donde alma-full le gana a la mejor fija (≥6/10).

Decisiones documentadas:
  - El orden alternado usa oráculos ESTIMADOS de EXP1-4 solo para ordenar;
    el regret usa el oráculo MEDIDO en 5A. Si 5A discrepa, el mundo sigue
    siendo no estacionario (los oráculos difieren entre bloques).
  - En los 3 problemas del probe, el reward de la política = reward del
    arco elegido por el probe (como si lo hubiera corrido); el costo de las
    6 llamadas del probe se carga completo al budget. Es el costo honesto
    del mecanismo: gastar llamadas para decidir bien.
  - Brazos restringidos a {single, cot}: 10 clases de evidencia de que el
    oráculo siempre cae ahí; más brazos solo sumaría ruido y costo.
  - Sin demo de gates: EXP5 no toca el núcleo (gates PASS ×3 ya establecido).

Uso:
    python3 run_experiment5.py --mock
    python3 run_experiment5.py --api
    python3 resume_experiment5.py --out resultados/exp5-20260926
"""
import argparse
import json
import os
import random
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_experiment as rx

rx.NOMBRE_EXPERIMENTO = "ALMA-EXP5: mundo no estacionario (drift)"

CLASES_EXP1 = ["calculo", "codigo", "qa_multihop", "herramientas", "puzzles"]
CLASES_EXP2 = ["logica", "traduccion", "resumen", "depuracion", "conocimiento"]
CLASES10 = CLASES_EXP1 + CLASES_EXP2

# Oráculos estimados en EXP1-4 (solo para ORDENAR el stream; el regret usa 5A).
EST_SINGLE = ["codigo", "herramientas", "puzzles", "traduccion", "depuracion"]
EST_COT = ["calculo", "qa_multihop", "logica", "conocimiento", "resumen"]

SEED = 999
ARMS = ["single", "cot"]
N0_PSEUDO = 2        # fuerza del prior warm (EXP4)
PROBE_N = 3          # problemas del probe por clase (EXP3)
PROBE_MARGEN = 0.05  # cot debe superar a single por este margen (EXP3)

FASE_PROBE = "5B-alma-probe"

CRITERIO_EXP5 = {
    "gana_a_mejor_fija": True,      # regret(alma-full) < min(regret fijas)
    "gana_a_thompson_global": True,
    "min_bloques_gana_vs_fija": 6,  # diagnóstico, de 10
}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def cargar_todo(base):
    problemas_por_clase = {}
    for clase in CLASES_EXP1:
        with open(os.path.join(base, "data", f"{clase}.json"), encoding="utf-8") as f:
            problemas_por_clase[clase] = json.load(f)
    for clase in CLASES_EXP2:
        with open(os.path.join(base, "data_exp2", f"{clase}.json"), encoding="utf-8") as f:
            problemas_por_clase[clase] = json.load(f)
    return problemas_por_clase


def ordenar_stream(seed):
    """Bloques de 12 con oráculo estimado alternado."""
    rng = random.Random(seed)
    s = EST_SINGLE[:]
    c = EST_COT[:]
    rng.shuffle(s)
    rng.shuffle(c)
    orden = []
    empieza_single = rng.random() < 0.5
    for a, b in zip(s, c):
        orden += [a, b] if empieza_single else [b, a]
    return orden


def make_puller(store, backend, evaluator, budget):
    """Pull idempotente: devuelve (reward, fue_nuevo). Resume-safe por
    construcción: si la fila ya existe en el store, no ejecuta."""
    hechos = {}
    for r in store.read_all():
        hechos[(r.get("fase"), r.get("problema_id"), r.get("arch_id"))] = \
            r["metricas"]["reward"]

    def pull(p, arch, fase):
        key = (fase, p["id"], arch)
        if key in hechos:
            return hechos[key], False
        res, met = rx.ejecutar_y_evaluar(p, arch, backend, evaluator,
                                        store, budget, fase)
        if met is None:
            # El wrapper de resume lo salteó por ya registrado: releer.
            for r in store.read_all():
                if (r.get("fase"), r.get("problema_id"), r.get("arch_id")) == key:
                    hechos[key] = r["metricas"]["reward"]
                    return hechos[key], False
            raise RuntimeError(f"pull fantasma sin fila: {key}")
        hechos[key] = met["reward"]
        return met["reward"], True

    return pull, hechos


def filas_fase(store, fase):
    return [r for r in store.read_all() if r.get("fase") == fase]


def fase_5a_oraculo(stream, pull):
    """Oráculo por problema: mejor de {single, cot}. Idempotente vía pull."""
    oracle_arch, oracle_reward = {}, {}
    for pos, (_clase, p) in enumerate(stream):
        rs = {arch: pull(p, arch, "5A-oracle")[0] for arch in ARMS}
        mejor = max(rs, key=lambda a: rs[a])
        oracle_arch[pos] = mejor
        oracle_reward[pos] = rs[mejor]
    return oracle_arch, oracle_reward


def repertorio_hacia_adelante(store, stream, pos_limite):
    """Medias globales por brazo con observaciones de posiciones < pos_limite.
    Fases válidas: 5A-oracle, 5B-alma-full y 5B-alma-probe (experiencia real
    del sistema; NO pulls de otras políticas sobre la misma clase)."""
    pos_de_pid = {p["id"]: i for i, (_c, p) in enumerate(stream)}
    rep = {a: [] for a in ARMS}
    for r in store.read_all():
        if r.get("fase") not in ("5A-oracle", "5B-alma-full", FASE_PROBE):
            continue
        if r.get("arch_id") not in ARMS:
            continue
        if pos_de_pid.get(r.get("problema_id", ""), 10 ** 9) < pos_limite:
            rep[r["arch_id"]].append(r["metricas"]["reward"])
    return rep


def bandit_warm(repertorio):
    b = rx.BanditPorClase(ARMS)
    for a in ARMS:
        rs = repertorio.get(a, [])
        m = mean(rs) if rs else 0.5
        b.alpha[a] = 1.0 + N0_PSEUDO * m
        b.beta[a] = 1.0 + N0_PSEUDO * (1.0 - m)
        b.pulls[a] = N0_PSEUDO
    return b


def probe_choice(probe_rs):
    """Regla del probe (EXP3): cot solo si supera a single por el margen."""
    return "cot" if (mean(probe_rs["cot"]) - mean(probe_rs["single"])) > PROBE_MARGEN else "single"


def correr_fija(politica, stream, pull, seed):
    fase = f"5B-{politica}"
    arch_fijo = politica.split("-")[1]
    rewards = {}
    for pos, (_clase, p) in enumerate(stream):
        rewards[pos], _ = pull(p, arch_fijo, fase)
    return rewards


def correr_thompson_global(stream, pull, hechos, seed):
    fase = "5B-thompson-global"
    bandit = rx.BanditPorClase(ARMS)
    # Replay: estado desde el store, en orden de stream.
    pid_a_filas = {}
    for (f, pid, _a), _r in hechos.items():
        if f == fase:
            pid_a_filas.setdefault(pid, []).append(pid)
    rewards, pendientes = {}, []
    for pos, (_clase, p) in enumerate(stream):
        if p["id"] in pid_a_filas:
            arch = next(a for (f, pid, a) in hechos
                        if f == fase and pid == p["id"])
            r = hechos[(fase, p["id"], arch)]
            bandit.update(arch, r)
            rewards[pos] = r
        else:
            pendientes.append(pos)
    for pos in pendientes:
        _clase, p = stream[pos]
        rng = random.Random(f"{seed}-exp5-{pos}")
        arch = bandit.select(rng)
        r, nuevo = pull(p, arch, fase)
        if nuevo:
            bandit.update(arch, r)
        rewards[pos] = r
    return rewards


def correr_alma_full(stream, orden, pull, hechos, store, seed):
    """Bloque por bloque: warm-start (repertorio hacia adelante) + probe
    (3 problemas × {single,cot}) + Thompson en el resto. Todo idempotente."""
    rewards = {}

    def filas_probe(pid):
        return [(a, hechos[(FASE_PROBE, pid, a)])
                for a in ARMS if (FASE_PROBE, pid, a) in hechos]

    def fila_full(pid):
        for a in ARMS:
            if ("5B-alma-full", pid, a) in hechos:
                return a, hechos[("5B-alma-full", pid, a)]
        return None

    for b, clase in enumerate(orden):
        base = b * 12
        rep = repertorio_hacia_adelante(store, stream, base)
        bandit = bandit_warm(rep)
        # Replay del probe existente + completar faltante.
        probe_rs = {(q, a): None for q in range(PROBE_N) for a in ARMS}
        for q in range(PROBE_N):
            qp = stream[base + q][1]
            for a, r in filas_probe(qp["id"]):
                probe_rs[(q, a)] = r
                bandit.update(a, r)
        for q in range(PROBE_N):
            qp = stream[base + q][1]
            for arch in ARMS:
                if probe_rs[(q, arch)] is None:
                    r, nuevo = pull(qp, arch, FASE_PROBE)
                    probe_rs[(q, arch)] = r
                    if nuevo:
                        bandit.update(arch, r)
        por_arch = {a: [probe_rs[(q, a)] for q in range(PROBE_N)] for a in ARMS}
        elegido = probe_choice(por_arch)
        for q in range(PROBE_N):
            rewards[base + q] = probe_rs[(q, elegido)]
        # Thompson en el resto del bloque.
        for q in range(PROBE_N, 12):
            pos = base + q
            p = stream[pos][1]
            hit = fila_full(p["id"])
            if hit is not None:
                arch, r = hit
                bandit.update(arch, r)
                rewards[pos] = r
                continue
            rng = random.Random(f"{seed}-exp5-{pos}")
            arch = bandit.select(rng)
            r, nuevo = pull(p, arch, "5B-alma-full")
            if nuevo:
                bandit.update(arch, r)
            rewards[pos] = r
    return rewards


def main():
    ap = argparse.ArgumentParser(description="ALMA-EXP5: mundo no estacionario")
    ap.add_argument("--mock", action="store_true", default=True)
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "resultados"))
    ap.add_argument("--append", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    if not args.append and os.path.exists(args.out):
        shutil.rmtree(args.out)
    os.makedirs(args.out, exist_ok=True)

    base = os.path.dirname(os.path.abspath(__file__))
    prereg = {
        "experimento": rx.NOMBRE_EXPERIMENTO,
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "criterio_exito": CRITERIO_EXP5,
        "diseno": {
            "stream": "10 clases x 12 problemas, bloques alternados (seed 999)",
            "oraculo": "por problema, mejor de {single, cot} (fase 5A)",
            "politicas": ["fija-single", "fija-cot", "thompson-global",
                          "alma-full"],
            "alma-full": "bandit por clase + warm-start repertorio hacia "
                         "adelante (n0=2) + probe 3 problemas (margen 0.05)",
            "rng": "pareado por posición de stream entre políticas",
        },
        "versiones": {
            "alma": rx.ALMA_VERSION,
            "registry": rx.registry.REGISTRY_VERSION,
            "evaluator": rx.evaluator_mod.EVALUATOR_VERSION,
        },
        "seed": args.seed,
        "modo": "api" if args.api else "mock",
    }
    with open(os.path.join(args.out, "preregistro.json"), "w") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito. Criterio: {CRITERIO_EXP5}")

    problemas_por_clase = cargar_todo(base)
    orden = ordenar_stream(args.seed)
    stream = [(clase, p) for clase in orden for p in problemas_por_clase[clase]]
    assert len(stream) == 120
    print(f"Stream: {len(stream)} problemas, orden de bloques: {orden}")

    if args.api:
        backend = rx.VaultBackend()
        print(f"Backend real (vault): {backend.model} vía skill openai")
        limites = {rx.RESOLUCION: 50.0, rx.SELECCION: 1.0, rx.EXPERIMENTACION: 5.0}
    else:
        index = {p["id"]: p for ps in problemas_por_clase.values() for p in ps}
        backend = rx.MockBackend(index, seed=args.seed)
        print("Backend mock (mundo sintético determinista)")
        limites = {rx.RESOLUCION: 10.0, rx.SELECCION: 1.0, rx.EXPERIMENTACION: 5.0}

    evaluator = rx.Evaluator(judge=rx.StubJudge())
    store = rx.ExperienceStore(os.path.join(args.out, "experiencias.jsonl"))
    budget = rx.BudgetManager(limites)
    assert store.verify_chain()

    pull, hechos = make_puller(store, backend, evaluator, budget)

    print("Fase 5A: oráculo por problema...")
    oracle_arch, oracle_reward = fase_5a_oraculo(stream, pull)
    n_cot = sum(1 for a in oracle_arch.values() if a == "cot")
    print(f"   oráculo medido: {n_cot}/120 problemas → cot")

    politicas = ["fija-single", "fija-cot", "thompson-global", "alma-full"]
    regrets, por_bloque = {}, {}
    for pol in politicas:
        print(f"Política {pol}...")
        tpol = time.time()
        if pol.startswith("fija-"):
            rewards = correr_fija(pol, stream, pull, args.seed)
        elif pol == "thompson-global":
            rewards = correr_thompson_global(stream, pull, hechos, args.seed)
        else:
            rewards = correr_alma_full(stream, orden, pull, hechos, store,
                                       args.seed)
        assert len(rewards) == 120, f"{pol}: {len(rewards)} rewards"
        reg = {pos: oracle_reward[pos] - rewards[pos] for pos in range(120)}
        regrets[pol] = reg
        bloques = [round(sum(reg[b * 12 + q] for q in range(12)), 4)
                   for b in range(10)]
        por_bloque[pol] = bloques
        print(f"   regret total={sum(reg.values()):.3f} ({time.time()-tpol:.0f}s)")

    r_alma = sum(regrets["alma-full"].values())
    r_fijas = min(sum(regrets["fija-single"].values()),
                  sum(regrets["fija-cot"].values()))
    r_th = sum(regrets["thompson-global"].values())
    gana_fija = r_alma < r_fijas
    gana_th = r_alma < r_th
    bloques_gana = sum(
        1 for b in range(10)
        if por_bloque["alma-full"][b] < min(por_bloque["fija-single"][b],
                                           por_bloque["fija-cot"][b]))
    pasa = bool(gana_fija and gana_th)
    motivos = [
        f"regret alma-full={r_alma:.4f} vs mejor fija={r_fijas:.4f} "
        f"(diff={r_alma - r_fijas:+.4f})",
        f"regret alma-full={r_alma:.4f} vs thompson-global={r_th:.4f} "
        f"(diff={r_alma - r_th:+.4f})",
        f"alma-full gana el bloque en {bloques_gana}/10 "
        f"(diagnóstico, mín {CRITERIO_EXP5['min_bloques_gana_vs_fija']})",
    ]
    veredicto = {"pasa": pasa, "criterio": CRITERIO_EXP5, "motivos": motivos,
                 "medido": {"regret_alma_full": round(r_alma, 4),
                            "regret_mejor_fija": round(r_fijas, 4),
                            "regret_thompson_global": round(r_th, 4),
                            "bloques_gana_vs_fija": bloques_gana}}

    costo_total = sum(budget.gastado.values())
    report = {
        "preregistro": prereg,
        "orden_bloques": orden,
        "oraculo_por_problema": {str(k): v for k, v in oracle_arch.items()},
        "regret_total_por_politica": {p: round(sum(r.values()), 4)
                                      for p, r in regrets.items()},
        "regret_por_bloque": por_bloque,
        "budget": budget.report(),
        "costo_total_usd": round(costo_total, 4),
        "experiencias": len(store),
        "store_chain_ok": store.verify_chain(),
        "veredicto": veredicto,
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO ================")
    for m in motivos:
        print("  " + m)
    print(f"  costo total: ${costo_total:.4f} USD  |  {len(store)} experiencias  "
          f"|  {report['duracion_s']}s")
    print("  RESULTADO:", "PASS — el loop rinde cuando el mundo se mueve"
          if pasa else "FAIL — el loop no le gana a lo fijo ni a lo ingenuo")
    print("===========================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
