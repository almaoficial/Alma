"""Corrida pre-registrada de crossover (16/10/2026).

Pre-registro: preregistro-crossover-2026-10-16.md — leerlo ANTES
de correr cualquiera de los dos pasos. Este script ES el
procedimiento declarado en ese documento:

  Paso 1 — generar y congelar la tanda (US$0, sin LLM):
      python3 correr_crossover.py --generar
      Construye la población declarada (P0 = base vigente + los 11
      válidos de la tanda del generador), extrae mecánicamente el
      conjunto de exclusión (población + ledger + screening) y
      escribe la tanda de hijos a tanda_crossover_<ts>.json con el
      operador de alma_service/crossover.py. NO evalúa a nadie.

  Paso 2 — la corrida (autorizada por Alejandro, «Correr»):
      python3 correr_crossover.py --tanda tanda_crossover_<ts>.json
      Mide cada hijo INDEPENDIENTE contra la base en train
      (validador congelado, panel [400..417]) y lleva SOLO al
      mejor hijo positivo por el camino normal de la puerta
      (dos splits -> E3 -> piso 5,4781 -> auto-adopción), con
      origen_operador='crossover' y sus padres en el audit record.
      Si adopta, mide el Δ de confirmación en el panel virgen
      [5000..5017]/[5100..5111] (adenda 1 del generador). Es UNA
      corrida a efectos del freno de estancamiento: sin adopción,
      la racha pasa de 2/3 a 3/3 y el freno queda ACTIVO por
      diseño (no se desbloquea: el token es de Alejandro).

Sin flags, no hace nada.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service import crossover as x  # noqa: E402
from alma_service.metaloop import (  # noqa: E402
    MetaLoop, SPACES, TRAIN_REPS, HELDOUT_REPS)
from alma_service.gate import (  # noqa: E402
    PuertaDosSplits, decidir_auto_adopcion, PISO_RUIDO_DELTA)
from alma_service.puerta_e3 import (  # noqa: E402
    audit_record_e3, resumen_config_e3)
from alma_service.promotor import NucleoProtegidoError  # noqa: E402
from alma_service.presupuesto import (  # noqa: E402
    PresupuestoFase2, BUCKET_METALOOP)

AQUI = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(AQUI, "alma_store.db")
LEDGER = os.path.join(AQUI, "metaloop_ledger.jsonl")
TANDA_GENERADOR = os.path.join(AQUI, "tanda_generador_1792192469.json")
SCREENING = os.path.join(
    AQUI, "data_screening_factorial_2026-10-16", "resultados.json")
DATA_DIR = os.path.join(AQUI, "data_crossover_2026-10-16")

# Semilla de la corrida, declarada: la tanda entera es
# reproducible a partir de ella (pre-registro §5).
SEMILLA = 20261016

# Base declarada en el pre-registro (§1/§4). Si el scaffold
# vigente difiere, el paso se niega (fail-closed): la población
# del papel parte de esta base.
BASE_DECLARADA = {"decay": 0.5, "gate_margin": 0.0, "n0": 4,
                  "umbral_base": 1, "umbral_divisor": 3}

# Δ_train asentados de los padres (pre-registro §4): etiqueta de
# estrato; la medición que vale es la de cada hijo.
DELTA_TRAIN_PADRES = [0.0, -4.3333, -3.7222, -0.4444, -3.8889,
                      0.0556, -1.3333, -5.0556, -0.6667, -1.6111,
                      -2.9444, -1.2222]
MARCA_MEJOR_PADRE = 0.0556  # Δ_train de P5 (pre-registro §8)

# Panel de confirmación (adenda 1 del generador): solo se consume
# si hay auto-adopción.
PANEL_CONF_TRAIN = list(range(5000, 5018))   # [5000..5017]
PANEL_CONF_HO = list(range(5100, 5112))      # [5100..5111]


def cargar_poblacion(ml):
    """La población cerrada del pre-registro §4: P0 = scaffold
    vigente (debe ser la base declarada) + P1..P11 de la tanda."""
    vigente = ml.scaffold_vigente()
    if vigente != BASE_DECLARADA:
        raise SystemExit(
            f"fail-closed: el scaffold vigente {vigente} no es la "
            f"base declarada del pre-registro {BASE_DECLARADA}")
    with open(TANDA_GENERADOR, encoding="utf-8") as f:
        doc = json.load(f)
    pob = [dict(vigente)] + [dict(c["config"])
                             for c in doc["candidatos"]]
    if len(pob) != 12:
        raise SystemExit(f"población de {len(pob)} padres, "
                         "el pre-registro declara 12")
    for c in pob:
        if sorted(c.keys()) != x.PARAMS or \
                any(c[k] not in x.SPACES[k] for k in x.PARAMS):
            raise SystemExit(f"padre fuera de SPACES: {c}")
    return pob


def paso_generar():
    ml = MetaLoop(DB, presupuesto=PresupuestoFase2(DB))
    pob = cargar_poblacion(ml)
    excluidos = x.conjunto_exclusion(pob, LEDGER, SCREENING)
    res = x.generar_tanda(pob, excluidos, seed=SEMILLA)
    ruta = os.path.join(AQUI, f"tanda_crossover_{int(time.time())}.json")
    x.guardar_tanda(res, ruta, pob,
                    delta_train_padres=DELTA_TRAIN_PADRES,
                    n_excluidos=len(excluidos))
    print(f"tanda congelada: {ruta}")
    print(f"hijos válidos: {len(res['hijos'])}/{res['n_objetivo']} "
          f"(pares procesados: {res['pares_procesados']}/"
          f"{res['pares_total']}, excluidos: {len(excluidos)})")
    if len(res["hijos"]) < x.N_MINIMO_TANDA:
        print(f"OJO: bajo el mínimo declarado ({x.N_MINIMO_TANDA}): "
              "la corrida NO se lanza con esta tanda "
              "(pre-registro §8, tanda insuficiente).")
    return ruta


def _veredicto(adopcion_id, mediciones):
    """Veredictos del pre-registro §8, con nombre exacto."""
    if adopcion_id:
        return "ADOPCIÓN"
    if mediciones and max(m["delta_train"] for m in mediciones) \
            > MARCA_MEJOR_PADRE:
        return "SEÑAL PARCIAL"
    return "FRACASO INFORMATIVO"


def paso_correr(ruta_tanda):
    with open(ruta_tanda, encoding="utf-8") as f:
        doc = json.load(f)
    hijos = doc["hijos"]
    if len(hijos) < x.N_MINIMO_TANDA:
        print(f"tanda insuficiente ({len(hijos)} < "
              f"{x.N_MINIMO_TANDA}): la corrida no se lanza y el "
              "freno no se mueve.")
        return 1
    ml = MetaLoop(DB, presupuesto=PresupuestoFase2(DB))
    if not ml.presupuesto.autorizar(BUCKET_METALOOP, 0.0):
        print("presupuesto del bucket metaloop agotado")
        return 1
    freno_antes = ml.estado_freno()
    if freno_antes["freno_activo"]:
        print(f"freno de estancamiento activo "
              f"({freno_antes['racha_planas']} corridas planas): "
              "la corrida se niega hasta revisión humana.")
        return 1
    vigente = ml.scaffold_vigente()
    if vigente != doc["poblacion"][0]["config"]:
        print("fail-closed: el scaffold vigente cambió desde el "
              "congelamiento de la tanda.")
        return 1

    cache = {}
    media_train_base, _ = ml._evaluar(vigente, TRAIN_REPS, cache)
    base_held, _ = ml._evaluar(vigente, HELDOUT_REPS, cache)

    # Pre-registro de la corrida ANTES de medir (espejo del camino
    # normal: archivo en disco + evento corrida_iniciada).
    prereg = {
        "experimento": "metaloop_crossover",
        "seed": SEMILLA,
        "tanda": ruta_tanda,
        "n_hijos": len(hijos),
        "criterio_parada": "tanda congelada completa, medición "
                           "independiente contra la base",
        "scaffold_partida": vigente,
        "heldout_partida": base_held,
        "criterio_adopcion": ("finalista único: puerta de dos "
                              "splits + E3 siempre exigido + piso "
                              "de ruido 5,4781 (camino normal)"),
        "puerta_e3": resumen_config_e3(),
        "validador": "congelado (e47/e56), panel 18/12 + E3 "
                     "[500,501]",
        "preregistro_experimento":
            "preregistro-crossover-2026-10-16.md",
        "timestamp": time.time(),
    }
    pr_path = os.path.join(
        AQUI, f"metaloop_preregistro_{int(time.time())}.json")
    with open(pr_path, "w", encoding="utf-8") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    ml._ledger_append({"tipo": "corrida_iniciada",
                       "preregistro": pr_path, **prereg})
    ml._emitir_ciclo("metaloop_corrida_iniciada",
                     {"preregistro": pr_path, "seed": SEMILLA,
                      "experimento": "metaloop_crossover"})

    # 1. Medición INDEPENDIENTE de cada hijo contra la base (train).
    mediciones = []
    for h in hijos:
        media, _ = ml._evaluar(h["config"], TRAIN_REPS, cache)
        mediciones.append({
            "indice": h["indice"], "padres": h["padres"],
            "padres_ids": h["padres_ids"], "config": h["config"],
            "herencia": h["herencia"],
            "origen_operador": "crossover",
            "media_train": round(media, 4),
            "delta_train": round(media_train_base - media, 4),
        })
    ml._ledger_append({
        "tipo": "corrida_crossover", "tanda": ruta_tanda,
        "semilla": SEMILLA, "n_hijos": len(mediciones),
        "media_train_base": round(media_train_base, 4),
        "mediciones": mediciones})

    # 2. Finalista único: el mejor hijo con Δ_train > 0.
    positivos = sorted(
        (m for m in mediciones if m["delta_train"] > 0),
        key=lambda m: (-m["delta_train"], m["indice"]))
    finalista = positivos[0] if positivos else None

    puerta = None
    e3 = {"aceptado": False, "e3_exigido": False,
          "e3_evaluado": False, "delta_e3": None,
          "delta_in": 0.0, "delta_ho": 0.0,
          "motivo": "sin finalista: ningún hijo con Δ_train > 0 "
                    "(la puerta no se recorrió)"}
    adoptado = False
    auto_ok, motivo_auto, requiere_si = False, e3["motivo"], False
    adopcion_id = None
    confirmacion = None
    media_held_fin = base_held

    if finalista is not None:
        fin_cfg = finalista["config"]
        media_held_fin, _ = ml._evaluar(fin_cfg, HELDOUT_REPS, cache)
        # El decidir consume las medias ya medidas (la train del
        # finalista es su medición independiente contra la base).
        puerta = PuertaDosSplits.decidir(
            media_train_base, base_held,
            finalista["media_train"], media_held_fin)
        e3 = ml._puerta_e3(vigente, fin_cfg, cache, puerta)
        adoptado = bool(e3["aceptado"])
        if adoptado:
            auto_ok, motivo_auto, requiere_si = \
                decidir_auto_adopcion(e3["delta_in"], e3["delta_ho"])
        else:
            auto_ok, motivo_auto, requiere_si = \
                False, e3["motivo"], False
        rec_e3 = audit_record_e3(
            propuesta={"clave": "scaffold_completo",
                       "anterior": vigente, "nuevo": fin_cfg,
                       "descripcion": "adopción del candidato final",
                       "origen_operador": "crossover",
                       "padres": finalista["padres_ids"],
                       "herencia": finalista["herencia"]},
            delta_in=e3["delta_in"], delta_ho=e3["delta_ho"],
            delta_e3=e3["delta_e3"],
            aceptado=adoptado, motivo=e3["motivo"],
            e3_exigido=e3["e3_exigido"],
            e3_evaluado=e3["e3_evaluado"],
            superficie="scaffold completo",
            efecto_esperado="mejorar el scaffold vigente")
        d_max = (max(e3["delta_in"], e3["delta_ho"])
                 if adoptado else None)
        rec_e3["auto_adopcion"] = {
            "auto_adoptado": bool(auto_ok),
            "motivo": motivo_auto,
            "requiere_si_explicito": bool(requiere_si),
            "piso_ruido_delta": PISO_RUIDO_DELTA,
            "sobre_piso_ruido": (
                d_max > PISO_RUIDO_DELTA if d_max is not None
                else None),
        }
        ml._ledger_append(rec_e3)
        ml.archivo.guardar(rec_e3)
        if adoptado and requiere_si:
            ml._emitir_ciclo("metaloop_requiere_si",
                             {"delta_in": e3["delta_in"],
                              "delta_ho": e3["delta_ho"],
                              "motivo": motivo_auto})
        if adoptado and auto_ok:
            try:
                adop = ml.promotor.auto_adoptar(
                    scaffold_antes=vigente, scaffold_despues=fin_cfg,
                    delta_in=puerta["delta_in"],
                    delta_ho=puerta["delta_ho"],
                    motivo_puerta=puerta["motivo"],
                    regla=puerta["regla"],
                    evidencia={
                        "seed": SEMILLA,
                        "experimento": "metaloop_crossover",
                        "preregistro": pr_path,
                        "tanda": ruta_tanda,
                        "padres": finalista["padres_ids"],
                        "herencia": finalista["herencia"],
                        "train_anterior": round(media_train_base, 4),
                        "train_candidato":
                            finalista["media_train"],
                        "heldout_anterior": round(base_held, 4),
                        "heldout_candidato": round(media_held_fin, 4),
                        "delta_e3": e3["delta_e3"],
                        "e3_exigido": e3["e3_exigido"],
                        "e3_evaluado": e3["e3_evaluado"],
                        "e3_reps": e3.get("e3_reps"),
                        "motivo_e3": e3["motivo"],
                        "origen": ("metaloop_crossover "
                                   f"semilla={SEMILLA}"),
                    },
                    claves_permitidas=set(SPACES),
                    costo_usd=0.0,
                    presupuesto=ml.presupuesto,
                    bucket=BUCKET_METALOOP)
            except NucleoProtegidoError as e:
                ml._ledger_append({"tipo": "metaloop_nucleo_bloqueado",
                                   "error": str(e)})
                adop = {"adoptada": False,
                        "motivo": f"núcleo protegido: {e}"}
            adopcion_id = adop.get("id") if adop.get("adoptada") \
                else None
        ml._emitir_ciclo("metaloop_puerta",
                         {"aceptado": bool(adoptado),
                          "delta_in": puerta["delta_in"],
                          "delta_ho": puerta["delta_ho"],
                          "motivo": puerta["motivo"],
                          "regla": puerta["regla"],
                          "e3_exigido": e3["e3_exigido"],
                          "e3_evaluado": e3["e3_evaluado"],
                          "delta_e3": e3["delta_e3"],
                          "motivo_e3": e3["motivo"]})

    # 3. Confirmación (solo si hubo auto-adopción): la ganancia
    #    oficial se mide en el panel fresco, contra el incumbente.
    if adopcion_id:
        cache_conf = {}
        inc_tr, _ = ml._evaluar(vigente, PANEL_CONF_TRAIN, cache_conf)
        ad_tr, _ = ml._evaluar(finalista["config"],
                               PANEL_CONF_TRAIN, cache_conf)
        inc_ho, _ = ml._evaluar(vigente, PANEL_CONF_HO, cache_conf)
        ad_ho, _ = ml._evaluar(finalista["config"],
                               PANEL_CONF_HO, cache_conf)
        confirmacion = {
            "tipo": "confirmacion_adopcion",
            "scaffold_anterior": vigente,
            "scaffold_adoptado": finalista["config"],
            "origen_operador": "crossover",
            "padres": finalista["padres_ids"],
            "delta_seleccion": {"delta_in": e3["delta_in"],
                                "delta_ho": e3["delta_ho"]},
            "delta_confirmacion": {
                "train": round(inc_tr - ad_tr, 4),
                "heldout": round(inc_ho - ad_ho, 4)},
            "medias": {
                "conf_train_incumbente": round(inc_tr, 4),
                "conf_train_adoptado": round(ad_tr, 4),
                "conf_heldout_incumbente": round(inc_ho, 4),
                "conf_heldout_adoptado": round(ad_ho, 4)},
            "panel_confirmacion": {
                "train": [PANEL_CONF_TRAIN[0], PANEL_CONF_TRAIN[-1]],
                "heldout": [PANEL_CONF_HO[0], PANEL_CONF_HO[-1]]},
        }
        confirmacion["ganancia_oficial"] = {
            **confirmacion["delta_confirmacion"],
            "max": max(confirmacion["delta_confirmacion"].values())}
        ml._ledger_append(confirmacion)

    # 4. Cierre de la corrida + contabilidad del freno (§9).
    ml._ledger_append({
        "tipo": "corrida_finalizada",
        "experimento": "metaloop_crossover",
        "tanda": ruta_tanda,
        "puerta_pass": adoptado,
        "adopcion_id": adopcion_id,
        "auto_adopcion": bool(adopcion_id),
        "scaffold_anterior": vigente,
        "scaffold_candidato": (finalista["config"] if finalista
                               else vigente),
        "finalista": ({"indice": finalista["indice"],
                       "padres": finalista["padres_ids"],
                       "delta_train": finalista["delta_train"]}
                      if finalista else None),
        "hijos_medidos": len(mediciones),
        "keeps": [],
        "heldout_anterior": base_held,
        "heldout_candidato": media_held_fin,
        "delta_train": (puerta["delta_in"] if puerta else 0.0),
        "delta_heldout": (puerta["delta_ho"] if puerta else 0.0),
        "regla_puerta": (puerta["regla"] if puerta else None),
        "motivo_puerta": (puerta["motivo"] if puerta
                          else e3["motivo"]),
        "e3_exigido": e3["e3_exigido"],
        "e3_evaluado": e3["e3_evaluado"],
        "delta_e3": e3["delta_e3"],
        "motivo_e3": e3["motivo"],
        "config_e3": resumen_config_e3(),
    })
    freno_despues = ml.registrar_corrida(adoptado=bool(adopcion_id))

    veredicto = _veredicto(adopcion_id, mediciones)
    resumen = {
        "veredicto": veredicto,
        "tanda": ruta_tanda,
        "preregistro_corrida": pr_path,
        "media_train_base": round(media_train_base, 4),
        "mediciones": mediciones,
        "finalista": finalista,
        "puerta": puerta,
        "e3": {k: e3.get(k) for k in
               ("aceptado", "e3_exigido", "e3_evaluado", "delta_in",
                "delta_ho", "delta_e3", "motivo")},
        "auto_adopcion": {"auto_ok": bool(auto_ok),
                          "motivo": motivo_auto,
                          "requiere_si": bool(requiere_si),
                          "adopcion_id": adopcion_id},
        "confirmacion": confirmacion,
        "freno_antes": freno_antes,
        "freno_despues": freno_despues,
        "scaffold_vigente": ml.scaffold_vigente(),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "mediciones.json"), "w",
              encoding="utf-8") as f:
        json.dump(mediciones, f, indent=2, ensure_ascii=False)
    with open(os.path.join(DATA_DIR, "resumen_corrida.json"), "w",
              encoding="utf-8") as f:
        json.dump(resumen, f, indent=2, ensure_ascii=False)

    print(f"hijos medidos: {len(mediciones)} "
          f"(media train base: {media_train_base:.4f})")
    for m in mediciones:
        print(f"  hijo {m['indice']:>2} "
              f"{'x'.join(m['padres_ids']):>7} "
              f"Δ_train {m['delta_train']:+.4f}")
    if finalista:
        print(f"finalista: hijo {finalista['indice']} "
              f"({'x'.join(finalista['padres_ids'])}) "
              f"Δ_train {finalista['delta_train']:+.4f} -> puerta: "
              f"Δ_in {e3['delta_in']:+.4f} Δ_ho {e3['delta_ho']:+.4f} "
              f"Δ_e3 {e3['delta_e3']} | {e3['motivo']}")
    else:
        print("sin finalista: ningún hijo con Δ_train > 0")
    print(f"VEREDICTO (§8): {veredicto}")
    print(f"freno: {freno_antes['racha_planas']}/3 -> "
          f"{freno_despues['racha_planas']}/3 "
          f"(activo: {freno_despues['freno_activo']})")
    print("scaffold vigente:", ml.scaffold_vigente())
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--generar", action="store_true",
                    help="paso 1: generar y congelar la tanda")
    ap.add_argument("--tanda", metavar="RUTA",
                    help="paso 2: correr la tanda congelada")
    args = ap.parse_args()
    if args.generar:
        paso_generar()
        return 0
    if args.tanda:
        return paso_correr(args.tanda)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
