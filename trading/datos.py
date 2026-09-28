"""Carga de precios diarios (cierres ajustados) desde CSVs cacheados.

Fuente: Yahoo Finance (gratuito, sin API key). Los CSVs ya están descargados
en trading/data/. Este módulo NO descarga nada en la evaluación: trabaja con
lo cacheado para que la corrida sea reproducible y US$0.
"""
import csv
import os

DIR_DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
# v2: se agregan XLE (ETF energía: perdedor 2015-2020, ganador 2021-2022) y
# GE (colapso 2017-2018, nunca se recuperó del todo). El universo v1 tenía
# solo ganadores conocidos a posteriori (sesgo de supervivencia); estos dos
# se eligen por razones estructurales (perdedor sostenido + flip de régimen),
# no por su efecto en el veredicto — que aún no existe al escribir esto.
TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "TSLA", "XLE", "GE"]


def cargar_universo(tickers=TICKERS):
    """Devuelve (fechas, precios) alineados en el calendario común.

    fechas: lista de 'YYYY-MM-DD' (solo días donde TODOS los tickers cotizan).
    precios: dict ticker -> lista de cierres ajustados (float), alineada con fechas.
    """
    series = {}
    for t in tickers:
        ruta = os.path.join(DIR_DATOS, f"{t}.csv")
        with open(ruta, encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
        series[t] = {r["fecha"]: float(r["cierre_ajustado"]) for r in filas}

    comunes = sorted(set.intersection(*(set(s) for s in series.values())))
    precios = {t: [series[t][f] for f in comunes] for t in tickers}
    return comunes, precios


def recortar_por_fecha(fechas, precios, desde, hasta):
    """Recorta a [desde, hasta] inclusive. Fechas 'YYYY-MM-DD'."""
    idx = [i for i, f in enumerate(fechas) if desde <= f <= hasta]
    fechas2 = [fechas[i] for i in idx]
    precios2 = {t: [precios[t][i] for i in idx] for t in precios}
    return fechas2, precios2
