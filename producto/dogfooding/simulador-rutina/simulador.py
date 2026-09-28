#!/usr/bin/env python3
"""
SIM-RUTINA — simulador mock del dogfooding de rutina de ALMA.
US$0, autocontenido, no toca alma_service ni el servicio vivo.

Diseño congelado en preregistro.md (2026-09-28). No cambiar parámetros
después de ver números: la vara es sagrada.

Uso:
    python3 simulador.py --split A --out resultados/splitA.json
    python3 simulador.py --split B --out resultados/splitB.json
"""
import argparse
import json
import math
import random
from collections import defaultdict

# ----------------------------------------------------------------------------
# Parámetros congelados (preregistro §3 y §6)
# ----------------------------------------------------------------------------
ARMS = ["playa", "gym", "descanso", "mixto"]
N_DAYS = 120
EVAL_START = 61          # ventana de evaluación: días 61..120 (1-indexed)
N0 = 4.0                # fuerza del prior
DECAY = 0.5             # olvido
SKIP_THRESHOLD = 1.0 / 3.0   # umbral_base / umbral_divisor
P_CUMPLIMIENTO = 0.8
BOOTSTRAP_REPS = 10000

BASE_Q = {
    ("libre", "playa"): 1.25, ("libre", "gym"): 0.80,
    ("libre", "descanso"): 0.15, ("libre", "mixto"): 0.65,
    ("turno", "playa"): 0.10, ("turno", "gym"): -0.55,
    ("turno", "descanso"): 0.60, ("turno", "mixto"): -0.10,
}
P_TURNO_OPTS = (0.35, 0.50, 0.65, 0.80)

SPLITS = {
    "A": {"world": 101, "loop": 1001, "tglobal": 1002},
    "B": {"world": 202, "loop": 2001, "tglobal": 2002},
}

# ----------------------------------------------------------------------------
# Mundo sintético
# ----------------------------------------------------------------------------
class Mundo:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        # bloques de 15..25 días con p_turno y perturbaciones por bloque
        self.blocks = []
        d = 0
        while d < N_DAYS:
            L = self.rng.randint(15, 25)
            p_turno = self.rng.choice(P_TURNO_OPTS)
            delta = {(t, a): self.rng.gauss(0, 0.35)
                     for t in ("libre", "turno") for a in ARMS}
            self.blocks.append({"start": d, "len": L, "p_turno": p_turno,
                                "delta": delta})
            d += L
        # tipo de día por día (0-indexed)
        self.tipos = []
        for b in self.blocks:
            for _ in range(b["len"]):
                if len(self.tipos) >= N_DAYS:
                    break
                self.tipos.append("turno" if self.rng.random() < b["p_turno"]
                                  else "libre")

    def block_of(self, day):
        for b in self.blocks:
            if b["start"] <= day < b["start"] + b["len"]:
                return b
        return self.blocks[-1]

    def q(self, day, tipo, brazo):
        b = self.block_of(day)
        return BASE_Q[(tipo, brazo)] + b["delta"][(tipo, brazo)]

    def mean_q_over_horizon(self, tipo, brazo):
        """Calidad media verdadera sobre el horizonte (para el oráculo)."""
        tot, n = 0.0, 0
        for day in range(N_DAYS):
            if self.tipos[day] == tipo:
                tot += self.q(day, tipo, brazo)
                n += 1
        return tot / n if n else 0.0


def racha_sueno_corta(suenos):
    return len(suenos) >= 2 and sum(suenos[-2:]) / 2 < 6.0


def racha_energia_baja(energias):
    return len(energias) >= 3 and all(e < 5 for e in energias[-3:])


def firma(tipo, suenos, energias):
    return (tipo,
            1 if racha_sueno_corta(suenos) else 0,
            1 if racha_energia_baja(energias) else 0)


# ----------------------------------------------------------------------------
# Políticas
# ----------------------------------------------------------------------------
class ThompsonRegimen:
    """ALMA-full: Thompson por firma de régimen + probe + skip + olvido."""

    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.post = defaultdict(lambda: {a: [1 + N0 * 0.5, 1 + N0 * 0.5]
                                        for a in ARMS})
        self.probe_days = 0
        self.skip_days = 0
        self.decisions = 0

    def decidir(self, sig):
        self.decisions += 1
        means = {a: self.post[sig][a][0] / (self.post[sig][a][0] +
                                            self.post[sig][a][1])
                 for a in ARMS}
        orden = sorted(ARMS, key=lambda a: (-means[a], a))
        f, segundo = orden[0], orden[1]
        if means[f] - means[segundo] >= SKIP_THRESHOLD:
            self.skip_days += 1
            return f, False
        theta = {a: self.rng.betavariate(*self.post[sig][a]) for a in ARMS}
        elegido = max(ARMS, key=lambda a: (theta[a], a))
        es_probe = elegido != f
        if es_probe:
            self.probe_days += 1
        return elegido, es_probe

    def actualizar(self, sig, brazo, r):
        a, b = self.post[sig][brazo]
        a, b = DECAY * a, DECAY * b
        a += r
        b += (1.0 - r)
        self.post[sig][brazo] = [a, b]


class ThompsonGlobal:
    """Mismo scaffold, una sola firma (ignora el régimen)."""

    def __init__(self, seed):
        self.inner = ThompsonRegimen(seed)

    def decidir(self, sig):
        return self.inner.decidir(("global",))

    def actualizar(self, sig, brazo, r):
        self.inner.actualizar(("global",), brazo, r)


class FijaOraculo:
    """Mejor rutina fija: mapeo tipo_día -> brazo óptimo según ground truth."""

    def __init__(self, mundo):
        self.mapa = {}
        for tipo in ("libre", "turno"):
            self.mapa[tipo] = max(
                ARMS, key=lambda a: mundo.mean_q_over_horizon(tipo, a))

    def decidir(self, sig):
        return self.mapa[sig[0]], False

    def actualizar(self, sig, brazo, r):
        pass


# ----------------------------------------------------------------------------
# Corrida de una política sobre el mundo
# ----------------------------------------------------------------------------
def correr(mundo, politica, seed_ruido):
    rng = random.Random(seed_ruido)
    energias = [6.5]       # energía_1 (mañana del día 1, ya observada)
    suenos = []
    brazos_jugados = []
    cumplimientos = []
    rewards = []
    es_probe = []

    for day in range(N_DAYS):          # day 0-indexed = día day+1
        tipo = mundo.tipos[day]
        sig = firma(tipo, suenos, energias)
        sugerido, probe = politica.decidir(sig)
        # cumplimiento: jugar lo sugerido con p=0.8
        if rng.random() < P_CUMPLIMIENTO:
            jugado = sugerido
            cumpl = 1
        else:
            jugado = rng.choice([a for a in ARMS if a != sugerido])
            cumpl = 0
        # sueño de la noche del día t
        base_s = 6.2 if tipo == "turno" else 7.2
        if jugado in ("playa", "gym"):
            base_s += 0.15
        s = min(10.0, max(3.5, rng.gauss(base_s, 0.9 if tipo == "turno"
                                         else 0.8)))
        suenos.append(s)
        # energía del día siguiente
        q = mundo.q(day, tipo, jugado)
        if racha_energia_baja(energias):
            q += 0.8 if jugado == "descanso" else (-0.6 if jugado == "gym"
                                                  else 0.0)
        if racha_sueno_corta(suenos):
            q += 0.5 if jugado == "descanso" else (-0.4 if jugado == "gym"
                                                  else 0.0)
        e_next = 5.6 + q + 0.45 * (s - 6.5) + rng.gauss(0, 1.1)
        e_next = min(10.0, max(1.0, e_next))
        energias.append(e_next)
        # reward del día t (observado en t+1)
        r = 0.7 * (e_next - 1.0) / 9.0 + 0.3 * cumpl
        politica.actualizar(sig, jugado, r)

        brazos_jugados.append(jugado)
        cumplimientos.append(cumpl)
        rewards.append(r)
        es_probe.append(1 if probe else 0)

    return {
        "energias": energias[1:],      # energía observada cada noche (120)
        "suenos": suenos,
        "brazos": brazos_jugados,
        "cumplimientos": cumplimientos,
        "rewards": rewards,
        "probe": es_probe,
    }


# ----------------------------------------------------------------------------
# Estadística: bootstrap del Δ
# ----------------------------------------------------------------------------
def bootstrap_ci(x, y, reps=BOOTSTRAP_REPS, seed=777):
    rng = random.Random(seed)
    nx, ny = len(x), len(y)
    diffs = []
    for _ in range(reps):
        mx = sum(x[rng.randrange(nx)] for _ in range(nx)) / nx
        my = sum(y[rng.randrange(ny)] for _ in range(ny)) / ny
        diffs.append(mx - my)
    diffs.sort()
    lo = diffs[int(0.025 * reps)]
    hi = diffs[int(0.975 * reps)]
    return lo, hi


def resumen(vals):
    n = len(vals)
    m = sum(vals) / n
    v = sum((v - m) ** 2 for v in vals) / (n - 1) if n > 1 else 0.0
    return {"n": n, "media": m, "sd": math.sqrt(v)}


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["A", "B"], required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    S = SPLITS[args.split]

    mundo = Mundo(S["world"])
    fija = FijaOraculo(mundo)

    res = {}
    series = {}
    pols = {
        "alma_full": ThompsonRegimen(S["loop"]),
        "mejor_fija": fija,
        "thompson_global": ThompsonGlobal(S["tglobal"]),
    }
    for nombre, pol in pols.items():
        # ruido independiente por política (semilla derivada, determinista)
        r = correr(mundo, pol, seed_ruido=9000 + S["world"] * 7 +
                   {"alma_full": 1, "mejor_fija": 2,
                    "thompson_global": 3}[nombre])
        ev = slice(EVAL_START - 1, N_DAYS)   # días 61..120
        res[nombre] = {
            "energia_eval": resumen(r["energias"][ev]),
            "reward_eval": resumen(r["rewards"][ev]),
            "cumplimiento_eval": sum(r["cumplimientos"][ev]) /
                                 len(r["cumplimientos"][ev]),
            "tasa_probe_eval": sum(r["probe"][ev]) / len(r["probe"][ev]),
            "mapa_fija": fija.mapa if nombre == "mejor_fija" else None,
        }
        if nombre == "alma_full":
            res[nombre]["skip_days_total"] = pol.skip_days  # descriptivo
            res[nombre]["probe_days_total"] = pol.probe_days
        series[nombre] = r["energias"][ev]

    lo, hi = bootstrap_ci(series["alma_full"], series["mejor_fija"])
    d = (sum(series["alma_full"]) / len(series["alma_full"]) -
         sum(series["mejor_fija"]) / len(series["mejor_fija"]))
    lo_g, hi_g = bootstrap_ci(series["alma_full"], series["thompson_global"])
    d_g = (sum(series["alma_full"]) / len(series["alma_full"]) -
           sum(series["thompson_global"]) / len(series["thompson_global"]))

    out = {
        "split": args.split,
        "seeds": S,
        "n_dias": N_DAYS,
        "ventana_eval": [EVAL_START, N_DAYS],
        "politicas": res,
        "delta_loop_vs_fija": {"delta": d, "ic95": [lo, hi],
                               "pass": lo > 0},
        "delta_loop_vs_tglobal": {"delta": d_g, "ic95": [lo_g, hi_g]},
        "bloques": [{"start": b["start"] + 1, "len": b["len"],
                     "p_turno": b["p_turno"]} for b in mundo.blocks],
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"split {args.split}: Δ loop−fija = {d:+.3f} IC95 [{lo:+.3f}, {hi:+.3f}] "
          f"→ {'PASS' if lo > 0 else 'FAIL'}")
    print(f"  mapa fija oráculo: {fija.mapa}")


if __name__ == "__main__":
    main()
