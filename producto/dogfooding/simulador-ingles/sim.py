#!/usr/bin/env python3
"""Simulador mock (US$0) del dogfooding de inglés — pre-registro en preregistro.md.

Schedule: probe rotativo 10 noches + Thompson + skip + re-probe, 1 pull/noche,
28 noches (4 semanas). Cada mundo: 5 brazos con parámetros verdaderos aleatorios.
Vara: (1) >=70% convergencia al mejor verdadero a las 4 semanas; (2) skip falso <20%;
(3) regret_mock <= 1.5 * regret_roundrobin (ver operacionalización en preregistro.md).
"""
import math
import random

ARMS = ["A", "B", "C", "D", "E"]
LIGHT = {"A", "C", "D"}          # régimen de energía
N_NIGHTS = 28
PROBE_NIGHTS = 10
PRIOR_A = 1.0
PRIOR_B = 1.0
SKIP_MIN_PULLS = 5
SKIP_GAP = 0.15
STALE_DAYS = 7
SUNDAYS = {7, 14, 21, 28}


class World:
    def __init__(self, rng):
        self.pi = {a: rng.uniform(0.55, 1.0) for a in ARMS}       # P(p=1)
        self.mu_s = {a: rng.uniform(2.0, 4.8) for a in ARMS}      # E[s | p=1]
        self.rho = {a: rng.uniform(0.2, 0.9) for a in ARMS}       # retención
        self.true_mu = {a: self.pi[a] * (0.6 + 0.4 * self.mu_s[a] / 5.0) for a in ARMS}
        self.best = max(ARMS, key=lambda a: self.true_mu[a])
        self.unavail = {"E": 0.25, "A": 0.02, "B": 0.02, "C": 0.02, "D": 0.02}
        self.p_tired = 0.15

    def night_state(self, rng):
        tired = rng.random() < self.p_tired
        avail = {a: rng.random() >= self.unavail[a] for a in ARMS}
        return tired, avail

    def pull(self, arm, rng):
        """Devuelve (p, s, r) con r según la fórmula de la spec."""
        p = 1 if rng.random() < self.pi[arm] else 0
        if p == 0:
            return 0, None, 0.0
        s = int(round(rng.gauss(self.mu_s[arm], 0.9)))
        s = max(1, min(5, s))
        return p, s, 0.6 + 0.4 * (s / 5.0)


class Bandit:
    def __init__(self):
        self.alpha = {a: PRIOR_A for a in ARMS}
        self.beta = {a: PRIOR_B for a in ARMS}
        self.pulls = {a: 0 for a in ARMS}
        self.last_p = {a: [] for a in ARMS}     # p de los últimos pulls (máx 3)

    def observe(self, arm, r, p):
        self.alpha[arm] += r
        self.beta[arm] += (1.0 - r)
        self.pulls[arm] += 1
        self.last_p[arm].append(p)
        self.last_p[arm] = self.last_p[arm][-3:]

    def post_mean(self, arm):
        return self.alpha[arm] / (self.alpha[arm] + self.beta[arm])

    def sample(self, rng, eligible):
        return {a: rng.betavariate(self.alpha[a], self.beta[a]) for a in eligible}


def eligible_arms(tired, avail):
    pool = LIGHT if tired else set(ARMS)
    return [a for a in ARMS if a in pool and avail[a]]


def skip_candidate(b, winner):
    """Tres condiciones de la spec."""
    if b.pulls[winner] < SKIP_MIN_PULLS:
        return False
    means = sorted((b.post_mean(a) for a in ARMS), reverse=True)
    if means[0] - means[1] < SKIP_GAP:
        return False
    if len(b.last_p[winner]) < 3 or any(p != 1 for p in b.last_p[winner]):
        return False
    return True


def run_world(seed):
    rng = random.Random(seed)
    w = World(rng)
    b = Bandit()

    # Probe: 2 pulls medidos por brazo (round-robin; noches no disponibles no cuentan)
    probe_target = {a: 2 for a in ARMS}
    order = ["A", "B", "C", "D", "E"]
    oi = 0
    probe_done = {a: 0 for a in ARMS}
    chosen = []
    rewards = []

    skip_active = False
    skip_winner = None
    skip_lock_until = 0          # noche hasta la cual el skip está bloqueado
    nights_since_other = 0       # para la regla stale
    zero_p_streak = 0            # p=0 seguidos en el ganador con skip
    ret_zero_weeks = {a: 0 for a in ARMS}
    week_pulls = {a: 0 for a in ARMS}
    false_skip = False
    regret = 0.0
    regret_rr = 0.0
    rr_i = 0                     # índice round-robin del baseline

    for night in range(1, N_NIGHTS + 1):
        tired, avail = w.night_state(rng)
        elig = eligible_arms(tired, avail)
        if not elig:
            elig = [a for a in ARMS if avail[a]]  # fallback: nada elegible -> disponibles
        if not elig:
            elig = ["A"]

        probe_active = sum(probe_done.values()) < 10

        # --- selección ---
        if probe_active:
            # fase 1: rotativo hasta completar 2 pulls por brazo
            a = None
            for _ in range(5):
                cand = order[oi % 5]
                oi += 1
                if probe_done[cand] < 2 and cand in elig:
                    a = cand
                    break
            if a is None:  # brazo de rotación no disponible -> Thompson entre elegibles
                samp = b.sample(rng, elig)
                a = max(elig, key=lambda x: samp[x])
            probe_done[a] += 1
            nights_since_other = 0
        else:
            # fase 2: Thompson + skip
            if skip_active and skip_lock_until >= night:
                skip_active = False
            if skip_active and skip_winner in elig and skip_candidate(b, skip_winner):
                a = skip_winner
                nights_since_other += 1
            else:
                skip_active = False
                samp = b.sample(rng, elig)
                a = max(elig, key=lambda x: samp[x])
                nights_since_other = 0

        p, s, r = w.pull(a, rng)
        b.observe(a, r, p)
        chosen.append(a)
        rewards.append(r)
        week_pulls[a] += 1

        # --- regret vs oráculo (mismo constraint de disponibilidad/energía) ---
        oracle_arm = max(elig, key=lambda x: w.true_mu[x])
        regret += w.true_mu[oracle_arm] - w.true_mu[a]

        # --- baseline round-robin ---
        rr_arm = None
        for _ in range(5):
            cand = order[rr_i % 5]
            rr_i += 1
            if cand in elig:
                rr_arm = cand
                break
        if rr_arm is None:
            rr_arm = elig[0]
        regret_rr += w.true_mu[oracle_arm] - w.true_mu[rr_arm]

        # --- evaluar skip después de observar (fases 2+) ---
        if not probe_active and night >= skip_lock_until:
            post = {x: b.post_mean(x) for x in ARMS}
            cand = max(ARMS, key=lambda x: post[x])
            if cand == skip_winner and skip_active:
                pass  # sigue
            elif skip_candidate(b, cand):
                skip_active = True
                skip_winner = cand
                nights_since_other = 0
                if cand != w.best:
                    false_skip = True

        # --- re-probe: p=0 dos noches seguidas en el ganador ---
        if skip_active and a == skip_winner:
            zero_p_streak = zero_p_streak + 1 if p == 0 else 0
            if zero_p_streak >= 2:
                skip_active = False
                skip_lock_until = night + 3
                zero_p_streak = 0
        else:
            zero_p_streak = 0

        # --- stale: 7 noches sin probar otro brazo ---
        if skip_active and nights_since_other >= STALE_DAYS:
            others = [x for x in elig if x != skip_winner]
            if others:
                samp = b.sample(rng, others)
                a2 = max(others, key=lambda x: samp[x])
                p2, s2, r2 = w.pull(a2, rng)
                b.observe(a2, r2, p2)
                chosen[-1] = a2            # la noche exploratoria reemplaza al pull
                rewards[-1] = r2
                week_pulls[a] -= 1
                week_pulls[a2] += 1
                regret += (w.true_mu[oracle_arm] - w.true_mu[a2]) - (w.true_mu[oracle_arm] - w.true_mu[a])
            nights_since_other = 0

        # --- retención dominical ---
        if night in SUNDAYS:
            for x in ARMS:
                if week_pulls[x] > 0:
                    recalled = rng.random() < w.rho[x]
                    if skip_active and x == skip_winner:
                        ret_zero_weeks[x] = 0 if recalled else ret_zero_weeks[x] + 1
            if skip_active and ret_zero_weeks[skip_winner] >= 2:
                skip_active = False
                skip_lock_until = night + 3
            week_pulls = {a_: 0 for a_ in ARMS}

    post = {a: b.post_mean(a) for a in ARMS}
    ranked = sorted(ARMS, key=lambda a: post[a], reverse=True)
    converged = ranked[0] == w.best
    gap_best = w.true_mu[w.best] - sorted(w.true_mu.values(), reverse=True)[1]
    return {
        "seed": seed,
        "converged": converged,
        "false_skip": false_skip,
        "regret": regret,
        "regret_rr": regret_rr,
        "gap_best": gap_best,
        "pulls": b.pulls,
        "ranked": ranked,
        "best": w.best,
    }


def main(n_worlds=500, base_seed=20260928):
    results = [run_world(base_seed + i) for i in range(n_worlds)]
    conv = sum(1 for r in results if r["converged"])
    fs = sum(1 for r in results if r["false_skip"])
    reg = sum(r["regret"] for r in results) / n_worlds
    reg_rr = sum(r["regret_rr"] for r in results) / n_worlds
    ratio = reg / reg_rr if reg_rr > 0 else float("inf")
    gaps = sorted(r["gap_best"] for r in results)

    print(f"mundos={n_worlds}")
    print(f"convergencia: {conv}/{n_worlds} = {conv/n_worlds:.3f} (vara >= 0.70)")
    print(f"skip falso: {fs}/{n_worlds} = {fs/n_worlds:.3f} (vara < 0.20)")
    print(f"regret mock medio: {reg:.4f} | regret round-robin medio: {reg_rr:.4f} | cociente: {ratio:.3f} (vara <= 1.5)")
    print(f"gap mejor-segundo verdadero: mediana={gaps[n_worlds//2]:.3f} p10={gaps[int(n_worlds*0.1)]:.3f} p90={gaps[int(n_worlds*0.9)]:.3f}")
    # convergencia condicional al gap
    import statistics
    small = [r for r in results if r["gap_best"] < 0.05]
    big = [r for r in results if r["gap_best"] >= 0.10]
    if small:
        print(f"conv | gap<0.05: {sum(r['converged'] for r in small)}/{len(small)} = {sum(r['converged'] for r in small)/len(small):.3f}")
    if big:
        print(f"conv | gap>=0.10: {sum(r['converged'] for r in big)}/{len(big)} = {sum(r['converged'] for r in big)/len(big):.3f}")
    # barras crudas: pulls por brazo promedio
    avg_pulls = {a: statistics.mean(r["pulls"][a] for r in results) for a in ARMS}
    print(f"pulls medios por brazo: " + ", ".join(f"{a}={avg_pulls[a]:.1f}" for a in ARMS))


if __name__ == "__main__":
    main()
