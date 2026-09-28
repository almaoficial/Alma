"""Motor fase 1 — cableado de servicio/motor.py al Resolver de alma_service.

El motor persistente corre el loop resolver → feedback con memoria
SQLite real (MemoriaExperiencias: olvido 0.5^d + evicción lógica) y
skills reales (SkillIndex + SKILL.md generados por el modelo).

Arquitectura (sin duplicar lo que ya existe):
- Decisiones: alma_service.resolver.Resolver con la costura
  ProveedorSkills. En fase 1 el proveedor es ProveedorSkillsReal
  (lee SkillIndex + MemoriaExperiencias); el mock quedó en fase 0.
- Ejecución: alma.executors sobre problemas reales (LLM vía VaultBackend,
  medido por ClienteMedido con presupuesto duro).
- Recompensa: exact-match contra ground truth (Evaluator + StubJudge),
  reward binario 1.0/0.0 como el acierto del mock.
- Skills: GeneradorSkills (crea/refina SKILL.md desde experiencias) y
  BackendConSkill (la skill guía la ejecución del brazo recomendado).
  Los probes (Q1/Q2) miden brazos raw: la medición queda limpia.
- Compuerta: DetectorRecurrencia — en modo adaptativo no se generan ni
  usan skills (diseño §2.1); el loop sigue con Thompson + re-probe.

Diferencia honesta vs el mock: en el camino de skip NO se mide el
contrafáctico (medir todos los brazos anularía el ahorro del skip y
costaría). El misfire de un bloque saltado queda como desconocido,
no como 0.

No modifica servicio/motor.py (v2: baterías, TRIZ, horizontes — otra
familia de política). Este es el cableado de la política validada
EXP45/49/51 al mundo real.
"""

import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alma import executors
from alma.evaluator import Evaluator, StubJudge

from alma_service.resolver import Resolver
from alma_service.proveedor_real import (
    ProveedorSkillsReal, ProveedorSkillsNulo, GeneradorSkills,
    BackendConSkill,
)
from alma_service.memoria import MemoriaExperiencias
from alma_service.skills import SkillIndex
from alma_service.curator import Curator
from alma_service.recurrencia import DetectorRecurrencia, MODO_SKILLS
from alma_service.llm import Presupuesto, ClienteMedido, PresupuestoAgotado
# Fase 2.4 (EXP68 PASS, 2026-09-27): detector de heterogeneidad como
# meta-regla aditiva del servicio. K/J congelados por el pre-registro
# (K_EXP68/J_EXP68): no se tunean.
from alma_service.heterogeneidad import (
    DetectorHeterogeneidad, ganador_estricto, EXPLORAR, ENCOGIDO,
    K_EXP68, J_EXP68,
)

# Estructura de bloque real (6 problemas). Análoga al mock (10 ítems:
# Q1=0,1,2; Q2=6,7; resto Thompson): lo que importa es la política
# (skip endurecido, gate adaptativo), no las posiciones exactas.
BLOQUE = 6
Q1 = (0, 1)
THOMPSON_PRE = (2,)
Q2 = (3,)
THOMPSON_POST = (4, 5)
# Ítems del spot-check del detector de heterogeneidad (fase 2.4):
# los 3 ítems de probe del bloque (Q1+Q2), como en la validación EXP68.
SPOT_ITEMS = Q1 + Q2

BRAZOS_DEFAULT = ("single", "cot", "reflexion")


class MotorFase1:
    """Loop persistente resolver → feedback con componentes reales."""

    def __init__(self, dir_trabajo, brazos=BRAZOS_DEFAULT,
                 budget_usd=0.40, usar_skills=True, seed=0,
                 backend=None, modelo="gpt-4o-mini",
                 ventana_recurrencia=20, umbral_recurrencia=0.30,
                 detector_heterogeneidad=True, trazas=None):
        self.dir = os.path.abspath(dir_trabajo)
        os.makedirs(self.dir, exist_ok=True)
        self.brazos = tuple(brazos)
        self.usar_skills = bool(usar_skills)
        self.seed = int(seed)

        self.memoria = MemoriaExperiencias(
            os.path.join(self.dir, "memoria.db"))
        self.skill_index = SkillIndex(
            os.path.join(self.dir, "skills-indice.db"))
        self.curator = Curator(
            self.skill_index,
            ledger_path=os.path.join(self.dir, "curator-ledger.jsonl"))
        self.detector = DetectorRecurrencia(
            ventana=ventana_recurrencia, umbral=umbral_recurrencia)

        self.presupuesto = (budget_usd if isinstance(budget_usd, Presupuesto)
                             else Presupuesto(budget_usd))
        if backend is None:
            from alma.backends import VaultBackend
            backend = VaultBackend(model=modelo)
        self.cliente = ClienteMedido(backend, self.presupuesto,
                                     modelo=modelo)
        self.cliente.etiqueta_default = "resolver"

        self.prov_real = ProveedorSkillsReal(
            self.skill_index, self.memoria, self.brazos)
        self.prov_nulo = ProveedorSkillsNulo()
        self.resolver = Resolver(
            self.brazos,
            proveedor=self.prov_real if usar_skills else self.prov_nulo)
        self.generador = GeneradorSkills(
            self.skill_index, self.memoria,
            os.path.join(self.dir, "skills"),
            curator=self.curator)
        self.evaluador = Evaluator(judge=StubJudge())

        self._h = 0  # contador global de ítems (para observar())
        self._t0 = time.time()
        self.bloques = []  # telemetría por bloque
        # -- fase 2.4: detector de heterogeneidad (EXP68 PASS) ------------
        # Meta-regla aditiva y conmutable: True → crea uno con K/J
        # congelados; instancia → se usa tal cual; False/None → off.
        # Si el detector falla, se desactiva y el servicio sigue con la
        # política vigente (fail-safe: el camino sin detector es el
        # validado). Nunca toca el scaffold ni la política del resolver.
        if detector_heterogeneidad is True:
            self.detector_het = DetectorHeterogeneidad(
                K=K_EXP68, J=J_EXP68)
        elif isinstance(detector_heterogeneidad, DetectorHeterogeneidad):
            self.detector_het = detector_heterogeneidad
        else:
            self.detector_het = None
        self._detector_roto = False
        self._det_historial_visto = 0
        # Event log 2.2 (opcional, lo cablea quien instancia): las
        # transiciones del detector se asientan como eventos de ciclo.
        self.trazas = trazas

    # -- utilidades ------------------------------------------------------
    def _rng(self, b, q):
        return random.Random(self.seed * 1000003 + b * 1009 + q)

    @staticmethod
    def _firma_bloque(problemas):
        firmas = [p["firma"] for p in problemas]
        return max(set(firmas), key=firmas.count)

    def _backend_para(self, brazo, skill_arm, skill_obj):
        if (skill_obj is not None and skill_arm is not None
                and brazo == skill_arm):
            return BackendConSkill(self.cliente, skill_obj), True
        return self.cliente, False

    def _medir(self, brazo, problema, b, q, fase, sig,
               skill_arm=None, skill_obj=None):
        """Ejecuta un brazo sobre un problema real. Retorna reward 0/1."""
        backend, guiada = self._backend_para(brazo, skill_arm, skill_obj)
        prob = {"id": problema["id"], "enunciado": problema["enunciado"],
                "verificador": "exact", "esperado": problema["esperado"]}
        res = executors.ejecutar(brazo, prob, backend)
        met = self.evaluador.score(prob, res["respuesta"], brazo,
                                   res["traza"])
        reward = float(met["exito"])
        self.memoria.append_experiencia({
            "problema_id": problema["id"],
            "clase": sig,
            "arch_id": brazo,
            "config": {},
            "features": {"enunciado": problema["enunciado"][:500]},
            "respuesta": res["respuesta"][:2000],
            "traza": res["traza"],
            "metricas": {
                "reward": reward,
                "exito": met["exito"],
                "detalle": met["detalle_verificador"],
                "fase_medicion": fase,
                "bloque": b,
                "firma": sig,
                "con_skill": guiada,
            },
            "costo_usd": res["costo_usd"],
            "fase": "fase1:servicio",
            "origen": "motor-fase1",
        })
        self.resolver.observar(brazo, self._h, reward, b)
        self._h += 1
        return reward

    def _thompson(self, bandit, b, q, problema, sig,
                  skill_arm=None, skill_obj=None):
        a_sel = bandit.select(self._rng(b, q))
        r = self._medir(a_sel, problema, b, q, "thompson", sig,
                        skill_arm=skill_arm, skill_obj=skill_obj)
        bandit.update(a_sel, r)
        return a_sel, r

    # -- fase 2.4: detector de heterogeneidad (EXP68) -----------------------
    def _detector_vivo(self):
        """El detector, o None si está apagado o se rompió (fail-safe)."""
        if self._detector_roto:
            return None
        return self.detector_het

    def _romper_detector(self, motivo):
        """Fail-safe: desactiva el detector para la sesión. El servicio
        sigue con la política vigente (el camino validado sin detector).
        Nunca rompe: ni siquiera si el event log falla."""
        self._detector_roto = True
        self.detector_het = None
        try:
            if self.trazas is not None:
                self.trazas.asentar_ciclo(
                    "detector_desactivado", actor="detector",
                    detalle={"motivo": str(motivo)})
        except Exception:
            pass

    def _drenar_historial_detector(self, det):
        """Emite al event log 2.2 cada transición explorar↔encogido y
        cada spot-check. Fail-safe por dentro."""
        try:
            nuevos = det.historial[self._det_historial_visto:]
        except Exception:
            return
        self._det_historial_visto = len(det.historial)
        if self.trazas is None:
            return
        tipos = {"encoge": "detector_encoge",
                 "restaura": "detector_restaura",
                 "spot_ok": "detector_spot_ok"}
        for ev in nuevos:
            tipo = tipos.get(ev.get("evento"))
            if tipo is None:
                continue
            try:
                self.trazas.asentar_ciclo(
                    tipo, actor="detector",
                    detalle={k: v for k, v in ev.items()
                             if k != "evento"})
            except Exception:
                pass

    def _alimentar_detector(self, b, det, rs_q1, rs_q2):
        """Hook EXP68: el veredicto del bloque es el argmax ESTRICTO de
        las medias del probe MEDIDO (los ítems que la política
        efectivamente midió: Q1 + Q2 si el gate no lo saltó). Nunca el
        fav del posterior (hallazgo de calibración EXP68). Un empate
        (None) reinicia la racha. Fail-safe: nunca rompe el bloque."""
        if det is None:
            return
        try:
            medidas = {a: [rs_q1[q][a] for q in rs_q1]
                       for a in self.brazos}
            if rs_q2:
                for a in self.brazos:
                    medidas[a] += [rs_q2[q][a] for q in rs_q2]
            pm = {a: sum(v) / len(v) for a, v in medidas.items()}
            det.registrar_veredicto(b, ganador_estricto(pm))
            self._drenar_historial_detector(det)
        except Exception:
            self._romper_detector("alimentar")

    def _bloque_encogido(self, b, problemas, sig, det, es_spot,
                         rewards, tel):
        """Bloque en modo ENCOGIDO: se juega el brazo comprometido en
        los 6 ítems, sin probe ni Thompson — réplica del camino de skip
        del diseño validado en EXP68 (modo 'probe').

        El brazo se juega RAW (sin guía de skill): el veredicto que lo
        comprometió se midió raw, y medir el contrafáctico anularía el
        ahorro (misma honestidad que el skip: lo no medido queda
        desconocido, no 0). Cada J bloques: spot-check — Q1+Q2 miden a
        todos los brazos (se banca al comprometido); con margen de
        salida el detector puede restaurar la exploración.
        """
        w = det.comprometido
        aciertos = {a: 0 for a in self.brazos} if es_spot else None
        for q, prob in enumerate(problemas):
            if es_spot and q in SPOT_ITEMS:
                rs = {a: self._medir(a, prob, b, q, "spot", sig)
                      for a in self.brazos}
                for a in self.brazos:
                    aciertos[a] += int(rs[a])  # rewards binarios 0/1
                rewards.append(rs[w])  # se banca al comprometido
            else:
                r = self._medir(w, prob, b, q, "encogido", sig)
                rewards.append(r)
        # Sin probe: sin evidencia (como un bloque saltado).
        self.resolver.probe_obs[b] = None
        try:
            if es_spot:
                det.resolver_spot_check(b, aciertos)
        except Exception:
            self._romper_detector("spot_check")
        tel.update({"saltado": False, "encogido": True,
                    "brazo_comprometido": w, "spot_check": bool(es_spot),
                    "acc": round(sum(rewards) / len(rewards), 4)})
        self._drenar_historial_detector(det)

    # -- el loop -----------------------------------------------------------
    def correr_bloque(self, b, problemas):
        """Un bloque de problemas → decisiones + aprendizaje.

        problemas: lista de BLOQUE dicts {id, enunciado, firma, esperado}.
        Retorna dict de telemetría del bloque."""
        assert len(problemas) == BLOQUE, f"bloque debe tener {BLOQUE}"
        sig = self._firma_bloque(problemas)
        self.detector.observar(sig)
        modo = self.detector.modo()
        skills_on = self.usar_skills and modo == MODO_SKILLS
        self.resolver.proveedor = (self.prov_real if skills_on
                                   else self.prov_nulo)
        self.resolver.block_sig[b] = sig
        skill_obj = (self.prov_real.cargar_skill(sig)
                     if skills_on else None)
        dec = self.resolver.decidir_salto(b, sig)
        saltar, skill_arm = dec["saltar"], dec["skill_arm"]

        rewards = []
        tel = {"bloque": b, "firma": sig, "modo": modo,
               "skills_on": skills_on,
               "skill_archivo": (skill_obj.path if skill_obj else None),
               "soporte": {"wins": dec["wins"], "K": dec["K"],
                           "umbral": dec["umbral"]}}

        # -- fase 2.4: detector de heterogeneidad (EXP68) ----------------
        # En ENCOGIDO el detector manda: réplica del camino de skip
        # (juega el brazo comprometido, sin probe ni Thompson).
        # Fail-safe: si el detector falla antes de medir, se desactiva
        # y el bloque corre por el camino vigente.
        det = self._detector_vivo()
        va_encogido = False
        if det is not None:
            try:
                if det.modo == ENCOGIDO:
                    es_spot = det.iniciar_bloque_encogido()
                    self._bloque_encogido(b, problemas, sig, det, es_spot,
                                          rewards, tel)
                    va_encogido = True
            except Exception:
                self._romper_detector("encogido")
                det = None

        if va_encogido:
            pass  # el bloque ya corrió por el detector
        elif saltar:
            # SKIP: se juega el brazo de la skill, guiado por ella.
            for q, prob in enumerate(problemas):
                r = self._medir(skill_arm, prob, b, q, "skip", sig,
                                skill_arm=skill_arm, skill_obj=skill_obj)
                rewards.append(r)
            acc = sum(rewards) / len(rewards)
            self.resolver.cerrar_bloque_saltado(
                b, sig, skill_arm, dec["wins"], dec["K"], dec["umbral"],
                acc, "no-medido", None)
            # Honestidad: el contrafáctico no se midió (medirlo anularía
            # el skip). El misfire queda desconocido, no 0.
            self.resolver.saltados_det[-1]["misfire"] = None
            tel.update({"saltado": True, "brazo_skill": skill_arm,
                        "acc": round(acc, 4)})
        else:
            bandit, _fav = self.resolver.bandit_ciego(b)
            rs_q1 = {}
            for q in Q1:
                rs = {a: self._medir(a, problemas[q], b, q, "Q1", sig)
                      for a in self.brazos}
                rs_q1[q] = rs
                for a in self.brazos:
                    bandit.update(a, rs[a])
                rewards.append(rs[_fav])
            usa_skill = skill_arm is not None
            if usa_skill:
                bandit = self.resolver.bandit_con_skill(b, sig, rs_q1)
            gate = (usa_skill and skill_arm is not None
                    and self.resolver.gate_q1(rs_q1, skill_arm))
            for q in THOMPSON_PRE:
                _a, r = self._thompson(bandit, b, q, problemas[q], sig,
                                       skill_arm=skill_arm,
                                       skill_obj=skill_obj)
                rewards.append(r)
            rs_q2 = None
            if gate:
                self.resolver.q2_saltados += 1
                for q in Q2:
                    _a, r = self._thompson(bandit, b, q, problemas[q],
                                           sig, skill_arm=skill_arm,
                                           skill_obj=skill_obj)
                    rewards.append(r)
            else:
                rs_q2 = {}
                for q in Q2:
                    rs = {a: self._medir(a, problemas[q], b, q, "Q2", sig)
                          for a in self.brazos}
                    rs_q2[q] = rs
                    for a in self.brazos:
                        bandit.update(a, rs[a])
                    rewards.append(rs[_fav])
            for q in THOMPSON_POST:
                _a, r = self._thompson(bandit, b, q, problemas[q], sig,
                                       skill_arm=skill_arm,
                                       skill_obj=skill_obj)
                rewards.append(r)
            obs = {a: ([rs_q1[q][a] for q in Q1]
                       + ([rs_q2[q][a] for q in Q2] if rs_q2 else []))
                   for a in self.brazos}
            self.resolver.cerrar_bloque_probe(b, obs)
            self.memoria.registrar_bloque_probe(b, sig, obs)
            # Hook EXP68 (fase 2.4): alimentar el detector con el
            # veredicto del probe MEDIDO (nunca el fav del posterior:
            # hallazgo de calibración). El bloque saltado no se alimenta
            # (no extiende ni reinicia la racha, por diseño).
            self._alimentar_detector(b, det, rs_q1, rs_q2)
            tel.update({"saltado": False, "skill_usada": usa_skill,
                        "gate_q1": bool(gate),
                        "acc": round(sum(rewards) / len(rewards), 4)})

        # Generación / refinamiento (solo en modo skills: en adaptativo
        # no se invierte un token en skills — diseño §2.1).
        gen_accion, gen_det = ("omitida", {"razon": "modo adaptativo"})
        if skills_on:
            gen_accion, gen_det = self.generador.maybe_generar_o_refinar(
                sig, self.cliente, self.brazos)
        tel["skill_gen"] = {"accion": gen_accion, "detalle": gen_det}

        tel["regret_bloque"] = round(BLOQUE - sum(rewards), 4)
        tel["costo_usd_acum"] = round(self.cliente.total_usd, 6)
        self.bloques.append(tel)
        return tel

    def feedback(self, experiencia_id, reward, nota=""):
        """Recompensa explícita posterior. El bandit la ve vía la memoria
        (recuperar_con_decaimiento incluye feedback)."""
        fila = self.memoria.por_id(experiencia_id)
        if not fila:
            raise KeyError(f"experiencia {experiencia_id} inexistente")
        fid = self.memoria.append_feedback(
            experiencia_id, max(0.0, min(1.0, float(reward))), nota)
        return {"feedback_id": fid, "experiencia_id": experiencia_id}

    def estado(self):
        det = self._detector_vivo()
        return {
            "version": "motor-fase1",
            "brazos": list(self.brazos),
            "usar_skills": self.usar_skills,
            "bloques_corridos": len(self.bloques),
            "regret_total": round(
                sum(t["regret_bloque"] for t in self.bloques), 4),
            "skills_activas": len(self.skill_index.listar()),
            "probes_saltados": self.resolver.probes_saltados,
            "q2_saltados": self.resolver.q2_saltados,
            "skills_usadas": self.resolver.skills_usadas,
            "modo_recurrencia": self.detector.modo(),
            "tasa_recurrencia": round(
                self.detector.tasa_recurrencia(), 4),
            "costo_usd": round(self.cliente.total_usd, 6),
            "llamados_llm": len(self.cliente.registro),
            "presupuesto": self.presupuesto.estado(),
            "cadena_ok": self.memoria.verify_chain(),
            "uptime_s": round(time.time() - self._t0, 1),
            # fase 2.4: detector de heterogeneidad (EXP68)
            "detector_heterogeneidad": (
                None if det is None else {
                    "activo": True,
                    "K": det.K, "J": det.J,
                    "modo": det.modo,
                    "comprometido": det.comprometido,
                    "racha": list(det.racha),
                    "roto": self._detector_roto,
                }),
        }

    def cerrar(self):
        self.memoria.close()
        self.skill_index.close()
