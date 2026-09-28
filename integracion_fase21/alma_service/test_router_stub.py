#!/usr/bin/env python3
"""Tests del stub mock del endpoint POST /route.

Cero gasto, cero red, cero puertos: todos los pings van por dobles
inyectados. Además verifica que el stub NO reescribe el registry real
(persistir=False) y que jamás ve secretos.
"""

import hashlib
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from router_stub import (  # noqa: E402
    RouterStub,
    RouterError,
    clasificar_tarea,
    SLICES,
)

YAML_REAL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "proveedores.yaml")


def ping_ok(proveedor):
    return None


def ping_401(proveedor):
    raise urllib.error.HTTPError(proveedor["ping_url"], 401, "Unauthorized",
                                 {}, None)


def ping_401_solo_deepseek(proveedor):
    if proveedor["id"] == "deepseek":
        raise urllib.error.HTTPError(proveedor["ping_url"], 401,
                                     "Unauthorized", {}, None)
    return None


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


class TestClasificacion(unittest.TestCase):
    def test_slice_exacto(self):
        for sl in SLICES:
            self.assertEqual(clasificar_tarea(sl), sl)

    def test_keywords(self):
        self.assertEqual(
            clasificar_tarea("resolver un problema de matemáticas"), "gsm8k")
        self.assertEqual(
            clasificar_tarea("escribir una función en python"), "mbpp")
        self.assertEqual(
            clasificar_tarea("pregunta de historia con opciones"), "mmlu")

    def test_desconocida_422(self):
        with self.assertRaises(RouterError) as cm:
            clasificar_tarea("horóscopo de hoy")
        self.assertEqual(cm.exception.status, 422)
        self.assertEqual(cm.exception.codigo, "unknown_task")

    def test_tarea_vacia_400(self):
        with self.assertRaises(RouterError) as cm:
            clasificar_tarea("   ")
        self.assertEqual(cm.exception.status, 400)


class TestRoute(unittest.TestCase):
    def setUp(self):
        self.r = RouterStub(yaml_path=YAML_REAL, ping_fn=ping_ok)

    def test_gsm8k_reproduce_exp69(self):
        resp = self.r.route("gsm8k", presupuesto_usd=0.01)
        self.assertEqual(resp["proveedor"], "deepseek")
        self.assertEqual(resp["modelo"], "deepseek-flash")
        self.assertEqual(resp["brazo"], "single")
        self.assertAlmostEqual(resp["costo_estimado_usd"], 0.0000142)
        self.assertIn("EXP69", resp["motivo"])
        self.assertIn("n=120", resp["motivo"])

    def test_mmlu_y_mbpp(self):
        for tarea in ("mmlu", "mbpp"):
            resp = self.r.route(tarea, presupuesto_usd=0.01)
            self.assertEqual((resp["proveedor"], resp["brazo"]),
                             ("deepseek", "single"))

    def test_schema_respuesta(self):
        resp = self.r.route("gsm8k", presupuesto_usd=0.01)
        self.assertEqual(set(resp.keys()),
                         {"proveedor", "modelo", "brazo",
                          "costo_estimado_usd", "motivo"})

    def test_presupuesto_invalido_400(self):
        for malo in (0, -1, "mucho", None):
            with self.assertRaises(RouterError) as cm:
                self.r.route("gsm8k", presupuesto_usd=malo)
            self.assertEqual(cm.exception.status, 400)
            self.assertEqual(cm.exception.codigo, "invalid_request")

    def test_latencia_invalida_400(self):
        with self.assertRaises(RouterError) as cm:
            self.r.route("gsm8k", presupuesto_usd=0.01, latencia_max_ms=-5)
        self.assertEqual(cm.exception.status, 400)

    def test_latencia_valida_no_rompe(self):
        # El stub acepta latencia_max_ms pero no la usa para elegir
        # (el registry aún no tiene mediciones de latencia; ver diseño).
        resp = self.r.route("gsm8k", presupuesto_usd=0.01,
                            latencia_max_ms=30000)
        self.assertEqual(resp["proveedor"], "deepseek")

    def test_budget_exceeded_402(self):
        with self.assertRaises(RouterError) as cm:
            self.r.route("gsm8k", presupuesto_usd=1e-9)
        self.assertEqual(cm.exception.status, 402)
        self.assertEqual(cm.exception.codigo, "budget_exceeded")

    def test_failover_401_deepseek(self):
        r = RouterStub(yaml_path=YAML_REAL,
                       ping_fn=ping_401_solo_deepseek)
        resp = r.route("gsm8k", presupuesto_usd=0.01)
        self.assertEqual(resp["proveedor"], "openai")
        self.assertEqual(resp["modelo"], "gpt-4o-mini")
        self.assertEqual(resp["brazo"], "single")

    def test_todos_caidos_503(self):
        r = RouterStub(yaml_path=YAML_REAL, ping_fn=ping_401)
        with self.assertRaises(RouterError) as cm:
            r.route("gsm8k", presupuesto_usd=0.01)
        self.assertEqual(cm.exception.status, 503)
        self.assertEqual(cm.exception.codigo, "no_provider_available")

    def test_sin_secretos_en_respuesta(self):
        resp = self.r.route("gsm8k", presupuesto_usd=0.01)
        blob = str(resp).lower()
        for palabra in ("token", "secret", "key", "bearer", "password",
                        "credential"):
            self.assertNotIn(palabra, blob)

    def test_no_muta_el_yaml_real(self):
        antes = sha(YAML_REAL)
        for tarea in ("gsm8k", "mmlu", "mbpp"):
            self.r.route(tarea, presupuesto_usd=0.01)
        r2 = RouterStub(yaml_path=YAML_REAL, ping_fn=ping_401)
        try:
            r2.route("gsm8k", presupuesto_usd=0.01)
        except RouterError:
            pass
        self.assertEqual(sha(YAML_REAL), antes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
