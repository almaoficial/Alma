"""Scaffold del servicio: hiperparámetros validados de la política.

EXP56 (RSO estilo MiniMax, mock US$0) evolucionó 5 hiperparámetros del
scaffold de EXP51 en 24 rondas greedy con validador congelado; EXP57
(ablación + replicación en seed independiente) confirmó que n0=4 y
umbral_base=1 son load-bearing (revertirlos empeora el regret) y que
umbral_base=1 es además protector (sin él, el scaffold queda PEOR que
la política manual). El keep de umbral_divisor 3→2 resultó ruido de
entrenamiento (revertirlo mejora el held-out): se conserva el valor
original 3.

Estos son los defaults del servicio. No son constantes mágicas: cada
valor tiene su experimento y su ablación. No cambiar sin evidencia
falsable (diseño §3.2, anti-DGM).

Las funciones parametrizadas son puertos verbatim de
exp56_rso/run_experiment56.py (a su vez copias verbatim de
run_experiment47/run_experiment49 con las constantes como argumentos).
"""

from alma.selector import BanditPorClase

# Defaults validados por EXP56/57 (dos seeds independientes).
DEFAULT_SCAFFOLD = {
    "n0": 4,            # EXP45-51: 2 → validado 4 (load-bearing, EXP57)
    "umbral_base": 1,   # EXP49: 2 → validado 1 (load-bearing y protector)
    "umbral_divisor": 3,  # EXP56 lo movió a 2; EXP57 mostró que era ruido
    "decay": 0.5,       # sin cambios (el loop no lo movió)
    "gate_margin": 0.0,  # sin cambios
}


def umbral_soporte(k, umbral_base=None, umbral_divisor=None):
    """Umbral endurecido con el horizonte.

    umbral(K) = umbral_base + floor(K / umbral_divisor).
    Sin argumentos usa los defaults validados (1 + floor(K/3)).
    """
    ub = (DEFAULT_SCAFFOLD["umbral_base"] if umbral_base is None
          else umbral_base)
    ud = (DEFAULT_SCAFFOLD["umbral_divisor"] if umbral_divisor is None
          else umbral_divisor)
    return ub + k // ud


def prior_params_param(brazos, rep_hist, block_sig, b, sig, n0, decay):
    """Copia verbatim de e47.prior_params con N0->n0, DECAY->decay."""
    params = {}
    for a in brazos:
        if sig is None:
            obs = [(r, blk) for (h, r, blk) in rep_hist[a] if blk < b]
        else:
            obs = [(r, blk) for (h, r, blk) in rep_hist[a]
                   if blk < b and block_sig.get(blk) == sig]
            if not obs:
                obs = [(r, blk) for (h, r, blk) in rep_hist[a] if blk < b]
        if obs:
            ws = [decay ** (b - 1 - blk) for (_, blk) in obs]
            sw = sum(ws)
            m = sum(r * w for (r, _), w in zip(obs, ws)) / sw
        else:
            m = 0.5
        params[a] = (1.0 + n0 * m, 1.0 + n0 * (1.0 - m))
    return params


def nuevo_bandit_param(brazos, params, n0):
    """Copia verbatim de e47.nuevo_bandit con N0->n0."""
    bandit = BanditPorClase(brazos)
    for a in brazos:
        bandit.alpha[a], bandit.beta[a] = params[a]
        bandit.pulls[a] = n0
    return bandit


def soporte_param(brazos, probe_obs, block_sig, b, sig, skill_arm,
                  umbral_base, umbral_divisor):
    """Copia verbatim de e49.soporte_endurecido salvo la fórmula del umbral:
    umbral(K) = umbral_base + floor(K / umbral_divisor)."""
    wins = 0
    K = 0
    for b2 in range(b):
        if block_sig.get(b2) != sig:
            continue
        obs = probe_obs.get(b2)
        if not obs:
            continue  # bloque saltado: sin comparación pareada
        K += 1
        m_s = sum(obs[skill_arm]) / len(obs[skill_arm])
        if all(m_s > sum(obs[a]) / len(obs[a])
               for a in brazos if a != skill_arm):
            wins += 1
    umbral = umbral_base + K // umbral_divisor
    return wins >= umbral, wins, K, umbral
