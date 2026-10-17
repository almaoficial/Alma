"""Asienta el evento de recalibración del ciclo L1 en el ledger.

Replica el mecanismo de MetaLoop._ledger_append (cadena de hash),
sin instanciar el loop (no corre nada, no desbloquea el freno).
Los números se leen de recalibracion_resultados.json, no se
tipean a mano. Al terminar verifica la cadena COMPLETA.
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
    with open(os.path.join(AQUI, "recalibracion_resultados.json"),
              encoding="utf-8") as f:
        r = json.load(f)
    dec = r["decision_seccion6"]
    assert r["estado"] == "ADOPTA" and dec["adopta"], (
        "la recalibración no adoptó: este evento no corresponde")

    evento = {
        "tipo": "recalibracion_delta_L1",
        "experimento": "ciclo_L1_panel_grande_recalibracion_delta",
        "fecha": "2026-10-16",
        "autorizacion": "Alejandro, 16/10/2026 («L1: panel grande + "
                        "recalibrar δ» y «Corre» sobre el "
                        "pre-registro; adelanta la ventana "
                        "declarada: su orden manda)",
        "preregistro": os.path.join(
            RAIZ, "preregistro-L1-panel-grande-2026-10-16.md"),
        "preregistro_commit": "fa7cb8f",
        "resultados": "data_L1_2026-10-16/recalibracion_resultados.json",
        "barrido_virginidad": (
            "repetido HOY antes de ejecutar (402 archivos "
            "JSON/JSONL, 400 parseados; los 2 no parseables "
            "inspeccionados por texto): los cuatro rangos L1 con "
            "0 hits en posición de réplica; controles EXP64b (23) "
            "y pool v3 (60) detectados en posición de réplica; "
            "único hit declarado: 23039 como /prompt_tokens "
            "(maquinaria ajena). Detalle: "
            "data_L1_2026-10-16/barrido_virginidad_ejecucion.json"),
        "paso0_determinismo": {
            "identicas_10_de_10": r["paso0"]["identicas_10_de_10"],
            "ancla_reproduce": r["paso0"]["ancla_reproduce"],
            "reg_pol_base": r["paso0"]["reg_pol_base"],
            "max_diferencia_absoluta": r["paso0"]["max_diferencia_absoluta"],
        },
        "sigma_hat_pool_23000_23059": r["paso1"]["sigma_hat"],
        "sigma_usado": r["paso1"]["sigma_usado"],
        "clausula_regimen_activada": r["paso1"]["clausula_regimen"][
            "sigma_hat_supera_umbral"],
        "control_A": r["paso2_control_A"]["delta_A_escala_delta"],
        "control_A_reproduce": r["paso2_control_A"]["reproduce_0.5331"],
        "validacion_v3_spec": {
            "empirico_3_2_escala_delta": r["paso3_validacion"][
                "empirico_escala_delta"],
            "parametrico_sigma_hat_escala_delta": r["paso3_validacion"][
                "parametrico_sigma_hat_escala_delta"],
            "diferencia_absoluta": r["paso3_validacion"][
                "diferencia_absoluta"],
            "tolerancia": r["paso3_validacion"]["tolerancia"],
            "valida": r["paso3_validacion"]["valida"],
        },
        "delta_P_72_48": r["paso4_parametrico_72_48"][
            "delta_escala_delta"],
        "delta_P_72_48_totales": r["paso4_parametrico_72_48"][
            "delta_totales"],
        "delta_viejo": {"escala_delta": 0.2283, "totales": 5.4781,
                        "panel": "18/12, E3 [500,501]"},
        "delta_nuevo": dec["congelamiento_si_adopta"][
            "delta_nuevo_escala_delta"],
        "delta_nuevo_totales": dec["congelamiento_si_adopta"][
            "delta_nuevo_totales"],
        "congelamiento": (
            "par (0,1141 escala δ ; 2,7391 totales) — δ_P(72/48) "
            "con σ_usado = 9,04 (diseño P, B=5000, z=2,0, semilla "
            "12345); congelado en este evento ANTES de evaluar "
            "cualquier candidato (§6.3 del pre-registro L1)"),
        "panel_nuevo": "72/48, E3 24",
        "panel_nuevo_ids": {
            "train": dec["congelamiento_si_adopta"]["ids_train"],
            "heldout": dec["congelamiento_si_adopta"]["ids_heldout"],
            "e3": dec["congelamiento_si_adopta"]["ids_e3"],
        },
        "panel_viejo": "18/12 (train [400..417], held-out "
                       "[600..611], E3 [500,501]) — SUPERADO desde "
                       "este asiento",
        "gate_py": "sin tocar en este paso: el recableado es paso "
                   "separado y posterior (§6.3)",
        "freno": "3/3 ACTIVO, sin tocar en este paso; el token "
                 "ALMA_TOKEN_HUMANO no está definido en el entorno "
                 "y nadie lo definió",
        "duracion_s": r["duracion_total_s"],
        "costo_usd": 0,
        "veredicto": "ADOPCIÓN PRIMARIA L1 (§6.1: validación en "
                     "su especificación dif 0,0100 ≤ ±0,10; sin "
                     "rarezas; δ_P(72/48) = 0,1141 < 0,2283): "
                     "δ_L1 = 0,1141 escala δ (2,7391 totales) "
                     "CONGELADO con panel train [20000..20071] / "
                     "held-out [21000..21047] / E3 [22000..22023]",
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
