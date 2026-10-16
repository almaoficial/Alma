"""Backends de LLM — la única pieza que habla con un modelo.

- LLMBackend: interfaz abstracta. complete() devuelve (texto, uso) donde
  uso = {"prompt_tokens": int, "completion_tokens": int}.
- MockBackend: mundo sintético determinista para probar el selector sin
  API key. Cada par (clase, arquitectura) tiene una tasa de éxito conocida
  (TASAS_MOCK); el mock decide por (problema, arquitectura, intento) si la
  respuesta es correcta, con RNG seedeado por hash → reproducible.
  Las tasas están diseñadas para que cada clase tenga un oráculo distinto
  (heterogeneidad: la hipótesis que el experimento pone a prueba).
- OpenAICompatBackend: habla con cualquier API formato chat-completions
  (OpenAI, y compatibles). Lee ALMA_API_KEY, ALMA_API_BASE, ALMA_MODEL.

Precios USD por millón de tokens (¡verificar vigentes antes de un run
real!): se usan solo para contabilidad de costo, no para el reward.
"""

import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.request

from .evaluator import normalize_text


class BackendError(Exception):
    pass


def _es_transitorio(mensaje):
    """¿El error huele a hipo de red/API temporal (reintentable)?"""
    m = mensaje.lower()
    claves = ("timeout", "timed out", "remote end closed", "connection",
              "reset by peer", "refused", "eof", "429", "rate limit",
              "temporarily", "unavailable", "bad gateway", "502", "503",
              "504", "socket", "dns")
    return any(c in m for c in claves)


def con_reintento(fn, intentos=3, base_s=2.0, que="llamado"):
    """Ejecuta fn(); ante BackendError transitorio reintenta con backoff
    exponencial (base_s, 2*base_s, 4*base_s). Errores no transitorios
    (auth, modelo inválido, etc.) abortan de inmediato."""
    ultimo = None
    for i in range(intentos):
        try:
            return fn()
        except BackendError as e:
            ultimo = e
            if not _es_transitorio(str(e)) or i == intentos - 1:
                raise
            espera = base_s * (2 ** i)
            print(f"[reintento] {que}: fallo transitorio ({str(e)[:120]}); "
                  f"reintento {i + 2}/{intentos} en {espera:.0f}s...",
                  file=sys.stderr, flush=True)
            time.sleep(espera)
    raise ultimo


# USD por 1M tokens (prompt, completion). Valores ilustrativos 2026.
PRECIOS = {
    "mock": (0.15, 0.60),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "default": (1.00, 3.00),
}

# Probabilidad de éxito EFECTIVA por (clase, arquitectura) en el mundo
# sintético: es lo que el evaluador mide (incluye reintentos y votos por
# mayoría propios de cada arquitectura). El mock invierte a probabilidad
# por intento y calibra con búsqueda de sal para que el ground truth
# efectivo quede a ±0.045 del diseño (verificable en tests).
# Diseñado para heterogeneidad: oráculos distintos por clase
#   calculo→cot, codigo→plan_tools_verify, qa_multihop→cot,
#   herramientas→plan_tools_verify, puzzles→debate
# y "reflexion" como mejor fija global (buena en todo, la mejor en nada:
# el baseline más exigente para la hipótesis de selección).
TASAS_MOCK = {
    "calculo": {
        "single": 0.55, "cot": 0.80, "self_consistency": 0.80,
        "reflexion": 0.82, "debate": 0.60, "plan_tools_verify": 0.40,
    },
    "codigo": {
        "single": 0.30, "cot": 0.25, "self_consistency": 0.55,
        "reflexion": 0.68, "debate": 0.55, "plan_tools_verify": 0.90,
    },
    "qa_multihop": {
        "single": 0.55, "cot": 0.82, "self_consistency": 0.80,
        "reflexion": 0.80, "debate": 0.70, "plan_tools_verify": 0.30,
    },
    "herramientas": {
        "single": 0.45, "cot": 0.25, "self_consistency": 0.50,
        "reflexion": 0.77, "debate": 0.50, "plan_tools_verify": 0.92,
    },
    "puzzles": {
        "single": 0.35, "cot": 0.20, "self_consistency": 0.65,
        "reflexion": 0.55, "debate": 0.90, "plan_tools_verify": 0.65,
    },
    # --- Clases de EXP2 (replicación hostil): mundo heterogéneo calibrado.
    # Oráculos distintos por clase a propósito: la hipótesis bajo prueba
    # es que el selector explota la heterogeneidad. Tasas plausibles con
    # un modelo real (single domina lo trivial; cot/reflexion lo analítico).
    "logica": {
        "single": 0.55, "cot": 0.85, "self_consistency": 0.80,
        "reflexion": 0.82, "debate": 0.60, "plan_tools_verify": 0.35,
    },
    "traduccion": {
        "single": 0.95, "cot": 0.85, "self_consistency": 0.90,
        "reflexion": 0.88, "debate": 0.80, "plan_tools_verify": 0.50,
    },
    "resumen": {
        "single": 0.80, "cot": 0.85, "self_consistency": 0.82,
        "reflexion": 0.80, "debate": 0.65, "plan_tools_verify": 0.35,
    },
    "depuracion": {
        "single": 0.45, "cot": 0.70, "self_consistency": 0.65,
        "reflexion": 0.85, "debate": 0.60, "plan_tools_verify": 0.40,
    },
    "conocimiento": {
        "single": 0.90, "cot": 0.80, "self_consistency": 0.85,
        "reflexion": 0.82, "debate": 0.70, "plan_tools_verify": 0.35,
    },
}


def _rng(*partes):
    digest = hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()
    return random.Random(int(digest, 16) % (2 ** 32))


class LLMBackend:
    """Interfaz. `uso` siempre trae prompt_tokens y completion_tokens."""

    precios = PRECIOS["default"]

    def complete(self, prompt, system=None, problem_id=None, arch_id=None,
                 modo=None, intento=0, idx=0, formato=None):
        raise NotImplementedError

    def costo(self, uso):
        pin, pout = self.precios
        return uso["prompt_tokens"] / 1e6 * pin + uso["completion_tokens"] / 1e6 * pout


def _estructura_intentos(arch_id, clase):
    """Cómo la arquitectura convierte intentos en un resultado final."""
    if arch_id == "self_consistency":
        return ("mayoria", 5)
    if arch_id == "reflexion":
        return ("al_menos_uno", 3)  # hasta 3 intentos, frena al acertar
    if arch_id == "debate":
        return ("mayoria", 3)
    if arch_id == "plan_tools_verify" and clase == "codigo":
        return ("al_menos_uno", 2)  # intento + fix con tests
    return ("uno", 1)


def _tasa_efectiva_sets(sets, kind, m, pids):
    """Tasa efectiva que un runner produce con estos conjuntos de éxitos.

    kind "uno"/"al_menos_uno": basta un intento bueno (unión).
    kind "mayoria": más de la mitad de los intentos buenos.
    """
    ok = 0
    for pid in pids:
        hits = sum(1 for s in sets if pid in s)
        good = hits > m // 2 if kind == "mayoria" else hits >= 1
        ok += good
    return ok / len(pids)


def _prob_mayoria(p, k):
    from math import comb
    m = k // 2 + 1
    return sum(comb(k, i) * p ** i * (1 - p) ** (k - i) for i in range(m, k + 1))


def _nominal_para(arch_id, clase, objetivo):
    """Invierte la tasa efectiva a probabilidad por intento."""
    kind, k = _estructura_intentos(arch_id, clase)
    if objetivo <= 0.0:
        return 0.0
    if objetivo >= 1.0:
        return 1.0
    if kind == "uno":
        return objetivo
    if kind == "al_menos_uno":
        return 1.0 - (1.0 - objetivo) ** (1.0 / k)
    # mayoria: bisección (monótona en p)
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if _prob_mayoria(mid, k) < objetivo:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


class MockBackend(LLMBackend):
    """Mundo sintético determinista con ground truth calibrado.

    Para cada (clase, arquitectura) se generan conjuntos de éxitos por
    intento (barajados con semilla derivada) y se elige con búsqueda de
    sal el primero cuya tasa EFECTIVA —la que el runner produce vía
    unión (reintentos) o mayoría (votos)— quede a ±0.045 del diseño.
    Los intentos siguen siendo sorteos independientes: el beneficio de
    reflexion/self-consistency/debate se preserva. Es un laboratorio
    controlado, no un estudio de campo: el ruido real aparece al correr
    contra una API de verdad.
    """

    def __init__(self, problem_index, tasas=None, seed=0):
        self.problem_index = problem_index  # id -> problema dict
        self.tasas = tasas or TASAS_MOCK   # EFECTIVAS por (clase, arch)
        self.seed = seed
        self.precios = PRECIOS["mock"]
        self._debate = {}  # (pid, arch) -> [(texto, ok)] para el agregador
        # Inversión a probabilidad por intento.
        self._nominal = {}
        for clase, d in self.tasas.items():
            for arch_id, objetivo in d.items():
                self._nominal[(clase, arch_id)] = _nominal_para(arch_id, clase, objetivo)
        # Conjuntos de éxitos por (clase, arch): lista de sets (uno por intento).
        self._ok = {}
        por_clase = {}
        for pid, p in problem_index.items():
            por_clase.setdefault(p["clase"], []).append(pid)
        for clase, pids in por_clase.items():
            n = len(pids)
            for arch_id, objetivo in self.tasas.get(clase, {}).items():
                kind, m = _estructura_intentos(arch_id, clase)
                nominal = self._nominal[(clase, arch_id)]
                n_intentos = 1 if kind == "uno" else m
                elegidos, mejor_dist = None, float("inf")
                for salt in range(300):
                    sets = []
                    for intento in range(n_intentos):
                        rng = _rng(seed, clase, arch_id, intento, salt)
                        orden = pids[:]
                        rng.shuffle(orden)
                        k = int(round(nominal * n))
                        sets.append(set(orden[:k]))
                    eff = _tasa_efectiva_sets(sets, kind, m, pids)
                    dist = abs(eff - objetivo)
                    if dist < mejor_dist:
                        mejor_dist, elegidos = dist, sets
                    if dist <= 0.045:
                        break
                self._ok[(clase, arch_id)] = elegidos

    # -- núcleo del mock -------------------------------------------------
    def _roll(self, problem_id, arch_id, intento):
        """True si este intento sale bien (determinista, tasa calibrada)."""
        p = self.problem_index[problem_id]
        sets = self._ok.get((p["clase"], arch_id))
        if sets is None:  # arquitectura no tabulada: Bernoulli honesto
            nominal = self._nominal.get((p["clase"], arch_id), 0.30)
            return _rng(problem_id, arch_id, intento, self.seed).random() < nominal
        return problem_id in sets[min(intento, len(sets) - 1)]

    def _formatear(self, problema, ok, formato):
        clase = problema["clase"]
        if ok:
            if clase == "codigo":
                cuerpo = problema["codigo_correcto"]
            elif clase == "calculo":
                cuerpo = str(problema["esperado"])
            else:
                cuerpo = str(problema["esperado"])
        else:
            if clase == "codigo":
                cuerpo = (
                    "```python\n"
                    f"def {problema['funcion']}(*args, **kwargs):\n"
                    "    return None\n```"
                )
            elif clase == "calculo":
                cuerpo = str(problema["esperado"] + 1)
            elif clase == "puzzles":
                cuerpo = "no encontré una expresión válida"
            else:
                cuerpo = "No estoy seguro."
        if formato == "respuesta_marcada":
            return f"Razonamiento simulado paso a paso.\nRespuesta: {cuerpo}"
        return cuerpo

    # -- interfaz ---------------------------------------------------------
    def complete(self, prompt, system=None, problem_id=None, arch_id=None,
                 modo=None, intento=0, idx=0, formato=None):
        if problem_id not in self.problem_index:
            raise BackendError(f"problema desconocido para el mock: {problem_id!r}")
        problema = self.problem_index[problem_id]

        if modo == "critica":
            ok = self._roll(problem_id, arch_id, intento)
            texto = (
                "La respuesta es correcta."
                if ok
                else "La respuesta es incorrecta: hay un error en el procedimiento. "
                     "Revisá los pasos y corregilo."
            )
        elif modo == "agente":
            ok = self._roll(problem_id, arch_id, idx)
            texto = self._formatear(problema, ok, formato)
            self._debate.setdefault((problem_id, arch_id), []).append((texto, ok))
        elif modo == "agrega":
            # pop: los votos se consumen; si no, se acumularían entre runs
            # del mismo problema (fuga de estado entre fases del experimento).
            votos = self._debate.pop((problem_id, arch_id), [])
            if not votos:
                texto = self._formatear(problema, False, formato)
            else:
                conteo = {}
                for t, _ok in votos:
                    k = normalize_text(t)
                    conteo[k] = conteo.get(k, 0) + 1
                ganador = max(conteo, key=lambda k: conteo[k])
                texto = next(t for t, _ok in votos if normalize_text(t) == ganador)
        else:
            ok = self._roll(problem_id, arch_id, intento)
            texto = self._formatear(problema, ok, formato)

        uso = {
            "prompt_tokens": max(1, len(prompt) // 4),
            "completion_tokens": max(1, len(texto) // 4),
        }
        return texto, uso


class OpenAICompatBackend(LLMBackend):
    """Backend real contra API formato chat-completions (solo stdlib)."""

    def __init__(self):
        key = os.environ.get("ALMA_API_KEY")
        if not key:
            raise BackendError("falta ALMA_API_KEY en el entorno")
        self.key = key
        self.base = os.environ.get("ALMA_API_BASE", "https://api.openai.com/v1").rstrip("/")
        self.model = os.environ.get("ALMA_MODEL", "gpt-4o-mini")
        self.precios = PRECIOS.get(self.model, PRECIOS["default"])
        if self.model not in PRECIOS:
            print(f"[aviso] modelo {self.model!r} sin precio tabulado; "
                  f"uso default {PRECIOS['default']} USD/1M. Verificá precios vigentes.")

    def complete(self, prompt, system=None, problem_id=None, arch_id=None,
                 modo=None, intento=0, idx=0, formato=None):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }).encode()
        req = urllib.request.Request(
            f"{self.base}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            raise BackendError(f"falló el llamado a {self.base}: {e}")
        try:
            texto = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage", {})
        except (KeyError, IndexError) as e:
            raise BackendError(f"respuesta inesperada de la API: {e}")
        uso = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
        }
        return texto, uso


class VaultBackend(LLMBackend):
    """Backend real vía la credencial guardada en el Secure Vault.

    No toca la key nunca: delega cada llamado al CLI del skill openai
    (~/workspace/skills/openai/bin/openai_chat.py), que adjunta la
    credencial como surrogate y authd la reemplaza al salir.
    La key no aparece en el entorno, en logs ni en archivos.
    Misma interfaz que OpenAICompatBackend: complete() -> (texto, uso).
    """

    def __init__(self, model=None, cli=None):
        self.model = model or os.environ.get("ALMA_MODEL", "gpt-4o-mini")
        self.cli = cli or os.path.expanduser(
            "~/workspace/skills/openai/bin/openai_chat.py")
        if not os.path.isfile(self.cli):
            raise BackendError(f"no existe el CLI del skill openai: {self.cli}")
        self.precios = PRECIOS.get(self.model, PRECIOS["default"])
        if self.model not in PRECIOS:
            print(f"[aviso] modelo {self.model!r} sin precio tabulado; "
                  f"uso default {PRECIOS['default']} USD/1M. Verificá precios vigentes.")

    def complete(self, prompt, system=None, problem_id=None, arch_id=None,
                 modo=None, intento=0, idx=0, formato=None):
        # Reintento ante hipos de red: un fallo transitorio no debe matar
        # horas de cómputo (lección EXP18: rc=4 "Remote end closed").
        return con_reintento(
            lambda: self._complete_una_vez(prompt, system=system),
            que=f"vault {self.model}")

    def _complete_una_vez(self, prompt, system=None):
        cmd = [sys.executable, self.cli,
               "--model", self.model,
               "--temperature", "0.2",
               "--max-tokens", "1024",
               "--timeout", "180"]
        if system:
            cmd += ["--system", system]
        cmd += ["--user", prompt]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=200)
        except subprocess.TimeoutExpired:
            raise BackendError("timeout llamando al CLI del skill openai")
        if proc.returncode != 0:
            raise BackendError(
                f"el CLI del skill falló (rc={proc.returncode}): "
                f"{proc.stderr.strip()[:300]}")
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise BackendError("el CLI devolvió algo no-JSON")
        if "error" in data:
            raise BackendError(
                f"error de la API: {data['error']} {data.get('detail', '')[:200]}")
        try:
            texto = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage", {})
        except (KeyError, IndexError) as e:
            raise BackendError(f"respuesta inesperada de la API: {e}")
        uso = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
        }
        return texto, uso
