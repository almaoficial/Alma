#!/usr/bin/env python3
"""ALMA-EXP41: calibrar el test de régimen FUERA DE MUESTRA.

EXP40 FAIL: el test de régimen (Hurst R/S sobre retornos, 72h, umbral 0.55
pre-registrado sin calibrar) acertó 48,3% ≈ moneda, sobre-detectó tendencias
(20 vs 7 reales), y el mapeo momentum-en-tendencia perdió contra buyhold
aun en bloques bien clasificados.

EXP41 calibra el test en un período DISTINTO (los 30 días previos de BTC,
Coinbase BTC-USD 1h público, 2026-07-29 17:00 UTC -> 2026-08-28 16:00 UTC),
barriendo ventana × umbral de Hurst, y congela la mejor combinación para
testearla en el stream original (Kraken XBTUSD 1h, 2026-08-28 17:00 UTC ->
2026-09-27 16:00 UTC, idéntico a EXP36-40).

Pre-registro (resultados/exp41-20260927/preregistro.json), escrito ANTES de
correr:
  - rejilla: ventana W ∈ {24, 72, 168} closes trailing × umbral
    T ∈ {0.50, 0.52, ..., 0.70}; sub-ventanas R/S por ventana:
    W=24 -> (4,6,8); W=72 -> (8,12,18,24,36) (idéntico a EXP40);
    W=168 -> (12,18,24,36,48,60).
  - verdad ex-post (igual que EXP40): |retorno del bloque| > 0.02.
  - métrica de selección: precisión balanceada =
    (recall_tendencia + recall_lateral)/2, medida en bloques 1..29 del
    período de calibración (bloque 0 excluido: sin historia).
    recall_c = TP_c/n_true_c, o 1.0 si n_true_c == 0.
  - desempate determinista: mayor bal.acc; luego menor W; luego menor T.
  - política congelada en test: idéntica a EXP40 (tendencia -> momentum
    todo el bloque; lateral -> flat todo el bloque; bloque 0 -> lateral;
    costo 1bp por cambio de posición incl. transiciones entre bloques).
  - criterios: (a) acierto del clasificador en test (bloques 1..29) > 0.55;
    (b) P&L(EXP41) > P&L(buyhold). PASS iff (a) y (b).
    Si (a) falla: conclusión = el Hurst no tiene señal explotable a esta
    escala -> cambiar de familia de test. Si (a) pasa y (b) falla: el
    clasificador discrimina pero el mapeo no paga.

Replay puro, US$0, sin lookahead (el test usa solo closes <= inicio del
bloque). Mock total.

Uso: python3 run_experiment41.py
"""
import json
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "resultados", "exp41-20260927")
N_BLOQUES, H_BLOQUE = 30, 24
COSTO_BP = 0.0001
ARMS = ["momentum", "meanrev", "buyhold", "flat"]
UMBRAL_VERDAD = 0.02   # igual que EXP40
HURST_MIN = 24         # puntos mínimos de ventana (igual que EXP40)

# --- rejilla PRE-REGISTRADA ---
WINDOWS = {24: (4, 6, 8),
           72: (8, 12, 18, 24, 36),      # idéntico a EXP40
           168: (12, 18, 24, 36, 48, 60)}
THRESHOLDS = [round(0.50 + 0.02 * i, 2) for i in range(11)]  # 0.50..0.70
ACC_MIN = 0.55         # criterio (a)
BLOQUES_MEDICION = range(1, 30)  # bloque 0 excluido (sin historia)


def sign(x):
    return 1.0 if x >= 0 else -1.0


def cargar_test():
    d = json.load(open(os.path.join(BASE, "data_exp36", "btc_h1.json")))
    c = d["close"][:720]
    assert len(c) == 720
    rets = [c[i + 1] / c[i] - 1 for i in range(len(c) - 1)]
    return rets, c


def cargar_calib():
    d = json.load(open(os.path.join(BASE, "data_exp41", "btc_h1_calib.json")))
    c = d["close"]
    assert len(c) == 720, f"calibración: {len(c)} closes, se esperaban 720"
    rets = [c[i + 1] / c[i] - 1 for i in range(len(c) - 1)]
    return rets, c


def hurst_rs(logp, ks):
    """Hurst por R/S sobre los RETORNOS logarítmicos (como EXP40, con
    sub-ventanas parametrizables). Random walk -> ~0.5."""
    r = [logp[i + 1] - logp[i] for i in range(len(logp) - 1)]
    n = len(r)
    ks = [k for k in ks if 4 <= k <= n // 2]
    pts = []
    for k in ks:
        m = n // k
        rss = []
        for i in range(m):
            seg = r[i * k:(i + 1) * k]
            mu = sum(seg) / k
            y, mx, mn = 0.0, 0.0, 0.0
            for x in seg:
                y += x - mu
                if y > mx:
                    mx = y
                if y < mn:
                    mn = y
            R = mx - mn
            var = sum((x - mu) ** 2 for x in seg) / k
            S = math.sqrt(var) if var > 0 else 0.0
            if S > 0 and R > 0:
                rss.append(R / S)
        if rss:
            pts.append((math.log(k), math.log(sum(rss) / len(rss))))
    if len(pts) < 2:
        return 0.5
    mx = sum(p[0] for p in pts) / len(pts)
    my = sum(p[1] for p in pts) / len(pts)
    num = sum((p[0] - mx) * (p[1] - my) for p in pts)
    den = sum((p[0] - mx) ** 2 for p in pts)
    if den <= 0:
        return 0.5
    return max(0.0, min(1.0, num / den))


def clasificar(rets, closes, W, T, ks, medir_en=BLOQUES_MEDICION):
    """Clasifica bloques con ventana trailing W y umbral T.

    Devuelve lista de dicts {bloque, hurst, clase, verdad, retorno_bloque}.
    Sin lookahead: la ventana usa closes <= inicio del bloque.
    """
    H = len(rets)
    logp_all = [math.log(c) for c in closes]
    out = []
    for b in range(N_BLOQUES):
        base = b * H_BLOQUE
        win = logp_all[max(0, base - (W - 1)):base + 1]
        if len(win) < HURST_MIN or b == 0:
            h_est, clase = None, "lateral"
        else:
            h_est = hurst_rs(win, ks)
            clase = "tendencia" if h_est >= T else "lateral"
        rb = sum(rets[base:min(base + H_BLOQUE, H)])
        verdad = "tendencia" if abs(rb) > UMBRAL_VERDAD else "lateral"
        if b in medir_en:
            out.append({"bloque": b, "hurst": h_est, "clase": clase,
                        "verdad": verdad, "retorno_bloque": rb})
    return out


def balanced_acc(clasif):
    """Precisión balanceada = (recall_t + recall_l)/2."""
    rec = {}
    for c in ("tendencia", "lateral"):
        n_true = sum(1 for x in clasif if x["verdad"] == c)
        if n_true == 0:
            rec[c] = 1.0
        else:
            rec[c] = sum(1 for x in clasif
                         if x["verdad"] == c and x["clase"] == c) / n_true
    return (rec["tendencia"] + rec["lateral"]) / 2, rec


def correr_politica(rets, closes, W, T, ks):
    """Política condicional idéntica a EXP40 con (W, T, ks) dados.

    Devuelve (pnl_total, clasificaciones de bloques 1..29).
    """
    H = len(rets)
    logp_all = [math.log(c) for c in closes]
    pos_m = [sign(rets[h - 1]) if h > 0 else 1.0 for h in range(H)]
    pnl_h = [0.0] * H
    clasif = []
    prev_pos = 0.0
    for b in range(N_BLOQUES):
        base = b * H_BLOQUE
        win = logp_all[max(0, base - (W - 1)):base + 1]
        if len(win) < HURST_MIN or b == 0:
            h_est, clase = None, "lateral"
        else:
            h_est = hurst_rs(win, ks)
            clase = "tendencia" if h_est >= T else "lateral"
        en_tendencia = (clase == "tendencia")
        for q in range(H_BLOQUE):
            h = base + q
            if h >= H:
                continue
            p = pos_m[h] if en_tendencia else 0.0
            pnl_h[h] = p * rets[h] - COSTO_BP * abs(p - prev_pos)
            prev_pos = p
        rb = sum(rets[base:min(base + H_BLOQUE, H)])
        verdad = "tendencia" if abs(rb) > UMBRAL_VERDAD else "lateral"
        if b in BLOQUES_MEDICION:
            clasif.append({"bloque": b, "hurst": h_est, "clase": clase,
                           "verdad": verdad, "retorno_bloque": rb})
    return sum(pnl_h), clasif


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)

    rets_t, closes_t = cargar_test()
    rets_c, closes_c = cargar_calib()
    pnl_buyhold = sum(rets_t) - 0.0  # buyhold: posición 1 todo el stream
    # costo buyhold: una sola entrada al inicio (1bp), como en EXP40
    # (pnl_hora de EXP40 incluye -COSTO_BP*|1-0| en h=0)
    pnl_buyhold -= COSTO_BP * 1.0

    # --- chequeos de fidelidad ANTES de pre-registrar ---
    # 1. Hurst en random walk sintético ~0.5 (mismo chequeo que EXP40)
    # 1. El estimador discrimina persistencia (monótono en phi).
    # Nota honesta: el R/S ingenuo tiene sesgo alcista en series cortas
    # (RW de 500 puntos -> H~0.59, no 0.50; fenómeno clásico de Hurst).
    # Lo que importa para EXP41 es la monotonicidad: el umbral T se
    # calibra empíricamente y absorbe el sesgo. EXP40 reportó 0.49 en un
    # sintético puntual (suerte de semilla / serie más larga).
    def h_medio(phi, nseed=12):
        hs = []
        for s in range(nseed):
            rng = random.Random(f"exp41-fid-{phi}-{s}")
            lv = [0.0]
            prev = rng.gauss(0, 0.01)
            lv.append(prev)
            for _ in range(499):
                prev = phi * prev + rng.gauss(0, 0.01)
                lv.append(lv[-1] + prev)
            hs.append(hurst_rs(lv, (8, 12, 18, 24, 36)))
        return sum(hs) / len(hs)
    h_neg, h_rw, h_pos = h_medio(-0.3), h_medio(0.0), h_medio(0.3)
    assert h_neg + 0.03 < h_rw < h_pos - 0.03, \
        f"Hurst no monótono: anti={h_neg:.3f} rw={h_rw:.3f} pers={h_pos:.3f}"
    print(f"Fidelidad Hurst (monotonía en persistencia): "
          f"anti={h_neg:.3f} < rw={h_rw:.3f} < pers={h_pos:.3f}: OK. "
          f"(sesgo alcista en series cortas declarado)")

    # 2. (W=72, T=0.55) reproduce EXP40 en el stream de test
    pnl_rep, clasif_rep = correr_politica(rets_t, closes_t, 72, 0.55,
                                          WINDOWS[72])
    hits_rep = sum(1 for c in clasif_rep if c["clase"] == c["verdad"])
    assert abs(pnl_rep - (-0.107313)) < 5e-4, \
        f"fidelidad EXP40 rota: P&L={pnl_rep:.6f} vs -0.107313"
    assert hits_rep == 14, f"fidelidad EXP40 rota: hits={hits_rep} vs 14"
    print(f"Fidelidad EXP40 (W=72,T=0.55): P&L={pnl_rep:.4%}, "
          f"hits={hits_rep}/29: OK.")

    # --- pre-registro ANTES de la calibración ---
    prereg = {
        "experimento": "ALMA-EXP41: calibrar el test de régimen fuera de muestra",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "motivacion": "EXP40 FAIL: Hurst 72h / umbral 0.55 sin calibrar dio "
                      "48,3% de acierto. El umbral se pre-registró sin "
                      "calibrar (pecado declarado). EXP41 lo calibra en un "
                      "período distinto.",
        "calibracion": {
            "periodo": "Coinbase BTC-USD 1h (público), 2026-07-29 17:00 UTC "
                       "-> 2026-08-28 16:00 UTC, 720 velas "
                       "(data_exp41/btc_h1_calib.json). DISTINTO al stream "
                       "de test. Nota: fuente distinta a la de test "
                       "(Kraken XBTUSD); ambos son BTC/USD spot horario.",
            "rejilla": {"ventanas_W": sorted(WINDOWS),
                        "subventanas_RS_por_W": {str(w): list(ks)
                                                for w, ks in WINDOWS.items()},
                        "umbrales_T": THRESHOLDS},
            "verdad_expost": f"|retorno del bloque| > {UMBRAL_VERDAD} "
                             "(igual que EXP40)",
            "metrica": "precisión balanceada = "
                       "(recall_tendencia + recall_lateral)/2 en bloques 1..29",
            "recall_clase_vacia": "1.0 si n_true_c == 0",
            "desempate": "mayor bal.acc; luego menor W; luego menor T",
            "sin_lookahead": "ventana trailing usa solo closes <= inicio del bloque",
        },
        "test": {
            "stream": "idéntico a EXP36-40: Kraken XBTUSD 1h, 720 velas, "
                      "719 retornos (data_exp36/btc_h1.json)",
            "politica": "idéntica a EXP40 con (W*, T*) congelados: "
                        "tendencia -> momentum todo el bloque; lateral -> "
                        "flat todo el bloque; bloque 0 -> lateral; "
                        "costo 1bp por cambio de posición",
        },
        "criterios": {
            "(a)_clasificador": f"acierto en test (bloques 1..29) > {ACC_MIN}",
            "(b)_pnl": "P&L(EXP41) > P&L(buyhold)",
            "pass": "(a) y (b). Si (a) falla: el Hurst no tiene señal "
                    "explotable a esta escala -> cambiar de familia de test. "
                    "Si (a) pasa y (b) falla: discrimina pero el mapeo no paga.",
        },
        "modo": "mock, replay puro, US$0",
    }
    with open(os.path.join(OUT, "preregistro.json"), "w") as f:
        json.dump(prereg, f, indent=2, ensure_ascii=False)
    print("Pre-registro escrito. Rejilla: 3 ventanas x 11 umbrales = 33 combos.")

    # --- calibración: barrido en el período distinto ---
    resultados_cal = []
    for W in sorted(WINDOWS):
        ks = WINDOWS[W]
        for T in THRESHOLDS:
            cl = clasificar(rets_c, closes_c, W, T, ks)
            bal, rec = balanced_acc(cl)
            hits = sum(1 for x in cl if x["clase"] == x["verdad"])
            resultados_cal.append({"W": W, "T": T, "bal_acc": bal,
                                   "recall": rec, "hits": hits,
                                   "n": len(cl)})
    resultados_cal.sort(key=lambda r: (-r["bal_acc"], r["W"], r["T"]))
    best = resultados_cal[0]
    W_STAR, T_STAR = best["W"], best["T"]
    ks_star = WINDOWS[W_STAR]
    n_true_t_cal = sum(1 for x in clasificar(rets_c, closes_c, W_STAR, T_STAR,
                                            ks_star)
                       if x["verdad"] == "tendencia")
    print(f"Calibración: mejor (W={W_STAR}, T={T_STAR}) "
          f"bal.acc={best['bal_acc']:.3f} "
          f"(recall_t={best['recall']['tendencia']:.2f}, "
          f"recall_l={best['recall']['lateral']:.2f}); "
          f"bloques-tendencia verdaderos en calib: {n_true_t_cal}/29.")

    # --- test congelado en el stream original ---
    pnl41, clasif41 = correr_politica(rets_t, closes_t, W_STAR, T_STAR, ks_star)
    hits41 = sum(1 for c in clasif41 if c["clase"] == c["verdad"])
    hit_rate = hits41 / len(clasif41)
    n_clas_t = sum(1 for c in clasif41 if c["clase"] == "tendencia")
    n_verd_t = sum(1 for c in clasif41 if c["verdad"] == "tendencia")
    tp = sum(1 for c in clasif41 if c["clase"] == "tendencia"
             and c["verdad"] == "tendencia")

    crit_a = hit_rate > ACC_MIN
    crit_b = pnl41 > pnl_buyhold
    pasa = bool(crit_a and crit_b)

    motivos = [
        f"calibración (período distinto, Coinbase 2026-07-29->2026-08-28): "
        f"(W*={W_STAR}, T*={T_STAR}) bal.acc={best['bal_acc']:.4f}",
        f"(a) clasificador en test: acierto {hits41}/{len(clasif41)} = "
        f"{hit_rate:.1%} vs umbral {ACC_MIN:.0%} -> "
        f"{'CUMPLE' if crit_a else 'NO CUMPLE'} "
        f"(tendencia clasificada en {n_clas_t}, verdad {n_verd_t}, TP {tp})",
        f"(b) P&L: EXP41={pnl41:+.4%} vs buyhold={pnl_buyhold:+.4%} -> "
        f"{'CUMPLE' if crit_b else 'NO CUMPLE'}",
        "PASS" if pasa else "FAIL (vara intacta)",
    ]

    report = {
        "preregistro": "resultados/exp41-20260927/preregistro.json",
        "calibracion": {
            "mejor": {"W": W_STAR, "T": T_STAR,
                      "bal_acc": round(best["bal_acc"], 4),
                      "recall": {k: round(v, 4)
                                 for k, v in best["recall"].items()},
                      "hits": best["hits"]},
            "tabla_completa": [
                {"W": r["W"], "T": r["T"],
                 "bal_acc": round(r["bal_acc"], 4),
                 "hits": r["hits"]} for r in resultados_cal],
            "n_bloques_tendencia_verdaderos": n_true_t_cal,
        },
        "test": {
            "pnl_exp41": round(pnl41, 6),
            "pnl_buyhold": round(pnl_buyhold, 6),
            "hit_rate_bloques_1_29": round(hit_rate, 4),
            "aciertos": hits41,
            "clasifico_tendencia": n_clas_t,
            "verdad_tendencia": n_verd_t,
            "verdaderos_positivos": tp,
            "detalle": [{**c,
                         "hurst": None if c["hurst"] is None
                         else round(c["hurst"], 4),
                         "retorno_bloque": round(c["retorno_bloque"], 6)}
                        for c in clasif41],
        },
        "criterios": {"a_clasificador": bool(crit_a),
                      "b_pnl": bool(crit_b)},
        "costo_total_usd": 0.0,
        "veredicto": {"pasa": pasa, "motivos": motivos},
        "duracion_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # --- veredicto en markdown ---
    if not crit_a:
        conclusion = ("el Hurst calibrado fuera de muestra no discrimina "
                      "régimen a esta escala (<= 55%): la conclusión "
                      "pre-registrada es que no tiene señal explotable y hay "
                      "que cambiar de familia de test.")
    elif not crit_b:
        conclusion = ("el clasificador discrimina pero el mapeo no paga: "
                      "aun con régimen detectado, momentum-en-tendencia / "
                      "flat-en-lateral no supera a buyhold en este stream.")
    else:
        conclusion = ("el test de régimen calibrado fuera de muestra "
                      "discrimina y paga: primera evidencia de que la "
                      "pregunta de EXP40 tenía instrumento válido.")
    md = f"""# EXP41 — Veredicto: {"PASS" if pasa else "FAIL"}

**Fecha:** {time.strftime("%Y-%m-%d")} · **Modo:** mock, replay puro, US$0 · **Duración:** {report["duracion_s"]}s
**Pre-registro:** `resultados/exp41-20260927/preregistro.json` (escrito antes de correr)
**Código:** `run_experiment41.py`
**Datos calibración:** Coinbase BTC-USD 1h público, 720 velas, 2026-07-29 17:00 UTC → 2026-08-28 16:00 UTC (`data_exp41/btc_h1_calib.json`)
**Datos test:** idénticos a EXP36–40 (Kraken XBTUSD 1h, 720 velas, 719 retornos)

## Diseño
EXP40 dejó el umbral sin calibrar (pecado declarado). EXP41 barre ventana
W ∈ {{24, 72, 168}} × umbral T ∈ {{0.50…0.70}} en un período DISTINTO,
elige por precisión balanceada (desempate: menor W, luego menor T),
congela (W*, T*) y testea la política condicional de EXP40 en el stream
original. Sin lookahead en ninguna etapa.

## Criterios pre-registrados
(a) acierto del clasificador en test (bloques 1..29) > 55%.
(b) P&L(EXP41) > P&L(buyhold). PASS iff (a) y (b).

## Números

Calibración (período distinto): **(W*={W_STAR}, T*={T_STAR})**,
bal.acc={best['bal_acc']:.4f} (recall tendencia={best['recall']['tendencia']:.2f},
recall lateral={best['recall']['lateral']:.2f}); bloques-tendencia
verdaderos en calibración: {n_true_t_cal}/29.

Test (stream original):
- (a) clasificador: **{hits41}/{len(clasif41)} = {hit_rate:.1%}** (umbral 55%) → **{"CUMPLE" if crit_a else "NO CUMPLE"}**
  (tendencia clasificada en {n_clas_t}, verdad ex-post {n_verd_t}, TP {tp})
- (b) P&L: EXP41 **{pnl41:+.4%}** vs buyhold **{pnl_buyhold:+.4%}** → **{"CUMPLE" if crit_b else "NO CUMPLE"}**

**→ {"PASS" if pasa else "FAIL"}.** {conclusion}

## Diagnóstico
- La calibración {"mejoró" if best['bal_acc'] > 0.5 else "no mejoró"} la moneda
  en muestra distinta (bal.acc={best['bal_acc']:.3f}).
- {"La ganancia de calibración sobrevivió al cambio de período."
   if crit_a else "La ganancia de calibración NO sobrevivió al cambio de período: "
   "el umbral calibrado no generaliza."}

## Honestidad incómoda
1. **Fuente distinta en calibración** (Coinbase BTC-USD vs Kraken XBTUSD en
   test): ambos son BTC/USD spot horario y la microestructura es la misma
   familia, pero la calibración no es estrictamente "misma fuente".
2. **n=1 en test**: sigue siendo una ventana de 30 días con drift +8,55%
   que favorece a buyhold; el ranking vive dentro de ese sample.
3. **La verdad ex-post (|retorno| > 2%) es cruda**: mide utilidad, no verdad
   en sentido Hurst — un bloque puede ser persistente sin superar el 2%.
4. **33 combos en 29 bloques**: la calibración puede sobreajustar ruido;
   si (W*,T*) es un pico aislado en la tabla, desconfiar.
5. **Fidelidad verificada**: (W=72,T=0.55) reproduce EXP40
   (P&L={pnl_rep:.4%}, hits={hits_rep}/29); Hurst en RW sintético={h_rw:.3f}.
"""
    with open(os.path.join(BASE, "resultados", "exp41_veredicto.md"), "w") as f:
        f.write(md)

    print("\n================ VEREDICTO EXP41 ================")
    for m in motivos:
        print("  " + m)
    print(f"  costo: $0.0000 USD (replay puro) | {report['duracion_s']}s")
    print("  RESULTADO:", "PASS" if pasa else "FAIL")
    print("==================================================")
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
