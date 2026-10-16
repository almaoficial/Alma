"""Archivo de variantes del meta-loop — tercera pata de la puerta.

Motivación (estudio revoluciones-para-alma-20261007, §6-7): la ablación
de la Darwin-Gödel Machine muestra que sin archivo de variantes el
agente que se mejora solo SE TRABA — el greedy de "quedarse con lo
mejor" es una trampa medida, no una opinión. Lo rechazado no se tira:
es el pool genético del que el loop escapa de óptimos locales.

Contrato:
- El archivo NO decide nada. Solo guarda, con timestamp, cada variante
  que la puerta de dos splits evaluó (adoptada o rechazada), con sus
  deltas medidos, costo y motivo.
- La puerta (gate.py) no se toca: la regla de aceptación es idéntica.
- Lectura reservada al futuro proponente (muestreo por diversidad).
  Hoy nadie lee el archivo salvo `listar()`/`resumen()` para
  observabilidad.

Formato: un JSON por línea en `metaloop_archivo.jsonl`, junto al
`metaloop_ledger.jsonl`. Cada registro = el audit record de la puerta
+ `ts` (UTC) + `archivo_id` (`av-<n>` monotónico por archivo).
"""

import json
import os
import threading
from datetime import datetime, timezone

NOMBRE_DEFAULT = "metaloop_archivo.jsonl"


def _ts_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ArchivoVariantes:
    """Solo-append de variantes evaluadas por la puerta. Thread-safe."""

    def __init__(self, ruta=None):
        if ruta is None:
            base = os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))
            ruta = os.path.join(base, NOMBRE_DEFAULT)
        self.ruta = ruta
        self._lock = threading.Lock()
        if not os.path.exists(self.ruta):
            with open(self.ruta, "w", encoding="utf-8"):
                pass

    def _siguiente_id(self):
        n = 0
        with open(self.ruta, encoding="utf-8") as f:
            for linea in f:
                if linea.strip():
                    n += 1
        return f"av-{n + 1}"

    def guardar(self, registro):
        """Guarda una variante evaluada. Retorna el registro guardado
        (con `ts` y `archivo_id`). `registro` no se muta."""
        rec = dict(registro)
        with self._lock:
            rec["archivo_id"] = self._siguiente_id()
            rec["ts"] = _ts_utc()
            with open(self.ruta, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def listar(self):
        """Lee todas las variantes archivadas (uso futuro: el
        proponente muestrea por diversidad)."""
        out = []
        with open(self.ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    out.append(json.loads(linea))
        return out

    def resumen(self):
        """Conteo para observabilidad. No decide nada."""
        regs = self.listar()
        return {
            "total": len(regs),
            "adoptadas": sum(1 for r in regs if r.get("aceptado")),
            "rechazadas": sum(1 for r in regs if not r.get("aceptado")),
        }
