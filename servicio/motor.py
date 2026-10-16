"""Motor ALMA — probe → selección → ejecución → aprendizaje.

Reutiliza los módulos del prototipo sin modificarlos:
  alma.registry   → repertorio fijo de arquitecturas
  alma.selector   → Thompson sampling por clase
  alma.executors  → runners con interfaz común
  alma.backends   → MockBackend / OpenAICompatBackend / VaultBackend
  alma.evaluator  → Evaluator (exact-match o juez LLM)
  alma.featurizer → classify() cuando no se da clase

El motor agrega lo que el servicio necesita y los experimentos no:
  - prior warm con olvido: al arrancar (y tras cada feedback) reconstruye
    los priors desde SQLite, ponderando cada experiencia pasada por
    0.5^días (maquinaria del EXP9). Nada se borra; lo viejo pesa menos.
    Las experiencias de agentes-batería NO entran al prior (v2.1):
    la batería muere sin dejar deriva.
  - aprendizaje sin ground truth: si el problema trae "esperado" se evalúa
    con exact-match; si el backend es real se usa el juez LLM (1 llamado
    extra, documentado en el costo); si no hay señal, reward=None y el
    bandit NO aprende hasta que llegue feedback explícito vía /feedback.

ALMA v2 (spec servicio/ALMA_V2_SPEC.md):
  - V2.1 baterías vs persistentes según horizonte ("corto"|"largo"|"auto").
  - V2.2 probe consciente de ruido: sin compromiso duro si el gap no
    supera el umbral (exploración adaptativa en vez de lock-in ruidoso).
  - V2.3 contradicción TRIZ formulada antes de la selección; ordena los
    brazos candidatos del probe.
"""

import os
import json
import random
import sys
import hashlib
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alma import backends as B
from alma import executors
from alma.evaluator import Evaluator, StubJudge, LLMJudge
from alma.featurizer import classify, featurize, DESCONOCIDA
import transferencia
from alma.registry import get_arch
from alma.selector import SelectorArquitecturas, PRIOR_ALPHA, PRIOR_BETA

from store_sqlite import SQLiteStore

# -- fase 2 ---------------------------------------------------------------
# Presupuesto con topes duros (diseño §4.3) + revisión de background con
# gate de aprobación (diseño §1.1.3). Sin presupuesto mensual configurado
# el servicio corre en modo barato: la key arranca APAGADA por default.
import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from alma_service.presupuesto import (
    PresupuestoFase2, BUCKET_SERVICIO, MODO_BARATO)
from alma_service.revision import RevisionBackground

# Brazos del servicio v1: los 3 validados en EXP10 (single/cot/reflexion).
BRAZOS_V1 = ("single", "cot", "reflexion")

# Olvido: una experiencia de hace d días pesa 0.5^d (EXP9).
BASE_OLVIDO = 0.5
# Tope de pseudo-observaciones por brazo: evita fosilización del prior.
TOPE_PRIOR = 200.0

# --- ALMA v2 (spec: servicio/ALMA_V2_SPEC.md) -------------------------------
# V2.2 Umbral de ruido del probe: EXP21 mostró que con gap 0,12 y 8 pulls
# medir no le gana a adaptarse; EXP19/20 mostraron que con gaps >= 0,25
# la selección funciona. Default en el medio, documentado.
UMBRAL_RUIDO_DEFAULT = 0.15
# V2.1 Horizontes: "largo" = tareas con deriva / riesgo de cola → baterías.
HORIZONTES = ("corto", "largo", "auto")
# Clases que en modo "auto" se tratan como horizonte largo (tareas
# recurrentes con deriva acumulada y riesgo de cola).
CLASES_HORIZONTE_LARGO = {"analisis_diario"}
# V2.3 Perfiles de brazo para ordenar candidatos según la contradicción.
# (costo y profundidad relativos; 1 = bajo, 3 = alto)
PERFILES_BRAZO = {
    "single": {"costo": 1, "profundidad": 1},
    "cot": {"costo": 2, "profundidad": 2},
    "reflexion": {"costo": 3, "profundidad": 3},
}
PERFIL_DEFAULT = {"costo": 2, "profundidad": 2}


def formular_contradiccion(texto, clase, brazos):
    """V2.3 — paso TRIZ previo a la selección.

    Formula la contradicción del problema (qué parámetro mejora / cuál
    empeora) y ordena los brazos candidatos según la resuelvan.
    Heurística documentada, sin LLM (funciona en demo):
      - problemas cortos o de cálculo → mejora=velocidad,
        empeora=sobre_razonamiento → single primero;
      - resto → mejora=calidad, empeora=costo → reflexion primero.
    La selección sigue siendo el motor (EXP19/20); la contradicción la enfoca.
    """
    n = len(texto or "")
    if clase == "calculo" or n < 60:
        mejora, empeora = "velocidad", "sobre_razonamiento"
    else:
        mejora, empeora = "calidad", "costo"

    def puntaje(arch_id):
        # La mejora pesa doble (el objetivo manda); el empeoramiento
        # penaliza simple. Así la contradicción ordena de verdad en vez
        # de empatar (los perfiles costo/profundidad son proporcionales).
        p = PERFILES_BRAZO.get(arch_id, PERFIL_DEFAULT)
        s = 0
        if mejora == "calidad":
            s += 2 * p["profundidad"]
        if mejora == "velocidad":
            s -= 2 * p["costo"]
        if empeora == "costo":
            s -= p["costo"]
        if empeora == "sobre_razonamiento":
            s -= p["profundidad"]
        return s

    orden = sorted(brazos, key=puntaje, reverse=True)
    return {"mejora": mejora, "empeora": empeora,
            "brazos_ordenados": list(orden)}


def decidir_compromiso(rewards, umbral):
    """V2.2 — probe consciente de ruido (función pura, testeable).

    rewards: dict arch_id → reward (float). Devuelve
    (ganador, gap, compromiso):
      - gap = mejor reward − segundo mejor;
      - compromiso "duro" si gap > umbral (la selección funciona: EXP19/20);
      - compromiso "adaptativo" si no (sin compromiso duro: exploración
        adaptativa continua con re-probe, lección EXP7; eco EXP21/EXP6).
    """
    items = sorted(rewards.items(), key=lambda kv: kv[1], reverse=True)
    ganador = items[0][0]
    segundo = items[1][1] if len(items) > 1 else 0.0
    gap = items[0][1] - segundo
    compromiso = "duro" if gap > umbral else "adaptativo"
    return ganador, gap, compromiso


class BackendDemo(B.LLMBackend):
    """Backend honesto para modo demo/puerta de calidad: NO finge
    inteligencia. Si el problema trae 'esperado' (fijado vía
    fijar_esperado, solo plumbing de prueba), lo devuelve para que el
    evaluador exact-match genere una señal de reward real; si no,
    devuelve un texto marcado como demo y el reward queda en None."""

    def __init__(self):
        self.precios = B.PRECIOS["mock"]
        self._esperados = {}

    def fijar_esperado(self, problem_id, esperado):
        """Solo para pruebas: el demo devuelve este valor como respuesta."""
        self._esperados[problem_id] = esperado

    def complete(self, prompt, system=None, problem_id=None, arch_id=None,
                 modo=None, intento=0, idx=0, formato=None):
        if problem_id in self._esperados:
            cuerpo = str(self._esperados[problem_id])
            texto = (f"Razonamiento demo.\nRespuesta: {cuerpo}"
                     if formato == "respuesta_marcada" else cuerpo)
        else:
            texto = f"[demo:{arch_id}] sin modelo real"
        return texto, {
            "prompt_tokens": max(1, len(prompt) // 4),
            "completion_tokens": max(1, len(texto) // 4),
        }


def _backend_segun_modo(modo_backend):
    if modo_backend == "demo":
        return BackendDemo()
    if modo_backend == "mock":
        # MockBackend necesita índice de problemas; en el servicio los
        # problemas son ad-hoc → el demo honesto es lo correcto.
        return BackendDemo()
    if modo_backend == "vault":
        return B.VaultBackend()
    if modo_backend == "openai":
        return B.OpenAICompatBackend()
    raise ValueError(f"backend desconocido: {modo_backend!r} "
                     "(usá demo | vault | openai)")


def _es_real(backend):
    return isinstance(backend, (B.VaultBackend, B.OpenAICompatBackend))


class Motor:
    def __init__(self, db_path, backend_kind=None, brazos=BRAZOS_V1, seed=0):
        self.brazos = tuple(brazos)
        for b in self.brazos:
            get_arch(b)  # valida que exista en el registry
        backend_kind = backend_kind or os.environ.get("ALMA_BACKEND", "demo")
        self.backend_kind = backend_kind
        self.backend = _backend_segun_modo(backend_kind)
        self.store = SQLiteStore(db_path)
        self.selector = SelectorArquitecturas(arch_ids=list(self.brazos))
        self._rng = random.Random(seed)
        self._lock = threading.Lock()
        self._inicio = time.time()
        self.resueltos = 0
        self._reconstruir_priors()
        # -- fase 2: presupuesto + revisión de background ------------------
        self.presupuesto = PresupuestoFase2(db_path)
        self.revision_bg = RevisionBackground(db_path)
        self._backend_demo = None  # fallback barato, lazy
        self._costo_estimado_resolucion = float(
            os.environ.get("ALMA_COSTO_ESTIMADO_RESOLUCION", "0.005"))
        self._costo_estimado_juez = float(
            os.environ.get("ALMA_COSTO_ESTIMADO_JUEZ", "0.001"))
        # -- fase 2.2: trazas unificadas (lo cablea server.py) ------------
        # EventLog o None; version_scaffold_fn o None. Nada de esto
        # cambia el comportamiento: solo emite al event log.
        self.trazas = None
        self.version_scaffold_fn = None
        self._exp_a_evento = {}  # experiencia_id -> evento de traza

    def _backend_efectivo(self):
        """Gate de presupuesto por resolución (diseño §4.3).

        Sin presupuesto mensual configurado, `autorizar()` devuelve False
        para cualquier costo > 0 y se usa el backend demo: la key arranca
        APAGADA por default. El backend configurado (p. ej. vault, que el
        watchdog exige) se conserva: queda cableado pero sin gastar.
        """
        if _es_real(self.backend) and self.presupuesto.autorizar(
                BUCKET_SERVICIO, self._costo_estimado_resolucion):
            return self.backend
        if self._backend_demo is None:
            self._backend_demo = _backend_segun_modo("demo")
        return self._backend_demo

    def _es_modo_barato_efectivo(self):
        return self._backend_efectivo() is not self.backend

    # -- prior warm con olvido -------------------------------------------
    def _reconstruir_priors(self, clase=None):
        ahora = time.time()
        clases = [clase] if clase else self.store.clases()
        for c in clases:
            bandit = self.selector._bandit(c)
            bandit.alpha = {a: PRIOR_ALPHA for a in self.brazos}
            bandit.beta = {a: PRIOR_BETA for a in self.brazos}
            bandit.pulls = {a: 0 for a in self.brazos}
            for arch_id, reward, ts in self.store.recompensas_por_clase(c):
                if arch_id not in bandit.alpha:
                    continue
                dias = max(0.0, (ahora - ts) / 86400.0)
                peso = BASE_OLVIDO ** dias
                bandit.alpha[arch_id] += reward * peso
                bandit.beta[arch_id] += (1.0 - reward) * peso
                bandit.pulls[arch_id] += 1
            # tope anti-fosilización: escala si un brazo acumuló demasiado
            for a in self.brazos:
                total = bandit.alpha[a] + bandit.beta[a] - 2.0
                if total > TOPE_PRIOR:
                    f = TOPE_PRIOR / total
                    bandit.alpha[a] = 1.0 + (bandit.alpha[a] - 1.0) * f
                    bandit.beta[a] = 1.0 + (bandit.beta[a] - 1.0) * f

    # -- núcleo ------------------------------------------------------------
    def _evaluar(self, problema, respuesta, arch_id, traza, backend=None):
        backend = backend if backend is not None else self.backend
        if problema.get("esperado") is not None:
            ev = Evaluator(judge=StubJudge())
            return ev.score(problema, respuesta, arch_id, traza)
        if _es_real(backend):
            ev = Evaluator(judge=LLMJudge(backend))
            m = ev.score(problema, respuesta, arch_id, traza)
            m["nota"] = "juez LLM (1 llamado extra incluido en costo)"
            return m
        return {
            "exito": None,
            "reward": None,
            "detalle_verificador": "sin señal: ni esperado ni juez;"
                                   " aprende vía /feedback",
            "evaluator_version": "eval-v1",
            "traza": traza,
        }

    def _guardar_y_aprender(self, problema, features, arch_id, resultado,
                            metricas, modo, extras=None):
        met = dict(metricas)
        if extras:
            met.update(extras)
        fila = self.store.append_experiencia({
            "problema_id": problema["id"],
            "clase": problema["clase"],
            "arch_id": arch_id,
            "config": get_arch(arch_id)["parametros"],
            "features": features,
            "respuesta": resultado["respuesta"][:4000],
            "traza": resultado["traza"],
            "metricas": met,
            "costo_usd": resultado["costo_usd"],
            "fase": f"servicio:v2:{modo}:{met.get('modo_agente', '?')}",
            "origen": "servicio-v2",
        })
        reward = met.get("reward")
        # V2.1: la batería muere sin entrenar al bandit (colapso de
        # varianza, no deriva acumulada). Solo el persistente aprende.
        if reward is not None and met.get("modo_agente") != "bateria":
            self.selector.update(problema["clase"], arch_id, reward)
        return fila

    # -- ALMA v2: horizontes y selección ---------------------------------
    def _resolver_horizonte(self, horizonte, clase):
        if horizonte not in HORIZONTES:
            raise ValueError(
                f"horizonte inválido: {horizonte!r} (usá {HORIZONTES})")
        if horizonte == "auto":
            return ("largo" if clase in CLASES_HORIZONTE_LARGO
                    else "corto")
        return horizonte

    def _seleccion_bateria(self, candidatos):
        """Agente-batería: nace sin historia → prior uniforme puro.
        No toca el bandit compartido."""
        return max(candidatos,
                   key=lambda a: self._rng.betavariate(1.0, 1.0))

    def _thompson_restringido(self, clase, candidatos):
        """Thompson sampling entre un subconjunto de brazos, usando el
        posterior warm de la clase."""
        bandit = self.selector._bandit(clase)
        return max(candidatos,
                   key=lambda a: self._rng.betavariate(
                       bandit.alpha.get(a, PRIOR_ALPHA),
                       bandit.beta.get(a, PRIOR_BETA)))

    def _extras_base(self, modo_agente, horizonte, contradiccion,
                     gap_estimado, compromiso, umbral, transferencia="completa"):
        return {
            "modo_agente": modo_agente,          # bateria | persistente
            "horizonte": horizonte,              # corto | largo (resuelto)
            "gap_estimado": gap_estimado,        # float | None
            "contradiccion": contradiccion,      # {mejora, empeora, brazos_ordenados}
            "compromiso": compromiso,           # duro | adaptativo | thompson | probe
            "umbral_ruido": umbral,              # umbral aplicado
            "transferencia": transferencia,      # mapless | completa (V2.4)
        }

    def resolver(self, texto, clase=None, esperado=None, modo="thompson",
                 horizonte="auto", umbral_ruido=None):
        """Un problema → respuesta + aprendizaje. Hilo-seguro.

        horizonte: "corto" | "largo" | "auto" (default). "largo" usa
            agentes-batería (nacen por tarea, no entrenan al bandit).
        umbral_ruido: float >= 0 para el probe consciente de ruido
            (default UMBRAL_RUIDO_DEFAULT).
        """
        with self._lock:
            return self._resolver_locked(texto, clase, esperado, modo,
                                         horizonte, umbral_ruido)

    def _resolver_locked(self, texto, clase, esperado, modo, horizonte,
                         umbral_ruido):
        t0 = time.time()  # fase 2.2: latencia de la decisión para la traza
        if not texto or not texto.strip():
            raise ValueError("texto vacío")
        if modo not in ("thompson", "probe"):
            raise ValueError("modo: thompson | probe")
        if umbral_ruido is None:
            umbral_ruido = UMBRAL_RUIDO_DEFAULT
        try:
            umbral_ruido = float(umbral_ruido)
        except (TypeError, ValueError):
            raise ValueError("umbral_ruido debe ser un número >= 0")
        if umbral_ruido < 0:
            raise ValueError("umbral_ruido debe ser >= 0")
        clase = clase or classify(texto)[0]
        if clase == DESCONOCIDA:
            clase = "desconocida"  # el bandit la trata como una clase más
        horizonte_ef = self._resolver_horizonte(horizonte, clase)
        modo_agente = ("bateria" if horizonte_ef == "largo"
                       else "persistente")
        problema = {
            "id": f"srv-{int(time.time()*1000)}-{self.resueltos}",
            "enunciado": texto,
            "clase": clase,
            "verificador": "exact" if esperado is not None else "ninguno",
            "esperado": esperado,
        }
        features = featurize(texto)
        # Fase 2: gate de presupuesto. Sin tope mensual, `backend` es el
        # demo aunque el configurado sea vault: la key arranca APAGADA.
        backend = self._backend_efectivo()
        # V2.3: la contradicción se formula ANTES de seleccionar.
        contradiccion = formular_contradiccion(texto, clase, self.brazos)
        if isinstance(backend, BackendDemo) and esperado is not None:
            backend.fijar_esperado(problema["id"], esperado)

        gap, compromiso, ganador = None, "thompson", None
        transferencia_usada = "completa"
        if modo == "probe":
            if esperado is None and not _es_real(backend):
                raise ValueError(
                    "el modo probe necesita señal de reward: pasá 'esperado'"
                    " o usá un backend real (vault/openai)")
            # V2.3: el probe evalúa los candidatos en el orden que sugiere
            # la contradicción.
            orden_triz = [a for a in contradiccion["brazos_ordenados"]
                          if a in self.brazos]
            for a in self.brazos:
                if a not in orden_triz:
                    orden_triz.append(a)
            # V2.4: clase fina (< 5 experiencias con reward) → shortlist
            # mapless: top-2 brazos por frecuencia global de
            # mejor-brazo-por-clase, desempate por contradicción TRIZ.
            # Evidencia: EXP27/28/29 (el mapa es una apuesta; el shortlist
            # global nunca es catastrófico).
            if transferencia.es_clase_fina(self.store, clase):
                orden = transferencia.shortlist_mapless(
                    self.store, self.brazos, orden_desempate=orden_triz)
                transferencia_usada = "mapless"
            else:
                orden = orden_triz
                transferencia_usada = "completa"
            resultados = {}
            for arch_id in orden:
                res = executors.ejecutar(arch_id, problema, backend)
                met = self._evaluar(problema, res["respuesta"], arch_id,
                                    res["traza"], backend)
                extras_med = self._extras_base(
                    modo_agente, horizonte_ef, contradiccion,
                    None, "probe", umbral_ruido)
                self._guardar_y_aprender(problema, features, arch_id,
                                         res, met, modo, extras_med)
                resultados[arch_id] = (res, met)
            rewards = {a: resultados[a][1].get("reward") for a in orden}
            validas = {a: r for a, r in rewards.items() if r is not None}
            if len(validas) >= 2:
                ganador, gap, compromiso = decidir_compromiso(
                    validas, umbral_ruido)
            else:
                # Sin señal medible en ≥2 brazos: no hay gap → adaptativo.
                ganador, gap, compromiso = orden[0], None, "adaptativo"
            if compromiso == "duro":
                arch_id = ganador
            else:
                # V2.2: sin compromiso duro → exploración adaptativa
                # continua entre los candidatos (re-probe, lección EXP7).
                # Se reutiliza la ejecución ya hecha: sin costo extra.
                arch_id = (self._seleccion_bateria(orden)
                           if modo_agente == "bateria"
                           else self._thompson_restringido(clase, orden))
            res, met = resultados[arch_id]
            extras_fin = self._extras_base(
                modo_agente, horizonte_ef, contradiccion,
                gap, compromiso, umbral_ruido,
                transferencia=transferencia_usada)
            fila = self._guardar_y_aprender(problema, features, arch_id,
                                            res, met, modo, extras_fin)
        else:
            if modo_agente == "bateria":
                arch_id = self._seleccion_bateria(self.brazos)
            else:
                arch_id = self.selector.select(clase, self._rng)
            res = executors.ejecutar(arch_id, problema, backend)
            met = self._evaluar(problema, res["respuesta"], arch_id,
                                res["traza"], backend)
            extras = self._extras_base(
                modo_agente, horizonte_ef, contradiccion,
                None, "thompson", umbral_ruido)
            fila = self._guardar_y_aprender(problema, features, arch_id,
                                            res, met, modo, extras)

        # Fase 2.2: traza unificada de la decisión (fail-safe por dentro:
        # nunca rompe la resolución aunque el event log falle).
        self._asentar_traza(t0, clase, modo, horizonte_ef, modo_agente,
                            gap, compromiso, ganador, transferencia_usada,
                            arch_id, res, met, fila, backend)

        self.resueltos += 1
        # Fase 2: registrar el gasto medido y contar la interacción para
        # la revisión de background (hilo separado, fuera del crítico).
        try:
            if backend is self.backend and _es_real(backend):
                self.presupuesto.cargar(BUCKET_SERVICIO,
                                        float(res["costo_usd"] or 0.0))
                if "juez LLM" in (met.get("nota") or ""):
                    self.presupuesto.cargar(BUCKET_SERVICIO,
                                            self._costo_estimado_juez)
        except Exception:
            pass  # el presupuesto nunca rompe una resolución
        try:
            self.revision_bg.registrar_interaccion()
        except Exception:
            pass
        return {
            "respuesta": res["respuesta"],
            "brazo": arch_id,
            "clase": clase,
            "modo": modo,
            "reward": met.get("reward"),
            "exito": met.get("exito"),
            "costo_usd": round(res["costo_usd"], 6),
            "experiencia_id": fila["id"],
            "traza": res["traza"],
            "backend": self.backend_kind,
            "backend_efectivo": ("demo_forzado_modo_barato"
                                 if backend is not self.backend
                                 else self.backend_kind),
            # ALMA v2 (compatibles: campos nuevos, ninguno viejo cambia)
            "modo_agente": modo_agente,
            "horizonte": horizonte_ef,
            "gap_estimado": gap,
            "contradiccion": contradiccion,
            "compromiso": compromiso,
            "transferencia": transferencia_usada,
        }

    def feedback(self, experiencia_id, reward, nota=""):
        """Recompensa explícita posterior (ej: ¿sirvió el análisis de anoche?)."""
        with self._lock:
            r = max(0.0, min(1.0, float(reward)))
            fila = self.store.por_id(experiencia_id)
            if not fila:
                raise KeyError(f"experiencia {experiencia_id} inexistente")
            fid = self.store.append_feedback(experiencia_id, r, nota)
            # V2.1: ni el feedback explícito entrena al bandit si la
            # experiencia fue de un agente-batería (murió sin dejar deriva).
            try:
                met = json.loads(fila["metricas"])
            except (ValueError, TypeError):
                met = {}
            es_bateria = (isinstance(met, dict)
                          and met.get("modo_agente") == "bateria")
            if not es_bateria:
                self.selector.update(fila["clase"], fila["arch_id"], r)
            # Fase 2.2: completar el reward medido en la traza unificada.
            # El minero solo lee eventos con reward medido (§4.2).
            try:
                eid = self._exp_a_evento.pop(experiencia_id, None)
                if eid is not None and self.trazas is not None:
                    self.trazas.actualizar_reward(eid, r)
            except Exception:
                pass
            return {"feedback_id": fid, "experiencia_id": experiencia_id,
                    "reward": r, "aplico_al_bandit": not es_bateria}

    # -- fase 2.2: trazas unificadas ---------------------------------------
    def _version_scaffold(self):
        """Hash corto del scaffold vigente, para la traza."""
        try:
            sc = (self.version_scaffold_fn()
                  if self.version_scaffold_fn is not None else None)
        except Exception:
            sc = None
        if sc is None:
            from alma_service.scaffold import DEFAULT_SCAFFOLD
            sc = DEFAULT_SCAFFOLD
        canon = json.dumps(sc, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]

    def _asentar_traza(self, t0, clase, modo, horizonte_ef, modo_agente,
                       gap, compromiso, ganador, transferencia_usada,
                       arch_id, res, met, fila, backend):
        """Asienta la decisión en el event log unificado.

        Fail-safe por dentro: cualquier error se traga — la traza
        nunca rompe la resolución (mismo patrón que el presupuesto).
        """
        if self.trazas is None:
            return
        try:
            eid = self.trazas.asentar_decision(
                firma_regimen=clase,
                veredicto_probe=(str(ganador) if modo == "probe"
                                 and ganador else None),
                brazo_elegido=arch_id,
                reward=met.get("reward"),
                costo_usd=float(res.get("costo_usd") or 0.0),
                latencia_ms=round((time.time() - t0) * 1000.0, 1),
                scaffold_version=self._version_scaffold(),
                modo=modo,
                backend_efectivo=("demo_forzado_modo_barato"
                                  if backend is not self.backend
                                  else self.backend_kind),
                extras={"gap": gap, "compromiso": compromiso,
                        "transferencia": transferencia_usada,
                        "modo_agente": modo_agente,
                        "horizonte": horizonte_ef})
            # mapa experiencia -> evento para que feedback() complete
            # el reward medido a posteriori.
            try:
                self._exp_a_evento[fila["id"]] = eid
                if len(self._exp_a_evento) > 10000:
                    for k in list(self._exp_a_evento)[:5000]:
                        del self._exp_a_evento[k]
            except Exception:
                pass
        except Exception:
            pass

    def estado(self):
        with self._lock:
            medias = {c: self.selector.means(c)
                      for c in self.selector.clases}
            try:
                fase2 = {
                    "presupuesto": self.presupuesto.estado(),
                    "backend_efectivo_barato": self._es_modo_barato_efectivo(),
                    "revision_bg": self.revision_bg.estado(),
                }
            except Exception as e:  # el estado nunca rompe /estado
                fase2 = {"error": str(e)[:200]}
            return {
                "version": "servicio-v2",
                "backend": self.backend_kind,
                "brazos": list(self.brazos),
                "umbral_ruido_default": UMBRAL_RUIDO_DEFAULT,
                "clases_horizonte_largo": sorted(CLASES_HORIZONTE_LARGO),
                "experiencias": self.store.contar(),
                "resueltos_sesion": self.resueltos,
                "clases": self.store.clases(),
                "medias_por_clase": medias,
                "cadena_ok": self.store.verify_chain(),
                "uptime_s": round(time.time() - self._inicio, 1),
                "fase2": fase2,
            }
