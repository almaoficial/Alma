"""Meta-loop fase 2 — el loop RSO de EXP56 como proponente de scaffold.

Diseño §3.1/§3.2: propone variantes de los 5 hiperparámetros del scaffold
sobre el registry existente (no inventa arquitecturas), validadas por el
harness en sandbox con keep/revert estricto.

REGLA DE ORO (diseño §3.2, anti-DGM): el loop NUNCA edita al validador.
El oráculo (tasas), el stream, el cómputo de regret y los splits
entrenamiento/held-out están congelados; solo los hiperparámetros mutan.
Este módulo los importa, no los define ni los toca.

Protocolo de adopción (idéntico al laboratorio hasta la puerta):
  sandbox → pre-registro en disco ANTES de la primera réplica →
  A/B pareado (réplicas train [0,1,2], held-out [3,4] que el loop no ve
  durante la búsqueda) → keep/revert greedy → PASS de la PUERTA DE DOS
  SPLITS (fase 2.1: Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(Δ_in,Δ_ho) > 0) →
  E3 (integración 28/9): tercer split ciego (réplicas reservadas
  [500,501]); endurecimiento 28/9: E3 SIEMPRE exigido cuando los dos
  splits aceptan (forzar_e3=True), y veta ante regresión en el ciego;
  nunca relaja la puerta → AUTO-ADOPCIÓN gobernada (27/9 ~22:50, refino "pero no peor"): solo ante
  mejora medida (Δ_ho > 0 estricto, Δ_in ≥ 0, frenos sanos); lo igual o
  peor se rechaza con números y no se adopta; el núcleo protegido
  (presupuesto, puerta, notificaciones) bloquea con raise + aviso →
  audit record por propuesta (ronda y adopción final) → ledger con
  lineage + rollback (toda adopción es reversible y notificada).

Cada ronda asienta un audit record con la debilidad clusterizada
vigente (minería por firmas exactas, debilidades.py): el minero
DESCRIBE, no prescribe — no dirige las mutaciones (EXP58).

El loop corre por schedule (semanal) o a pedido, en un hilo separado:
NUNCA en el camino crítico de una respuesta. En mock (US$0) el costo es
cero, así que el presupuesto siempre lo autoriza; si algún día el
meta-loop usara modelos reales, pasaría por el bucket 'metaloop'.
"""

import hashlib
import json
import os
import random
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                               "exp56_rso"))

import run_experiment47 as e47  # noqa: E402  (validador congelado)
import run_experiment56 as e56  # noqa: E402  (maquinaria RSO validada)
from alma_service.scaffold import DEFAULT_SCAFFOLD  # noqa: E402
from alma_service.presupuesto import (  # noqa: E402
    PresupuestoFase2, BUCKET_METALOOP)
from alma_service.gate import (  # noqa: E402
    PuertaDosSplits, audit_record, decidir_auto_adopcion,
    PISO_RUIDO_DELTA)
from alma_service.archivo import ArchivoVariantes  # noqa: E402
from alma_service.puerta_e3 import (  # noqa: E402  (integración 28/9)
    E3_HABILITADO, MARGEN_MIN_DEFAULT, E3_REPS, SUPERFICIE_METALOOP,
    exigir_e3, decidir as decidir_e3, audit_record_e3,
    resumen_config_e3)
from alma_service.debilidades import (  # noqa: E402
    MineroDebilidades, firma_meta)
from alma_service.verificacion import (  # noqa: E402
    LoopVerificacion, declarar_criterio)
from alma_service.promotor import (  # noqa: E402
    Promotor, NucleoProtegidoError)  # gobernanza 27/9 ~22:50

# Mismo espacio de mutación validado en EXP56 (pre-registrado, acotado).
SPACES = dict(e56.SPACES)
TRAIN_REPS = list(e56.TRAIN_REPS)      # [0, 1, 2]
HELDOUT_REPS = list(e56.HELDOUT_REPS)  # [3, 4]
RONDAS_DEFAULT = 8  # el servicio usa 8 (EXP56 usó 24); documentado.

# Freno de estancamiento (idea 2, revisión nocturna 7/10): el meta-loop
# corre desatendido (semanal). Si propone 3 corridas seguidas sin mejora
# medida (sin adopción por la puerta), algo está estancado: el loop se
# detiene solo y avisa. Solo un humano lo reanuda (desbloquear_freno).
# Diseño: a nivel CORRIDA, no propuesta — dentro de una corrida los
# reverts seguidos son exploración normal de RSO (EXP56); frenar ahí
# rompería la búsqueda validada. "Mejora medida" = adopción (la puerta
# ya midió Δ>0); una corrida sin adopción suma a la racha.
RACHA_MAX_PLANA = 3


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def _hash_evento(prev, cuerpo):
    return hashlib.sha256(
        (prev + _canonical(cuerpo)).encode("utf-8")).hexdigest()


class MetaLoop:
    """Proponente RSO del scaffold. Toda adopción queda en el ledger."""

    def __init__(self, db_path, presupuesto=None, ledger_path=None,
                 rondas=RONDAS_DEFAULT, archivo_path=None):
        self.db_path = db_path
        self.presupuesto = presupuesto or PresupuestoFase2(db_path)
        d = os.path.dirname(os.path.abspath(db_path))
        self.ledger_path = (ledger_path or
                            os.path.join(d, "metaloop_ledger.jsonl"))
        # Archivo de variantes (decisión del usuario 7/10 ~01:01): tercera
        # pata de la puerta. Solo-append; la puerta y la adopción no cambian.
        self.archivo = ArchivoVariantes(
            archivo_path or os.path.join(d, "metaloop_archivo.jsonl"))
        self.rondas = rondas
        self._lock = threading.Lock()
        self._hilo = None
        # Minería de debilidades (fase 2.1, Self-Harness §3.2): clusteriza
        # firmas exactas de keeps/reverts históricos. Describe, no
        # prescribe: audita contexto en los audit records, no dirige las
        # mutaciones (lección EXP58).
        self.minero = MineroDebilidades()
        self._reproducir_mineria()
        self._estado = {"fase": "inactivo", "ultima_corrida": None}
        # Fase 2.2: event log unificado (lo cablea server.py). None =
        # no emite; el loop no cambia su comportamiento. Fase 2.3: el
        # setter propaga al promotor (staging + freno humano).
        self._event_log = None
        # Fase 2.3: promotor con freno humano. El commit real
        # (_aplicar_promocion) SOLO se invoca desde aprobar() con un
        # aprobador de la allowlist ("humano",).
        # Gobernanza 27/9 ~22:50 (decisión del usuario, refino "pero no
        # peor"): la fase 2.3 queda SUPERADA para el meta-loop. Un PASS de
        # la puerta se AUTO-ADOPTA vía promotor.auto_adoptar() solo ante
        # mejora medida (Δ_ho > 0, Δ_in ≥ 0, frenos sanos); el núcleo
        # protegido (presupuesto, puerta, notificaciones) está fuera de
        # su alcance. El camino manual proponer/aprobar sigue existiendo.
        self.promotor = Promotor(
            self.db_path,
            aplicar_fn=self._aplicar_promocion,
            ledger_fn=self._ledger_append,
            revertir_fn=self._revertir_adopcion)
        self.promotor.event_log = self._event_log
        self._init_db()
        # Freno de estancamiento (idea 2): tabla de una sola fila con la
        # racha de corridas planas y el estado del freno. Persiste en la
        # DB del loop (sobrevive reinicios: las corridas son semanales).
        self._init_freno()
        if not os.path.exists(self.ledger_path):
            with open(self.ledger_path, "w", encoding="utf-8"):
                pass
        if self.scaffold_vigente() is None:
            self._asentar_scaffold(dict(DEFAULT_SCAFFOLD),
                                   origen="default_validado_EXP56_57")

    # -- freno de estancamiento (idea 2) ----------------------------------
    def _init_freno(self):
        with self._con() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS freno_estancamiento (
                       id INTEGER PRIMARY KEY CHECK (id = 1),
                       racha_planas INTEGER NOT NULL DEFAULT 0,
                       freno_activo INTEGER NOT NULL DEFAULT 0,
                       actualizado REAL NOT NULL
                   )""")
            hay = con.execute(
                "SELECT 1 FROM freno_estancamiento WHERE id = 1"
            ).fetchone()
            if hay is None:
                con.execute(
                    "INSERT INTO freno_estancamiento"
                    " (id, racha_planas, freno_activo, actualizado)"
                    " VALUES (1, 0, 0, ?)", (time.time(),))

    def estado_freno(self):
        """Racha de corridas planas y si el freno está activo."""
        with self._con() as con:
            fila = con.execute(
                "SELECT racha_planas, freno_activo"
                " FROM freno_estancamiento WHERE id = 1").fetchone()
        return {"racha_planas": fila[0],
                "freno_activo": bool(fila[1]),
                "racha_max": RACHA_MAX_PLANA}

    def registrar_corrida(self, adoptado):
        """Registra el resultado de una corrida para el freno.

        adoptado=True (la puerta midió mejora y se adoptó) resetea la
        racha. adoptado=False la incrementa; al llegar a RACHA_MAX_PLANA
        el freno se activa: correr() se niega hasta revisión humana.
        El freno, una vez activo, solo lo limpia desbloquear_freno().
        Se llama sola al final de _correr_bg; en tests se invoca directo.
        """
        with self._con() as con:
            fila = con.execute(
                "SELECT racha_planas, freno_activo"
                " FROM freno_estancamiento WHERE id = 1").fetchone()
            racha = 0 if adoptado else fila[0] + 1
            freno = fila[1]
            recien_activado = False
            if racha >= RACHA_MAX_PLANA and not freno:
                freno = 1
                recien_activado = True
            con.execute(
                "UPDATE freno_estancamiento SET racha_planas = ?,"
                " freno_activo = ?, actualizado = ? WHERE id = 1",
                (racha, freno, time.time()))
        if recien_activado:
            # Aviso: ledger (auditable) + event log (lo ve el servicio).
            self._ledger_append({
                "tipo": "metaloop_freno_estancamiento",
                "racha_planas": racha,
                "mensaje": (f"{RACHA_MAX_PLANA} corridas seguidas sin"
                            " mejora medida: el meta-loop se detiene"
                            " hasta revisión humana"),
            })
            self._emitir_ciclo("metaloop_freno_estancamiento",
                               {"racha_planas": racha})
        return {"racha_planas": racha, "freno_activo": bool(freno)}

    def desbloquear_freno(self, origen="humano"):
        """Reanuda el loop tras revisar el estancamiento. Solo humano
        (como el rollback): el loop nunca se desbloquea solo."""
        with self._con() as con:
            con.execute(
                "UPDATE freno_estancamiento SET racha_planas = 0,"
                " freno_activo = 0, actualizado = ? WHERE id = 1",
                (time.time(),))
        self._ledger_append({"tipo": "metaloop_freno_desbloqueado",
                             "origen": origen})
        self._emitir_ciclo("metaloop_freno_desbloqueado",
                           {"origen": origen})
        return {"freno_activo": False, "racha_planas": 0}

    # -- persistencia (aditiva) -------------------------------------------
    def _con(self):
        import sqlite3
        con = sqlite3.connect(self.db_path, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init_db(self):
        with self._con() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS scaffold_activo (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       scaffold_json TEXT NOT NULL,
                       origen TEXT NOT NULL DEFAULT '',
                       timestamp REAL NOT NULL
                   )""")

    def _asentar_scaffold(self, scaffold, origen=""):
        with self._con() as con:
            con.execute(
                "INSERT INTO scaffold_activo (scaffold_json, origen,"
                " timestamp) VALUES (?, ?, ?)",
                (_canonical(scaffold), origen, time.time()))

    def scaffold_vigente(self):
        with self._con() as con:
            fila = con.execute(
                "SELECT scaffold_json FROM scaffold_activo"
                " ORDER BY id DESC LIMIT 1").fetchone()
        return json.loads(fila[0]) if fila else None

    def historial_scaffold(self, n=20):
        with self._con() as con:
            filas = con.execute(
                "SELECT id, scaffold_json, origen, timestamp FROM"
                " scaffold_activo ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        return [{"id": f[0], "scaffold": json.loads(f[1]),
                 "origen": f[2], "timestamp": f[3]} for f in filas]

    # -- ledger -------------------------------------------------------------
    def _ledger_append(self, evento):
        with self._lock:
            prev = "GENESIS"
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                for linea in f:
                    linea = linea.strip()
                    if linea:
                        prev = json.loads(linea)["hash"]
            cuerpo = dict(evento)
            cuerpo["timestamp"] = time.time()
            h = _hash_evento(prev, cuerpo)
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(_canonical({"prev": prev, "hash": h,
                                    "evento": cuerpo}) + "\n")
            return h

    def ledger_leer(self):
        eventos = []
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    eventos.append(json.loads(linea))
        return eventos

    # -- fase 2.3: el event log se propaga al promotor ------------------
    @property
    def event_log(self):
        return self._event_log

    @event_log.setter
    def event_log(self, el):
        self._event_log = el
        prom = getattr(self, "promotor", None)
        if prom is not None:
            prom.event_log = el

    def _aplicar_promocion(self, scaffold, origen=""):
        """Commit real de una promoción APROBADA por el humano.

        Uno de los tres caminos por los que el scaffold vigente cambia
        por decisión del ciclo de mejora: aprobar() manual con aprobador
        de la allowlist, auto_adoptar() ante mejora medida, o
        revertir_adopcion(). Además del rollback manual (acción humana
        directa).
        """
        self._asentar_scaffold(dict(scaffold), origen=origen)

    def _revertir_adopcion(self, scaffold, origen=""):
        """Deshace una auto-adopción re-asentando el scaffold previo.
        Lo invoca Promotor.revertir_adopcion(); toda adopción es
        reversible por construcción."""
        self._asentar_scaffold(dict(scaffold), origen=origen)

    # -- fase 2.2: trazas unificadas --------------------------------------
    def _emitir_ciclo(self, tipo, detalle):
        """Evento del ciclo al event log unificado. Fail-safe: el log
        nunca rompe el loop (mismo patrón que el presupuesto)."""
        if self.event_log is None:
            return
        try:
            self.event_log.asentar_ciclo(tipo=tipo, actor="metaloop",
                                         detalle=detalle)
        except Exception:
            pass

    # -- validador congelado --------------------------------------------------
    @staticmethod
    def _evaluar(scaffold, replicas, cache):
        """Regret medio del scaffold en las réplicas (validador congelado:
        e56.correr_replica_param + stream y tasas de e47, sin tocar)."""
        k = (tuple(sorted(scaffold.items())), tuple(replicas))
        if k not in cache:
            items = e47.construir_stream()
            tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
            regs = [e56.correr_replica_param(r, items, tasas,
                                             dict(scaffold))["reg_pol"]
                    for r in replicas]
            cache[k] = (sum(regs) / len(regs), regs)
        return cache[k]

    @staticmethod
    def _proponer(rng, actual):
        """Una mutación: un parámetro -> otro valor de su espacio."""
        clave = rng.choice(sorted(SPACES.keys()))
        opciones = [v for v in SPACES[clave] if v != actual[clave]]
        nuevo = dict(actual)
        nuevo[clave] = rng.choice(opciones)
        return nuevo, clave

    # -- tercer split ciego (integración 28/9, decisión del usuario) ----
    def _puerta_e3(self, vigente, actual, cache, puerta):
        """Endurece la puerta de dos splits con el tercer split ciego.

        Solo endurece, nunca relaja: si los dos splits rechazan, el E3
        ni se evalúa (short-circuit). Fail-closed: si el E3 es exigido
        pero no se puede evaluar, no hay adopción.

        Endurecimiento 28/9 (decisión del usuario): E3 SIEMPRE exigido
        cuando los dos splits aceptan — se pasa forzar_e3=True tanto al
        chequeo de exigencia como al decidir_e3 final (consistencia: el
        decidir puro re-evaluaría la regla condicional y desharía el
        endurecimiento). El kill switch E3_HABILITADO sigue siendo la
        válvula de seguridad (en False, vuelve a dos splits).

        El split ciego corre sobre E3_REPS (réplicas reservadas, nunca
        vistas por la búsqueda ni por E1/E2) con el validador congelado
        — el mismo _evaluar de siempre, sin tocar el oráculo.
        """
        base = {"puerta_dos_splits_aceptado": bool(puerta["aceptado"]),
                "delta_in": puerta["delta_in"],
                "delta_ho": puerta["delta_ho"],
                "e3_habilitado": bool(E3_HABILITADO)}
        if not puerta["aceptado"]:
            return {**base, "aceptado": False, "e3_exigido": False,
                    "e3_evaluado": False, "delta_e3": None,
                    "motivo": (f"dos splits rechazan: {puerta['motivo']}"
                               " (E3 no evaluado)")}
        if not E3_HABILITADO:
            return {**base, "aceptado": True, "e3_exigido": False,
                    "e3_evaluado": False, "delta_e3": None,
                    "motivo": (f"dos splits aceptan: {puerta['motivo']} | "
                               "E3 deshabilitado (kill switch)")}
        try:
            exigido, motivo_ex = exigir_e3(
                puerta["delta_in"], puerta["delta_ho"],
                superficie=SUPERFICIE_METALOOP,
                margen_min=MARGEN_MIN_DEFAULT,
                forzar_e3=True)  # endurecimiento 28/9: E3 siempre exigido
        except ValueError as e:
            return {**base, "aceptado": False, "e3_exigido": False,
                    "e3_evaluado": False, "delta_e3": None,
                    "motivo": f"E3 no evaluable (config): {e} (fail-closed)"}
        if not exigido:
            return {**base, "aceptado": True, "e3_exigido": False,
                    "e3_evaluado": False, "delta_e3": None,
                    "motivo": (f"dos splits aceptan: {puerta['motivo']} | "
                               f"E3 no exigido: {motivo_ex}")}
        try:
            e3_base, _ = self._evaluar(vigente, E3_REPS, cache)
            e3_cand, _ = self._evaluar(actual, E3_REPS, cache)
            delta_e3 = round(e3_base - e3_cand, 4)
        except Exception as e:  # noqa: BLE001
            return {**base, "aceptado": False, "e3_exigido": True,
                    "e3_evaluado": False, "delta_e3": None,
                    "motivo": (f"E3 exigido pero no evaluable: {e} "
                               "(fail-closed: sin tercer split no hay"
                               " adopción)")}
        dec = decidir_e3(puerta["delta_in"], puerta["delta_ho"],
                         delta_e3=delta_e3,
                         superficie=SUPERFICIE_METALOOP,
                         margen_min=MARGEN_MIN_DEFAULT,
                         forzar_e3=True)  # endurecimiento: consistencia
        return {**base,
                "aceptado": dec["aceptado"], "motivo": dec["motivo"],
                "e3_exigido": dec["e3_exigido"],
                "e3_evaluado": dec["e3_evaluado"],
                "delta_e3": delta_e3,
                "e3_reps": list(E3_REPS),
                "e3_base": round(e3_base, 4),
                "e3_cand": round(e3_cand, 4)}

    # -- corrida ---------------------------------------------------------------
    def correr(self, seed=None, rondas=None, bloqueante=False,
               contexto_disparo=None):
        """Lanza el loop RSO en background (nunca en el camino crítico).

        Devuelve inmediatamente {"aceptado": bool, ...}. Si ya hay una
        corrida en curso, la rechaza (una sola línea de evolución).

        contexto_disparo (opcional, fase 2.6): dict del trigger por trazas
        (p. ej. {"nuevas_trazas": N}) que se documenta en el pre-registro.
        No cambia el loop: solo contexto auditado.
        """
        if not self.presupuesto.autorizar(BUCKET_METALOOP, 0.0):
            return {"aceptado": False,
                    "motivo": "presupuesto del bucket metaloop agotado"}
        # Freno de estancamiento (idea 2): con el freno activo no se
        # arranca ninguna corrida hasta revisión humana.
        freno = self.estado_freno()
        if freno["freno_activo"]:
            return {"aceptado": False,
                    "motivo": (f"freno de estancamiento activo:"
                               f" {freno['racha_planas']} corridas seguidas"
                               f" sin mejora medida; revisar y llamar"
                               f" desbloquear_freno()")}
        with self._lock:
            if self._hilo and self._hilo.is_alive():
                return {"aceptado": False,
                        "motivo": "ya hay una corrida en curso"}
            self._estado["fase"] = "en_curso"
            self._hilo = threading.Thread(
                target=self._correr_bg,
                args=(seed if seed is not None else int(time.time()) % 100000,
                      rondas or self.rondas, contexto_disparo),
                daemon=True)
            self._hilo.start()
            hilo = self._hilo
        # El join va FUERA del lock: el worker lo necesita al finalizar
        # (deadlock si se joinea adentro).
        if bloqueante:
            hilo.join()
        return {"aceptado": True, "fase": "en_curso"}

    def _reproducir_mineria(self):
        """Alimenta el minero con los keeps/reverts de corridas pasadas
        (audit records del ledger). Solo lee; no cambia nada."""
        try:
            for e in self.ledger_leer():
                ev = e.get("evento", {})
                if ev.get("tipo") != "audit_propuesta":
                    continue
                p = ev.get("propuesta") or {}
                if not p.get("clave"):
                    continue
                self.minero.alimentar(firma_meta(
                    p["clave"], p.get("anterior"), p.get("nuevo"),
                    "keep" if ev.get("aceptado") else "revert"))
        except Exception:
            pass  # un ledger viejo/ilegible no frena el arranque

    def _correr_bg(self, seed, rondas, contexto_disparo=None):
        # Cherny (f): el meta-loop corre como ROUTINE — memoria compartida
        # (ledger, scaffold_activo, DBs), contexto NO compartido: cada
        # corrida reconstruye su estado efímero desde lo persistido. El
        # minero se relee del ledger acá (nada in-memory cruza corridas) y
        # el cache de evaluación es por corrida.
        self.minero = MineroDebilidades()
        self._reproducir_mineria()
        rng = random.Random(seed)
        vigente = self.scaffold_vigente()
        cache = {}
        # Cherny (e): el criterio de parada se declara ANTES del loop y va
        # al pre-registro. El loop es producir → observar → comparar →
        # parar (LoopVerificacion), no un for abierto.
        criterio_parada = declarar_criterio("rondas_fijas", n=rondas)
        # Pre-registro ANTES de la primera réplica (diseño §3.2).
        # Fase 2.1: se mide también el train del vigente, porque la
        # puerta de dos splits exige no-regresión en ambos.
        media_train_base, _ = self._evaluar(vigente, TRAIN_REPS, cache)
        base_actual, _ = self._evaluar(vigente, HELDOUT_REPS, cache)
        prereg = {
            "experimento": "metaloop_rso",
            "seed": seed,
            "rondas": rondas,
            "criterio_parada": criterio_parada,
            "scaffold_partida": vigente,
            "heldout_partida": base_actual,
            "criterio_adopcion": ("puerta de dos splits: Δ_in ≥ 0 ∧ Δ_ho ≥ 0"
                                  " ∧ max(Δ_in,Δ_ho) > 0 (Self-Harness"
                                  " §3.4) + E3: tercer split ciego siempre"
                                  " exigido, veta ante regresión"
                                  " (endurecimiento 28/9)"),
            "puerta_e3": resumen_config_e3(),
            "validador": "congelado (e47/e56, splits [0,1,2]/[3,4])",
            "evidencia_debilidades": self.minero.paquete_evidencia(),
            # Fase 2.6 (disparo continuo): cuántas trazas frescas trae la
            # ventana (N_m = 500 de referencia). Contexto auditado, no
            # insumo de la puerta (diseño §5).
            "contexto_disparo": contexto_disparo or {},
            "timestamp": time.time(),
        }
        d = os.path.dirname(os.path.abspath(self.db_path))
        pr_path = os.path.join(
            d, f"metaloop_preregistro_{int(time.time())}.json")
        with open(pr_path, "w", encoding="utf-8") as f:
            json.dump(prereg, f, indent=2, ensure_ascii=False)
        self._ledger_append({"tipo": "corrida_iniciada",
                             "preregistro": pr_path, **prereg})
        self._emitir_ciclo("metaloop_corrida_iniciada",
                           {"preregistro": pr_path, "seed": seed,
                            "rondas": rondas})

        estado = {"actual": dict(vigente)}
        estado["media_actual"], _ = self._evaluar(estado["actual"],
                                                 TRAIN_REPS, cache)
        keeps = []

        def producir():
            # producir: muta un parámetro del scaffold (EXP56 keep/revert)
            cand, clave = self._proponer(rng, estado["actual"])
            return {"candidato": cand, "clave": clave,
                    "prop": {"clave": clave,
                             "anterior": estado["actual"][clave],
                             "nuevo": cand[clave],
                             "descripcion": (f"{clave}:"
                                             f" {estado['actual'][clave]}"
                                             f" -> {cand[clave]}")}}

        def observar(prop):
            # observar: el validador congelado mide el candidato en train
            media_cand, _ = self._evaluar(prop["candidato"], TRAIN_REPS,
                                          cache)
            return {"media_cand": media_cand}

        def comparar(prop, obs):
            # comparar: mejora > 0 ssi el candidato baja el regret en
            # train. Greedy keep/revert (EXP56).
            delta_ronda = estado["media_actual"] - obs["media_cand"]
            return {"mejora": delta_ronda,
                    "aceptar": obs["media_cand"] < estado["media_actual"]}

        def on_paso(prop, obs, comp, paso):
            # Audit record por propuesta (Self-Harness §3.3): la
            # debilidad clusterizada es contexto DESCRIPTO — no dirige
            # la mutación (EXP58).
            keep = comp["aceptar"]
            delta_ronda = comp["mejora"]
            cand, clave = prop["candidato"], prop["clave"]
            if keep:
                keeps.append({"clave": clave,
                              "de": estado["actual"][clave],
                              "a": cand[clave],
                              "train_antes": estado["media_actual"],
                              "train_despues": obs["media_cand"]})
                estado["actual"] = cand
                estado["media_actual"] = obs["media_cand"]
            # si no mejora: revert implícito (no se adopta)
            ctx = self.minero.clusters(n=1)
            self._ledger_append(audit_record(
                propuesta=prop["prop"],
                delta_in=delta_ronda,
                delta_ho=None,
                aceptado=keep,
                motivo="keep en train" if keep else "revert en train",
                debilidad=ctx[0] if ctx else None,
                superficie="scaffold:" + clave,
                efecto_esperado="mejorar regret en train",
                riesgo_regresion="sobreajuste a train; lo decide la"
                                 " puerta de dos splits al final",
            ))
            self.minero.alimentar(firma_meta(
                clave, prop["prop"]["anterior"], prop["prop"]["nuevo"],
                "keep" if keep else "revert"))
            self._emitir_ciclo("metaloop_propuesta",
                               {"clave": clave,
                                "anterior": prop["prop"]["anterior"],
                                "nuevo": prop["prop"]["nuevo"],
                                "keep": bool(keep),
                                "delta_ronda": round(delta_ronda, 4)})

        # Cherny (e): producir → observar → comparar → parar. El criterio
        # se declaró antes del loop (pre-registro) y solo él para.
        LoopVerificacion(criterio_parada).correr(
            producir, observar, comparar, on_paso=on_paso)
        actual = estado["actual"]
        media_actual = estado["media_actual"]

        # Medición final en held-out que el loop nunca vio.
        # Adopción por puerta de dos splits (fase 2.1): exige no
        # regresión en train Y en held-out, con mejora estricta en al
        # menos uno. (delta_in ≥ 0 siempre por construcción greedy.)
        media_held, regs_held = self._evaluar(actual, HELDOUT_REPS, cache)
        puerta = PuertaDosSplits.decidir(
            media_train_base, base_actual, media_actual, media_held)
        # E3 (integración 28/9, decisión del usuario "hacelo";
        # endurecimiento 28/9: E3 SIEMPRE exigido, forzar_e3=True).
        # Nunca relaja la puerta (gate.py no se toca: núcleo protegido).
        e3 = self._puerta_e3(vigente, actual, cache, puerta)
        adoptado = e3["aceptado"]
        # Piso de ruido (cableado 11/10/2026, pre-registro
        # metaloop_preregistro_piso_ruido_puerta.json): la puerta pura y
        # el E3 deciden la ELEGIBILIDAD; la AUTO-ADOPCIÓN exige además
        # superar el piso de ruido (decidir_auto_adopcion, gate.py).
        # Solo endurece: lo que la puerta/E3 rechazan sigue rechazado.
        # Lo que cae en banda queda asentado con flag y solo se adopta
        # con el «sí» explícito del operador (camino manual existente).
        if adoptado:
            auto_ok, motivo_auto, requiere_si = decidir_auto_adopcion(
                e3["delta_in"], e3["delta_ho"])
        else:
            auto_ok, motivo_auto, requiere_si = (
                False, e3["motivo"], False)
        rec_e3 = audit_record_e3(
            propuesta={"clave": "scaffold_completo",
                       "anterior": vigente, "nuevo": actual,
                       "descripcion": "adopción del candidato final"},
            delta_in=e3["delta_in"], delta_ho=e3["delta_ho"],
            delta_e3=e3["delta_e3"],
            aceptado=adoptado, motivo=e3["motivo"],
            e3_exigido=e3["e3_exigido"], e3_evaluado=e3["e3_evaluado"],
            superficie="scaffold completo",
            efecto_esperado="mejorar el scaffold vigente",
        )
        # Bloque aditivo de la capa de auto-adopción (no cambia el
        # contrato de audit_record_e3: la puerta y el E3 ya hablaron).
        d_max = (max(e3["delta_in"], e3["delta_ho"])
                 if adoptado else None)
        rec_e3["auto_adopcion"] = {
            "auto_adoptado": bool(auto_ok),
            "motivo": motivo_auto,
            "requiere_si_explicito": bool(requiere_si),
            "piso_ruido_delta": PISO_RUIDO_DELTA,
            "sobre_piso_ruido": (
                d_max > PISO_RUIDO_DELTA if d_max is not None else None),
        }
        self._ledger_append(rec_e3)
        # La puerta evalúa, el archivo guarda: cada variante queda con sus
        # deltas medidos aunque se rechace (lección Darwin-Gödel Machine).
        self.archivo.guardar(rec_e3)
        if adoptado and requiere_si:
            # En banda: no se auto-adopta. Se asienta con el flag y se
            # avisa; el «sí» explícito corre por el camino manual.
            self._emitir_ciclo("metaloop_requiere_si",
                               {"delta_in": e3["delta_in"],
                                "delta_ho": e3["delta_ho"],
                                "motivo": motivo_auto,
                                "ledger": "ver audit_propuesta_e3 con"
                                          " auto_adopcion.requiere_si_"
                                          "explicito=true"})
        if adoptado and auto_ok:
            # Gobernanza 27/9 ~22:50 (decisión del usuario, refino "pero
            # no peor"): la fase 2.3 queda superada para el meta-loop.
            # El PASS de la puerta se AUTO-ADOPTA solo ante mejora medida
            # (Δ_ho > 0 estricto, Δ_in ≥ 0, frenos sanos); lo igual o peor
            # se registra como rechazo con números y no se adopta. El
            # núcleo protegido (presupuesto, puerta, notificaciones) hace
            # raise + log + aviso si se intenta tocar.
            try:
                adop = self.promotor.auto_adoptar(
                    scaffold_antes=vigente, scaffold_despues=actual,
                    delta_in=puerta["delta_in"],
                    delta_ho=puerta["delta_ho"],
                    motivo_puerta=puerta["motivo"], regla=puerta["regla"],
                    evidencia={
                        "seed": seed, "rondas": rondas,
                        "preregistro": pr_path,
                        "keeps": keeps,
                        "train_anterior": round(media_train_base, 4),
                        "train_candidato": round(media_actual, 4),
                        "heldout_anterior": round(base_actual, 4),
                        "heldout_candidato": round(media_held, 4),
                        "delta_e3": e3["delta_e3"],
                        "e3_exigido": e3["e3_exigido"],
                        "e3_evaluado": e3["e3_evaluado"],
                        "e3_reps": e3.get("e3_reps"),
                        "motivo_e3": e3["motivo"],
                        "origen": (f"metaloop_rso seed={seed}"
                                   f" rondas={rondas}"),
                    },
                    claves_permitidas=set(SPACES),
                    costo_usd=0.0,
                    presupuesto=self.presupuesto,
                    bucket=BUCKET_METALOOP)
            except NucleoProtegidoError as e:
                # El promotor ya hizo log + ledger + aviso; acá se deja
                # constancia en el ciclo y la corrida termina sin adoptar.
                self._ledger_append({"tipo": "metaloop_nucleo_bloqueado",
                                     "error": str(e)})
                self._emitir_ciclo("metaloop_nucleo_bloqueado",
                                   {"error": str(e)})
                adop = {"adoptada": False,
                        "motivo": f"núcleo protegido: {e}"}
            adopcion_id = adop.get("id") if adop.get("adoptada") else None
        else:
            adopcion_id = None
        self._emitir_ciclo("metaloop_puerta",
                           {"aceptado": bool(adoptado),
                            "delta_in": puerta["delta_in"],
                            "delta_ho": puerta["delta_ho"],
                            "motivo": puerta["motivo"],
                            "regla": puerta["regla"],
                            "e3_exigido": e3["e3_exigido"],
                            "e3_evaluado": e3["e3_evaluado"],
                            "delta_e3": e3["delta_e3"],
                            "motivo_e3": e3["motivo"]})
        self._ledger_append({
            "tipo": "corrida_finalizada",
            "puerta_pass": adoptado,
            "adopcion_id": adopcion_id,
            "auto_adopcion": bool(adopcion_id),
            "scaffold_anterior": vigente,
            "scaffold_candidato": actual,
            "keeps": keeps,
            "heldout_anterior": base_actual,
            "heldout_candidato": media_held,
            "heldout_regs": regs_held,
            "delta_train": puerta["delta_in"],
            "delta_heldout": puerta["delta_ho"],
            "regla_puerta": puerta["regla"],
            "motivo_puerta": puerta["motivo"],
            "e3_exigido": e3["e3_exigido"],
            "e3_evaluado": e3["e3_evaluado"],
            "delta_e3": e3["delta_e3"],
            "motivo_e3": e3["motivo"],
            "config_e3": resumen_config_e3(),
        })
        # Freno de estancamiento (idea 2): la corrida terminó; se registra
        # si hubo mejora medida (adopción) o fue plana.
        self.registrar_corrida(adoptado=bool(adopcion_id))
        with self._lock:
            self._estado = {
                "fase": "inactivo",
                "ultima_corrida": {
                    "seed": seed, "rondas": rondas,
                    "puerta_pass": adoptado,
                    "adopcion_id": adopcion_id,
                    "auto_adopcion": bool(adopcion_id),
                    "keeps": len(keeps),
                    "heldout_anterior": round(base_actual, 2),
                    "heldout_candidato": round(media_held, 2),
                    "delta_train": puerta["delta_in"],
                    "delta_heldout": puerta["delta_ho"],
                    "regla_puerta": puerta["regla"],
                    "motivo_puerta": puerta["motivo"],
                    "timestamp": time.time(),
                },
            }

    def revertir(self):
        """Rollback: vuelve al scaffold anterior al último adoptado."""
        hist = self.historial_scaffold(n=2)
        if len(hist) < 2:
            return {"revertido": False,
                    "motivo": "no hay scaffold anterior"}
        anterior = hist[1]["scaffold"]
        self._asentar_scaffold(anterior, origen="rollback_manual")
        self._ledger_append({"tipo": "rollback",
                             "restaurado": anterior})
        self._emitir_ciclo("metaloop_rollback",
                           {"restaurado": anterior})
        return {"revertido": True, "scaffold": anterior}

    def estado(self):
        with self._lock:
            est = dict(self._estado)
        est["scaffold_vigente"] = self.scaffold_vigente()
        est["ledger_eventos"] = len(self.ledger_leer())
        est["debilidades"] = self.minero.estado()
        est["freno_estancamiento"] = self.estado_freno()
        return est
