#!/usr/bin/env python3
"""ALMA-EXP11: preparación de datos — problemas duros reales.

Fuentes públicas:
  - GSM8K test (1319): https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl
  - MMLU test (cais/mmlu vía datasets-server API de HuggingFace):
    materias duras: college_mathematics, college_physics, formal_logic,
    high_school_mathematics, abstract_algebra, college_chemistry,
    high_school_physics, high_school_chemistry, conceptual_physics,
    machine_learning.

Selección determinista (seed 999, documentada en seleccion.json):
  - GSM8K: shuffle de los 1319, primeros 100.
  - MMLU: pool de las 10 materias, shuffle, primeros 100.

NO se inventa ningún problema: todo viene de las fuentes de arriba.
"""
import csv
import json
import os
import random
import re
import sys
import urllib.request

SEED = 999
BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "data_exp11", "raw")
os.makedirs(RAW, exist_ok=True)

MMLU_SUBJECTS = [
    "college_mathematics", "college_physics", "formal_logic",
    "high_school_mathematics", "abstract_algebra", "college_chemistry",
    "high_school_physics", "high_school_chemistry", "conceptual_physics",
    "machine_learning",
]
LETRAS = ["A", "B", "C", "D"]


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "alma-exp11"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def cargar_gsm8k():
    path = "/tmp/gsm8k_test.jsonl"
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    assert len(rows) == 1319, f"GSM8K test inesperado: {len(rows)} filas"
    with open(os.path.join(RAW, "gsm8k_test.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows


def parse_gsm8k_answer(ans):
    m = re.search(r"####\s*(.+)", ans)
    v = (m.group(1) if m else ans).strip()
    # Separador de miles ("1,000" -> "1000") para exact-match numérico.
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+", v):
        v = v.replace(",", "")
    return v


def fetch_mmlu_subject(subject):
    base = ("https://datasets-server.huggingface.co/rows?dataset=cais/mmlu"
            f"&config={subject}&split=test")
    meta = fetch_json(base + "&offset=0&length=1")
    total = meta["num_rows_total"]
    rows = []
    offset = 0
    while offset < total:
        data = fetch_json(base + f"&offset={offset}&length=100")
        for r in data["rows"]:
            rows.append(r["row"])
        offset += len(data["rows"])
        if data.get("partial"):
            break
    assert len(rows) == total, f"{subject}: {len(rows)} != {total}"
    with open(os.path.join(RAW, f"mmlu_{subject}.json"), "w",
              encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    return rows


def main():
    rng = random.Random(SEED)

    print("GSM8K...")
    gsm = cargar_gsm8k()
    idx = list(range(len(gsm)))
    rng.shuffle(idx)
    sel_gsm = idx[:100]
    problemas_gsm = []
    for j, i in enumerate(sel_gsm):
        r = gsm[i]
        problemas_gsm.append({
            "id": f"gsm8k-{j:04d}",
            "clase": "gsm8k",
            "enunciado": r["question"].strip(),
            "esperado": parse_gsm8k_answer(r["answer"]),
            "verificador": "exact",
            "fuente": "GSM8K test (openai/grade-school-math)",
            "indice_original": i,
        })

    print("MMLU (10 materias)...")
    pool = []
    por_materia = {}
    for s in MMLU_SUBJECTS:
        rows = fetch_mmlu_subject(s)
        por_materia[s] = len(rows)
        for i, r in enumerate(rows):
            pool.append((s, i, r))
    print(f"   pool MMLU: {len(pool)} problemas")
    rng.shuffle(pool)
    sel_mmlu = pool[:100]
    problemas_mmlu = []
    conteo = {}
    for j, (s, i, r) in enumerate(sel_mmlu):
        ch = r["choices"]
        assert len(ch) == 4, f"{s}[{i}]: {len(ch)} opciones"
        enunciado = (
            f"Pregunta: {r['question'].strip()}\n"
            f"A) {ch[0]}\nB) {ch[1]}\nC) {ch[2]}\nD) {ch[3]}\n"
            "Respondé solo con la letra correcta (A, B, C o D)."
        )
        problemas_mmlu.append({
            "id": f"mmlu-{s}-{i:04d}",
            "clase": "mmlu",
            "enunciado": enunciado,
            "esperado": LETRAS[int(r["answer"])],
            "verificador": "exact",
            "fuente": f"MMLU {s} test (cais/mmlu)",
            "materia": s,
            "indice_original": i,
        })
        conteo[s] = conteo.get(s, 0) + 1

    out_gsm = os.path.join(BASE, "data_exp11", "gsm8k_sample.json")
    out_mmlu = os.path.join(BASE, "data_exp11", "mmlu_sample.json")
    with open(out_gsm, "w", encoding="utf-8") as f:
        json.dump(problemas_gsm, f, indent=1, ensure_ascii=False)
    with open(out_mmlu, "w", encoding="utf-8") as f:
        json.dump(problemas_mmlu, f, indent=1, ensure_ascii=False)

    seleccion = {
        "seed": SEED,
        "fecha": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "gsm8k": {
            "fuente_url": "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl",
            "total_fuente": 1319,
            "seleccionados": 100,
            "metodo": "shuffle con seed 999, primeros 100",
            "indices_originales": sel_gsm,
        },
        "mmlu": {
            "fuente_api": "https://datasets-server.huggingface.co/rows?dataset=cais/mmlu",
            "dataset": "cais/mmlu",
            "materias": por_materia,
            "pool_total": len(pool),
            "seleccionados": 100,
            "metodo": "pool de 10 materias, shuffle con seed 999, primeros 100",
            "conteo_por_materia_en_muestra": conteo,
        },
    }
    with open(os.path.join(BASE, "data_exp11", "seleccion.json"), "w",
              encoding="utf-8") as f:
        json.dump(seleccion, f, indent=2, ensure_ascii=False)

    print(f"GSM8K: 100 problemas -> {out_gsm}")
    print(f"MMLU: 100 problemas -> {out_mmlu} {conteo}")
    print("OK")


if __name__ == "__main__":
    sys.exit(main())
