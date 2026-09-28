#!/usr/bin/env python3
"""Siembra el registry con lo medido de Claude (EXP70-piloto + EXP67-Claude-Full).

Lee:
  - ../exp70-claude-pilot-20260928/claude_pulls.jsonl (63 pulls, campana exp70-piloto)
  - claude_oracle_summary.json (esta corrida, campana exp67-claude-full)

Agrega la entrada `anthropic` a alma_service/proveedores.yaml por INSERCION
DE TEXTO (preserva comentarios y procedencia existentes; NOTA.md opcion A
extendida a proveedor nuevo). Valida con registro.py::validar_documento.

No toca secretos: solo IDs y estadisticas medidas.
No toca el servicio vivo ni el nucleo.

Uso:
    ~/workspace/venvs/exp67/bin/python sembrar_claude.py   # --check para solo validar
"""
import argparse
import json
import os
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
EXP70_PULLS = os.path.join(
    os.path.dirname(BASE), "exp70-claude-pilot-20260928", "claude_pulls.jsonl")
SUMMARY = os.path.join(BASE, "claude_oracle_summary.json")
YAML_PATH = os.path.join(os.path.expanduser("~"),
                         "workspace/alma-prototype/integracion_fase21/"
                         "alma_service/proveedores.yaml")
ALMA_SERVICE = os.path.dirname(YAML_PATH)
sys.path.insert(0, ALMA_SERVICE)
from registro import validar_documento  # noqa: E402
import yaml  # noqa: E402

ORDEN = ["gsm8k", "mmlu", "mbpp"]
BRAZOS = ["single", "cot", "reflexion"]


def agregar_pulls(path):
    celdas = defaultdict(list)
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        celdas[(r["slice"], r["arm"])].append(r)
    return celdas


def linea_celda(sl, arm, rs):
    n = len(rs)
    mr = sum(r["reward"] for r in rs) / n
    mc = sum(r["costo_usd"] for r in rs) / n
    return (f"          {sl}/{arm}:" + " " * max(1, 14 - len(f"{sl}/{arm}:"))
            + f"{{n: {n}, reward_medio: {mr:.4f}, "
            f"costo_medio_usd: {mc:.6f}}}")


def bloque_proveedor(celdas_piloto, summary):
    lineas = []
    lineas.append("  - id: anthropic")
    lineas.append("    connector: custom.anthropic")
    lineas.append("    modelos: [claude-haiku-4-5-20251001]")
    lineas.append("    hosts_permitidos: [api.anthropic.com]")
    lineas.append("    ping_url: https://api.anthropic.com/v1/models")
    lineas.append("    credencial_entry: access_token")
    lineas.append("    habilitado: true")
    lineas.append("    estado:")
    lineas.append("      disponibilidad: disponible")
    lineas.append("      motivo: null")
    lineas.append("      fecha: null")
    lineas.append('    ultima_medicion: "2026-09-28"')
    # --- campana exp70-piloto
    n_piloto = sum(len(v) for v in celdas_piloto.values())
    costo_piloto = sum(r["costo_usd"] for v in celdas_piloto.values()
                       for r in v)
    lineas.append("    # Piloto EXP70 (madrugada 28/9): 63 pulls en 24 problemas")
    lineas.append("    # del subset pilot (8 gsm8k / 8 mmlu / 8 mbpp... mbpp parcial")
    lineas.append("    # n=5), claude-haiku-4-5-20251001, brazos por prompting")
    lineas.append("    # (single/cot/reflexion, max_tokens 256/1024/2048).")
    lineas.append("    # Precios lista verificados 28/9: 1/5 USD por 1M (in/out).")
    lineas.append("    # Fuente: resultados/exp70-claude-pilot-20260928/.")
    lineas.append("    # CAVEAT: n=8/5 por celda (piloto) — confianza menor que oraculo.")
    lineas.append("    mediciones:")
    lineas.append("      - campana: exp70-piloto")
    lineas.append('        fecha: "2026-09-28"')
    lineas.append(f'        fuente: "EXP70 piloto: {n_piloto} pulls, 24 problemas '
                  f"del subset pilot (disjuntos del stream del oraculo), "
                  f"claude-haiku-4-5-20251001, precios 1/5 USD por 1M (in/out), "
                  f"costo total US${costo_piloto:.4f}. n=8/5 por celda: "
                  f'confianza menor que oraculo"')
    lineas.append("        celdas:")
    for sl in ORDEN:
        for arm in BRAZOS:
            rs = celdas_piloto.get((sl, arm), [])
            if rs:
                lineas.append(linea_celda(sl, arm, rs))
    # --- campana exp67-claude-full
    por_config = summary["por_configuracion"]
    medicion = summary["medicion"]
    costo_total = summary["costo_total_usd"]
    n_total = summary["pulls"]
    caveat = "" if medicion == "COMPLETA" else (
        f" MEDICION PARCIAL ({n_total}/1080 pulls): n por celda desigual.")
    lineas.append("    # EXP67-Claude-Full (madrugada 28/9): replica del oraculo EXP67")
    lineas.append(f"    # ({n_total} pulls, seccion stream del manifiesto — mismos 180")
    lineas.append("    # problemas que el oraculo DeepSeek),")
    lineas.append("    # claude-haiku-4-5-20251001, 3 brazos x 2 intentos.")
    lineas.append("    # Fuente: resultados/exp67-claude-full-20260928/.")
    if caveat:
        lineas.append(f"    # CAVEAT:{caveat}")
    lineas.append("      - campana: exp67-claude-full")
    lineas.append('        fecha: "2026-09-28"')
    lineas.append(f'        fuente: "EXP67-Claude-Full ({medicion}): {n_total} pulls, '
                  f"180 problemas del stream (mismos que oraculo DeepSeek), "
                  f"claude-haiku-4-5-20251001, costo total US${costo_total:.4f}."
                  f"{caveat}\"")
    lineas.append("        celdas:")
    for sl in ORDEN:
        for arm in BRAZOS:
            cfg = por_config[f"{sl}/{arm}"]
            n = cfg["n"]
            mr = cfg["reward_medio"]
            mc = cfg["costo_medio_usd"]
            lineas.append(
                f"          {sl}/{arm}:" + " " * max(1, 14 - len(f"{sl}/{arm}:"))
                + f"{{n: {n}, reward_medio: {mr:.4f}, "
                f"costo_medio_usd: {mc:.6f}}}")
    return "\n".join(lineas) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="solo valida el YAML actual, no modifica")
    args = ap.parse_args()

    if args.check:
        with open(YAML_PATH, encoding="utf-8") as f:
            validar_documento(yaml.safe_load(f))
        print("YAML valido")
        return 0

    if not os.path.exists(SUMMARY):
        print(f"FALTA {SUMMARY}: la corrida no cerro todavia. "
              "No se siembra sin datos.", file=sys.stderr)
        return 1
    summary = json.load(open(SUMMARY, encoding="utf-8"))
    celdas_piloto = agregar_pulls(EXP70_PULLS)

    with open(YAML_PATH, encoding="utf-8") as f:
        texto = f.read()
    if "\n  - id: anthropic\n" in texto:
        print("anthropic ya esta en el registry: no se duplica. "
              "Revisar a mano si hace falta actualizar.", file=sys.stderr)
        return 1

    bloque = bloque_proveedor(celdas_piloto, summary)
    if not texto.endswith("\n"):
        texto += "\n"
    nuevo = texto + "\n" + bloque
    # Validar ANTES de escribir.
    validar_documento(yaml.safe_load(nuevo))
    with open(YAML_PATH, "w", encoding="utf-8") as f:
        f.write(nuevo)
    print("anthropic sembrado en proveedores.yaml (2 campanas).")
    print("Validacion de schema: OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
