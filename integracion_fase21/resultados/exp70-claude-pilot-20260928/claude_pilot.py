#!/usr/bin/env python3
"""ALMA-EXP70 piloto Claude (medicion para el registry de proveedores).

24 problemas del subset pilot (8 por slice: PRIMEROS 8 de cada slice en el
orden del manifiesto, sin cherry-picking) x 3 brazos x 1 intento = 72
llamadas contra claude-haiku-4-5-20251001 (snapshot pineado).

Espejo del piloto OpenAI del EXP69: mismos problemas del manifiesto, mismos
brazos por prompting (single/cot/reflexion, disciplina EXP1-9), mismos
max_tokens por brazo (256/1024/2048, presupuestos de EXP62).

DIFERENCIAS DOCUMENTADAS vs EXP69 (ver preregistro.md):
- N_INTENTOS=1 (no 2): haiku cuesta ~7x gpt-4o-mini por token (pricing
  verificado en docs oficiales 2026-09-28: $1/$5 por MTok). 180 llamadas
  proyectaban ~US$0,20 > freno US$0,10. 72 llamadas proyectan ~US$0,08.
- 24 problemas (no 30): mismo motivo de presupuesto.
- La replica completa del oraculo (180 problemas x 3 x 2 = 1080 llamadas)
  costaria ~US$1,20 en haiku: NO recomendada sin aprobacion separada.

Auth: SOLO por surrogate del vault (conector custom.anthropic, patron del
skill anthropic). Este script nunca ve, pide, imprime ni escribe ninguna key.

Freno duro: US$0,10 TOTAL por default (--tope lo ajusta). Aborta limpio con
parcial si se alcanza (exit 2).

Uso:
    ~/workspace/venvs/exp67/bin/python claude_pilot.py --out <dir>
    ... claude_pilot.py --out <dir> --dry-run   # sin API: valida problemas+scorers
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

EXP67_DIR = os.path.join(
    os.path.expanduser("~"),
    "workspace/alma-prototype/integracion_fase21/resultados/"
    "exp67-benchmark-real-20260927")
EXP62_DIR = os.path.join(os.path.expanduser("~"),
                         "workspace/alma-prototype/exp62_deepseek")
sys.path.insert(0, EXP67_DIR)
sys.path.insert(0, EXP62_DIR)
sys.path.insert(0, os.path.join(os.path.expanduser("~"),
                                "workspace/alma-prototype"))
sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")

from dynamic_credentials import (
    add_surrogate_to_request,
    read_json_response,
    DynamicCredentialError,
)
from alma.backends import LLMBackend, BackendError, con_reintento

import pilot as P  # noqa: E402  (cargar_problemas, puntuar, Piloto, ARMS...)
from run_exp62 import ejecutar  # noqa: E402

BASE_URL = "https://api.anthropic.com"
# Snapshot pineado descubierto via GET /v1/models el 2026-09-28
# (el alias claude-haiku-4-5 no aparecia en el listado).
MODEL = "claude-haiku-4-5-20251001"
ALLOWED_HOSTS = ["api.anthropic.com"]
CONNECTOR = "custom.anthropic"

# Precios claude-haiku-4-5, USD por 1M tokens (in, out).
# VERIFICADOS 2026-09-28 en https://docs.anthropic.com/en/docs/about-claude/pricing
# (pagina oficial, leida en vivo): Haiku 4.5 = $1 / $5.
PRECIOS_HAIKU = (1.0, 5.0)

# Presupuesto de tokens por brazo (replica los max_tokens de EXP62/EXP69).
MAX_TOKENS_POR_BRAZO = {"single": 256, "cot": 1024, "reflexion": 2048}

ARMS = P.ARMS
N_INTENTOS = 1
N_POR_SLICE = 8
FASE = "exp70-claude"


class ClaudeBackend(LLMBackend):
    """Backend Messages API contra api.anthropic.com.

    Auth SOLO por surrogate del vault (custom.anthropic): la key nunca pasa por
    este proceso como valor visible.
    """

    def __init__(self, model=MODEL, precios=PRECIOS_HAIKU):
        self.model = model
        self.precios = precios
        self.llamadas = 0
        self.truncadas = 0

    def _request_con_credencial(self, url, data=None, method="GET",
                                extra_headers=None):
        headers = {"Content-Type": "application/json",
                   "anthropic-version": "2023-06-01"}
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method=method)
        try:
            add_surrogate_to_request(
                req, CONNECTOR, entry_name="access_token",
                allowed_hosts=ALLOWED_HOSTS)
        except DynamicCredentialError as e:
            raise BackendError(f"credencial {CONNECTOR} no disponible: {e}")
        return req

    def ping(self):
        """GET /v1/models: valida auth sin gastar tokens."""
        req = self._request_con_credencial(f"{BASE_URL}/v1/models")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = read_json_response(resp)
        except Exception as e:
            raise BackendError(f"ping /v1/models fallo: {e}")
        return [m.get("id") for m in data.get("data", [])]

    def costo(self, uso):
        pin, pout = self.precios
        return (uso["prompt_tokens"] * pin / 1e6
                + uso["completion_tokens"] * pout / 1e6)

    def complete(self, prompt, system=None, problem_id=None, arch_id=None,
                 modo=None, intento=0, idx=0, formato=None):
        max_tokens = MAX_TOKENS_POR_BRAZO.get(arch_id or "",
                                              MAX_TOKENS_POR_BRAZO["cot"])
        return con_reintento(
            lambda: self._complete_una_vez(prompt, system, max_tokens),
            intentos=6, base_s=3.0,
            que=f"anthropic {self.model}/{arch_id}")

    def _complete_una_vez(self, prompt, system, max_tokens):
        # La API de Anthropic NO tiene rol system dentro de messages:
        # el system prompt va como campo top-level.
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        body = json.dumps(payload).encode("utf-8")
        req = self._request_con_credencial(
            f"{BASE_URL}/v1/messages", data=body, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = read_json_response(resp)
        except urllib.error.HTTPError as e:
            # 401/403/404 y 400: no reintentables.
            raise BackendError(f"HTTP {e.code} en {BASE_URL}: "
                               f"error no reintentable")
        except Exception as e:
            raise BackendError(f"fallo el llamado a {BASE_URL}: connection "
                               f"transitoria ({type(e).__name__}: {e})")
        try:
            bloques = data.get("content", [])
            texto = "".join(b.get("text", "") for b in bloques
                            if b.get("type") == "text")
            usage = data.get("usage", {})
            if data.get("stop_reason") == "max_tokens":
                self.truncadas += 1
        except (KeyError, IndexError, AttributeError) as e:
            raise BackendError(f"respuesta inesperada de la API: {e}")
        uso = {
            "prompt_tokens": int(usage.get("input_tokens", 0)),
            "completion_tokens": int(usage.get("output_tokens", 0)),
        }
        self.llamadas += 1
        return texto, uso


# ---------------------------------------------------------------- resumen

def resumen_claude(pulls, backend, gastado, tope, duracion_s):
    """Agrega por (slice, brazo): reward medio, costo medio, reward/USD.
    Formato compatible con el registry de proveedores (ver
    alma_service/proveedores.yaml). NO calcula veredicto comparativo."""
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
            "costo_mediana_usd": round(
                sorted(r["costo_usd"] for r in rs)[len(rs) // 2], 6),
            "reward_por_usd": round(mr / mc, 2) if mc > 0 else None,
        }
    mr_all = sum(r["reward"] for r in pulls) / len(pulls)
    mc_all = sum(r["costo_usd"] for r in pulls) / len(pulls)
    return {
        "experimento": "ALMA-EXP70 piloto Claude (medicion para registry)",
        "proveedor": "anthropic",
        "modelo": MODEL,
        "precios_usd_por_1M": {"input": PRECIOS_HAIKU[0],
                               "output": PRECIOS_HAIKU[1]},
        "precios_fuente": "https://docs.anthropic.com/en/docs/about-claude/pricing (verificado 2026-09-28)",
        "fase": FASE,
        "diseno": {"problemas_por_slice": N_POR_SLICE, "brazos": ARMS,
                   "intentos": N_INTENTOS,
                   "nota": "subset pilot, primeros 8 por slice en orden de manifiesto"},
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


def subset_pilot(problemas, n_por_slice=N_POR_SLICE):
    """Primeros n problemas de cada slice en el orden del manifiesto."""
    por_slice = {}
    for p in problemas:
        por_slice.setdefault(p["slice"], []).append(p)
    out = []
    for sl in ("gsm8k", "mmlu", "mbpp"):
        out.extend(por_slice.get(sl, [])[:n_por_slice])
    return out


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tope", type=float, default=0.10,
                    help="freno duro en USD (default 0.10)")
    args = ap.parse_args()
    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)

    print("== EXP70 piloto Claude: carga de problemas ==")
    problemas = P.cargar_problemas(dry=args.dry_run, seccion="pilot")
    problemas = subset_pilot(problemas)
    print(f"   {len(problemas)} problemas "
          f"({sum(1 for p in problemas if p['slice'] == 'gsm8k')} gsm8k, "
          f"{sum(1 for p in problemas if p['slice'] == 'mmlu')} mmlu, "
          f"{sum(1 for p in problemas if p['slice'] == 'mbpp')} mbpp)")

    if args.dry_run:
        ok = P.chequeo_scorers()
        nada = not os.path.exists(os.path.join(args.out,
                                               "claude_pulls.jsonl"))
        print("   dry-run:", "VERDE" if (ok and nada) else
              "ROJO — revisar scorers o pulls residuales")
        return 0 if (ok and nada) else 1

    backend = ClaudeBackend()
    modelos = backend.ping()
    assert any(MODEL in (m or "") for m in modelos), \
        f"{MODEL} no visible en /v1/models"
    print("   ping /v1/models OK (gratis, via surrogate del vault)")

    pil = P.Piloto(args.out, fase=FASE, pulls_fname="claude_pulls.jsonl",
                   tope_usd=args.tope)
    total = len(problemas) * len(ARMS) * N_INTENTOS
    hecho_nuevos = 0

    print(f"== piloto claude: {total} pulls "
          f"(3 brazos x {N_INTENTOS} intento x {len(problemas)}) ==")
    try:
        for p in problemas:
            for arm in ARMS:
                for i in range(N_INTENTOS):
                    r, nuevo = pil.pull(p, arm, i, backend, ejecutar)
                    if nuevo:
                        hecho_nuevos += 1
            if hecho_nuevos and hecho_nuevos % 12 == 0:
                print(f"   {len(pil.hechos)}/{total} pulls | "
                      f"gastado ${pil.gastado:.4f} | {time.time() - t0:.0f}s",
                      flush=True)
    except RuntimeError as e:
        print(f"\nABORTO POR FRENO: {e}")
        print(f"   parcial: {len(pil.hechos)} pulls, "
              f"gastado ${pil.gastado:.4f} — sin resumen ni veredicto")
        return 2

    pulls = list(pil.hechos.values())
    res = resumen_claude(pulls, backend, pil.gastado, args.tope,
                         time.time() - t0)
    with open(os.path.join(args.out, "claude_summary.json"), "w") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)

    print("\n================ RESUMEN CLAUDE ================")
    for cfg, inf in res["por_configuracion"].items():
        print(f"  {cfg}: n={inf['n']} reward={inf['reward_medio']} "
              f"costo=${inf['costo_medio_usd']:.6f} "
              f"reward/USD={inf['reward_por_usd']}")
    g = res["global"]
    print(f"  GLOBAL: reward={g['reward_medio']} "
          f"costo=${g['costo_medio_usd']:.6f} reward/USD={g['reward_por_usd']}")
    print(f"  costo total: ${pil.gastado:.4f} | llamadas: {backend.llamadas} "
          f"| truncadas: {backend.truncadas} | {res['duracion_s']}s")
    print("================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
