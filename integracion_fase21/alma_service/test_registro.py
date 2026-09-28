#!/usr/bin/env python3
"""Tests del registry de proveedores. Cero gasto de API: todos los pings
van por dobles inyectados, nunca tocan la red real."""

import copy
import io
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from registro import (  # noqa: E402
    RegistroProveedores,
    RegistryInvalido,
    SinProveedorDisponible,
)

YAML_REAL = os.path.join(os.path.dirname(os.path.abspath(__file__),
                                         ), "proveedores.yaml")


def ping_ok(proveedor):
    return None


def ping_401(proveedor):
    raise urllib.error.HTTPError(proveedor["ping_url"], 401, "Unauthorized",
                                 {}, None)


def ping_403(proveedor):
    raise urllib.error.HTTPError(proveedor["ping_url"], 403, "Forbidden",
                                 {}, None)


def ping_500(proveedor):
    raise urllib.error.HTTPError(proveedor["ping_url"], 500, "Server Error",
                                 {}, None)


def ping_red(proveedor):
    raise urllib.error.URLError("connection refused (simulado)")


def ping_401_solo_deepseek(proveedor):
    if proveedor["id"] == "deepseek":
        raise urllib.error.HTTPError(proveedor["ping_url"], 401,
                                     "Unauthorized", {}, None)
    return None


class TestCarga(unittest.TestCase):
    def test_carga_valida(self):
        reg = RegistroProveedores(YAML_REAL, ping_fn=ping_ok)
        ids = sorted(p["id"] for p in reg._proveedores)
        # 2026-09-28: EXP67-Claude-Full sembro la entrada `anthropic`
        # (2 campanas: exp70-piloto + exp67-claude-full).
        self.assertEqual(ids, ["anthropic", "deepseek", "openai"])

    def test_falta_campo_ruidoso(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "mal.yaml")
            with open(ruta, "w") as f:
                f.write("proveedores:\n  - id: x\n")
            with self.assertRaises(RegistryInvalido) as cm:
                RegistroProveedores(ruta, ping_fn=ping_ok)
            self.assertIn("connector", str(cm.exception))

    def test_celda_invalida_ruidosa(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "mal2.yaml")
            shutil.copy(YAML_REAL, ruta)
            reg = RegistroProveedores(ruta, ping_fn=ping_ok)
            # corrompo una celda: reward fuera de [0,1]
            prov = reg._por_id("openai")
            prov["mediciones"][0]["celdas"]["gsm8k/single"]["reward_medio"] = 2.5
            reg.guardar()
            with self.assertRaises(RegistryInvalido):
                RegistroProveedores(ruta, ping_fn=ping_ok)

    def test_id_duplicado_ruidoso(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "mal3.yaml")
            shutil.copy(YAML_REAL, ruta)
            reg = RegistroProveedores(ruta, ping_fn=ping_ok)
            reg._doc["proveedores"].append(copy.deepcopy(reg._por_id("openai")))
            reg.guardar()
            with self.assertRaises(RegistryInvalido) as cm:
                RegistroProveedores(ruta, ping_fn=ping_ok)
            self.assertIn("duplicado", str(cm.exception))


class TestFailover(unittest.TestCase):
    def test_401_voltea_solo_al_caido(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "reg.yaml")
            shutil.copy(YAML_REAL, ruta)
            reg = RegistroProveedores(ruta, ping_fn=ping_401_solo_deepseek)
            disp = reg.disponibles(persistir=True)
            # 2026-09-28: `anthropic` tambien esta habilitado y disponible.
            self.assertEqual(disp, ["openai", "anthropic"])
            est = reg.estado("deepseek")
            self.assertEqual(est["disponibilidad"], "no_disponible")
            self.assertIn("401", est["motivo"])
            self.assertTrue(est["fecha"])  # fecha registrada
            # el otro no se voltea
            self.assertEqual(reg.estado("openai")["disponibilidad"],
                             "disponible")
            # y persiste en el archivo
            reg2 = RegistroProveedores(ruta, ping_fn=ping_ok)
            self.assertEqual(reg2.estado("deepseek")["disponibilidad"],
                             "no_disponible")

    def test_403_tambien_voltea(self):
        reg = RegistroProveedores(YAML_REAL, ping_fn=ping_403)
        self.assertEqual(reg.disponibles(persistir=False), [])
        for pid in ("deepseek", "openai"):
            self.assertEqual(reg.estado(pid)["disponibilidad"],
                             "no_disponible")

    def test_error_transitorio_no_voltea_estado(self):
        # deepseek con hipo de red, openai ok
        def ping_mixto(p):
            if p["id"] == "deepseek":
                raise urllib.error.URLError("timeout (simulado)")
            return None
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "reg.yaml")
            shutil.copy(YAML_REAL, ruta)
            reg = RegistroProveedores(ruta, ping_fn=ping_mixto)
            disp = reg.disponibles(persistir=True)
            # fail-closed para el ruteo: no se ofrece esta ronda...
            # 2026-09-28: `anthropic` tambien esta habilitado y disponible.
            self.assertEqual(disp, ["openai", "anthropic"])
            # ...pero el estado persistido NO se voltea por un hipo
            self.assertEqual(reg.estado("deepseek")["disponibilidad"],
                             "disponible")
            reg2 = RegistroProveedores(ruta, ping_fn=ping_ok)
            self.assertEqual(reg2.estado("deepseek")["disponibilidad"],
                             "disponible")

    def test_500_no_voltea(self):
        reg = RegistroProveedores(YAML_REAL, ping_fn=ping_500)
        self.assertEqual(reg.disponibles(persistir=False), [])
        for pid in ("deepseek", "openai"):
            self.assertEqual(reg.estado(pid)["disponibilidad"],
                             "disponible")


class TestElegir(unittest.TestCase):
    def test_reproduce_exp69(self):
        # Con los datos sembrados y ambos disponibles, el router elige
        # deepseek/single en los 3 slices (veredicto EXP69 + generalización).
        reg = RegistroProveedores(YAML_REAL, ping_fn=ping_ok)
        for sl in ("gsm8k", "mmlu", "mbpp"):
            self.assertEqual(reg.elegir(sl, persistir=False),
                             ("deepseek", "single"), f"slice {sl}")

    def test_fail_closed_sin_proveedores(self):
        reg = RegistroProveedores(YAML_REAL, ping_fn=ping_401)
        with self.assertRaises(SinProveedorDisponible):
            reg.elegir("gsm8k", persistir=False)

    def test_failover_en_elegir(self):
        # deepseek caído (401) → el router usa openai sin inventar nada
        reg = RegistroProveedores(YAML_REAL, ping_fn=ping_401_solo_deepseek)
        self.assertEqual(reg.elegir("gsm8k", persistir=False)[0], "openai")

    def test_desempate_por_menor_costo(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "reg.yaml")
            shutil.copy(YAML_REAL, ruta)
            reg = RegistroProveedores(ruta, ping_fn=ping_ok)
            # fuerzo empate de score entre dos celdas de gsm8k
            camp = reg._mejor_campana(reg._por_id("deepseek"))
            # fuerzo empate de score: cot con doble reward y doble costo
            r = camp["celdas"]["gsm8k/single"]["reward_medio"]
            c = camp["celdas"]["gsm8k/single"]["costo_medio_usd"]
            camp["celdas"]["gsm8k/cot"] = {"n": 120, "reward_medio": r * 2,
                                           "costo_medio_usd": c * 2}
            self.assertAlmostEqual(
                camp["celdas"]["gsm8k/cot"]["reward_medio"]
                / camp["celdas"]["gsm8k/cot"]["costo_medio_usd"], r / c)
            self.assertEqual(reg.elegir("gsm8k", persistir=False),
                             ("deepseek", "single"))

    def test_slice_sin_mediciones(self):
        reg = RegistroProveedores(YAML_REAL, ping_fn=ping_ok)
        with self.assertRaises(ValueError):
            reg.elegir("inexistente", persistir=False)


class TestActualizarMedicion(unittest.TestCase):
    def test_media_corrida(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "reg.yaml")
            shutil.copy(YAML_REAL, ruta)
            reg = RegistroProveedores(ruta, ping_fn=ping_ok)
            # la medición nueva va a la campaña "acumulada-operativa"
            # (no corrompe la campaña inmutable del experimento)
            celda = reg.actualizar_medicion("openai", "single", "gsm8k",
                                            reward=1.0, costo=0.00002, n=20)
            self.assertEqual(celda["n"], 20)
            # segunda medición a la misma celda: media corrida
            celda2 = reg.actualizar_medicion("openai", "single", "gsm8k",
                                             reward=0.0, costo=0.00004, n=20)
            self.assertEqual(celda2["n"], 40)
            self.assertAlmostEqual(celda2["reward_medio"], 0.5)
            self.assertAlmostEqual(celda2["costo_medio_usd"], 0.00003)
            # una medición chica no tapa la campaña grande en elegir()
            camp = reg._mejor_campana(reg._por_id("openai"))
            self.assertEqual(camp["campana"], "exp69-piloto")

    def test_proveedor_desconocido(self):
        reg = RegistroProveedores(YAML_REAL, ping_fn=ping_ok)
        with self.assertRaises(KeyError):
            reg.actualizar_medicion("inexistente", "single", "gsm8k",
                                    reward=1.0, costo=0.0001)

    def test_sin_secretos_en_registry(self):
        with open(YAML_REAL, encoding="utf-8") as f:
            texto = f.read()
        self.assertNotIn("sk-", texto)
        # ningún campo con pinta de secreto
        reg = RegistroProveedores(YAML_REAL, ping_fn=ping_ok)
        for p in reg._proveedores:
            for k in p:
                self.assertNotIn("secret", k.lower())
                self.assertNotIn("password", k.lower())
                self.assertNotIn("token", k.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
