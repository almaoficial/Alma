"""Tests del generador de candidatos del meta-loop (16/10/2026).

Pre-registro: preregistro-generador-sakana-2026-10-16.md
Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_generador_candidatos.py

Cubre:
- El prompt: la tabla MEDIDA del historial (Δ_train exactos desde el
  ledger, fixture y ledger real) y las reglas duras declaradas.
- El CORTAFUEGOS DEL PROPONENTE (adenda 2026-10-16): un ledger
  envenenado con puntajes held-out/E3 plantados demuestra que ningún
  dato de la etapa puerta llega al historial ni al prompt.
- El parseo: JSON directo, con fences, con texto alrededor, roto.
- La validación mecánica: forma, tipos, rango, idéntico a la base,
  movimiento simple, duplicados y el PISO DE DIVERSIDAD (distancia
  mínima 2 entre todo par válido).
- El protocolo de generación con mocks: feedback entre llamados,
  respuesta no parseable, tanda vacía. SIN llamadas vivas (US$0).
- La FRONTERA DURA por hashes: importar y ejecutar el generador con
  mocks no altera gate.py, metaloop.py, puerta_e3.py, scaffold.py,
  el validador (e47/e56) ni el ledger/archivo (subproceso, antes y
  después).
- La integración opt-in en metaloop: la tanda corre por el camino
  normal (keep/revert, puerta, E3, auto-adopción, freno) y la
  corrida RSO default queda intacta.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service import generador_candidatos as g  # noqa: E402
from alma_service.metaloop import MetaLoop, TRAIN_REPS  # noqa: E402
from alma_service.presupuesto import PresupuestoFase2  # noqa: E402
from alma_service.scaffold import DEFAULT_SCAFFOLD  # noqa: E402

PASSOS = []
AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = dict(DEFAULT_SCAFFOLD)


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def cand(**cambios):
    cfg = dict(BASE)
    cfg.update(cambios)
    return {"config": cfg, "justificacion": "interacción de prueba"}


# Seis candidatos válidos: ≥2 parámetros desde la base y distancia
# ≥2 entre todo par (verificado a mano contra SPACES).
SEIS = [
    cand(umbral_base=2, decay=0.25),
    cand(umbral_base=3, decay=0.75),
    cand(umbral_divisor=2, gate_margin=0.05),
    cand(umbral_divisor=4, gate_margin=0.10),
    cand(n0=1, decay=0.75),
    cand(n0=2, gate_margin=0.10),
]
RESP_SEIS = json.dumps({"candidatos": SEIS})

# Las 8 mutaciones medidas de la corrida de hoy (seed 87859), tal
# como quedaron en el ledger: (clave, anterior, nuevo, Δ_train).
HOY = [
    ("umbral_base", 1, 3, -3.0556),
    ("decay", 0.5, 0.75, -0.5),
    ("umbral_divisor", 3, 4, -0.3333),
    ("decay", 0.5, 0.75, -0.5),
    ("gate_margin", 0.0, 0.1, 0.0),
    ("umbral_divisor", 3, 2, -2.7778),
    ("umbral_base", 1, 2, -3.1667),
    ("gate_margin", 0.0, 0.05, 0.0),
]


def _ledger_fixture(ruta):
    eventos = [{"tipo": "corrida_iniciada", "seed": 87859, "rondas": 8}]
    for clave, a, n, d in HOY:
        eventos.append({
            "tipo": "audit_propuesta",
            "propuesta": {"clave": clave, "anterior": a, "nuevo": n},
            "delta_in": d, "aceptado": False})
    with open(ruta, "w", encoding="utf-8") as f:
        for ev in eventos:
            f.write(json.dumps({"prev": "x", "hash": "y",
                                "evento": ev}) + "\n")


def _sha(ruta):
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


PROTEGIDOS = [
    "alma_service/gate.py", "alma_service/metaloop.py",
    "alma_service/puerta_e3.py", "alma_service/scaffold.py",
    "run_experiment47.py", "exp56_rso/run_experiment56.py",
    "metaloop_ledger.jsonl", "metaloop_archivo.jsonl",
]


def main():
    # -- 1. El prompt con la tabla medida (fixture del ledger) --------
    d = tempfile.mkdtemp(prefix="alma_gen_")
    fx = os.path.join(d, "ledger.jsonl")
    _ledger_fixture(fx)
    hist = g.historial_desde_ledger(fx)
    check("historial: 8 propuestas de la corrida fixture",
          hist["total"] == 8 and len(hist["propuestas"]) == 8)
    prompt = g.construir_prompt(BASE, hist, 14)
    for texto in ["umbral_base: 1 -> 3", "-3.0556", "-3.1667",
                  "-2.7778", "-0.3333", "gate_margin: 0.0 -> 0.1",
                  "+0.0000", "umbral_divisor: 3 -> 2"]:
        check(f"prompt trae la fila medida «{texto}»", texto in prompt)
    check("prompt: instrucción de cambios coordinados (≥2)",
          "AL MENOS 2 parámetros" in prompt)
    check("prompt: piso de diversidad declarado",
          "Distancia mínima 2 entre TODO par" in prompt)
    check("prompt: base y espacio completos",
          '"umbral_base": 1' in prompt
          and '"umbral_divisor": [2, 3, 4, 6]' in prompt)

    # -- 2. El prompt contra el ledger REAL (la corrida de hoy) -------
    real = os.path.join(AQUI, "metaloop_ledger.jsonl")
    hist_real = g.historial_desde_ledger(real)
    prompt_real = g.construir_prompt(BASE, hist_real, 14)
    check("ledger real: la corrida 87859 está en el historial",
          any(c["seed"] == 87859 and len(c["propuestas"]) == 8
              for c in hist_real["corridas"]))
    for texto in ["-3.0556", "-3.1667", "-2.7778", "-0.5000"]:
        check(f"prompt real trae el Δ medido {texto}",
              texto in prompt_real)

    # -- 2b. CORTAFUEGOS DEL PROPONENTE (adenda 2026-10-16) ------------
    # Ledger envenenado: puntajes held-out/E3 plantados en (a) el
    # campo delta_ho de un audit_propuesta, (b) un audit_propuesta_e3
    # completo, (c) el corrida_finalizada y (d) textos libres
    # (descripcion/motivo) de un audit_propuesta limpio. NINGUNO puede
    # llegar al historial ni al prompt: el proponente solo ve la
    # etapa train.
    PLANTADOS = ["777.7777", "999.9999", "888.8888", "666.6666",
                 "555.5555", "-6.5432", "111.1111", "222.2222"]
    env = os.path.join(d, "ledger_envenenado.jsonl")
    eventos_env = [
        {"tipo": "corrida_iniciada", "seed": 777, "rondas": 2},
        # audit_propuesta LIMPIO (con veneno solo en textos libres
        # que el generador no proyecta):
        {"tipo": "audit_propuesta",
         "propuesta": {"clave": "umbral_base", "anterior": 1, "nuevo": 2,
                       "descripcion": "delta_ho fue 555.5555"},
         "delta_in": -1.25, "delta_ho": None, "aceptado": False,
         "motivo": "revert en train; el held-out dio 555.5555"},
        # audit_propuesta CONTAMINADO con carga de puerta:
        {"tipo": "audit_propuesta",
         "propuesta": {"clave": "decay", "anterior": 0.5, "nuevo": 0.25},
         "delta_in": -6.5432, "delta_ho": 777.7777, "aceptado": False},
        # la puerta entera, en sus eventos propios:
        {"tipo": "audit_propuesta_e3",
         "propuesta": {"clave": "scaffold_completo",
                       "anterior": dict(BASE), "nuevo": dict(BASE)},
         "delta_in": 0.5, "delta_ho": 999.9999, "delta_e3": 888.8888,
         "e3_base": 111.1111, "e3_cand": 222.2222, "aceptado": False},
        {"tipo": "corrida_finalizada", "delta_train": 0.5,
         "delta_heldout": 666.6666, "delta_e3": 888.8888},
    ]
    with open(env, "w", encoding="utf-8") as f:
        for ev in eventos_env:
            f.write(json.dumps({"prev": "x", "hash": "y",
                                "evento": ev}) + "\n")
    hist_env = g.historial_desde_ledger(env)
    check("cortafuegos: el evento contaminado se excluye entero; "
          "solo entra la propuesta train limpia",
          hist_env["total"] == 1
          and hist_env["propuestas"][0]["clave"] == "umbral_base")
    check("cortafuegos: las filas solo traen campos de etapa train",
          all(set(fila.keys()) == set(g.CAMPOS_TRAIN)
              for fila in hist_env["propuestas"]))
    hist_env_json = json.dumps(hist_env)
    check("cortafuegos: el historial no contiene claves de puerta",
          "delta_ho" not in hist_env_json
          and "delta_e3" not in hist_env_json)
    prompt_env = g.construir_prompt(BASE, hist_env, 14)
    check("cortafuegos: la fila train limpia SÍ llega al prompt",
          "-1.2500" in prompt_env and "umbral_base: 1 -> 2" in prompt_env)
    for plantado in PLANTADOS:
        check(f"cortafuegos: {plantado} no llega al prompt",
              plantado not in prompt_env)
        check(f"cortafuegos: {plantado} no llega al historial",
              plantado not in hist_env_json)

    # -- 3. Parseo ------------------------------------------------------
    crudos, err = g.parsear_respuesta(RESP_SEIS)
    check("parseo: JSON directo", err is None and len(crudos) == 6)
    crudos, err = g.parsear_respuesta("```json\n" + RESP_SEIS + "\n```")
    check("parseo: con fences", err is None and len(crudos) == 6)
    crudos, err = g.parsear_respuesta("Acá va: " + RESP_SEIS + " ¡suerte!")
    check("parseo: con texto alrededor", err is None and len(crudos) == 6)
    crudos, err = g.parsear_respuesta("no tengo ningún JSON para darte")
    check("parseo: sin JSON -> error, sin inventar",
          err is not None and crudos == [])
    crudos, err = g.parsear_respuesta('{"otra_cosa": 1}')
    check("parseo: JSON sin candidatos -> error",
          err is not None and crudos == [])
    crudos, err = g.parsear_respuesta("")
    check("parseo: vacío -> error", err is not None and crudos == [])

    # -- 4. Validación mecánica -----------------------------------------
    res = g.validar_tanda(SEIS, BASE)
    check("validación: los 6 bien formados pasan",
          len(res["validos"]) == 6 and res["descartados"] == [])

    def motivo_de(crudo):
        r = g.validar_tanda([crudo], BASE)
        return r["descartados"][0]["motivo"] if r["descartados"] else None

    check("fuera de rango", motivo_de(cand(umbral_base=7, decay=0.25))
          == g.M_RANGO)
    check("tipo inválido: string en parámetro entero",
          motivo_de(cand(n0="4", decay=0.25)) == g.M_TIPO)
    check("tipo inválido: float no integral en entero",
          motivo_de(cand(n0=2.5, decay=0.25)) == g.M_TIPO)
    check("tipo inválido: bool no es número",
          motivo_de(cand(decay=True, n0=1)) == g.M_TIPO)
    incompleta = cand(umbral_base=2, decay=0.25)
    del incompleta["config"]["gate_margin"]
    check("config incompleta", motivo_de(incompleta) == g.M_INCOMPLETA)
    desconocido = cand(umbral_base=2, decay=0.25)
    desconocido["config"]["otro_param"] = 1
    check("parámetro desconocido",
          motivo_de(desconocido) == g.M_DESCONOCIDO)
    check("idéntico a la base", motivo_de(cand()) == g.M_BASE)
    check("movimiento simple (1 parámetro)",
          motivo_de(cand(decay=0.25)) == g.M_SIMPLE)
    sin_just = {"config": dict(BASE, umbral_base=2, decay=0.25)}
    check("sin justificación", motivo_de(sin_just) == g.M_SIN_JUSTIFICACION)
    check("no es objeto", motivo_de("hola") == g.M_NO_OBJETO)
    check("sin config", motivo_de({"justificacion": "x"}) == g.M_SIN_CONFIG)
    r = g.validar_tanda([SEIS[0], SEIS[0]], BASE)
    check("duplicado en la tanda",
          len(r["validos"]) == 1
          and r["descartados"][0]["motivo"] == g.M_DUPLICADO)
    cerca = cand(umbral_base=2, decay=0.25, umbral_divisor=2)
    r = g.validar_tanda([SEIS[0], cerca], BASE)
    check("piso de diversidad: distancia 1 contra otro válido",
          len(r["validos"]) == 1
          and r["descartados"][0]["motivo"] == g.M_DIVERSIDAD)
    r = g.validar_tanda([cerca], BASE, previos=[SEIS[0]])
    check("piso de diversidad también contra previos",
          len(r["validos"]) == 0
          and r["descartados"][0]["motivo"] == g.M_DIVERSIDAD)


    # -- 5. Generación con mocks (ninguna llamada viva) -----------------
    vacio = {"corridas": [], "propuestas": [], "total": 0}
    res = g.generar_tanda(lambda p: RESP_SEIS, BASE, vacio,
                          n_objetivo=6, max_llamados=1)
    check("generación: tanda bien formada de un llamado",
          len(res["candidatos"]) == 6 and res["llamados"] == 1
          and res["descartados"] == [])

    respuestas = iter(["esto no es json", RESP_SEIS])
    res = g.generar_tanda(lambda p: next(respuestas), BASE, vacio,
                          n_objetivo=6, max_llamados=3)
    check("generación: feedback tras respuesta no parseable",
          res["llamados"] == 2 and len(res["candidatos"]) == 6
          and res["descartados"][0]["motivo"] == g.M_PARSEO)
    check("generación: el 2º prompt trae los motivos de descarte",
          "respuesta_no_parseable" in res["prompts"][1])

    res = g.generar_tanda(lambda p: '{"candidatos": []}', BASE, vacio,
                           n_objetivo=6, max_llamados=2)
    check("generación: tanda vacía no rompe ni inventa",
          res["candidatos"] == [] and res["llamados"] == 2)

    mitad = json.dumps({"candidatos": [SEIS[0],
                                       cand(umbral_base=2, decay=0.25,
                                            umbral_divisor=2)]})
    resto = json.dumps({"candidatos": [SEIS[1]]})
    respuestas = iter([mitad, resto])
    res = g.generar_tanda(lambda p: next(respuestas), BASE, vacio,
                           n_objetivo=2, max_llamados=2)
    check("generación: completa con feedback de diversidad",
          len(res["candidatos"]) == 2 and res["llamados"] == 2
          and any(dd["motivo"] == g.M_DIVERSIDAD
                  for dd in res["descartados"]))
    check("generación: el 2º prompt lista los ya aceptados",
          "Ya aceptados en esta tanda" in res["prompts"][1])

    # guardar_tanda escribe SOLO donde se le dice
    ruta_tanda = os.path.join(d, "tanda.json")
    g.guardar_tanda(res, ruta_tanda, BASE, ledger_path=fx)
    with open(ruta_tanda, encoding="utf-8") as f:
        doc = json.load(f)
    check("tanda congelada a disco con candidatos y descartes",
          doc["tipo"] == "tanda_generador_candidatos"
          and doc["n_validos"] == 2 and len(doc["descartados"]) >= 1)

    # -- 6. FRONTERA DURA: hashes antes/después (subproceso) ------------
    hash_snippet = (
        "import hashlib, json\n"
        "def h(p):\n"
        "    return hashlib.sha256(open(p,'rb').read()).hexdigest()\n"
        f"print(json.dumps({{p: h(p) for p in {PROTEGIDOS!r}}}))\n")
    antes = json.loads(subprocess.run(
        [sys.executable, "-c", hash_snippet], cwd=AQUI,
        capture_output=True, text=True, check=True).stdout)
    ejecuta = (
        "import json, sys\n"
        "from alma_service import generador_candidatos as g\n"
        "from alma_service.scaffold import DEFAULT_SCAFFOLD\n"
        "base = dict(DEFAULT_SCAFFOLD)\n"
        "h = g.historial_desde_ledger('metaloop_ledger.jsonl')\n"
        f"resp = {RESP_SEIS!r}\n"
        "r = g.generar_tanda(lambda p: resp, base, h, n_objetivo=6,"
        " max_llamados=1)\n"
        "assert len(r['candidatos']) == 6\n"
        "g.guardar_tanda(r, sys.argv[1], base,"
        " 'metaloop_ledger.jsonl')\n")
    destino = os.path.join(d, "tanda_sub.json")
    subprocess.run([sys.executable, "-c", ejecuta, destino], cwd=AQUI,
                   capture_output=True, text=True, check=True)
    despues = json.loads(subprocess.run(
        [sys.executable, "-c", hash_snippet], cwd=AQUI,
        capture_output=True, text=True, check=True).stdout)
    check("frontera: importar + ejecutar con mocks no toca ningún "
          "archivo protegido", antes == despues)
    check("frontera: la única escritura fue la tanda pedida",
          os.path.exists(destino))


    # -- 7. Integración opt-in: la tanda por el camino normal -----------
    BUENO = dict(BASE, umbral_base=2, decay=0.25)
    MALO = dict(BASE, umbral_divisor=2, gate_margin=0.05)

    def _ml(tmp):
        db = os.path.join(tmp, "ml.db")
        return MetaLoop(db, presupuesto=PresupuestoFase2(
            db, tope_mensual_usd=0.0))

    def _fake(vigente):
        def fake(scaffold, replicas, cache):
            es_train = tuple(replicas) == tuple(TRAIN_REPS)
            if scaffold == BUENO:
                return ((84.0, [84.0] * len(replicas)) if es_train
                        else (89.0, [89.0] * len(replicas)))
            if scaffold == vigente:
                return ((90.0, [90.0] * len(replicas)) if es_train
                        else (95.0, [95.0] * len(replicas)))
            return ((96.0, [96.0] * len(replicas)) if es_train
                    else (97.0, [97.0] * len(replicas)))
        return fake

    orig_evaluar = MetaLoop._evaluar

    d7 = tempfile.mkdtemp(prefix="alma_gen_ml_")
    ml = _ml(d7)
    vigente = ml.scaffold_vigente()
    MetaLoop._evaluar = staticmethod(_fake(vigente))
    try:
        rr = ml.correr(seed=99, candidatos=[MALO, BUENO],
                       bloqueante=True)
    finally:
        MetaLoop._evaluar = orig_evaluar
    check("integración: la corrida con tanda es aceptada",
          rr.get("aceptado") is True)
    check("integración: auto-adoptó el candidato bueno de la tanda",
          ml.scaffold_vigente() == BUENO)
    eventos = [e["evento"] for e in ml.ledger_leer()]
    audits = [e for e in eventos if e.get("tipo") == "audit_propuesta"
              and (e.get("propuesta") or {}).get("clave")
              == "scaffold_completo"]
    check("integración: un audit record por candidato de la tanda",
          len(audits) == 2)
    check("integración: el malo revirtió y el bueno hizo keep",
          audits[0]["aceptado"] is False and audits[1]["aceptado"] is True)
    preregs = [f for f in os.listdir(d7)
               if f.startswith("metaloop_preregistro_")]
    with open(os.path.join(d7, preregs[0]), encoding="utf-8") as f:
        prereg = json.load(f)
    check("integración: la tanda quedó en el pre-registro de la corrida",
          prereg.get("proponente") == "generador_candidatos"
          and prereg.get("tanda_candidatos") == [MALO, BUENO]
          and prereg.get("rondas") == 2)
    check("integración: adopción resetea la racha del freno",
          ml.estado_freno()["racha_planas"] == 0)

    d8 = tempfile.mkdtemp(prefix="alma_gen_ml2_")
    ml2 = _ml(d8)
    vigente2 = ml2.scaffold_vigente()
    MetaLoop._evaluar = staticmethod(_fake(vigente2))
    try:
        ml2.correr(seed=98, candidatos=[MALO], bloqueante=True)
    finally:
        MetaLoop._evaluar = orig_evaluar
    check("integración: tanda sin mejora no adopta",
          ml2.scaffold_vigente() == vigente2)
    check("integración: la corrida plana suma a la racha (1/3)",
          ml2.estado_freno()["racha_planas"] == 1)

    # La corrida default (sin candidatos) queda intacta: RSO + sin
    # campos de tanda en su pre-registro.
    d9 = tempfile.mkdtemp(prefix="alma_gen_ml3_")
    ml3 = _ml(d9)
    vigente3 = ml3.scaffold_vigente()

    def fake_rso(scaffold, replicas, cache):
        es_train = tuple(replicas) == tuple(TRAIN_REPS)
        if scaffold == vigente3:
            return ((90.0, [90.0] * len(replicas)) if es_train
                    else (95.0, [95.0] * len(replicas)))
        return ((84.0, [84.0] * len(replicas)) if es_train
                else (89.0, [89.0] * len(replicas)))

    MetaLoop._evaluar = staticmethod(fake_rso)
    try:
        ml3.correr(seed=5, rondas=2, bloqueante=True)
    finally:
        MetaLoop._evaluar = orig_evaluar
    check("default intacto: la RSO sin tanda sigue auto-adoptando",
          ml3.scaffold_vigente() != vigente3)
    preregs3 = [f for f in os.listdir(d9)
                if f.startswith("metaloop_preregistro_")]
    with open(os.path.join(d9, preregs3[0]), encoding="utf-8") as f:
        prereg3 = json.load(f)
    check("default intacto: su pre-registro no gana campos de tanda",
          "tanda_candidatos" not in prereg3
          and "proponente" not in prereg3)

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
