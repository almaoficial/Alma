"""Tests del Experience Store: append-only real con detección de reescritura."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alma.store import ExperienceStore, StoreError
from alma.gates import ReadOnlyStore, PrivilegeError


def fila(i):
    return {
        "problema_id": f"p-{i}",
        "features": {"n_numeros": 2},
        "clase": "calculo",
        "arch_id": "cot",
        "config": {},
        "respuesta": "42",
        "traza": "t",
        "metricas": {"exito": 1.0, "reward": 0.9},
        "costo_usd": 0.0001,
    }


def test_append_y_lectura():
    with tempfile.TemporaryDirectory() as d:
        s = ExperienceStore(os.path.join(d, "exp.jsonl"))
        s.append(fila(1))
        s.append(fila(2))
        assert len(s) == 2
        rows = list(s.read_all())
        assert rows[0]["problema_id"] == "p-1"
        assert rows[1]["prev_hash"] == rows[0]["hash"]
        assert s.verify_chain()


def test_requiere_campos():
    with tempfile.TemporaryDirectory() as d:
        s = ExperienceStore(os.path.join(d, "exp.jsonl"))
        try:
            s.append({"problema_id": "x"})
            raise AssertionError("aceptó fila incompleta")
        except StoreError:
            pass


def test_reescritura_se_detecta():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "exp.jsonl")
        s = ExperienceStore(path)
        s.append(fila(1))
        assert s.verify_chain()
        # Atacante: modifica una línea del archivo directamente.
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        row = json.loads(lines[0])
        row["metricas"]["reward"] = 1.0  # "mejorar" la historia
        lines[0] = json.dumps(row) + "\n"
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        assert not s.verify_chain(), "la reescritura NO fue detectada"


def test_no_hay_update_ni_delete():
    with tempfile.TemporaryDirectory() as d:
        s = ExperienceStore(os.path.join(d, "exp.jsonl"))
        assert not hasattr(s, "update")
        assert not hasattr(s, "delete")


def test_solo_lectura_para_el_selector():
    with tempfile.TemporaryDirectory() as d:
        s = ExperienceStore(os.path.join(d, "exp.jsonl"))
        s.append(fila(1))
        ro = ReadOnlyStore(s)
        assert len(ro) == 1
        assert len(list(ro.read_all())) == 1
        try:
            ro.append(fila(2))
            raise AssertionError("ReadOnlyStore permitió escribir")
        except PrivilegeError:
            pass


if __name__ == "__main__":
    test_append_y_lectura()
    test_requiere_campos()
    test_reescritura_se_detecta()
    test_no_hay_update_ni_delete()
    test_solo_lectura_para_el_selector()
    print("test_store: 5/5 OK")
