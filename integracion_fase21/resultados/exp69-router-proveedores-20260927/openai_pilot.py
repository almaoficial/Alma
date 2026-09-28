#!/usr/bin/env python3
"""ALMA-EXP69 piloto OpenAI (router de proveedores).

30 problemas del pilot (10 por slice) x 3 brazos x 2 intentos = 180 llamadas
contra gpt-4o-mini. Espejo del piloto DeepSeek de EXP67: mismos problemas del
manifiesto, mismos brazos.

ASIMETRIA DOCUMENTADA (preregistro.md): en gpt-4o-mini NO hay knob de
reasoning-effort como en deepseek-flash; los brazos son por prompting
(single/cot/reflexion, disciplina EXP1-9) y el arch_id es solo etiqueta. El
router compara configuraciones (proveedor x politica), que es la abstraccion
correcta. Los max_tokens por brazo replican los presupuestos de EXP62
(256/1024/2048) para disciplina de costo comparable.

Auth: SOLO por surrogate del vault (conector custom.openai, patron del skill
openai). Este script nunca ve, pide, imprime ni escribe ninguna key.

Freno duro: US$0,25 TOTAL por default (--tope lo ajusta). Aborta limpio con
parcial si se alcanza (exit 2).

Uso:
    ~/workspace/venvs/exp67/bin/python openai_pilot.py --out <dir>
    ... openai_pilot.py --out <dir> --dry-run   # sin API: valida problemas+scorers
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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# el paquete alma vive en ~/workspace/alma-prototype/
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

BASE_URL = "https://api.openai.com"
MODEL = "gpt-4o-mini"
ALLOWED_HOSTS = ["api.openai.com"]
CONNECTOR = "custom.openai"

# Precios gpt-4o-mini, USD por 1M tokens (in, out).
# Fuentes verificadas 2026-09-27: Requesty (actualizado 27/9/2026),
# model card de SAS (Azure OpenAI), rate card de conductai, doc de
# ai-engineering-sheet — las cuatro coinciden: $0.15 / $0.60.
PRECIOS_GPT4O_MINI = (0.15, 0.60)

# Presupuesto de tokens por brazo (replica los max_tokens de EXP62;
# en OpenAI el esfuerzo viene del prompting, no de un dial).
MAX_TOKENS_POR_BRAZO = {"single": 256, "cot": 1024, "reflexion": 2048}

ARMS = P.ARMS
N_INTENTOS = P.N_INTENTOS
FASE = "exp69-openai"


class OpenAIBackend(LLMBackend):
    """Backend OpenAI-compatible contra api.openai.com.

    Auth SOLO por surrogate del vault (custom.openai): la key nunca pasa por
    este proceso como valor visible.
    """

    def __init__(self):
        self.model = MODEL
        self.precios = PRECIOS_GPT4O_MINI
        self.llamadas = 0
        self.truncadas = 0

    def _request_con_credencial(self, url, data=None, method="GET"):
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
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

    def complete(self, prompt, system=None, problem_id=None, arch_id=None,
                 modo=None, intento=0, idx=0, formato=None):
        # Sin dial de esfuerzo en este proveedor: el brazo es solo etiqueta
        # (el prompting de cada runner hace el trabajo). Se respeta el
        # presupuesto de tokens por brazo de EXP62.
        max_tokens = MAX_TOKENS_POR_BRAZO.get(arch_id or "",
                                              MAX_TOKENS_POR_BRAZO["cot"])
        return con_reintento(
            lambda: self._complete_una_vez(prompt, system, max_tokens),
            intentos=6, base_s=3.0,
            que=f"openai {self.model}/{arch_id}")

    def _complete_una_vez(self, prompt, system, max_tokens):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        body = json.dumps(payload).encode("utf-8")
        req = self._request_con_credencial(
            f"{BASE_URL}/v1/chat/completions", data=body, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = read_json_response(resp)
        except urllib.error.HTTPError as e:
            # 401/403/404 y 400: no reintentables (sin palabra "connection"
            # para que con_reintento aborte de inmediato).
            raise BackendError(f"HTTP {e.code} en {BASE_URL}: "
                               f"error no reintentable")
        except Exception as e:
            raise BackendError(f"fallo el llamado a {BASE_URL}: connection "
                               f"transitoria ({type(e).__name__}: {e})")
        try:
            choice = data["choices"][0]
            texto = choice["message"]["content"] or ""
            usage = data.get("usage", {})
            if choice.get("finish_reason") == "length":
                self.truncadas += 1
        except (KeyError, IndexError) as e:
            raise BackendError(f"respuesta inesperada de la API: {e}")
        uso = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
        }
        self.llamadas += 1
        return texto, uso


# ---------------------------------------------------------------- resumen

def resumen_openai(pulls, backend, gastado, tope, duracion_s):
    """Agrega por (slice, brazo): reward medio, costo medio, reward/USD.
    Tambien global por proveedor. NO calcula veredicto (lo hace el padre
    al comparar con los datos DeepSeek)."""
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
        "experimento": "ALMA-EXP69 piloto OpenAI (router de proveedores)",
        "proveedor": "openai",
        "modelo": MODEL,
        "precios_usd_por_1M": {"input": PRECIOS_GPT4O_MINI[0],
                               "output": PRECIOS_GPT4O_MINI[1]},
        "fase": FASE,
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


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tope", type=float, default=0.25,
                    help="freno duro en USD (default 0.25)")
    args = ap.parse_args()
    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)

    print("== EXP69 piloto OpenAI: carga de problemas ==")
    problemas = P.cargar_problemas(dry=args.dry_run, seccion="pilot")
    print(f"   {len(problemas)} problemas "
          f"({sum(1 for p in problemas if p['slice'] == 'gsm8k')} gsm8k, "
          f"{sum(1 for p in problemas if p['slice'] == 'mmlu')} mmlu, "
          f"{sum(1 for p in problemas if p['slice'] == 'mbpp')} mbpp)")

    if args.dry_run:
        ok = P.chequeo_scorers()
        nada = not os.path.exists(os.path.join(args.out,
                                               "openai_pulls.jsonl"))
        print("   dry-run:", "VERDE" if (ok and nada) else
              "ROJO — revisar scorers o pulls residuales")
        print("   (sin llamadas a la API; openai_pulls.jsonl no creado: "
              f"{nada})")
        return 0 if (ok and nada) else 1

    backend = OpenAIBackend()
    modelos = backend.ping()
    assert any(MODEL in (m or "") for m in modelos), \
        f"{MODEL} no visible en /v1/models"
    print("   ping /v1/models OK (gratis, via surrogate del vault)")

    pil = P.Piloto(args.out, fase=FASE, pulls_fname="openai_pulls.jsonl",
                   tope_usd=args.tope)
    total = len(problemas) * len(ARMS) * N_INTENTOS
    hecho_nuevos = 0

    print(f"== piloto openai: {total} pulls (3 brazos x 2 intentos x 30) ==")
    try:
        for p in problemas:
            for arm in ARMS:
                for i in range(N_INTENTOS):
                    r, nuevo = pil.pull(p, arm, i, backend, ejecutar)
                    if nuevo:
                        hecho_nuevos += 1
            if hecho_nuevos and hecho_nuevos % 30 == 0:
                print(f"   {len(pil.hechos)}/{total} pulls | "
                      f"gastado ${pil.gastado:.4f} | {time.time() - t0:.0f}s",
                      flush=True)
    except RuntimeError as e:
        print(f"\nABORTO POR FRENO: {e}")
        print(f"   parcial: {len(pil.hechos)} pulls, "
              f"gastado ${pil.gastado:.4f} — sin resumen")
        return 2

    pulls = list(pil.hechos.values())
    res = resumen_openai(pulls, backend, pil.gastado, args.tope,
                         time.time() - t0)
    with open(os.path.join(args.out, "openai_summary.json"), "w") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)

    print("\n================ RESUMEN OPENAI ================")
    for cfg, inf in res["por_configuracion"].items():
        print(f"  {cfg}: reward={inf['reward_medio']} "
              f"costo=${inf['costo_medio_usd']:.6f} "
              f"reward/USD={inf['reward_por_usd']}")
    g = res["global"]
    print(f"  GLOBAL: reward={g['reward_medio']} "
          f"costo=${g['costo_medio_usd']:.6f} reward/USD={g['reward_por_usd']}")
    print(f"  costo total: ${pil.gastado:.4f} | llamadas: {backend.llamadas} "
          f"| {res['duracion_s']}s")
    print("================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
