#!/usr/bin/env python3
"""Genera claude_oracle_summary.json a partir de los pulls en disco.

Uso: para el cierre PARCIAL del EXP67-Claude-Full (el script del oraculo solo
escribe el resumen ante MEDICION COMPLETA). Mismo esquema que
claude_oracle.py::resumen_oraculo, con medicion="PARCIAL".
No llama a la API: no gasta.
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
PULLS = os.path.join(BASE, "claude_oracle_pulls.jsonl")
SUMMARY = os.path.join(BASE, "claude_oracle_summary.json")
TOPE = 1.3972  # freno duro usado en esta corrida (ver preregistro + tarea)

ARMS = ["single", "cot", "reflexion"]


def main():
    pulls = []
    with open(PULLS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                pulls.append(json.loads(line))
    if not pulls:
        print("sin pulls", file=sys.stderr)
        return 1
    # Idempotencia: deduplicar por (pid, arm, intento) por si el jsonl tiene
    # duplicados de un append interrumpido.
    vistos = {}
    for r in pulls:
        vistos[(r["pid"], r["arm"], r["intento"])] = r
    pulls = list(vistos.values())

    celdas = {}
    for r in pulls:
        celdas.setdefault((r["slice"], r["arm"]), []).append(r)
    por_config = {}
    for (sl, arm), rs in sorted(celdas.items()):
        mr = sum(r["reward"] for r in rs) / len(rs)
        mc = sum(r["costo_usd"] for r in rs) / len(rs)
        por_config[f"{sl}/{arm}"] = {
            "n": len(rs),
            "reward_medio": round(mr, 4),
            "costo_medio_usd": round(mc, 6),
            "reward_por_usd": round(mr / mc, 2) if mc > 0 else None,
        }
    gastado = sum(r["costo_usd"] for r in pulls)
    mr_all = sum(r["reward"] for r in pulls) / len(pulls)
    mc_all = gastado / len(pulls)
    res = {
        "experimento": "ALMA EXP67-Claude-Full: replica del oraculo EXP67",
        "proveedor": "anthropic",
        "modelo": "claude-haiku-4-5-20251001",
        "precios_usd_por_1M": {"input": 1, "output": 5},
        "precios_fuente": "https://docs.anthropic.com/en/docs/about-claude/pricing (verificado 2026-09-28)",
        "fase": "exp67-claude-oraculo",
        "diseno": {"problemas": 180, "brazos": ARMS, "intentos": 2,
                   "nota": "seccion stream del manifiesto EXP67, mismos "
                           "problemas que el oraculo DeepSeek"},
        "medicion": "PARCIAL",
        "nota_cierre": ("resumen generado offline desde los pulls en disco: el "
                        "freno duro corto la corrida antes de los 1080 pulls; "
                        "sin veredicto comparativo (misma regla que EXP70)"),
        "pulls": len(pulls),
        "llamadas_api": len(pulls),
        "truncadas": None,
        "costo_total_usd": round(gastado, 4),
        "freno_usd": TOPE,
        "por_configuracion": por_config,
        "global": {
            "reward_medio": round(mr_all, 4),
            "costo_medio_usd": round(mc_all, 6),
            "reward_por_usd": round(mr_all / mc_all, 2) if mc_all > 0 else None,
        },
    }
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print(f"resumen parcial escrito: {len(pulls)} pulls, "
          f"gastado ${gastado:.4f}, {len(por_config)} celdas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
