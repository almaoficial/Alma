"""Asienta el evento de recableado en el ledger del meta-loop.

Replica el mecanismo de MetaLoop._ledger_append (cadena de hash:
prev = hash del último evento; hash = _hash_evento(prev, cuerpo);
línea canónica {"prev","hash","evento"}), sin instanciar el loop
(no corre nada). Al terminar, verifica la cadena COMPLETA del
ledger recomputando cada hash.

Los números de la evaluación base se leen de resultados_base.json
(generado por run_recableado_base.py), no se tipean a mano.
"""

import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from alma_service.metaloop import _canonical, _hash_evento  # noqa: E402

LEDGER = os.path.join(RAIZ, "metaloop_ledger.jsonl")
AQUI = os.path.dirname(os.path.abspath(__file__))


def ultimo_hash(path):
    prev = "GENESIS"
    with open(path, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                prev = json.loads(linea)["hash"]
    return prev


def verificar_cadena(path):
    prev = "GENESIS"
    n = 0
    with open(path, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            reg = json.loads(linea)
            assert reg["prev"] == prev, f"cadena rota en el evento {n + 1}"
            assert reg["hash"] == _hash_evento(prev, reg["evento"]), (
                f"hash inválido en el evento {n + 1}")
            prev = reg["hash"]
            n += 1
    return n, prev


def main():
    with open(os.path.join(AQUI, "resultados_base.json"),
              encoding="utf-8") as f:
        base = json.load(f)
    pn = base["panel_nuevo"]

    evento = {
        "tipo": "recableado_puerta_delta_v3",
        "experimento": "recableado_puerta_tras_recalibracion_delta_v3",
        "fecha": "2026-10-16",
        "autorizacion": "Alejandro, 16/10/2026 («Vamos a hacerlo»)",
        "preregistro": os.path.join(
            RAIZ, "preregistro-recalibracion-delta-v3-2026-10-16.md"),
        "resultados_calibracion": os.path.join(
            RAIZ, "resultados-recalibracion-delta-v3-2026-10-16.md"),
        "commit_calibracion": "b834e3d",
        "documento_recableado": os.path.join(
            RAIZ, "recableado-puerta-delta-v3-2026-10-16.md"),
        "escala_declarada": (
            "TOTALES (puntos de regret total por réplica): la escala en "
            "que metaloop._evaluar (media de reg_pol) y "
            "PuertaDosSplits.decidir producen los Δ que "
            "decidir_auto_adopcion compara contra PISO_RUIDO_DELTA. "
            "Equivalencia: totales / 24 = escala δ (media por bloque)"),
        "delta_anterior": {
            "cableado": 0.53,
            "calibrado_escala_delta": 0.5331,
            "panel": "3/2 (train [0,1,2], held-out [3,4])",
        },
        "delta_cableado": 5.4781,
        "delta_cableado_escala_delta": 0.2283,
        "par_congelado": "(0,2283 escala delta ; 5,4781 totales) — el "
                         "asentado en resultados v3; 0,2283 x 24 = "
                         "5,4792 difiere por redondeo (0,0011)",
        "panel_nuevo": {
            "train": list(range(400, 418)),
            "heldout": list(range(600, 612)),
            "e3_sin_cambio": [500, 501],
        },
        "archivos_cambiados": [
            "alma_service/gate.py: PISO_RUIDO_DELTA 0.53 -> 5.4781 "
            "(totales) + REGLA_AUTO_ADOPCION + notas de escala e "
            "historia en docstring y comentarios",
            "alma_service/metaloop.py: TRAIN_REPS/HELDOUT_REPS del "
            "panel 3/2 (alias e56) al panel 18/12 [400..417]/"
            "[600..611]; e56 y puerta_e3 intactos",
            "test_piso_ruido_puerta.py: suite del piso re-escalada a "
            "totales (banda/borde/sobre la banda contra 5,4781)",
            "test_fase23_freno_humano.py y "
            "test_gobernanza_auto_adopcion.py: fakes de _evaluar "
            "reconocen el train por TRAIN_REPS cableado y usan Δ=6 "
            "(el Δ=5 de sus fixtures caía en la banda nueva)",
        ],
        "evaluacion_base_panel_nuevo": {
            "media_train_18": pn["train"]["media"],
            "media_heldout_12": pn["heldout"]["media"],
            "delta_base_contra_base": [
                base["delta_base_contra_base"]["delta_in"],
                base["delta_base_contra_base"]["delta_ho"]],
            "determinismo": "segunda evaluación con caché fresco "
                            "idéntica por réplica",
            "ancla_panel_historico": "reg_pol [0..4] = "
            "[71, 83, 90, 84, 81], idénticos al Paso 0 de v1/v2/v3",
            "e3_media_base": base["e3_contexto"]["media"],
            "resultados": "data_recableado_puerta_v3/resultados_base.json",
        },
        "suites_gobernanza": {
            "baseline_pre_recableado": "44/44 PASS",
            "post_recableado": "44/44 PASS",
            "diferencias": "ninguna (dos regresiones intermedias por "
                           "fixtures atados al panel/piso viejos, "
                           "corregidas y reverificadas)",
        },
        "candidatos_evaluados": 0,
        "costo_usd": 0,
        "nota_arbol": "gate.py y metaloop.py entran al commit con las "
                      "capas que vivían sin commitear en el árbol "
                      "(auto-adopción 11/10, E3 28/9, freno de "
                      "estancamiento, archivo de variantes), "
                      "verificadas coherentes por las suites antes y "
                      "después; el resto de archivos modificados del "
                      "árbol queda fuera de este commit, como estaba",
        "hallazgo_documento_resultados_v3": (
            "resultados-recalibracion-delta-v3-2026-10-16.md está "
            "truncado en disco (9.563 bytes; corta a mitad de frase en "
            "§Congelamiento con el marcador literal '[truncated 5474 "
            "chars]'); los valores congelados se verificaron contra "
            "este ledger (evento recalibracion_delta_v3) y el commit "
            "b834e3d, que coinciden — el recableado no depende de la "
            "cola perdida del documento"),
        "veredicto": "RECABLEADO COMPLETO: la puerta compara con "
                     "5,4781 totales (δ 0,2283) sobre el panel 18/12; "
                     "scaffold base evaluado sobre el panel nuevo "
                     "antes de cualquier candidato (§5.5); ningún "
                     "candidato evaluado en este paso",
    }

    prev = ultimo_hash(LEDGER)
    cuerpo = dict(evento)
    cuerpo["timestamp"] = time.time()
    h = _hash_evento(prev, cuerpo)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(_canonical({"prev": prev, "hash": h,
                            "evento": cuerpo}) + "\n")
    n, ultimo = verificar_cadena(LEDGER)
    print(f"evento asentado: hash {h}")
    print(f"cadena verificada: {n} eventos, último hash {ultimo}")


if __name__ == "__main__":
    main()
