#!/usr/bin/env python3
"""ALMA-EXP61: techo del proveedor generativo ("skills como priors").

Rediseño post-fase-1: la skill deja de ser prosa inyectada al prompt (fase 1
FAIL: diferencia conductual 0.000) y pasa a ser PARAMETROS del prior por firma
que el resolver consume numericamente. Este mock mide el TECHO de esa via:
un proveedor oraculo con abstraccion perfecta (medias verdaderas por grupo)
vs el scaffold global fijo evolucionado (SC_EVO).

Un solo moving part: el prior condicionado a la firma. Todo lo demas es
e56.correr_replica_param verbatim via monkey-patch de un unico call site
(e56.prior_params_param). Con oraculo_on=False el wrapper delega siempre ->
bit-identico al control por construccion (chequeo pre-registrado).

Criterio pre-registrado: PASS ssi efecto < -1.0 (vara exigente: el oraculo
es el techo; un LLM real capturaria solo una fraccion).
"""

import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # alma-prototype/
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "exp56_rso"))
sys.path.insert(0, HERE)
import run_experiment47 as e47  # noqa: E402
import run_experiment56 as e56  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "exp61_oraculo")

SC_EVO = {"umbral_base": 1, "umbral_divisor": 3, "gate_margin": 0.0,
          "n0": 4, "decay": 0.5}
REPS = [0, 1, 2, 3, 4]

_ORIGINAL_PRIOR = e56.prior_params_param
_ORIGINAL_SKILL_EXISTE = e47.skill_existe

ORACULO_ON = True
MEDIAS_ORACULO = {}   # (grupo, brazo) -> media verdadera
SKILL_CALLS = []      # (rep_id, bloque, sig, existe) -- diagnostico


def construir_medias_oraculo(items, tasas):
    """Medias verdaderas por grupo (techo informativo, pre-registrado).

    m_a(g) = suma ponderada por frecuencia de tasa(a, cat) sobre las
    categorias del grupo g. Para 'mayoria' (sin tasa en el oraculo):
    aproximacion pre-registrada con la moda global de categorias del stream.
    """
    brazos = tasas["brazos"]
    per_cat = tasas["por_categoria"]
    por_defecto = tasas["por_defecto"]
    freq = Counter((it["category"] or "").strip().lower() for it in items)
    moda = Counter(it["category"] for it in items).most_common(1)[0][0]

    def tasa(a, cat):
        if a == "mayoria":
            return None
        return per_cat.get(cat, {}).get(a, por_defecto[a])

    medias = {}
    for g, cats in e47.GRUPOS.items():
        sw = sum(freq[c] for c in cats)
        assert sw > 0, f"grupo sin frecuencia: {g}"
        for a in brazos:
            if a == "mayoria":
                m = sum(freq[c] / sw * (1.0 if c == moda else 0.0)
                        for c in cats)
            else:
                m = sum(freq[c] / sw * tasa(a, c) for c in cats)
            medias[(g, a)] = m
    return medias


def prior_oraculo(brazos, rep_hist, block_sig, b, sig, n0, decay):
    """Wrapper pre-registrado: solo el prior condicionado a la firma usa el
    oraculo. El prior no condicionado (sig=None, fav) delega al original."""
    if not ORACULO_ON or sig is None:
        return _ORIGINAL_PRIOR(brazos, rep_hist, block_sig, b, sig,
                               n0, decay)
    params = {}
    for a in brazos:
        m = MEDIAS_ORACULO.get((sig, a))
        if m is None:  # no deberia ocurrir; fallback honesto
            return _ORIGINAL_PRIOR(brazos, rep_hist, block_sig, b, sig,
                                   n0, decay)
        params[a] = (1.0 + n0 * m, 1.0 + n0 * (1.0 - m))
    return params


def skill_existe_count(rep_hist, block_sig, b, sig):
    r = _ORIGINAL_SKILL_EXISTE(rep_hist, block_sig, b, sig)
    # se llama 2x por bloque en camino con probe; 1x si se salta.
    # Guardamos todas; el diagnostico usa la primera por bloque.
    SKILL_CALLS.append((b, sig, bool(r)))
    return r


def correr_replica_oraculo(rep_id, items, tasas, sc, oraculo_on=True):
    global ORACULO_ON
    ORACULO_ON = oraculo_on
    e56.prior_params_param = prior_oraculo
    e47.skill_existe = skill_existe_count
    try:
        return e56.correr_replica_param(rep_id, items, tasas, sc)
    finally:
        e56.prior_params_param = _ORIGINAL_PRIOR
        e47.skill_existe = _ORIGINAL_SKILL_EXISTE


def main():
    items = e47.construir_stream()
    tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
    global MEDIAS_ORACULO
    MEDIAS_ORACULO = construir_medias_oraculo(items, tasas)

    # --- Chequeo 1 (pre-registrado): bit-identidad con modulo off ---
    for r in REPS:
        ref = e56.correr_replica_param(r, items, tasas, dict(SC_EVO))
        got = correr_replica_oraculo(r, items, tasas, dict(SC_EVO),
                                     oraculo_on=False)
        assert got["reg_pol"] == ref["reg_pol"], (
            f"bit-identidad rota en rep {r}: {got['reg_pol']} vs "
            f"{ref['reg_pol']}")
        assert got["reg_pol_bloques"] == ref["reg_pol_bloques"], (
            f"bit-identidad (bloques) rota en rep {r}")
    print("chequeo bit-identidad: OK 5/5")

    # --- Chequeo 2 (pre-registrado): magnitudes del control ---
    ctrl_regs = [e56.correr_replica_param(r, items, tasas, dict(SC_EVO))
                 for r in REPS]
    for r, c in zip(REPS, ctrl_regs):
        assert 70 <= c["reg_pol"] <= 95, (
            f"magnitud fuera de rango en rep {r}: {c['reg_pol']}")
    print("chequeo magnitudes: OK",
          [round(c["reg_pol"], 2) for c in ctrl_regs])

    # --- Corrida principal: pareada ---
    efectos = []
    por_rep = []
    d_trat, d_ctrl = [], []
    for r, c in zip(REPS, ctrl_regs):
        SKILL_CALLS.clear()
        t = correr_replica_oraculo(r, items, tasas, dict(SC_EVO),
                                   oraculo_on=True)
        ef = t["reg_pol"] - c["reg_pol"]
        efectos.append(ef)
        # diagnostico: bloques 0-11 vs 12-23
        tb, cb = t["reg_pol_bloques"], c["reg_pol_bloques"]
        early = sum(tb[:12]) - sum(cb[:12])
        late = sum(tb[12:]) - sum(cb[12:])
        # diagnostico: bloques con skill disponible (1er call por bloque)
        vistos = set()
        n_skill = 0
        for (b, sig, ex) in SKILL_CALLS:
            if b not in vistos:
                vistos.add(b)
                n_skill += ex
        por_rep.append({
            "rep": r,
            "reg_ctrl": round(c["reg_pol"], 2),
            "reg_trat": round(t["reg_pol"], 2),
            "efecto": round(ef, 2),
            "efecto_early_0_11": round(early, 2),
            "efecto_late_12_23": round(late, 2),
            "bloques_con_skill": n_skill,
            "mejor_fija": c["mejor_fija"],
            "reg_mejor_fija": round(c["reg_mejor_fija"], 2),
        })
        d_trat.append(t["reg_pol"] - t["reg_mejor_fija"])
        d_ctrl.append(c["reg_pol"] - c["reg_mejor_fija"])

    efecto = sum(efectos) / len(efectos)
    veredicto = "PASS" if efecto < -1.0 else "FAIL"
    report = {
        "experimento": "EXP61",
        "descripcion": "techo del proveedor generativo (skills como priors)",
        "modo": "mock US$0",
        "criterio_pre_registrado": "PASS ssi efecto < -1.0",
        "efecto_medio": round(efecto, 2),
        "efectos_por_replica": [round(e, 2) for e in efectos],
        "veredicto": veredicto,
        "distancia_mejor_fija_trat": round(sum(d_trat) / len(d_trat), 2),
        "distancia_mejor_fija_ctrl": round(sum(d_ctrl) / len(d_ctrl), 2),
        "por_replica": por_rep,
        "scaffold_control": SC_EVO,
        "n_replicas": len(REPS),
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: report[k] for k in
                      ("efecto_medio", "veredicto",
                       "distancia_mejor_fija_trat",
                       "distancia_mejor_fija_ctrl")},
                     indent=2))


if __name__ == "__main__":
    main()
