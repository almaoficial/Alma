"""Re-medición acotada del ciclo L1 — las 58 configuraciones de §8.

EJECUCIÓN del pre-registro preregistro-L1-panel-grande-2026-10-16.md
§8 (autorizado por Alejandro, «Corre», 16/10/2026), DESPUÉS de la
recalibración adoptada (δ_L1 = 0,1141 escala δ = 2,7391 totales,
evento recalibracion_delta_L1) y del recableado asentado (evento
recableado_puerta_delta_L1). US$0, simulador determinista, SIN
correr el meta-loop (el freno 3/3 sigue activo: esta medición es
el procedimiento declarado del ciclo, por evaluación directa con
la maquinaria congelada — el mismo patrón del diagnóstico §9).

Procedimiento (§8.2 del pre-registro):
  1. Medición INDEPENDIENTE contra la base de las 58
     configuraciones del alcance cerrado (conteo_alcance.json,
     union_sin_base) sobre el panel train nuevo [20000..20071]:
     Δ_train^L1 = media base − media config, en totales.
     Ancla fail-closed: los reg_pol de la base deben reproducir
     EXACTOS los de resultados_base_L1.json (recableado); si no,
     se detiene todo sin interpretar.
  2. Selección (umbral declarado): Δ_train^L1 > δ_nuevo en
     totales (2,7391).
  3. Finalistas: en orden de Δ_train^L1 descendente, MÁXIMO 3
     recorren la puerta por la ruta cableada: held-out nuevo
     [21000..21047] → PuertaDosSplits.decidir; si acepta, E3
     nuevo [22000..22023] por su regla cableada (decidir_e3 con
     forzar_e3=True y MARGEN_MIN_DEFAULT — el endurecimiento
     del 28/9: E3 siempre exigido cuando los dos splits aceptan;
     short-circuit si los dos splits rechazan); si el E3 no
     veta, decidir_auto_adopcion con el piso cableado
     (2,7391). La PRIMERA adopción cierra la re-medición.
  4. REGLA DEL TOKEN (instrucción de ejecución): si un finalista
     supera TODA la puerta, este script se DETIENE justo antes
     de asentar adopción alguna y reporta ADOPCION_PENDIENTE_
     TOKEN con el candidato y sus Δ completos. NO asienta la
     adopción, NO consume el panel de confirmación, NO llama a
     desbloquear_freno (el token ALMA_TOKEN_HUMANO no está
     definido y nadie lo define en este ciclo).

Salida: data_L1_2026-10-16/remedicion_resultados.json
"""
import sys, os, json, time
import numpy as np

BASE = "/home/hatch/workspace/alma-prototype"
sys.path.insert(0, BASE)
sys.path.insert(0, BASE + "/exp56_rso")
import run_experiment47 as e47
import run_experiment56 as e56
from alma_service.scaffold import DEFAULT_SCAFFOLD
from alma_service.gate import (
    PuertaDosSplits, decidir_auto_adopcion, PISO_RUIDO_DELTA)
from alma_service.puerta_e3 import (
    E3_REPS, MARGEN_MIN_DEFAULT, SUPERFICIE_METALOOP,
    decidir as decidir_e3)

OUT = BASE + "/data_L1_2026-10-16"
TRAIN = list(range(20000, 20072))
HELDOUT = list(range(21000, 21048))
CLAVES = ["decay", "gate_margin", "n0", "umbral_base",
          "umbral_divisor"]
DELTA_NUEVO_TOTALES = 2.7391
assert PISO_RUIDO_DELTA == DELTA_NUEVO_TOTALES, (
    f"el piso cableado ({PISO_RUIDO_DELTA}) no es el congelado "
    "L1 (2,7391): DETENER")
assert E3_REPS == list(range(22000, 22024)), "E3 cableado no es el L1"

t_inicio = time.time()
items = e47.construir_stream()
tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
BASE_SC = dict(DEFAULT_SCAFFOLD)

conteo = json.load(open(
    BASE + "/data_preregistro_L1_2026-10-16/conteo_alcance.json",
    encoding="utf-8"))
UNION = [tuple(x) for x in conteo["conjuntos"]["union_sin_base"]]
assert len(UNION) == 58 and len(set(UNION)) == 58
FUENTES = {}
for fuente, lista in conteo["conjuntos"]["fuentes"].items():
    for t in lista:
        FUENTES.setdefault(tuple(t), []).append(fuente)

base_prev = json.load(open(OUT + "/resultados_base_L1.json",
                           encoding="utf-8"))


def evaluar(scaffold, replicas):
    regs = {}
    for r in replicas:
        rr = e56.correr_replica_param(r, items, tasas, dict(scaffold))
        regs[r] = rr["reg_pol"]
    return float(np.mean([regs[r] for r in replicas])), regs


def cfg(t):
    return {k: v for k, v in zip(CLAVES, t)}


RES = {"fecha": "2026-10-16", "ciclo": "L1",
       "preregistro": "preregistro-L1-panel-grande-2026-10-16.md "
                      "(commit fa7cb8f)",
       "delta_nuevo_totales": DELTA_NUEVO_TOTALES,
       "delta_nuevo_escala_delta": 0.1141,
       "panel": {"train": TRAIN, "heldout": HELDOUT,
                 "e3": list(E3_REPS)},
       "n_alcance": 58}

# ---------- 1. Base en train (ancla) + medición de las 58 ----------
print("[1] base en train nuevo (ancla) ...", flush=True)
media_base_tr, regs_base_tr = evaluar(BASE_SC, TRAIN)
ancla_tr = [regs_base_tr[r] for r in TRAIN] == \
    base_prev["panel_nuevo"]["train"]["reg_pol"]
print(f"    media base train = {media_base_tr:.4f}; "
      f"ancla vs recableado: {ancla_tr}", flush=True)
assert ancla_tr and abs(media_base_tr -
                        base_prev["panel_nuevo"]["train"]["media"]) < 1e-9, \
    "ANCLA CAÍDA: la base en train no reproduce el recableado; DETENER"
RES["media_base_train"] = media_base_tr

print("[1] midiendo las 58 (independientes contra la base) ...",
      flush=True)
t0 = time.time()
tabla = []
for i, t in enumerate(UNION, 1):
    media_c, _ = evaluar(cfg(t), TRAIN)
    d = round(media_base_tr - media_c, 4)
    tabla.append({"tupla": list(t), "config": cfg(t),
                  "fuentes": FUENTES.get(t, []),
                  "media_train": round(media_c, 4),
                  "delta_train_L1": d,
                  "supera_seleccion": bool(d > DELTA_NUEVO_TOTALES)})
    if i % 20 == 0:
        print(f"    {i}/58 ...", flush=True)
RES["tabla_58"] = tabla
RES["duracion_medicion_s"] = round(time.time() - t0, 2)
sobre = [x for x in tabla if x["supera_seleccion"]]
sobre.sort(key=lambda x: -x["delta_train_L1"])
RES["n_sobre_seleccion"] = len(sobre)
RES["mejores_marcas"] = sorted(
    tabla, key=lambda x: -x["delta_train_L1"])[:5]
print(f"[1] {len(sobre)} configuraciones superan la selección "
      f"(Δ_train > {DELTA_NUEVO_TOTALES}); mejor marca: "
      f"{RES['mejores_marcas'][0]['delta_train_L1']}", flush=True)

# ---------- 2/3. Finalistas (máx 3) por la puerta cableada ----------
finalistas = sobre[:3]
RES["finalistas"] = []
adopcion_pendiente = None
if finalistas:
    print("[2] base en held-out nuevo (ancla) ...", flush=True)
    media_base_ho, regs_base_ho = evaluar(BASE_SC, HELDOUT)
    ancla_ho = [regs_base_ho[r] for r in HELDOUT] == \
        base_prev["panel_nuevo"]["heldout"]["reg_pol"]
    assert ancla_ho, "ANCLA CAÍDA en held-out; DETENER"
    RES["media_base_heldout"] = media_base_ho
    media_base_e3, regs_base_e3 = evaluar(BASE_SC, list(E3_REPS))
    ancla_e3 = abs(media_base_e3 -
                   base_prev["e3_contexto"]["media"]) < 1e-9
    assert ancla_e3, "ANCLA CAÍDA en E3; DETENER"
    RES["media_base_e3"] = media_base_e3

for j, fin in enumerate(finalistas, 1):
    c = fin["config"]
    print(f"[3] finalista {j}: {c} (Δ_train "
          f"{fin['delta_train_L1']}) ...", flush=True)
    media_c_ho, _ = evaluar(c, HELDOUT)
    puerta = PuertaDosSplits.decidir(media_base_tr, media_base_ho,
                                     fin["media_train"], media_c_ho)
    reg = {"orden": j, "config": c, "fuentes": fin["fuentes"],
           "delta_train_L1": fin["delta_train_L1"],
           "delta_in": puerta["delta_in"],
           "delta_ho": puerta["delta_ho"],
           "media_heldout": round(media_c_ho, 4),
           "puerta_dos_splits": {"aceptado": puerta["aceptado"],
                                 "motivo": puerta["motivo"]},
           "delta_e3": None, "e3": None, "auto_adopcion": None,
           "destino": None}
    if not puerta["aceptado"]:
        reg["destino"] = "rechazado en la puerta de dos splits " \
                          "(E3 no evaluado, short-circuit cableado)"
        print(f"    Δ_in {puerta['delta_in']} / Δ_ho "
              f"{puerta['delta_ho']} -> {reg['destino']}", flush=True)
        RES["finalistas"].append(reg)
        continue
    media_c_e3, _ = evaluar(c, list(E3_REPS))
    d_e3 = round(media_base_e3 - media_c_e3, 4)
    dec_e3 = decidir_e3(puerta["delta_in"], puerta["delta_ho"],
                        delta_e3=d_e3,
                        superficie=SUPERFICIE_METALOOP,
                        margen_min=MARGEN_MIN_DEFAULT,
                        forzar_e3=True)
    reg["delta_e3"] = d_e3
    reg["e3"] = {"exigido": dec_e3["e3_exigido"],
                 "evaluado": dec_e3["e3_evaluado"],
                 "aceptado": dec_e3["aceptado"],
                 "motivo": dec_e3["motivo"]}
    if not dec_e3["aceptado"]:
        reg["destino"] = "rechazado por el E3 (veto del tercer " \
                          "split ciego)"
        print(f"    Δ_e3 {d_e3} -> {reg['destino']}", flush=True)
        RES["finalistas"].append(reg)
        continue
    auto, motivo_auto, req_si = decidir_auto_adopcion(
        puerta["delta_in"], puerta["delta_ho"])
    reg["auto_adopcion"] = {"auto": auto, "motivo": motivo_auto,
                            "requiere_si": req_si}
    if auto:
        reg["destino"] = "SUPERA TODA LA PUERTA — adopción " \
                          "pendiente del token humano (regla del " \
                          "token: no se asienta en este ciclo)"
        adopcion_pendiente = reg
        RES["finalistas"].append(reg)
        print(f"    *** PUERTA SUPERADA: {reg['destino']}",
              flush=True)
        break
    reg["destino"] = "aceptado por la puerta pero bajo el piso " \
                      "de ruido (no auto-adopción)"
    print(f"    -> {reg['destino']}", flush=True)
    RES["finalistas"].append(reg)

RES["adopcion_pendiente_token"] = adopcion_pendiente
if adopcion_pendiente is not None:
    RES["estado"] = "ADOPCION_PENDIENTE_TOKEN"
elif finalistas:
    RES["estado"] = "SIN_ADOPCION_CON_FINALISTAS"
else:
    RES["estado"] = "SIN_ADOPCION_SIN_FINALISTAS"
RES["duracion_total_s"] = round(time.time() - t_inicio, 2)
with open(OUT + "/remedicion_resultados.json", "w",
          encoding="utf-8") as f:
    json.dump(RES, f, indent=2, ensure_ascii=False)
print(f"[fin] estado={RES['estado']} en "
      f"{RES['duracion_total_s']}s", flush=True)
