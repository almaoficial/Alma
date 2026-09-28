#!/usr/bin/env python3
"""ALMA-EXP31: ¿el orden TRIZ de los brazos en el probe abarata encontrar
la estrategia correcta, vs un orden fijo o aleatorio?

Mock, US$0. La V2.3 ordena los brazos del probe con la contradicción TRIZ
y está en producción SIN experimento detrás. Este experimento la pone a
prueba contra dos controles: orden fijo canónico y orden aleatorio.

Diseño: probe secuencial con parada temprana (para en el primer éxito).
Por problema se pre-sortean los rewards de los 3 brazos (números aleatorios
comunes): los 3 ordenamientos se evalúan sobre los mismos draws, así la
única diferencia es el ORDEN.
Métrica primaria: pulls medios de probe por problema (costo).
Métrica secundaria: precisión (brazo elegido == mejor brazo verdadero).

Criterio pre-registrado (ver preregistro.json): W = seeds donde
pulls(TRIZ) < pulls(FIJO) y < pulls(ALEATORIO).
PASS si W>=7/8 con guarda de precisión (<=3pp de pérdida vs controles).
NO CONFIABLE si W en {5,6} o falla la guarda. FAIL si W<=4.

Uso: python3 run_experiment31.py [--out DIR]
"""
import argparse
import hashlib
import json
import os
import random
import sys

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(DIR_BASE, "servicio"))
from motor import formular_contradiccion  # noqa: E402  (la función REAL de producción)

RES_DIR = os.path.join(DIR_BASE, "resultados", "exp31-20260927")

SEEDS = [3121, 3122, 3123, 3124, 3125, 3126, 3127, 3128]
SEEDS_ESTACIONARIAS = set(SEEDS[:4])
N_PROBLEMAS = 200
BRAZOS = ["single", "cot", "reflexion"]
ORDEN_FIJO = ["single", "cot", "reflexion"]

P_MEJOR = {
    "calculo": {"single": 0.80, "cot": 0.15, "reflexion": 0.05},
    "medio": {"single": 0.15, "cot": 0.70, "reflexion": 0.15},
    "largo": {"single": 0.05, "cot": 0.20, "reflexion": 0.75},
}
P_EXITO_MEJOR = 0.85
P_EXITO_OTRO = 0.10

MIX_ESTACIONARIO = [("calculo", 0.40), ("medio", 0.30), ("largo", 0.30)]
MIX_FLIP_A = [("calculo", 0.70), ("medio", 0.30)]          # problemas 0-99
MIX_FLIP_B = [("largo", 0.70), ("medio", 0.30)]            # problemas 100-199

# Textos mock dimensionados para que formular_contradiccion vea lo mismo
# que en producción (corto/clase calculo -> single primero; largo -> reflexion).
TEXTO = {
    "calculo": ("¿cuánto es 17*23?", "calculo"),
    "medio": ("Explicá en un párrafo por qué el cielo se ve azul al mediodía "
              "y qué fenómenos físicos intervienen en el color observado. ",
              "general"),
    "largo": ("Analizá en detalle las causas estructurales de la crisis "
              "financiera de 2008, comparando el rol de los derivados, la "
              "regulación y la política monetaria, y extraé lecciones "
              "aplicables a la arquitectura financiera actual. " * 2,
              "general"),
}


def _rng(*partes):
    digest = hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()
    return random.Random(int(digest, 16) % (2 ** 32))


def _elegir(rng, pares_tipo_prob):
    x = rng.random()
    acc = 0.0
    for tipo, p in pares_tipo_prob:
        acc += p
        if x < acc:
            return tipo
    return pares_tipo_prob[-1][0]


def tipo_problema(rng, seed, i):
    if seed in SEEDS_ESTACIONARIAS:
        return _elegir(rng, MIX_ESTACIONARIO)
    mix = MIX_FLIP_A if i < N_PROBLEMAS // 2 else MIX_FLIP_B
    return _elegir(rng, mix)


def mejor_brazo(rng, tipo):
    return _elegir(rng, [(b, P_MEJOR[tipo][b]) for b in BRAZOS])


def orden_triz(tipo):
    texto, clase = TEXTO[tipo]
    c = formular_contradiccion(texto, clase, list(BRAZOS))
    return list(c["brazos_ordenados"])


def simular_problema(draws_rewards, orden):
    """draws_rewards: dict brazo -> reward (0/1) pre-sorteado.
    Recorre el orden, para en el primer éxito. Devuelve (pulls, elegido)."""
    vistos = []
    for k, brazo in enumerate(orden, 1):
        r = draws_rewards[brazo]
        vistos.append((brazo, r))
        if r == 1:
            return k, brazo
    # sin éxito: el mejor observado (empate -> primero en el orden)
    elegido = max(orden, key=lambda b: draws_rewards[b])
    return len(orden), elegido


def seed_exp(seed, debilitar=0.0):
    """debilitar=0: mundo pre-registrado. debilitar=0.5: distribuciones del
    mejor brazo a mitad de camino hacia uniforme (sensibilidad exploratoria)."""
    rng = _rng("exp31", seed)
    pulls = {"triz": 0, "fijo": 0, "aleatorio": 0}
    aciertos = {"triz": 0, "fijo": 0, "aleatorio": 0}
    for i in range(N_PROBLEMAS):
        tipo = tipo_problema(rng, seed, i)
        # mejor brazo verdadero (con eventual debilitamiento)
        dist = {b: (1 - debilitar) * P_MEJOR[tipo][b] + debilitar / 3.0
                for b in BRAZOS}
        mejor = _elegir(rng, [(b, dist[b]) for b in BRAZOS])
        # números aleatorios comunes: un pull por brazo
        draws = {b: 1 if rng.random() < (P_EXITO_MEJOR if b == mejor
                                         else P_EXITO_OTRO) else 0
                 for b in BRAZOS}
        ordenes = {
            "triz": orden_triz(tipo),
            "fijo": list(ORDEN_FIJO),
            "aleatorio": None,
        }
        rord = _rng("exp31-orden", seed, i)
        perm = list(BRAZOS)
        rord.shuffle(perm)
        ordenes["aleatorio"] = perm
        for nombre, orden in ordenes.items():
            n_pulls, elegido = simular_problema(draws, orden)
            pulls[nombre] += n_pulls
            aciertos[nombre] += 1 if elegido == mejor else 0
    return {"pulls_medios": {k: pulls[k] / N_PROBLEMAS for k in pulls},
            "precision": {k: aciertos[k] / N_PROBLEMAS for k in aciertos}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=RES_DIR)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    por_seed = {}
    for seed in SEEDS:
        por_seed[str(seed)] = seed_exp(seed)

    # veredicto pre-registrado
    wins = {}
    for s, r in por_seed.items():
        pm = r["pulls_medios"]
        wins[s] = bool(pm["triz"] < pm["fijo"] and pm["triz"] < pm["aleatorio"])
    W = sum(wins.values())
    acc = {k: sum(r["precision"][k] for r in por_seed.values()) / len(SEEDS)
           for k in ("triz", "fijo", "aleatorio")}
    guarda_ok = (acc["triz"] >= acc["fijo"] - 0.03
                 and acc["triz"] >= acc["aleatorio"] - 0.03)
    if W >= 7 and guarda_ok:
        veredicto = "PASS"
    elif W <= 4:
        veredicto = "FAIL"
    else:
        veredicto = "NO CONFIABLE"
    motivo = (f"W={W}/8 seeds con pulls(TRIZ)<pulls(FIJO) y <pulls(ALEATORIO); "
              f"precision media triz={acc['triz']:.3f} fijo={acc['fijo']:.3f} "
              f"aleatorio={acc['aleatorio']:.3f} "
              f"(guarda <=3pp: {'ok' if guarda_ok else 'FALLA'}).")

    # sensibilidad exploratoria (no afecta el veredicto): correlación debilitada
    sens = {}
    for seed in SEEDS:
        sens[str(seed)] = seed_exp(seed, debilitar=0.5)
    sens_w = sum(1 for s, r in sens.items()
                 if r["pulls_medios"]["triz"] < r["pulls_medios"]["fijo"]
                 and r["pulls_medios"]["triz"] < r["pulls_medios"]["aleatorio"])

    resultado = {
        "experimento": "ALMA-EXP31",
        "mock": True,
        "costo_usd": 0.0,
        "seeds": SEEDS,
        "por_seed": por_seed,
        "wins_por_seed": wins,
        "W": W,
        "precision_media": acc,
        "guarda_precision_ok": guarda_ok,
        "veredicto": veredicto,
        "motivo": motivo,
        "sensibilidad_exploratoria": {
            "descripcion": "Mismo diseño con la correlación tipo->mejor brazo "
                           "debilitada a mitad de camino hacia uniforme. "
                           "NO afecta el veredicto.",
            "W_debilitado": sens_w,
            "por_seed": sens,
        },
    }
    with open(os.path.join(args.out, "resultados.json"), "w",
              encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    # resumen legible
    lineas = ["# ALMA-EXP31 — ¿el orden TRIZ abarata el probe?",
              "",
              "Mock, US$0. Probe secuencial con parada temprana; números "
              "aleatorios comunes por problema.",
              "",
              "| seed | pulls triz | pulls fijo | pulls aleat | prec triz | "
              "prec fijo | prec aleat | win |",
              "|------|------------|------------|-------------|-----------|"
              "-----------|------------|-----|"]
    for s in SEEDS:
        r = por_seed[str(s)]
        pm, pr = r["pulls_medios"], r["precision"]
        lineas.append(
            f"| {s} | {pm['triz']:.3f} | {pm['fijo']:.3f} | "
            f"{pm['aleatorio']:.3f} | {pr['triz']:.3f} | {pr['fijo']:.3f} | "
            f"{pr['aleatorio']:.3f} | {'✓' if wins[str(s)] else '✗'} |")
    lineas += ["",
               f"**Veredicto: {veredicto}**",
               "",
               motivo,
               "",
               f"Sensibilidad exploratoria (correlación debilitada): "
               f"W={sens_w}/8."]
    with open(os.path.join(args.out, "resumen.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")

    print(f"veredicto: {veredicto}")
    print(motivo)
    print(f"sensibilidad (debilitada): W={sens_w}/8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
