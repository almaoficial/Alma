"""Tests fase 2.5 (vivo): drift cableado al servicio real (US$0).

Verifica el cableado de verdad (no el detector puro, que ya cubre
test_fase25_drift.py):

1. MonitorDriftVivo corre sobre las trazas del servicio: lee los
   veredictos de probe MEDIDOS del event log (fase 2.2), ancla el
   baseline con el primero y alimenta la ventana.
2. Ante un flip del mundo (contradicciones al baseline), el evento de
   drift se REGISTRA: entrada en drift-ledger.jsonl + evento de ciclo
   "drift_detectado" en el event log.
3. Empates (gap <= 0) y decisiones sin probe no alimentan (convención
   EXP68: sin veredicto estricto no hay veredicto).
4. La señal se enclava hasta el re-anclaje explícito.
5. Fail-safe: si las trazas fallan, el monitor se desactiva y no
   rompe nada.
6. End-to-end HTTP contra server.py real (puerto efímero, DB
   temporal): /salud sigue respondiendo, /drift/estado expone el
   drift, /drift/escanear y /drift/anclar funcionan, /fase2/estado
   trae el bloque fase25, y /resolver no se alteró.

Sin key, sin red externa, sin LLM. El backend del servidor de prueba
es demo.

Correr: python3 test_fase25_drift_vivo.py
"""

import importlib.util
import json
import os
import sys
import tempfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.drift_vivo import MonitorDriftVivo
from alma_service.trazas import EventLog

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def nuevo_log(tmp):
    return EventLog(db_path=os.path.join(tmp, "eventos.db"))


def decision_probe(log, ganador, gap=0.5, firma="calculo"):
    """Asienta una decisión modo probe con la forma exacta que escribe
    el motor vivo (_asentar_traza): veredicto_probe + extras.gap."""
    return log.asentar_decision(
        firma_regimen=firma, brazo_elegido=ganador, reward=1.0,
        veredicto_probe=ganador, modo="probe",
        extras={"gap": gap, "compromiso": "duro"})


def monitor_fresco(tmp):
    log = nuevo_log(tmp)
    mon = MonitorDriftVivo(log, dir_base=tmp)
    return log, mon


# -- 1-5: el monitor sobre trazas ------------------------------------------


def test_ancla_con_primer_veredicto():
    tmp = tempfile.mkdtemp()
    log, mon = monitor_fresco(tmp)
    decision_probe(log, "single")
    decision_probe(log, "single")
    r = mon.escanear()
    check("escaneo activo", r["activo"] is True)
    check("2 veredictos nuevos leídos", r["veredictos_nuevos"] == 2)
    est = mon.estado()
    check("baseline anclada con el primero",
          est["anclado"] and est["detector"]["baseline"] == "single")
    check("sin drift en mundo estable",
          not est["detector"]["drift"])


def test_sin_probe_no_hay_baseline():
    """Fail-closed: sin veredictos medidos no hay baseline ni señal."""
    tmp = tempfile.mkdtemp()
    log, mon = monitor_fresco(tmp)
    log.asentar_decision(firma_regimen="calculo", brazo_elegido="cot",
                         reward=None, modo="thompson")  # sin probe
    r = mon.escanear()
    est = mon.estado()
    check("sin probe: no ancla", not est["anclado"])
    check("sin probe: no hay drift", not est["detector"]["drift"])
    check("sin probe: 0 veredictos", r["veredictos_nuevos"] == 0)


def test_empate_no_alimenta():
    """gap <= 0 = empate = sin veredicto (convención EXP68): no ancla
    ni alimenta la ventana."""
    tmp = tempfile.mkdtemp()
    log, mon = monitor_fresco(tmp)
    decision_probe(log, "single")          # ancla
    mon.escanear()
    decision_probe(log, "cot", gap=0.0)    # empate: no cuenta
    decision_probe(log, "cot", gap=0.0)    # empate: no cuenta
    r = mon.escanear()
    est = mon.estado()
    check("empates: no alimentan", r["veredictos_nuevos"] == 0)
    check("empates: no disparan", not est["detector"]["drift"])
    check("empates: ventana vacía",
          est["detector"]["ventana"] == [])


def test_flip_registra_evento():
    """2 contradicciones al baseline → drift: ledger + ciclo."""
    tmp = tempfile.mkdtemp()
    log, mon = monitor_fresco(tmp)
    for _ in range(3):
        decision_probe(log, "single")
    mon.escanear()
    decision_probe(log, "cot")
    decision_probe(log, "cot")
    r = mon.escanear()
    check("flip: dispara", r["drift"] is True and r["drift_nuevo"])
    est = mon.estado()
    check("flip: senial con accion re_probe",
          est["detector"]["accion"] == "re_probe"
          and est["detector"]["baseline"] == "single")
    # Ledger: una entrada de drift con el detalle de la señal.
    with open(mon.ledger_path, encoding="utf-8") as f:
        entradas = [json.loads(l) for l in f if l.strip()]
    drifts = [e for e in entradas if e["tipo"] == "drift"]
    check("ledger: evento drift registrado",
          len(drifts) == 1
          and drifts[0]["senial"]["baseline"] == "single"
          and drifts[0]["senial"]["contradicciones"] == 2)
    check("ledger: anclaje inicial registrado",
          any(e["tipo"] == "anclaje" for e in entradas))
    # Evento de ciclo para la capa de crons/minero.
    ciclos = log.ciclo(tipo="drift_detectado")
    check("ciclo: drift_detectado asentado",
          len(ciclos) == 1 and ciclos[0]["actor"] == "detector_drift")
    # Idempotencia: otro escaneo no duplica el ledger.
    mon.escanear()
    with open(mon.ledger_path, encoding="utf-8") as f:
        entradas2 = [json.loads(l) for l in f if l.strip()]
    check("escaneo repetido no duplica",
          len(entradas2) == len(entradas))


def test_enclavado_y_reanclaje():
    tmp = tempfile.mkdtemp()
    log, mon = monitor_fresco(tmp)
    for _ in range(2):
        decision_probe(log, "single")
    mon.escanear()
    for _ in range(2):
        decision_probe(log, "cot")
    mon.escanear()
    check("disparó", mon.estado()["detector"]["drift"])
    for _ in range(6):  # calma posterior: sigue enclavado
        decision_probe(log, "single")
    mon.escanear()
    check("enclavado pese a calma", mon.estado()["detector"]["drift"])
    r = mon.anclar()  # re-ancla con el último veredicto medido
    check("re-anclaje ok", r["ok"] is True)
    est = mon.estado()
    check("re-anclaje libera la señal", not est["detector"]["drift"])
    check("re-anclaje al último veredicto",
          est["detector"]["baseline"] == "single")
    with open(mon.ledger_path, encoding="utf-8") as f:
        tipos = [json.loads(l)["tipo"] for l in f if l.strip()]
    check("ledger: anclaje de re-anclaje",
          tipos.count("anclaje") == 2)


def test_fail_safe():
    """Si las trazas fallan, el monitor se desactiva sin levantar."""

    class LogRoto:
        def decisiones(self, **kw):
            raise RuntimeError("db rota")

    mon = MonitorDriftVivo(LogRoto(), dir_base=tempfile.mkdtemp())
    r = mon.escanear()
    check("trazas rotas: escanear no levanta",
          r == {"activo": False, "motivo": "db rota"})
    check("trazas rotas: queda desactivado",
          mon.estado()["activo"] is False and mon.roto)
    check("trazas rotas: anclar tampoco levanta",
          mon.anclar()["ok"] is False)


# -- 6: end-to-end HTTP contra server.py real -------------------------------


def cargar_servidor(tmp, drift_env="1"):
    """Importa servicio/server.py con env temporal (DB en tmp,
    backend demo) y lo levanta en un puerto efímero."""
    env_prev = dict(os.environ)
    os.environ["ALMA_DB"] = os.path.join(tmp, "alma_store.db")
    os.environ["ALMA_BACKEND"] = "demo"
    os.environ["ALMA_DRIFT_VIVO"] = drift_env
    os.environ["ALMA_PORT"] = "8471"  # no se bindea al importar
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "servicio", "server.py")
    nombre = "alma_server_test_%s" % drift_env.replace("0", "off")
    try:
        spec = importlib.util.spec_from_file_location(nombre, ruta)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[nombre] = mod
        spec.loader.exec_module(mod)
    finally:
        os.environ.clear()
        os.environ.update(env_prev)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), mod.Manejador)
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    return mod, srv, base


def http_get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def http_post(base, path, datos):
    cuerpo = json.dumps(datos).encode("utf-8")
    req = urllib.request.Request(
        base + path, data=cuerpo,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def test_http_end_to_end():
    tmp = tempfile.mkdtemp()
    mod, srv, base = cargar_servidor(tmp)
    try:
        st, cuerpo = http_get(base, "/salud")
        check("/salud responde", st == 200 and cuerpo == {"ok": True})

        st, est = http_get(base, "/drift/estado")
        check("/drift/estado activo sin baseline",
              st == 200 and est["activo"] is True
              and est["anclado"] is False
              and est["detector"]["drift"] is False)

        # Trazas con la forma exacta del motor vivo: 3 veredictos
        # "single" → ancla; 2 "cot" → drift.
        for _ in range(3):
            decision_probe(mod.event_log, "single")
        st, esc = http_post(base, "/drift/escanear", {})
        check("/drift/escanear ancla",
              st == 200 and esc["activo"] and not esc["drift"])
        for _ in range(2):
            decision_probe(mod.event_log, "cot")
        st, est = http_get(base, "/drift/estado")
        check("/drift/estado expone el drift",
              st == 200 and est["detector"]["drift"] is True
              and est["detector"]["baseline"] == "single")
        check("/drift/estado trae la cola del ledger",
              any(e["tipo"] == "drift"
                  for e in est["ultimos_eventos"]))
        ledger = os.path.join(tmp, "drift-ledger.jsonl")
        with open(ledger, encoding="utf-8") as f:
            tipos = [json.loads(l)["tipo"] for l in f if l.strip()]
        check("ledger en disco con drift", "drift" in tipos)

        st, f2 = http_get(base, "/fase2/estado")
        check("/fase2/estado trae fase25",
              st == 200 and f2["fase25"]["drift"]["detector"]["drift"]
              is True)

        st, rea = http_post(base, "/drift/anclar", {})
        check("/drift/anclar libera",
              st == 200 and rea["ok"] is True)
        st, est = http_get(base, "/drift/estado")
        check("tras anclar: sin drift",
              est["detector"]["drift"] is False)

        # El núcleo no se alteró: /resolver sigue respondiendo.
        st, res = http_post(base, "/resolver",
                            {"texto": "¿Cuánto es 2 + 2?"})
        check("/resolver intacto",
              st == 200 and res["brazo"] in ("single", "cot", "reflexion")
              and "respuesta" in res)
        st, _ = http_get(base, "/salud")
        check("el servicio sigue en pie", st == 200)
    finally:
        srv.shutdown()


def test_http_kill_switch():
    """ALMA_DRIFT_VIVO=0 → endpoints informan monitor desactivado,
    el resto del servicio igual."""
    tmp = tempfile.mkdtemp()
    mod, srv, base = cargar_servidor(tmp, drift_env="0")
    try:
        st, est = http_get(base, "/drift/estado")
        check("kill switch: /drift/estado informa desactivado",
              st == 200 and est["activo"] is False)
        st, f2 = http_get(base, "/fase2/estado")
        check("kill switch: fase25 informa desactivado",
              st == 200
              and f2["fase25"]["drift"]["activo"] is False)
        st, _ = http_get(base, "/salud")
        check("kill switch: /salud intacto", st == 200)
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_ancla_con_primer_veredicto()
    test_sin_probe_no_hay_baseline()
    test_empate_no_alimenta()
    test_flip_registra_evento()
    test_enclavado_y_reanclaje()
    test_fail_safe()
    test_http_end_to_end()
    test_http_kill_switch()
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if all(PASSOS) else 1)
