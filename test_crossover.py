"""Tests del operador crossover del meta-loop (16/10/2026).

Pre-registro: preregistro-crossover-2026-10-16.md (§7.1 adapta las
pruebas del papel del 12/10). Convención del repo: funciones
planas, sin pytest. Correr:
    python3 test_crossover.py

Cubre:
- El orden de pares determinista del §6 (bloques P5 → P3/P8 → P0
  → resto lexicográfico; 66 pares, sin duplicados).
- La mezcla uniforme con semilla fija: cada valor del hijo
  pertenece a {A, B}; misma semilla → mismo hijo (determinismo).
- La regla «hijo != padre disfrazado»: hereda >= 1 parámetro en
  disputa de cada padre y difiere de ambos; el clon se descarta.
- Par a distancia 1 -> inelegible (toda mezcla sería un clon).
- La deduplicación: punto ya medido en train (conjunto de
  exclusión) y duplicado dentro de la tanda se descartan con
  motivo.
- La extracción mecánica del conjunto de exclusión: fixture de
  ledger (simulación keep/revert) y el screening real (18).
- La tanda real sobre la población declarada y el ledger real,
  con la semilla de la corrida: >= 8 hijos, todos válidos contra
  las reglas, determinista entre dos generaciones. NO evalúa a
  nadie (sin validador): US$0, sin escrituras al ledger.
- Paridad de puerta: las funciones de decisión son ciegas al
  origen del candidato (mismos deltas -> mismo veredicto).
- La frontera: importar y operar el crossover no altera gate.py,
  metaloop.py, puerta_e3.py ni scaffold.py (hashes antes/después).
"""

import hashlib
import json
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service import crossover as x  # noqa: E402
from alma_service.gate import decidir_auto_adopcion  # noqa: E402
from alma_service.puerta_e3 import decidir as decidir_e3  # noqa: E402
from alma_service.scaffold import DEFAULT_SCAFFOLD  # noqa: E402

PASSOS = []
AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = dict(DEFAULT_SCAFFOLD)
SEMILLA_CORRIDA = 20261016  # la declarada en correr_crossover.py


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def cfg(**cambios):
    c = dict(BASE)
    c.update(cambios)
    return c


def hash_archivo(ruta):
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    # -- frontera: hashes antes -------------------------------------------
    frontera = {}
    for nombre in ("gate.py", "metaloop.py", "puerta_e3.py",
                   "scaffold.py"):
        ruta = os.path.join(AQUI, "alma_service", nombre)
        frontera[nombre] = hash_archivo(ruta)

    # -- 1. orden de pares --------------------------------------------------
    pares = x.orden_pares(12)
    check("orden: 66 pares sin duplicados",
          len(pares) == 66 and len(set(pares)) == 66)
    bloque_p5 = [(0, 5), (1, 5), (2, 5), (3, 5), (4, 5), (5, 6),
                 (5, 7), (5, 8), (5, 9), (5, 10), (5, 11)]
    check("orden: bloque 1 = pares de P5 por índice del otro",
          pares[:11] == bloque_p5)
    bloque_p3 = [(0, 3), (1, 3), (2, 3), (3, 4), (3, 6), (3, 7),
                 (3, 8), (3, 9), (3, 10), (3, 11)]
    check("orden: bloque 2 empieza con los pares nuevos de P3",
          pares[11:21] == bloque_p3)
    bloque_p8 = [(0, 8), (1, 8), (2, 8), (4, 8), (6, 8), (7, 8),
                 (8, 9), (8, 10), (8, 11)]
    check("orden: bloque 2 sigue con los pares nuevos de P8",
          pares[21:30] == bloque_p8)
    bloque_p0 = [(0, 1), (0, 2), (0, 4), (0, 6), (0, 7), (0, 9),
                 (0, 10), (0, 11)]
    check("orden: bloque 3 = pares nuevos de P0 por índice",
          pares[30:38] == bloque_p0)
    resto = pares[38:]
    check("orden: bloque 4 = resto en orden lexicográfico",
          resto == sorted(resto) and len(resto) == 28)
    check("orden: determinista entre llamadas",
          x.orden_pares(12) == pares)

    # -- 2. mezcla con semilla fija -----------------------------------------
    a = cfg(decay=0.25, gate_margin=0.1, n0=1, umbral_base=3,
            umbral_divisor=6)
    b = cfg(decay=0.75, gate_margin=0.0, n0=4, umbral_base=1,
            umbral_divisor=2)
    rng1, rng2 = random.Random(99), random.Random(99)
    h1, h2 = x.mezclar(rng1, a, b), x.mezclar(rng2, a, b)
    check("mezcla: misma semilla -> mismo hijo", h1 == h2)
    check("mezcla: cada valor del hijo pertenece a {A, B}",
          all(h1[k] in (a[k], b[k]) for k in x.PARAMS))
    check("mezcla: los valores quedan dentro de SPACES",
          all(h1[k] in x.SPACES[k] for k in x.PARAMS))
    rng3 = random.Random(7)
    hijos_rng = [x.mezclar(rng3, a, b) for _ in range(40)]
    check("mezcla: sin mutación — 40 hijos solo combinan a los padres",
          all(all(h[k] in (a[k], b[k]) for k in x.PARAMS)
              for h in hijos_rng))

    # -- 3. validez del hijo --------------------------------------------------
    her = x.herencia(h1, a, b)
    check("herencia: disputa = los 5 parámetros (estos padres)",
          len(her["en_disputa"]) == 5)
    valido = x.motivo_invalidez(h1, a, b, set(), set()) \
        if her["de_a"] and her["de_b"] else "no_hereda_de_ambos"
    # Con la semilla 99 el hijo puede salir clon; se verifica la
    # REGLA, no el azar: un hijo con herencia de ambos es válido.
    rngv = random.Random(1234)
    algun_valido = False
    for _ in range(50):
        hv = x.mezclar(rngv, a, b)
        hv_her = x.herencia(hv, a, b)
        if hv_her["de_a"] and hv_her["de_b"]:
            algun_valido = x.motivo_invalidez(hv, a, b, set(),
                                              set()) is None
            break
    check("validez: hijo con herencia de ambos -> válido", algun_valido)
    check("validez: el clon de A no hereda de B -> descartado",
          x.motivo_invalidez(dict(a), a, b, set(), set())
          == "no_hereda_de_ambos")
    check("validez: el clon de B no hereda de A -> descartado",
          x.motivo_invalidez(dict(b), a, b, set(), set())
          == "no_hereda_de_ambos")
    check("validez: válido difiere de AMBOS padres",
          hv != a and hv != b)

    # -- 4. pares inelegibles -------------------------------------------------
    c1 = cfg(decay=0.75)  # difiere de la base en 1 parámetro
    check("par: distancia 1 -> inelegible",
          not x.par_elegible(BASE, c1)
          and x.par_elegible(BASE, a))
    res_ine = x.generar_tanda([BASE, c1], set(), seed=1)
    check("par: generar_tanda salta el par inelegible con motivo",
          res_ine["hijos"] == []
          and res_ine["registro_pares"][0]["resultado"]
          == "par_inelegible")

    # -- 5. deduplicación -------------------------------------------------------
    pa = cfg(decay=0.25, gate_margin=0.0, n0=1, umbral_base=1,
             umbral_divisor=2)
    pb = cfg(decay=0.75, gate_margin=0.0, n0=1, umbral_base=3,
             umbral_divisor=2)
    # pa y pb difieren en decay y umbral_base: 4 mezclas posibles,
    # dos son los padres y dos los recombinantes rx y ry.
    rx = cfg(decay=0.25, gate_margin=0.0, n0=1, umbral_base=3,
             umbral_divisor=2)
    ry = cfg(decay=0.75, gate_margin=0.0, n0=1, umbral_base=1,
             umbral_divisor=2)
    excl = {x.clave_config(pa), x.clave_config(pb),
            x.clave_config(rx)}
    check("dedupe: recombinante ya medido -> ya_medido_train",
          x.motivo_invalidez(rx, pa, pb, excl, set())
          == "ya_medido_train")
    check("dedupe: recombinante ya en la tanda -> duplicado_en_tanda",
          x.motivo_invalidez(ry, pa, pb, excl,
                             {x.clave_config(ry)})
          == "duplicado_en_tanda")
    res_ded = x.generar_tanda([pa, pb], excl, seed=SEMILLA_CORRIDA)
    check("dedupe: la tanda solo puede traer el recombinante libre",
          all(h["config"] == ry for h in res_ded["hijos"])
          and len(res_ded["hijos"]) <= 1)

    # -- 6. extracción del conjunto de exclusión ------------------------------
    # Fixture: una corrida con una mutación keep, una revert y un
    # candidato completo — la simulación reconstruye los 3 puntos
    # medidos + el scaffold de partida.
    partida = cfg()
    mut_keep = cfg(n0=1)
    mut_rev = cfg(n0=1, decay=0.75)
    completo = cfg(decay=0.75, gate_margin=0.05, n0=2, umbral_base=1,
                   umbral_divisor=4)
    eventos = [
        {"evento": {"tipo": "corrida_iniciada",
                    "scaffold_partida": partida}},
        {"evento": {"tipo": "audit_propuesta", "aceptado": True,
                    "propuesta": {"clave": "n0", "anterior": 4,
                                  "nuevo": 1}}},
        {"evento": {"tipo": "audit_propuesta", "aceptado": False,
                    "propuesta": {"clave": "decay", "anterior": 0.5,
                                  "nuevo": 0.75}}},
        {"evento": {"tipo": "audit_propuesta", "aceptado": False,
                    "propuesta": {"clave": "scaffold_completo",
                                  "anterior": mut_keep,
                                  "nuevo": completo}}},
        {"evento": {"tipo": "audit_propuesta_e3",
                    "propuesta": {"clave": "scaffold_completo",
                                  "nuevo": mut_keep}}},
    ]
    with tempfile.TemporaryDirectory() as d:
        ruta_fix = os.path.join(d, "ledger_fixture.jsonl")
        with open(ruta_fix, "w", encoding="utf-8") as f:
            for e in eventos:
                f.write(json.dumps(e) + "\n")
        desde_fixture = x.configs_desde_ledger(ruta_fix)
    esperados = {x.clave_config(c) for c in
                 (partida, mut_keep, mut_rev, completo)}
    check("exclusión: la simulación del ledger reconstruye lo medido",
          desde_fixture == esperados)

    ruta_screening = os.path.join(
        AQUI, "data_screening_factorial_2026-10-16", "resultados.json")
    desde_screening = x.configs_desde_screening(ruta_screening)
    check("exclusión: el screening aporta sus 18 configuraciones",
          len(desde_screening) == 18)

    ruta_ledger = os.path.join(AQUI, "metaloop_ledger.jsonl")
    desde_ledger = x.configs_desde_ledger(ruta_ledger)
    with open(os.path.join(AQUI, "tanda_generador_1792192469.json"),
              encoding="utf-8") as f:
        tanda_doc = json.load(f)
    pob_real = [dict(BASE)] + [c["config"]
                               for c in tanda_doc["candidatos"]]
    check("exclusión: el ledger real cubre la tanda entera",
          all(x.clave_config(c) in desde_ledger for c in pob_real[1:]))
    check("exclusión: el ledger real cubre las mutaciones históricas",
          len(desde_ledger) >= 13)  # partida(s) + 10 mutaciones +
    # candidatos finales de las corridas (con solapes entre corridas)

    # -- 7. tanda real determinista (sin evaluar a nadie) ---------------------
    excl_real = x.conjunto_exclusion(pob_real, ruta_ledger,
                                     ruta_screening)
    r1 = x.generar_tanda(pob_real, excl_real, seed=SEMILLA_CORRIDA)
    r2 = x.generar_tanda(pob_real, excl_real, seed=SEMILLA_CORRIDA)
    check("tanda real: >= mínimo de 8 hijos válidos",
          len(r1["hijos"]) >= x.N_MINIMO_TANDA)
    check("tanda real: determinista con la semilla de la corrida",
          [h["config"] for h in r1["hijos"]]
          == [h["config"] for h in r2["hijos"]])
    claves_hijos = [x.clave_config(h["config"]) for h in r1["hijos"]]
    check("tanda real: hijos únicos y ninguno ya medido",
          len(set(claves_hijos)) == len(claves_hijos)
          and not any(k in excl_real for k in claves_hijos))
    ok_herencia = True
    for h in r1["hijos"]:
        pa_, pb_ = (pob_real[h["padres"][0]], pob_real[h["padres"][1]])
        her_h = x.herencia(h["config"], pa_, pb_)
        if not her_h["de_a"] or not her_h["de_b"] \
                or h["config"] == pa_ or h["config"] == pb_:
            ok_herencia = False
    check("tanda real: todo hijo hereda de ambos y difiere de ambos",
          ok_herencia)
    check("tanda real: todo hijo trae origen_operador='crossover'",
          all(h["origen_operador"] == "crossover"
              for h in r1["hijos"]))
    check("tanda real: pares inelegibles en la población real = 0",
          all(x.par_elegible(pob_real[i], pob_real[j])
              for i in range(12) for j in range(i + 1, 12)))

    # -- 8. paridad de puerta ---------------------------------------------------
    # Las funciones de decisión no reciben el origen: mismos deltas,
    # mismo veredicto, venga el candidato de donde venga.
    for (di, dh, de3) in ((6.0, 1.0, 0.5), (1.0, 1.0, 0.5),
                          (6.0, -1.0, None), (0.0, 0.0, None)):
        v_auto = decidir_auto_adopcion(di, dh)
        v_e3 = decidir_e3(di, dh, delta_e3=de3, forzar_e3=True) \
            if de3 is not None else None
        check(f"paridad: decisión pura de los deltas ({di}, {dh})",
              v_auto == decidir_auto_adopcion(di, dh)
              and (v_e3 is None
                   or v_e3 == decidir_e3(di, dh, delta_e3=de3,
                                          forzar_e3=True)))

    # -- 9. congelamiento ---------------------------------------------------------
    with tempfile.TemporaryDirectory() as d:
        ruta_t = os.path.join(d, "tanda_crossover_test.json")
        x.guardar_tanda(r1, ruta_t, pob_real,
                        delta_train_padres=[0.0] * 12,
                        n_excluidos=len(excl_real))
        with open(ruta_t, encoding="utf-8") as f:
            doc_t = json.load(f)
    check("congelamiento: el archivo declara tipo, semilla e hijos",
          doc_t["tipo"] == "tanda_crossover"
          and doc_t["semilla"] == SEMILLA_CORRIDA
          and doc_t["n_validos"] == len(r1["hijos"])
          and len(doc_t["poblacion"]) == 12
          and doc_t["poblacion"][0]["id"] == "P0")

    # -- frontera: hashes después ---------------------------------------------
    check("frontera: gate/metaloop/puerta_e3/scaffold intactos",
          all(hash_archivo(os.path.join(AQUI, "alma_service", n)) == h
              for n, h in frontera.items()))

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
