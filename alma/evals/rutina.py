"""Evals de rutina y de patrones con datos reales.

- rutina_manana: ¿ALMA predice qué ítems de la rutina se van a cumplir
  mañana? Ground truth: la rutina reportada por el usuario.
- patron_sostiene: ¿los patrones detectados en el estudio de patrones
  se sostienen contra datos NUEVOS? Es el meta-eval: valida que el
  "módulo 1 de ALMA" (detección de patrones) no alucina.
"""

import json
import os
from collections import defaultdict
from datetime import date, timedelta

from .base import EvalResult, accuracy

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ITEMS = ["despertar_8", "playa", "meditacion", "flexiones", "ingles",
         "gym", "bici", "futbol"]


def _cargar_rutina():
    with open(os.path.join(DATA_DIR, "rutina.json"), encoding="utf-8") as f:
        dias = json.load(f)
    dias = [d for d in dias if "fecha" in d]  # saltea la nota documental
    return sorted(dias, key=lambda d: d["fecha"])


def predecir_rutina_persistencia(historia):
    """Baseline: mañana = último día conocido (por ítem)."""
    ultimo = historia[-1]
    return {item: bool(ultimo.get(item)) for item in ITEMS
            if ultimo.get(item) is not None}


def eval_rutina_manana(predict_fn=None, fecha_objetivo=None):
    """Predice la rutina de `fecha_objetivo` usando solo la historia
    ANTERIOR a esa fecha. Por defecto evalúa la última fecha con ground
    truth (el pasado ya ocurrido: sin fuga de información).

    Si se pide una fecha futura sin ground truth, devuelve la predicción
    marcada como pendiente (no se guarda en el historial: lo no medido
    no puntúa).
    """
    dias = _cargar_rutina()
    if fecha_objetivo is None:
        fecha_objetivo = dias[-1]["fecha"]
    anteriores = [d for d in dias if d["fecha"] < fecha_objetivo]
    objetivo = next((d for d in dias if d["fecha"] == fecha_objetivo), None)

    if not anteriores:
        raise ValueError("sin historia previa para predecir")

    if predict_fn:
        pred = {k: bool(v) for k, v in predict_fn(anteriores).items()}
        metodo = "llm"
    else:
        pred = predecir_rutina_persistencia(anteriores)
        metodo = "baseline_persistencia"

    if objetivo is None:
        return EvalResult(
            eval_id="rutina_manana", score=0.0, metodo=metodo,
            detalle={"pendiente": True, "fecha_objetivo": fecha_objetivo,
                     "prediccion": pred,
                     "nota": "sin ground truth todavía; no puntúa"},
        )

    ys_true, ys_pred = [], []
    for item in ITEMS:
        real = objetivo.get(item)
        if real is None or item not in pred:
            continue  # lo no reportado no se evalúa
        ys_true.append(bool(real))
        ys_pred.append(bool(pred[item]))
    acc = accuracy(ys_true, ys_pred)
    return EvalResult(
        eval_id="rutina_manana",
        score=round(acc, 4),
        metodo=metodo,
        detalle={"fecha_objetivo": fecha_objetivo, "items_evaluados": len(ys_true)},
    )


# -- patrones: el meta-eval ---------------------------------------------------
def _cargar_crudos():
    with open(os.path.join(DATA_DIR, "transacciones_crudos.json"), encoding="utf-8") as f:
        return json.load(f)


def _flujos_ultimos_dias(txs, dias=60, hoy="2026-09-25", con_alquiler=True):
    """Devuelve (gastos_por_dia, ingresos_total, gastos_total) de los
    últimos `dias` en la cuenta corriente.

    con_alquiler=True: se incluye todo (para medir el flujo neto real,
      p. ej. el patrón 'la plata pasa').
    con_alquiler=False: se excluye el débito del alquiler (gasto fijo
      conocido; para patrones de *comportamiento*, p. ej. finde vs semana).
    """
    f0 = (date.fromisoformat(hoy) - timedelta(days=dias)).isoformat()
    gastos_dia = defaultdict(float)
    ing, gas = 0.0, 0.0
    for t in txs:
        f = t.get("date", "")
        if not (f0 <= f <= hoy):
            continue
        n, m = t.get("name", ""), t.get("amount", 0) or 0
        if not any(k in n for k in ("Zelle", "MOBILE", "CHECKCARD", "BKOFAMERICA", "ATM", "PURCHASE")):
            continue
        if m > 0:
            if not con_alquiler and "BKOFAMERICA" in n and "WITHDRWL" in n and m > 2000:
                continue
            gastos_dia[f] += m
            gas += m
        else:
            ing += -m
    return gastos_dia, ing, gas


def patron_fin_de_semana(gastos_dia):
    """'Gasta más los fines de semana': ratio gasto diario promedio
    finde vs día de semana. Sostiene si ratio > 1.15."""
    finde, semana = [], []
    for f, total in gastos_dia.items():
        (finde if date.fromisoformat(f).weekday() >= 5 else semana).append(total)
    if not semana:
        return False, 0.0
    pf = sum(finde) / len(finde) if finde else 0.0
    ps = sum(semana) / len(semana)
    ratio = pf / ps if ps else 0.0
    return ratio > 1.15, round(ratio, 3)


def patron_plata_pasa(ingresos, gastos):
    """'La plata pasa, no se queda': tasa de ahorro < 10%."""
    if ingresos <= 0:
        return False, 0.0
    tasa = (ingresos - gastos) / ingresos
    return tasa < 0.10, round(tasa, 3)


def patron_cargos_banco(txs, dias=60, hoy="2026-09-25"):
    """'Los cargos del banco existen': hubo cargos evitables
    (late fees, overdraft) en los últimos días."""
    f0 = (date.fromisoformat(hoy) - timedelta(days=dias)).isoformat()
    cargos = [t for t in txs
              if f0 <= t.get("date", "") <= hoy
              and any(k in t.get("name", "").upper()
                      for k in ("CARGO POR PAGO", "LATE FEE", "OVERDRAFT"))]
    total = sum(t["amount"] for t in cargos)
    return len(cargos) > 0, {"cantidad": len(cargos), "usd": round(total, 2)}


def eval_patron_sostiene():
    """¿Los patrones del estudio se sostienen con datos nuevos?

    Cada patrón es una hipótesis falsable con umbral explícito.
    Score = fracción de patrones que se sostienen. Si ALMA detecta
    patrones que no se sostienen, ESTE eval lo muestra.
    """
    txs = _cargar_crudos()
    gastos_dia, ing, gas = _flujos_ultimos_dias(txs, con_alquiler=True)
    gastos_dia_sin_alq, _, _ = _flujos_ultimos_dias(txs, con_alquiler=False)
    resultados = {}

    ok, efecto = patron_fin_de_semana(gastos_dia_sin_alq)
    resultados["fin_de_semana_gasta_mas"] = {"sostiene": ok, "ratio_finde_semana": efecto}

    ok, efecto = patron_plata_pasa(ing, gas)
    resultados["plata_pasa_no_se_queda"] = {"sostiene": ok, "tasa_ahorro": efecto}

    ok, efecto = patron_cargos_banco(txs)
    resultados["cargos_banco_existen"] = {"sostiene": ok, **efecto}

    sostiene = sum(1 for r in resultados.values() if r["sostiene"])
    return EvalResult(
        eval_id="patron_sostiene",
        score=round(sostiene / len(resultados), 4),
        metodo="verificacion_datos",
        detalle={"patrones": len(resultados), "sostenidos": sostiene,
                 **{k: v["sostiene"] for k, v in resultados.items()}},
    )
