"""Disparo del ciclo de mejora por trazas — benchmark continuo (fase 2.6).

Diseño aprobado por el usuario el 28/9
(integracion_fase21/DISENO_BENCHMARK_CONTINUO.md):

- Loop A — Benchmark continuo: cada N_b = 100 trazas de decisión nuevas
  CON reward medido, corre el benchmark (vigente vs baseline, ~0,3 s) y
  asienta la media de reward real de la ventana en la serie
  `benchmark_recompensa_real`. Solo mide; no propone, no adopta, no toca
  el scaffold.
- Loop B — Meta-loop: corre como máximo 1 vez cada 7 días (techo = piso =
  semanal, igual que hoy). El disparo lo evalúa `debe_correr()`: techo de
  cadencia + condición de no-regresión del benchmark + ventana fresca de
  referencia N_m = 500 trazas. El cron semanal (alma-fase2-semanal) queda
  como backstop.

Definiciones (diseño §6, §10.6):
- "traza con reward medido" = fila de `eventos_decision` con
  `reward IS NOT NULL` (incluye rewards completados a posteriori vía
  feedback/actualizar_reward). Si esta definición cambia, el watermark se
  mueve: documentarlo acá.
- "trazas nuevas" = MAX(id) con reward medido − watermark registrado en
  la última corrida. El watermark vive en la DB del meta-loop, aditivo
  (tabla nueva, sin tocar tablas existentes).

Gobernanza (líneas rojas, diseño §2):
- El trigger vive FUERA del loop (código nuestro, determinista): el loop
  no se auto-dispara ni se auto-modifica (anti-DGM).
- Topes de gasto y obligación de notificar: intactos.
- Auto-adopción solo ante mejora medida: este módulo no adopta nada.

US$0: todo mock local (mundo/validador congelados); el presupuesto
autoriza costo 0 como en el resto de la fase 2.
"""

import json
import os
import sqlite3
import threading
import time

# -- constantes aprobadas (diseño §9.4) ------------------------------------
N_B = 100          # loop A: benchmark cada 100 trazas con reward medido
N_M = 500          # loop B: ventana de referencia de trazas frescas
PISO_DIAS = 7.0    # piso semanal: con tráfico ralo corre igual
TECHO_DIAS = 7.0   # techo semanal: nunca más de 1 corrida / 7 días
# Diseño §8.2: si el benchmark posterior a la última adopción muestra
# mejora < −2·SE (SE ≈ s/√5 ≈ 1,4 con s=3,2 → umbral ≈ −2,8), la próxima
# corrida se bloquea y se avisa.
UMBRAL_REGRESION = -2.8

WM_BENCHMARK = "benchmark"   # loop A
WM_METALOOP = "metaloop"     # loop B


def debe_correr(nuevas_trazas, dias_desde_ultima, benchmark_ok):
    """Criterio exacto de disparo del meta-loop (diseño §6, verbatim).

    dias_desde_ultima=None significa "nunca corrió" (piso satisfecho).
    Retorna (debe: bool, motivo: str).
    """
    dias = (float("inf") if dias_desde_ultima is None
            else float(dias_desde_ultima))
    # N_m = 500 · piso = 7 días · techo = 7 días · benchmark_ok = la
    # última adopción no muestra regresión en el benchmark posterior
    if dias < TECHO_DIAS:
        return (False, "techo de cadencia: mínimo 7 días entre corridas")
    if not benchmark_ok:
        return (False, "el benchmark posterior a la última adopción "
                       "muestra regresión: se bloquea y se avisa")
    if nuevas_trazas >= N_M:
        return (True, "ventana fresca completa: ≥500 trazas nuevas")
    return (True, "piso semanal: 7 días sin corrida (tráfico ralo)")


class DisparoContinuo:
    """Trigger por trazas del ciclo de mejora. Determinista, fail-safe.

    - Loop A: `notificar()` es el chequeo barato que corre al asentar cada
      decisión (lo cablea server.py vía event_log.on_decision). Cuando se
      cruza el borde de N_B trazas con reward, evalúa en background.
    - Loop B: `evaluar_loop_b()` implementa debe_correr(); el endpoint
      /fase2/metaloop/correr lo consulta antes de lanzar.
    """

    def __init__(self, db_path, event_log=None, benchmark=None,
                 metaloop=None, n_b=None):
        # El watermark vive en la DB del meta-loop (diseño §6). Si se pasa
        # un metaloop, su DB manda; si no, la db_path recibida.
        self.db_path = (metaloop.db_path if metaloop is not None
                        else db_path)
        self.event_log = event_log
        self.benchmark = benchmark
        self.metaloop = metaloop
        self.n_b = int(n_b) if n_b is not None else N_B
        self._lock = threading.Lock()
        self._loop_a_en_curso = False
        self._hilo_a = None
        self._init_db()

    # -- persistencia (aditiva: tablas nuevas, nada existente se toca) ----
    def _con(self):
        con = sqlite3.connect(self.db_path, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init_db(self):
        with self._con() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS disparo_watermark (
                       clave TEXT PRIMARY KEY,
                       traza_id INTEGER NOT NULL,
                       ts REAL NOT NULL
                   )""")
            con.execute(
                """CREATE TABLE IF NOT EXISTS benchmark_recompensa_real (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       timestamp REAL NOT NULL,
                       desde_id INTEGER NOT NULL,
                       hasta_id INTEGER NOT NULL,
                       n INTEGER NOT NULL,
                       media REAL,
                       scaffold_json TEXT NOT NULL DEFAULT '{}'
                   )""")

    def _watermark(self, clave):
        with self._con() as con:
            fila = con.execute(
                "SELECT traza_id FROM disparo_watermark WHERE clave=?",
                (clave,)).fetchone()
        return int(fila[0]) if fila else 0

    def _fijar_watermark(self, clave, traza_id):
        with self._con() as con:
            con.execute(
                "INSERT INTO disparo_watermark (clave, traza_id, ts)"
                " VALUES (?, ?, ?)"
                " ON CONFLICT(clave) DO UPDATE SET traza_id=excluded.traza_id,"
                " ts=excluded.ts",
                (str(clave), int(traza_id), time.time()))

    # -- loop A: chequeo barato + evaluación --------------------------------
    def _max_id_con_reward(self):
        """MAX(id) de eventos_decision con reward medido (diseño §6)."""
        if self.event_log is None:
            return 0
        try:
            with sqlite3.connect(self.event_log.db_path) as con:
                fila = con.execute(
                    "SELECT MAX(id) FROM eventos_decision"
                    " WHERE reward IS NOT NULL").fetchone()
            return int(fila[0]) if fila and fila[0] is not None else 0
        except Exception:
            return 0

    def notificar(self):
        """Chequeo barato al asentar cada decisión (diseño §6).

        Callback para event_log.on_decision. Nunca bloquea ni rompe el
        camino crítico: el trabajo pesado va a un hilo de fondo.
        """
        try:
            if self.benchmark is None or self.event_log is None:
                return
            max_id = self._max_id_con_reward()
            with self._lock:
                if self._loop_a_en_curso:
                    return
                if max_id - self._watermark(WM_BENCHMARK) < self.n_b:
                    return
                self._loop_a_en_curso = True
            t = threading.Thread(target=self._evaluar_loop_a,
                                 args=(max_id,), daemon=True)
            self._hilo_a = t
            t.start()
        except Exception:
            pass  # fail-safe: el log nunca rompe la resolución

    def _evaluar_loop_a(self, hasta_id):
        """Benchmark + serie de reward real de la ventana. Solo mide."""
        try:
            desde_id = self._watermark(WM_BENCHMARK)
            res = self.benchmark.correr(bloqueante=True)
            if not res.get("aceptado"):
                return  # sin benchmark no se avanza el watermark
            # Media de reward real de la ventana (monitoreo del vigente
            # en producción, no comparación contra baseline: sin
            # contrafactuales, diseño §3).
            ventana = [d for d in self.event_log.decisiones(
                           con_reward=True, limite=1000000)
                       if desde_id < d["id"] <= hasta_id]
            n = len(ventana)
            media = (sum(d["reward"] for d in ventana) / n
                     if n else None)
            scaffold = (self.metaloop.scaffold_vigente()
                        if self.metaloop is not None else {})
            with self._con() as con:
                con.execute(
                    "INSERT INTO benchmark_recompensa_real"
                    " (timestamp, desde_id, hasta_id, n, media,"
                    "  scaffold_json)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (time.time(), desde_id, hasta_id, n, media,
                     json.dumps(scaffold or {}, ensure_ascii=False,
                                sort_keys=True)))
            self._fijar_watermark(WM_BENCHMARK, hasta_id)
            self._emitir_ciclo("disparo_loop_a",
                               {"desde_id": desde_id, "hasta_id": hasta_id,
                                "n": n, "media_reward_real": media,
                                "mejora_benchmark":
                                    (res.get("resultado") or {}).get(
                                        "mejora")})
        except Exception as e:  # noqa: BLE001
            self._emitir_ciclo("disparo_loop_a_error",
                               {"error": str(e)[:200]})
        finally:
            with self._lock:
                self._loop_a_en_curso = False

    def esperar_loop_a(self, timeout=60.0):
        """Espera a que termine una evaluación del loop A (tests)."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self._lock:
                hilo, en_curso = self._hilo_a, self._loop_a_en_curso
            if not en_curso and (hilo is None or not hilo.is_alive()):
                return True
            time.sleep(0.05)
        return False

    def serie_recompensa_real(self, n=20):
        """Serie de monitoreo del vigente en producción (diseño §5).

        Hasta calibrar el umbral con las primeras 500 trazas reales, la
        serie solo se registra (no dispara alertas): el σ del reward real
        es desconocido.
        """
        with self._con() as con:
            filas = con.execute(
                "SELECT id, timestamp, desde_id, hasta_id, n, media"
                " FROM benchmark_recompensa_real"
                " ORDER BY id DESC LIMIT ?", (int(n),)).fetchall()
        return [{"id": f[0], "timestamp": f[1], "desde_id": f[2],
                 "hasta_id": f[3], "n": f[4], "media": f[5]}
                for f in reversed(filas)]

    # -- loop B: trigger semanal + no-regresión ------------------------------
    def _dias_desde_ultima_corrida(self):
        """Días desde la última corrida_finalizada del ledger. None si
        nunca corrió (piso satisfecho)."""
        if self.metaloop is None:
            return None
        ultimo = None
        try:
            for e in self.metaloop.ledger_leer():
                ev = e.get("evento", {})
                if ev.get("tipo") == "corrida_finalizada":
                    ts = ev.get("timestamp")
                    if ts is not None and (ultimo is None or ts > ultimo):
                        ultimo = ts
        except Exception:
            return None
        if ultimo is None:
            return None
        return (time.time() - float(ultimo)) / 86400.0

    def _benchmark_ok(self):
        """True salvo que el benchmark posterior a la última adopción
        muestre regresión (mejora < UMBRAL_REGRESION, diseño §8.2).

        Sin adopciones: True. Con adopción pero sin benchmark posterior:
        True (nada que juzgar).
        """
        if self.metaloop is None or self.benchmark is None:
            return True, {"motivo": "sin metaloop/benchmark cableados"}
        try:
            with self._con() as con:
                fila = con.execute(
                    "SELECT MAX(ts) FROM adopciones"
                    " WHERE modo='auto' AND estado='adoptada'").fetchone()
        except Exception:
            return True, {"motivo": "tabla adopciones ausente"}
        ts_adop = fila[0] if fila and fila[0] is not None else None
        if ts_adop is None:
            return True, {"adopciones": 0}
        try:
            bdb = self.benchmark.db_path
            with sqlite3.connect(bdb) as con:
                filas = con.execute(
                    "SELECT id, timestamp, mejora FROM benchmark_corridas"
                    " WHERE timestamp > ? ORDER BY id",
                    (float(ts_adop),)).fetchall()
        except Exception:
            return True, {"motivo": "benchmark_corridas ausente"}
        regres = [{"id": f[0], "timestamp": f[1], "mejora": f[2]}
                  for f in filas if f[2] is not None
                  and float(f[2]) < UMBRAL_REGRESION]
        return (len(regres) == 0,
                {"ultima_adopcion_ts": ts_adop,
                 "benchmarks_posteriores": len(filas),
                 "regresiones": regres,
                 "umbral_regresion": UMBRAL_REGRESION})

    def evaluar_loop_b(self):
        """Evalúa debe_correr() con el estado real. Lo consulta el
        endpoint /fase2/metaloop/correr antes de lanzar."""
        nuevas = self._max_id_con_reward() - self._watermark(WM_METALOOP)
        dias = self._dias_desde_ultima_corrida()
        ok, detalle = self._benchmark_ok()
        debe, motivo = debe_correr(max(0, nuevas), dias, ok)
        return {"debe": debe, "motivo": motivo,
                "nuevas_trazas": max(0, nuevas),
                "dias_desde_ultima": dias,
                "benchmark_ok": ok, "detalle_benchmark": detalle,
                "n_m": N_M, "piso_dias": PISO_DIAS, "techo_dias": TECHO_DIAS}

    def marcar_corrida_metaloop(self):
        """Registra el watermark del loop B al aceptar una corrida.

        Retorna el contexto que va al pre-registro (diseño §5: cuántas
        trazas frescas trae la ventana).
        """
        max_id = self._max_id_con_reward()
        nuevas = max(0, max_id - self._watermark(WM_METALOOP))
        self._fijar_watermark(WM_METALOOP, max_id)
        contexto = {"nuevas_trazas": nuevas,
                    "watermark_metaloop": max_id,
                    "n_m_referencia": N_M,
                    "definicion_trazas":
                        "MAX(id) de eventos_decision con reward IS NOT"
                        " NULL menos watermark"}
        self._emitir_ciclo("disparo_metaloop", contexto)
        return contexto

    def avisar_bloqueo(self, decision):
        """Emite el aviso cuando el disparo bloquea por regresión
        (diseño §6: 'se bloquea y se avisa'). El techo de cadencia es
        rutina y no avisa."""
        if not decision.get("benchmark_ok", True):
            self._emitir_ciclo(
                "disparo_bloqueo_regresion",
                {"motivo": decision.get("motivo"),
                 "detalle_benchmark":
                     decision.get("detalle_benchmark", {})})

    # -- observabilidad ------------------------------------------------------
    def _emitir_ciclo(self, tipo, detalle):
        if self.event_log is not None:
            try:
                self.event_log.asentar_ciclo(tipo=tipo, actor="disparo",
                                             detalle=detalle)
            except Exception:
                pass

    def estado(self):
        ev = self.evaluar_loop_b()
        with self._lock:
            en_curso = self._loop_a_en_curso
        return {"n_b": self.n_b, "n_m": N_M,
                "piso_dias": PISO_DIAS, "techo_dias": TECHO_DIAS,
                "umbral_regresion": UMBRAL_REGRESION,
                "watermark_benchmark": self._watermark(WM_BENCHMARK),
                "watermark_metaloop": self._watermark(WM_METALOOP),
                "loop_a_en_curso": en_curso,
                "loop_b": ev,
                "serie_recompensa_real": self.serie_recompensa_real(n=5)}
