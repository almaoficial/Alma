#!/usr/bin/env python3
"""ALMA-EXP71: el loop sobre el feed real durante 1 semana (mock, US$0).

Cada dia = 1 bloque. El loop predice la categoria dominante del feed del
dia; a la manana siguiente se puntua contra el dominante observado.

Maquinaria (parametros congelados en data_exp71/PREREGISTRO.md):
  Thompson Beta por categoria + skip/gate + detector de heterogeneidad
  (K=3, J=3, semantica EXP68 adaptada a 1 observacion/dia).
Scaffold: n0=4, umbral_base=1, umbral_divisor=3, decay=0.5.

NO toca el servicio vivo del puerto 8471 ni alma_service: todo el loop
vive en este archivo (transplante autocontenido y pre-registrado).

Uso:
  python3 run_exp71.py --setup            # hoy: semilla + congela prediccion de hoy
  python3 run_exp71.py --run              # diario (cron): puntua ayer, predice hoy
  python3 run_exp71.py --run --hoy YYYY-MM-DD   # override solo para tests
  python3 run_exp71.py --selftest         # escenario sintetico en /tmp (valida el harness)

Variables de entorno:
  EXP71_DATA: directorio de datos (default: <este_dir>/data_exp71)
"""

import argparse
import json
import os
import random
import shutil
import sys
import tempfile
from collections import Counter
from datetime import date, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("EXP71_DATA", os.path.join(BASE, "data_exp71"))
INBOX = os.path.join(DATA, "inbox")
ESTADO_P = os.path.join(DATA, "estado.json")
RESULTADOS_P = os.path.join(DATA, "resultados.jsonl")
PREDICCIONES_P = os.path.join(DATA, "predicciones.jsonl")
VEREDICTO_P = os.path.join(DATA, "VEREDICTO.md")
SEED_FEED = os.path.join(BASE, "data_exp44", "feed_units.json")

# --- parametros congelados (PREREGISTRO.md) ---
N0 = 4
DECAY = 0.5
SKIP_GAP = 1.0 / 3.0      # transplante de umbral_base/umbral_divisor a P
K_DET = 3
J_DET = 3
MIN_UNITS = 5
SETUP_FECHA = "2026-09-28"
MAX_RUNS = 10
N_PUNTUADOS_VEREDICTO = 7

EXPLORAR = "explorar"
ENCOGIDO = "encogido"


# ---------------------------------------------------------------- detector
class DetectorDiario:
    """Transplante del DetectorHeterogeneidad (EXP68) a 1 observacion/dia.

    K veredictos estrictos iguales seguidos -> ENCOGIDO (compromete).
    Spot-check cada J dias encogidos. Salida: el dominante observado del
    spot-check es estricto Y distinto del comprometido (los empates no
    expulsan: histeresis EXP68). En ENCOGIDO el posterior sigue
    actualizandose; solo la prediccion esta comprometida.
    """

    def __init__(self, d=None):
        d = d or {}
        self.modo = d.get("modo", EXPLORAR)
        self.racha_ganador = d.get("racha_ganador")
        self.racha_n = d.get("racha_n", 0)
        self.comprometido = d.get("comprometido")
        self.n_encogido = d.get("n_encogido", 0)
        self.historial = d.get("historial", [])

    def to_dict(self):
        return {"modo": self.modo, "racha_ganador": self.racha_ganador,
                "racha_n": self.racha_n, "comprometido": self.comprometido,
                "n_encogido": self.n_encogido, "historial": self.historial}

    def registrar_veredicto(self, fecha, ganador):
        """ganador: categoria del dominante estricto, o None (empate/SKIP)."""
        if self.modo != EXPLORAR:
            return
        if ganador is not None and ganador == self.racha_ganador:
            self.racha_n += 1
        elif ganador is not None:
            self.racha_ganador = ganador
            self.racha_n = 1
        else:
            self.racha_ganador = None
            self.racha_n = 0
        if self.racha_n >= K_DET:
            self.modo = ENCOGIDO
            self.comprometido = self.racha_ganador
            self.n_encogido = 0
            self.historial.append({"evento": "encoge", "fecha": fecha,
                                   "brazo": self.comprometido,
                                   "racha": self.racha_n})

    def iniciar_dia(self):
        """Avanza el contador encogido. Retorna True si toca spot-check."""
        assert self.modo == ENCOGIDO
        self.n_encogido += 1
        return self.n_encogido % J_DET == 0

    def resolver_spotcheck(self, fecha, dominante, empate):
        """Retorna True si se restaura la exploracion."""
        assert self.modo == ENCOGIDO
        if not empate and len(dominante) == 1 and dominante[0] != self.comprometido:
            self.historial.append({"evento": "restaura", "fecha": fecha,
                                   "brazo": self.comprometido,
                                   "observado": dominante[0]})
            self.modo = EXPLORAR
            self.racha_ganador = None
            self.racha_n = 0
            self.comprometido = None
            self.n_encogido = 0
            return True
        self.historial.append({"evento": "spot_ok", "fecha": fecha,
                               "brazo": self.comprometido})
        return False


# ---------------------------------------------------------------- utilidades
def hoy_local(override=None):
    if override:
        return override
    return date.today().isoformat()


def ayer(fecha):
    d = date(*map(int, fecha.split("-")))
    return (d - timedelta(days=1)).isoformat()


def dominante_de(conteo):
    """-> (lista_top, es_empate)."""
    if not conteo:
        return [], True
    mx = max(conteo.values())
    top = sorted([c for c, n in conteo.items() if n == mx])
    return top, len(top) > 1


def cargar_inbox(fecha):
    """-> (lista_categorias | None, motivo)."""
    p = os.path.join(INBOX, "feed_%s.json" % fecha)
    if not os.path.exists(p):
        return None, "sin inbox"
    try:
        with open(p, encoding="utf-8") as f:
            doc = json.load(f)
        cats = []
        sin_cat = 0
        for u in doc.get("unidades", []):
            c = (u.get("categoria") or "").strip()
            if c:
                cats.append(c)
            else:
                sin_cat += 1
        return {"categorias": cats, "sin_categoria": sin_cat}, None
    except Exception as e:  # noqa: BLE001 - inbox corrupto = SKIP honesto
        return None, "inbox ilegible: %s" % e


def cargar_estado():
    with open(ESTADO_P, encoding="utf-8") as f:
        return json.load(f)


def guardar_estado(est):
    tmp = ESTADO_P + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(est, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ESTADO_P)


def append_jsonl(path, obj):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def leer_prediccion(fecha):
    if not os.path.exists(PREDICCIONES_P):
        return None
    with open(PREDICCIONES_P, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("fecha") == fecha:
                return r
    return None


def medias(posterior):
    return {c: a / (a + b) for c, (a, b) in posterior.items()}


def favorito(posterior):
    m = medias(posterior)
    orden = sorted(m, key=lambda c: (-m[c], c))
    return orden[0], (orden[1] if len(orden) > 1 else None), m


# ---------------------------------------------------------------- setup
def cmd_setup(hoy):
    assert hoy == SETUP_FECHA, "el setup pre-registrado corre el %s" % SETUP_FECHA
    assert not os.path.exists(ESTADO_P), "estado ya existe; setup una sola vez"
    os.makedirs(INBOX, exist_ok=True)

    with open(SEED_FEED, encoding="utf-8") as f:
        seed = json.load(f)
    conteo = Counter(u["category"].strip() for u in seed
                     if (u.get("category") or "").strip())
    n_seed = sum(conteo.values())
    w = N0 / n_seed
    posterior = {c: [1.0 + w * n, 1.0 + w * (n_seed - n)]
                 for c, n in conteo.items()}
    dom, empate = dominante_de(conteo)
    assert not empate, "la semilla debe tener dominante estricto"
    dom_seed = dom[0]

    est = {
        "setup_fecha": hoy,
        "n_seed": n_seed,
        "n_categorias_seed": len(posterior),
        "dominante_seed": dom_seed,
        "posterior": posterior,
        "observados": [{"fecha": "seed:2026-09-22/23", "dominante": [dom_seed],
                        "empate": False, "estricto": True}],
        "detector": DetectorDiario().to_dict(),
        "runs": [],
        "puntuados": 0,
        "skips": 0,
        "aviso_inbox_enviado": False,
        "rot_transiciones": 0,
        "rot_totales": 0,
        "empates": 0,
        "dias_probe": 0,
        "probe_aciertos": 0,
        "veredicto_emitido": False,
    }
    # La prediccion para hoy se congela con SOLO la semilla (no se lee el
    # feed de hoy en el setup).
    pred = predecir(est, hoy)
    guardar_estado(est)
    append_jsonl(PREDICCIONES_P, pred)
    print(json.dumps({"ok": True, "setup": hoy,
                      "dominante_seed": dom_seed,
                      "n_seed": n_seed, "n_categorias": len(posterior),
                      "prediccion_hoy": pred["loop_predicho"],
                      "via": pred["via"]}, ensure_ascii=False))


# ---------------------------------------------------------------- prediccion
def predecir(est, fecha_T):
    """Congela la prediccion para fecha_T. Muta est (detector n_encogido)."""
    det = DetectorDiario(est["detector"])
    post = est["posterior"]
    fav, segundo, m = favorito(post)
    es_spotcheck = False
    via = None
    if det.modo == ENCOGIDO:
        es_spotcheck = det.iniciar_dia()
        if es_spotcheck:
            rng = random.Random(int(fecha_T.replace("-", "")))
            theta = {c: rng.betavariate(a, b) for c, (a, b) in post.items()}
            orden = sorted(theta, key=lambda c: (-theta[c], c))
            pred = orden[0]
            via = "spotcheck_thompson"
        else:
            pred = det.comprometido
            via = "encogido"
        es_probe = None
    else:
        gap = m[fav] - (m[segundo] if segundo else 0.0)
        if gap >= SKIP_GAP:
            pred, via, es_probe = fav, "skip", False
        else:
            rng = random.Random(int(fecha_T.replace("-", "")))
            theta = {c: rng.betavariate(a, b) for c, (a, b) in post.items()}
            orden = sorted(theta, key=lambda c: (-theta[c], c))
            pred = orden[0]
            via = "thompson"
            es_probe = (pred != fav)
    est["detector"] = det.to_dict()

    # baselines con la misma historia (solo dominantes estrictos)
    estrictos = [(o["fecha"], o["dominante"][0]) for o in est["observados"]
                 if o.get("estricto")]
    persist = estrictos[-1][1]
    cnt = Counter(d for _, d in estrictos)
    mx = max(cnt.values())
    cand = [c for c, n in cnt.items() if n == mx]
    if len(cand) == 1:
        moda = cand[0]
    else:
        ultima = {c: max(f for f, d in estrictos if d == c) for c in cand}
        top_rec = max(ultima.values())
        cand2 = sorted(c for c in cand if ultima[c] == top_rec)
        moda = cand2[0]
    n_cats = len(post)

    return {"tipo": "prediccion", "fecha": fecha_T, "loop_predicho": pred,
            "via": via, "es_probe": es_probe, "es_spotcheck": es_spotcheck,
            "modo_detector": det.modo, "comprometido": det.comprometido,
            "favorito": fav, "baseline_persistencia": persist,
            "baseline_moda": moda, "n_categorias": n_cats}


# ---------------------------------------------------------------- update
def actualizar(est, fecha_obs, dominante, empate):
    """Actualiza posterior + detector con el dia observado."""
    # 1. registrar brazos nuevos (Beta(1,1)) antes de computar nada
    for c in dominante:
        if c not in est["posterior"]:
            est["posterior"][c] = [1.0, 1.0]
    # 2. posterior (empates: sin update, pre-registrado)
    if not empate and len(dominante) == 1:
        d = dominante[0]
        for c in est["posterior"]:
            a, b = est["posterior"][c]
            est["posterior"][c] = [a * DECAY, b * DECAY + 1.0]
        a, b = est["posterior"][d]
        est["posterior"][d] = [a + 1.0, b]
    # 3. detector
    det = DetectorDiario(est["detector"])
    if det.modo == ENCOGIDO:
        # la salida solo se evalua en dias de spot-check
        # (el flag se guardo en la prediccion congelada de este dia)
        pred_dia = leer_prediccion(fecha_obs) or {}
        if pred_dia.get("es_spotcheck"):
            det.resolver_spotcheck(fecha_obs, dominante, empate)
    else:
        det.registrar_veredicto(fecha_obs,
                                dominante[0] if not empate and len(dominante) == 1 else None)
    est["detector"] = det.to_dict()
    # 4. historia de observados
    est["observados"].append({"fecha": fecha_obs, "dominante": dominante,
                              "empate": empate,
                              "estricto": (not empate and len(dominante) == 1)})
    if empate:
        est["empates"] += 1


# ---------------------------------------------------------------- run diario
def final_flags(est):
    return {"aviso_inbox": False,
            "veredicto_listo": bool(est.get("veredicto_emitido")),
            "desactivar_cron": bool(est.get("veredicto_emitido"))}


def cmd_run(hoy):
    if os.path.exists(VEREDICTO_P):
        est = cargar_estado()
        out = {"ok": True, "fecha_run": hoy, "nota": "veredicto ya emitido"}
        out.update(final_flags(est))
        print(json.dumps(out, ensure_ascii=False))
        return

    est = cargar_estado()
    if hoy <= est["setup_fecha"]:
        # El primer disparo del cron (lun 28/9 11:00) cae en el dia del
        # setup: la prediccion de hoy ya esta congelada; no hay nada que
        # puntuar (los dias puntuados arrancan el 28/9). No-op idempotente.
        print(json.dumps({"ok": True, "fecha_run": hoy,
                          "nota": "dia de setup: no-op, la prediccion de hoy "
                                  "ya esta congelada"}, ensure_ascii=False))
        return
    if hoy in est["runs"]:
        out = {"ok": True, "fecha_run": hoy, "nota": "run ya ejecutado hoy"}
        out.update(final_flags(est))
        print(json.dumps(out, ensure_ascii=False))
        return

    dia = ayer(hoy)  # se puntua el dia completo de ayer
    inbox, motivo = cargar_inbox(dia)
    aviso = False

    if inbox is None or len(inbox["categorias"]) < MIN_UNITS:
        motivo = motivo or ("pocas unidades: %d < %d"
                            % (len(inbox["categorias"]), MIN_UNITS))
        append_jsonl(RESULTADOS_P, {"tipo": "skip", "fecha": dia,
                                    "motivo": motivo})
        est["skips"] += 1
        if motivo == "sin inbox" and not est["aviso_inbox_enviado"]:
            aviso = True
            est["aviso_inbox_enviado"] = True
        # La prediccion para hoy igual se congela (continuidad de la
        # cadena); el SKIP no puntua, no actualiza, no alimenta al detector.
        pred = predecir(est, hoy)
        append_jsonl(PREDICCIONES_P, pred)
        est["runs"].append(hoy)
        guardar_estado(est)
        out = {"ok": True, "fecha_run": hoy, "dia": dia, "skip": True,
               "motivo": motivo, "puntuados": est["puntuados"],
               "runs": len(est["runs"]), "aviso_inbox": aviso,
               "veredicto_listo": False, "desactivar_cron": False}
        print(json.dumps(out, ensure_ascii=False))
        return

    conteo = Counter(inbox["categorias"])
    for c in conteo:  # brazos nuevos antes del dominante
        if c not in est["posterior"]:
            est["posterior"][c] = [1.0, 1.0]
    dom, empate = dominante_de(conteo)

    # puntuar la prediccion congelada de ayer
    pc = leer_prediccion(dia)
    assert pc is not None, "falta la prediccion congelada de %s" % dia
    ok_loop = pc["loop_predicho"] in dom
    ok_p = pc["baseline_persistencia"] in dom
    ok_m = pc["baseline_moda"] in dom
    if pc.get("es_probe"):
        est["dias_probe"] += 1
        est["probe_aciertos"] += 1 if ok_loop else 0

    # rotacion vs dia anterior puntuado (la semilla no cuenta como dia:
    # X/(puntuados-1) transiciones entre dias puntuados)
    prev = est["observados"][-1]
    if not prev["fecha"].startswith("seed:"):
        if set(prev["dominante"]) != set(dom):
            est["rot_transiciones"] += 1
        est["rot_totales"] += 1

    append_jsonl(RESULTADOS_P,
                 {"tipo": "dia", "fecha": dia, "n_unidades": len(inbox["categorias"]),
                  "n_sin_categoria": inbox["sin_categoria"],
                  "dominante": dom, "empate": empate,
                  "conteo_top5": dict(conteo.most_common(5)),
                  "loop_predicho": pc["loop_predicho"], "via": pc["via"],
                  "es_probe": pc["es_probe"], "modo_detector": pc["modo_detector"],
                  "correcto_loop": ok_loop,
                  "baseline_persistencia": pc["baseline_persistencia"],
                  "correcto_persistencia": ok_p,
                  "baseline_moda": pc["baseline_moda"],
                  "correcto_moda": ok_m})

    actualizar(est, dia, dom, empate)
    est["puntuados"] += 1

    pred = predecir(est, hoy)
    append_jsonl(PREDICCIONES_P, pred)
    est["runs"].append(hoy)
    guardar_estado(est)

    veredicto_listo = est["puntuados"] >= N_PUNTUADOS_VEREDICTO
    desactivar = False
    if veredicto_listo:
        escribir_veredicto(est, "completo")
        est["veredicto_emitido"] = True
        guardar_estado(est)
        desactivar = True
    elif len(est["runs"]) >= MAX_RUNS:
        escribir_veredicto(est, "inconcluso")
        est["veredicto_emitido"] = True
        guardar_estado(est)
        desactivar = True
        veredicto_listo = True

    out = {"ok": True, "fecha_run": hoy, "dia": dia, "skip": False,
           "dominante": dom, "empate": empate,
           "correcto_loop": ok_loop, "puntuados": est["puntuados"],
           "runs": len(est["runs"]), "aviso_inbox": aviso,
           "prediccion_hoy": pred["loop_predicho"], "via_hoy": pred["via"],
           "veredicto_listo": veredicto_listo,
           "desactivar_cron": desactivar}
    print(json.dumps(out, ensure_ascii=False))


# ---------------------------------------------------------------- veredicto
def escribir_veredicto(est, modo):
    dias = []
    if os.path.exists(RESULTADOS_P):
        with open(RESULTADOS_P, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("tipo") == "dia":
                    dias.append(r)
    n = len(dias)
    acc = lambda k: (sum(1 for d in dias if d[k]) / n) if n else 0.0
    a_loop, a_p, a_m = acc("correcto_loop"), acc("correcto_persistencia"), acc("correcto_moda")

    if modo == "inconcluso":
        titulo = "INCONCLUSO"
        decision = ("No se reunieron 7 dias puntuados en 10 runs "
                    "(puntuados=%d). La falta de datos no es refutacion." % n)
    else:
        ok = (a_loop > a_p) and (a_loop > a_m)
        titulo = "PASS" if ok else "FAIL"
        decision = ("PASS ⟺ acc_loop > acc_persist ∧ acc_loop > acc_moda. "
                    "Resultado: %s." % titulo)

    det = DetectorDiario(est["detector"])
    enganches = [h for h in det.historial if h["evento"] == "encoge"]
    restauras = [h for h in det.historial if h["evento"] == "restaura"]

    L = []
    L.append("# EXP71 — Veredicto: **%s**" % titulo)
    L.append("")
    L.append("**Fecha:** %s. **Costo:** mock, US$0. Pre-registro congelado el 2026-09-28." % hoy_local())
    L.append("**Modo:** %s (puntuados=%d, runs=%d, skips=%d)." % (modo, n, len(est["runs"]), est["skips"]))
    L.append("")
    L.append("## Decision pre-registrada")
    L.append("")
    L.append(decision)
    L.append("")
    L.append("| Politica | Accuracy | Correctos |")
    L.append("|---|---|---|")
    L.append("| loop (Thompson+probe+skip+detector) | %.3f | %d/%d |" % (a_loop, sum(1 for d in dias if d["correcto_loop"]), n))
    L.append("| persistencia | %.3f | %d/%d |" % (a_p, sum(1 for d in dias if d["correcto_persistencia"]), n))
    L.append("| moda historica | %.3f | %d/%d |" % (a_m, sum(1 for d in dias if d["correcto_moda"]), n))
    L.append("")
    L.append("## Dia por dia")
    L.append("")
    L.append("| Dia | Dominante | Loop (via) | OK | Persist | OK | Moda | OK |")
    L.append("|---|---|---|---|---|---|---|---|")
    for d in dias:
        L.append("| %s | %s%s | %s (%s) | %s | %s | %s | %s | %s |" % (
            d["fecha"], ",".join(d["dominante"]),
            " [empate]" if d["empate"] else "",
            d["loop_predicho"], d["via"],
            "1" if d["correcto_loop"] else "0",
            d["baseline_persistencia"], "1" if d["correcto_persistencia"] else "0",
            d["baseline_moda"], "1" if d["correcto_moda"] else "0"))
    L.append("")
    L.append("## Secundarias")
    L.append("")
    rot = ("%d/%d" % (est["rot_transiciones"], est["rot_totales"])
           if est["rot_totales"] else "n/d")
    L.append("- Rotacion del dominante dia a dia: %s (EXP44 a nivel bloque: 8/8)." % rot)
    L.append("- Dias de probe: %d, aciertos en probe: %d." % (est["dias_probe"], est["probe_aciertos"]))
    L.append("- Enganches del detector: %d; restauraciones: %d." % (len(enganches), len(restauras)))
    L.append("- Empates de dominante: %d." % est["empates"])
    L.append("- Skips: %d (%s)." % (est["skips"], "ver resultados.jsonl"))
    L.append("")
    L.append("## Caveats")
    L.append("")
    L.append("- n=7: piloto de baja potencia, pre-registrado como tal.")
    L.append("- Stream curado por interes personal + ~18%% fabricado: ver PREREGISTRO.md §2.")
    L.append("- Taxonomia sin normalizar: casi-duplicados cuentan como distintos.")
    L.append("- En dias SKIP la prediccion igual se congelo (continuidad); no puntuan.")
    L.append("")
    L.append("## Archivos")
    L.append("")
    L.append("- `PREREGISTRO.md` — diseno y criterio (congelado antes de medir).")
    L.append("- `resultados.jsonl` — un registro por dia puntuado/SKIP.")
    L.append("- `predicciones.jsonl` — predicciones congeladas con timestamp de escritura.")
    L.append("- `estado.json` — posterior, detector, contadores (auditoria).")
    with open(VEREDICTO_P, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


# ---------------------------------------------------------------- selftest
def cmd_selftest():
    tmp = tempfile.mkdtemp(prefix="exp71_selftest_")
    os.environ["EXP71_DATA"] = tmp
    global DATA, INBOX, ESTADO_P, RESULTADOS_P, PREDICCIONES_P, VEREDICTO_P
    DATA, INBOX = tmp, os.path.join(tmp, "inbox")
    ESTADO_P = os.path.join(tmp, "estado.json")
    RESULTADOS_P = os.path.join(tmp, "resultados.jsonl")
    PREDICCIONES_P = os.path.join(tmp, "predicciones.jsonl")
    VEREDICTO_P = os.path.join(tmp, "VEREDICTO.md")
    os.makedirs(INBOX, exist_ok=True)

    # semilla sintetica: 94 unidades, A dominante (16), B (11), C (9)
    seed = []
    for i, (c, n) in enumerate([("A", 16), ("B", 11), ("C", 9), ("D", 58)]):
        seed += [{"id": "s%d" % (i * 100 + j), "published_at": "2026-09-22T20:00:00",
                  "title": "t", "text": "x", "category": c} for j in range(n)]
    global SEED_FEED
    SEED_FEED = os.path.join(tmp, "seed.json")
    with open(SEED_FEED, "w", encoding="utf-8") as f:
        json.dump(seed, f)

    def inbox(fecha, pares):
        doc = {"fecha": fecha, "unidades": []}
        k = 0
        for c, n in pares:
            for _ in range(n):
                doc["unidades"].append({"id": "u%d" % k, "categoria": c})
                k += 1
        with open(os.path.join(INBOX, "feed_%s.json" % fecha), "w", encoding="utf-8") as f:
            json.dump(doc, f)

    d0 = date(2026, 9, 28)
    dias = [(d0 + timedelta(days=i)).isoformat() for i in range(9)]
    # d0..d7 observados; d4 sin inbox (SKIP); d6 empate
    inbox(dias[0], [("A", 6), ("B", 2)])
    inbox(dias[1], [("A", 5), ("B", 3)])
    inbox(dias[2], [("A", 7), ("C", 1)])
    inbox(dias[3], [("A", 5), ("B", 2)])
    # dias[4]: sin inbox -> SKIP
    inbox(dias[5], [("B", 6), ("A", 2)])
    inbox(dias[6], [("A", 4), ("B", 4)])   # empate
    inbox(dias[7], [("C", 5), ("A", 2)])
    # dias[8] no necesita inbox: el run 8 puntua dias[7] y cierra el veredicto

    cmd_setup(dias[0])
    for t in dias[1:]:
        cmd_run(t)

    assert os.path.exists(VEREDICTO_P), "el veredicto debio emitirse"
    est = cargar_estado()
    assert est["puntuados"] == 7, est["puntuados"]
    assert est["skips"] == 1, est["skips"]
    det = DetectorDiario(est["detector"])
    evs = [h["evento"] for h in det.historial]
    assert "encoge" in evs, evs  # A x3 -> shrink
    print("SELFTEST OK")
    print("eventos detector:", evs)
    print("puntuados=%d skips=%d" % (est["puntuados"], est["skips"]))
    with open(VEREDICTO_P, encoding="utf-8") as f:
        print("---- VEREDICTO (sintetico) ----")
        print(f.read())
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--hoy", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        cmd_selftest()
    elif a.setup:
        cmd_setup(hoy_local(a.hoy))
    elif a.run:
        cmd_run(hoy_local(a.hoy))
    else:
        ap.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
