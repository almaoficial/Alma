"""Generador de candidatos del meta-loop — proponente estilo Sakana.

Rol: proponer como Sakana, adoptar como ALMA. Este módulo SOLO propone:
lee la configuración vigente del scaffold y el historial medido del
ledger, le pide a un modelo (tier gratuito de OpenRouter, vía la ruta
existente) una tanda de candidatos con cambios COORDINADOS, valida la
FORMA mecánicamente y devuelve la tanda. No evalúa a nadie: cada
candidato válido entra después por el camino normal del meta-loop
(train → held-out → E3 → puerta), que es el único que decide.

Por qué existe (medido, no opinado): la primera corrida contra la
puerta recableada (16/10/2026, seed 87859) evaluó 8 mutaciones
puntuales del proponente RSO y TODAS dieron Δ_train ≤ 0 — el scaffold
vigente es un óptimo local para movimientos de un parámetro. El
cuello de botella pasó a ser la búsqueda, no la puerta. Este
generador ataca la búsqueda: cambios de ≥ 2 parámetros por candidato,
con el historial de fracasos medido en el prompt para no repetirlos.

FRONTERA DURA (verificada por test_generador_candidatos.py con hashes
antes/después de importar y ejecutar con mocks):
- No importa gate, metaloop, puerta_e3 ni el validador: no puede
  tocar el piso, el panel ni la regla aunque quisiera.
- Del ledger solo LEE (historial). Su única escritura posible es el
  archivo de tanda que el llamador le pasa a guardar_tanda().
- La validación es de FORMA (completitud, tipos, rango, diversidad);
  jamás usa el validador congelado ni la puerta.

Ruta de modelos: la existente del sistema — el CLI or_chat.py de la
skill openrouter (la misma que usa juez_barato.backend_openrouter),
con la credencial surrogate de siempre. Nada de claves en archivos.
Durante la construcción y las pruebas NO se llama a ningún modelo:
todo backend vivo queda para la corrida pre-registrada y autorizada.
"""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                               "exp56_rso"))

import run_experiment56 as e56  # noqa: E402  (SPACES pre-registrado EXP56)

# El espacio de búsqueda es el de EXP56/metaloop, sin cambios: cada
# parámetro solo puede tomar los valores de su lista. Esto ES el rango.
SPACES = {k: list(v) for k, v in e56.SPACES.items()}
PARAMS = sorted(SPACES.keys())
PARAMS_INT = {k for k, vals in SPACES.items()
              if all(isinstance(v, int) for v in vals)}

# Modelo de la corrida pre-registrada: el del precedente del sistema
# (EXP-JUEZ-001 lo pre-registró como tier :free de OpenRouter). La
# regla de reemplazo si el tier rota está en el pre-registro, no acá.
MODELO_DEFAULT = "inclusionai/ling-3.1-flash:free"
TEMPERATURA_DEFAULT = 0.7   # diversidad de propuestas; el validador
#                             es determinista y la tanda se congela a
#                             disco antes de evaluar: la corrida es
#                             reproducible desde la tanda, no desde
#                             el muestreo.
MAX_TOKENS_DEFAULT = 4000
N_TANDA_DEFAULT = 14        # declarado en el pre-registro
N_MINIMO_TANDA = 8          # bajo esto la corrida no se lanza
MAX_LLAMADOS_DEFAULT = 3    # 1 inicial + hasta 2 con feedback mecánico

# Motivos de descarte (validación de forma + piso de diversidad).
M_NO_OBJETO = "no_es_objeto"
M_SIN_CONFIG = "sin_config"
M_SIN_JUSTIFICACION = "sin_justificacion"
M_INCOMPLETA = "config_incompleta"
M_DESCONOCIDO = "parametro_desconocido"
M_TIPO = "tipo_invalido"
M_RANGO = "fuera_de_rango"
M_BASE = "identico_a_base"
M_SIMPLE = "movimiento_simple"
M_DUPLICADO = "duplicado_en_tanda"
M_DIVERSIDAD = "diversidad_insuficiente"
M_PARSEO = "respuesta_no_parseable"


# -- historial medido (solo lectura del ledger) -----------------------------
#
# CORTAFUEGOS DEL PROPONENTE (adenda 2026-10-16, ajuste 1 — origen:
# auditoría web externa: un split ciego reutilizado deja de ser ciego
# si el proponente puede ver sus resultados). El prompt de este
# generador SOLO puede contener: la configuración base, resultados
# de la etapa TRAIN (Δ_train y keep/revert de cada propuesta) y
# categorías de fracaso. NUNCA puntajes ni resultados de held-out o
# E3 de ninguna propuesta, pasada o futura.
#
# Estructuralmente: el historial se construye SOLO desde eventos
# audit_propuesta (la etapa train del meta-loop: on_paso los emite
# con delta_in = Δ de la ronda en train y delta_ho = None por
# construcción) y proyectando SOLO los campos de CAMPOS_TRAIN. Los
# resultados de la puerta viven en otros eventos (audit_propuesta_e3,
# corrida_finalizada) que esta función jamás abre. Y si un evento
# audit_propuesta llegara alguna vez contaminado con carga de la
# etapa puerta (delta_ho no-None o delta_e3 presente), se EXCLUYE
# entero del historial en vez de leerse parcialmente.
# test_generador_candidatos.py lo demuestra con un ledger envenenado:
# puntajes held-out/E3 plantados no llegan ni al historial ni al
# prompt.

EVENTO_HISTORIAL = "audit_propuesta"
CAMPOS_TRAIN = ("clave", "anterior", "nuevo", "delta_in", "aceptado")


def _es_evento_train_limpio(ev):
    """True si el evento es de la etapa train y no trae carga de la
    etapa puerta (cortafuegos: ante la duda, el evento no entra)."""
    return (ev.get("tipo") == EVENTO_HISTORIAL
            and ev.get("delta_ho") is None
            and "delta_e3" not in ev)


def historial_desde_ledger(ledger_path, max_propuestas=24):
    """Lee el ledger del meta-loop y devuelve las propuestas de
    búsqueda ya evaluadas (eventos audit_propuesta), agrupadas por
    corrida. SOLO LECTURA: el archivo no se abre nunca en escritura.

    CORTAFUEGOS (ver el bloque de arriba): solo entran eventos de la
    etapa train sin carga de puerta, y de cada uno se proyectan solo
    los CAMPOS_TRAIN. Ningún Δ de held-out o E3 puede llegar al
    historial — y por tanto tampoco al prompt.

    Devuelve {"corridas": [{"seed":..., "propuestas":[...]}...],
              "propuestas": [ultimas max_propuestas filas],
              "total": n}. Cada fila: {clave, anterior, nuevo,
    delta_in, aceptado} — delta_in es el Δ_train medido (totales).
    """
    corridas = []
    actual = None
    with open(ledger_path, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            ev = json.loads(linea).get("evento", {})
            if ev.get("tipo") == "corrida_iniciada":
                actual = {"seed": ev.get("seed"), "propuestas": []}
                corridas.append(actual)
            elif _es_evento_train_limpio(ev) and actual is not None:
                p = ev.get("propuesta") or {}
                actual["propuestas"].append({
                    "clave": p.get("clave"),
                    "anterior": p.get("anterior"),
                    "nuevo": p.get("nuevo"),
                    "delta_in": ev.get("delta_in"),
                    "aceptado": bool(ev.get("aceptado")),
                })
    filas = [p for c in corridas for p in c["propuestas"]]
    return {"corridas": corridas,
            "propuestas": filas[-max_propuestas:],
            "total": len(filas)}


def _fila_historial(p):
    """Una propuesta medida como fila de tabla para el prompt."""
    a, n = p.get("anterior"), p.get("nuevo")
    if isinstance(a, dict) and isinstance(n, dict):
        cambios = [f"{k}: {a.get(k)} -> {n.get(k)}"
                   for k in PARAMS if a.get(k) != n.get(k)]
        cambio = ("tanda [" + ", ".join(cambios) + "]" if cambios
                  else "scaffold_completo (candidato final, sin cambios)")
    else:
        cambio = f"{p.get('clave')}: {a} -> {n}"
    d = p.get("delta_in")
    delta = f"{d:+.4f}" if isinstance(d, (int, float)) else "?"
    resultado = "KEEP en train" if p.get("aceptado") else "revertido"
    return cambio, delta, resultado


def distancia_cfg(a, b):
    """Distancia de Hamming entre dos configuraciones completas:
    en cuántos parámetros difieren."""
    return sum(1 for k in PARAMS if a.get(k) != b.get(k))


def _fmt_cfg(cfg):
    return json.dumps({k: cfg.get(k) for k in PARAMS},
                      ensure_ascii=False, sort_keys=True)


# -- el prompt ----------------------------------------------------------------

def construir_prompt(base, historial, n_objetivo, aceptados=None,
                     descartes=None):
    """Arma el prompt del generador. Entradas declaradas en el
    pre-registro: config base, espacio válido, la TABLA MEDIDA de
    propuestas ya evaluadas con su Δ_train exacto (desde el ledger,
    sin resumir), y las reglas duras de la tanda. En llamados de
    feedback (2º/3º) se agregan los aceptados y los motivos de
    descarte del llamado anterior, y se pide solo lo que falta.
    """
    lineas = []
    lineas.append(
        "Sos el generador de candidatos de un meta-loop que optimiza "
        "los 5 hiperparámetros de un scaffold. Tu única salida es el "
        "objeto JSON declarado al final, sin texto fuera del JSON.")
    lineas.append("")
    lineas.append("## Configuración vigente (la base)")
    lineas.append(_fmt_cfg(base))
    lineas.append("")
    lineas.append("## Espacio válido (cada parámetro SOLO puede tomar "
                  "estos valores)")
    lineas.append(json.dumps(SPACES, ensure_ascii=False, sort_keys=True))
    lineas.append("")
    lineas.append("## Historial medido: propuestas ya evaluadas en el "
                  "split de entrenamiento")
    lineas.append("Δ_train = mejora del regret medio en train, en "
                  "totales (positivo = mejora; negativo = empeora). "
                  "Para auto-adoptarse, un candidato final necesita "
                  "Δ > 5.4781 en la puerta completa; en train, ninguna "
                  "propuesta histórica superó siquiera el 0.")
    nro = 0
    for corrida in historial.get("corridas", []):
        if not corrida["propuestas"]:
            continue
        lineas.append(f"Corrida (seed {corrida.get('seed')}):")
        lineas.append("| # | cambio | Δ_train | resultado |")
        lineas.append("|---|--------|---------|-----------|")
        for p in corrida["propuestas"]:
            nro += 1
            cambio, delta, resultado = _fila_historial(p)
            lineas.append(f"| {nro} | {cambio} | {delta} | {resultado} |")
    if nro == 0:
        lineas.append("(sin propuestas previas registradas)")
    lineas.append("")
    lineas.append("Lectura obligada de ese historial: TODAS las "
                  "mutaciones de UN SOLO parámetro ya están medidas y "
                  "ninguna mejoró (la mejor empató en 0.0000). No "
                  "propongas movimientos de un solo parámetro ni "
                  "repitas configuraciones ya evaluadas.")
    lineas.append("")
    lineas.append(f"## Tu tarea: proponé {n_objetivo} candidatos NUEVOS")
    lineas.append("Reglas duras (la validación mecánica descarta lo "
                  "que las viole, sin evaluar):")
    lineas.append("1. Cada candidato mueve AL MENOS 2 parámetros "
                  "respecto de la base (cambios coordinados: la "
                  "hipótesis es que la mejora, si existe, está en las "
                  "combinaciones, no en los pasos simples ya medidos).")
    lineas.append("2. Distancia mínima 2 entre TODO par de candidatos "
                  "de la tanda: ninguno puede diferir de otro en un "
                  "solo parámetro. Nada de la misma idea con retoques.")
    lineas.append("3. Configuración completa (los 5 parámetros) y cada "
                  "valor dentro del espacio válido.")
    lineas.append("4. Ni la base ni configuraciones del historial.")
    lineas.append("5. Por candidato, una justificación de UNA línea "
                  "que nombre la interacción que explota (qué "
                  "parámetros combina y por qué).")
    if aceptados:
        lineas.append("")
        lineas.append("## Ya aceptados en esta tanda (no los repitas "
                      "ni les hagas retoques a distancia 1)")
        for a in aceptados:
            lineas.append("- " + _fmt_cfg(a["config"]))
    if descartes:
        from collections import Counter
        motivos = Counter(d["motivo"] for d in descartes)
        lineas.append("")
        lineas.append("## Descartes del llamado anterior (validación "
                      "mecánica)")
        for motivo, cant in sorted(motivos.items()):
            lineas.append(f"- {motivo}: {cant}")
        lineas.append("Corregí esos errores de forma en esta tanda.")
    lineas.append("")
    lineas.append("## Formato de salida (SOLO este JSON)")
    lineas.append('{"candidatos": [{"config": {"decay": ..., '
                  '"gate_margin": ..., "n0": ..., "umbral_base": ..., '
                  '"umbral_divisor": ...}, "justificacion": "..."}, '
                  "...]}")
    return "\n".join(lineas)


# -- parseo de la respuesta ---------------------------------------------------

def parsear_respuesta(texto):
    """Extrae la lista cruda de candidatos de la respuesta del modelo.

    Devuelve (crudos, error): crudos es la lista tal como vino (sin
    validar) y error es None si el JSON se pudo extraer. Tolera
    fences ```json y texto alrededor buscando el objeto JSON; no
    tolera — ni repara — contenido que no sea JSON.
    """
    if not isinstance(texto, str) or not texto.strip():
        return [], "respuesta vacía"
    t = texto.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        t = t.strip()
    obj = None
    try:
        obj = json.loads(t)
    except ValueError:
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            try:
                obj = json.loads(t[i:j + 1])
            except ValueError:
                obj = None
    if obj is None:
        return [], "sin objeto JSON parseable"
    if isinstance(obj, list):
        return obj, None
    if isinstance(obj, dict) and isinstance(obj.get("candidatos"), list):
        return obj["candidatos"], None
    return [], "el JSON no trae una lista de candidatos"


# -- validación mecánica (forma y diversidad; NO evalúa) ----------------------

def _normalizar_valor(clave, valor):
    """Devuelve (valor_normalizado, motivo) — motivo None si es válido
    en tipo y rango. Tipos: bool no es número; los parámetros enteros
    aceptan float integral (se coercionan); el resto, tipo_invalido.
    Rango = membresía en SPACES (el espacio discreto pre-registrado).
    """
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None, M_TIPO
    if clave in PARAMS_INT:
        if isinstance(valor, float):
            if not valor.is_integer():
                return None, M_TIPO
            valor = int(valor)
    else:
        valor = float(valor)
    if valor not in SPACES[clave]:
        return None, M_RANGO
    return valor, None


def validar_candidato(crudo, base):
    """Valida UN candidato crudo contra la base. Devuelve
    (item, motivo): item = {"config", "justificacion"} normalizado o
    None; motivo = None si es válido, o la causa del descarte.
    Solo forma: no mide nada."""
    if not isinstance(crudo, dict):
        return None, M_NO_OBJETO
    cfg = crudo.get("config")
    if not isinstance(cfg, dict):
        return None, M_SIN_CONFIG
    just = crudo.get("justificacion")
    if not isinstance(just, str) or not just.strip():
        return None, M_SIN_JUSTIFICACION
    if set(cfg.keys()) - set(PARAMS):
        return None, M_DESCONOCIDO
    if set(PARAMS) - set(cfg.keys()):
        return None, M_INCOMPLETA
    normalizada = {}
    for clave in PARAMS:
        valor, motivo = _normalizar_valor(clave, cfg[clave])
        if motivo:
            return None, motivo
        normalizada[clave] = valor
    if all(normalizada[k] == base.get(k) for k in PARAMS):
        return None, M_BASE
    if distancia_cfg(normalizada, base) < 2:
        return None, M_SIMPLE
    return {"config": normalizada, "justificacion": just.strip()}, None


def validar_tanda(crudos, base, previos=None):
    """Valida una lista cruda contra la base y el piso de diversidad.

    PISO DE DIVERSIDAD (mecánico, declarado en el pre-registro):
    ningún par de candidatos válidos puede ser idéntico (distancia 0
    → duplicado_en_tanda) ni diferir en un solo parámetro
    (distancia 1 → diversidad_insuficiente). Se aplica contra los
    aceptados de ESTA lista y contra `previos` (aceptados de llamados
    anteriores de la misma tanda), en orden: el primero que llega y
    cumple, queda; el que choca, se descarta con motivo.

    Devuelve {"validos": [items nuevos aceptados],
              "descartados": [{"crudo", "motivo", ...}]}.
    """
    aceptados = [dict(p["config"]) for p in (previos or [])]
    validos = []
    descartados = []
    for crudo in crudos:
        item, motivo = validar_candidato(crudo, base)
        if motivo:
            descartados.append({"crudo": crudo, "motivo": motivo})
            continue
        cfg = item["config"]
        choque = None
        for otra in aceptados:
            d = distancia_cfg(cfg, otra)
            if d == 0:
                choque = M_DUPLICADO
                break
            if d == 1:
                choque = M_DIVERSIDAD
                break
        if choque:
            descartados.append({"crudo": crudo, "motivo": choque,
                                "config": cfg})
            continue
        validos.append(item)
        aceptados.append(cfg)
    return {"validos": validos, "descartados": descartados}


# -- generación (orquestación sobre un backend prompt -> texto) ---------------

def generar_tanda(backend, base, historial, n_objetivo=N_TANDA_DEFAULT,
                  max_llamados=MAX_LLAMADOS_DEFAULT,
                  modelo=MODELO_DEFAULT):
    """Genera y valida la tanda. `backend` es un callable
    prompt -> texto (en producción, backend_openrouter(); en las
    pruebas, un mock — la construcción nunca llama a un modelo vivo).

    Protocolo (declarado en el pre-registro): hasta max_llamados
    llamados; cada llamado posterior al primero recibe los motivos
    de descarte y los aceptados, y pide solo los que faltan. Lo que
    no pasa la validación mecánica se descarta con motivo registrado;
    nada se repara a mano.

    Devuelve {"modelo", "n_objetivo", "candidatos", "descartados",
              "llamados", "prompts"} — la tanda completa, no solo
    los válidos: adoptada o no, es la población registrada.
    """
    validos = []
    descartados = []
    prompts = []
    llamados = 0
    while len(validos) < n_objetivo and llamados < max_llamados:
        prompt = construir_prompt(
            base, historial, n_objetivo - len(validos),
            aceptados=validos if llamados else None,
            descartes=descartados if llamados else None)
        prompts.append(prompt)
        texto = backend(prompt)
        llamados += 1
        crudos, error = parsear_respuesta(texto)
        if error:
            descartados.append({"crudo": None, "motivo": M_PARSEO,
                                "detalle": error})
            continue
        res = validar_tanda(crudos, base, previos=validos)
        validos.extend(res["validos"])
        descartados.extend(res["descartados"])
    return {"modelo": modelo, "n_objetivo": n_objetivo,
            "candidatos": validos, "descartados": descartados,
            "llamados": llamados, "prompts": prompts}


def guardar_tanda(resultado, ruta, base, ledger_path=None):
    """Escribe la tanda completa a disco (JSON). Es la ÚNICA
    escritura de este módulo, y solo al `ruta` que pasa el llamador:
    la tanda queda congelada antes de que el meta-loop evalúe a
    nadie, para que la corrida sea reproducible desde el archivo.
    """
    doc = {
        "tipo": "tanda_generador_candidatos",
        "timestamp": time.time(),
        "modelo": resultado.get("modelo"),
        "base": {k: base.get(k) for k in PARAMS},
        "ledger_fuente": ledger_path,
        "n_objetivo": resultado.get("n_objetivo"),
        "n_validos": len(resultado.get("candidatos", [])),
        "llamados": resultado.get("llamados"),
        "candidatos": resultado.get("candidatos", []),
        "descartados": resultado.get("descartados", []),
        "prompts": resultado.get("prompts", []),
    }
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    return ruta


# -- backend vivo (SOLO lo usa la corrida autorizada) ---------------------------

def backend_openrouter(modelo=MODELO_DEFAULT,
                       max_tokens=MAX_TOKENS_DEFAULT,
                       temperature=TEMPERATURA_DEFAULT, timeout=240):
    """Backend OpenRouter por la ruta existente: el CLI or_chat.py de
    la skill openrouter (el mismo de juez_barato.backend_openrouter,
    parametrizado en temperatura/max_tokens porque generar no es
    juzgar). La credencial viaja como surrogate dentro del CLI; este
    módulo nunca ve ni guarda claves.
    """
    or_chat = os.path.expanduser(
        "~/workspace/skills/openrouter/bin/or_chat.py")

    def _backend(prompt):
        msgs = json.dumps([{"role": "user", "content": prompt}])
        r = subprocess.run(
            [sys.executable, or_chat, "--model", modelo,
             "--messages", msgs, "--max-tokens", str(max_tokens),
             "--temperature", str(temperature),
             "--timeout", str(timeout)],
            capture_output=True, text=True, timeout=timeout + 30)
        if r.returncode != 0:
            raise RuntimeError(f"or_chat falló: {r.stderr[:200]}")
        return json.loads(r.stdout)["text"]

    return _backend
