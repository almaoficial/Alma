#!/usr/bin/env python3
"""ALMA-EXP53: banco de skills versionado con scoring (idea oriental SkillRL)
vs diario plano (mock, US$0).

Serie nueva: "ideas orientales". NO es reapertura de la línea EXP45-52
(cerrada en EXP52 por techo estructural del mecanismo skip/probe). La
hipótesis es distinta: la REPRESENTACIÓN de la memoria.

Diseño:
- Control: el tratamiento de EXP51 VERBATIM
  (run_experiment51.correr_replica_probe_barato, importada sin copiar):
  skip con umbral endurecido 2+floor(K/3) + probe adaptativo con gate Q1.
- Tratamiento ("skill-bank"): COPIA VERBATIM del control, salvo UN moving
  part: la memoria. El diario plano (prior_params / skill_arm_actual sobre
  todo el historial con olvido 0.5^d) se reemplaza por un SkillBank:
  por firma, entradas versionadas {brazo, v, score, media} con score =
  win-rate con decaimiento; retrieval = la no-deprecada de mayor score;
  victoria -> se versiona reforzada; derrota -> se penaliza y si otro
  brazo ganó nace una versión con ese brazo (evolución); score < 0.25 ->
  deprecada. El prior de Thompson se concentra en el campeón (los demás
  brazos van a uniforme: el banco olvida estructuralmente). Soporte del
  skip y gate Q1: reglas IDÉNTICAS al control, aplicadas al campeón del
  banco. Sin skill: fallback idéntico al control (prior ciego).

Mismo stream de 24 bloques bit-idéntico (construir_stream de EXP47),
5 réplicas pareadas con RNG común, mismos namespaces de RNG del oráculo.

Criterio PRE-REGISTRADO (ver exp53_skillrl/preregistro.md):
  PASS ssi media sobre réplicas de regret(skill-bank)-regret(control) < 0.

Uso:
    python3 run_experiment53.py [--out DIR] [--replicas N]
"""

import argparse
import json
import os
import random
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
sys.path.insert(0, RAIZ)
import run_experiment47 as e47  # noqa: E402  (maquinaria base)
import run_experiment49 as e49  # noqa: E402  (soporte_endurecido)
import run_experiment51 as e51  # noqa: E402  (control verbatim)

EXP51_REPORT = os.path.join(RAIZ, "resultados", "exp51-20260927",
                            "report.json")

DECAY = 0.5   # mismo olvido que la línea
PISO_SCORE = 0.25
MASA_MIN_DEPREC = 1.5
N0 = 2  # misma fuerza de prior que el control


class SkillBank:
    """Banco de skills versionado con scoring (idea oriental SkillRL).

    Por firma de régimen: entradas por brazo {v, num, den, rnum, rden,
    deprecada}. score = num/den (win-rate con decaimiento exponencial),
    media = rnum/rden (accuracy con decaimiento, para el prior).
    Retrieval: la entrada no-deprecada de mayor score (desempate: orden
    de brazos, determinista como el control). Evolución por scoring:
    la victoria refuerza (nueva versión), la derrota penaliza, y si otro
    brazo ganó estrictamente su entrada suma la victoria (el campeón
    migra por score). score < piso con masa suficiente -> deprecada.
    """

    def __init__(self, brazos, decay=DECAY, piso=PISO_SCORE,
                 masa_min=MASA_MIN_DEPREC, n0=N0):
        self.brazos = list(brazos)
        self.decay = decay
        self.piso = piso
        self.masa_min = masa_min
        self.n0 = n0
        self.banco = {}  # sig -> {brazo: entrada}
        self.stats = {"nacimientos": 0, "refuerzos": 0,
                      "penalizaciones": 0, "evoluciones": 0,
                      "deprecaciones": 0}

    def _nueva_entrada(self, brazo, acc, b):
        return {"brazo": brazo, "v": 1, "num": 1.0, "den": 1.0,
                "rnum": float(acc), "rden": 1.0,
                "deprecada": False, "nacida_en": b}

    def recuperar(self, sig):
        """(brazo, entrada) de mayor score no-deprecada, o None."""
        ent = self.banco.get(sig)
        if not ent:
            return None
        cands = [(a, e) for a, e in ent.items() if not e["deprecada"]]
        if not cands:
            return None

        def clave(item):
            a, e = item
            return (e["num"] / e["den"], -self.brazos.index(a))

        return max(cands, key=clave)

    def existe(self, sig):
        return self.recuperar(sig) is not None

    def prior_params(self, brazos, sk):
        """Prior concentrado en el campeón; el resto a uniforme (el banco
        olvida estructuralmente los brazos no-campeones)."""
        a_c, e = sk
        m = e["rnum"] / e["rden"] if e["rden"] > 0 else 0.5
        n0 = self.n0
        params = {}
        for a in brazos:
            if a == a_c:
                params[a] = (1.0 + n0 * m, 1.0 + n0 * (1.0 - m))
            else:
                params[a] = (1.0 + n0 * 0.5, 1.0 + n0 * 0.5)
        return params

    def nacer(self, sig, brazo, win, acc, b):
        ent = self.banco.setdefault(sig, {})
        e = self._nueva_entrada(brazo, acc, b)
        e["num"] = float(win)
        e["den"] = 1.0
        ent[brazo] = e
        self.stats["nacimientos"] += 1
        return e

    def evaluar_bloque(self, sig, campeon, win_c, acc_c, ganador, acc_g,
                       b):
        """Cierra el bloque: decae todas las entradas de la firma, refuerza
        o penaliza al campeón, suma la victoria al ganador estricto si es
        otro brazo (evolución por scoring), y depreca bajo el piso."""
        D = self.decay
        ent = self.banco.setdefault(sig, {})
        diag = {"evolucion": False, "deprecado_campeon": False}
        for e in ent.values():
            e["num"] *= D
            e["den"] *= D
            e["rnum"] *= D
            e["rden"] *= D
        ec = ent.get(campeon)
        if ec is None:  # robustez: no debería pasar
            ec = self._nueva_entrada(campeon, acc_c, b)
            ec["num"] = float(win_c)
            ent[campeon] = ec
        else:
            ec["num"] += float(win_c)
            ec["den"] += 1.0
            ec["rnum"] += float(acc_c)
            ec["rden"] += 1.0
            if win_c:
                ec["v"] += 1  # se versiona reforzada
                self.stats["refuerzos"] += 1
            else:
                self.stats["penalizaciones"] += 1  # se penaliza
        if ganador is not None and ganador != campeon:
            eg = ent.get(ganador)
            if eg is None:
                eg = self._nueva_entrada(ganador, acc_g, b)
                ent[ganador] = eg
            else:
                eg["num"] += 1.0
                eg["den"] += 1.0
                eg["rnum"] += float(acc_g)
                eg["rden"] += 1.0
                eg["v"] += 1
            self.stats["evoluciones"] += 1
            diag["evolucion"] = True
        for a, e in ent.items():
            if (not e["deprecada"] and e["den"] >= self.masa_min
                    and (e["num"] / e["den"]) < self.piso):
                e["deprecada"] = True
                self.stats["deprecaciones"] += 1
                if a == campeon:
                    diag["deprecado_campeon"] = True
        return diag


def victoria_pareada(brazos, obs, arm):
    """Victoria pareada estricta: media de `arm` estrictamente mayor que la
    de cada otro brazo sobre los items observados. Misma regla que el
    soporte de la línea."""
    m_s = sum(obs[arm]) / len(obs[arm])
    return all(m_s > sum(obs[a]) / len(obs[a])
               for a in brazos if a != arm)


def ganador_estricto(brazos, obs):
    """Brazo estrictamente mejor (desempate primer máximo como el control),
    o None si nadie gana estrictamente."""
    medias = {a: sum(obs[a]) / len(obs[a]) for a in brazos}
    best = max(brazos, key=lambda a: medias[a])
    if all(medias[best] > medias[a] for a in brazos if a != best):
        return best
    return None


def correr_replica_skill_bank(rep_id, items, tasas):
    """Tratamiento skill-bank de EXP53.

    COPIA VERBATIM de e51.correr_replica_probe_barato: misma lógica,
    mismos seeds de RNG, mismo orden de sorteos, misma contabilidad
    honesta, mismo diagnóstico de misfires. El ÚNICO moving part: los
    hooks de memoria (skill_existe / skill_arm_actual / prior_params
    condicionado) leen del SkillBank en vez del diario plano.
    """
    brazos = tasas["brazos"]
    H = len(items)
    n_bloques = H // e47.BLOQUE
    rep_hist = {a: [] for a in brazos}  # (h, reward, bloque)
    block_sig = {}
    probe_obs = {}  # b -> {brazo: [rewards en items de probe]} | None
    rew_pol = [0.0] * H
    rew_fija = {a: [0.0] * H for a in brazos}
    reg_pol_bloques = []
    diag = []
    skills_usadas = 0
    probes_saltados = 0
    saltados_det = []
    q2_saltados = 0
    costo_probe_q1 = 0.0
    costo_probe_q2_items = 0.0
    bank = SkillBank(brazos)

    for b in range(n_bloques):
        base = b * e47.BLOQUE
        sig = e47.firma_grupo([items[base + q]["grupo"]
                               for q in e47.PROBE_Q1])
        block_sig[b] = sig

        saltar = False
        skill_arm = None
        wins = 0
        K = None
        umbral = None
        # --- HOOK DE MEMORIA (banco en vez de diario) ---
        sk = bank.recuperar(sig)
        existe_skill = sk is not None
        if existe_skill:
            skill_arm = sk[0]
            fuerte, wins, K, umbral = e49.soporte_endurecido(
                brazos, probe_obs, block_sig, b, sig, skill_arm)
            saltar = fuerte

        clf = e47.MockClasificador(tasas)
        for hh in range(base):
            clf.registrar(items[hh])

        if saltar:
            # PROBE SALTADO: idéntico a EXP51 (sin probe, sin gate).
            probes_saltados += 1
            probe_obs[b] = None
            for q in range(e47.BLOQUE):
                h = base + q
                it = items[h]
                rs = {a: clf.acierto(
                    a, it, random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                    for a in brazos}
                for a in brazos:
                    rew_fija[a][h] = rs[a]
                r = rs[skill_arm]
                rep_hist[skill_arm].append((h, r, b))
                rew_pol[h] = r
                clf.registrar(it)
            acc = {a: sum(rew_fija[a][base:base + e47.BLOQUE]) / e47.BLOQUE
                   for a in brazos}
            mejor = max(brazos, key=lambda a: acc[a])
            obs10 = {a: rew_fija[a][base:base + e47.BLOQUE]
                     for a in brazos}
            win_c = 1.0 if victoria_pareada(brazos, obs10,
                                            skill_arm) else 0.0
            ganador = ganador_estricto(brazos, obs10)
            bank_diag = bank.evaluar_bloque(
                sig, skill_arm, win_c, acc[skill_arm], ganador,
                acc[ganador] if ganador else 0.0, b)
            saltados_det.append({
                "bloque": b, "firma": sig, "brazo_skill": skill_arm,
                "soporte_wins": wins, "K_oportunidades": K,
                "umbral_exigido": umbral,
                "acc_skill": round(acc[skill_arm], 4),
                "mejor_expost": mejor, "acc_mejor": round(acc[mejor], 4),
                "misfire": bool(mejor != skill_arm),
                "bank_score": round(sk[1]["num"] / sk[1]["den"], 4),
                "bank_version": sk[1]["v"],
            })
            reg_pol_bloques.append(
                e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))
            diag.append({
                "bloque": b, "regimen": items[base]["regimen"], "firma": sig,
                "probe_saltado": True, "soporte_wins": wins,
                "K_oportunidades": K, "umbral_exigido": umbral,
                "brazo_skill": skill_arm,
                "bank_score": round(sk[1]["num"] / sk[1]["den"], 4),
                "bank_version": sk[1]["v"],
                "bank_evolucion": bank_diag["evolucion"],
                "bank_deprecado": bank_diag["deprecado_campeon"],
                "acc_pol": round(
                    sum(rew_pol[base:base + e47.BLOQUE]) / e47.BLOQUE, 4),
                "acc_fijas": {
                    a: round(sum(rew_fija[a][base:base + e47.BLOQUE]) /
                             e47.BLOQUE, 4)
                    for a in brazos},
            })
            continue

        # --- Camino con probe: idéntico a EXP51 hasta el prior ---
        bandit = e47.nuevo_bandit(
            brazos, e47.prior_params(brazos, rep_hist, block_sig, b, None))
        prior_means = {a: bandit.mean(a) for a in brazos}
        fav = max(brazos, key=lambda a: prior_means[a])

        def medir(q, rng_tag):
            h = base + q
            it = items[h]
            rs = {a: clf.acierto(
                a, it, random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                for a in brazos}
            for a in brazos:
                bandit.update(a, rs[a])
                rep_hist[a].append((h, rs[a], b))
                rew_fija[a][h] = rs[a]
            clf.registrar(it)
            return rs

        # PROBE Q1: bit-idéntico al control (mismos sorteos, scoring ciego).
        rs_q1 = {}
        for q in e47.PROBE_Q1:
            h = base + q
            rs_q1[q] = medir(q, "q1")
            rew_pol[h] = rs_q1[q][fav]
        costo_probe_q1 += len(e47.PROBE_Q1) - sum(
            rew_pol[base + q] for q in e47.PROBE_Q1)

        usa_skill = False
        if existe_skill:
            usa_skill = True
            skills_usadas += 1
            # HOOK DE MEMORIA: prior concentrado del banco (no del diario).
            bandit = e47.nuevo_bandit(
                brazos, bank.prior_params(brazos, sk))
            for q in e47.PROBE_Q1:
                for a in brazos:
                    bandit.update(a, rs_q1[q][a])

        # Gate adaptativo idéntico a EXP51, sobre el campeón del banco.
        gate = (skill_arm is not None and usa_skill and
                e51.q1_decisivo(brazos, rs_q1, skill_arm))

        def thompson(qs):
            for q in qs:
                h = base + q
                it = items[h]
                a_sel = bandit.select(
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-sel"))
                r_sel = clf.acierto(
                    a_sel, it,
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a_sel}"))
                bandit.update(a_sel, r_sel)
                rep_hist[a_sel].append((h, r_sel, b))
                rew_pol[h] = r_sel
                for a in brazos:
                    rew_fija[a][h] = clf.acierto(
                        a, it, random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                clf.registrar(it)

        thompson(tuple(q for q in e47.THOMPSON_Q if q < e47.PROBE_Q2[0]))
        if gate:
            # Q2 SALTADO: items 6,7 como jugadas de Thompson (sin re-probe).
            q2_saltados += 1
            thompson(e47.PROBE_Q2)
        else:
            # RE-PROBE Q2: idéntico al control, scoring honesto con fav ciego.
            rs_q2 = {}
            for q in e47.PROBE_Q2:
                h = base + q
                rs_q2[q] = medir(q, "q2")
                rew_pol[h] = rs_q2[q][fav]
        thompson(tuple(q for q in e47.THOMPSON_Q if q > e47.PROBE_Q2[-1]))
        costo_probe_q2_items += len(e47.PROBE_Q2) - sum(
            rew_pol[base + q] for q in e47.PROBE_Q2)

        if gate:
            probe_obs[b] = {a: [rs_q1[q][a] for q in e47.PROBE_Q1]
                            for a in brazos}
        else:
            probe_obs[b] = {a: [rs_q1[q][a] for q in e47.PROBE_Q1] +
                               [rs_q2[q][a] for q in e47.PROBE_Q2]
                            for a in brazos}

        # --- Evaluación del banco con la evidencia del probe ---
        obs = probe_obs[b]
        medias = {a: sum(obs[a]) / len(obs[a]) for a in brazos}
        ganador = ganador_estricto(brazos, obs)
        bank_diag = None
        if existe_skill:
            win_c = 1.0 if victoria_pareada(brazos, obs,
                                            skill_arm) else 0.0
            bank_diag = bank.evaluar_bloque(
                sig, skill_arm, win_c, medias[skill_arm], ganador,
                medias[ganador] if ganador else 0.0, b)
        else:
            # Nacimiento: primer máximo (como el argmax del control); el
            # score inicial refleja la evidencia (1 si victoria estricta).
            brazo_nac = max(brazos, key=lambda a: medias[a])
            win_nac = 1.0 if ganador == brazo_nac else 0.0
            bank.nacer(sig, brazo_nac, win_nac, medias[brazo_nac], b)

        reg_pol_bloques.append(
            e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))

        diag.append({
            "bloque": b, "regimen": items[base]["regimen"], "firma": sig,
            "probe_saltado": False, "soporte_wins": wins,
            "K_oportunidades": K, "umbral_exigido": umbral,
            "skill_usada": usa_skill,
            "q1_decisivo": bool(gate),
            "q2_saltado": bool(gate),
            "bank_campeon": skill_arm,
            "bank_score": (round(sk[1]["num"] / sk[1]["den"], 4)
                           if sk else None),
            "bank_evolucion": (bank_diag["evolucion"]
                               if bank_diag else None),
            "acc_pol": round(
                sum(rew_pol[base:base + e47.BLOQUE]) / e47.BLOQUE, 4),
            "acc_fijas": {
                a: round(sum(rew_fija[a][base:base + e47.BLOQUE]) /
                         e47.BLOQUE, 4)
                for a in brazos},
        })

    reg_pol = H - sum(rew_pol)
    reg_fijas = {a: H - sum(rew_fija[a]) for a in brazos}
    mejor = min(brazos, key=lambda a: reg_fijas[a])
    return {"politica": "skill-bank", "reg_pol": reg_pol,
            "reg_pol_bloques": reg_pol_bloques,
            "reg_fijas": reg_fijas,
            "mejor_fija": mejor, "reg_mejor_fija": reg_fijas[mejor],
            "skills_usadas": skills_usadas, "probes_saltados": probes_saltados,
            "q2_saltados": q2_saltados,
            "costo_probe_q1": costo_probe_q1,
            "costo_probe_q2_items": costo_probe_q2_items,
            "saltados_det": saltados_det, "n_bloques": n_bloques,
            "diag": diag, "n": H,
            "bank_stats": dict(bank.stats),
            "bank_tamano": {s: len(v) for s, v in bank.banco.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--replicas", type=int, default=e47.N_REPLICAS)
    args = ap.parse_args()
    t0 = time.time()

    out = args.out or AQUI
    os.makedirs(out, exist_ok=True)

    items = e47.construir_stream()  # bit-idéntico al stream de EXP47-51
    H = len(items)
    n_bloques = H // e47.BLOQUE
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))

    # --- pre-registro ANTES de correr (el .md canónico ya existe;
    #     aquí la versión JSON resumida para la máquina) ---
    prereg = {
        "experimento": "ALMA-EXP53: banco de skills versionado con scoring "
                       "(idea oriental SkillRL) vs diario plano (mock, US$0)",
        "serie": "ideas orientales (nueva; no reapertura de EXP45-52)",
        "fase": "mock",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "preregistro_canonico": "exp53_skillrl/preregistro.md",
        "hipotesis": "Un banco de skills versionado con scoring (win-rate "
                     "con decaimiento por firma, retrieval de mejor score, "
                     "evolución del campeón, deprecación) reduce el regret "
                     "frente al prior plano de EXP51: media sobre réplicas "
                     "pareadas de regret(skill-bank) - regret(control) < 0.",
        "moving_part": "SOLO la representación de la memoria: diario plano "
                       "-> SkillBank (versionado, scoring con decaimiento "
                       "D=0.5, retrieval mejor score, evolución, "
                       "deprecación score<0.25). Prior de Thompson "
                       "concentrado en el campeón (N0=2); resto uniforme. "
                       "Soporte del skip y gate Q1: reglas idénticas al "
                       "control.",
        "nota_refutacion": "Riesgo: la concentración olvida brazos "
                           "no-campeones (prior más frágil si el campeón "
                           "está stale); la evolución por victorias ruidosas "
                           "puede migrar al brazo equivocado.",
        "criterio": {"efecto": "regret(skill-bank) - regret(control-EXP51), "
                               "media sobre réplicas pareadas",
                     "pass": "media(efecto) < 0"},
        "reproducibilidad_control": "reg_control_bloques por réplica debe "
            "ser bit-idéntico al TRATAMIENTO de EXP51 (la política "
            "probe-barato, que es el control de EXP53): "
            "resultados/exp51-20260927/report.json -> reg_trat_bloques "
            "([78.0, 86.0, 93.0, 95.0, 80.0]); si no, no válido.",
        "rng": "namespaces idénticos al control ('exp45-...'); oráculo "
               "bit-idéntico; Thompson diverge legítimamente por priors "
               "distintos.",
        "modo": "mock, US$0",
    }
    with open(os.path.join(out, "preregistro.json"), "w",
              encoding="utf-8") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print(f"Pre-registro escrito ({H} items, {n_bloques} bloques, "
          f"{args.replicas} réplicas pareadas).")

    efectos, det = [], []
    for r in range(args.replicas):
        ctrl = e51.correr_replica_probe_barato(r, items, tasas)
        trt = correr_replica_skill_bank(r, items, tasas)
        ef = trt["reg_pol"] - ctrl["reg_pol"]
        efectos.append(ef)

        def misfires(d):
            sd = d["saltados_det"]
            return (sum(1 for s in sd if s["misfire"]), len(sd))

        mis_c = misfires(ctrl)
        mis_t = misfires(trt)
        det.append({
            "replica": r,
            "efecto": round(ef, 3),
            "reg_control": round(ctrl["reg_pol"], 3),
            "reg_tratamiento": round(trt["reg_pol"], 3),
            "reg_control_bloques": [round(x, 3)
                                    for x in ctrl["reg_pol_bloques"]],
            "reg_trat_bloques": [round(x, 3)
                                 for x in trt["reg_pol_bloques"]],
            "reg_mejor_fija": round(ctrl["reg_mejor_fija"], 3),
            "mejor_fija": ctrl["mejor_fija"],
            "skips_control": ctrl["probes_saltados"],
            "misfires_control": mis_c,
            "skips_tratamiento": trt["probes_saltados"],
            "misfires_tratamiento": mis_t,
            "q2_saltados_control": ctrl["q2_saltados"],
            "q2_saltados_trat": trt["q2_saltados"],
            "bank_stats": trt["bank_stats"],
            "bank_tamano": trt["bank_tamano"],
        })
        if r == 0:
            diag_rep0 = {"control": ctrl["diag"],
                         "tratamiento": trt["diag"]}
            salt_rep0 = {"control": ctrl["saltados_det"],
                         "tratamiento": trt["saltados_det"]}

    n = len(efectos)
    media_ef = sum(efectos) / n
    mejor = min(efectos)
    media_sin_mejor = ((sum(efectos) - mejor) / (n - 1)
                         if n > 1 else float("nan"))
    cargado_una_replica = bool(n > 1 and media_sin_mejor >= 0)

    reg_trat_medio = sum(d["reg_tratamiento"] for d in det) / n
    reg_ctrl_medio = sum(d["reg_control"] for d in det) / n
    reg_fija_medio = sum(d["reg_mejor_fija"] for d in det) / n
    d_trat = reg_trat_medio - reg_fija_medio
    d_ctrl = reg_ctrl_medio - reg_fija_medio

    pasa = bool(media_ef < 0)

    # --- chequeo de reproducibilidad bit-idéntica del control vs EXP51 ---
    repro_ok = None
    try:
        rep51 = json.load(open(EXP51_REPORT, encoding="utf-8"))
        # El control de EXP53 es la política probe-barato = el TRATAMIENTO
        # de EXP51 (reg_trat_bloques), no su control (skip-endurecido).
        d51 = {d["replica"]: d["reg_trat_bloques"]
               for d in rep51["detalle_replicas"]}
        repro_ok = all(
            [round(x, 3) for x in det[r]["reg_control_bloques"]] ==
            [round(x, 3) for x in d51[r]]
            for r in range(args.replicas))
    except Exception as e:  # noqa: BLE001
        repro_ok = f"no verificable: {e}"

    bank_tot = {}
    for d in det:
        for k, v in d["bank_stats"].items():
            bank_tot[k] = bank_tot.get(k, 0) + v

    motivos = [
        f"items={H}, bloques={n_bloques} (3 regímenes x 8 recurrencias), "
        f"réplicas pareadas={args.replicas} (RNG común, oráculo idéntico)",
        f"efecto medio (reg_trat - reg_ctrl) = {media_ef:+.3f} "
        f"(por réplica: {', '.join(f'{e:+.2f}' for e in efectos)})",
        f"(1) media(efecto) < 0: {'SÍ → PASS' if pasa else 'NO → FAIL'}",
        f"regret medio control: {reg_ctrl_medio:.2f} | tratamiento: "
        f"{reg_trat_medio:.2f} | mejor fija: {reg_fija_medio:.2f}",
        f"distancia a la mejor fija — control: {d_ctrl:.2f} | tratamiento: "
        f"{d_trat:.2f} (EXP51: 2.20 vs 3.80)",
        f"media del efecto sin la mejor réplica: {media_sin_mejor:+.2f} "
        f"(¿cargado por una sola réplica? "
        f"{'SÍ' if cargado_una_replica else 'NO'})",
        f"skips — control: "
        f"{sum(d['skips_control'] for d in det)} "
        f"(misfires {sum(d['misfires_control'][0] for d in det)}/"
        f"{sum(d['misfires_control'][1] for d in det)}) | tratamiento: "
        f"{sum(d['skips_tratamiento'] for d in det)} "
        f"(misfires {sum(d['misfires_tratamiento'][0] for d in det)}/"
        f"{sum(d['misfires_tratamiento'][1] for d in det)})",
        f"banco (5 réplicas): {bank_tot}",
        f"reproducibilidad del control vs EXP51 (bit-idéntico): {repro_ok}",
    ]
    report = {
        "preregistro": "preregistro.json (mismo directorio) + "
                       "preregistro.md (canónico)",
        "n_items": H, "n_bloques": n_bloques,
        "detalle_replicas": det,
        "efecto_medio": round(media_ef, 3),
        "efecto_por_replica": [round(e, 3) for e in efectos],
        "media_efecto_sin_mejor_replica": round(media_sin_mejor, 3),
        "cargado_por_una_sola_replica": cargado_una_replica,
        "reg_tratamiento_medio": round(reg_trat_medio, 3),
        "reg_control_medio": round(reg_ctrl_medio, 3),
        "reg_mejor_fija_medio": round(reg_fija_medio, 3),
        "distancia_trat_a_mejor_fija": round(d_trat, 3),
        "distancia_ctrl_a_mejor_fija": round(d_ctrl, 3),
        "bank_stats_total": bank_tot,
        "saltados_det_rep0": salt_rep0,
        "diagnostico_bloques_rep0": diag_rep0,
        "reproducibilidad_exp51": repro_ok,
        "costo_total_usd": 0.0,
        "veredicto": {"pass_efecto": pasa, "pass": pasa,
                      "criterio": prereg["criterio"], "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO EXP53 ================")
    for m in motivos:
        print("  " + m)
    print("  costo: $0.0000 USD (mock) | "
          f"{report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL",
          f"(efecto medio {media_ef:+.3f})")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
