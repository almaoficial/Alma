#!/usr/bin/env python3
"""ALMA-EXP68 — detector de heterogeneidad (mock, US$0, sin API keys).

Valida a dos puntas el DetectorHeterogeneidad de
alma_service/heterogeneidad.py:

  Mundo A (homogéneo, estilo EXP62): un solo brazo dominante en todo
    el stream. El detector debería enganchar y ahorrar exploración.
  Mundo B (heterogéneo, estilo EXP5): tres regímenes con ganadores
    distintos que rotan. El detector NO debería enganchar (K=4 >
    racha máxima determinista de 3 del stream congelado).

Runner: copia fiel de exp56_rso/run_experiment56.py::correr_replica_param
(mismo namespace RNG "exp45-...", mismos draws por celda) + hooks del
detector. Con detector=None el runner debe reproducir al baseline
bit-idéntico (test diferencial contra e56 en modo --sanity).

Modos:
  --sanity    test diferencial: runner(detector=None) vs e56 en el
              mundo default (stream e47 + tasas default), reps 0-4.
  --calibrar  réplicas de calibración 10-14 (nunca las de validación):
              diagnósticos de enganche/flaps + deltas por mundo.
  (sin flag)  validación pre-registrada: 5 réplicas pareadas (0-4) por
              mundo, escribe report.json en el dir de resultados.

Criterio (pre-registrado, estilo puerta de dos splits, como
alma_service/gate.py): sobre medias puntuales pareadas,
  PASS  <=>  media(Δ_B) >= 0  y  media(Δ_A) > 0,
donde Δ = regret(baseline) - regret(detector) por réplica pareada.
Se reportan además IC95 por mundo (t, df=4).
"""
import sys
import os
import json
import math
import random

BASE68 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/home/hatch/workspace/alma-prototype/exp56_rso")
sys.path.insert(0, "/home/hatch/workspace/alma-prototype")
import run_experiment47 as e47
import run_experiment56 as e56
from alma_service.heterogeneidad import (
    DetectorHeterogeneidad, ganador_estricto, EXPLORAR, ENCOGIDO)
from alma_service.scaffold import DEFAULT_SCAFFOLD

K_DET = 3   # pre-registrado (ver preregistro.md)
J_DET = 3   # pre-registrado (ver preregistro.md)
BRAZOS = ["titular", "contexto", "estable"]
REPS_VALID = list(range(5))
REPS_CALIB = list(range(10, 15))


# ---------------------------------------------------------------- mundos
def construir_mundo_A():
    """Homogéneo estilo EXP62: un brazo domina todo el stream.

    Firmas de bloque únicas por bloque => la skill/skip del scaffold
    queda dormida (sin recurrencias) y el detector es el único
    mecanismo de explotación. El brazo 'mayoria' se excluye en ambos
    mundos (en categoría única sería un brazo perfecto: degenera el
    experimento). Mismo recorte en baseline y tratamiento.
    """
    items = []
    for b in range(24):
        for q in range(10):
            items.append({
                "id": f"exp68A-b{b:02d}-q{q}",
                "category": "tarea",
                "grupo": f"bloque_{b:02d}",   # firma única por bloque
                "regimen": f"bloque_{b:02d}",
            })
    tasas = {
        "brazos": BRAZOS,
        "por_categoria": {
            "tarea": {"titular": 0.50, "contexto": 0.75, "estable": 0.50}},
        "por_defecto": {"titular": 0.50, "contexto": 0.75, "estable": 0.50},
    }
    return items, tasas


def construir_mundo_B():
    """Heterogéneo estilo EXP5: stream e47 estándar, ganador por régimen.

    tech -> titular, dinero -> contexto, deportes -> estable (0.75 vs
    0.50). El skip del scaffold opera normal (hay recurrencias).
    """
    items = e47.construir_stream()
    por_cat = {}
    ganadores = {"tech": "titular", "dinero": "contexto",
                 "deportes": "estable"}
    for grupo, win in ganadores.items():
        for cat in e47.GRUPOS[grupo]:
            por_cat[cat] = {a: (0.75 if a == win else 0.50)
                            for a in BRAZOS}
    tasas = {"brazos": BRAZOS, "por_categoria": por_cat,
             "por_defecto": {a: 0.50 for a in BRAZOS}}
    return items, tasas


# ---------------------------------------------------------------- runner
def correr_replica_exp68(rep_id, items, tasas, sc, detector=None,
                          modo_veredicto="fav"):
    """Copia fiel de e56.correr_replica_param + hooks del detector EXP68.

    Los hooks están marcados con '# --- hook EXP68 ---'. Todo lo demás
    es verbatim (mismo namespace RNG "exp45-...", mismos draws por
    celda): con detector=None reproduce al baseline bit-idéntico.

    modo_veredicto (solo calibración): cómo se computa el veredicto
    del bloque para el detector.
      "fav"             = brazo comprometido (skill_arm si skip, fav si probe)
      "probe"           = argmax estricto de las medias del probe (Q1+Q2)
      "probe_decisivo"  = como "probe" pero solo si el margen >= 1 item
                          (de 5); si no, veredicto None (reinicia racha)
    En modo ENCOGIDO el bloque juega el brazo comprometido en los 10
    items (réplica exacta del camino de skip); cada J bloques encogidos
    el bloque es spot-check: los 3 primeros items miden a todos los
    brazos (aciertos enteros -> resolver_spot_check con margen).
    """
    H = len(items)
    brazos = tasas["brazos"]
    n_bloques = H // e47.BLOQUE
    rep_hist = {a: [] for a in brazos}
    block_sig = {}
    probe_obs = {}
    rew_pol = [0.0] * H
    rew_fija = {a: [0.0] * H for a in brazos}
    reg_pol_bloques = []
    ub, ud, gm, n0, decay = (sc["umbral_base"], sc["umbral_divisor"],
                             sc["gate_margin"], sc["n0"], sc["decay"])
    for b in range(n_bloques):
        base = b * e47.BLOQUE
        sig = e47.firma_grupo([items[base + q]["grupo"]
                               for q in e47.PROBE_Q1])
        block_sig[b] = sig
        saltar = False
        skill_arm = None
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            skill_arm = e47.skill_arm_actual(brazos, rep_hist, block_sig,
                                             b, sig)
            fuerte, _, _, _ = e56.soporte_param(
                brazos, probe_obs, block_sig, b, sig, skill_arm, ub, ud)
            saltar = fuerte
        clf = e47.MockClasificador(tasas)
        for hh in range(base):
            clf.registrar(items[hh])

        # --- hook EXP68: modo encogido (réplica del camino de skip) ---
        if detector is not None and detector.modo == ENCOGIDO:
            w = detector.comprometido
            es_spot = detector.iniciar_bloque_encogido()
            aciertos = {a: 0 for a in brazos} if es_spot else None
            for q in range(e47.BLOQUE):
                h = base + q
                it = items[h]
                rs = {a: clf.acierto(
                    a, it,
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                    for a in brazos}
                for a in brazos:
                    rew_fija[a][h] = rs[a]
                r = rs[w]
                rep_hist[w].append((h, r, b))
                rew_pol[h] = r
                clf.registrar(it)
                if es_spot and q in e47.PROBE_Q1:
                    for a in brazos:
                        aciertos[a] += rs[a]
            if es_spot:
                detector.resolver_spot_check(b, aciertos)
            probe_obs[b] = None
            reg_pol_bloques.append(
                e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))
            continue

        if saltar:
            # PROBE SALTADO: idéntico a EXP51.
            probe_obs[b] = None
            for q in range(e47.BLOQUE):
                h = base + q
                it = items[h]
                rs = {a: clf.acierto(
                    a, it,
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                    for a in brazos}
                for a in brazos:
                    rew_fija[a][h] = rs[a]
                r = rs[skill_arm]
                rep_hist[skill_arm].append((h, r, b))
                rew_pol[h] = r
                clf.registrar(it)
            reg_pol_bloques.append(
                e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))
            # --- hook EXP68: veredicto (skip: sin probe salvo modo fav) ---
            if detector is not None:
                v = skill_arm if modo_veredicto == "fav" else None
                detector.registrar_veredicto(b, v)
            continue

        # --- Camino con probe: idéntico a EXP51 ---
        bandit = e56.nuevo_bandit_param(
            brazos, e56.prior_params_param(brazos, rep_hist, block_sig, b,
                                           None, n0, decay), n0)
        prior_means = {a: bandit.mean(a) for a in brazos}
        fav = max(brazos, key=lambda a: prior_means[a])

        def medir(q):
            h = base + q
            it = items[h]
            rs = {a: clf.acierto(
                a, it, random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                for a in brazos}
            for a in brazos:
                bandit.update(a, rs[a])
                rep_hist[a].append((h, rs[a], b))
                rew_fija[a][h] = rs[a]
            clf.registrar(it)
            return rs

        # PROBE Q1: bit-idéntico al control (mismos sorteos, scoring ciego).
        rs_q1 = {}
        for q in e47.PROBE_Q1:
            h = base + q
            rs_q1[q] = medir(q)
            rew_pol[h] = rs_q1[q][fav]

        usa_skill = False
        if e47.skill_existe(rep_hist, block_sig, b, sig):
            usa_skill = True
            bandit = e56.nuevo_bandit_param(
                brazos, e56.prior_params_param(brazos, rep_hist, block_sig,
                                               b, sig, n0, decay), n0)
            for q in e47.PROBE_Q1:
                for a in brazos:
                    bandit.update(a, rs_q1[q][a])

        # Gate adaptativo (parametrizado por el margen).
        gate = (skill_arm is not None and usa_skill and
                e56.q1_decisivo_param(brazos, rs_q1, skill_arm, gm))

        def thompson(qs):
            for q in qs:
                h = base + q
                it = items[h]
                a_sel = bandit.select(
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-sel"))
                r_sel = clf.acierto(
                    a_sel, it,
                    random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a_sel}"))
                bandit.update(a_sel, r_sel)
                rep_hist[a_sel].append((h, r_sel, b))
                rew_pol[h] = r_sel
                for a in brazos:
                    rew_fija[a][h] = clf.acierto(
                        a, it,
                        random.Random(f"exp45-r{rep_id}-b{b}-q{q}-{a}"))
                clf.registrar(it)

        thompson(tuple(q for q in e47.THOMPSON_Q if q < e47.PROBE_Q2[0]))
        if gate:
            # Q2 SALTADO: items 6,7 como jugadas de Thompson.
            thompson(e47.PROBE_Q2)
        else:
            # RE-PROBE Q2: scoring honesto con fav ciego.
            rs_q2 = {}
            for q in e47.PROBE_Q2:
                h = base + q
                rs_q2[q] = medir(q)
                rew_pol[h] = rs_q2[q][fav]
        thompson(tuple(q for q in e47.THOMPSON_Q if q > e47.PROBE_Q2[-1]))

        if gate:
            probe_obs[b] = {a: [rs_q1[q][a] for q in e47.PROBE_Q1]
                            for a in brazos}
        else:
            probe_obs[b] = {a: [rs_q1[q][a] for q in e47.PROBE_Q1] +
                               [rs_q2[q][a] for q in e47.PROBE_Q2]
                            for a in brazos}
        reg_pol_bloques.append(
            e47.BLOQUE - sum(rew_pol[base:base + e47.BLOQUE]))
        # --- hook EXP68: veredicto del bloque ---
        if detector is not None:
            if modo_veredicto == "fav":
                veredicto = fav
            else:
                qp = [(q, rs_q1) for q in e47.PROBE_Q1]
                if not gate:
                    qp += [(q, rs_q2) for q in e47.PROBE_Q2]
                pm = {a: sum(d[q][a] for q, d in qp) / len(qp)
                      for a in brazos}
                veredicto = ganador_estricto(pm)
                if (modo_veredicto == "probe_decisivo"
                        and veredicto is not None):
                    orden = sorted(pm.values(), reverse=True)
                    # margen >= 1 item del probe; si no, no hay veredicto
                    if (orden[0] - orden[1]) * len(qp) < 1 - 1e-9:
                        veredicto = None
            detector.registrar_veredicto(b, veredicto)

    reg_pol = H - sum(rew_pol)
    reg_fijas = {a: H - sum(rew_fija[a]) for a in brazos}
    mejor = min(brazos, key=lambda a: reg_fijas[a])
    return {"reg_pol": reg_pol, "reg_pol_bloques": reg_pol_bloques,
            "reg_fijas": reg_fijas, "mejor_fija": mejor,
            "reg_mejor_fija": reg_fijas[mejor], "n": H}


# ---------------------------------------------------------------- modos
def sanity():
    """Test diferencial: runner(detector=None) vs e56 en mundo default."""
    print("== sanity: runner(detector=None) vs e56.correr_replica_param ==")
    items = e47.construir_stream()
    tasas = json.load(open(
        "/home/hatch/workspace/alma-prototype/data_exp44/tasas.json"))
    sc = dict(DEFAULT_SCAFFOLD)
    ok = True
    for rep in range(5):
        ref = e56.correr_replica_param(rep, items, tasas, sc)
        mio = correr_replica_exp68(rep, items, tasas, sc, detector=None)
        same = (ref["reg_pol"] == mio["reg_pol"]
                and ref["reg_fijas"] == mio["reg_fijas"])
        print(f"  rep {rep}: e56={ref['reg_pol']:.4f} "
              f"mio={mio['reg_pol']:.4f} {'BIT-IDENTICO' if same else 'DIFIERE'}")
        ok = ok and same
    print("SANITY " + ("OK" if ok else "FALLA"))
    return ok


def _resumen_detector(det):
    ev = [e for e in det.historial
          if e.get("evento") in ("encoge", "restaura")]
    return {"enganches": [e["bloque"] for e in ev
                          if e["evento"] == "encoge"],
            "restauraciones": [e["bloque"] for e in ev
                               if e["evento"] == "restaura"],
            "modo_final": det.modo,
            "comprometido_final": det.comprometido}


def _t_ci95(xs):
    n = len(xs)
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else 0.0
    # t_{0.975, df=4} = 2.776
    h = 2.776 * sd / math.sqrt(n) if n > 1 else 0.0
    return m, m - h, m + h, sd


def correr_mundo(nombre, items, tasas, sc, reps, calibrar=False,
                 modo_veredicto="fav", K=K_DET, J=J_DET):
    print(f"-- mundo {nombre} (reps {reps[0]}-{reps[-1]}) "
          f"[veredicto={modo_veredicto} K={K} J={J}] --")
    base_regs, trat_regs, deltas, diags = [], [], [], []
    for rep in reps:
        base = correr_replica_exp68(rep, items, tasas, sc, detector=None,
                                    modo_veredicto=modo_veredicto)
        det = DetectorHeterogeneidad(K=K, J=J)
        trat = correr_replica_exp68(rep, items, tasas, sc, detector=det,
                                    modo_veredicto=modo_veredicto)
        d = base["reg_pol"] - trat["reg_pol"]
        base_regs.append(base["reg_pol"])
        trat_regs.append(trat["reg_pol"])
        deltas.append(d)
        diags.append(_resumen_detector(det))
        if calibrar:
            dg = diags[-1]
            print(f"  rep {rep}: base={base['reg_pol']:.2f} "
                  f"trat={trat['reg_pol']:.2f} Δ={d:+.2f} "
                  f"engage={dg['enganches']} restore={dg['restauraciones']} "
                  f"final={dg['modo_final']}")
    m, lo, hi, sd = _t_ci95(deltas)
    print(f"  Δ medio={m:+.2f} IC95=[{lo:+.2f},{hi:+.2f}] sd={sd:.2f}")
    return {"base_regs": base_regs, "trat_regs": trat_regs,
            "deltas": deltas, "delta_medio": m, "ic95": [lo, hi],
            "sd": sd, "diagnosticos": diags}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--sanity":
        sys.exit(0 if sanity() else 1)
    calibrar = len(sys.argv) > 1 and sys.argv[1] == "--calibrar"
    if not sanity():
        print("ABORTO: sanity falló")
        sys.exit(1)
    sc = dict(DEFAULT_SCAFFOLD)
    print(f"scaffold: {sc}  K={K_DET} J={J_DET}")
    itemsA, tasasA = construir_mundo_A()
    itemsB, tasasB = construir_mundo_B()
    reps = REPS_CALIB if calibrar else REPS_VALID
    if calibrar:
        for mv, K in [("probe", 3), ("probe", 4),
                      ("probe_decisivo", 3), ("probe_decisivo", 4)]:
            rA = correr_mundo("A (homogéneo)", itemsA, tasasA, sc, reps,
                              calibrar=True, modo_veredicto=mv, K=K)
            rB = correr_mundo("B (heterogéneo)", itemsB, tasasB, sc, reps,
                              calibrar=True, modo_veredicto=mv, K=K)
        return
    rA = correr_mundo("A (homogéneo)", itemsA, tasasA, sc, reps,
                      modo_veredicto="probe", K=K_DET, J=J_DET)
    rB = correr_mundo("B (heterogéneo)", itemsB, tasasB, sc, reps,
                      modo_veredicto="probe", K=K_DET, J=J_DET)
    if calibrar:
        return
    pasa = (rB["delta_medio"] >= 0) and (rA["delta_medio"] > 0)
    reporte = {
        "experimento": "EXP68",
        "descripcion": "detector de heterogeneidad: validación a dos puntas",
        "K": K_DET, "J": J_DET,
        "modo_veredicto": "probe",
        "scaffold": sc,
        "replicas": REPS_VALID,
        "criterio": "PASS <=> media(Δ_B) >= 0 y media(Δ_A) > 0, "
                    "Δ = regret(baseline) - regret(detector) pareado",
        "mundo_A": rA, "mundo_B": rB,
        "veredicto": "PASS" if pasa else "FAIL",
    }
    outdir = BASE68  # el script ya vive en el dir de resultados
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "report.json"), "w") as f:
        json.dump(reporte, f, indent=2)
    print(f"\nreport.json -> {outdir}")
    print(f"Δ_A medio = {rA['delta_medio']:+.2f} IC95 [{rA['ic95'][0]:+.2f},"
          f"{rA['ic95'][1]:+.2f}]")
    print(f"Δ_B medio = {rB['delta_medio']:+.2f} IC95 [{rB['ic95'][0]:+.2f},"
          f"{rB['ic95'][1]:+.2f}]")
    print("VEREDICTO:", reporte["veredicto"])


if __name__ == "__main__":
    main()
