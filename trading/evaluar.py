"""Evaluación con ética pre-registrada: calibrar en in-sample, veredicto en out-of-sample.

Protocolo (ver PREREGISTRO.md, escrito antes de correr):
  1. Calibrar (ventana_probe, umbral_evi, umbral_cd) solo en 2015-2020.
  2. Congelar parámetros.
  3. Correr ALMA + brazos fijos en 2015-2026; métricas del veredicto solo en 2021-2026.
  4. Veredicto numérico, sin mover la vara.
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
from banco_papel import verificar_solo_papel

IN_SAMPLE = ("2015-01-02", "2020-12-31")
OUT_SAMPLE = ("2021-01-01", "2026-09-25")

GRILLA = {
    "ventana_probe": [42, 63],
    "umbral_evi": [2.0, 3.0, 5.0],
    "umbral_cd": [1.5, 2.0, 2.5],
}


def metricas(banco, desde, hasta):
    """Retorno neto, Sharpe anualizado y max drawdown sobre [desde, hasta]."""
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
    return {"retorno_neto": ret_total, "sharpe": sharpe, "max_drawdown": max_dd,
            "dias": len(eq)}


def main():
    verificar_solo_papel()  # este programa es papel, siempre
    fechas, precios = cargar_universo()
    f_in, p_in = recortar_por_fecha(fechas, precios, *IN_SAMPLE)

    # --- 1. Calibración solo in-sample ---
    print("Calibrando en in-sample", IN_SAMPLE, flush=True)
    mejor, mejor_r = None, float("-inf")
    for vp, ue, uc in itertools.product(GRILLA["ventana_probe"],
                                       GRILLA["umbral_evi"],
                                       GRILLA["umbral_cd"]):
        banco, _ = correr_alma(p_in, f_in, ventana_probe=vp, umbral_evi=ue,
                               umbral_cd=uc)
        m = metricas(banco, *IN_SAMPLE)
        print(f"  vp={vp} evi={ue} cd={uc}: ret_in={m['retorno_neto']:.4f}",
              flush=True)
        if m["retorno_neto"] > mejor_r:
            mejor, mejor_r = (vp, ue, uc), m["retorno_neto"]
    vp, ue, uc = mejor
    print(f"Parámetros congelados: ventana_probe={vp}, umbral_evi={ue}, "
          f"umbral_cd={uc} (ret_in={mejor_r:.4f})", flush=True)

    # --- 2. Corrida completa con parámetros congelados ---
    resultados = {}
    banco_alma, decisiones = correr_alma(
        precios, fechas, ventana_probe=vp, umbral_evi=ue, umbral_cd=uc)
    resultados["alma"] = metricas(banco_alma, *OUT_SAMPLE)
    for nombre in BRAZOS:
        b = correr_brazo_fijo(nombre, precios, fechas)
        resultados["fijo_" + nombre] = metricas(b, *OUT_SAMPLE)

    # --- 3. Veredicto (criterio pre-registrado, no se mueve) ---
    a, h = resultados["alma"], resultados["fijo_hold"]
    cond1 = a["retorno_neto"] > h["retorno_neto"]
    cond2 = a["max_drawdown"] <= 1.2 * h["max_drawdown"]
    veredicto = "PASS" if (cond1 and cond2) else "FAIL"

    reporte = {
        "parametros_congelados": {"ventana_probe": vp, "umbral_evi": ue,
                                  "umbral_cd": uc},
        "in_sample": list(IN_SAMPLE), "out_sample": list(OUT_SAMPLE),
        "metricas_out_sample": resultados,
        "criterio": ("ret(ALMA)>ret(hold) y maxDD(ALMA)<=1.2*maxDD(hold); "
                     f"cond1={cond1}, cond2={cond2}"),
        "veredicto": veredicto,
        "n_decisiones_alma": len(decisiones),
    }
    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, "resultados_corrida1.json"), "w") as f:
        json.dump(reporte, f, indent=2)
    with open(os.path.join(base, "decisiones_alma.json"), "w") as f:
        json.dump(decisiones, f, indent=2)

    print("\n===== VEREDICTO (out-of-sample, parámetros congelados) =====")
    for k, m in resultados.items():
        print(f"  {k:14s} ret={m['retorno_neto']:+.4f} "
              f"sharpe={m['sharpe']:+.3f} maxDD={m['max_drawdown']:.4f}")
    print(f"  -> {veredicto}  [{reporte['criterio']}]")
    return veredicto


if __name__ == "__main__":
    main()
