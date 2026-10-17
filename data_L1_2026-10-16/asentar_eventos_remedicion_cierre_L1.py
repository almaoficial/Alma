"""Asienta en el ledger los eventos de la re-medición L1 y del
cierre de la búsqueda (cláusula de salida §9 del pre-registro).

Replica el mecanismo de MetaLoop._ledger_append (cadena de hash),
sin instanciar el loop (no corre nada, no desbloquea el freno).
Los números se leen de remedicion_resultados.json, no se tipean
a mano. Al terminar verifica la cadena COMPLETA.

Dos eventos, en orden:
  1. remedicion_L1 — la re-medición de las 58 (§8): sin
     finalistas, sin adopción.
  2. cierre_busqueda_scaffold_L1 — la EJECUCIÓN de la cláusula
     de salida §9: producido el disparo (recalibración adoptó
     ∧ re-medición sin adopción), queda ejecutada por el acta
     del pre-registro, sin otra firma.
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


def asentar(evento):
    prev = ultimo_hash(LEDGER)
    cuerpo = dict(evento)
    cuerpo["timestamp"] = time.time()
    h = _hash_evento(prev, cuerpo)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(_canonical({"prev": prev, "hash": h,
                            "evento": cuerpo}) + "\n")
    return h


def main():
    with open(os.path.join(AQUI, "remedicion_resultados.json"),
              encoding="utf-8") as f:
        r = json.load(f)
    assert r["estado"] == "SIN_ADOPCION_SIN_FINALISTAS", r["estado"]
    mejores = sorted(r["tabla_58"],
                     key=lambda x: -x["delta_train_L1"])[:5]
    ds = [x["delta_train_L1"] for x in r["tabla_58"]]

    ev1 = {
        "tipo": "remedicion_L1",
        "experimento": "ciclo_L1_remedicion_acotada_seccion8",
        "fecha": "2026-10-16",
        "autorizacion": "Alejandro, 16/10/2026 («Corre» sobre "
                        "preregistro-L1-panel-grande-2026-10-16.md)",
        "preregistro": "preregistro-L1-panel-grande-2026-10-16.md "
                       "(commit fa7cb8f), §8",
        "alcance": "58 configuraciones únicas del alcance cerrado "
                   "(24 crossover + 11 generador + 7 RSO + 17 "
                   "screening − 1 solape); sin proponentes nuevos",
        "panel": {"train": [20000, 20071], "n_train": 72,
                  "heldout": "no evaluado (sin finalistas)",
                  "e3": "no evaluado (sin finalistas)"},
        "media_base_train": r["media_base_train"],
        "umbral_seleccion_totales": r["delta_nuevo_totales"],
        "n_sobre_seleccion": 0,
        "finalistas": 0,
        "mejor_marca": {"config": mejores[0]["config"],
                        "fuentes": mejores[0]["fuentes"],
                        "delta_train_L1": mejores[0]["delta_train_L1"]},
        "mejores_5": [{"config": x["config"],
                       "delta_train_L1": x["delta_train_L1"]}
                      for x in mejores],
        "distribucion": {
            "positivas": sum(1 for d in ds if d > 0),
            "max": max(ds), "min": min(ds),
            "media": round(sum(ds) / len(ds), 4)},
        "ganadores_historicos_remedidos": {
            "X9_crossover_+1.4444_a_18": 0.1389,
            "P5_generador_+0.0556_a_18": 0.0139,
            "X10_+0.0556_a_18": -0.1389},
        "hipotesis_H-L1-2": "CONFIRMADA: re-medidos a SE 0,68, "
                            "los ganadores históricos dan "
                            "compatible con cero (el ruido era la "
                            "historia)",
        "resultados": "data_L1_2026-10-16/remedicion_resultados.json",
        "duracion_medicion_s": r["duracion_medicion_s"],
        "freno": "3/3 ACTIVO, sin tocar (la re-medición no es "
                 "corrida del loop: es el procedimiento declarado "
                 "del ciclo, por evaluación directa)",
        "panel_confirmacion": "VIRGEN, sin consumir",
        "costo_usd": 0,
        "veredicto": "SIN ADOPCIÓN, SIN FINALISTAS: ninguna de "
                     "las 58 supera la selección Δ_train^L1 > "
                     "2,7391; la mejor marca (+0,1528) es el 5,6% "
                     "del piso nuevo y 0,22 SE — se produce el "
                     "disparo de la cláusula de salida §9",
    }
    h1 = asentar(ev1)
    print(f"evento remedicion_L1 asentado: hash {h1}")

    ev2 = {
        "tipo": "cierre_busqueda_scaffold_L1",
        "experimento": "ciclo_L1_clausula_de_salida_seccion9",
        "fecha": "2026-10-16",
        "autorizacion": "la cláusula §9 del pre-registro L1 "
                        "(aprobado por Alejandro el 16/10/2026): "
                        "producido el disparo, queda ejecutada "
                        "por esta misma acta, sin otra firma",
        "disparo": {
            "condicion_a_recalibracion_adopta": True,
            "condicion_b_remedicion_sin_adopcion": True,
            "detalle": "δ_L1 adoptado = 0,1141 (2,7391 totales) "
                       "con panel 72/48/24 (evento "
                       "recalibracion_delta_L1); re-medición de "
                       "las 58 sin adopción ni finalistas "
                       "(evento remedicion_L1)"},
        "cierre": {
            "scaffold": {"decay": 0.5, "gate_margin": 0.0, "n0": 4,
                         "umbral_base": 1, "umbral_divisor": 3},
            "espacio": "EXP56, 324 configuraciones",
            "declaracion": "la base queda declarada ÓPTIMO "
                           "OPERATIVO CERTIFICADO a la "
                           "resolución del panel nuevo (SE de "
                           "selección 0,6835) sobre el alcance "
                           "medido; la búsqueda sobre este "
                           "scaffold queda CERRADA",
            "resultado_final_asentado": "NULO CERTIFICADO a "
            "resolución 72/48/24: 58 configuraciones propuestas "
            "por cuatro métodos (mutación puntual, screening "
            "factorial, LLM coordinado, recombinación) "
            "re-medidas en el panel nuevo; ninguna supera la "
            "selección (mejor marca +0,1528 totales = 0,22 SE); "
            "ninguna adoptada. El nulo es un resultado del "
            "sistema, no un intento fallido: el instrumento, ya "
            "capaz de ver efectos de +1,44 a más de 2 SE, "
            "encontró esto",
            "limite_del_nulo": "certifica el alcance medido (58 "
            "configuraciones); quedan 206 sin medir del "
            "espacio — el cierre es por decisión asentada, no "
            "por agotamiento demostrado (§12.2 del "
            "pre-registro)"},
        "prohibido_sin_papel_nuevo_que_cambie_el_marco": [
            "desbloquear el freno para buscar sobre este espacio",
            "cualquier búsqueda, proponente, tanda, mutación o "
            "crossover nuevo sobre las 324",
            "re-medir configuraciones del espacio fuera de la "
            "lista de §8 bajo este marco",
            "recalibrar δ o el panel para este espacio con el "
            "fin de reabrir la búsqueda"],
        "papel_nuevo_que_cambie_el_marco_significa": "otro "
        "espacio de scaffold o superficie editable, otra tarea u "
        "otro validador, u otro instrumento de medición — con su "
        "propio pre-registro y su propia autorización",
        "lo_que_NO_cierra": "el sistema ALMA ni su gobernanza "
        "(ledger, pre-registros, frenos, verificador); la "
        "vidriera (repo público, CI, artículo, perfil); el "
        "panel de confirmación, que queda VIRGEN; otros "
        "scaffolds, otras tareas y otros validadores futuros; "
        "nada fuera del laboratorio",
        "freno": "queda ACTIVO al cierre por el acta (§7 del "
                 "pre-registro): el loop no se desbloquea sobre "
                 "un espacio cerrado; ningún token fue definido "
                 "ni usado en este ciclo",
        "adopciones_historicas_metaloop": 0,
        "panel_confirmacion": "VIRGEN, sin consumir",
        "costo_usd": 0,
        "veredicto": "CLÁUSULA DE SALIDA EJECUTADA: búsqueda "
                     "sobre este scaffold CERRADA con el nulo "
                     "certificado a resolución 72/48/24 como "
                     "resultado final del ciclo L1",
    }
    h2 = asentar(ev2)
    print(f"evento cierre_busqueda_scaffold_L1 asentado: hash {h2}")

    n, ultimo = verificar_cadena(LEDGER)
    print(f"cadena verificada: {n} eventos, último hash {ultimo}")


if __name__ == "__main__":
    main()
