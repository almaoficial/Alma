"""Cliente del chequeo nocturno: el análisis del día pasa por el motor.

Uso:
    python3 cliente_chequeo.py diario-2026-09-26.txt
    cat diario.txt | python3 cliente_chequeo.py

Lee el log del día (rutina, gastos, inglés), lo envía al servicio ALMA
como problema de clase "analisis_diario", y el motor elige la arquitectura
de análisis (single/cot/reflexion), ejecuta y guarda la experiencia.
Cada noche el motor aprende: el feedback ("¿sirvió el análisis?") llega
después vía POST /feedback con el experiencia_id impreso abajo.

No modifica crons: el cron nocturno puede llamar a este script y usar su
salida. Variable de entorno ALMA_URL (default http://127.0.0.1:8471).
"""

import json
import os
import sys
import urllib.request

ALMA_URL = os.environ.get("ALMA_URL", "http://127.0.0.1:8471").rstrip("/")


def _post(ruta, datos):
    cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{ALMA_URL}{ruta}", data=cuerpo,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            diario = f.read()
        fuente = sys.argv[1]
    else:
        diario = sys.stdin.read()
        fuente = "stdin"
    if not diario.strip():
        print("Log del día vacío; nada que analizar.", file=sys.stderr)
        sys.exit(1)

    prompt = (
        "Analizá el día del usuario a partir de su log. Estructura tu "
        "respuesta en 4 partes breves: 1) Rutina: qué cumplió y qué no, "
        "2) Gastos: total y patrón visible, 3) Inglés: qué practicó, "
        "4) Una sola acción concreta para mañana. Sé directo, sin relleno.\n\n"
        f"LOG DEL DÍA (fuente: {fuente}):\n{diario}"
    )
    res = _post("/resolver", {"texto": prompt, "clase": "analisis_diario"})

    print("=" * 60)
    print(res["respuesta"])
    print("=" * 60)
    print(f"[motor] brazo={res['brazo']} clase={res['clase']} "
          f"costo_usd={res['costo_usd']} experiencia_id={res['experiencia_id']}")
    if res.get("reward") is None:
        print("[motor] sin señal de reward: el aprendizaje llega vía "
              "/feedback (¿sirvió el análisis?).")

    salida = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "ultimo_analisis.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f"[motor] respuesta completa guardada en {salida}")


if __name__ == "__main__":
    main()
