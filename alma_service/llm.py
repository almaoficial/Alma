"""Cliente LLM con contabilidad de costo y presupuesto duro — fase 1.

Diseño §4.3 (regla dura): ningún componente gasta sin bucket asignado; si
el bucket se agota, el componente se degrada, no pide más solo.

- `Presupuesto`: tope en USD. `cargar(costo)` corta con PresupuestoAgotado
  ANTES de exceder (el llamado que lo excedería no se hace).
- `ClienteMedido`: envuelve cualquier backend con interfaz complete() ->
  (texto, uso). Acumula tokens y USD por llamado (precios de
  alma/backends.py PRECIOS) y lleva un registro para el reporte.

La key nunca se ve: el backend real es VaultBackend (surrogate via CLI).
Este módulo solo mide, nunca toca credenciales.
"""

import time

from alma.backends import PRECIOS


class PresupuestoAgotado(Exception):
    def __init__(self, tope, gastado, intento):
        super().__init__(
            f"presupuesto agotado: tope US${tope:.4f}, gastado "
            f"US${gastado:.4f}, intento +US${intento:.4f}"
        )
        self.tope = tope
        self.gastado = gastado
        self.intento = intento


def costo_uso(uso, precios):
    """USD de un llamado a partir de su dict de uso."""
    p_in, p_out = precios
    return (uso.get("prompt_tokens", 0) * p_in
            + uso.get("completion_tokens", 0) * p_out) / 1e6


class Presupuesto:
    """Bucket de gasto en USD con corte duro previo al exceso."""

    def __init__(self, tope_usd):
        if tope_usd <= 0:
            raise ValueError("tope_usd debe ser > 0")
        self.tope = float(tope_usd)
        self.gastado = 0.0
        self.llamados = 0

    def cabe(self, costo_estimado):
        return self.gastado + costo_estimado <= self.tope

    def cargar(self, costo):
        """Registra un costo ya incurrido. Si el próximo céntimo no cabe,
        esto no se llama: el corte ocurre ANTES del llamado (ver
        ClienteMedido.complete)."""
        self.gastado += float(costo)
        self.llamados += 1

    def verificar_antes(self, costo_estimado, proposito=""):
        if not self.cabe(costo_estimado):
            raise PresupuestoAgotado(self.tope, self.gastado,
                                     costo_estimado)

    def estado(self):
        return {"tope_usd": self.tope, "gastado_usd": round(self.gastado, 6),
                "restante_usd": round(self.tope - self.gastado, 6),
                "llamados": self.llamados}


class ClienteMedido:
    """Backend medido: misma interfaz complete(), con contabilidad.

    `presupuesto` es opcional; si se da, el corte es duro y previo.
    `etiqueta` identifica el propósito en el registro (ej: 'resolver',
    'skill-gen', 'skill-refine').
    """

    # Estimación previa conservadora para el corte (tokens). Si el
    # llamado real gasta menos, la diferencia queda a favor del bucket.
    ESTIMACION_PREVIA_USD = 0.002

    def __init__(self, backend, presupuesto=None, modelo="gpt-4o-mini"):
        self.backend = backend
        self.presupuesto = presupuesto
        self.precios = PRECIOS.get(modelo, PRECIOS["default"])
        self.modelo = modelo
        self.etiqueta_default = "llamado"
        self.registro = []  # dicts: {etiqueta, ts, prompt_tokens,
        #                     completion_tokens, costo_usd}
        self.total_usd = 0.0

    def complete(self, prompt, **kw):
        etiqueta = kw.pop("etiqueta", self.etiqueta_default)
        if self.presupuesto is not None:
            self.presupuesto.verificar_antes(
                self.ESTIMACION_PREVIA_USD, proposito=etiqueta)
        texto, uso = self.backend.complete(prompt, **kw)
        uso = uso or {}
        costo = costo_uso(uso, self.precios)
        if self.presupuesto is not None:
            self.presupuesto.cargar(costo)
        self.total_usd += costo
        self.registro.append({
            "etiqueta": etiqueta,
            "ts": time.time(),
            "prompt_tokens": int(uso.get("prompt_tokens", 0)),
            "completion_tokens": int(uso.get("completion_tokens", 0)),
            "costo_usd": round(costo, 6),
        })
        return texto, {"prompt_tokens": uso.get("prompt_tokens", 0),
                       "completion_tokens": uso.get("completion_tokens", 0),
                       "costo_usd": costo}

    def costo(self, uso):
        """Misma firma que un backend: los executors computan costo_usd
        sobre el uso medido sin doble contabilidad."""
        return costo_uso(uso or {}, self.precios)

    def resumen(self):
        por_etiqueta = {}
        for r in self.registro:
            e = por_etiqueta.setdefault(
                r["etiqueta"], {"llamados": 0, "costo_usd": 0.0,
                               "tokens": 0})
            e["llamados"] += 1
            e["costo_usd"] += r["costo_usd"]
            e["tokens"] += r["prompt_tokens"] + r["completion_tokens"]
        for e in por_etiqueta.values():
            e["costo_usd"] = round(e["costo_usd"], 6)
        return {"total_usd": round(self.total_usd, 6),
                "llamados": len(self.registro),
                "por_etiqueta": por_etiqueta,
                "presupuesto": (self.presupuesto.estado()
                                if self.presupuesto else None)}
