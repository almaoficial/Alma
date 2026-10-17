"""Operador crossover del meta-loop — recombinación uniforme de scaffold.

Pre-registro: preregistro-crossover-2026-10-16.md (sucede al diseño
del 12/10, metaloop_preregistro_crossover.json). Este módulo SOLO
propone: mezcla configuraciones de scaffold ya congeladas de una
población declarada. No evalúa, no decide, no toca la puerta, el
panel, el piso ni el validador — la gobernanza decide, como siempre.

El operador, tal como el papel lo declara:

- Pares elegibles: padres que difieren en >= 2 parámetros (si
  difieren en 1, toda mezcla es un clon).
- Mezcla uniforme por parámetro: por cada parámetro, el hijo toma
  el valor de uno de los dos padres con probabilidad 1/2, con el
  rng sembrado por la semilla de la corrida (reproducible entera).
- Validez del hijo (mecánica, ANTES de evaluar): hereda >= 1
  parámetro-en-disputa de CADA padre (la regla «hijo != padre
  disfrazado»: difiere de ambos en >= 1); no es idéntico a ningún
  padre ni a ningún hijo ya aceptado de la tanda; no coincide con
  ninguna configuración que ya tenga medición train asentada
  (deduplicación contra el conjunto de exclusión: población +
  historial del ledger + screening factorial).
- Hasta 10 re-rolls por par; si no sale un hijo válido, el par se
  salta y queda asentado con motivo. Un hijo por par.
- SIN mutación posterior: ningún paso toca al hijo después del
  cruce, para que su Δ sea atribuible a recombinar.
- Orden de pares determinista (pre-registro §6): (1) los pares de
  P5 por índice del otro padre; (2) los de P3 y después P8 aún no
  procesados; (3) los de P0 aún no procesados; (4) el resto en
  orden lexicográfico (i, j).

La extracción del conjunto de exclusión es mecánica y de solo
lectura: reconstruye del ledger toda configuración con medición
train asentada, simulando cada corrida desde su scaffold_partida
con su semántica keep/revert en orden — la misma secuencia que el
validador midió. Cortafuegos: de los eventos de la etapa puerta
(audit_propuesta_e3) solo se leen las CONFIGURACIONES (para no
re-medir un punto); ningún puntaje held-out/E3 entra a este
módulo en ninguna forma.
"""

import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "exp56_rso"))

import run_experiment56 as e56  # noqa: E402  (SPACES pre-registrado EXP56)

# Mismo espacio que el metaloop y el generador (fuente única: e56).
SPACES = {k: list(v) for k, v in e56.SPACES.items()}
PARAMS = sorted(SPACES.keys())

# Declarados en el pre-registro del crossover (§5 y §6).
N_TANDA_OBJETIVO = 24       # hijos válidos objetivo
N_MINIMO_TANDA = 8          # bajo esto la corrida no se lanza
MAX_REROLLS = 10            # re-rolls por par con el mismo rng
DISTANCIA_MINIMA_PAR = 2    # parámetros en que deben diferir los padres
ORIGEN_OPERADOR = "crossover"


def clave_config(cfg):
    """Clave hashable canónica de una configuración completa."""
    return tuple(cfg[k] for k in PARAMS)


def distancia(a, b):
    """Cantidad de parámetros en que difieren dos configuraciones."""
    return sum(1 for k in PARAMS if a[k] != b[k])


def par_elegible(a, b):
    """Padres elegibles solo si difieren en >= 2 parámetros."""
    return distancia(a, b) >= DISTANCIA_MINIMA_PAR


def orden_pares(n):
    """Orden determinista de procesamiento de pares (pre-registro §6).

    (1) pares de P5 por índice del otro padre; (2) pares de P3 y
    después de P8 aún no procesados, por índice; (3) pares de P0
    aún no procesados, por índice; (4) todos los restantes en
    orden lexicográfico (i, j). Devuelve la lista completa de
    pares (i, j) con i < j, sin duplicados.
    """
    orden = []

    def agregar(i):
        for j in range(n):
            if j == i:
                continue
            par = (min(i, j), max(i, j))
            if par not in orden:
                orden.append(par)

    if n > 5:
        agregar(5)
    if n > 3:
        agregar(3)
    if n > 8:
        agregar(8)
    if n > 0:
        agregar(0)
    for i in range(n):
        for j in range(i + 1, n):
            if (i, j) not in orden:
                orden.append((i, j))
    return orden


def mezclar(rng, a, b):
    """Mezcla uniforme por parámetro: por cada parámetro (en orden
    canónico), el hijo toma el valor de `a` o de `b` con
    probabilidad 1/2 según el rng de la corrida."""
    hijo = {}
    for k in PARAMS:
        hijo[k] = a[k] if rng.random() < 0.5 else b[k]
    return hijo


def herencia(hijo, a, b):
    """Herencia del hijo sobre los parámetros en disputa: de cuáles
    tomó el valor de cada padre. En los parámetros donde los padres
    coinciden, el hijo coincide con ambos por construcción."""
    disputa = [k for k in PARAMS if a[k] != b[k]]
    return {
        "en_disputa": disputa,
        "de_a": [k for k in disputa if hijo[k] == a[k]],
        "de_b": [k for k in disputa if hijo[k] == b[k]],
    }


def motivo_invalidez(hijo, a, b, excluidos, aceptados):
    """None si el hijo es válido; si no, el motivo del descarte.

    `excluidos` y `aceptados` son conjuntos de clave_config().
    Prioridad declarada: (1) la regla del hijo disfrazado;
    (2) identidad con un padre (guarda: la implica (1), pero se
    chequea explícita); (3) duplicado dentro de la tanda;
    (4) punto ya medido en train.
    """
    h = herencia(hijo, a, b)
    if not h["de_a"] or not h["de_b"]:
        return "no_hereda_de_ambos"
    if hijo == a or hijo == b:
        return "identico_a_padre"
    k = clave_config(hijo)
    if k in aceptados:
        return "duplicado_en_tanda"
    if k in excluidos:
        return "ya_medido_train"
    return None


def generar_tanda(poblacion, excluidos, seed,
                  n_objetivo=N_TANDA_OBJETIVO,
                  max_rerolls=MAX_REROLLS):
    """Genera la tanda de hijos bajando por el orden de pares.

    Un hijo por par (el primer roll válido); hasta `max_rerolls`
    rolls por par con el rng de la corrida. Se detiene al llegar a
    `n_objetivo` hijos válidos o al agotar los pares. Todo roll
    queda registrado con su motivo: la tanda es auditable entera
    desde este resultado, sin re-correr nada.

    Devuelve {"semilla", "n_objetivo", "hijos", "registro_pares",
    "pares_total", "pares_procesados", "pares_no_procesados"}.
    """
    rng = random.Random(seed)
    pares = orden_pares(len(poblacion))
    aceptados = []
    aceptados_claves = set()
    registro = []
    for (i, j) in pares:
        if len(aceptados) >= n_objetivo:
            break
        a, b = poblacion[i], poblacion[j]
        if not par_elegible(a, b):
            registro.append({"par": [i, j], "resultado": "par_inelegible",
                             "motivo": "padres_difieren_en_menos_de_2",
                             "rolls": []})
            continue
        rolls = []
        elegido = None
        for r in range(1, max_rerolls + 1):
            hijo = mezclar(rng, a, b)
            motivo = motivo_invalidez(hijo, a, b, excluidos,
                                      aceptados_claves)
            rolls.append({"roll": r, "config": hijo, "motivo": motivo})
            if motivo is None:
                elegido = hijo
                break
        if elegido is not None:
            aceptados.append({
                "indice": len(aceptados) + 1,
                "padres": [i, j],
                "padres_ids": [f"P{i}", f"P{j}"],
                "config": elegido,
                "herencia": herencia(elegido, a, b),
                "roll": len(rolls),
                "origen_operador": ORIGEN_OPERADOR,
            })
            aceptados_claves.add(clave_config(elegido))
            registro.append({"par": [i, j], "resultado": "hijo_aceptado",
                             "hijo_indice": len(aceptados),
                             "rolls": rolls})
        else:
            registro.append({"par": [i, j],
                             "resultado": "par_saltado_sin_hijo_valido",
                             "rolls": rolls})
    procesados = {(r["par"][0], r["par"][1]) for r in registro}
    return {
        "semilla": seed,
        "n_objetivo": n_objetivo,
        "hijos": aceptados,
        "registro_pares": registro,
        "pares_total": len(pares),
        "pares_procesados": len(registro),
        "pares_no_procesados": [list(p) for p in pares
                                if p not in procesados],
    }


# -- conjunto de exclusión: todo punto con medición train asentada ------

def configs_desde_ledger(ledger_path):
    """Reconstruye mecánicamente las configuraciones con medición
    train asentada en el ledger (conjunto de clave_config).

    Simula cada corrida desde su `scaffold_partida` aplicando en
    orden las propuestas auditadas con su semántica: mutación de un
    parámetro (clave = parámetro, anterior/nuevo escalares) o
    candidato completo (clave = 'scaffold_completo', nuevo = config);
    un keep mueve el scaffold simulado, un revert no. De los
    `audit_propuesta_e3` solo se toma la configuración final
    evaluada por la puerta. No se lee ningún delta de held-out/E3:
    las configuraciones identifican puntos ya medidos, nada más.
    """
    configs = set()
    actual = None
    with open(ledger_path, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            ev = json.loads(linea).get("evento", {})
            tipo = ev.get("tipo")
            if tipo == "corrida_iniciada":
                partida = ev.get("scaffold_partida")
                actual = dict(partida) if isinstance(partida, dict) \
                    else None
                if actual is not None and \
                        all(k in actual for k in PARAMS):
                    configs.add(clave_config(actual))
            elif tipo == "audit_propuesta" and actual is not None:
                p = ev.get("propuesta") or {}
                nuevo = p.get("nuevo")
                if p.get("clave") == "scaffold_completo" \
                        and isinstance(nuevo, dict):
                    cand = dict(nuevo)
                elif p.get("clave") in PARAMS:
                    cand = dict(actual)
                    cand[p["clave"]] = nuevo
                else:
                    continue
                if all(k in cand for k in PARAMS):
                    configs.add(clave_config(cand))
                    if ev.get("aceptado"):
                        actual = cand
            elif tipo == "audit_propuesta_e3":
                p = ev.get("propuesta") or {}
                nuevo = p.get("nuevo")
                if isinstance(nuevo, dict) and \
                        all(k in nuevo for k in PARAMS):
                    configs.add(clave_config(nuevo))
    return configs


def configs_desde_screening(ruta):
    """Las 18 configuraciones del screening factorial (16 del
    diseño + punto central + incumbente), todas con medición train
    asentada en su resultados.json."""
    with open(ruta, encoding="utf-8") as f:
        doc = json.load(f)
    configs = set()
    for m in doc.get("mediciones", []):
        configs.add(clave_config(m["config"]))
    for clave in ("centro", "incumbente"):
        if doc.get(clave):
            configs.add(clave_config(doc[clave]["config"]))
    return configs


def conjunto_exclusion(poblacion, ledger_path, screening_path):
    """Unión declarada en el pre-registro §5(iii): la población, el
    historial del ledger y las configuraciones del screening."""
    excluidos = {clave_config(c) for c in poblacion}
    excluidos |= configs_desde_ledger(ledger_path)
    excluidos |= configs_desde_screening(screening_path)
    return excluidos


def guardar_tanda(resultado, ruta, poblacion, delta_train_padres=None,
                  n_excluidos=None):
    """Escribe la tanda completa a disco (JSON) ANTES de evaluar a
    nadie: pares, padres, herencia por parámetro, semilla, rolls
    con motivos. Es la única escritura de este módulo, y solo a la
    `ruta` que pasa el llamador — espejo de guardar_tanda del
    generador."""
    import time
    doc = {
        "tipo": "tanda_crossover",
        "timestamp": time.time(),
        "semilla": resultado.get("semilla"),
        "preregistro": "preregistro-crossover-2026-10-16.md",
        "poblacion": [
            {"id": f"P{i}", "config": {k: c.get(k) for k in PARAMS},
             "delta_train_registrado": (delta_train_padres[i]
                                        if delta_train_padres else None)}
            for i, c in enumerate(poblacion)
        ],
        "n_excluidos": n_excluidos,
        "n_objetivo": resultado.get("n_objetivo"),
        "n_validos": len(resultado.get("hijos", [])),
        "pares_total": resultado.get("pares_total"),
        "pares_procesados": resultado.get("pares_procesados"),
        "pares_no_procesados": resultado.get("pares_no_procesados"),
        "hijos": resultado.get("hijos", []),
        "registro_pares": resultado.get("registro_pares", []),
    }
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    return ruta
