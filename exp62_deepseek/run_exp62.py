#!/usr/bin/env python3
"""ALMA-EXP62: test de agnosticismo al modelo — réplica de EXP5 con
deepseek-flash como motor (3 brazos mapeados al dial de esfuerzo).

Fases: 0) GET /models (gratis)  1) smoke (3 llamadas)  2) oráculo
(1080 llamadas, disciplina EXP8)  3) políticas. Freno duro US$1,00.

La key viaja SOLO por la variable de entorno DEEPSEEK_API_KEY. Este script
nunca la escribe en disco ni en logs.

Uso:
    DEEPSEEK_API_KEY=... python3 run_exp62.py --out ~/workspace/alma-prototype/exp62_deepseek
"""
import argparse
import json
import os
import random
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_experiment as rx
from alma.backends import LLMBackend, BackendError, con_reintento
from alma.budget import BudgetManager, BudgetExceeded, RESOLUCION, SELECCION, EXPERIMENTACION
from alma.evaluator import Evaluator, StubJudge, normalize_text
from alma.store import ExperienceStore

# ---------------------------------------------------------------- backend

BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-flash"
PRECIOS_FLASH_OFFPEAK = (0.15, 0.60)  # USD/1M (in, out); verificado en vivo 2026-09-27

# Mapeo brazo -> dial de esfuerzo (docs oficiales 2026-09-27: niveles
# efectivos none/high/max; low->high por compatibilidad).
EFFORT_POR_BRAZO = {
    "single":    {"thinking": {"type": "disabled"}, "reasoning_effort": "none",
                  "max_tokens": 256},
    "cot":       {"thinking": {"type": "enabled"},  "reasoning_effort": "high",
                  "max_tokens": 1024},
    "reflexion": {"thinking": {"type": "enabled"},  "reasoning_effort": "max",
                  "max_tokens": 2048},
}
ARMS = ["single", "cot", "reflexion"]


class DeepSeekBackend(LLMBackend):
    """Backend OpenAI-compatible contra api.deepseek.com. Key solo de env."""

    def __init__(self):
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise BackendError("falta DEEPSEEK_API_KEY en el entorno")
        self.key = key
        self.model = MODEL
        self.precios = PRECIOS_FLASH_OFFPEAK
        self.llamadas = 0
        self.truncadas = 0

    def _post(self, payload):
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/chat/completions", data=body,
            headers={"Authorization": "Bearer " + self.key,
                     "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            # IncompleteRead/timeouts son hipos transitorios de red: marcar el
            # mensaje con "connection" para que con_reintento los reintente
            # (lección EXP18; la lista de claves de backends.py no cubre
            # IncompleteRead).
            raise BackendError(f"falló el llamado a {BASE_URL}: connection "
                               f"transitoria ({type(e).__name__}: {e})")

    def ping(self):
        """GET /models: valida auth sin gastar tokens."""
        req = urllib.request.Request(
            f"{BASE_URL}/models",
            headers={"Authorization": "Bearer " + self.key}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            raise BackendError(f"ping /models falló: {e}")
        modelos = [m.get("id") for m in data.get("data", [])]
        return modelos

    def complete(self, prompt, system=None, problem_id=None, arch_id=None,
                 modo=None, intento=0, idx=0, formato=None):
        cfg = EFFORT_POR_BRAZO.get(arch_id or "", EFFORT_POR_BRAZO["cot"])
        return con_reintento(
            lambda: self._complete_una_vez(prompt, system, cfg),
            intentos=6, base_s=3.0,
            que=f"deepseek {self.model}/{arch_id}")

    def _complete_una_vez(self, prompt, system, cfg):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": cfg["max_tokens"],
            "thinking": cfg["thinking"],
            "reasoning_effort": cfg["reasoning_effort"],
            "stream": False,
        }
        data = self._post(payload)
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


# ---------------------------------------------------------------- runners

def _extraer_respuesta_marcada(texto):
    m = re.search(r"Respuesta:\s*(.+)", texto, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else texto.strip()


def _prompt_base(problema):
    return f"Problema: {problema['enunciado']}"


def _run_single(problema, backend):
    prompt = ("Respondé de forma concisa, solo con la respuesta final, "
              "sin explicación.\n\n" + _prompt_base(problema))
    if problema.get("verificador") == "codigo":
        prompt = ("Escribí solo el código Python pedido, dentro de un bloque "
                  "```python.\n\n" + _prompt_base(problema))
    texto, uso = backend.complete(prompt, system="Sos un asistente conciso.",
                                  problem_id=problema["id"], arch_id="single")
    return {"respuesta": texto.strip(), "costo_usd": backend.costo(uso),
            "llamados": 1, "uso": uso}


def _run_cot(problema, backend):
    prompt = ("Pensá paso a paso y al final escribí exactamente una línea con "
              "el formato: Respuesta: <tu respuesta final>\n\n"
              + _prompt_base(problema))
    if problema.get("verificador") == "codigo":
        prompt = ("Pensá paso a paso el algoritmo y al final escribí solo el "
                  "código Python dentro de un bloque ```python.\n\n"
                  + _prompt_base(problema))
    texto, uso = backend.complete(
        prompt, system="Sos un asistente que razona paso a paso.",
        problem_id=problema["id"], arch_id="cot")
    return {"respuesta": _extraer_respuesta_marcada(texto),
            "costo_usd": backend.costo(uso), "llamados": 1, "uso": uso}


def _run_reflexion(problema, backend):
    prompt = ("Pensá paso a paso. Cuestioná tu propio razonamiento: verificá "
              "cada paso, buscá errores, y si encontrás uno corregilo antes "
              "de responder. Al final escribí exactamente una línea con el "
              "formato: Respuesta: <tu respuesta final>\n\n"
              + _prompt_base(problema))
    if problema.get("verificador") == "codigo":
        prompt = ("Pensá paso a paso el algoritmo, cuestioná tu razonamiento "
                  "y verificá mentalmente los casos borde. Al final escribí "
                  "solo el código Python dentro de un bloque ```python.\n\n"
                  + _prompt_base(problema))
    texto, uso = backend.complete(
        prompt, system="Sos un agente que razona y se auto-corrige.",
        problem_id=problema["id"], arch_id="reflexion")
    return {"respuesta": _extraer_respuesta_marcada(texto),
            "costo_usd": backend.costo(uso), "llamados": 1, "uso": uso}


RUNNERS = {"single": _run_single, "cot": _run_cot, "reflexion": _run_reflexion}


def ejecutar(arch_id, problema, backend):
    if arch_id not in RUNNERS:
        raise KeyError(f"runner desconocido: {arch_id!r}")
    return RUNNERS[arch_id](problema, backend)


# ---------------------------------------------------------------- stream (réplica EXP5)

CLASES_EXP1 = ["calculo", "codigo", "qa_multihop", "herramientas", "puzzles"]
CLASES_EXP2 = ["logica", "traduccion", "resumen", "depuracion", "conocimiento"]
EST_SINGLE = ["codigo", "herramientas", "puzzles", "traduccion", "depuracion"]
EST_COT = ["calculo", "qa_multihop", "logica", "conocimiento", "resumen"]
SEED = 999
N0_PSEUDO = 2
PROBE_N = 3
PROBE_MARGEN = 0.05
N_INTENTOS_ORACULO = 3
FASE_ORACULO = "62A-oracle"
FASE_PROBE = "62B-alma-probe"
TOPE_USD = 1.00


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def cargar_todo(base):
    problemas_por_clase = {}
    for clase in CLASES_EXP1:
        with open(os.path.join(base, "data", f"{clase}.json"), encoding="utf-8") as f:
            problemas_por_clase[clase] = json.load(f)
    for clase in CLASES_EXP2:
        with open(os.path.join(base, "data_exp2", f"{clase}.json"), encoding="utf-8") as f:
            problemas_por_clase[clase] = json.load(f)
    return problemas_por_clase


def ordenar_stream(seed):
    rng = random.Random(seed)
    s, c = EST_SINGLE[:], EST_COT[:]
    rng.shuffle(s)
    rng.shuffle(c)
    orden = []
    empieza_single = rng.random() < 0.5
    for a, b in zip(s, c):
        orden += [a, b] if empieza_single else [b, a]
    return orden


# ---------------------------------------------------------------- pulls

class Corrida:
    def __init__(self, out):
        self.out = out
        self.backend = DeepSeekBackend()
        self.evaluator = Evaluator(judge=StubJudge())
        self.store = ExperienceStore(os.path.join(out, "experiencias.jsonl"))
        assert self.store.verify_chain()
        self.budget = BudgetManager({RESOLUCION: TOPE_USD, SELECCION: 1.0,
                                     EXPERIMENTACION: 5.0})
        self.hechos = {}
        gastado_previo = 0.0
        for r in self.store.read_all():
            k = (r.get("fase"), r.get("problema_id"), r.get("arch_id"),
                 r.get("intento", 0))
            self.hechos[k] = r["metricas"]["reward"]
            gastado_previo += r.get("costo_usd", 0.0)
        # El freno de US$1,00 es TOTAL: sembrar lo ya gastado en corridas
        # anteriores para que el budget no lo olvide al resumir.
        self.budget.gastado[RESOLUCION] = gastado_previo
        if gastado_previo:
            print(f"   resume: {len(self.hechos)} pulls en store, "
                  f"gastado previo ${gastado_previo:.4f}")
        self.gasto_log = []

    def pull(self, p, arch, fase, intento=0):
        key = (fase, p["id"], arch, intento)
        if key in self.hechos:
            return self.hechos[key], False
        res = ejecutar(arch, p, self.backend)
        met = self.evaluator.score(p, res["respuesta"], arch)
        self.budget.charge(RESOLUCION, res["costo_usd"],
                           f"{fase}:{p['id']}:{arch}:i{intento}")
        self.store.append({
            "problema_id": p["id"],
            "features": rx.featurizer.featurize(p["enunciado"]),
            "clase": p["clase"],
            "arch_id": arch,
            "config": {"motor": MODEL,
                       "effort": EFFORT_POR_BRAZO[arch]["reasoning_effort"],
                       "max_tokens": EFFORT_POR_BRAZO[arch]["max_tokens"],
                       "intento": intento},
            "intento": intento,
            "respuesta": res["respuesta"][:2000],
            "traza": f"exp62:{arch}:1 llamado",
            "metricas": met,
            "costo_usd": round(res["costo_usd"], 6),
            "fase": fase,
            "uso_tokens": res["uso"],
        })
        self.hechos[key] = met["reward"]
        u = res["uso"]
        self.gasto_log.append({
            "fase": fase, "pid": p["id"], "arch": arch, "intento": intento,
            "in": u["prompt_tokens"], "out": u["completion_tokens"],
            "usd": round(res["costo_usd"], 6),
        })
        return met["reward"], True


# ---------------------------------------------------------------- fases

def fase_oraculo(corr, stream):
    oracle_arch, oracle_reward, detalle = {}, {}, {}
    total = len(stream) * len(ARMS) * N_INTENTOS_ORACULO
    hecho = 0
    t0 = time.time()
    for pos, (_clase, p) in enumerate(stream):
        rs = {}
        for arch in ARMS:
            intentos = [corr.pull(p, arch, FASE_ORACULO, intento=i)[0]
                        for i in range(N_INTENTOS_ORACULO)]
            rs[arch] = intentos
            hecho += N_INTENTOS_ORACULO
        medias = {a: mean(v) for a, v in rs.items()}
        mejor = max(medias, key=lambda a: medias[a])
        oracle_arch[pos], oracle_reward[pos] = mejor, medias[mejor]
        detalle[pos] = {a: [round(x, 4) for x in v] for a, v in rs.items()}
        if (pos + 1) % 12 == 0:
            g = corr.budget.gastado[RESOLUCION]
            print(f"  oráculo {hecho}/{total} celdas-intento | "
                  f"gastado ${g:.4f} | {time.time()-t0:.0f}s", flush=True)
    return oracle_arch, oracle_reward, detalle


def repertorio_hacia_adelante(corr, stream, pos_limite):
    pos_de_pid = {p["id"]: i for i, (_c, p) in enumerate(stream)}
    rep = {a: [] for a in ARMS}
    for r in corr.store.read_all():
        if r.get("fase") not in (FASE_ORACULO, "62B-alma-full", FASE_PROBE):
            continue
        if r.get("arch_id") not in ARMS:
            continue
        if pos_de_pid.get(r.get("problema_id", ""), 10 ** 9) < pos_limite:
            rep[r["arch_id"]].append(r["metricas"]["reward"])
    return rep


def bandit_warm(repertorio):
    b = rx.BanditPorClase(ARMS)
    for a in ARMS:
        rs = repertorio.get(a, [])
        m = mean(rs) if rs else 0.5
        b.alpha[a] = 1.0 + N0_PSEUDO * m
        b.beta[a] = 1.0 + N0_PSEUDO * (1.0 - m)
        b.pulls[a] = N0_PSEUDO
    return b


def probe_choice(probe_rs):
    """Default barato + margen (generalización de EXP3 a 3 brazos)."""
    orden = ["single", "cot", "reflexion"]
    elegido = "single"
    for cand in orden[1:]:
        if mean(probe_rs[cand]) - mean(probe_rs[elegido]) > PROBE_MARGEN:
            elegido = cand
    return elegido


def correr_fija(corr, politica, stream):
    fase = f"62B-{politica}"
    arch_fijo = politica.split("-")[1]
    return {pos: corr.pull(p, arch_fijo, fase)[0]
            for pos, (_clase, p) in enumerate(stream)}


def correr_thompson_global(corr, stream, seed):
    fase = "62B-thompson-global"
    bandit = rx.BanditPorClase(ARMS)
    rewards = {}
    for pos, (_clase, p) in enumerate(stream):
        hit = None
        for a in ARMS:
            if (fase, p["id"], a, 0) in corr.hechos:
                hit = (a, corr.hechos[(fase, p["id"], a, 0)])
                break
        if hit is not None:
            arch, r = hit
            bandit.update(arch, r)
            rewards[pos] = r
            continue
        rng = random.Random(f"exp62-{seed}-{pos}")
        arch = bandit.select(rng)
        r, nuevo = corr.pull(p, arch, fase)
        if nuevo:
            bandit.update(arch, r)
        rewards[pos] = r
    return rewards


def correr_alma_full(corr, stream, orden, seed):
    rewards, elecciones = {}, {}

    def fila_full(pid):
        for a in ARMS:
            if ("62B-alma-full", pid, a, 0) in corr.hechos:
                return a, corr.hechos[("62B-alma-full", pid, a, 0)]
        return None

    for b, clase in enumerate(orden):
        base = b * 12
        bandit = bandit_warm(repertorio_hacia_adelante(corr, stream, base))
        probe_rs = {}
        for q in range(PROBE_N):
            qp = stream[base + q][1]
            for arch in ARMS:
                key = (FASE_PROBE, qp["id"], arch, 0)
                if key in corr.hechos:
                    r = corr.hechos[key]
                else:
                    r, nuevo = corr.pull(qp, arch, FASE_PROBE)
                    if nuevo:
                        bandit.update(arch, r)
                probe_rs.setdefault(arch, []).append(r)
        elegido = probe_choice(probe_rs)
        elecciones[b] = {"clase": clase, "elegido": elegido,
                         "medias": {a: round(mean(v), 4)
                                    for a, v in probe_rs.items()}}
        for q in range(PROBE_N):
            pos = base + q
            rewards[pos] = probe_rs[elegido][q]
        for q in range(PROBE_N, 12):
            pos = base + q
            p = stream[pos][1]
            hit = fila_full(p["id"])
            if hit is not None:
                arch, r = hit
                bandit.update(arch, r)
                rewards[pos] = r
                continue
            rng = random.Random(f"exp62-{seed}-{pos}")
            arch = bandit.select(rng)
            r, nuevo = corr.pull(p, arch, "62B-alma-full")
            if nuevo:
                bandit.update(arch, r)
            rewards[pos] = r
        print(f"  bloque {b} ({clase}): probe eligió {elegido} "
              f"{elecciones[b]['medias']}", flush=True)
    return rewards, elecciones


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--solo-oraculo", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    corr = Corrida(args.out)

    print("== EXP62 fase 0: ping /models (gratis) ==")
    modelos = corr.backend.ping()
    print(f"   modelos visibles: {modelos}")
    assert MODEL in modelos, f"{MODEL} no está en /models"

    # Fidelidad del stream vs EXP5.
    orden = ordenar_stream(args.seed)
    with open(os.path.join(base, "resultados", "exp5-20260926",
                            "report.json"), encoding="utf-8") as f:
        orden_exp5 = json.load(f)["orden_bloques"]
    assert orden == orden_exp5, f"orden difiere de EXP5: {orden} vs {orden_exp5}"
    print(f"== stream fiel a EXP5: {orden}")

    problemas_por_clase = cargar_todo(base)
    stream = [(clase, p) for clase in orden
              for p in problemas_por_clase[clase]]
    assert len(stream) == 120

    print("== EXP62 fase 1: smoke (3 llamadas) ==")
    p0 = stream[0][1]
    for arch in ARMS:
        r, nuevo = corr.pull(p0, arch, "62-smoke")
        if nuevo and corr.gasto_log:
            g = corr.gasto_log[-1]
            uso_s = f"uso={g['in']}in/{g['out']}out"
        else:
            uso_s = "replay del store (sin llamada nueva)"
        print(f"   smoke {arch}: reward={r} nuevo={nuevo} {uso_s}")
    print(f"   gastado tras smoke: ${corr.budget.gastado[RESOLUCION]:.6f}")

    print("== EXP62 fase 2: oráculo (3 intentos/celda, disciplina EXP8) ==")
    try:
        oracle_arch, oracle_reward, detalle = fase_oraculo(corr, stream)
    except BudgetExceeded as e:
        return abortar(args, corr, t0, f"freno US$1,00 en oráculo: {e}")
    n_por_brazo = {a: sum(1 for v in oracle_arch.values() if v == a)
                   for a in ARMS}
    print(f"   oráculo: {n_por_brazo} | "
          f"gastado ${corr.budget.gastado[RESOLUCION]:.4f}")

    with open(os.path.join(args.out, "oraculo.json"), "w") as f:
        json.dump({"arch": oracle_arch, "reward": oracle_reward,
                   "detalle": detalle}, f, ensure_ascii=False)
    guardar_gasto(args, corr)

    if args.solo_oraculo:
        print("   (solo-oráculo: fin)")
        return 0

    print("== EXP62 fase 3: políticas ==")
    regrets, por_bloque = {}, {}
    try:
        for pol in ["fija-single", "fija-cot", "fija-reflexion",
                    "thompson-global", "alma-full"]:
            print(f"  política {pol}...", flush=True)
            tpol = time.time()
            if pol.startswith("fija-"):
                rewards = correr_fija(corr, pol, stream)
                elecciones = None
            elif pol == "thompson-global":
                rewards = correr_thompson_global(corr, stream, args.seed)
                elecciones = None
            else:
                rewards, elecciones = correr_alma_full(corr, stream, orden,
                                                       args.seed)
            assert len(rewards) == 120, f"{pol}: {len(rewards)}"
            reg = {pos: oracle_reward[pos] - rewards[pos] for pos in range(120)}
            regrets[pol] = reg
            por_bloque[pol] = [round(sum(reg[b * 12 + q] for q in range(12)), 4)
                               for b in range(10)]
            print(f"    regret={sum(reg.values()):.3f} ({time.time()-tpol:.0f}s)")
    except BudgetExceeded as e:
        return abortar(args, corr, t0, f"freno US$1,00 en políticas: {e}")

    r_alma = sum(regrets["alma-full"].values())
    r_fijas = min(sum(regrets[f"fija-{a}"].values()) for a in ARMS)
    r_th = sum(regrets["thompson-global"].values())
    bloques_gana = sum(
        1 for b in range(10)
        if por_bloque["alma-full"][b] < min(por_bloque[f"fija-{a}"][b]
                                           for a in ARMS))
    pasa = bool(r_alma < r_fijas and r_alma < r_th)
    veredicto = {
        "pasa": pasa,
        "criterio": {"gana_a_mejor_fija": bool(r_alma < r_fijas),
                    "gana_a_thompson_global": bool(r_alma < r_th)},
        "motivos": [
            f"regret alma-full={r_alma:.4f} vs mejor fija={r_fijas:.4f} "
            f"(diff={r_alma - r_fijas:+.4f})",
            f"regret alma-full={r_alma:.4f} vs thompson-global={r_th:.4f} "
            f"(diff={r_alma - r_th:+.4f})",
            f"alma-full gana el bloque en {bloques_gana}/10 (diagnóstico)",
        ],
        "medido": {"regret_alma_full": round(r_alma, 4),
                   "regret_mejor_fija": round(r_fijas, 4),
                   "regret_thompson_global": round(r_th, 4),
                   "bloques_gana_vs_fija": bloques_gana},
    }
    costo_total = sum(corr.budget.gastado.values())
    report = {
        "experimento": "ALMA-EXP62: agnosticismo al modelo (deepseek-flash)",
        "motor": MODEL,
        "precios_usd_1M": {"in": PRECIOS_FLASH_OFFPEAK[0],
                           "out": PRECIOS_FLASH_OFFPEAK[1],
                           "ventana": "off-peak (domingo)"},
        "orden_bloques": orden,
        "oraculo_por_problema": {str(k): v for k, v in oracle_arch.items()},
        "oraculo_distribucion": n_por_brazo,
        "regret_total_por_politica": {p: round(sum(r.values()), 4)
                                      for p, r in regrets.items()},
        "regret_por_bloque": por_bloque,
        "elecciones_probe": elecciones,
        "budget": corr.budget.report(),
        "costo_total_usd": round(costo_total, 4),
        "llamadas_api": corr.backend.llamadas,
        "truncadas_por_max_tokens": corr.backend.truncadas,
        "experiencias": len(corr.store),
        "store_chain_ok": corr.store.verify_chain(),
        "veredicto": veredicto,
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    guardar_gasto(args, corr)
    print("\n================ VEREDICTO ================")
    for m in veredicto["motivos"]:
        print("  " + m)
    print(f"  costo total: ${costo_total:.4f} | llamadas: "
          f"{corr.backend.llamadas} | {report['duracion_s']}s")
    print("  RESULTADO:", "PASS — el loop replica con deepseek-flash"
          if pasa else "FAIL — no replica con deepseek-flash")
    print("===========================================")
    return 0 if pasa else 1


def guardar_gasto(args, corr):
    with open(os.path.join(args.out, "gasto_por_llamada.jsonl"), "w") as f:
        for g in corr.gasto_log:
            f.write(json.dumps(g) + "\n")


def abortar(args, corr, t0, motivo):
    guardar_gasto(args, corr)
    parcial = {
        "experimento": "ALMA-EXP62 (ABORTADO por freno de presupuesto)",
        "motivo": motivo,
        "budget": corr.budget.report(),
        "costo_total_usd": round(sum(corr.budget.gastado.values()), 4),
        "llamadas_api": corr.backend.llamadas,
        "experiencias": len(corr.store),
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(parcial, f, indent=2, ensure_ascii=False)
    print(f"\nABORTO: {motivo}")
    print(f"  gastado: ${parcial['costo_total_usd']:.4f} | "
          f"llamadas: {corr.backend.llamadas}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
