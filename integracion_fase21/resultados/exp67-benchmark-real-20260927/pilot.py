#!/usr/bin/env python3
"""ALMA-EXP67 piloto anti-colapso (pre-oráculo).

30 problemas del pilot (10 por slice) x 3 brazos x 2 intentos = 180 llamadas.
Regla pre-registrada (preregistro.md): el slice pasa si ningun brazo gana
>80% de sus problemas; si colapsa -> backup pre-registrado.

La key viaja SOLO por DEEPSEEK_API_KEY (variable de entorno). Este script
nunca la escribe en disco ni en logs.

Freno duro: US$0,05 TOTAL (aborta limpio con parcial si se alcanza).

Uso:
    DEEPSEEK_API_KEY=... ~/workspace/venvs/exp67/bin/python pilot.py --out <dir>
    ... pilot.py --out <dir> --dry-run   # sin API: valida problemas+scorers
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.expanduser("~"),
                                "workspace/alma-prototype/exp62_deepseek"))

ARMS = ["single", "cot", "reflexion"]
N_INTENTOS = 2
TOPE_USD = 0.05
MANIFIESTO = os.path.join(
    os.path.expanduser("~"),
    "workspace/alma-prototype/integracion_fase21/resultados/"
    "exp67-benchmark-real-20260927/stream_manifest.json")


# ---------------------------------------------------------------- problemas

def _pids_de_seccion(man, seccion):
    """pids en orden pre-registrado: pilot (10 por slice) o stream
    (9 bloques x 20 en el orden del manifiesto)."""
    if seccion == "pilot":
        return (man["pilot"]["gsm8k"] + man["pilot"]["mmlu"]
                + man["pilot"]["mbpp"])
    if seccion == "stream":
        return [pid for bl in man["stream"] for pid in bl["problemas"]]
    raise ValueError(f"seccion desconocida: {seccion!r} (pilot|stream)")


def _problema_desde_pid(pid, g, b, mmlu_cache, dry):
    sl = pid.split(":")[0]
    if sl == "gsm8k":
        idx = int(pid.split(":")[1])
        if dry:
            en, gt = "dry", "0"
        else:
            row = g[idx]
            en = row["question"]
            gt = row["answer"].split("####")[-1].strip()
        return {"id": pid, "slice": "gsm8k", "enunciado": en,
                "verificador": "numero", "gt": gt}
    if sl == "mmlu":
        _, subj, idxs = pid.split(":")
        idx = int(idxs)
        if dry:
            en, gt = "dry", "A"
        else:
            row = mmlu_cache[subj][idx]
            letras = ["A", "B", "C", "D"]
            en = row["question"] + "\n" + "\n".join(
                f"{l}) {c}" for l, c in zip(letras, row["choices"]))
            gt = letras[int(row["answer"])]
        return {"id": pid, "slice": "mmlu", "enunciado": en,
                "verificador": "letra", "gt": gt}
    if sl == "mbpp":
        idx = int(pid.split(":")[1])
        if dry:
            en, setup, tests = "dry", "", ["assert True"]
        else:
            row = b[idx]
            en = row["text"]
            setup = row.get("test_setup_code") or ""
            tests = list(row["test_list"])
        return {"id": pid, "slice": "mbpp", "enunciado": en,
                "verificador": "codigo",
                "gt": {"setup": setup, "tests": tests}}
    raise ValueError(f"pid desconocido: {pid!r}")


def cargar_problemas(dry=False, seccion="pilot"):
    """Devuelve lista de dicts {id, slice, enunciado, verificador, gt}
    en el orden pre-registrado de la seccion (pilot|stream).
    En dry-run no toca la red."""
    with open(MANIFIESTO, encoding="utf-8") as f:
        man = json.load(f)
    pids = _pids_de_seccion(man, seccion)

    g = b = None
    mmlu_cache = {}
    if not dry:
        from datasets import load_dataset
        if any(p.startswith("gsm8k:") for p in pids):
            g = load_dataset("openai/gsm8k", "main", split="test")
        if any(p.startswith("mbpp:") for p in pids):
            b = load_dataset("google-research-datasets/mbpp", "full",
                             split="test")
        for pid in pids:
            if pid.startswith("mmlu:"):
                subj = pid.split(":")[1]
                if subj not in mmlu_cache:
                    mmlu_cache[subj] = load_dataset("cais/mmlu", subj,
                                                    split="test")
    return [_problema_desde_pid(pid, g, b, mmlu_cache, dry) for pid in pids]


# ---------------------------------------------------------------- scorers

def _num(s):
    toks = re.findall(r"-?\d[\d,]*\.?\d*", s.replace("$", ""))
    if not toks:
        return None
    try:
        return float(toks[-1].replace(",", ""))
    except ValueError:
        return None


def score_numero(respuesta, gt):
    a, b = _num(respuesta), _num(gt)
    if a is None or b is None:
        return 0
    return 1 if abs(a - b) < 1e-6 else 0


def score_letra(respuesta, gt):
    m = re.findall(r"\b([A-D])\b", respuesta.upper())
    return 1 if m and m[0] == gt else 0


def _extraer_codigo(respuesta):
    m = re.search(r"```python(.*?)```", respuesta, re.DOTALL | re.IGNORECASE)
    return m.group(1) if m else respuesta


def score_codigo(respuesta, gt, timeout_s=15):
    codigo = _extraer_codigo(respuesta)
    prog = (gt["setup"] or "") + "\n" + codigo + "\n" + "\n".join(gt["tests"])
    with tempfile.NamedTemporaryFile("w", suffix=".py",
                                     delete=False) as f:
        f.write(prog)
        path = f.name
    try:
        r = subprocess.run([sys.executable, path], capture_output=True,
                           timeout=timeout_s)
        return 1 if r.returncode == 0 else 0
    except subprocess.TimeoutExpired:
        return 0
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def puntuar(p, respuesta):
    v = p["verificador"]
    if v == "numero":
        return score_numero(respuesta, p["gt"])
    if v == "letra":
        return score_letra(respuesta, p["gt"])
    if v == "codigo":
        return score_codigo(respuesta, p["gt"])
    raise ValueError(f"verificador desconocido: {v}")


def chequeo_scorers():
    """Valida los scorers con ejemplos enlatados + la solucion de
    referencia de un problema MBPP real del cache local. Devuelve True
    si todo pasa. No toca la API."""
    print("== dry-run: valida scorers con ejemplos enlatados ==")
    checks = [
        ({"verificador": "numero", "gt": "72,000"},
         "El total es 72,000 unidades.", 1),
        ({"verificador": "numero", "gt": "42"},
         "Respuesta: 43", 0),
        ({"verificador": "numero", "gt": "7.5"},
         "da 7.5", 1),
        ({"verificador": "letra", "gt": "B"},
         "Respuesta: B", 1),
        ({"verificador": "letra", "gt": "C"},
         "creo que es (a)", 0),
        ({"verificador": "codigo",
          "gt": {"setup": "", "tests": ["assert add(2,3)==5"]}},
         "```python\ndef add(a,b):\n return a+b\n```", 1),
        ({"verificador": "codigo",
          "gt": {"setup": "", "tests": ["assert add(2,3)==5"]}},
         "```python\ndef add(a,b):\n return a-b\n```", 0),
    ]
    ok = True
    for p, resp, esp in checks:
        got = puntuar(p, resp)
        marca = "OK" if got == esp else "FALLA"
        if got != esp:
            ok = False
        print(f"   [{marca}] {p['verificador']} gt={p['gt']!r} -> {got} "
              f"(esperado {esp})")
    # scorer de codigo contra un problema MBPP real del cache
    from datasets import load_dataset
    b = load_dataset("google-research-datasets/mbpp", "full",
                     split="test")
    row = b[0]
    p = {"verificador": "codigo",
         "gt": {"setup": row.get("test_setup_code") or "",
                "tests": list(row["test_list"])}}
    r_ref = score_codigo(row["code"], p["gt"])
    print(f"   [MBPP real task_id={row['task_id']}] solucion de "
          f"referencia -> reward={r_ref} (esperado 1)")
    if r_ref != 1:
        ok = False
    return ok


# ---------------------------------------------------------------- corrida

class Piloto:
    def __init__(self, out, fase="piloto", pulls_fname="pilot_pulls.jsonl",
                 tope_usd=None):
        self.out = out
        self.fase = fase
        self.tope = TOPE_USD if tope_usd is None else tope_usd
        os.makedirs(out, exist_ok=True)
        self.pulls_path = os.path.join(out, pulls_fname)
        self.hechos = {}
        self.gastado = 0.0
        if os.path.exists(self.pulls_path):
            with open(self.pulls_path, encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    k = (r["pid"], r["arm"], r["intento"])
                    self.hechos[k] = r
                    self.gastado += r.get("costo_usd", 0.0)
            print(f"   resume [{self.fase}]: {len(self.hechos)} pulls, "
                  f"gastado previo ${self.gastado:.4f}")

    def pull(self, p, arm, intento, backend, ejecutar):
        key = (p["id"], arm, intento)
        if key in self.hechos:
            return self.hechos[key]["reward"], False
        if self.gastado >= self.tope:
            raise RuntimeError(
                f"freno duro US${self.tope:.2f} alcanzado "
                f"({len(self.hechos)} pulls hechos)")
        res = ejecutar(arm, p, backend)
        reward = puntuar(p, res["respuesta"])
        self.gastado += res["costo_usd"]
        rec = {"fase": self.fase, "pid": p["id"], "slice": p["slice"],
               "arm": arm, "intento": intento, "reward": reward,
               "costo_usd": round(res["costo_usd"], 6),
               "in": res["uso"]["prompt_tokens"],
               "out": res["uso"]["completion_tokens"],
               "respuesta_head": res["respuesta"][:300]}
        with open(self.pulls_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.hechos[key] = rec
        return reward, True


# ---------------------------------------------------------------- veredicto

def veredicto_puerta(pulls):
    """Por slice: share de problemas ganados por brazo (media de 2 intentos,
    gana el estrictamente mayor; empates no cuentan para nadie)."""
    por_slice = {}
    for r in pulls:
        por_slice.setdefault(r["slice"], {}).setdefault(
            r["pid"], {}).setdefault(r["arm"], []).append(r["reward"])
    informe = {}
    pasa_todo = True
    for sl, probs in por_slice.items():
        wins = {a: 0 for a in ARMS}
        empates = 0
        for pid, arms in probs.items():
            medias = {a: sum(v) / len(v) for a, v in arms.items()}
            top = max(medias.values())
            ganadores = [a for a, m in medias.items() if m == top]
            if len(ganadores) == 1:
                wins[ganadores[0]] += 1
            else:
                empates += 1
        n = len(probs)
        shares = {a: round(wins[a] / n, 3) for a in ARMS}
        max_share = max(shares.values())
        pasa = max_share <= 0.80
        pasa_todo = pasa_todo and pasa
        informe[sl] = {"n": n, "wins": wins, "empates": empates,
                       "shares": shares, "max_share": max_share,
                       "pasa": pasa}
    return {"pasa_puerta": pasa_todo, "slices": informe}


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-smoke", action="store_true")
    ap.add_argument("--tope", type=float, default=0.05,
                    help="freno duro en USD (default 0.05)")
    args = ap.parse_args()
    global TOPE_USD
    TOPE_USD = args.tope
    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)

    print("== EXP67 piloto: carga de problemas ==")
    problemas = cargar_problemas(dry=args.dry_run)
    print(f"   {len(problemas)} problemas "
          f"({sum(1 for p in problemas if p['slice']=='gsm8k')} gsm8k, "
          f"{sum(1 for p in problemas if p['slice']=='mmlu')} mmlu, "
          f"{sum(1 for p in problemas if p['slice']=='mbpp')} mbpp)")

    if args.dry_run:
        ok = chequeo_scorers()
        print("   dry-run:", "VERDE" if ok else "ROJO — revisar scorers")
        return 0 if ok else 1

    from run_exp62 import DeepSeekBackend, ejecutar
    backend = DeepSeekBackend()
    modelos = backend.ping()
    assert "deepseek-flash" in modelos, "deepseek-flash no visible en /models"
    print("   ping /models OK (gratis)")

    pil = Piloto(args.out)
    total = len(problemas) * len(ARMS) * N_INTENTOS
    hecho_nuevos = 0

    if not args.skip_smoke:
        print("== smoke (3 llamadas, 1 problema gsm8k) ==")
        p0 = next(p for p in problemas if p["slice"] == "gsm8k")
        for arm in ARMS:
            r, nuevo = pil.pull(p0, arm, 0, backend, ejecutar)
            print(f"   smoke {arm}: reward={r} nuevo={nuevo} "
                  f"gastado=${pil.gastado:.6f}")
        print(f"   gastado tras smoke: ${pil.gastado:.6f}")

    print(f"== piloto: {total} pulls (3 brazos x 2 intentos x 30) ==")
    try:
        for p in problemas:
            for arm in ARMS:
                for i in range(N_INTENTOS):
                    r, nuevo = pil.pull(p, arm, i, backend, ejecutar)
                    if nuevo:
                        hecho_nuevos += 1
            if hecho_nuevos and hecho_nuevos % 30 == 0:
                print(f"   {len(pil.hechos)}/{total} pulls | "
                      f"gastado ${pil.gastado:.4f} | {time.time()-t0:.0f}s",
                      flush=True)
    except RuntimeError as e:
        print(f"\nABORTO POR FRENO: {e}")
        print(f"   parcial: {len(pil.hechos)} pulls, "
              f"gastado ${pil.gastado:.4f} — sin veredicto")
        return 2

    pulls = list(pil.hechos.values())
    ver = veredicto_puerta(pulls)
    ver["meta"] = {"experimento": "ALMA-EXP67 piloto anti-colapso",
                   "pulls": len(pulls), "llamadas_api": backend.llamadas,
                   "costo_total_usd": round(pil.gastado, 4),
                   "freno_usd": TOPE_USD,
                   "duracion_s": round(time.time() - t0, 1),
                   "regla": "pasa si ningun brazo gana >80% de los "
                            "problemas de cada slice (media de 2 intentos, "
                            "gana el estrictamente mayor)"}
    with open(os.path.join(args.out, "pilot_verdict.json"), "w") as f:
        json.dump(ver, f, indent=2, ensure_ascii=False)

    print("\n================ VEREDICTO PUERTA ================")
    for sl, inf in ver["slices"].items():
        print(f"  {sl}: wins={inf['wins']} empates={inf['empates']} "
              f"shares={inf['shares']} max={inf['max_share']} "
              f"-> {'PASA' if inf['pasa'] else 'COLAPSA'}")
    print(f"  costo total: ${pil.gastado:.4f} | llamadas: {backend.llamadas} "
          f"| {ver['meta']['duracion_s']}s")
    print("  PUERTA:", "ABIERTA — correr oraculo"
          if ver["pasa_puerta"] else
          "CERRADA — activar backup pre-registrado (HumanEval/ARC-Challenge)")
    print("==================================================")
    return 0 if ver["pasa_puerta"] else 1


if __name__ == "__main__":
    sys.exit(main())
