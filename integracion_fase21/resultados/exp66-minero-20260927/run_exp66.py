#!/usr/bin/env python3
"""EXP66 validación: Thompson con prior anclado al ganador del probe.

Edición (una sola, contra la firma de EXP66-FaseA "Thompson no escucha al
probe"): al arrancar cada bloque, sumar N_ANCLA=8 pseudo-observaciones en
el ganador del probe con su media del probe. Thompson sigue explorando;
solo arranca creyéndole al probe.

Reutilización honesta (US$0): stream idéntico a EXP62, oráculo medido y
las 90 rewards del probe de 62B-alma-probe (el probe no cambia).
Gasto nuevo: 90 pulls de Thompson-anclado por réplica (fase 66B-alma-edit),
3 réplicas. Freno duro US$1,00. Key solo por DEEPSEEK_API_KEY.

Pre-registro: integracion_fase21/resultados/exp66-minero-20260927/preregistro.md

Uso:
  DEEPSEEK_API_KEY=<key> python3 run_exp66.py --out <dir_vacio>
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, "/home/hatch/workspace/alma-prototype/exp62_deepseek")
sys.path.insert(0, "/home/hatch/workspace/alma-prototype")

import run_exp62 as E
from alma_service.gate import aceptar

EXP62 = "/home/hatch/workspace/alma-prototype/exp62_deepseek"
BASE = "/home/hatch/workspace/alma-prototype"
N_ANCLA = 8
FASE = "66B-alma-edit"
REPLICAS = [6601, 6602, 6603]
BLOQUES_IN = range(0, 5)
BLOQUES_HO = range(5, 10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    corr = E.Corrida(args.out)  # falla acá si falta DEEPSEEK_API_KEY

    rep62 = json.load(open(os.path.join(EXP62, "report.json"), encoding="utf-8"))
    orden = rep62["orden_bloques"]
    orac = json.load(open(os.path.join(EXP62, "oraculo.json"), encoding="utf-8"))
    oracle_reward = {int(k): v for k, v in orac["reward"].items()}
    detalle = orac["detalle"]
    baseline_bloque = rep62["regret_por_bloque"]["alma-full"]

    problemas = E.cargar_todo(BASE)
    stream = [(clase, p) for clase in orden for p in problemas[clase]]
    assert len(stream) == 120, f"stream={len(stream)}"
    pos_de_pid = {p["id"]: i for i, (_c, p) in enumerate(stream)}

    # Probe medido de EXP62: (bloque, arch) -> [3 rewards]
    probe_rs = {}
    for l in open(os.path.join(EXP62, "experiencias.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        if r.get("fase") != "62B-alma-probe":
            continue
        pos = pos_de_pid[r["problema_id"]]
        probe_rs.setdefault((pos // 12, r["arch_id"]), []).append(
            r["metricas"]["reward"])
    assert all(len(probe_rs[(b, a)]) == 3 for b in range(10)
               for a in E.ARMS), "probe medido incompleto"

    # Oráculo expandido: pos -> {arch: [3 intentos]}
    oracle_rep = {pos: {a: detalle[str(pos)][a] for a in E.ARMS}
                  for pos in range(120)}

    reg_por_replica = []
    for seed in REPLICAS:
        historia = {a: [] for a in E.ARMS}  # pulls propios de la réplica
        rewards = {}
        for b in range(10):
            base_pos = b * 12
            # Warm start: oráculo (celdas < base) + probe medido
            # (bloques < b) + pulls propios anteriores. Auto-consistente.
            rep = {a: [] for a in E.ARMS}
            for pos in range(base_pos):
                for a in E.ARMS:
                    rep[a].extend(oracle_rep[pos][a])
            for (bb, a), rs in probe_rs.items():
                if bb < b:
                    rep[a].extend(rs)
            for a in E.ARMS:
                rep[a].extend(historia[a])
            bandit = E.bandit_warm(rep)
            # Probe del bloque (medido): alimenta al bandit como en EXP62
            prs = {a: probe_rs[(b, a)] for a in E.ARMS}
            for a in E.ARMS:
                for r in prs[a]:
                    bandit.update(a, r)
            medias = {a: E.mean(prs[a]) for a in E.ARMS}
            elegido = E.probe_choice(prs)
            # *** LA EDICIÓN: ancla al ganador del probe ***
            bandit.alpha[elegido] += N_ANCLA * medias[elegido]
            bandit.beta[elegido] += N_ANCLA * (1.0 - medias[elegido])
            bandit.pulls[elegido] += N_ANCLA
            # 9 pulls de Thompson anclado
            for q in range(3, 12):
                pos = base_pos + q
                p = stream[pos][1]
                rng = random.Random(f"exp66-{seed}-{pos}")
                arch = bandit.select(rng)
                r, nuevo = corr.pull(p, arch, FASE)
                if nuevo:
                    bandit.update(arch, r)
                historia[arch].append(r)
                rewards[pos] = r
        reg = {pos: oracle_reward[pos] - rewards[pos] for pos in range(120)}
        por_bloque = [round(sum(reg[b * 12 + q] for q in range(12)), 4)
                      for b in range(10)]
        reg_por_replica.append(por_bloque)
        print(f"  réplica seed={seed}: regret={sum(por_bloque):.3f} "
              f"bloques={por_bloque}", flush=True)

    n = len(REPLICAS)
    medio = [round(sum(reg_por_replica[s][b] for s in range(n)) / n, 4)
             for b in range(10)]
    d_in = round(sum(baseline_bloque[b] - medio[b] for b in BLOQUES_IN), 4)
    d_ho = round(sum(baseline_bloque[b] - medio[b] for b in BLOQUES_HO), 4)
    ok, motivo = aceptar(d_in, d_ho)
    rep_out = {
        "edicion": "prior-anclado-al-probe",
        "N_ANCLA": N_ANCLA,
        "replicas": REPLICAS,
        "regret_por_bloque_medio": medio,
        "regret_por_bloque_replicas": reg_por_replica,
        "baseline_alma_full": baseline_bloque,
        "delta_in": d_in,
        "delta_ho": d_ho,
        "puerta": motivo,
        "veredicto": "PASS" if ok else "FAIL",
        "gastado_usd": round(corr.budget.gastado[E.RESOLUCION], 6),
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(rep_out, f, indent=1)
    with open(os.path.join(args.out, "gasto_por_llamada.jsonl"), "w") as f:
        for g in corr.gasto_log:
            f.write(json.dumps(g) + "\n")
    print(json.dumps(rep_out, indent=1))


if __name__ == "__main__":
    main()
