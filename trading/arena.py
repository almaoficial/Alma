"""ARENA ALMA-trading: las versiones de ALMA compiten entre sí y contra
brazos fijos, en varias ventanas out-of-sample no solapadas.

Protocolo: ver ARENA_PREREGISTRO.md (escrito ANTES de correr). No se mueve.

Para que v3, v4, ... entren sin reescribir nada: agregar UNA entrada al
registro RETADORES con su factory (firma: f(precios, fechas, **params) ->
(banco, decisiones)) y su grilla de calibración. El resto (ventanas,
criterio, tabla) no cambia.

Papel, siempre: verificar_solo_papel() al inicio. US$0.
"""
import itertools
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datos import cargar_universo, recortar_por_fecha
from estrategias import BRAZOS
from alma_trading import correr_alma, correr_brazo_fijo
from alma_v3 import correr_alma_v3
from banco_papel import verificar_solo_papel

BASE = os.path.dirname(os.path.abspath(__file__))

VENTANAS = [
    ("2016-01-01", "2017-12-31"),
    ("2018-01-01", "2019-12-31"),
    ("2020-01-01", "2021-12-31"),
    ("2022-01-01", "2023-12-31"),
    ("2024-01-01", "2026-09-25"),
]
CALENTAMIENTO_DIAS = 126  # período efectivo = [inicio+126d hábiles, fin]
INICIO_DATOS = "2015-01-02"

FIJOS = ["hold", "momentum", "reversion", "cash"]

# Registro de retadores. v3 = agregar una entrada acá. Nada más cambia.
RETADORES = {
    "ALMA v1": {
        "factory": lambda p, f, **kw: correr_alma(p, f, version="v1", **kw),
        "grilla": {"ventana_probe": [42, 63],
                   "umbral_evi": [2.0, 3.0, 5.0],
                   "umbral_cd": [1.5, 2.0, 2.5]},
        "orden": 1,
    },
    "ALMA v2": {
        "factory": lambda p, f, **kw: correr_alma(p, f, version="v2", **kw),
        "grilla": {"ventana_probe": [42, 63],
                   "umbral_evi": [2.0, 3.0, 5.0],
                   "umbral_cd": [1.5, 2.0, 2.5],
                   "penalidad_churn": [0.0, 0.005, 0.01]},
        "orden": 2,
    },
    "ALMA v3": {
        # Sin parámetros tuneados: grilla vacía por diseño (addendum v3 en
        # ARENA_PREREGISTRO.md). La calibración corre trivialmente (1 combo).
        "factory": lambda p, f, **kw: correr_alma_v3(p, f, **kw),
        "grilla": {},
        "orden": 3,
    },
}

CAMPEON_INICIAL = "reversion"


def metricas(banco, fechas, i0, i1):
    """Retorno neto, Sharpe anualizado y max drawdown sobre fechas[i0..i1]."""
    desde, hasta = fechas[i0], fechas[i1]
    eq = [(f, p) for f, p in banco.equity if desde <= f <= hasta]
    if len(eq) < 2:
        return None
    ret_total = eq[-1][1] / eq[0][1] - 1.0
    rets = [eq[i][1] / eq[i - 1][1] - 1.0 for i in range(1, len(eq))]
    mu = sum(rets) / len(rets)
    var = sum((x - mu) ** 2 for x in rets) / max(1, len(rets) - 1)
    sharpe = (mu / math.sqrt(var) * math.sqrt(252)) if var > 0 else 0.0
    pico = eq[0][1]
    max_dd = 0.0
    for _, p in eq:
        pico = max(pico, p)
        max_dd = max(max_dd, pico / p - 1.0 if p > 0 else 0.0)
    return {"retorno_neto": ret_total, "sharpe": sharpe,
            "max_drawdown": max_dd, "dias": len(eq)}


def calibrar(nombre, spec, f_cal, p_cal):
    """Elige parámetros maximizando retorno neto en calibración (causal)."""
    nombres = list(spec["grilla"])
    mejor, mejor_r, mejor_p = None, float("-inf"), None
    for combo in itertools.product(*(spec["grilla"][k] for k in nombres)):
        params = dict(zip(nombres, combo))
        banco, _ = spec["factory"](p_cal, f_cal, **params)
        m = metricas(banco, f_cal, 0, len(f_cal) - 1)
        if m["retorno_neto"] > mejor_r:
            mejor, mejor_r, mejor_p = m, m["retorno_neto"], params
    return mejor_p


def cumple_vs(ret_r, dd_r, ret_c, dd_c):
    cond1 = ret_r > ret_c
    cond2 = dd_r <= (0.02 if dd_c == 0 else 1.2 * dd_c)
    return cond1 and cond2


def main():
    verificar_solo_papel()
    fechas, precios = cargar_universo()
    print(f"Universo: {sorted(precios)} | días: {len(fechas)} "
          f"({fechas[0]} → {fechas[-1]})", flush=True)

    res = {"ventanas": [], "campeon_inicial": CAMPEON_INICIAL,
           "asaltos": []}

    for ini, fin in VENTANAS:
        print(f"\n=== Ventana {ini} → {fin} ===", flush=True)
        f_cal, p_cal = recortar_por_fecha(fechas, precios, INICIO_DATOS,
                                          prev_day(ini, fechas))
        f_w, p_w = recortar_por_fecha(fechas, precios, ini, fin)
        i0 = CALENTAMIENTO_DIAS
        met = {}

        for nombre in sorted(RETADORES, key=lambda k: RETADORES[k]["orden"]):
            spec = RETADORES[nombre]
            params = calibrar(nombre, spec, f_cal, p_cal)
            banco, _ = spec["factory"](p_w, f_w, **params)
            met[nombre] = {"metricas": metricas(banco, f_w, i0, len(f_w) - 1),
                           "params": params}
            m = met[nombre]["metricas"]
            print(f"  {nombre:10s} params={params} "
                  f"ret={m['retorno_neto']:+.4f} dd={m['max_drawdown']:.4f}",
                  flush=True)

        for nombre in FIJOS:
            banco = correr_brazo_fijo(nombre, p_w, f_w)
            met["fijo_" + nombre] = {
                "metricas": metricas(banco, f_w, i0, len(f_w) - 1),
                "params": None}
            m = met["fijo_" + nombre]["metricas"]
            print(f"  {'fijo_' + nombre:10s} ret={m['retorno_neto']:+.4f} "
                  f"dd={m['max_drawdown']:.4f}", flush=True)

        res["ventanas"].append({"inicio": ini, "fin": fin,
                                "competidores": met})

    # --- Asaltos por el título (orden pre-registrado) ---
    campeon = CAMPEON_INICIAL
    for nombre in sorted(RETADORES, key=lambda k: RETADORES[k]["orden"]):
        ganadas = 0
        detalle = []
        for v in res["ventanas"]:
            mc = v["competidores"]["fijo_" + campeon
                                  if campeon in FIJOS else campeon]["metricas"]
            mr = v["competidores"][nombre]["metricas"]
            ok = cumple_vs(mr["retorno_neto"], mr["max_drawdown"],
                           mc["retorno_neto"], mc["max_drawdown"])
            ganadas += 1 if ok else 0
            detalle.append({"ventana": f"{v['inicio']}→{v['fin']}",
                            "gana_ventana": ok,
                            "ret_retador": mr["retorno_neto"],
                            "ret_campeon": mc["retorno_neto"],
                            "dd_retador": mr["max_drawdown"],
                            "dd_campeon": mc["max_drawdown"]})
        toma = ganadas >= 3
        res["asaltos"].append({"retador": nombre, "campeon_vigente": campeon,
                               "ventanas_ganadas": ganadas,
                               "toma_titulo": toma, "detalle": detalle})
        print(f"\nAsalto: {nombre} vs {campeon}: {ganadas}/5 ventanas "
              f"→ {'TOMA EL TÍTULO' if toma else 'no alcanza'}", flush=True)
        if toma:
            campeon = nombre

    res["campeon_final"] = campeon
    with open(os.path.join(BASE, "resultados_arena.json"), "w") as f:
        json.dump(res, f, indent=2)
    escribir_arena_md(res)
    print(f"\n===== CAMPEÓN FINAL: {campeon} =====")
    return campeon


def prev_day(fecha, fechas):
    """Última fecha de datos estrictamente anterior a `fecha`."""
    cands = [f for f in fechas if f < fecha]
    return cands[-1] if cands else fechas[0]


def escribir_arena_md(res):
    """Tabla de posiciones persistente, generada desde los resultados."""
    L = []
    L.append("# ARENA ALMA-trading — Tabla de posiciones (papel)")
    L.append("")
    L.append(f"Campeón defensor inicial: **reversión fija** "
             f"(+265,9% en 2021–2026).")
    L.append(f"**Campeón actual: {res['campeon_final']}**")
    L.append("")
    L.append("Protocolo: `ARENA_PREREGISTRO.md` (pre-registrado, sin mover). "
             "5 ventanas no solapadas; cada retador calibra solo con datos "
             "anteriores a la ventana. Período efectivo por ventana: "
             "inicio+126 días hábiles → fin.")
    L.append("")
    comps = []
    for v in res["ventanas"]:
        for c in v["competidores"]:
            if c not in comps:
                comps.append(c)
    # orden: retadores primero, luego fijos
    comps = ([c for c in comps if not c.startswith("fijo_")]
             + [c for c in comps if c.startswith("fijo_")])

    L.append("| Competidor | " + " | ".join(
        f"{v['inicio'][:4]}–{v['fin'][:4]} (ret / dd)" for v in res["ventanas"])
        + " | Ret medio | DD medio |")
    L.append("|" + "---|" * (len(res["ventanas"]) + 3))
    for c in comps:
        celdas = []
        rets, dds = [], []
        nombre_c = f"{c} 👑" if c == res["campeon_final"] else c
        for v in res["ventanas"]:
            m = v["competidores"][c]["metricas"]
            rets.append(m["retorno_neto"])
            dds.append(m["max_drawdown"])
            celdas.append(f"{m['retorno_neto']:+.1%} / {m['max_drawdown']:.2f}")
        L.append(f"| {nombre_c} | " + " | ".join(celdas)
                 + f" | {sum(rets)/len(rets):+.1%} | {sum(dds)/len(dds):.2f} |")
    L.append("")
    L.append("## Asaltos por el título")
    L.append("")
    for a in res["asaltos"]:
        L.append(f"- **{a['retador']}** vs {a['campeon_vigente']}: "
                 f"{a['ventanas_ganadas']}/5 ventanas "
                 f"→ {'🏆 TOMA EL TÍTULO' if a['toma_titulo'] else 'no destrona'}.")
        for d in a["detalle"]:
            L.append(f"  - {d['ventana']}: "
                     f"{'✓' if d['gana_ventana'] else '✗'} "
                     f"(ret {d['ret_retador']:+.1%} vs {d['ret_campeon']:+.1%}, "
                     f"dd {d['dd_retador']:.2f} vs {d['dd_campeon']:.2f})")
    L.append("")
    L.append("## Cómo entra un retador nuevo (v3, v4, ...)")
    L.append("")
    L.append("1. Agregar una entrada a `RETADORES` en `arena.py` con `factory` "
             "(firma `f(precios, fechas, **params) -> (banco, decisiones)`) y "
             "`grilla` de calibración.")
    L.append("2. Correr `python3 arena.py`. La tabla se regenera sola; el "
             "nuevo retador reta al campeón vigente en último lugar.")
    L.append("")
    L.append("_Papel: ningún resultado autoriza dinero real._")
    with open(os.path.join(BASE, "ARENA.md"), "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
