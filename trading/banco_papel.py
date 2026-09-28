"""Banco de papel + guardián anti-dinero-real.

Este módulo opera EXCLUSIVAMENTE en papel. No se conecta a ningún servicio
de trading, no acepta credenciales, no guarda claves. Si alguien intenta
agregarle dinero real, falla con un mensaje claro (ver `prohibir_dinero_real`).

Costos simulados: 0,10% (10 bps) por pata operada, sobre el nocional.
"""
import math

COSTO_POR_PATA = 0.001  # 10 bps


class DineroRealProhibido(Exception):
    """Se lanza si alguien intenta operar con dinero real."""


def prohibir_dinero_real(*args, **kwargs):
    """Cualquier intento de activar dinero real muere acá, con mensaje claro."""
    raise DineroRealProhibido(
        "ALMA-trading es SOLO papel. No hay intermediarios, no hay credenciales, "
        "no hay dinero real. Si querés operar de verdad, este no es el programa."
    )


class BancoPapel:
    """Portafolio en papel: efectivo + posiciones. Sin apalancamiento ni cortos."""

    def __init__(self, capital_inicial=10000.0):
        self._dinero_real = False  # inmutable; no hay setter
        self.capital_inicial = capital_inicial
        self.efectivo = capital_inicial
        self.posiciones = {}  # ticker -> cantidad de acciones
        self.equity = []  # lista de (fecha, patrimonio neto)

    def activar_dinero_real(self, *args, **kwargs):
        prohibir_dinero_real()

    def _precio(self, precios, ticker, t):
        return precios[ticker][t]

    def ejecutar(self, senal, precios, t, fecha):
        """Lleva el portafolio a la señal objetivo {ticker: peso}.

        Vende todo lo que no está en la señal, compra lo indicado.
        Cada pata paga COSTO_POR_PATA sobre el nocional operado.
        """
        # 1. Valuar posiciones actuales
        valor_pos = {tk: q * self._precio(precios, tk, t)
                     for tk, q in self.posiciones.items() if q > 0}
        patrimonio = self.efectivo + sum(valor_pos.values())

        # 2. Vender todo (una pata por posición cerrada)
        for tk, v in valor_pos.items():
            costo = v * COSTO_POR_PATA
            self.efectivo += v - costo
            patrimonio -= costo
        self.posiciones = {}

        # 3. Comprar según la señal (una pata por ticker comprado)
        for tk, peso in (senal or {}).items():
            if peso <= 0:
                continue
            nocional = patrimonio * peso
            if nocional <= 0:
                continue
            costo = nocional * COSTO_POR_PATA
            cantidad = (nocional - costo) / self._precio(precios, tk, t)
            self.posiciones[tk] = cantidad
            self.efectivo -= nocional
            patrimonio -= costo

        self.equity.append((fecha, patrimonio))
        return patrimonio

    def valuar(self, precios, t, fecha):
        """Registra el patrimonio sin operar (para los días sin rebalanceo)."""
        patrimonio = self.efectivo + sum(
            q * self._precio(precios, tk, t) for tk, q in self.posiciones.items())
        self.equity.append((fecha, patrimonio))
        return patrimonio


def verificar_solo_papel():
    """Auto-chequeo: este módulo no debe importar ni mencionar intermediarios reales."""
    import pathlib
    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    # Se excluye el bloque de la blocklist (si no, el guardián se mordería).
    lineas = []
    saltando = False
    for l in src.splitlines():
        if "for prohibida in [" in l:
            saltando = True
        if not saltando:
            lineas.append(l)
        if saltando and l.rstrip().endswith("]:"):
            saltando = False
    src = "\n".join(lineas)
    for prohibida in ["alpaca", "ibkr", "interactive", "api_key", "apikey",
                      "secret", "token", "broker"]:
        if prohibida in src.lower():
            raise DineroRealProhibido(
                f"Palabra prohibida en banco_papel.py: {prohibida!r}. "
                "Este programa es solo papel.")
    return True
