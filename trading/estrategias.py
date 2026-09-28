"""Brazos = estrategias simples, cada una explicable en una línea.

Cada brazo es una función pura: dado el historial de precios HASTA el día t
(sin mirar el futuro), devuelve el portafolio objetivo {ticker: peso}.
El efectivo es el resto (1 - suma de pesos). Nada de apalancamiento, nada de
cortos: honestidad antes que sofisticación.
"""
from datos import TICKERS


def _retorno(precios_ticker, t, ventana):
    """Retorno simple sobre `ventana` días hábiles terminando en t (exclusive)."""
    if t < ventana:
        return None
    p0 = precios_ticker[t - ventana]
    p1 = precios_ticker[t]
    return p1 / p0 - 1.0


def brazo_hold(precios, t):
    """Buy & hold SPY desde el día 0. La línea base contra la que todo se mide."""
    return {"SPY": 1.0}


def brazo_momentum(precios, t, ventana=63):
    """Cada rebalanceo, tener la acción con mejor retorno de 63 días; si todas caen, efectivo."""
    mejor, mejor_r = None, 0.0
    for ticker in TICKERS:
        r = _retorno(precios[ticker], t, ventana)
        if r is None:
            return {}
        if r > mejor_r:
            mejor, mejor_r = ticker, r
    return {mejor: 1.0} if mejor else {}


def brazo_reversion(precios, t, ventana=21):
    """Cada rebalanceo, comprar la perdedora de 21 días (reversión a la media)."""
    peor, peor_r = None, float("inf")
    for ticker in TICKERS:
        r = _retorno(precios[ticker], t, ventana)
        if r is None:
            return {}
        if r < peor_r:
            peor, peor_r = ticker, r
    return {peor: 1.0}


def brazo_cash(precios, t):
    """Quedarse en efectivo. El brazo que dice 'no sé'."""
    return {}


BRAZOS = {
    "hold": brazo_hold,
    "momentum": brazo_momentum,
    "reversion": brazo_reversion,
    "cash": brazo_cash,
}
