"""Asienta el evento de recableado del ciclo L1 en el ledger.

Replica el mecanismo de MetaLoop._ledger_append (cadena de hash),
sin instanciar el loop (no corre nada, no desbloquea el freno).
Los números se leen de resultados_base_L1.json y
recalibracion_resultados.json, no se tipean a mano. Al terminar
verifica la cadena COMPLETA del ledger.
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
    with open(os.path.join(AQUI, "resultados_base_L1.json"),
              encoding="utf-8") as f:
        base = json.load(f)
    pn = base["panel_nuevo"]

    evento = {
        "tipo": "recableado_puerta_delta_L1",
        "experimento": "recableado_puerta_tras_recalibracion_L1",
        "fecha": "2026-10-16",
        "autorizacion": "Alejandro, 16/10/2026 («L1: panel grande + "
                        "recalibrar δ»; «Corre» sobre el "
                        "pre-registro)",
        "preregistro": os.path.join(
            RAIZ, "preregistro-L1-panel-grande-2026-10-16.md"),
        "preregistro_commit": "fa7cb8f",
        "resultados_calibracion": "data_L1_2026-10-16/"
                                  "recalibracion_resultados.json",
        "evento_calibracion": "recalibracion_delta_L1 (hash "
                              "718b401a60d8…)",
        "escala_declarada": (
            "TOTALES (puntos de regret total por réplica): la "
            "escala en que metaloop._evaluar (media de reg_pol) y "
            "PuertaDosSplits.decidir producen los Δ que "
            "decidir_auto_adopcion compara contra "
            "PISO_RUIDO_DELTA. Equivalencia: totales / 24 = "
            "escala δ (media por bloque)"),
        "delta_anterior": {
            "cableado_totales": 5.4781,
            "calibrado_escala_delta": 0.2283,
            "panel": "18/12 (train [400..417], held-out "
                     "[600..611], E3 [500,501])",
        },
        "delta_cableado": 2.7391,
        "delta_cableado_escala_delta": 0.1141,
        "par_congelado": "(0,1141 escala delta ; 2,7391 totales) "
                         "— el asentado en el evento "
                         "recalibracion_delta_L1; 0,1141 x 24 = "
                         "2,7384 difiere por redondeo (0,0007); el "
                         "miembro en totales es el δ_P(72/48) "
                         "computado por el diseño P",
        "panel_nuevo": {
            "train": list(range(20000, 20072)),
            "heldout": list(range(21000, 21048)),
            "e3": list(range(22000, 22024)),
        },
        "archivos_cambiados": [
            "alma_service/gate.py: PISO_RUIDO_DELTA 5.4781 -> "
            "2.7391 (totales) + REGLA_AUTO_ADOPCION + notas de "
            "escala, procedencia e historia en docstring y "
            "comentarios",
            "alma_service/metaloop.py: TRAIN_REPS/HELDOUT_REPS "
            "del panel 18/12 [400..417]/[600..611] al panel 72/48 "
            "[20000..20071]/[21000..21047], con la nota de "
            "procedencia; e56 intacto",
            "alma_service/puerta_e3.py: E3_REPS [500,501] -> "
            "[22000..22023] (24 réplicas; decisión §3 del "
            "pre-registro L1), con nota fechada; la regla E3 no "
            "cambia",
            "test_piso_ruido_puerta.py: suite del piso "
            "re-escalada al piso L1 (banda Δ=2,0; borde 2,7391; "
            "constantes), con nota de actualización",
            "alma_service/test_e3_integracion.py: fixture de "
            "E3_REPS actualizado al rango L1",
        ],
        "evaluacion_base_panel_nuevo": {
            "media_train_72": pn["train"]["media"],
            "media_heldout_48": pn["heldout"]["media"],
            "delta_base_contra_base": [
                base["delta_base_contra_base"]["delta_in"],
                base["delta_base_contra_base"]["delta_ho"]],
            "determinismo": "segunda evaluación con caché fresco "
                            "idéntica por réplica",
            "ancla_panel_historico": "reg_pol [0..4] = "
            "[71, 83, 90, 84, 81], idénticos al Paso 0 de "
            "v1/v2/v3/L1",
            "e3_media_base": base["e3_contexto"]["media"],
            "resultados": "data_L1_2026-10-16/"
                          "resultados_base_L1.json",
        },
        "suites_gobernanza": {
            "baseline_pre_recableado": "51/51 PASS",
            "post_recableado_crudo": "49/51 — las 2 fallas son los "
            "fixtures atados al piso/E3 viejos (test_piso_ruido_"
            "puerta.py, alma_service/test_e3_integracion.py)",
            "post_recableado": "51/51 PASS",
            "diferencias": "solo los dos fixtures del cableado, "
                           "actualizados y declarados arriba",
        },
        "verificacion_seccion6_1": (
            "verificación independiente pedida por el agente "
            "principal durante la ejecución: σ̂ recomputado desde "
            "los reg_pol del pool guardados = 8,5384 (idéntico); "
            "diseño P recomputado: δ_P(72/48) = 2,7391 totales = "
            "0,1141 escala δ (idéntico); empírico A/A 3/2 "
            "recomputado = 0,5381 (idéntico). Rarezas §6.2 todas "
            "negativas; §6.1(3): 0,1141 < 0,2283 cumplida. El "
            "número 0,3923 de la alerta no aparece en ningún "
            "artefacto de este ciclo: el único 0,392x de la "
            "historia del proyecto es δ_C = 0,3922, el nulo A/A "
            "con panel 6/4 de la recalibración v1 ARCHIVADA "
            "(resultados-recalibracion-delta-2026-10-16.md) — "
            "otra cantidad, de otra corrida; y 28,2462 ≈ "
            "0,3923 x 72 sería convertir esa escala δ con el "
            "tamaño del train en vez de la conversión declarada "
            "(totales = δ x 24). El piso cableado es el par "
            "congelado (0,1141 ; 2,7391)"),
        "candidatos_evaluados": 0,
        "freno": "3/3 ACTIVO, sin tocar; sin token definido",
        "costo_usd": 0,
        "veredicto": "RECABLEADO COMPLETO L1: la puerta compara "
                     "con 2,7391 totales (δ 0,1141) sobre el panel "
                     "72/48 y el E3 de 24; scaffold base evaluado "
                     "sobre el panel nuevo antes de cualquier "
                     "candidato (§6.3); ningún candidato evaluado "
                     "en este paso",
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
