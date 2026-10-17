# -*- coding: utf-8 -*-
"""Construye corpus_planes.jsonl y planes_reales.jsonl desde corpus_datos.py.
Uso: python3 construir_corpus.py  (idempotente; sobrescribe ambos archivos)"""
import json
import os

from corpus_datos import DIAS, REALES

AQUI = os.path.dirname(os.path.abspath(__file__))


def main():
    with open(os.path.join(AQUI, "corpus_planes.jsonl"), "w", encoding="utf-8") as f:
        for d in DIAS:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    with open(os.path.join(AQUI, "planes_reales.jsonl"), "w", encoding="utf-8") as f:
        for fecha in sorted(REALES):
            f.write(json.dumps({"fecha": fecha, "variante": "real_historico",
                                "rep": 0, "texto": REALES[fecha]},
                               ensure_ascii=False) + "\n")
    print(f"corpus: {len(DIAS)} días · reales: {len(REALES)} planes")


if __name__ == "__main__":
    main()
