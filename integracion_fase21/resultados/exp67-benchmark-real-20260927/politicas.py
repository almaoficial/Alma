#!/usr/bin/env python3
"""ALMA-EXP67 fase de politicas (la pregunta principal del experimento).

5 politicas sobre el stream pre-registrado de 180 problemas reales
(9 bloques x 20, orden del manifiesto): alma-full vs fija-single /
fija-cot / fija-reflexion vs thompson-global. Cada politica procesa el
stream en orden; por problema elige un brazo -> 1 llamada real a
deepseek-flash. Regret contra el mejor reward posible segun el oraculo
(oracle_pulls.jsonl). NO dictamina PASS/FAIL: eso se hace contra la vara
pre-registrada fuera de este script.

Disciplina del probe (espeja run_exp62.py::correr_alma_full, fase
62B-alma-probe — no inventada):
  - Al entrar a cada bloque NO saltado: probe de los PRIMEROS 3 problemas
    del bloque x 3 brazos = 9 llamadas, fase "exp67-politicas-probe".
  - probe_choice: default "single"; se sube a cot/reflexion solo si su
    media de probe supera a la del elegido por > 0.05 (PROBE_MARGEN).
  - Los pulls del probe SON los outcomes de alma-full en esas 3
    posiciones (rewards[pos] = probe_rs[elegido][q], como en EXP62).

Skip del probe (port fiel de EXP49/51/52, cada elemento con analogo
directo en tarea real — nada inventado):
  - firma del regimen -> slice (diseno_stream.md: "el regimen cambia en
    cada bloque").
  - skill_arm -> argmax de las medias del prior warm condicionado al
    slice, desempate determinista al primer maximo (como
    e47.skill_arm_actual).
  - probe_obs[b] -> {brazo: [3 rewards]} de los bloques con probe
    completo; None si el bloque se salto (como en EXP51).
  - win -> el skill arm tiene media de probe ESTRICTAMENTE mayor que
    cada otro brazo (como e49.soporte_endurecido; EXP52 "soporte-puro":
    solo probes completos cuentan para K y wins).
  - umbral(K) = umbral_base + K//umbral_divisor = 1 + K//3 (scaffold
    vigente). K = bloques pasados no-saltados del mismo slice con probe
    completo.
  - Si wins >= umbral -> se salta el probe: las 20 posiciones van con
    skill_arm, sin pulls de probe (camino "PROBE SALTADO" de EXP51).
  - Diagnostico de misfire ex post: skill_arm vs mejor brazo del bloque
    segun el oraculo.

Warm-start de alma-full ("Thompson por slice", scaffold vigente):
  - Al entrar a cada bloque: bandit fresco con prior
    alpha = 1 + n0*m, beta = 1 + n0*(1-m), n0 = 4.
  - m = media con olvido de rewards pasados del MISMO slice
    (w = decay^(b-1-blk), decay = 0.5), fallback a toda la historia,
    fallback a 0.5 (estructura de e47.prior_params sin firmas
    sinteticas).
  - Repertorio "hacia adelante": oracle + probe + pulls propios de
    alma-full con pos < base del bloque (sin lookahead; espeja
    repertorio_hacia_adelante de EXP62, que incluia el oraculo).

Evaluador identico al EXP62:
  reward = 0.75*exito + 0.25*(1 - costo_rel/5),
  costo_rel del registry {single:1.0, cot:1.2, reflexion:4.0}.
RNG pareado por posicion entre politicas: random.Random(f"exp67-{seed}-{pos}").

Idempotencia:
  - pulls de politica: (fase="exp67-politicas", policy, pos)
    -> politicas_pulls.jsonl
  - pulls de probe: (fase="exp67-politicas-probe", bloque, arm, probe_idx)
    -> politicas_probe.jsonl
Resume limpio: el bandit se reconstruye deterministicamente desde los
archivos (warm-start + replay en orden), asi que un resume retoma exacto.

Freno duro: --tope (default US$0.45) sobre el gasto de ESTA fase
(politicas + probe). Al alcanzarlo: RuntimeError, parcial guardado,
exit 2, sin regret.

La key viaja SOLO por DEEPSEEK_API_KEY (variable de entorno). Este
script nunca la escribe en disco ni en logs. --dry-run no necesita key.

Uso:
    DEEPSEEK_API_KEY=... ~/workspace/venvs/exp67/bin/python politicas.py --out <dir>
    ... politicas.py --out <dir> --dry-run   # sin API
    ... politicas.py --out <dir> --tope 0.60  # freno distinto
"""
import argparse
import json
import os
import random
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.expanduser("~"),
                                "workspace/alma-prototype/exp62_deepseek"))
sys.path.insert(0, os.path.join(os.path.expanduser("~"),
                                "workspace/alma-prototype"))

import pilot
from pilot import ARMS, cargar_problemas, chequeo_scorers, puntuar
from run_exp62 import DeepSeekBackend, ejecutar
from alma.selector import BanditPorClase

# ---------------------------------------------------------------- constantes

COSTO_REL = {"single": 1.0, "cot": 1.2, "reflexion": 4.0}
MAX_COSTO_REL = 5.0
W_EXITO, W_COSTO = 0.75, 0.25

N0 = 4               # warm-start (scaffold vigente; EXP62 usaba 2)
DECAY = 0.5          # olvido por bloque en el warm-start (scaffold)
UMBRAL_BASE = 1      # skip gate: umbral(K) = 1 + K//3 (scaffold)
UMBRAL_DIVISOR = 3
PROBE_N = 3          # problemas por probe (los PRIMEROS del bloque)
PROBE_MARGEN = 0.05  # margen de probe_choice (EXP62)
POR_BLOQUE = 20
N_BLOQUES = 9

POLITICAS = ["fija-single", "fija-cot", "fija-reflexion",
             "thompson-global", "alma-full"]
FASE_POL = "exp67-politicas"
FASE_PROBE = "exp67-politicas-probe"
TOPE_USD = 0.45
SEED = 67

ORDEN_SLICES_PRE = ["gsm8k", "mmlu", "mbpp", "mmlu", "gsm8k",
                    "mbpp", "gsm8k", "mmlu", "mbpp"]


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def reward_eval(exito, arm):
    """Evaluador identico al EXP62 (alma/evaluator.py)."""
    return (W_EXITO * exito
            + W_COSTO * (1.0 - COSTO_REL[arm] / MAX_COSTO_REL))


# ---------------------------------------------------------------- skip gate (port de EXP49/51/52)

def umbral_endurecido(K):
    """Umbral del gate de skip con los params del scaffold vigente."""
    return UMBRAL_BASE + K // UMBRAL_DIVISOR


def decidir_skip(b, slice_b, slices, skill_arm, probe_obs):
    """Port de e49.soporte_endurecido: firma -> slice; solo probes
    completos cuentan (EXP52 soporte-puro). Retorna
    (saltar, wins, K, umbral)."""
    wins, K = 0, 0
    for b2 in range(b):
        if slices[b2] != slice_b:
            continue
        obs = probe_obs.get(b2)
        if not obs:
            continue  # bloque saltado: sin comparacion pareada
        if any(len(v) != PROBE_N for v in obs.values()):
            continue  # probe incompleto: no cuenta (soporte-puro)
        K += 1
        m_s = mean(obs[skill_arm])
        if all(m_s > mean(obs[a]) for a in ARMS if a != skill_arm):
            wins += 1
    umbral = umbral_endurecido(K)
    return wins >= umbral, wins, K, umbral


def probe_choice(probe_rs):
    """Default barato + margen (EXP62 verbatim, 3 brazos)."""
    orden = ["single", "cot", "reflexion"]
    elegido = "single"
    for cand in orden[1:]:
        if mean(probe_rs[cand]) - mean(probe_rs[elegido]) > PROBE_MARGEN:
            elegido = cand
    return elegido


# ---------------------------------------------------------------- oraculo

def cargar_oraculo(path):
    """Lee oracle_pulls.jsonl. Retorna (por_pid, plano) donde por_pid:
    pid -> {arm: [exitos]} y plano: lista de
    (bloque, slice, arm, reward_eval)."""
    pulls = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            pulls.append(json.loads(line))
    return pulls


def mejor_oraculo_por_pid(pulls_oraculo):
    """Mejor reward posible por problema segun el oraculo, en la escala
    del evaluador: max sobre brazos de
    0.75*media_exito + 0.25*(1 - costo_rel/5)."""
    por_pid = {}
    for r in pulls_oraculo:
        por_pid.setdefault(r["pid"], {}).setdefault(
            r["arm"], []).append(r["reward"])
    mejor = {}
    for pid, arms in por_pid.items():
        top = max(reward_eval(mean(v), a) for a, v in arms.items())
        mejor[pid] = top
    return mejor


def mejor_brazo_oraculo_por_bloque(pulls_oraculo, problemas):
    """Para el diagnostico de misfire: mejor brazo por bloque segun el
    oraculo (media de reward_eval sobre los 20 problemas)."""
    por_pid_arm = {}
    for r in pulls_oraculo:
        por_pid_arm.setdefault((r["pid"], r["arm"]), []).append(r["reward"])
    out = {}
    for b in range(N_BLOQUES):
        base = b * POR_BLOQUE
        medias = {}
        for a in ARMS:
            vals = [reward_eval(mean(por_pid_arm[(p["id"], a)]), a)
                    for p in problemas[base:base + POR_BLOQUE]]
            medias[a] = mean(vals)
        out[b] = max(ARMS, key=lambda a: medias[a])
    return out


# ---------------------------------------------------------------- fase (archivos, freno, idempotencia)

class FasePoliticas:
    def __init__(self, out, tope_usd=TOPE_USD, dry=False):
        self.out = out
        self.tope = tope_usd
        self.dry = dry
        os.makedirs(out, exist_ok=True)
        self.pulls_path = os.path.join(out, "politicas_pulls.jsonl")
        self.probe_path = os.path.join(out, "politicas_probe.jsonl")
        self.hechos = {}   # (policy, pos) -> rec
        self.probes = {}   # (bloque, arm, probe_idx) -> rec
        self.gastado = 0.0
        for path, dest, keyf in (
                (self.pulls_path, self.hechos,
                 lambda r: (r["policy"], r["pos"])),
                (self.probe_path, self.probes,
                 lambda r: (r["bloque"], r["arm"], r["probe_idx"]))):
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        r = json.loads(line)
                        dest[keyf(r)] = r
                        self.gastado += r.get("costo_usd", 0.0)
        if self.hechos or self.probes:
            print(f"   resume [{FASE_POL}]: {len(self.hechos)} pulls de "
                  f"politica, {len(self.probes)} de probe, gastado previo "
                  f"${self.gastado:.4f}")

    def _frenar_si_tope(self):
        if self.gastado >= self.tope:
            raise RuntimeError(
                f"freno duro US${self.tope:.2f} alcanzado "
                f"({len(self.hechos)} pulls de politica + "
                f"{len(self.probes)} de probe)")

    def _pull_api(self, p, arm, backend, ejecutar):
        """Un llamado real (o stub determinista en dry-run). Retorna
        (exito, reward_eval, costo_usd, uso, head)."""
        if self.dry:
            import zlib
            ex = 1 if (zlib.crc32(f"{p['id']}:{arm}".encode()) % 10) < 6 else 0
            return ex, reward_eval(ex, arm), 0.0, \
                {"prompt_tokens": 0, "completion_tokens": 0}, "dry"
        res = ejecutar(arm, p, backend)
        ex = puntuar(p, res["respuesta"])
        return (ex, reward_eval(ex, arm), res["costo_usd"], res["uso"],
                res["respuesta"][:300])

    def probe_pull(self, b, q, p, arm, backend, ejecutar):
        key = (b, arm, q)
        if key in self.probes:
            return self.probes[key]["reward"]
        self._frenar_si_tope()
        ex, rew, costo, uso, head = self._pull_api(p, arm, backend, ejecutar)
        self.gastado += costo
        rec = {"fase": FASE_PROBE, "bloque": b, "probe_idx": q,
               "pid": p["id"], "slice": p["slice"], "arm": arm,
               "exito": ex, "reward": round(rew, 4),
               "costo_usd": round(costo, 6),
               "in": uso["prompt_tokens"], "out": uso["completion_tokens"],
               "respuesta_head": head}
        with open(self.probe_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.probes[key] = rec
        return rew

    def policy_pull(self, policy, pos, p, arm, backend, ejecutar,
                    via_probe=False, probe_reward=None, probe_rec=None):
        key = (policy, pos)
        if key in self.hechos:
            return self.hechos[key]["reward"]
        if via_probe:
            rew = probe_reward
            ex = probe_rec["exito"]
            rec = {"fase": FASE_POL, "policy": policy, "pos": pos,
                   "pid": p["id"], "slice": p["slice"], "arm": arm,
                   "exito": ex, "reward": round(rew, 4), "costo_usd": 0.0,
                   "via_probe": True,
                   "in": probe_rec["in"], "out": probe_rec["out"],
                   "respuesta_head": probe_rec["respuesta_head"]}
        else:
            self._frenar_si_tope()
            ex, rew, costo, uso, head = self._pull_api(
                p, arm, backend, ejecutar)
            self.gastado += costo
            rec = {"fase": FASE_POL, "policy": policy, "pos": pos,
                   "pid": p["id"], "slice": p["slice"], "arm": arm,
                   "exito": ex, "reward": round(rew, 4),
                   "costo_usd": round(costo, 6), "via_probe": False,
                   "in": uso["prompt_tokens"],
                   "out": uso["completion_tokens"],
                   "respuesta_head": head}
        with open(self.pulls_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.hechos[key] = rec
        return rew

    def probe_obs(self):
        """{b: {arm: [rewards]} | None} desde lo persistido."""
        obs = {}
        for (b, arm, q), r in self.probes.items():
            obs.setdefault(b, {}).setdefault(arm, []).append(r["reward"])
        return obs

    def bloque_tocado(self, policy, b):
        base = b * POR_BLOQUE
        return any((policy, base + q) in self.hechos
                   for q in range(POR_BLOQUE))


# ---------------------------------------------------------------- repertorio y warm-start

def construir_repertorio(fase, pulls_oraculo, problemas):
    """Repertorio 'hacia adelante' (espeja repertorio_hacia_adelante de
    EXP62): oracle + probe + pulls propios de alma-full. Por brazo:
    lista de (bloque, slice, reward_eval). Los rewards del oraculo
    (binarios) se convierten a la escala del evaluador."""
    pos_de_pid = {p["id"]: i for i, p in enumerate(problemas)}
    rep = {a: [] for a in ARMS}
    for r in pulls_oraculo:
        pos = pos_de_pid.get(r["pid"])
        if pos is None:
            continue
        rep[r["arm"]].append((pos // POR_BLOQUE, r["slice"],
                              reward_eval(r["reward"], r["arm"])))
    for (b, arm, _q), r in fase.probes.items():
        rep[arm].append((b, r["slice"], r["reward"]))
    for (policy, pos), r in fase.hechos.items():
        if policy != "alma-full" or r.get("via_probe"):
            continue
        rep[r["arm"]].append((pos // POR_BLOQUE, r["slice"], r["reward"]))
    return rep


def warm_start_params(rep, b, slice_b):
    """Prior warm con olvido, condicionado al slice (fallback a toda la
    historia, fallback a 0.5) — estructura de e47.prior_params sin
    firmas sinteticas. Retorna {arm: (alpha, beta)} con n0=4."""
    params = {}
    for a in ARMS:
        obs_same = [(blk, r) for (blk, sl, r) in rep[a]
                    if blk < b and sl == slice_b]
        obs = obs_same or [(blk, r) for (blk, _sl, r) in rep[a] if blk < b]
        if obs:
            ws = [DECAY ** (b - 1 - blk) for (blk, _r) in obs]
            m = (sum(r * w for (_b, r), w in zip(obs, ws)) / sum(ws))
        else:
            m = 0.5
        params[a] = (1.0 + N0 * m, 1.0 + N0 * (1.0 - m))
    return params


def nuevo_bandit(params):
    b = BanditPorClase(ARMS)
    for a in ARMS:
        b.alpha[a], b.beta[a] = params[a]
        b.pulls[a] = N0
    return b


def skill_arm_para(params):
    """Brazo de la 'skill' del slice: argmax de las medias del prior,
    desempate determinista al primer maximo (como e47.skill_arm_actual)."""
    medias = {a: params[a][0] / (params[a][0] + params[a][1]) for a in ARMS}
    return max(ARMS, key=lambda a: medias[a])


# ---------------------------------------------------------------- politicas

def correr_fija(fase, policy, stream, backend, ejecutar):
    arm = policy.split("-")[1]
    for pos, p in enumerate(stream):
        if (policy, pos) in fase.hechos:
            continue
        fase.policy_pull(policy, pos, p, arm, backend, ejecutar)


def correr_thompson_global(fase, stream, seed, backend, ejecutar):
    policy = "thompson-global"
    bandit = BanditPorClase(ARMS)  # prior uniforme (control)
    for pos, p in enumerate(stream):
        if (policy, pos) in fase.hechos:
            r0 = fase.hechos[(policy, pos)]
            bandit.update(r0["arm"], r0["reward"])
            continue
        rng = random.Random(f"exp67-{seed}-{pos}")
        arm = bandit.select(rng)
        r = fase.policy_pull(policy, pos, p, arm, backend, ejecutar)
        bandit.update(arm, r)


def correr_alma_full(fase, stream, slices, seed, pulls_oraculo,
                     mejor_brazo_bloque, backend, ejecutar):
    elecciones = {}
    for b in range(N_BLOQUES):
        base = b * POR_BLOQUE
        slice_b = slices[b]
        rep = construir_repertorio(fase, pulls_oraculo, stream)
        params = warm_start_params(rep, b, slice_b)
        skill_arm = skill_arm_para(params)
        obs = fase.probe_obs()

        # --- estado persistido del bloque (para resume) ---
        probe_hecho = {a: [] for a in ARMS}
        for a in ARMS:
            qs = sorted(q for (bb, aa, q) in fase.probes
                        if bb == b and aa == a)
            probe_hecho[a] = qs
        pol_hecho = sorted(pos for (pol, pos) in fase.hechos
                           if pol == "alma-full"
                           and base <= pos < base + POR_BLOQUE)

        # --- decision de skip: determinista; en resume el camino ya quedo
        # fijado por lo persistido (probe -> camino con probe; pulls sin
        # probe -> camino saltado); si el bloque esta virgen se decide ahora.
        probe_iniciado = any(probe_hecho[a] for a in ARMS)
        if probe_iniciado:
            saltar, wins, K, umbral = False, None, None, None
        elif pol_hecho:
            saltar, wins, K, umbral = True, None, None, None
        else:
            saltar, wins, K, umbral = decidir_skip(
                b, slice_b, slices, skill_arm, obs)

        if saltar:
            # PROBE SALTADO (camino de EXP51): todo el bloque con skill_arm,
            # sin bandit, sin pulls de probe.
            for q in range(POR_BLOQUE):
                pos = base + q
                if ("alma-full", pos) in fase.hechos:
                    continue
                fase.policy_pull("alma-full", pos, stream[pos], skill_arm,
                                 backend, ejecutar)
            elecciones[b] = {"slice": slice_b, "saltado": True,
                             "skill_arm": skill_arm, "wins": wins, "K": K,
                             "umbral": umbral,
                             "misfire": bool(
                                 skill_arm != mejor_brazo_bloque[b]),
                             "mejor_oraculo": mejor_brazo_bloque[b]}
            print(f"  bloque {b} ({slice_b}): probe SALTADO "
                  f"(skill={skill_arm} wins={wins} K={K} "
                  f"umbral={umbral})", flush=True)
            continue

        # --- camino con probe (disciplina EXP62) ---
        bandit = nuevo_bandit(params)
        # replay en orden: probe (q, arm) luego pulls propios (pos)
        for q in range(PROBE_N):
            for a in ARMS:
                if (b, a, q) in fase.probes:
                    bandit.update(a, fase.probes[(b, a, q)]["reward"])
        for pos in pol_hecho:
            r0 = fase.hechos[("alma-full", pos)]
            if not r0.get("via_probe"):
                bandit.update(r0["arm"], r0["reward"])

        probe_rs = {a: [] for a in ARMS}
        for q in range(PROBE_N):
            if q in probe_hecho["single"] and all(
                    q in probe_hecho[a] for a in ARMS):
                for a in ARMS:
                    probe_rs[a].append(fase.probes[(b, a, q)]["reward"])
                continue
            p = stream[base + q]
            for a in ARMS:
                if (b, a, q) in fase.probes:
                    r = fase.probes[(b, a, q)]["reward"]
                else:
                    r = fase.probe_pull(b, q, p, a, backend, ejecutar)
                    bandit.update(a, r)
                probe_rs[a].append(r)
        elegido = probe_choice(probe_rs)
        for q in range(PROBE_N):
            pos = base + q
            if ("alma-full", pos) in fase.hechos:
                continue
            pr = fase.probes[(b, elegido, q)]
            fase.policy_pull("alma-full", pos, stream[pos], elegido,
                             backend, ejecutar, via_probe=True,
                             probe_reward=pr["reward"], probe_rec=pr)
        for q in range(PROBE_N, POR_BLOQUE):
            pos = base + q
            if ("alma-full", pos) in fase.hechos:
                continue
            rng = random.Random(f"exp67-{seed}-{pos}")
            arm = bandit.select(rng)
            r = fase.policy_pull("alma-full", pos, stream[pos], arm,
                                 backend, ejecutar)
            bandit.update(arm, r)
        elecciones[b] = {
            "slice": slice_b, "saltado": False, "skill_arm": skill_arm,
            "elegido": elegido,
            "medias": {a: round(mean(v), 4) for a, v in probe_rs.items()}}
        print(f"  bloque {b} ({slice_b}): probe eligio {elegido} "
              f"{elecciones[b]['medias']}", flush=True)
    return elecciones


# ---------------------------------------------------------------- regret

def calcular_regret(fase, stream, mejor_por_pid):
    reg = {}
    por_bloque = {}
    for policy in POLITICAS:
        tot, pb = 0.0, []
        for b in range(N_BLOQUES):
            rb = 0.0
            for q in range(POR_BLOQUE):
                pos = b * POR_BLOQUE + q
                rec = fase.hechos[(policy, pos)]
                rb += mejor_por_pid[rec["pid"]] - rec["reward"]
            pb.append(round(rb, 4))
            tot += rb
        reg[policy] = round(tot, 4)
        por_bloque[policy] = pb
    return reg, por_bloque


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--tope", type=float, default=TOPE_USD,
                    help="freno duro en USD (default 0.45)")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    t0 = time.time()

    print("== EXP67 politicas: carga del stream ==")
    problemas = cargar_problemas(dry=args.dry_run, seccion="stream")
    assert len(problemas) == 180, f"el stream debe tener 180, hay {len(problemas)}"
    slices = [problemas[b * POR_BLOQUE]["slice"] for b in range(N_BLOQUES)]
    for b in range(N_BLOQUES):
        bl = problemas[b * POR_BLOQUE:(b + 1) * POR_BLOQUE]
        assert len(bl) == POR_BLOQUE
        assert all(p["slice"] == slices[b] for p in bl), \
            f"bloque {b} mezcla slices"
    assert slices == ORDEN_SLICES_PRE, \
        f"orden de slices difiere del pre-registro: {slices}"
    print(f"   180 problemas, 9 bloques x 20, orden {slices}")

    if args.dry_run:
        return dry_run(args, problemas, slices, t0)

    oracle_path = os.path.join(args.out, "oracle_pulls.jsonl")
    assert os.path.exists(oracle_path), \
        f"falta {oracle_path}: el oraculo debe correr antes"
    pulls_oraculo = cargar_oraculo(oracle_path)
    assert len(pulls_oraculo) == 1080, \
        f"oraculo incompleto: {len(pulls_oraculo)}/1080 pulls"
    print(f"   oraculo: {len(pulls_oraculo)} pulls OK")

    backend = DeepSeekBackend()
    modelos = backend.ping()
    assert "deepseek-flash" in modelos, "deepseek-flash no visible en /models"
    print("   ping /models OK (gratis)")

    fase = FasePoliticas(args.out, tope_usd=args.tope)
    mejor_por_pid = mejor_oraculo_por_pid(pulls_oraculo)
    assert all(p["id"] in mejor_por_pid for p in problemas), \
        "el oraculo no cubre todo el stream"
    mejor_brazo_bloque = mejor_brazo_oraculo_por_bloque(
        pulls_oraculo, problemas)

    elecciones = {}
    try:
        for policy in POLITICAS:
            print(f"== politica {policy} ==", flush=True)
            tp = time.time()
            if policy.startswith("fija-"):
                correr_fija(fase, policy, problemas, backend, ejecutar)
            elif policy == "thompson-global":
                correr_thompson_global(fase, problemas, args.seed,
                                       backend, ejecutar)
            else:
                elecciones = correr_alma_full(
                    fase, problemas, slices, args.seed, pulls_oraculo,
                    mejor_brazo_bloque, backend, ejecutar)
            n = sum(1 for (pol, _p) in fase.hechos if pol == policy)
            assert n == 180, f"{policy}: {n}/180 pulls"
            print(f"   {policy}: 180/180 ({time.time()-tp:.0f}s) "
                  f"gastado ${fase.gastado:.4f}", flush=True)
    except RuntimeError as e:
        print(f"\nABORTO POR FRENO: {e}")
        print(f"   parcial: {len(fase.hechos)} pulls de politica + "
              f"{len(fase.probes)} de probe, gastado ${fase.gastado:.4f} "
              f"— sin regret (resume retoma)")
        return 2

    reg, por_bloque = calcular_regret(fase, problemas, mejor_por_pid)
    reporte = {
        "fase": FASE_POL,
        "meta": {
            "experimento": "ALMA-EXP67 fase de politicas",
            "politicas": POLITICAS,
            "stream": "9 bloques x 20 (orden pre-registrado)",
            "seed": args.seed,
            "evaluador": ("reward = 0.75*exito + 0.25*(1 - costo_rel/5), "
                          "costo_rel {single:1.0, cot:1.2, reflexion:4.0}"),
            "rng": "pareado por posicion: random.Random(f'exp67-{seed}-{pos}')",
            "pulls_politica": len(fase.hechos),
            "pulls_probe": len(fase.probes),
            "llamadas_api": backend.llamadas,
            "costo_total_usd": round(fase.gastado, 4),
            "freno_usd": args.tope,
            "duracion_s": round(time.time() - t0, 1),
        },
        "regret_total_por_politica": reg,
        "regret_por_bloque": por_bloque,
        "elecciones_probe": elecciones,
        "nota_veredicto": ("SIN veredicto PASS/FAIL: lo dictamina el padre "
                            "contra la vara pre-registrada "
                            "(regret(alma-full) < mejor fija y "
                            "< thompson-global)."),
    }
    with open(os.path.join(args.out, "politicas_regret.json"), "w") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    print("\n================ RESUMEN POLITICAS (sin veredicto) ================")
    for p in POLITICAS:
        print(f"  {p}: regret={reg[p]:.3f}")
    print(f"  costo total: ${fase.gastado:.4f} | llamadas API: "
          f"{backend.llamadas} | {reporte['meta']['duracion_s']}s")
    print("  (el veredicto PASS/FAIL lo dictamina el padre contra la vara)")
    print("==================================================================")
    return 0


def dry_run(args, problemas, slices, t0):
    """Sin API: valida manifiesto, scorers, init de las 5 politicas,
    gate de skip (unit) y los 9 bloques simulados con stub."""
    ok = chequeo_scorers()
    print("   scorers:", "VERDE" if ok else "ROJO")
    if not ok:
        return 1

    # --- unit: gate de skip (port de EXP49/52) ---
    obs_win = {0: {"single": [0.9, 0.9, 0.9], "cot": [0.5, 0.5, 0.5],
                   "reflexion": [0.4, 0.4, 0.4]}}
    obs_nowin = {0: {"single": [0.5, 0.5, 0.5], "cot": [0.9, 0.9, 0.9],
                     "reflexion": [0.4, 0.4, 0.4]}}
    sl = ["gsm8k", "x", "y", "gsm8k"]
    s, w, k, u = decidir_skip(3, "gsm8k", sl, "single", obs_win)
    assert (s, w, k, u) == (True, 1, 1, 1), (s, w, k, u)
    s2, w2, k2, u2 = decidir_skip(3, "gsm8k", sl, "single", obs_nowin)
    assert (s2, w2, k2, u2) == (False, 0, 1, 1), (s2, w2, k2, u2)
    assert umbral_endurecido(0) == 1 and umbral_endurecido(3) == 2 \
        and umbral_endurecido(6) == 3
    # probe incompleto no cuenta (soporte-puro)
    obs_parcial = {0: {"single": [0.9], "cot": [0.5], "reflexion": [0.4]}}
    s3, _w3, k3, _u3 = decidir_skip(3, "gsm8k", sl, "single", obs_parcial)
    assert (s3, k3) == (False, 0), (s3, k3)
    print("   gate de skip: VERDE (win/no-win/parcial/umbrales)")

    # --- unit: probe_choice (EXP62 verbatim) ---
    assert probe_choice({"single": [0.9] * 3, "cot": [0.94] * 3,
                         "reflexion": [0.5] * 3}) == "single"  # diff 0.04
    assert probe_choice({"single": [0.9] * 3, "cot": [0.96] * 3,
                         "reflexion": [0.5] * 3}) == "cot"     # diff 0.06
    print("   probe_choice: VERDE")

    # --- simulacion de los 9 bloques con stub (sin API ni key) ---
    with tempfile.TemporaryDirectory() as tmp:
        fase = FasePoliticas(tmp, tope_usd=args.tope, dry=True)
        pulls_oraculo = cargar_oraculo(
            os.path.join(args.out, "oracle_pulls.jsonl")) \
            if os.path.exists(os.path.join(args.out, "oracle_pulls.jsonl")) \
            else []
        if not pulls_oraculo:
            print("   (sin oracle_pulls.jsonl: warm-start con prior 0.5)")
        mejor_brazo_bloque = {b: "single" for b in range(N_BLOQUES)}
        for policy in POLITICAS:
            if policy.startswith("fija-"):
                correr_fija(fase, policy, problemas, None, None)
            elif policy == "thompson-global":
                correr_thompson_global(fase, problemas, args.seed, None, None)
            else:
                elecciones = correr_alma_full(
                    fase, problemas, slices, args.seed, pulls_oraculo,
                    mejor_brazo_bloque, None, None)
        # el probe usa los PRIMEROS 3 problemas del bloque (EXP62)
        for b in range(N_BLOQUES):
            base = b * POR_BLOQUE
            for q in range(PROBE_N):
                for a in ARMS:
                    r = fase.probes.get((b, a, q))
                    if r is not None:
                        assert r["pid"] == problemas[base + q]["id"], \
                            f"probe b{b}q{q} no usa el problema {base+q}"
        n_saltados = sum(1 for e in elecciones.values() if e["saltado"])
        print(f"   simulacion 9 bloques: VERDE "
              f"({len(fase.hechos)} pulls politica, {len(fase.probes)} probe, "
              f"{n_saltados} bloques saltados)")
        # idempotencia: re-correr no cambia nada
        h0, p0 = len(fase.hechos), len(fase.probes)
        fase2 = FasePoliticas(tmp, tope_usd=args.tope, dry=True)
        assert len(fase2.hechos) == h0 and len(fase2.probes) == p0
        assert abs(fase2.gastado - 0.0) < 1e-9
        print("   idempotencia (resume): VERDE")
        # regret computable
        if pulls_oraculo:
            mejor = mejor_oraculo_por_pid(pulls_oraculo)
            reg, _pb = calcular_regret(fase, problemas, mejor)
            assert set(reg) == set(POLITICAS)
            print(f"   regret (stub): { {p: round(v,2) for p,v in reg.items()} }")

    print(f"\n   dry-run VERDE en {time.time()-t0:.1f}s "
          f"(sin API, sin key)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
