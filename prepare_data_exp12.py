#!/usr/bin/env python3
"""ALMA-EXP12: preparación de datos — el flip real.

120 problemas = 72 sintéticos (6 clases x 12, mezcla de data/ y data_exp2/)
+ 24 GSM8K frescos + 24 MMLU frescos.

Los GSM8K/MMLU usan índices NO medidos en el oráculo de EXP11
(selección seed 1212, documentada en data_exp12/seleccion.json).
Las clases sintéticas se reutilizan tal cual (EXP11 no las midió).

Clases sintéticas elegidas: spread sobre los oráculos estimados de EXP5
(2 brazos) para maximizar la chance de diversidad de brazos con 3 brazos:
  est-single: codigo, herramientas, puzzles
  est-cot:    calculo, qa_multihop, logica
"""
import json
import os
import random
import re
import sys

SEED = 1212
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data_exp12")
RAW = os.path.join(BASE, "data_exp11", "raw")
os.makedirs(OUT, exist_ok=True)

CLASES_SINT = [
    ("data", "codigo"),
    ("data", "herramientas"),
    ("data", "puzzles"),
    ("data", "calculo"),
    ("data", "qa_multihop"),
    ("data_exp2", "logica"),
]
N_GSM8K = 24
N_MMLU = 24
MMLU_SUBJECTS = [
    "college_mathematics", "college_physics", "formal_logic",
    "high_school_mathematics", "abstract_algebra", "college_chemistry",
    "high_school_physics", "high_school_chemistry", "conceptual_physics",
    "machine_learning",
]
LETRAS = ["A", "B", "C", "D"]


def parse_gsm8k_answer(ans):
    m = re.search(r"####\s*(.+)", ans)
    v = (m.group(1) if m else ans).strip()
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+", v):
        v = v.replace(",", "")
    return v


def main():
    rng = random.Random(SEED)

    # --- sintéticas (tal cual, 12 por clase) ---
    sint = []
    for subdir, clase in CLASES_SINT:
        with open(os.path.join(BASE, subdir, f"{clase}.json"),
                  encoding="utf-8") as f:
            ps = json.load(f)
        assert len(ps) == 12, f"{clase}: {len(ps)}"
        sint.extend(ps)
    print(f"sintéticas: {len(sint)} (6 clases x 12)")

    # --- GSM8K frescos (índices no usados en EXP11) ---
    with open(os.path.join(RAW, "gsm8k_test.jsonl"), encoding="utf-8") as f:
        gsm_raw = [json.loads(l) for l in f if l.strip()]
    assert len(gsm_raw) == 1319
    usados11 = set(
        p["indice_original"] for p in json.load(
            open(os.path.join(BASE, "data_exp11", "gsm8k_sample.json"),
                 encoding="utf-8")))
    candidatos = [i for i in range(len(gsm_raw)) if i not in usados11]
    rng.shuffle(candidatos)
    sel_gsm = candidatos[:N_GSM8K]
    problemas_gsm = []
    for j, i in enumerate(sel_gsm):
        r = gsm_raw[i]
        problemas_gsm.append({
            "id": f"gsm8k12-{j:04d}",
            "clase": "gsm8k",
            "enunciado": r["question"].strip(),
            "esperado": parse_gsm8k_answer(r["answer"]),
            "verificador": "exact",
            "fuente": "GSM8K test (openai/grade-school-math)",
            "indice_original": i,
        })
    print(f"GSM8K frescos: {len(problemas_gsm)} "
          f"(reutilizados de EXP11: 0)")

    # --- MMLU frescos ((materia, índice) no usados en EXP11) ---
    usados_mmlu = set(
        (p["materia"], p["indice_original"]) for p in json.load(
            open(os.path.join(BASE, "data_exp11", "mmlu_sample.json"),
                 encoding="utf-8")))
    pool = []
    for s in MMLU_SUBJECTS:
        rows = json.load(open(os.path.join(RAW, f"mmlu_{s}.json"),
                              encoding="utf-8"))
        for i, r in enumerate(rows):
            if (s, i) not in usados_mmlu:
                pool.append((s, i, r))
    assert len(pool) == 1499 - 100, f"pool MMLU inesperado: {len(pool)}"
    rng.shuffle(pool)
    sel_mmlu = pool[:N_MMLU]
    problemas_mmlu = []
    conteo = {}
    for j, (s, i, r) in enumerate(sel_mmlu):
        ch = r["choices"]
        assert len(ch) == 4
        problemas_mmlu.append({
            "id": f"mmlu12-{s}-{i:04d}",
            "clase": "mmlu",
            "enunciado": (
                f"Pregunta: {r['question'].strip()}\n"
                f"A) {ch[0]}\nB) {ch[1]}\nC) {ch[2]}\nD) {ch[3]}\n"
                "Respondé solo con la letra correcta (A, B, C o D)."
            ),
            "esperado": LETRAS[int(r["answer"])],
            "verificador": "exact",
            "fuente": f"MMLU {s} test (cais/mmlu)",
            "materia": s,
            "indice_original": i,
        })
        conteo[s] = conteo.get(s, 0) + 1
    print(f"MMLU frescos: {len(problemas_mmlu)} {conteo} "
          f"(reutilizados de EXP11: 0)")

    with open(os.path.join(OUT, "gsm8k_sample.json"), "w",
              encoding="utf-8") as f:
        json.dump(problemas_gsm, f, indent=1, ensure_ascii=False)
    with open(os.path.join(OUT, "mmlu_sample.json"), "w",
              encoding="utf-8") as f:
        json.dump(problemas_mmlu, f, indent=1, ensure_ascii=False)

    seleccion = {
        "seed": SEED,
        "fecha": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "sinteticas": {
            "clases": [c for _, c in CLASES_SINT],
            "total": len(sint),
            "nota": "reutilizadas tal cual de data/ y data_exp2/ "
                    "(EXP11 no las midió en su oráculo)",
        },
        "gsm8k": {
            "fuente": "data_exp11/raw/gsm8k_test.jsonl (1319)",
            "seleccionados": N_GSM8K,
            "metodo": "shuffle con seed 1212 excluyendo los 100 índices "
                      "de EXP11, primeros 24",
            "indices_originales": sel_gsm,
            "reutilizados_exp11": 0,
        },
        "mmlu": {
            "fuente": "data_exp11/raw/mmlu_*.json (pool 1499)",
            "seleccionados": N_MMLU,
            "metodo": "pool excluyendo los 100 (materia, índice) de EXP11, "
                      "shuffle con seed 1212, primeros 24",
            "seleccion": [[s, i] for s, i, _ in sel_mmlu],
            "conteo_por_materia": conteo,
            "reutilizados_exp11": 0,
        },
        "total": len(sint) + len(problemas_gsm) + len(problemas_mmlu),
    }
    with open(os.path.join(OUT, "seleccion.json"), "w",
              encoding="utf-8") as f:
        json.dump(seleccion, f, indent=2, ensure_ascii=False)
    print(f"total: {seleccion['total']} -> {OUT}")
    print("OK")


if __name__ == "__main__":
    sys.exit(main())
