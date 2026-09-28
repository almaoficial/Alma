"""Resolver — probe → selección → ejecución + aprendizaje, fase 0.

La política por defecto del servicio es el SCAFFOLD EVOLUCIONADO validado
por EXP56/57 (RSO estilo MiniMax + ablación en dos seeds):

- Prior de Thompson condicionado a la firma del régimen (EXP45),
  con n0=4 (EXP45-51: 2; load-bearing según EXP57).
- Skip del probe con soporte fuerte y umbral endurecido
  umbral(K) = 1 + floor(K/3) (EXP49: base 2; base 1 validada por
  EXP56/57, además protectora).
- Gate adaptativo: si Q1 decide a favor del brazo de la skill, se salta
  el re-probe Q2 (EXP51).

Los defaults viven en alma_service/scaffold.py (DEFAULT_SCAFFOLD); el
Resolver acepta un scaffold alternativo para experimentación sin tocar
la política.

Reutilización, no reescritura: las funciones de decisión parametrizadas
vienen de exp56_rso/run_experiment56.py (puertos verbatim de
run_experiment47/run_experiment49 con los hiperparámetros como
argumentos).

La costura honesta para fase 1 es ProveedorSkills: el mock la implementa
sobre el historial; un proveedor real lee SkillIndex + MemoriaExperiencias
sin cambiar la política.

Disciplina de RNG (mock): idéntica a EXP45–51 — el oráculo se sortea por
celda 'exp45-r{rep}-b{b}-q{q}-{a}' y Thompson por (b,q), así el orden de
llamadas no afecta los números y la bit-identidad es verificable.
"""

import random

import run_experiment47 as e47
from alma_service.scaffold import (DEFAULT_SCAFFOLD, nuevo_bandit_param,
                                   prior_params_param, soporte_param)


class ProveedorSkills:
    """Interfaz: de dónde sale la skill para una firma.

    Fase 0: ProveedorSkillsMock (historial del mock). Fase 1: proveedor
    real sobre SkillIndex + MemoriaExperiencias. La política no cambia.
    """

    def existe(self, b, sig):
        raise NotImplementedError

    def brazo(self, b, sig):
        raise NotImplementedError

    def soporte(self, b, sig, skill_arm):
        """Retorna (fuerte, wins, K, umbral)."""
        raise NotImplementedError


class ProveedorSkillsMock(ProveedorSkills):
    """La skill vive en el historial observado.

    El soporte usa la fórmula parametrizada del scaffold
    (defaults validados EXP56/57), no la constante de EXP49.
    """

    def __init__(self, resolver):
        self.r = resolver

    def existe(self, b, sig):
        return e47.skill_existe(self.r.rep_hist, self.r.block_sig, b, sig)

    def brazo(self, b, sig):
        return e47.skill_arm_actual(self.r.brazos, self.r.rep_hist,
                                    self.r.block_sig, b, sig)

    def soporte(self, b, sig, skill_arm):
        sc = self.r.scaffold
        return soporte_param(self.r.brazos, self.r.probe_obs,
                             self.r.block_sig, b, sig, skill_arm,
                             sc["umbral_base"], sc["umbral_divisor"])


class Resolver:
    """Estado + decisiones de la política. El oráculo (medición de brazos)
    lo inyecta el driver: el Resolver decide, no mide."""

    def __init__(self, brazos, proveedor=None, scaffold=None):
        self.brazos = list(brazos)
        self.scaffold = (dict(scaffold) if scaffold is not None
                         else dict(DEFAULT_SCAFFOLD))
        self.rep_hist = {a: [] for a in self.brazos}  # (h, reward, bloque)
        self.block_sig = {}
        self.probe_obs = {}  # b -> {brazo: [rewards]} | None (saltado)
        self.proveedor = proveedor or ProveedorSkillsMock(self)
        # telemetría (misma que EXP51)
        self.skills_usadas = 0
        self.probes_saltados = 0
        self.q2_saltados = 0
        self.costo_probe_q1 = 0.0
        self.costo_probe_q2_items = 0.0
        self.saltados_det = []
        self.diag = []

    # -- decisiones (puras, testeables) ----------------------------------
    def decidir_salto(self, b, sig):
        """¿Se salta el probe? Umbral endurecido 2+floor(K/3) (EXP49)."""
        if self.proveedor.existe(b, sig):
            skill_arm = self.proveedor.brazo(b, sig)
            fuerte, wins, K, umbral = self.proveedor.soporte(b, sig,
                                                            skill_arm)
            return {"saltar": bool(fuerte), "skill_arm": skill_arm,
                    "wins": wins, "K": K, "umbral": umbral}
        return {"saltar": False, "skill_arm": None, "wins": 0,
                "K": None, "umbral": None}

    def bandit_ciego(self, b):
        """Bandit con prior ciego (toda la historia) + favorito ciego."""
        sc = self.scaffold
        bandit = nuevo_bandit_param(
            self.brazos,
            prior_params_param(self.brazos, self.rep_hist, self.block_sig,
                               b, None, sc["n0"], sc["decay"]),
            sc["n0"])
        means = {a: bandit.mean(a) for a in self.brazos}
        fav = max(self.brazos, key=lambda a: means[a])
        return bandit, fav

    def bandit_con_skill(self, b, sig, rs_q1):
        """Reconstruye el prior condicionado a la firma y re-aplica Q1
        (EXP45). Sin re-sortear: usa la evidencia ya recolectada.
        Agnóstico al layout: itera los items Q1 realmente medidos."""
        self.skills_usadas += 1
        sc = self.scaffold
        bandit = nuevo_bandit_param(
            self.brazos,
            prior_params_param(self.brazos, self.rep_hist, self.block_sig,
                               b, sig, sc["n0"], sc["decay"]),
            sc["n0"])
        for q in sorted(rs_q1):
            for a in self.brazos:
                bandit.update(a, rs_q1[q][a])
        return bandit

    def gate_q1(self, rs_q1, skill_arm):
        """Gate adaptativo (EXP51): Q1 decide a favor del brazo de la
        skill de forma estricta sobre cada otro brazo. Agnóstico al
        layout: promedia sobre los items Q1 realmente medidos
        (idéntico a q1_decisivo cuando las claves son PROBE_Q1)."""
        if skill_arm is None:
            return False
        qs = sorted(rs_q1)
        m_s = sum(rs_q1[q][skill_arm] for q in qs) / len(qs)
        return bool(all(m_s > sum(rs_q1[q][a] for q in qs) / len(qs)
                        for a in self.brazos if a != skill_arm))

    # -- aprendizaje ------------------------------------------------------
    def observar(self, brazo, h, r, b):
        self.rep_hist[brazo].append((h, r, b))

    def cerrar_bloque_saltado(self, b, sig, skill_arm, wins, K, umbral,
                              acc_skill, mejor, acc_mejor):
        self.probes_saltados += 1
        self.probe_obs[b] = None
        # acc_mejor=None: el contrafáctico no se midió (el camino de
        # skip real no lo mide: medirlo anularía el ahorro). El misfire
        # queda desconocido (None), no 0.
        self.saltados_det.append({
            "bloque": b, "firma": sig, "brazo_skill": skill_arm,
            "soporte_wins": wins, "K_oportunidades": K,
            "umbral_exigido": umbral,
            "acc_skill": round(acc_skill, 4),
            "mejor_expost": mejor,
            "acc_mejor": (round(acc_mejor, 4)
                          if acc_mejor is not None else None),
            "misfire": (None if acc_mejor is None
                        else bool(mejor != skill_arm)),
        })

    def cerrar_bloque_probe(self, b, obs):
        self.probe_obs[b] = obs


def correr_replica_servicio(rep_id, items, tasas, scaffold=None):
    """Driver mock de la política del servicio sobre el stream de EXP47–51.

    Puerto fiel del tratamiento "probe-barato" de EXP51
    (run_experiment51.correr_replica_probe_barato) con el scaffold
    evolucionado de EXP56/57 (n0=4, umbral_base=1): misma lógica, mismos
    seeds de RNG, misma contabilidad honesta. La diferencia es
    arquitectónica: las decisiones viven en Resolver con la costura
    ProveedorSkills y los hiperparámetros en alma_service/scaffold.py.
    El test de bit-identidad (test_fase0_resolver.py) lo verifica contra
    la implementación independiente exp56_rso/run_experiment56.py con el
    scaffold validado.
    """
    brazos = tasas["brazos"]
    H = len(items)
    n_bloques = H // e47.BLOQUE
    res = Resolver(brazos, scaffold=scaffold)
    rew_pol = [0.0] * H
    rew_fija = {a: [0.0] * H for a in brazos}
    reg_pol_bloques = []

    for b in range(n_bloques):
        base = b * e47.BLOQUE
        sig = e47.firma_grupo([items[base + q]["grupo"]
                               for q in e47.PROBE_Q1])
        res.block_sig[b] = sig
        dec = res.decidir_salto(b, sig)
        saltar, skill_arm = dec["saltar"], dec["skill_arm"]
        wins, K, umbral = dec["wins"], dec["K"], dec["umbral"]

        clf = e47.MockClasificador(tasas)
        for hh in range(base):
            clf.registrar(items[hh])

        def medir_todos(q):
            h = base + q
            it = items[h]
            rs = {a: clf.acierto(
                a, it, random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                for a in brazos}
            for a in brazos:
                rew_fija[a][h] = rs[a]
            clf.registrar(it)
            return rs

        if saltar:
            # PROBE SALTADO: se juega el brazo de la skill en los 10 items.
            for q in range(e47.BLOQUE):
                h = base + q
                rs = medir_todos(q)
                r = rs[skill_arm]
                res.observar(skill_arm, h, r, b)
                rew_pol[h] = r
            acc = {a: sum(rew_fija[a][base:base + e47.BLOQUE]) / e47.BLOQUE
                   for a in brazos}
            mejor = max(brazos, key=lambda a: acc[a])
            res.cerrar_bloque_saltado(b, sig, skill_arm, wins, K, umbral,
                                     acc[skill_arm], mejor, acc[mejor])
            reg_pol_bloques.append(
                e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))
            res.diag.append({
                "bloque": b, "regimen": items[base]["regimen"], "firma": sig,
                "probe_saltado": True, "soporte_wins": wins,
                "K_oportunidades": K, "umbral_exigido": umbral,
                "brazo_skill": skill_arm,
                "acc_pol": round(
                    sum(rew_pol[base:base + e47.BLOQUE]) / e47.BLOQUE, 4),
                "acc_fijas": {
                    a: round(sum(rew_fija[a][base:base + e47.BLOQUE]) /
                             e47.BLOQUE, 4)
                    for a in brazos},
            })
            continue

        # --- Camino con probe ---
        bandit, fav = res.bandit_ciego(b)

        # PROBE Q1: mide todos los brazos; scoring con fav ciego.
        rs_q1 = {}
        for q in e47.PROBE_Q1:
            h = base + q
            rs = medir_todos(q)
            rs_q1[q] = rs
            for a in brazos:
                bandit.update(a, rs[a])
                res.observar(a, h, rs[a], b)
            rew_pol[h] = rs[fav]
        res.costo_probe_q1 += len(e47.PROBE_Q1) - sum(
            rew_pol[base + q] for q in e47.PROBE_Q1)

        usa_skill = skill_arm is not None
        if usa_skill:
            bandit = res.bandit_con_skill(b, sig, rs_q1)

        # ÚNICO moving part de EXP51: gate adaptativo sobre Q1.
        gate = (skill_arm is not None and usa_skill
                and res.gate_q1(rs_q1, skill_arm))

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
                res.observar(a_sel, h, r_sel, b)
                rew_pol[h] = r_sel
                for a in brazos:
                    rew_fija[a][h] = clf.acierto(
                        a, it,
                        random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                clf.registrar(it)  # el oráculo de 'mayoría' ve la historia

        thompson(tuple(q for q in e47.THOMPSON_Q if q < e47.PROBE_Q2[0]))
        if gate:
            # Q2 SALTADO: items 6,7 como jugadas de Thompson.
            res.q2_saltados += 1
            thompson(e47.PROBE_Q2)
            rs_q2 = None
        else:
            # RE-PROBE Q2: scoring con fav ciego.
            rs_q2 = {}
            for q in e47.PROBE_Q2:
                h = base + q
                rs = medir_todos(q)
                rs_q2[q] = rs
                for a in brazos:
                    bandit.update(a, rs[a])
                    res.observar(a, h, rs[a], b)
                rew_pol[h] = rs[fav]
        thompson(tuple(q for q in e47.THOMPSON_Q if q > e47.PROBE_Q2[-1]))
        res.costo_probe_q2_items += len(e47.PROBE_Q2) - sum(
            rew_pol[base + q] for q in e47.PROBE_Q2)

        if gate:
            res.cerrar_bloque_probe(
                b, {a: [rs_q1[q][a] for q in e47.PROBE_Q1]
                    for a in brazos})
        else:
            res.cerrar_bloque_probe(
                b, {a: [rs_q1[q][a] for q in e47.PROBE_Q1] +
                       [rs_q2[q][a] for q in e47.PROBE_Q2]
                    for a in brazos})
        reg_pol_bloques.append(
            e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))
        res.diag.append({
            "bloque": b, "regimen": items[base]["regimen"], "firma": sig,
            "probe_saltado": False, "soporte_wins": wins,
            "K_oportunidades": K, "umbral_exigido": umbral,
            "skill_usada": usa_skill,
            "q1_decisivo": bool(gate),
            "q2_saltado": bool(gate),
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
    return {"politica": "servicio-exp56", "reg_pol": reg_pol,
            "reg_pol_bloques": reg_pol_bloques,
            "reg_fijas": reg_fijas,
            "mejor_fija": mejor, "reg_mejor_fija": reg_fijas[mejor],
            "skills_usadas": res.skills_usadas,
            "probes_saltados": res.probes_saltados,
            "q2_saltados": res.q2_saltados,
            "costo_probe_q1": res.costo_probe_q1,
            "costo_probe_q2_items": res.costo_probe_q2_items,
            "saltados_det": res.saltados_det, "n_bloques": n_bloques,
            "diag": res.diag, "n": H}
