#!/usr/bin/env python3
"""ALMA-EXP13: veredicto con datos existentes (SIN llamadas a la API).

Situacion: la recoleccion quedo trunca (v1: 208/220 pulls, v2: 0/220).
Este script NO fabrica datos: computa lo computable (regrets fijos por
replay del oraculo, regret parcial v1 en bloques completos 0-8) y deja el
veredicto como BLOQUEADO (pasa=null), con el inventario exacto de lo que
falta para poder evaluarlo segun el criterio pre-registrado.
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_experiment5 as rx5
import run_experiment12 as rx12

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "resultados", "exp13-20260926")
ARMS3 = ["single", "cot", "reflexion"]
BLOQUE, N_BLOQUES, N_PROB = 12, 10, 120
PROBE_Q1 = (0, 1, 2)
PROBE_Q2 = (10, 11)
THOMPSON_Q = tuple(q for q in range(BLOQUE)
                   if q not in PROBE_Q1 + PROBE_Q2)
MARGEN = rx5.PROBE_MARGEN  # 0.05


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def regla_v1(probe_means):
    mejor_alt = max([a for a in ARMS3 if a != "single"],
                    key=lambda a: probe_means[a])
    return (mejor_alt
            if probe_means[mejor_alt] - probe_means["single"] > MARGEN
            else "single")


def main():
    exp_path = os.path.join(OUT, "experiencias.jsonl")
    prereg = json.load(open(os.path.join(OUT, "preregistro.json"),
                            encoding="utf-8"))

    # --- Oráculo (fases 13A-*, copiado de EXP12) ---
    acc = defaultdict(list)
    costo_total = 0.0
    n_exp = 0
    probe = {}   # (pid, arm) -> reward  [13B-v1-probe]
    full = {}    # pid -> (arm, reward)  [13B-v1-full]
    for line in open(exp_path, encoding="utf-8"):
        r = json.loads(line)
        n_exp += 1
        costo_total += r.get("costo_usd", 0.0) or 0.0
        f = r.get("fase")
        if f in ("13A-oracle-r1", "13A-oracle-r2"):
            acc[(r["problema_id"], r["arch_id"])].append(
                r["metricas"]["reward"])
        elif f == "13B-v1-probe":
            probe[(r["problema_id"], r["arch_id"])] = \
                r["metricas"]["reward"]
        elif f == "13B-v1-full":
            full[r["problema_id"]] = (r["arch_id"],
                                      r["metricas"]["reward"])
    oracle_mean = {k: sum(v) / len(v) for k, v in acc.items()}
    assert len(oracle_mean) == N_PROB * 3, \
        f"oraculo incompleto: {len(oracle_mean)}"

    # --- Stream (reconstruido igual que run_experiment13.py) ---
    cands = rx12.cargar_problemas(BASE)
    bloques = rx12.bloques_clase_pura(cands)
    info = []
    for nombre, probs in bloques:
        mejor, medias, margen = rx12.mejor_brazo_bloque(probs, oracle_mean)
        info.append((nombre, mejor, probs, medias, margen))
    ordenado = rx12.ordenar_alternado(
        [(n, m, p) for n, m, p, _, _ in info])
    pre12 = json.load(open(os.path.join(
        BASE, "resultados", "exp12-20260926", "preregistro.json"),
        encoding="utf-8"))
    ord12 = [b["bloque"] for b in pre12["orden_bloques"]]
    assert [n for n, _, _ in ordenado] == ord12, "stream difiere de EXP12"
    stream = []
    for _nombre, _mejor, probs in ordenado:
        for p in probs:
            stream.append(p)
    assert len(stream) == N_PROB

    oracle_reward = {pos: max(oracle_mean[(p["id"], a)] for a in ARMS3)
                     for pos, p in enumerate(stream)}

    # --- Regrets fijos (replay del oráculo; 100% computable) ---
    reg_fijas = {}
    for a in ARMS3:
        reg_fijas[a] = round(sum(
            oracle_reward[pos] - oracle_mean[(stream[pos]["id"], a)]
            for pos in range(N_PROB)), 4)
    mejor_fija = min(reg_fijas, key=lambda a: reg_fijas[a])

    # --- Inventario de faltantes ---
    have_probe = set(probe)
    falt_probe = []   # (bloque, q, pid, arm)
    falt_full = []    # (bloque, q, pid)
    bloques_v1_ok = []
    for nb in range(N_BLOQUES):
        ok = True
        for q in PROBE_Q1 + PROBE_Q2:
            pid = stream[nb * BLOQUE + q]["id"]
            for a in ARMS3:
                if (pid, a) not in have_probe:
                    falt_probe.append((nb, q, pid, a))
                    ok = False
        for q in THOMPSON_Q:
            pid = stream[nb * BLOQUE + q]["id"]
            if pid not in full:
                falt_full.append((nb, q, pid))
                ok = False
        if ok:
            bloques_v1_ok.append(nb)

    # --- Regret parcial v1 (solo bloques 100% completos; INFORMATIVO) ---
    reg_v1_parcial = 0.0
    diag_v1 = []
    for nb in bloques_v1_ok:
        base_pos = nb * BLOQUE
        prs = {(q, a): probe[(stream[base_pos + q]["id"], a)]
               for q in PROBE_Q1 + PROBE_Q2 for a in ARMS3}
        pm1 = {a: mean([prs[(q, a)] for q in PROBE_Q1]) for a in ARMS3}
        e1 = regla_v1(pm1)
        pm2 = {a: mean([prs[(q, a)] for q in PROBE_Q1 + PROBE_Q2])
               for a in ARMS3}
        e2 = regla_v1(pm2)
        reg_b = 0.0
        for q in PROBE_Q1:
            pos = base_pos + q
            reg_b += oracle_reward[pos] - prs[(q, e1)]
        for q in THOMPSON_Q:
            pos = base_pos + q
            _arch, r = full[stream[pos]["id"]]
            reg_b += oracle_reward[pos] - r
        for q in PROBE_Q2:
            pos = base_pos + q
            reg_b += oracle_reward[pos] - prs[(q, e2)]
        reg_v1_parcial += reg_b
        diag_v1.append({"bloque": nb,
                        "clase": ordenado[nb][0],
                        "regret_parcial": round(reg_b, 4),
                        "eleccion_inicial": e1, "eleccion_final": e2,
                        "cambio": e1 != e2})
    reg_v1_parcial = round(reg_v1_parcial, 4)

    pulls_v2_hechos = sum(
        1 for line in open(exp_path, encoding="utf-8")
        if json.loads(line).get("fase") in ("13B-v2-probe", "13B-v2-full"))

    motivos = [
        "VEREDICTO BLOQUEADO: la recoleccion quedo trunca; "
        "regret(v2) indefinido (0 pulls) y regret(v1) incompleto.",
        f"v1: {220 - len(falt_probe) - len(falt_full)}/220 pulls "
        f"(bloques completos: {bloques_v1_ok}); "
        f"faltan {len(falt_probe)} probe + {len(falt_full)} full, "
        f"todos en bloque 9 (mmlu-b).",
        f"v2: {pulls_v2_hechos}/220 pulls (nunca corrio: sin fases "
        "13B-v2-* en experiencias.jsonl).",
        f"regret fijas (replay oraculo, computable): "
        f"{', '.join(f'{a}={reg_fijas[a]:.4f}' for a in ARMS3)}; "
        f"mejor fija = {mejor_fija}.",
        f"regret v1 PARCIAL bloques 0-8 (108/120 pos, INFORMATIVO, "
        f"no es el criterio): {reg_v1_parcial:.4f}.",
        f"costo gastado: ${costo_total:.4f} en {n_exp} experiencias; "
        "para completar faltan ~232 pulls con API (v1: 12 + v2: 220).",
        "No se uso backend mock: fabricar rewards invalidaria el veredicto.",
    ]
    report = {
        "preregistro": prereg,
        "regret_total": {
            **{f"fija_{a}": reg_fijas[a] for a in ARMS3},
            "alma_v1_parcial_bloques_0_8": reg_v1_parcial,
            "alma_v1_total": None,
            "alma_v2_total": None,
        },
        "estado_recoleccion": {
            "experiencias": n_exp,
            "v1_pulls": 220 - len(falt_probe) - len(falt_full),
            "v1_pulls_esperados": 220,
            "v1_bloques_completos": bloques_v1_ok,
            "v1_probe_faltantes": [
                {"bloque": nb, "q": q, "problema_id": pid, "brazo": a}
                for nb, q, pid, a in falt_probe],
            "v1_full_faltantes": [
                {"bloque": nb, "q": q, "problema_id": pid}
                for nb, q, pid in falt_full],
            "v2_pulls": pulls_v2_hechos,
            "v2_pulls_esperados": 220,
        },
        "diagnostico_v1_parcial": diag_v1,
        "costo_total_usd": round(costo_total, 4),
        "veredicto": {
            "pasa": None,
            "criterio": {"v2_gana_a_v1_y_a_mejor_fija": True},
            "motivos": motivos,
        },
    }
    with open(os.path.join(OUT, "report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("regret fijas:", {a: f"{v:.4f}" for a, v in reg_fijas.items()})
    print(f"regret v1 parcial (bloques 0-8): {reg_v1_parcial:.4f}")
    print("regret v1 total: NO COMPUTABLE (bloque 9 incompleto)")
    print("regret v2 total: NO COMPUTABLE (sin datos)")
    print(f"VEREDICTO: BLOQUEADO (pasa=null) — costo gastado ${costo_total:.4f}")
    for m in motivos:
        print("  -", m)


if __name__ == "__main__":
    main()
