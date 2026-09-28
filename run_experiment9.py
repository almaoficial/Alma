#!/usr/bin/env python3
"""ALMA-EXP9: memoria con olvido — ¿decaer el pasado ayuda cuando el mundo cambia?

EXP7 mostró que re-espiar corrige el sesgo del probe. Pero el warm-start
acumula TODA la historia con el mismo peso: si el régimen cambia de golpe,
la memoria vieja arrastra la decisión. Hipótesis: un prior que decae
exponencialmente (el pasado vale la mitad por bloque) se recupera más
rápido tras un cambio brusco.

Diseño (replay puro, 0 llamadas nuevas, US$0):
  - Stream reordenado con flip brusco a mitad: bloques nuevos 0-4 favorecen
    cot, 5-9 favorecen single (oráculo firme EXP8, media de 3 intentos).
    Orden nuevo (índices originales): [1,7,9,3,5,4,2,0,6,8].
  - Dos políticas, idénticas en todo salvo el prior warm-start:
      control: probe continuo EXP7 + prior uniforme (toda la historia igual)
      olvido : probe continuo EXP7 + prior con decaimiento 0.5^d
               (d = distancia en bloques; half-life = 1 bloque)
  - Probe (q=0,1,2 y re-probe q=6,7): rewards 7B-alma-probe grabados en
    EXP7, idénticos para ambas políticas; decisión con la regla de margen.
  - Thompson (q=3,4,5,8,9,10,11): RNG pareado por (bloque,q); el pull se
    resuelve con el oráculo firme EXP8 (media de 3 intentos) para
    (problema, brazo). Fuente única y documentada: sin esa concesión el
    replay de un brazo no grabado sería imposible.
  - Regret contra el oráculo firme (max sobre brazos de la media de 3).

Criterio PRE-REGISTRADO (PASS):
  - regret_total(olvido) < regret_total(control)
  - regret_postflip(olvido) < regret_postflip(control)  (bloques nuevos 5-9)

Uso:
    python3 run_experiment9.py
"""
import json
import os
import random
import shutil
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_experiment as rx
import run_experiment5 as rx5

NOMBRE = "ALMA-EXP9: memoria con olvido (decaimiento exponencial)"
ARMS = ["single", "cot"]
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (6, 7)
FASE_PROBE7 = "7B-alma-probe"
DECAY = 0.5  # el pasado vale la mitad por bloque
N0 = rx5.N0_PSEUDO

# Flip brusco: primero los 5 bloques más pro-cot, después los 5 más pro-single
# (oráculo firme EXP8). Índices originales del orden seed 999.
ORDEN_FLIP = [1, 7, 9, 3, 5, 4, 2, 0, 6, 8]

CRITERIO_EXP9 = {
    "olvido_gana_total": True,
    "olvido_gana_postflip": True,
}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def cargar_oraculo_firme(base):
    """{(pid, arm): media de intentos} + verdad por bloque original."""
    acc = defaultdict(list)
    store8 = rx.ExperienceStore(
        os.path.join(base, "resultados", "exp8-20260926", "experiencias.jsonl"))
    for r in store8.read_all():
        acc[(r["problema_id"], r["arch_id"])].append(r["metricas"]["reward"])
    return {k: sum(v) / len(v) for k, v in acc.items()}


def repertorio_ponderado(exp5_store, hechos7, stream, pos_limite, decay):
    """{arm: [(reward, peso)]} de observaciones pasadas en el orden actual.
    peso = decay^distancia_en_bloques. decay=1.0 -> uniforme (control)."""
    pos_de_pid = {p["id"]: i for i, (_c, p) in enumerate(stream)}
    rep = {a: [] for a in ARMS}
    for r in exp5_store.read_all():
        if r.get("fase") != "5A-oracle" or r.get("arch_id") not in ARMS:
            continue
        pos = pos_de_pid.get(r.get("problema_id", ""), 10 ** 9)
        if pos < pos_limite:
            d = (pos_limite - 1 - pos) // 12
            rep[r["arch_id"]].append((r["metricas"]["reward"], decay ** d))
    for (f, pid, a), rw in hechos7.items():
        if f != FASE_PROBE7 or a not in ARMS:
            continue
        pos = pos_de_pid.get(pid, 10 ** 9)
        if pos < pos_limite:
            d = (pos_limite - 1 - pos) // 12
            rep[a].append((rw, decay ** d))
    return rep


def bandit_warm_ponderado(rep_w):
    """Mismo prior que bandit_warm pero con media ponderada. La fuerza del
    prior (N0) se mantiene constante: solo cambia su UBICACIÓN."""
    b = rx.BanditPorClase(ARMS)
    for a in ARMS:
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


def correr_politica(stream, orden_nuevo, hechos7, oracle_mean, exp5_store,
                    seed, decay, tag):
    """Replay del probe continuo con prior uniforme (decay=1) o con olvido."""
    rewards = {}
    diag = []
    n_switch = 0
    for nb, b_orig in enumerate(orden_nuevo):
        base = nb * 12
        rep_w = repertorio_ponderado(exp5_store, hechos7, stream, base, decay)
        bandit = bandit_warm_ponderado(rep_w)
        prior_means = bandit.means()

        def probe_rewards(qs):
            prs = {}
            for q in qs:
                pid = stream[base + q][1]["id"]
                for a in ARMS:
                    key = (FASE_PROBE7, pid, a)
                    assert key in hechos7, f"falta probe grabado {key}"
                    prs[(q, a)] = hechos7[key]
                    bandit.update(a, prs[(q, a)])
            return prs

        def thompson_q(qs):
            for q in qs:
                pos = base + q
                p = stream[pos][1]
                rng = random.Random(f"{seed}-exp9-{nb}-{q}")
                arch = bandit.select(rng)
                r = oracle_mean[(p["id"], arch)]  # replay documentado
                bandit.update(arch, r)
                rewards[pos] = r

        prs = probe_rewards(PROBE_Q1)
        por1 = {a: [prs[(q, a)] for q in PROBE_Q1] for a in ARMS}
        elegido1 = rx5.probe_choice(por1)
        for q in PROBE_Q1:
            rewards[base + q] = prs[(q, elegido1)]

        thompson_q((3, 4, 5))

        prs2 = probe_rewards(PROBE_Q2)
        todo = dict(prs)
        todo.update(prs2)
        qs_all = PROBE_Q1 + PROBE_Q2
        por2 = {a: [todo[(q, a)] for q in qs_all] for a in ARMS}
        elegido2 = rx5.probe_choice(por2)
        if elegido1 != elegido2:
            n_switch += 1
        for q in PROBE_Q2:
            rewards[base + q] = todo[(q, elegido2)]

        thompson_q((8, 9, 10, 11))
        diag.append({"bloque_nuevo": nb, "bloque_orig": b_orig,
                     "prior_means": prior_means,
                     "inicial": elegido1, "final": elegido2,
                     "cambio": elegido1 != elegido2})
    return rewards, diag, n_switch


def main():
    t0 = time.time()
    base = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(base, "resultados", "exp9-20260926")
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)

    prereg = {
        "experimento": NOMBRE,
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "criterio_exito": CRITERIO_EXP9,
        "diseno": {
            "stream": "reordenado con flip brusco (orig [1,7,9,3,5,4,2,0,6,8]); "
                      "bloques 0-4 pro-cot, 5-9 pro-single",
            "oraculo": "firme EXP8 (media de 3 intentos), 0 llamadas nuevas",
            "control": "probe continuo + prior warm uniforme (decay=1.0)",
            "tratamiento": "probe continuo + prior warm con decaimiento 0.5^d",
            "replay_thompson": "oráculo firme como pull (fuente única)",
            "rng": "pareado por (bloque,q), seed 999",
        },
        "seed": 999,
        "modo": "replay",
    }
    with open(os.path.join(out, "preregistro.json"), "w") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito. Criterio: {CRITERIO_EXP9}")

    problemas = rx5.cargar_todo(base)
    orden_orig = rx5.ordenar_stream(999)
    orden_nuevo = [orden_orig[i] for i in ORDEN_FLIP]
    stream = [(c, p) for c in orden_nuevo for p in problemas[c]]
    assert len(stream) == 120

    oracle_mean = cargar_oraculo_firme(base)
    oracle_reward = {pos: max(oracle_mean[(p["id"], a)] for a in ARMS)
                     for pos, (_c, p) in enumerate(stream)}

    exp5_out = os.path.join(base, "resultados", "exp5-20260926")
    exp5_store = rx.ExperienceStore(
        os.path.join(exp5_out, "experiencias.jsonl"))
    store7 = rx.ExperienceStore(
        os.path.join(base, "resultados", "exp7-20260926", "experiencias.jsonl"))
    hechos7 = {(r["fase"], r["problema_id"], r["arch_id"]): r["metricas"]["reward"]
               for r in store7.read_all()}

    print("Control (prior uniforme, replay)...")
    rew_c, diag_c, sw_c = correr_politica(stream, orden_nuevo, hechos7,
                                          oracle_mean, exp5_store, 999, 1.0,
                                          "control")
    print("Tratamiento (prior con olvido 0.5^d, replay)...")
    rew_o, diag_o, sw_o = correr_politica(stream, orden_nuevo, hechos7,
                                          oracle_mean, exp5_store, 999, DECAY,
                                          "olvido")

    reg = {}
    for n, rw in (("control", rew_c), ("olvido", rew_o)):
        reg[n] = {pos: oracle_reward[pos] - rw[pos] for pos in range(120)}
    tot = {n: sum(v.values()) for n, v in reg.items()}
    post = {n: sum(v for pos, v in reg[n].items() if pos >= 60)
            for n in reg}
    pre = {n: sum(v for pos, v in reg[n].items() if pos < 60)
           for n in reg}

    pasa_total = tot["olvido"] < tot["control"]
    pasa_post = post["olvido"] < post["control"]
    pasa = bool(pasa_total and pasa_post)
    motivos = [
        f"regret total: olvido={tot['olvido']:.4f} vs "
        f"control={tot['control']:.4f} (diff={tot['olvido'] - tot['control']:+.4f})",
        f"regret post-flip (bloques 5-9): olvido={post['olvido']:.4f} vs "
        f"control={post['control']:.4f} (diff={post['olvido'] - post['control']:+.4f})",
        f"regret pre-flip (bloques 0-4): olvido={pre['olvido']:.4f} vs "
        f"control={pre['control']:.4f}",
        f"cambios tras re-probe: control {sw_c}/10, olvido {sw_o}/10",
    ]
    report = {
        "preregistro": prereg,
        "regret_total": {k: round(v, 4) for k, v in tot.items()},
        "regret_pre_flip": {k: round(v, 4) for k, v in pre.items()},
        "regret_post_flip": {k: round(v, 4) for k, v in post.items()},
        "diagnostico_control": diag_c,
        "diagnostico_olvido": diag_o,
        "costo_total_usd": 0.0,
        "experiencias_nuevas": 0,
        "veredicto": {"pasa": pasa, "criterio": CRITERIO_EXP9,
                       "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO ================")
    for m in motivos:
        print("  " + m)
    print("  costo: $0.0000 USD (replay puro) | "
          f"{report['duracion_s']}s")
    print("  RESULTADO:", "PASS — olvidar el pasado acelera la adaptación"
          if pasa else "FAIL — el olvido no supera a la memoria completa")
    print("===========================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
