"""Experience Store — núcleo FIJO (sección 9 del informe).

Append-only e inmutable: el aprendizaje nunca reescribe la historia, solo
la pondera. Cada fila lleva un hash encadenado (prev_hash) para que
cualquier reescritura sea detectable con verify_chain().

No existen métodos update() ni delete() a propósito: si necesitás
corregir algo, se agrega una fila nueva. Reescribir historia es
Goodhart institucionalizado.
"""

import hashlib
import json
import os
import time

SCHEMA_VERSION = "store-v1"

REQUIRED_FIELDS = [
    "problema_id",   # id del problema
    "features",      # dict de features del featurizer
    "clase",         # clase (etiqueta del dataset o del clasificador)
    "arch_id",       # familia arquitectónica usada
    "config",        # parámetros con los que corrió
    "respuesta",     # respuesta final del ejecutor
    "traza",         # resumen de la traza de ejecución
    "metricas",      # dict: exito (0/1), reward, detalle...
    "costo_usd",     # costo medido en USD
]


class StoreError(Exception):
    pass


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash_row(row, prev_hash):
    h = hashlib.sha256()
    h.update(prev_hash.encode("utf-8"))
    h.update(_canonical(row).encode("utf-8"))
    return h.hexdigest()


class ExperienceStore:
    """Store append-only persistido como JSONL."""

    def __init__(self, path):
        self.path = path
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        # No truncamos: si el archivo existe, se sigue desde el final.
        self._n = 0
        self._last_hash = "GENESIS"
        # Tocar el archivo: una cadena vacía es una cadena válida.
        open(path, "a", encoding="utf-8").close()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    self._last_hash = row["hash"]
                    self._n += 1

    def append(self, row):
        """Agrega una fila. Valida campos, firma con timestamp y hash encadenado."""
        for field in REQUIRED_FIELDS:
            if field not in row:
                raise StoreError(f"falta campo requerido: {field}")
        stored = dict(row)
        stored["schema"] = SCHEMA_VERSION
        stored["timestamp"] = time.time()
        prev = self._last_hash
        stored["prev_hash"] = prev
        body = {k: v for k, v in stored.items() if k != "hash"}
        stored["hash"] = _hash_row(body, prev)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(_canonical(stored) + "\n")
        self._last_hash = stored["hash"]
        self._n += 1
        return stored

    def read_all(self):
        """Itera todas las filas en orden de escritura."""
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def __len__(self):
        return self._n

    def verify_chain(self):
        """True si la cadena de hashes está intacta (nadie reescribió historia)."""
        prev = "GENESIS"
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    body = {k: v for k, v in row.items() if k != "hash"}
                    if row.get("prev_hash") != prev:
                        return False
                    if row.get("hash") != _hash_row(body, prev):
                        return False
                    prev = row["hash"]
        except (OSError, ValueError, KeyError):
            return False
        return True
