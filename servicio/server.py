"""Servidor HTTP del servicio ALMA (solo stdlib).

Endpoints:
  GET  /salud     → {"ok": true} (liveness)
  GET  /estado    → estadísticas del motor y la memoria
  POST /resolver  → {"texto": str, "clase"?: str, "esperado"?: str,
                      "modo"?: "thompson"|"probe",
                      "horizonte"?: "corto"|"largo"|"auto",
                      "umbral_ruido"?: float}
  POST /feedback  → {"experiencia_id": int, "reward": 0..1, "nota"?: str}
  GET  /drift/estado   → escanea trazas y devuelve el estado del detector
                          de drift en vivo (fase 2.5, observabilidad)
  POST /drift/escanear → fuerza un escaneo de trazas nuevas (crons)
  POST /drift/anclar   → {"ganador"?: str} re-ancla el baseline de drift

Variables de entorno:
  ALMA_PORT     puerto (default 8471)
  ALMA_DB       ruta SQLite (default ~/workspace/alma-prototype/alma_store.db)
  ALMA_BACKEND  demo | vault | openai (default demo; demo NO gasta API key)
"""

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor import Motor
from ingles import Ingles

# -- fase 2 (diseño §3 y §4) -------------------------------------------------
# Meta-loop RSO, benchmark propio, revisión de background y Curator viven
# acá como singletons del servicio. Todo corre en background o a pedido:
# nada de esto toca el camino crítico de /resolver.
from alma_service.metaloop import MetaLoop
from alma_service.benchmark import Benchmark
from alma_service.curator import Curator, consolidar_llm
from alma_service.politicas import PuertaPoliticas  # Song (g): puerta
from alma_service.procedencia import ProcedenciaSkills  # Song (h)
from alma_service.skills import SkillIndex

# -- fase 2.1 (integracion_fase21/DISENO.md) ---------------------------------
# Puerta de dos splits + minería de debilidades (Self-Harness), ciclo de
# confianza provisional→trusted + versionado FIX/DERIVED/CAPTURED +
# pipeline de admisión (OpenSpace). Todo determinista, US$0, sin LLM.
# Aditivo: no toca el camino crítico de /resolver ni los singletons
# existentes.
from alma_service.confianza import ConfianzaSkills
from alma_service.versiones import VersionadorSkills
from alma_service.admision import PipelineAdmision

# -- gobernanza: auto-adopción (decisión del usuario, 27/9 ~22:50) -----
# La fase 2.3 queda SUPERADA para el meta-loop: un PASS de la puerta se
# auto-adopta solo ante mejora medida ("pero no peor": Δ_ho > 0, Δ_in ≥ 0,
# frenos sanos). El núcleo protegido (presupuesto, puerta, notificaciones)
# está fuera de su alcance. El camino manual proponer/aprobar sigue
# existiendo; cada auto-adopción se notifica al usuario.
from alma_service.promotor import APROBADORES as APROBADORES_PROMOCION
# -- E3: tercer split ciego (integración 28/9, decisión del usuario) -----
from alma_service.puerta_e3 import resumen_config_e3

# -- fase 2.6: disparo continuo (benchmark cada N_b=100 trazas con reward;
# meta-loop con trigger semanal + no-regresión). Diseño aprobado 28/9.
# El trigger vive ACÁ, fuera del loop: el loop no se auto-dispara ni se
# auto-modifica (anti-DGM). El cron semanal queda como backstop.
from alma_service.disparo import DisparoContinuo

PUERTO = int(os.environ.get("ALMA_PORT", "8471"))
DB = os.path.expanduser(os.environ.get(
    "ALMA_DB", "~/workspace/alma-prototype/alma_store.db"))

motor = Motor(DB)
ingles = Ingles(DB)

_DB_DIR = os.path.dirname(os.path.abspath(DB))
metaloop = MetaLoop(DB)
benchmark = Benchmark(DB, presupuesto=motor.presupuesto,
                      obtener_scaffold_vigente=metaloop.scaffold_vigente)
_skill_index = SkillIndex(os.path.join(_DB_DIR, "skills-indice.db"))
curator = Curator(_skill_index,
                  ledger_path=os.path.join(_DB_DIR, "curator-ledger.jsonl"))
# Fase 2.1: confianza (ortogonal a active/stale/archived), versionado y
# admisión. Las skills admitidas nacen provisionales; el trust se gana
# con uso (confianza.py). Todo auditable en el ledger del Curator.
confianza_skills = ConfianzaSkills(
    os.path.join(_DB_DIR, "skills-confianza.db"))
versionador_skills = VersionadorSkills(
    os.path.join(_DB_DIR, "skills-versiones.db"), skill_index=_skill_index)
# Song (g): puerta determinística de políticas — allowlist sobre las
# herramientas que una skill declara; default-deny. (h): procedencia de
# skills admitidas (propio/tercero/importado + cuarentena).
puerta_politicas = PuertaPoliticas(
    {"skills": os.path.join(_DB_DIR, "skills"), "workspace": _DB_DIR},
    ledger_path=os.path.join(_DB_DIR, "politica-ledger.jsonl"))
procedencia_skills = ProcedenciaSkills(
    os.path.join(_DB_DIR, "skills-confianza.db"))
admision_skills = PipelineAdmision(
    os.path.join(_DB_DIR, "skills-admision.db"),
    skills_dir=os.path.join(_DB_DIR, "skills"),
    skill_index=_skill_index,
    confianza=confianza_skills,
    versionador=versionador_skills,
    registrar_ledger=curator.ledger.append,
    puerta=puerta_politicas,
    procedencia=procedencia_skills)

# -- fase 2.2: trazas unificadas (DISENO_PAQUETE_UNICO.md §5) ---------------
# UN event log estructurado del servicio: cada decisión del resolver, cada
# probe con su veredicto, cada costo/latencia, cada evento del ciclo
# (meta-loop, Curator, revisión). El minero (debilidades.py) lo lee para
# minar firmas sobre operación real. Aditivo y fail-safe: si el log
# falla, ningún camino crítico se rompe.
from alma_service.trazas import EventLog
event_log = EventLog(os.path.join(_DB_DIR, "alma_eventos.db"))
motor.trazas = event_log
motor.version_scaffold_fn = metaloop.scaffold_vigente
motor.revision_bg.event_log = event_log
metaloop.event_log = event_log
curator.event_log = event_log

# -- fase 2.6: disparo continuo --------------------------------------------
# Loop A: notificar() es el chequeo barato al asentar cada decisión
# (compara MAX(id) con reward contra el watermark); al cruzar N_b=100
# trazas evalúa el benchmark en background. Solo mide.
# Loop B: el endpoint /fase2/metaloop/correr consulta evaluar_loop_b()
# antes de lanzar (techo semanal + no-regresión + ventana fresca).
disparo = DisparoContinuo(DB, event_log=event_log, benchmark=benchmark,
                          metaloop=metaloop)
event_log.on_decision = disparo.notificar

# -- fase 2.5: drift en vivo (observabilidad, no política) ----------------
# MonitorDriftVivo: corre el DetectorDrift (fase 2.5, mock validado)
# sobre los veredictos de probe MEDIDOS del event log y, ante un
# cambio de régimen, REGISTRA el evento (drift-ledger.jsonl + evento
# de ciclo) y lo EXPONE (GET /drift/estado). Solo LEE trazas y escribe
# su propio ledger: no toca resolver, presupuesto ni topes. La
# notificación al usuario la maneja la capa de crons/chat; este
# cableado es infraestructura de observabilidad.
# Fail-safe: si la construcción falla, queda None y el servicio sigue
# igual (mismo patrón que el detector de heterogeneidad).
from alma_service.drift_vivo import MonitorDriftVivo
monitor_drift = None
try:
    if os.environ.get("ALMA_DRIFT_VIVO", "1") == "1":
        monitor_drift = MonitorDriftVivo(event_log, dir_base=_DB_DIR)
except Exception:
    monitor_drift = None


class Manejador(BaseHTTPRequestHandler):
    server_version = "ALMA-servicio/2.0"

    def _json(self, codigo, obj):
        cuerpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _leer_cuerpo(self):
        largo = int(self.headers.get("Content-Length", 0) or 0)
        if largo <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(largo).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ValueError("cuerpo no es JSON válido")

    def log_message(self, fmt, *args):
        # Log mínimo sin contenido sensible: método + ruta + código.
        sys.stderr.write(f"[http] {self.command} {self.path} -> {args[1]}\n")

    def do_GET(self):
        try:
            if self.path == "/salud":
                self._json(200, {"ok": True})
            elif self.path == "/estado":
                self._json(200, motor.estado())
            elif self.path == "/ingles/estado":
                self._json(200, ingles.estado())
            elif self.path == "/fase2/estado":
                self._json(200, {
                    "presupuesto": motor.presupuesto.estado(),
                    "backend_efectivo_barato":
                        motor._es_modo_barato_efectivo(),
                    "scaffold_vigente": metaloop.scaffold_vigente(),
                    "metaloop": metaloop.estado(),
                    "benchmark": benchmark.estado(),
                    "revision_bg": motor.revision_bg.estado(),
                    "curator_llm_opt_in":
                        os.environ.get("ALMA_CURATOR_LLM", "0") == "1",
                    # Fase 2.1: Self-Harness + OpenSpace (todo US$0).
                    "fase21": {
                        "puerta_dos_splits":
                            (metaloop.estado().get("ultima_corrida")
                             or {}).get("regla_puerta"),
                        "debilidades": metaloop.estado().get(
                            "debilidades"),
                        "confianza_skills": confianza_skills.resumen(),
                        "admision_pendientes": len(
                            admision_skills.pendientes()),
                        # Fase 2.1 §2: tres maestros (Song/Cherny/Yao).
                        "puerta_politicas":
                            list(puerta_politicas.politica_actual()),
                        "politica_pendientes": len(
                            puerta_politicas.pendientes()),
                    },
                    # Fase 2.2: trazas unificadas (event log del servicio).
                    "fase22": {
                        "trazas": event_log.estado(),
                    },
                    # Fase 2.6: disparo continuo (benchmark por trazas +
                    # trigger semanal del meta-loop con no-regresión).
                    "fase26": {
                        "disparo": disparo.estado(),
                    },
                    # Fase 2.5: drift en vivo (observabilidad). El monitor
                    # solo informa; no escanea acá para no encarecer
                    # /estado (el escaneo lo dispara /drift/estado o
                    # /drift/escanear).
                    "fase25": ({
                        "drift": monitor_drift.estado(),
                    } if monitor_drift is not None else {
                        "drift": {"activo": False,
                                  "motivo": "monitor desactivado"},
                    }),
                    # Fase 2.3: promotor (camino manual: staging + freno
                    # humano). Gobernanza 27/9 ~22:50: el meta-loop ya no
                    # usa este camino — auto-adopta mejoras medidas.
                    "fase23": {
                        "aprobadores": list(APROBADORES_PROMOCION),
                        "promocion_pendiente":
                            metaloop.promotor.pendiente(),
                        "historial_promociones":
                            metaloop.promotor.historial(n=5),
                    },
                    # Gobernanza 27/9 ~22:50: auto-adopción ante mejora
                    # medida ("pero no peor"), reversible y notificada.
                    # E3 28/9: tercer split ciego que endurece la puerta.
                    "gobernanza": {
                        "adopciones_recientes":
                            metaloop.promotor.adopciones_recientes(n=5),
                        "notificaciones_pendientes":
                            metaloop.promotor.notificaciones_pendientes(),
                        "e3": resumen_config_e3(),
                    },
                })
            elif self.path == "/fase2/revision/pendientes":
                self._json(200,
                           {"pendientes":
                            motor.revision_bg.pendientes()})
            elif self.path == "/fase2/promocion/pendiente":
                # Staging inspeccionable: qué cambia (diff), qué Δ la
                # justifica, en qué splits pasó (evidencia).
                self._json(200, {
                    "pendiente": metaloop.promotor.pendiente(),
                    "aprobadores": list(APROBADORES_PROMOCION),
                })
            elif self.path == "/fase2/disparo/estado":
                # Fase 2.6: estado del trigger por trazas (watermarks,
                # evaluación del loop B, serie de reward real).
                self._json(200, disparo.estado())
            elif self.path == "/drift/estado":
                # Fase 2.5: escanea trazas nuevas y devuelve el estado
                # del detector de drift (observabilidad solamente).
                if monitor_drift is None:
                    self._json(200, {"activo": False,
                                     "motivo": "monitor desactivado"})
                else:
                    self._json(200, monitor_drift.estado_vivo())
            else:
                self._json(404, {"error": "ruta desconocida"})
        except Exception as e:  # noqa: BLE001 - el servidor no debe caerse
            traceback.print_exc()
            self._json(500, {"error": str(e)[:300]})

    def do_POST(self):
        try:
            datos = self._leer_cuerpo()
            if self.path == "/resolver":
                if not datos.get("texto"):
                    self._json(400, {"error": "falta 'texto'"})
                    return
                res = motor.resolver(
                    texto=datos["texto"],
                    clase=datos.get("clase"),
                    esperado=datos.get("esperado"),
                    modo=datos.get("modo", "thompson"),
                    horizonte=datos.get("horizonte", "auto"),
                    umbral_ruido=datos.get("umbral_ruido"),
                )
                self._json(200, res)
            elif self.path == "/feedback":
                if datos.get("experiencia_id") is None or datos.get("reward") is None:
                    self._json(400, {"error": "faltan 'experiencia_id' y 'reward'"})
                    return
                res = motor.feedback(
                    datos["experiencia_id"], datos["reward"],
                    datos.get("nota", ""))
                self._json(200, res)
            elif self.path == "/ingles/recomendar":
                self._json(200, ingles.recomendar())
            elif self.path == "/ingles/puntuar":
                if not datos.get("metodo_id") or datos.get("puntaje") is None:
                    self._json(400, {"error": "faltan 'metodo_id' y 'puntaje' (1-5)"})
                    return
                res = ingles.puntuar(
                    datos["metodo_id"], datos["puntaje"],
                    datos.get("nota", ""))
                self._json(200, res)
            elif self.path == "/fase2/metaloop/correr":
                # Fase 2.6: el disparo evalúa debe_correr() antes de
                # lanzar — techo semanal + no-regresión del benchmark +
                # ventana fresca (N_m=500 de referencia). Si dice que no,
                # la corrida no arranca (el cron semanal queda como
                # backstop: este mismo chequeo lo deja pasar cuando toca).
                dec = disparo.evaluar_loop_b()
                if not dec["debe"]:
                    disparo.avisar_bloqueo(dec)
                    self._json(200, {"aceptado": False,
                                     "motivo": dec["motivo"],
                                     "disparo": dec})
                    return
                contexto = {"nuevas_trazas": dec["nuevas_trazas"],
                            "n_m_referencia": dec["n_m"],
                            "dias_desde_ultima": dec["dias_desde_ultima"]}
                res = metaloop.correr(
                    seed=datos.get("seed"),
                    rondas=datos.get("rondas"),
                    contexto_disparo=contexto)
                if res.get("aceptado"):
                    # Watermark del loop B solo si la corrida arrancó.
                    wm = disparo.marcar_corrida_metaloop()
                    res["disparo"] = dec
                    res["contexto_disparo"] = wm
                self._json(200, res)
            elif self.path == "/fase2/metaloop/revertir":
                self._json(200, metaloop.revertir())
            elif self.path == "/fase2/benchmark/correr":
                self._json(200, benchmark.correr())
            elif self.path == "/fase2/revision/aprobar":
                if datos.get("id") is None:
                    self._json(400, {"error": "falta 'id'"})
                    return
                self._json(200, motor.revision_bg.aprobar(datos["id"]))
            elif self.path == "/fase2/revision/rechazar":
                if datos.get("id") is None:
                    self._json(400, {"error": "falta 'id'"})
                    return
                self._json(200, motor.revision_bg.rechazar(datos["id"]))
            elif self.path == "/fase2/promocion/aprobar":
                # Camino manual (fase 2.3): commit de una promoción en
                # staging con un aprobador de la allowlist ("humano",).
                # El meta-loop ya no usa este camino: auto-adopta mejoras
                # medidas (gobernanza 27/9 ~22:50).
                if datos.get("id") is None:
                    self._json(400, {"error": "falta 'id'"})
                    return
                self._json(200, metaloop.promotor.aprobar(
                    datos["id"],
                    aprobador=datos.get("aprobador", "humano")))
            elif self.path == "/fase2/promocion/rechazar":
                if datos.get("id") is None:
                    self._json(400, {"error": "falta 'id'"})
                    return
                if not (datos.get("motivo") or "").strip():
                    self._json(400, {"error": "falta 'motivo'"})
                    return
                self._json(200, metaloop.promotor.rechazar(
                    datos["id"], datos["motivo"],
                    aprobador=datos.get("aprobador", "humano")))
            elif self.path == "/fase2/curator/ciclo":
                # Barrido determinista (diseño §1.1.2). La consolidación
                # LLM NO corre acá: es opt-in apagada por default.
                self._json(200, {"transiciones": curator.correr_ciclo()})
            elif self.path == "/fase2/torneo/semanal":
                # EXP78 (Forge #3, cableado aprobado 1/10): torneo
                # campeón vs candidatas acumuladas con el validador
                # congelado. No bloquea el handler: corre en background
                # y el resultado queda en alma_torneo.db (+ traza
                # unificada origen="torneo"). Lo invoca el cron semanal.
                from alma_service.cableado_forge import (
                    correr_torneo_semanal)
                self._json(200, correr_torneo_semanal(
                    metaloop, getattr(metaloop, "promotor", None),
                    bloqueante=False))
            elif self.path == "/drift/escanear":
                # Fase 2.5: fuerza un escaneo de trazas nuevas (lo usa
                # la capa de crons; /drift/estado también escanea).
                if monitor_drift is None:
                    self._json(200, {"activo": False,
                                     "motivo": "monitor desactivado"})
                else:
                    self._json(200, monitor_drift.escanear())
            elif self.path == "/drift/anclar":
                # Fase 2.5: re-anclaje explícito del baseline tras un
                # drift (libera la señal enclavada). "ganador"
                # opcional: sin él se re-ancla con el último veredicto
                # medido observado.
                if monitor_drift is None:
                    self._json(200, {"ok": False,
                                     "motivo": "monitor desactivado"})
                else:
                    self._json(200, monitor_drift.anclar(
                        ganador=datos.get("ganador")))
            else:
                self._json(404, {"error": "ruta desconocida"})
        except (ValueError, KeyError) as e:
            self._json(400, {"error": str(e)[:300]})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._json(500, {"error": str(e)[:300]})


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    print(f"[servicio] ALMA v2 en http://127.0.0.1:{PUERTO} "
          f"(db={DB}, backend={motor.backend_kind})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
