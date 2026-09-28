#!/usr/bin/env python3
"""Cliente del dominio inglés para el chequeo nocturno.

Uso:
  python3 cliente_ingles.py recomendar
      → imprime la recomendación de ALMA para mañana.

  python3 cliente_ingles.py puntuar <metodo_id> <1-5> [nota]
      → registra la práctica de hoy con su puntaje.

metodo_id: conversacion | podcast_3pasos | shadowing | frases_utiles |
           dictado | otro

Si el servicio está caído, intenta revivirlo solo antes de fallar.
"""

import json
import os
import subprocess
import sys
import urllib.request

URL = os.environ.get("ALMA_URL", "http://127.0.0.1:8471")
DIR = os.path.dirname(os.path.abspath(__file__))


def _http(metodo, ruta, datos=None):
    cuerpo = json.dumps(datos or {}).encode("utf-8") if datos is not None else None
    req = urllib.request.Request(
        URL + ruta, data=cuerpo, method=metodo,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def _asegurar_servicio():
    try:
        _http("GET", "/salud")
        return True
    except Exception:  # noqa: BLE001 - si está caído, revivir
        pass
    try:
        subprocess.run(["./arrancar.sh"], cwd=DIR, capture_output=True,
                       timeout=30)
        _http("GET", "/salud")
        print("(el servicio estaba caído y se revivió solo)", file=sys.stderr)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: no se pudo revivir el servicio: {e}", file=sys.stderr)
        return False


def cmd_recomendar():
    r = _http("POST", "/ingles/recomendar", {})
    m = r["metodo"]
    print(f"ALMA recomienda para mañana: {m['nombre']}")
    print(m["detalle"])
    if r["practicas_registradas"] == 0:
        print("Todavía no hay historial: estoy aprendiendo tus gustos, "
              "las primeras recomendaciones son exploratorias.")
    else:
        n = r['practicas_registradas']
        practicas_txt = "1 práctica registrada" if n == 1 else f"{n} prácticas registradas"
        print(f"Hasta ahora lo mejor: {r['mejor_hasta_ahora']} "
              f"({r['mejor_media_5']}/5, {practicas_txt}).")


def cmd_puntuar(metodo_id, puntaje, nota=""):
    r = _http("POST", "/ingles/puntuar",
              {"metodo_id": metodo_id, "puntaje": int(puntaje),
               "nota": nota})
    print(f"Registrado: {r['metodo']} — puntaje {puntaje}/5.")


def main(argv):
    if not _asegurar_servicio():
        return 1
    if len(argv) < 2:
        print(__doc__.strip())
        return 2
    cmd = argv[1]
    if cmd == "recomendar":
        cmd_recomendar()
    elif cmd == "puntuar":
        if len(argv) < 4:
            print("uso: cliente_ingles.py puntuar <metodo_id> <1-5> [nota]",
                  file=sys.stderr)
            return 2
        cmd_puntuar(argv[2], argv[3], " ".join(argv[4:]))
    else:
        print(f"comando desconocido: {cmd}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
