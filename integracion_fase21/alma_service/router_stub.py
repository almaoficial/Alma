#!/usr/bin/env python3
"""Stub mock del endpoint POST /route del router ALMA (fase 2.x).

Qué es: la lógica de decisión del endpoint documentada en
DISENO_API_ROUTE.md, sin HTTP, sin red y sin gastar un centavo. Responde con
datos MEDIDOS del registry (integracion_fase21/alma_service/proveedores.yaml),
nunca inventados.

REGLAS DURAS de este módulo:
  - US$0: jamás llama a una API de LLM. El ping por defecto es un doble
    (`lambda p: None`); los tests inyectan dobles que simulan fallos.
  - Sin red: no hace requests, no abre puertos, no expone nada.
  - Sin secretos: solo ve IDs de proveedor y estadísticas (igual que
    registro.py). Un test lo verifica.
  - No muta el registry real por defecto (`persistir=False`): el failover
    excluye proveedores de LA RONDA sin reescribir el YAML. El deploy real
    deberá persistir (ver DISENO_API_ROUTE.md).

Uso:
    from router_stub import RouterStub
    r = RouterStub()  # ping mock: todos disponibles
    r.route("resolver un problema de matemáticas", presupuesto_usd=0.01)
    # -> {"proveedor": "deepseek", "modelo": "deepseek-flash",
    #     "brazo": "single", "costo_estimado_usd": 0.0000142,
    #     "motivo": "regla EXP69 ..."}
"""

import os

from registro import RegistroProveedores, SinProveedorDisponible

DIR = os.path.dirname(os.path.abspath(__file__))
YAML_DEFAULT = os.path.join(DIR, "proveedores.yaml")

SLICES = ("gsm8k", "mmlu", "mbpp")

# Clasificador tarea -> slice: exacto primero, después keywords (es/en).
# Determinista; lo desconocido falla ruidoso (422) en vez de adivinar.
_KEYWORDS = {
    "gsm8k": ("matem", "arith", "number", "numer", "numeros", "números",
              "calcu", "suma", "resta", "ecuaci", "porcentaje"),
    "mmlu": ("conocimiento", "knowledge", "pregunta", "question", "opciones",
             "choices", "examen", "exam", "historia", "history", "ciencia",
             "science"),
    "mbpp": ("código", "codigo", "code", "python", "función", "funcion",
             "function", "program", "bug", "script", "debug"),
}


# ---------------------------------------------------------------- errores

class RouterError(Exception):
    """Error del endpoint con su status HTTP. `codigo` es estable para
    clientes (unknown_task, budget_exceeded, no_provider_available,
    invalid_request)."""

    def __init__(self, status, codigo, detalle):
        self.status = status
        self.codigo = codigo
        self.detalle = detalle
        super().__init__(f"{status} {codigo}: {detalle}")


# ---------------------------------------------------------------- helpers

def clasificar_tarea(tarea):
    """tarea -> slice del registry. Lanza RouterError(422) si no mapea."""
    if not isinstance(tarea, str) or not tarea.strip():
        raise RouterError(400, "invalid_request",
                          "tarea debe ser un string no vacío")
    t = tarea.strip().lower()
    if t in SLICES:
        return t
    for sl in SLICES:
        for kw in _KEYWORDS[sl]:
            if kw in t:
                return sl
    raise RouterError(422, "unknown_task",
                      f"tarea no mapea a ningún slice conocido "
                      f"(slices válidos: {', '.join(SLICES)})")


def _celda(reg, proveedor_id, slice, brazo):
    p = reg._por_id(proveedor_id)
    camp = reg._mejor_campana(p)
    return p, camp, camp["celdas"][f"{slice}/{brazo}"]


# ---------------------------------------------------------------- stub

class RouterStub:
    """Lógica del POST /route sin capa HTTP.

    ping_fn: doble inyectable (default: todos disponibles, cero red).
    persistir: si True, el failover reescribe el YAML (default False:
    el stub mock no muta el registry).
    """

    def __init__(self, yaml_path=YAML_DEFAULT, ping_fn=None, persistir=False):
        self._reg = RegistroProveedores(
            yaml_path, ping_fn=ping_fn or (lambda p: None))
        self._persistir = persistir

    def route(self, tarea, presupuesto_usd, latencia_max_ms=None):
        """Decide proveedor/modelo/brazo para una tarea.

        Lanza RouterError con status 400/422/402/503 según el caso.
        Devuelve el dict de respuesta del endpoint (200).
        """
        if not isinstance(presupuesto_usd, (int, float)) \
                or not (presupuesto_usd > 0):
            raise RouterError(400, "invalid_request",
                              "presupuesto_usd debe ser un número > 0")
        if latencia_max_ms is not None and (
                not isinstance(latencia_max_ms, (int, float))
                or not (latencia_max_ms > 0)):
            raise RouterError(400, "invalid_request",
                              "latencia_max_ms debe ser un número > 0 "
                              "o ausente")

        slice = clasificar_tarea(tarea)

        try:
            proveedor_id, brazo = self._reg.elegir(
                slice, persistir=self._persistir)
        except SinProveedorDisponible as e:
            raise RouterError(503, "no_provider_available", str(e))
        except ValueError as e:  # slice sin mediciones en el registry
            raise RouterError(422, "unknown_task", str(e))

        p, camp, celda = _celda(self._reg, proveedor_id, slice, brazo)
        costo = celda["costo_medio_usd"]
        if costo > presupuesto_usd:
            raise RouterError(
                402, "budget_exceeded",
                f"costo estimado US${costo:.7f} supera el presupuesto "
                f"US${presupuesto_usd:.7f} (fail-closed: ningún proveedor "
                f"cabe en el presupuesto)")

        modelo = p["modelos"][0]  # el medido en la campaña ganadora
        score = celda["reward_medio"] / costo
        motivo = (
            f"regla EXP69 (max reward/USD): {proveedor_id}/{brazo}, "
            f"reward {celda['reward_medio']:.4f} / costo US${costo:.7f} "
            f"-> {score:,.0f} reward/USD (n={celda['n']}, campaña "
            f"{camp['campana']}); presupuesto US${presupuesto_usd:.7f} OK"
        )
        return {
            "proveedor": proveedor_id,
            "modelo": modelo,
            "brazo": brazo,
            "costo_estimado_usd": costo,
            "motivo": motivo,
        }
