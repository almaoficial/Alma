"""Evals de finanzas con datos reales.

Tres evals, cada uno con baseline heurístico (sin LLM) y punto de
entrada para un predict_fn mejor (LLM/DSPy) que compita contra el
baseline con la misma vara.
"""

import json
import os
from collections import defaultdict
from datetime import date, timedelta

from .base import EvalResult, accuracy, precision_recall_f1, mape

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _cargar_etiquetas():
    with open(os.path.join(DATA_DIR, "gasto_etiquetas.json"), encoding="utf-8") as f:
        filas = json.load(f)
    # la primera fila puede ser una nota documental, no una etiqueta
    return [e for e in filas if "categoria" in e]


def _cargar_crudos():
    with open(os.path.join(DATA_DIR, "transacciones_crudos.json"), encoding="utf-8") as f:
        return json.load(f)


# -- baseline: categorizador por reglas ------------------------------------
REGLAS_CATEGORIA = [
    (("ZELLE",), lambda n, m: "ingresos" if "FROM" in n.upper() else "transf_persona"),
    (("BKOFAMERICA", "WITHDRWL"), lambda n, m: "alquiler" if m > 2000 else "otros"),
    (("BREEZELINE", "POWER", "FPL", "LAUNDRY", "APPLE.COM/BILL"), lambda n, m: "servicios"),
    (("FLAMINGO", "MERIDIAN", "SUPERMAR", "SUPERMARKET"), lambda n, m: "comida_super"),
    (("TST*", "BURGER", "FRIENDZ", "FOOD MARK"), lambda n, m: "comida_afuera"),
    (("CARGO POR PAGO", "LATE FEE", "OVERDRAFT"), lambda n, m: "cargos_banco"),
    (("STATEMENT CREDIT",), lambda n, m: "otros"),
    (("CITI BIKE",), lambda n, m: "transporte"),
]


def categorizar_baseline(nombre, monto):
    nu = nombre.upper()
    for claves, fn in REGLAS_CATEGORIA:
        if any(c in nu for c in claves):
            return fn(nombre, monto)
    return "otros"


def eval_categorizar_gastos(predict_fn=None):
    """¿ALMA clasifica los gastos como un humano que conoce al usuario?

    Ground truth: 31 transacciones reales etiquetadas a mano.
    Métrica: accuracy. Un método nuevo (LLM) se enchufa vía predict_fn
    con la misma firma (nombre, monto) -> categoria.
    """
    etiquetas = _cargar_etiquetas()
    predecir = predict_fn or categorizar_baseline
    ys_true = [e["categoria"] for e in etiquetas]
    ys_pred = [predecir(e["nombre"], e["monto"]) for e in etiquetas]
    acc = accuracy(ys_true, ys_pred)
    errores = sum(1 for t, p in zip(ys_true, ys_pred) if t != p)
    return EvalResult(
        eval_id="categorizar_gastos",
        score=round(acc, 4),
        metodo="llm" if predict_fn else "baseline_reglas",
        detalle={"n": len(etiquetas), "errores": errores,
                 "ejemplo_error": next(
                     ({"nombre": e["nombre"][:40], "real": t, "predicho": p}
                      for e, t, p in zip(etiquetas, ys_true, ys_pred) if t != p),
                     None)},
    )


# -- baseline: detector de anomalías ----------------------------------------
def _mediana(vals):
    vs = sorted(vals)
    n = len(vs)
    return vs[n // 2] if n else 0.0


def detectar_anomalia_baseline(nombre, monto, contexto_montos):
    """Marca anomalía si: es cargo bancario, o el monto supera 3x la
    mediana de su categoría, o supera US$150 en comida."""
    nu = nombre.upper()
    if any(k in nu for k in ("CARGO POR PAGO", "LATE FEE", "OVERDRAFT")):
        return True
    med = _mediana(contexto_montos) or 1.0
    if monto > 3 * med:
        return True
    if monto > 150 and any(k in nu for k in ("FOOD", "FLAMINGO", "MERIDIAN", "TST*")):
        return True
    return False


def eval_detectar_anomalia(predict_fn=None):
    """¿ALMA detecta lo raro? (late fees, compras 10x lo normal...).

    Ground truth: las mismas etiquetas, campo "anomalia".
    Métrica: F1 (las anomalías son raras: accuracy mentiría).
    """
    etiquetas = _cargar_etiquetas()
    montos = [abs(e["monto"]) for e in etiquetas if e["monto"] > 0]
    if predict_fn:
        ys_pred = [bool(predict_fn(e["nombre"], e["monto"])) for e in etiquetas]
        metodo = "llm"
    else:
        ys_pred = [detectar_anomalia_baseline(e["nombre"], e["monto"], montos)
                   for e in etiquetas]
        metodo = "baseline_reglas"
    ys_true = [bool(e.get("anomalia")) for e in etiquetas]
    prf = precision_recall_f1(ys_true, ys_pred, positivo=True)
    return EvalResult(
        eval_id="detectar_anomalia",
        score=prf["f1"],
        metodo=metodo,
        detalle={"n": len(etiquetas), "anomalias_reales": sum(ys_true),
                 **prf},
    )


# -- predicción de gasto semanal ---------------------------------------------
def _gasto_diario(txs, desde, hasta):
    """Suma por día lo que SALE (monto>0). Excluye movimientos únicos
    mayores a US$2.000 (alquiler y similares: gasto fijo conocido, no
    hay nada que predecir semana a semana)."""
    por_dia = defaultdict(float)
    for t in txs:
        f = t.get("date", "")
        if not (desde <= f <= hasta):
            continue
        m = t.get("amount", 0) or 0
        if m <= 0:
            continue  # entradas no cuentan como gasto
        if m > 2000:
            continue  # alquiler / movimientos extraordinarios
        por_dia[f] += m
    return por_dia


def predecir_gasto_semanal_baseline(por_dia_hist, dias=7, primer_dia=None):
    """Baseline: para cada día de la semana objetivo, la MEDIANA de lo
    gastado ese mismo día de semana en las 8 semanas previas.

    Mediana y no promedio: un día de derroche (p. ej. US$347 en
    anteojos) no contamina. Por día de semana: captura la estructura
    semanal si la hay. Sigue siendo un baseline tonto — un método con
    IA tiene que superarlo.
    """
    if not por_dia_hist or primer_dia is None:
        if not por_dia_hist:
            return 0.0
        # fallback: mediana global × días
        vals = sorted(por_dia_hist.values())
        return round(vals[len(vals) // 2] * dias, 2)
    por_dow = defaultdict(list)
    for f, total in por_dia_hist.items():
        por_dow[date.fromisoformat(f).weekday()].append(total)
    mediana_dow = {}
    for dow, vals in por_dow.items():
        vs = sorted(vals)
        mediana_dow[dow] = vs[len(vs) // 2]
    total = sum(mediana_dow.get((primer_dia + timedelta(days=i)).weekday(), 0.0)
                for i in range(dias))
    return round(total, 2)


def eval_gasto_semanal(predict_fn=None, fin_historia="2026-09-18"):
    """¿ALMA predice cuánto va a gastar la próxima semana?

    Ground truth: se congela la historia en `fin_historia` y se compara
    la predicción contra lo que REALMENTE se gastó los 7 días siguientes.
    Métrica: 1 - MAPE (mayor = mejor). Es un eval honesto porque el
    futuro ya ocurrió en los datos: no hay fuga de información.
    """
    txs = _cargar_crudos()
    ini = (date.fromisoformat(fin_historia) - timedelta(days=120)).isoformat()
    hist = _gasto_diario(txs, ini, fin_historia)
    f0 = date.fromisoformat(fin_historia) + timedelta(days=1)
    f1 = f0 + timedelta(days=6)
    real_d = _gasto_diario(txs, f0.isoformat(), f1.isoformat())
    # completar los 7 días (los ausentes = 0)
    real_total = sum(real_d.get((f0 + timedelta(days=i)).isoformat(), 0.0)
                     for i in range(7))
    if predict_fn:
        pred = float(predict_fn(hist))
        metodo = "llm"
    else:
        pred = predecir_gasto_semanal_baseline(hist, primer_dia=f0)
        metodo = "baseline_mediana_dow"
    err = mape(real_total, pred)
    score = round(1 - err, 4) if err is not None else 0.0
    return EvalResult(
        eval_id="gasto_semanal",
        score=max(score, 0.0),
        metodo=metodo,
        detalle={"semana": f"{f0}..{f1}", "real_usd": round(real_total, 2),
                 "predicho_usd": pred,
                 "mape": round(err, 4) if err is not None else None},
    )
