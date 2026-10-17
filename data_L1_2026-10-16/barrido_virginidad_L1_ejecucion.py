#!/usr/bin/env python3
"""Barrido amplio de virginidad para el pre-registro L1 (16/10/2026).

Criterio: el de la v3 (§5.6) — un id es virgen si no aparece en
ninguna posición estructural de id de réplica en ningún archivo
JSON/JSONL del árbol completo de alma-prototype (incluido
integracion_fase21/): listas de enteros bajo claves tipo
replicas/seeds/panel/ids/train/held/split/e3, escalares bajo esas
claves, claves de dict que parsean como entero con valores
numéricos, y cualquier secuencia de >=2 enteros en cualquier
posición (clasificadas por contexto). Extra de esta corrida: un
barrido de texto plano sobre el resto de archivos de texto
(.py/.md/.txt/.sh/.csv) para los mismos ids, clasificado aparte.
Controles: el detector debe encontrar los rangos ya usados
[200..219] (EXP64b) y [4000..4029] (pool v3) en posición de
réplica; si no los encuentra, el barrido no vale.
"""
import json, os, re, sys

RAIZ = os.path.expanduser("~/workspace/alma-prototype")
EXCLUIR_DIRS = {".git", "__pycache__", "data_preregistro_L1_2026-10-16", "data_L1_2026-10-16"}
CANDIDATOS = {
    "train_L1": list(range(20000, 20072)),
    "heldout_L1": list(range(21000, 21048)),
    "e3_L1": list(range(22000, 22024)),
    "pool_L1": list(range(23000, 23060)),
}
CONTROLES = {"control_exp64b": list(range(200, 220)), "control_pool_v3": list(range(4000, 4030))}
TODOS = {}
for nombre, ids in list(CANDIDATOS.items()) + list(CONTROLES.items()):
    for i in ids:
        TODOS[i] = nombre
CLAVES_REPLICA = ("replica", "seed", "panel", "ids", "train", "held", "split", "e3", "rep")

def es_clave_replica(clave):
    c = str(clave).lower()
    return any(k in c for k in CLAVES_REPLICA)

def recorrer(nodo, ruta, hits, archivo):
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            r = f"{ruta}/{k}"
            # clave de dict que parsea como entero con valor numérico
            try:
                ki = int(k)
            except (TypeError, ValueError):
                ki = None
            if ki is not None and ki in TODOS and isinstance(v, (int, float)):
                hits.append((archivo, TODOS[ki], ki, r, "clave_dict_entero"))
            if isinstance(v, int) and not isinstance(v, bool) and v in TODOS:
                cat = "estructural_replica" if es_clave_replica(k) else "escalar_otra_clave"
                hits.append((archivo, TODOS[v], v, r, cat))
            recorrer(v, r, hits, archivo)
    elif isinstance(nodo, list):
        enteros = [x for x in nodo if isinstance(x, int) and not isinstance(x, bool)]
        if len(enteros) >= 2:
            for x in enteros:
                if x in TODOS:
                    ult = ruta.rsplit("/", 1)[-1]
                    cat = "estructural_replica" if es_clave_replica(ult) else "secuencia_enteros"
                    hits.append((archivo, TODOS[x], x, ruta, cat))
        for idx, v in enumerate(nodo):
            if isinstance(v, (dict, list)):
                recorrer(v, f"{ruta}[{idx}]", hits, archivo)

def main():
    archivos_json = []
    for base, dirs, files in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in EXCLUIR_DIRS]
        for f in files:
            if f.endswith((".json", ".jsonl")):
                archivos_json.append(os.path.join(base, f))
    hits = []
    no_parseables = []
    parseados = 0
    for path in sorted(archivos_json):
        rel = os.path.relpath(path, RAIZ)
        try:
            if path.endswith(".jsonl"):
                for linea in open(path, encoding="utf-8", errors="replace"):
                    linea = linea.strip()
                    if linea:
                        recorrer(json.loads(linea), "", hits, rel)
            else:
                recorrer(json.load(open(path, encoding="utf-8")), "", hits, rel)
            parseados += 1
        except Exception:
            no_parseables.append(rel)
    # texto plano para no parseables y resto de archivos de texto
    patron = re.compile(r"\b(" + "|".join(str(i) for i in sorted(TODOS)) + r")\b")
    hits_texto = []
    for base, dirs, files in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in EXCLUIR_DIRS]
        for f in files:
            p = os.path.join(base, f)
            rel = os.path.relpath(p, RAIZ)
            if rel in no_parseables or f.endswith((".py", ".md", ".txt", ".sh", ".csv")):
                try:
                    txt = open(p, encoding="utf-8", errors="replace").read()
                except Exception:
                    continue
                for m in patron.finditer(txt):
                    v = int(m.group(1))
                    hits_texto.append((rel, TODOS[v], v, "texto_plano"))
    resumen = {}
    for nombre, ids in list(CANDIDATOS.items()) + list(CONTROLES.items()):
        hs = [h for h in hits if h[1] == nombre]
        ht = [h for h in hits_texto if h[1] == nombre]
        resumen[nombre] = {
            "rango": [ids[0], ids[-1]], "n_ids": len(ids),
            "hits_estructurales": [list(h) for h in hs],
            "hits_texto_extra": [list(h) for h in ht if not any(x[0] == h[0] and x[2] == h[2] for x in hs)],
        }
    salida = {
        "archivos_json_jsonl": len(archivos_json), "parseados": parseados,
        "no_parseables": no_parseables, "resumen": resumen,
    }
    out = os.path.join(RAIZ, "data_L1_2026-10-16", "barrido_virginidad_ejecucion.json")
    json.dump(salida, open(out, "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: {"rango": v["rango"], "n_hits_estruct": len(v["hits_estructurales"]),
                          "n_hits_texto_extra": len(v["hits_texto_extra"])}
                      for k, v in resumen.items()}, indent=1))
    print("archivos:", len(archivos_json), "parseados:", parseados, "no_parseables:", no_parseables)
    print("salida:", out)

if __name__ == "__main__":
    main()
