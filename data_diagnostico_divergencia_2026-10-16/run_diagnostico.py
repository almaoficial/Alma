"""Diagnóstico de la divergencia train → held-out (16/10/2026).

Pre-registro: preregistro-diagnostico-divergencia-2026-10-16.md
(commit c71ea8a) — leerlo ANTES de correr esto. Es ANÁLISIS, no
una corrida del meta-loop: no propone, no adopta, no toca la
puerta, el panel cableado, el validador, el E3 ni el panel de
confirmación. Usa la maquinaria congelada de MetaLoop._evaluar
(e56.correr_replica_param + stream y tasas de e47) y guarda el
reg_pol POR RÉPLICA.

Produce en esta carpeta:
  reg_por_replica.json — reg_pol por réplica (base y las 35
      configuraciones en train; base y las 7 de D3 en held-out).
  analisis.json — anclas de validez y estadísticas D1/D2/D3.

Fail-closed: si una ancla del §3/§6 del pre-registro no
reproduce, escribe el fallo en analisis.json y sale con error
SIN interpretar nada.
"""

import json
import math
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "exp56_rso"))

import run_experiment47 as e47  # noqa: E402  (validador congelado)
import run_experiment56 as e56  # noqa: E402

BASE = {"decay": 0.5, "gate_margin": 0.0, "n0": 4,
        "umbral_base": 1, "umbral_divisor": 3}
TRAIN_REPS = list(range(400, 418))
HELDOUT_REPS = list(range(600, 612))
TOL = 5e-5

# Δ_train independientes de P1..P5 asentados en el informe de la
# corrida del generador (contra la base; ancla del §3).
ANCLA_P = [-4.3333, -3.7222, -0.4444, -3.8889, 0.0556]
ANCLA_MEDIA_TRAIN = 85.2222
ANCLA_MEDIA_HO = 80.6667
ANCLA_HO = {"X9": -3.0833, "P5": -0.7500}
POSITIVAS_ESPERADAS = ["X4", "X7", "X9", "X10", "X13", "X17", "P5"]


def cargar_configs():
    """Las 35 del §3: X1..X24 (crossover) y P1..P11 (generador)."""
    with open(os.path.join(RAIZ, "data_crossover_2026-10-16",
                           "mediciones.json"), encoding="utf-8") as f:
        med = json.load(f)
    configs = {}
    oficial = {}
    for m in med:
        cid = f"X{m['indice']}"
        configs[cid] = dict(m["config"])
        oficial[cid] = m["delta_train"]
    with open(os.path.join(RAIZ, "tanda_generador_1792192469.json"),
              encoding="utf-8") as f:
        tanda = json.load(f)
    for i, c in enumerate(tanda["candidatos"], start=1):
        configs[f"P{i}"] = dict(c["config"])
    return configs, oficial


def media(xs):
    return sum(xs) / len(xs)


def signo(x):
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def pearson(xs, ys):
    n = len(xs)
    mx, my = media(xs), media(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return cov / math.sqrt(vx * vy)


def rangos(xs):
    """Rangos 1..n con promedio en empates (para Spearman)."""
    orden = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(orden):
        j = i
        while j + 1 < len(orden) and xs[orden[j + 1]] == xs[orden[i]]:
            j += 1
        prom = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[orden[k]] = prom
        i = j + 1
    return r


def spearman(xs, ys):
    return pearson(rangos(xs), rangos(ys))


def ols(xs, ys):
    """Pendiente e intercepto de ys ~ xs."""
    n = len(xs)
    mx, my = media(xs), media(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None, None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    return b, my - b * mx


def d2_jackknife(delta_r):
    """Medidas del §5 sobre el vector Δ_r de un finalista."""
    n = len(delta_r)
    total = sum(delta_r)
    prom = total / n
    pos = [d for d in delta_r if d > 0]
    neg = [d for d in delta_r if d < 0]
    masa_pos = sum(pos)
    masa_neg = sum(-d for d in neg)
    loo = [(total - delta_r[i]) / (n - 1) for i in range(n)]
    flips = sum(1 for v in loo if signo(v) != signo(prom))
    # k*: retirar los mayores Δ_r positivos, voraz descendente.
    restante = sorted(delta_r, reverse=True)
    k_estrella = None
    for k in range(1, n + 1):
        resto = restante[k:]
        if not resto or sum(resto) / len(resto) <= 0:
            k_estrella = k
            break
    m_loo = media(loo)
    # Varianza jackknife clásica del promedio:
    # ((n-1)/n)·Σ(θ_-i − θ̄_-·)² — para una media coincide con
    # la varianza clásica s²/n (se verifica en el informe).
    var_jk = ((n - 1) / n) * sum((v - m_loo) ** 2 for v in loo)
    se_jk = math.sqrt(var_jk)
    sd_r = math.sqrt(sum((d - prom) ** 2 for d in delta_r) / (n - 1))
    return {
        "delta_r": [round(d, 6) for d in delta_r],
        "promedio": prom,
        "n_pos": len(pos), "n_cero": n - len(pos) - len(neg),
        "n_neg": len(neg),
        "masa_positiva": masa_pos, "masa_negativa": masa_neg,
        "fraccion_masa_positiva": (masa_pos / (masa_pos + masa_neg)
                                   if (masa_pos + masa_neg) > 0 else None),
        "loo_min": min(loo), "loo_max": max(loo),
        "loo_flips_signo": flips,
        "k_estrella": k_estrella,
        "se_jackknife": se_jk,
        "sd_delta_r": sd_r,
        "se_apareado_clasico": sd_r / math.sqrt(n),
    }


def main():
    configs, oficial = cargar_configs()
    items = e47.construir_stream()
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))

    def regs(config, reps):
        return [e56.correr_replica_param(r, items, tasas,
                                         dict(config))["reg_pol"]
                for r in reps]

    # ---- medición cruda -------------------------------------------
    reg_train = {"BASE": regs(BASE, TRAIN_REPS)}
    for cid, cfg in configs.items():
        reg_train[cid] = regs(cfg, TRAIN_REPS)
    d3_ids = list(POSITIVAS_ESPERADAS)
    reg_ho = {"BASE": regs(BASE, HELDOUT_REPS)}
    for cid in d3_ids:
        reg_ho[cid] = regs(configs[cid], HELDOUT_REPS)

    with open(os.path.join(AQUI, "reg_por_replica.json"), "w",
              encoding="utf-8") as f:
        json.dump({
            "base_config": BASE,
            "train_reps": TRAIN_REPS, "heldout_reps": HELDOUT_REPS,
            "configs": configs,
            "reg_train": reg_train, "reg_ho": reg_ho,
        }, f, ensure_ascii=False, indent=1)

    base_tr = reg_train["BASE"]
    media_base_tr = media(base_tr)
    media_base_ho = media(reg_ho["BASE"])

    def delta(cid, regs_cfg, regs_base):
        return media(regs_base) - media(regs_cfg)

    delta_full = {cid: media_base_tr - media(reg_train[cid])
                  for cid in configs}

    # ---- anclas fail-closed (§3 y §6) ------------------------------
    fallos = []
    if abs(media_base_tr - ANCLA_MEDIA_TRAIN) > TOL:
        fallos.append(f"media base train {media_base_tr} != "
                      f"{ANCLA_MEDIA_TRAIN}")
    if abs(media_base_ho - ANCLA_MEDIA_HO) > TOL:
        fallos.append(f"media base held-out {media_base_ho} != "
                      f"{ANCLA_MEDIA_HO}")
    for cid, of in oficial.items():
        if abs(delta_full[cid] - of) > TOL:
            fallos.append(f"Δ_train {cid} {delta_full[cid]} != "
                          f"oficial {of}")
    for i, ancla in enumerate(ANCLA_P, start=1):
        if abs(delta_full[f"P{i}"] - ancla) > TOL:
            fallos.append(f"Δ_train P{i} {delta_full[f'P{i}']} != "
                          f"ancla {ancla}")
    delta_ho = {cid: media_base_ho - media(reg_ho[cid])
                for cid in d3_ids}
    for cid, ancla in ANCLA_HO.items():
        if abs(delta_ho[cid] - ancla) > TOL:
            fallos.append(f"Δ_ho {cid} {delta_ho[cid]} != ancla "
                          f"{ancla}")
    if fallos:
        with open(os.path.join(AQUI, "analisis.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"anclas_ok": False, "fallos": fallos}, f,
                      ensure_ascii=False, indent=1)
        print("ANCLAS FALLARON — paquete detenido sin interpretar:")
        for x in fallos:
            print(" -", x)
        return 1

    # ---- D1: split-half --------------------------------------------
    idx_a = [i for i in range(len(TRAIN_REPS)) if i % 2 == 0]
    idx_b = [i for i in range(len(TRAIN_REPS)) if i % 2 == 1]
    idx_c1 = list(range(0, 9))
    idx_c2 = list(range(9, 18))

    def delta_idx(cid, idx):
        return (media([base_tr[i] for i in idx])
                - media([reg_train[cid][i] for i in idx]))

    def bloque_d1(idx_x, idx_y, nombre):
        filas = {}
        for cid in configs:
            filas[cid] = {
                "delta_mitad1": delta_idx(cid, idx_x),
                "delta_mitad2": delta_idx(cid, idx_y),
                "delta_completo": delta_full[cid],
            }
        a = [filas[c][ "delta_mitad1"] for c in configs]
        b = [filas[c]["delta_mitad2"] for c in configs]
        acuerdo = sum(1 for x, y in zip(a, b) if signo(x) == signo(y))
        a_nz = [(x, y) for x, y in zip(a, b) if x != 0 and y != 0]
        acuerdo_nz = sum(1 for x, y in a_nz if signo(x) == signo(y))
        positivas = [c for c in configs if delta_full[c] > 0]
        ambas = [c for c in positivas
                 if filas[c]["delta_mitad1"] > 0
                 and filas[c]["delta_mitad2"] > 0]
        return {
            "nombre": nombre,
            "reps_mitad1": [TRAIN_REPS[i] for i in idx_x],
            "reps_mitad2": [TRAIN_REPS[i] for i in idx_y],
            "filas": filas,
            "pearson": pearson(a, b), "spearman": spearman(a, b),
            "acuerdo_signo": acuerdo, "n": len(a),
            "acuerdo_signo_sin_ceros": acuerdo_nz,
            "n_sin_ceros": len(a_nz),
            "positivas_completo": positivas,
            "positivas_ambas_mitades": ambas,
        }

    d1_primario = bloque_d1(idx_a, idx_b, "paridad_indice")
    d1_secundario = bloque_d1(idx_c1, idx_c2, "contigua")

    # ---- D2 ---------------------------------------------------------
    d2 = {}
    for cid in ("X9", "P5"):
        delta_r = [base_tr[i] - reg_train[cid][i]
                   for i in range(len(TRAIN_REPS))]
        d2[cid] = d2_jackknife(delta_r)

    # ---- D3 ---------------------------------------------------------
    pares = [{"id": cid, "delta_train": delta_full[cid],
              "delta_ho": delta_ho[cid]} for cid in d3_ids]
    xs = [p["delta_train"] for p in pares]
    ys = [p["delta_ho"] for p in pares]
    pend, inter = ols(xs, ys)
    d3 = {
        "pares": pares,
        "reversiones_signo": sum(1 for p in pares
                                 if signo(p["delta_train"])
                                 != signo(p["delta_ho"])),
        "pearson": pearson(xs, ys),
        "pendiente": pend, "intercepto": inter,
        "media_abs_train": media([abs(x) for x in xs]),
        "media_abs_ho": media([abs(y) for y in ys]),
    }

    analisis = {
        "anclas_ok": True,
        "media_base_train": media_base_tr,
        "media_base_heldout": media_base_ho,
        "delta_train_completo": delta_full,
        "d1_primario": d1_primario,
        "d1_secundario": d1_secundario,
        "d2": d2,
        "d3": d3,
    }
    with open(os.path.join(AQUI, "analisis.json"), "w",
              encoding="utf-8") as f:
        json.dump(analisis, f, ensure_ascii=False, indent=1)
    print("anclas OK; analisis.json y reg_por_replica.json escritos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
