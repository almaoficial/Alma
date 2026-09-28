#!/usr/bin/env python3
"""ALMA EXP67-Claude-Full: replica del oraculo EXP67 con Claude.

180 problemas del stream (seccion `stream` del manifiesto) x 3 brazos
(single/cot/reflexion) x 2 intentos = 1080 pulls contra
claude-haiku-4-5-20251001 (snapshot pineado, mismo que EXP70).

Diseno y vara: ver preregistro.md (escrito ANTES de correr).
Freno duro: US$1,50 TOTAL (default). Regla anti-overshoot pre-registrada:
antes de cada pull se estima su costo (media observada de la celda si n>=5,
si no el prior MEDIDO del EXP70) y no se arranca si
gastado + estimado + SLACK > TOPE -> parada limpia con parcial (exit 2).

Auth: SOLO por surrogate del vault (custom.anthropic). Nunca ve/pide/
imprime/escribe ninguna key.

Uso:
    ~/workspace/venvs/exp67/bin/python claude_oracle.py --out <dir>
    ... --dry-run        # sin API: valida carga de problemas + scorers
    ... --tope 1.50      # freno duro en USD (default 1.50)
"""
import argparse
import json
import os
import sys
import time

EXP67_DIR = os.path.join(
    os.path.expanduser("~"),
    "workspace/alma-prototype/integracion_fase21/resultados/"
    "exp67-benchmark-real-20260927")
EXP70_DIR = os.path.join(
    os.path.expanduser("~"),
    "workspace/alma-prototype/integracion_fase21/resultados/"
    "exp70-claude-pilot-20260928")
EXP62_DIR = os.path.join(os.path.expanduser("~"),
                         "workspace/alma-prototype/exp62_deepseek")
sys.path.insert(0, EXP67_DIR)
sys.path.insert(0, EXP70_DIR)
sys.path.insert(0, EXP62_DIR)
sys.path.insert(0, os.path.join(os.path.expanduser("~"),
                                "workspace/alma-prototype"))

import pilot as P  # noqa: E402
from run_exp62 import ejecutar  # noqa: E402
from claude_pilot import (  # noqa: E402
    ClaudeBackend, MODEL, PRECIOS_HAIKU, MAX_TOKENS_POR_BRAZO)

ARMS = P.ARMS
N_INTENTOS = 2
FASE = "exp67-claude-oraculo"
TOPE_DEFAULT = 1.50
SLACK_PULL = 0.01  # no arrancar un pull que no entra con esta holgura

# Prior de costo por (slice, brazo): medias MEDIDAS del EXP70
# (gsm8k/mmlu n=8, mbpp n=5). Ver preregistro.md.
PRIOR_COSTO = {
    ("gsm8k", "single"): 0.000178,
    ("gsm8k", "cot"): 0.001475,
    ("gsm8k", "reflexion"): 0.002150,
    ("mmlu", "single"): 0.000245,
    ("mmlu", "cot"): 0.002055,
    ("mmlu", "reflexion"): 0.002794,
    ("mbpp", "single"): 0.000637,
    ("mbpp", "cot"): 0.002331,
    ("mbpp", "reflexion"): 0.003356,
}


class ParadaPorProyeccion(RuntimeError):
    """El freno amenaza: parada limpia con parcial (exit 2)."""


def estimar_pull(p, arm, pil):
    """Costo estimado del proximo pull en la celda (slice, arm).

    Media observada de la celda si ya hay >=5 pulls, si no el prior medido
    del EXP70 (pre-registrado)."""
    obs = [r["costo_usd"] for r in pil.hechos.values()
           if r["slice"] == p["slice"] and r["arm"] == arm]
    if len(obs) >= 5:
        return sum(obs) / len(obs)
    return PRIOR_COSTO[(p["slice"], arm)]


def total_proyectado(problemas, pil, hechos_keys):
    """gastado + suma de estimados de las celdas restantes."""
    tot = pil.gastado
    for p in problemas:
        for arm in ARMS:
            for i in range(N_INTENTOS):
                if (p["id"], arm, i) not in hechos_keys:
                    tot += estimar_pull(p, arm, pil)
    return tot


def resumen_oraculo(pulls, backend, gastado, tope, duracion_s, completa):
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
    mr_all = sum(r["reward"] for r in pulls) / len(pulls)
    mc_all = sum(r["costo_usd"] for r in pulls) / len(pulls)
    return {
        "experimento": "ALMA EXP67-Claude-Full: replica del oraculo EXP67",
        "proveedor": "anthropic",
        "modelo": MODEL,
        "precios_usd_por_1M": {"input": PRECIOS_HAIKU[0],
                               "output": PRECIOS_HAIKU[1]},
        "precios_fuente": "https://docs.anthropic.com/en/docs/about-claude/pricing (verificado 2026-09-28)",
        "fase": FASE,
        "diseno": {"problemas": 180, "brazos": ARMS, "intentos": N_INTENTOS,
                   "nota": "seccion stream del manifiesto EXP67, mismos "
                           "problemas que el oraculo DeepSeek"},
        "medicion": "COMPLETA" if completa else "PARCIAL",
        "pulls": len(pulls),
        "llamadas_api": backend.llamadas,
        "truncadas": backend.truncadas,
        "costo_total_usd": round(gastado, 4),
        "freno_usd": tope,
        "duracion_s": round(duracion_s, 1),
        "por_configuracion": por_config,
        "global": {
            "reward_medio": round(mr_all, 4),
            "costo_medio_usd": round(mc_all, 6),
            "reward_por_usd": round(mr_all / mc_all, 2) if mc_all > 0 else None,
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tope", type=float, default=TOPE_DEFAULT,
                    help="freno duro en USD (default 1.50)")
    args = ap.parse_args()
    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)

    print("== EXP67-Claude-Full: carga de problemas (seccion stream) ==")
    problemas = P.cargar_problemas(dry=args.dry_run, seccion="stream")
    print(f"   {len(problemas)} problemas "
          f"({sum(1 for p in problemas if p['slice'] == 'gsm8k')} gsm8k, "
          f"{sum(1 for p in problemas if p['slice'] == 'mmlu')} mmlu, "
          f"{sum(1 for p in problemas if p['slice'] == 'mbpp')} mbpp)")

    if args.dry_run:
        ok = P.chequeo_scorers()
        nada = not os.path.exists(os.path.join(args.out,
                                               "claude_oracle_pulls.jsonl"))
        print("   dry-run:", "VERDE" if (ok and nada) else
              "ROJO — revisar scorers o pulls residuales")
        return 0 if (ok and nada) else 1

    backend = ClaudeBackend()
    modelos = backend.ping()
    assert any(MODEL in (m or "") for m in modelos), \
        f"{MODEL} no visible en /v1/models"
    print("   ping /v1/models OK (gratis, via surrogate del vault)")

    pil = P.Piloto(args.out, fase=FASE, pulls_fname="claude_oracle_pulls.jsonl",
                   tope_usd=args.tope)
    total = len(problemas) * len(ARMS) * N_INTENTOS
    assert total == 1080, f"diseno roto: total={total}, esperado 1080"
    print(f"== oraculo claude: {total} pulls "
          f"(3 brazos x {N_INTENTOS} intentos x {len(problemas)}) ==")
    print(f"   freno duro US${args.tope:.2f} | slack por pull US${SLACK_PULL:.2f}")

    try:
        for p in problemas:
            for arm in ARMS:
                for i in range(N_INTENTOS):
                    key = (p["id"], arm, i)
                    if key in pil.hechos:
                        continue
                    # Regla anti-overshoot (pre-registrada): no arrancar un
                    # pull que no entra bajo el freno con holgura.
                    est = estimar_pull(p, arm, pil)
                    if pil.gastado + est + SLACK_PULL > args.tope:
                        raise ParadaPorProyeccion(
                            f"gastado ${pil.gastado:.4f} + pull estimado "
                            f"${est:.6f} + slack ${SLACK_PULL:.2f} > "
                            f"freno ${args.tope:.2f} "
                            f"({len(pil.hechos)}/{total} pulls)")
                    pil.pull(p, arm, i, backend, ejecutar)
            n_hechos = len(pil.hechos)
            if n_hechos and n_hechos % 60 == 0:
                proj = total_proyectado(problemas, pil, set(pil.hechos))
                print(f"   {n_hechos}/{total} pulls | "
                      f"gastado ${pil.gastado:.4f} | "
                      f"proyectado ${proj:.4f} | {time.time() - t0:.0f}s",
                      flush=True)
    except (RuntimeError, ParadaPorProyeccion) as e:
        print(f"\nPARADA POR FRENO/PROYECCION: {e}")
        print(f"   parcial: {len(pil.hechos)}/{total} pulls, "
              f"gastado ${pil.gastado:.4f} — sin resumen completo")
        return 2

    pulls = list(pil.hechos.values())
    res = resumen_oraculo(pulls, backend, pil.gastado, args.tope,
                          time.time() - t0, completa=True)
    with open(os.path.join(args.out, "claude_oracle_summary.json"), "w") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)

    print("\n================ ORACULO CLAUDE ================")
    for cfg, inf in res["por_configuracion"].items():
        print(f"  {cfg}: n={inf['n']} reward={inf['reward_medio']} "
              f"costo=${inf['costo_medio_usd']:.6f} "
              f"reward/USD={inf['reward_por_usd']}")
    g = res["global"]
    print(f"  GLOBAL: reward={g['reward_medio']} "
          f"costo=${g['costo_medio_usd']:.6f} reward/USD={g['reward_por_usd']}")
    print(f"  costo total: ${pil.gastado:.4f} | llamadas: {backend.llamadas} "
          f"| truncadas: {backend.truncadas} | {res['duracion_s']}s")
    print("=================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
