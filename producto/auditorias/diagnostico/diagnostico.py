#!/usr/bin/env python3
"""diagnostico.py -- Diagnostico inicial de costo de IA (oferta de auditoria).

Lee un CSV de trazas anonimizadas (ver FORMATO-TRAZAS.md), calcula el costo
actual por tipo de consulta, simula un router ex post que maximiza
calidad-por-dolar SIN perdida de calidad medida, y escribe un mini informe en
Markdown con la estimacion de ahorro y su intervalo de confianza por bootstrap.

Solo usa la biblioteca estandar. No promete ahorros: reporta lo medido.

Uso:
    python3 diagnostico.py trazas.csv \
        --tipo-mapa '{"consulta_stock":"simple","disputa_garantia":"razonamiento"}' \
        --volumen '{"consulta_stock":15000,"disputa_garantia":900}' \
        --salida informe.md
"""

import argparse
import csv
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date

# ---------------------------------------------------------------------------
# CONSTANTES EDITABLES -- revisar antes de cada uso
# ---------------------------------------------------------------------------
PRECIOS = {
    # USD por 1M de tokens. Precios aproximados de referencia publica (2026).
    # ACTUALIZAR contra el pricing publicado de cada proveedor antes de cada uso.
    "deepseek":     {"in": 0.27, "out": 1.10},
    "gpt-4o-mini":  {"in": 0.15, "out": 0.60},
    "claude-haiku": {"in": 1.00, "out": 5.00},
}

REF_REWARD = {
    # Fraccion de tareas resueltas correctamente por el verificador, medida en
    # NUESTROS oraculos (1.323 llamadas reales, sep-2026). NO son mediciones del
    # workload del cliente: la Auditoria Completa las re-mide sobre sus consultas.
    "deepseek":     {"simple": 0.63, "razonamiento": 0.97},
    "gpt-4o-mini":  {"simple": 0.30, "razonamiento": 1.00},
    "claude-haiku": {"simple": 0.38, "razonamiento": 1.00},
}
# ---------------------------------------------------------------------------

COLUMNAS = ["tipo_consulta", "tokens_in", "tokens_out", "latencia_ms",
            "resultado", "modelo_usado", "fecha"]
RESULTADOS = {"resuelta", "escalada", "repregunta"}
MIN_MUESTRA = 200


def fail(msg):
    sys.exit("ERROR: " + msg)


def cargar_trazas(path):
    filas = []
    with open(path, newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        campos = lector.fieldnames or []
        faltan = [c for c in COLUMNAS if c not in campos]
        if faltan:
            fail("columnas faltantes en el CSV: %s. Ver FORMATO-TRAZAS.md" % faltan)
        for i, r in enumerate(lector, start=2):
            try:
                tin = int(r["tokens_in"])
                tout = int(r["tokens_out"])
            except (ValueError, TypeError):
                fail("linea %d: tokens_in/tokens_out deben ser enteros." % i)
            if tin < 0 or tout < 0:
                fail("linea %d: tokens negativos." % i)
            res = (r["resultado"] or "").strip()
            if res not in RESULTADOS:
                fail("linea %d: resultado debe ser uno de %s." % (i, sorted(RESULTADOS)))
            mod = (r["modelo_usado"] or "").strip()
            if mod not in PRECIOS:
                fail("linea %d: modelo '%s' sin precio en la tabla PRECIOS. "
                     "Validos: %s (o agregarlo arriba del script)." % (i, mod, sorted(PRECIOS)))
            lat = (r["latencia_ms"] or "").strip()
            try:
                latencia = int(lat) if lat else None
            except ValueError:
                fail("linea %d: latencia_ms debe ser entero o vacio." % i)
            tipo = (r["tipo_consulta"] or "").strip()
            if not tipo:
                fail("linea %d: tipo_consulta vacio." % i)
            filas.append({
                "tipo": tipo, "tin": tin, "tout": tout, "latencia": latencia,
                "resultado": res, "modelo": mod, "fecha": (r["fecha"] or "").strip(),
            })
    if not filas:
        fail("el CSV no tiene filas de datos.")
    return filas


def costo_llamada(modelo, tin, tout):
    p = PRECIOS[modelo]
    return tin / 1e6 * p["in"] + tout / 1e6 * p["out"]


def estadisticas_por_tipo(filas):
    """Devuelve dict tipo -> metricas de la muestra."""
    grupos = defaultdict(list)
    for r in filas:
        grupos[r["tipo"]].append(r)
    stats = {}
    for tipo, rs in grupos.items():
        n = len(rs)
        costos = [costo_llamada(r["modelo"], r["tin"], r["tout"]) for r in rs]
        res = Counter(r["resultado"] for r in rs)
        mods = Counter(r["modelo"] for r in rs)
        lat = [r["latencia"] for r in rs if r["latencia"] is not None]
        fechas = sorted(r["fecha"] for r in rs if r["fecha"])
        stats[tipo] = {
            "n": n,
            "filas": rs,
            "costo_total": sum(costos),
            "costo_mediana_llamada": statistics.median(costos),
            "med_tin": statistics.median(r["tin"] for r in rs),
            "med_tout": statistics.median(r["tout"] for r in rs),
            "pct_resuelta": 100.0 * res.get("resuelta", 0) / n,
            "pct_escalada": 100.0 * res.get("escalada", 0) / n,
            "pct_repregunta": 100.0 * res.get("repregunta", 0) / n,
            "modelo_actual": mods.most_common(1)[0][0],
            "modelos": dict(mods),
            "lat_mediana": statistics.median(lat) if lat else None,
            "fecha_min": fechas[0] if fechas else "-",
            "fecha_max": fechas[-1] if fechas else "-",
        }
    return stats


def router_ex_post(stats, tipo_mapa):
    """Para cada tipo, elige el modelo elegible mas barato.

    Elegible = reward de referencia >= reward del modelo actual (sin perdida
    de calidad medida). Entre elegibles, el de menor costo por llamada
    (tokens medianos del tipo x precios). Si el actual ya es el mas barato,
    se recomienda mantener.
    """
    reco = {}
    for tipo, s in stats.items():
        if s["n"] < MIN_MUESTRA:
            reco[tipo] = {"excluido": "muestra insuficiente (< %d)" % MIN_MUESTRA}
            continue
        clase = tipo_mapa.get(tipo)
        if clase not in ("simple", "razonamiento"):
            reco[tipo] = {"excluido": "sin clase en --tipo-mapa (simple|razonamiento)"}
            continue
        actual = s["modelo_actual"]
        rw_actual = REF_REWARD[actual][clase]
        mejor, mejor_rw, mejor_costo = None, None, None
        for m in PRECIOS:
            rw = REF_REWARD.get(m, {}).get(clase)
            if rw is None or rw < rw_actual:
                continue  # sin perdida de calidad: solo igual o mejor reward
            c = costo_total_si(m, s["filas"])
            if mejor_costo is None or c < mejor_costo:
                mejor, mejor_rw, mejor_costo = m, rw, c
        assert mejor is not None  # el modelo actual siempre es elegible
        costo_actual_total = sum(costo_llamada(r["modelo"], r["tin"], r["tout"]) for r in s["filas"])
        costo_routed_total = costo_total_si(mejor, s["filas"])
        ahorro_muestra = max(0.0, costo_actual_total - costo_routed_total)
        reco[tipo] = {
            "modelo_actual": actual,
            "rw_actual": rw_actual,
            "modelo_reco": mejor,
            "rw_reco": mejor_rw,
            "costo_llamada_actual": costo_actual_total / s["n"],
            "costo_llamada_reco": costo_routed_total / s["n"],
            "ahorro_muestra": ahorro_muestra,
            "cambia": mejor != actual,
        }
    return reco


def costo_total_si(modelo, filas):
    """Costo total que habrian tenido estas filas si usaran `modelo`."""
    return sum(costo_llamada(modelo, r["tin"], r["tout"]) for r in filas)


def ahorro_total_mensual(stats, reco, volumen):
    """Escala el ahorro por llamada al volumen mensual declarado por tipo."""
    total = 0.0
    detalle = {}
    for tipo, s in stats.items():
        r = reco[tipo]
        if "excluido" in r:
            detalle[tipo] = 0.0
            continue
        vol = (volumen or {}).get(tipo)
        if not vol:
            detalle[tipo] = None  # sin volumen declarado: no se estima
            continue
        ahorro = r["ahorro_muestra"] / s["n"] * vol
        detalle[tipo] = ahorro
        total += ahorro
    return total, detalle


def bootstrap_ic(filas_por_tipo, tipo_mapa, volumen, B, semilla):
    """IC 95% del ahorro mensual por bootstrap estratificado por tipo."""
    rng = random.Random(semilla)
    totales = []
    for _ in range(B):
        remuestreo = []
        for tipo, rs in filas_por_tipo.items():
            remuestreo.extend(rng.choices(rs, k=len(rs)))
        st = estadisticas_por_tipo(remuestreo)
        rc = router_ex_post(st, tipo_mapa)
        tot, _ = ahorro_total_mensual(st, rc, volumen)
        totales.append(tot)
    totales.sort()
    lo = totales[int(0.025 * B)]
    hi = totales[int(0.975 * B)]
    return lo, hi, statistics.median(totales)


def fmt_usd(x):
    if x < 0.01:
        return "US$ %.6f" % x
    if x < 10:
        return "US$ %.4f" % x
    return "US$ %.2f" % x


def generar_informe(path_csv, stats, reco, volumen, ic, mediana_boot, cliente):
    L = []
    L.append("# Diagnostico inicial de costo de IA — informe")
    L.append("")
    L.append("- **Cliente:** %s" % cliente)
    L.append("- **Fecha del informe:** %s" % date.today().isoformat())
    L.append("- **Fuente:** `%s` (%d llamadas, %d tipos de consulta)"
             % (path_csv, sum(s["n"] for s in stats.values()), len(stats)))
    L.append("")
    L.append("## 1. Muestra por tipo de consulta")
    L.append("")
    L.append("| Tipo | n | Resuelta | Escalada | Repregunta | Modelo (principal) | Costo total muestra | Costo mediano/llamada |")
    L.append("|---|---|---|---|---|---|---|---|")
    for tipo in sorted(stats):
        s = stats[tipo]
        L.append("| %s | %d | %.1f%% | %.1f%% | %.1f%% | %s | %s | %s |" % (
            tipo, s["n"], s["pct_resuelta"], s["pct_escalada"], s["pct_repregunta"],
            s["modelo_actual"], fmt_usd(s["costo_total"]), fmt_usd(s["costo_mediana_llamada"])))
    L.append("")
    L.append("## 2. Router ex post (calidad-por-dolar, sin perdida de calidad)")
    L.append("")
    L.append("Regla: para cada tipo se elige el modelo mas barato cuyo reward de referencia "
             "sea **igual o mayor** al del modelo actual. Si el actual ya es el mas barato, se mantiene.")
    L.append("")
    L.append("| Tipo | Modelo actual (rw ref) | Recomendado (rw ref) | Costo/llamada actual | Costo/llamada reco | Ahorro en muestra |")
    L.append("|---|---|---|---|---|---|")
    for tipo in sorted(stats):
        r = reco[tipo]
        if "excluido" in r:
            L.append("| %s | — | — | — | — | *Excluido: %s* |" % (tipo, r["excluido"]))
            continue
        accion = "**cambiar**" if r["cambia"] else "mantener"
        L.append("| %s | %s (%.2f) | %s (%.2f) %s | %s | %s | %s |" % (
            tipo, r["modelo_actual"], r["rw_actual"], r["modelo_reco"], r["rw_reco"],
            accion, fmt_usd(r["costo_llamada_actual"]), fmt_usd(r["costo_llamada_reco"]),
            fmt_usd(r["ahorro_muestra"])))
    L.append("")
    L.append("## 3. Estimacion de ahorro mensual")
    L.append("")
    if volumen:
        total, detalle = ahorro_total_mensual(stats, reco, volumen)
        L.append("| Tipo | Volumen mensual declarado | Ahorro mensual estimado |")
        L.append("|---|---|---|")
        for tipo in sorted(stats):
            v = volumen.get(tipo)
            d = detalle[tipo]
            L.append("| %s | %s | %s |" % (
                tipo, str(v) if v else "no declarado",
                fmt_usd(d) if d is not None else "no estimable"))
        L.append("")
        L.append("- **Ahorro mensual estimado (tipos con volumen declarado): %s**" % fmt_usd(total))
        if ic:
            lo, hi = ic
            L.append("- **IC 95%% por bootstrap (%d replicas): [%s, %s]** (mediana %s)"
                     % (args.bootstrap, fmt_usd(lo), fmt_usd(hi), fmt_usd(mediana_boot)))
    else:
        L.append("Sin volumen mensual declarado no se estima ahorro mensual. "
                 "Ahorro por cada 1.000 llamadas (muestra):")
        L.append("")
        L.append("| Tipo | Ahorro / 1.000 llamadas |")
        L.append("|---|---|")
        for tipo in sorted(stats):
            r = reco[tipo]
            if "excluido" in r:
                L.append("| %s | *excluido* |" % tipo)
            else:
                L.append("| %s | %s |" % (tipo, fmt_usd(r["ahorro_muestra"] / stats[tipo]["n"] * 1000)))
    L.append("")
    L.append("## 4. Supuestos y limites (leer antes de citar un numero)")
    L.append("")
    L.append("- Los *rewards de referencia* se midieron en **nuestros** oraculos (1.323 llamadas, sep-2026), "
             "no en el workload del cliente. La Auditoria Completa los re-mide sobre sus consultas.")
    L.append("- Los precios por token son los de la tabla `PRECIOS` del script; verificar contra el pricing "
             "publicado antes de cada uso.")
    L.append("- La estimacion mensual escala linealmente el ahorro por llamada: supone mezcla de consultas "
             "estable en el tiempo.")
    L.append("- El bootstrap mide incertidumbre de muestreo, no error de modelo ni cambios de precios.")
    L.append("- Este diagnostico **no promete** ningun porcentaje de ahorro: reporta lo medido en la muestra.")
    L.append("")
    return "\n".join(L) + "\n"


def main():
    global args
    ap = argparse.ArgumentParser(description="Diagnostico inicial de costo de IA.")
    ap.add_argument("csv", help="CSV de trazas (ver FORMATO-TRAZAS.md)")
    ap.add_argument("--tipo-mapa", required=True,
                    help='JSON tipo_consulta -> "simple"|"razonamiento"')
    ap.add_argument("--volumen", default=None,
                    help='JSON tipo_consulta -> llamadas por mes (opcional)')
    ap.add_argument("--salida", default="informe-diagnostico.md",
                    help="Archivo Markdown de salida")
    ap.add_argument("--cliente", default="[CLIENTE]", help="Nombre del cliente para el informe")
    ap.add_argument("--bootstrap", type=int, default=2000, help="Replicas bootstrap (0 = omitir)")
    ap.add_argument("--semilla", type=int, default=42, help="Semilla aleatoria (reproducibilidad)")
    args = ap.parse_args()

    try:
        tipo_mapa = json.loads(args.tipo_mapa)
        volumen = json.loads(args.volumen) if args.volumen else None
    except json.JSONDecodeError as e:
        fail("JSON invalido en argumentos: %s" % e)
    for t, c in tipo_mapa.items():
        if c not in ("simple", "razonamiento"):
            fail("clase invalida para '%s': %s (usar simple|razonamiento)" % (t, c))

    filas = cargar_trazas(args.csv)
    stats = estadisticas_por_tipo(filas)
    reco = router_ex_post(stats, tipo_mapa)

    ic = None
    mediana_boot = None
    if args.bootstrap > 0 and volumen:
        filas_por_tipo = defaultdict(list)
        for r in filas:
            filas_por_tipo[r["tipo"]].append(r)
        lo, hi, mediana_boot = bootstrap_ic(filas_por_tipo, tipo_mapa, volumen,
                                            args.bootstrap, args.semilla)
        ic = (lo, hi)

    informe = generar_informe(args.csv, stats, reco, volumen, ic, mediana_boot, args.cliente)
    with open(args.salida, "w", encoding="utf-8") as f:
        f.write(informe)
    print("OK: %d llamadas, %d tipos. Informe en %s" % (
        len(filas), len(stats), args.salida))
    excluidos = [t for t in reco if "excluido" in reco[t]]
    if excluidos:
        print("Advertencia: tipos excluidos: %s" % excluidos)


if __name__ == "__main__":
    main()
