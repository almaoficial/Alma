"""Screening factorial 2^(5-1) — sonda diagnóstica de la adenda
2026-10-16 (ajuste 3). NO es una corrida del meta-loop: no propone,
no adopta, no mueve el freno. Mide el paisaje (efectos principales
e interacciones de a pares) con el validador congelado sobre el
panel train cableado [400..417], tal como declara la adenda.

Diseño: resolución V, E = A·B·C·D. Factores y niveles (extremos de
SPACES): A decay 0.25/0.75 · B gate_margin 0.0/0.1 · C n0 1/4 ·
D umbral_base 1/3 · E umbral_divisor 2/6. 16 del diseño + centro +
incumbente = 18 evaluaciones. Efecto = media(y|+) − media(y|−);
detectable si |efecto| > 2·SE, con SE desde la varianza agrupada
intra-configuración (conservador bajo CRN).
"""

import itertools
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

from alma_service.metaloop import MetaLoop, TRAIN_REPS  # noqa: E402
from alma_service.scaffold import DEFAULT_SCAFFOLD  # noqa: E402

FACTORES = [  # (letra, parámetro, nivel -, nivel +)
    ("A", "decay", 0.25, 0.75),
    ("B", "gate_margin", 0.0, 0.1),
    ("C", "n0", 1, 4),
    ("D", "umbral_base", 1, 3),
    ("E", "umbral_divisor", 2, 6),
]
CENTRO = {"decay": 0.5, "gate_margin": 0.05, "n0": 2,
          "umbral_base": 2, "umbral_divisor": 4}


def diseno():
    """Las 16 configuraciones del 2^(5-1) con E = A·B·C·D.
    Devuelve [(signos {letra: ±1}, config)]."""
    filas = []
    for a, b, c, d in itertools.product((-1, 1), repeat=4):
        signos = {"A": a, "B": b, "C": c, "D": d, "E": a * b * c * d}
        cfg = {}
        for letra, param, bajo, alto in FACTORES:
            cfg[param] = alto if signos[letra] == 1 else bajo
        filas.append((signos, cfg))
    return filas


def main():
    cache = {}
    filas = diseno()
    mediciones = []  # {signos, config, media, regs}
    for signos, cfg in filas:
        media, regs = MetaLoop._evaluar(cfg, TRAIN_REPS, cache)
        mediciones.append({"signos": signos, "config": cfg,
                           "media": media, "regs": regs})
    media_centro, regs_centro = MetaLoop._evaluar(
        CENTRO, TRAIN_REPS, cache)
    incumbente = dict(DEFAULT_SCAFFOLD)
    media_inc, regs_inc = MetaLoop._evaluar(
        incumbente, TRAIN_REPS, cache)

    # Varianza agrupada intra-configuración (solo las 16 del diseño)
    n_rep = len(TRAIN_REPS)
    num, den = 0.0, 0
    for m in mediciones:
        media = m["media"]
        num += sum((r - media) ** 2 for r in m["regs"])
        den += n_rep - 1
    s2 = num / den
    se = (s2 * 4.0 / (16 * n_rep)) ** 0.5

    def efecto(columnas):
        """Contraste: media(y|producto +) − media(y|producto −)."""
        pos, neg = [], []
        for m in mediciones:
            prod = 1
            for col in columnas:
                prod *= m["signos"][col]
            (pos if prod == 1 else neg).append(m["media"])
        return sum(pos) / len(pos) - sum(neg) / len(neg)

    principales = {}
    for letra, param, _b, _a in FACTORES:
        e = efecto([letra])
        principales[param] = {"efecto": round(e, 4),
                              "detectable": abs(e) > 2 * se}
    interacciones = {}
    letras = [f[0] for f in FACTORES]
    nombre = {f[0]: f[1] for f in FACTORES}
    for l1, l2 in itertools.combinations(letras, 2):
        e = efecto([l1, l2])
        clave = f"{nombre[l1]} x {nombre[l2]}"
        interacciones[clave] = {"efecto": round(e, 4),
                                "detectable": abs(e) > 2 * se}
    hay_inter = any(v["detectable"] for v in interacciones.values())

    doc = {
        "tipo": "screening_factorial_2_5-1",
        "diseno": "2^(5-1) resolucion V, E=ABCD, niveles extremos "
                  "de SPACES; respuesta = regret medio (totales) "
                  "sobre TRAIN_REPS [400..417], validador congelado",
        "se_efecto": round(se, 4),
        "s2_agrupada": round(s2, 4),
        "umbral_detectable": round(2 * se, 4),
        "mediciones": [
            {"signos": m["signos"], "config": m["config"],
             "media_train": round(m["media"], 4)} for m in mediciones],
        "centro": {"config": CENTRO,
                   "media_train": round(media_centro, 4)},
        "incumbente": {"config": incumbente,
                       "media_train": round(media_inc, 4)},
        "efectos_principales": principales,
        "interacciones": interacciones,
        "veredicto": ("HAY interacciones detectables"
                      if hay_inter else
                      "SIN interacciones detectables"),
    }
    ruta = os.path.join(AQUI, "resultados.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    print(f"incumbente (base) media train: {media_inc:.4f}")
    print(f"centro media train: {media_centro:.4f}")
    print(f"SE(efecto) = {se:.4f} · umbral detectable = {2*se:.4f}")
    print("principales:", json.dumps(principales, ensure_ascii=False))
    print("interacciones:", json.dumps(interacciones,
                                       ensure_ascii=False))
    print("VEREDICTO:", doc["veredicto"])
    print("resultados en", ruta)


if __name__ == "__main__":
    main()
