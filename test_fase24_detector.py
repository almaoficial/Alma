"""Tests fase 2.4: detector de heterogeneidad (EXP68) en MotorFase1.

Sin key ni red: BackendFalso con mundo homogéneo determinista
("aritmetica" → single gana siempre) para disparar el detector.

Correr: python3 test_fase24_detector.py
"""

import os
import random
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from servicio.motor_fase1 import MotorFase1, BLOQUE
from test_fase1_motor import BackendFalso
from alma_service.heterogeneidad import (
    DetectorHeterogeneidad, ENCOGIDO, EXPLORAR, K_EXP68, J_EXP68,
)
from alma_service.trazas import EventLog

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def problemas_homogeneos(n_bloques, seed=11):
    """Mundo homogéneo: todo 'aritmetica' → el probe mide single=1.0,
    resto 0.0 → veredicto unánime 'single' bloque tras bloque."""
    rng = random.Random(seed)
    ps = []
    for b in range(n_bloques):
        for q in range(BLOQUE):
            a, c = rng.randint(101, 999), rng.randint(101, 999)
            ps.append({"id": f"h-b{b}-q{q}",
                       "enunciado": f"¿Cuánto es {a} + {c}?",
                       "firma": "aritmetica",
                       "esperado": str(a + c)})
    return ps


def test_deshabilitado_es_identico():
    """Con el detector apagado (o sin disparar), el comportamiento es
    bit-idéntico al vigente: la integración es aditiva."""
    from problemas_fase1 import generar_problemas
    probs = generar_problemas(seed=7, n_bloques=2)
    tmp1, tmp2 = tempfile.mkdtemp(), tempfile.mkdtemp()
    m_off = MotorFase1(os.path.join(tmp1, "m"),
                       backend=BackendFalso(probs), budget_usd=1.0,
                       usar_skills=False, seed=0,
                       detector_heterogeneidad=False)
    m_on = MotorFase1(os.path.join(tmp2, "m"),
                      backend=BackendFalso(probs), budget_usd=1.0,
                      usar_skills=False, seed=0,
                      detector_heterogeneidad=True)
    for b in range(2):
        m_off.correr_bloque(b, probs[b * BLOQUE:(b + 1) * BLOQUE])
        m_on.correr_bloque(b, probs[b * BLOQUE:(b + 1) * BLOQUE])
    r_off = [t["regret_bloque"] for t in m_off.bloques]
    r_on = [t["regret_bloque"] for t in m_on.bloques]
    check("sin disparo: regret idéntico con/sin detector", r_off == r_on)
    check("sin disparo: costo idéntico con/sin detector",
          m_off.estado()["costo_usd"] == m_on.estado()["costo_usd"])
    check("sin disparo: el detector sigue explorando",
          m_on.detector_het.modo == EXPLORAR)
    m_off.cerrar()
    m_on.cerrar()


def test_encoge_tras_k_unanimes():
    """K=3 bloques con veredicto unánime 'single' → ENCOGIDO; el bloque
    siguiente juega el brazo comprometido en los 6 ítems."""
    tmp = tempfile.mkdtemp()
    probs = problemas_homogeneos(4)
    m = MotorFase1(os.path.join(tmp, "m"), backend=BackendFalso(probs),
                   budget_usd=1.0, usar_skills=False, seed=0)
    jugadas = []  # (b, q, brazo, fase)
    orig_medir = m._medir

    def espiar(brazo, problema, b, q, fase, sig,
               skill_arm=None, skill_obj=None):
        jugadas.append((b, q, brazo, fase))
        return orig_medir(brazo, problema, b, q, fase, sig,
                          skill_arm=skill_arm, skill_obj=skill_obj)
    m._medir = espiar
    for b in range(4):
        m.correr_bloque(b, probs[b * BLOQUE:(b + 1) * BLOQUE])
    det = m.detector_het
    check("K/J congelados del pre-registro",
          (det.K, det.J) == (K_EXP68, J_EXP68) == (3, 3))
    check("engancha tras K bloques unánimes", det.modo == ENCOGIDO)
    check("compromete el brazo unánime", det.comprometido == "single")
    tel3 = m.bloques[3]
    check("bloque 3 corre encogido", tel3.get("encogido") is True)
    check("bloque 3 sin spot (1er encogido)",
          tel3.get("spot_check") is False)
    jug_b3 = [(q, a, f) for (b, q, a, f) in jugadas if b == 3]
    check("bloque 3: los 6 ítems con el comprometido",
          len(jug_b3) == 6 and {a for _, a, _ in jug_b3} == {"single"})
    check("bloque 3: sin probe ni thompson",
          {f for _, _, f in jug_b3} == {"encogido"})
    m.cerrar()


def test_spot_check():
    """Cada J=3 bloques encogidos hay spot-check: Q1+Q2 miden todos los
    brazos y se banca al comprometido."""
    tmp = tempfile.mkdtemp()
    probs = problemas_homogeneos(6)
    m = MotorFase1(os.path.join(tmp, "m"), backend=BackendFalso(probs),
                   budget_usd=1.0, usar_skills=False, seed=0)
    jugadas = []
    orig_medir = m._medir

    def espiar(brazo, problema, b, q, fase, sig,
               skill_arm=None, skill_obj=None):
        jugadas.append((b, q, brazo, fase))
        return orig_medir(brazo, problema, b, q, fase, sig,
                          skill_arm=skill_arm, skill_obj=skill_obj)
    m._medir = espiar
    for b in range(6):
        m.correr_bloque(b, probs[b * BLOQUE:(b + 1) * BLOQUE])
    # Bloques 3,4,5 encogidos → el 3ro (b=5) toca spot-check.
    tel5 = m.bloques[5]
    check("bloque 5 es spot-check", tel5.get("spot_check") is True)
    por_q = {}
    for (b, q, a, f) in jugadas:
        if b == 5:
            por_q.setdefault(q, set()).add(a)
    check("spot-check: Q1+Q2 miden los 3 brazos",
          all(por_q[q] == {"single", "cot", "reflexion"}
              for q in (0, 1, 3)))
    check("spot-check: el resto solo el comprometido",
          all(por_q[q] == {"single"} for q in (2, 4, 5)))
    check("sin falsa salida: sigue encogido",
          m.detector_het.modo == ENCOGIDO)
    m.cerrar()


def test_skip_no_alimenta():
    """Bloque saltado: no extiende ni reinicia la racha del detector."""
    tmp = tempfile.mkdtemp()
    probs = problemas_homogeneos(4)
    m = MotorFase1(os.path.join(tmp, "m"), backend=BackendFalso(probs),
                   budget_usd=1.0, usar_skills=False, seed=0)
    det = m.detector_het
    for b in range(2):  # 2 veredictos unánimes → racha ('single', 2)
        m.correr_bloque(b, probs[b * BLOQUE:(b + 1) * BLOQUE])
    check("racha en 2 tras dos probes", det.racha == ("single", 2))
    # Bloque 2: skip forzado (decidir_salto mockeado).
    with patch.object(
            m.resolver, "decidir_salto",
            return_value={"saltar": True, "skill_arm": "single",
                          "wins": 5, "K": 5, "umbral": 1}):
        m.correr_bloque(2, probs[2 * BLOQUE:3 * BLOQUE])
    check("skip no extiende ni reinicia la racha",
          det.racha == ("single", 2))
    check("tras el skip sigue explorando", det.modo == EXPLORAR)
    m.correr_bloque(3, probs[3 * BLOQUE:4 * BLOQUE])  # 3er unánime
    check("la racha continúa y engancha", det.modo == ENCOGIDO)
    m.cerrar()


def test_empate_reinicia():
    """Empate en el probe (sin ganador estricto) reinicia la racha."""
    tmp = tempfile.mkdtemp()
    probs = problemas_homogeneos(1)
    m = MotorFase1(os.path.join(tmp, "m"), backend=BackendFalso(probs),
                   budget_usd=1.0, usar_skills=False, seed=0)
    det = m.detector_het
    win = {q: {"single": 1.0, "cot": 0.0, "reflexion": 0.0}
           for q in (0, 1)}
    tie = {q: {"single": 1.0, "cot": 1.0, "reflexion": 0.0}
           for q in (0, 1)}
    m._alimentar_detector(0, det, win, None)
    m._alimentar_detector(1, det, win, None)
    check("dos unánimes → racha 2", det.racha == ("single", 2))
    m._alimentar_detector(2, det, tie, None)
    check("empate → racha reiniciada", det.racha == (None, 0))
    check("empate no engancha", det.modo == EXPLORAR)
    m.cerrar()


def test_fail_safe():
    """Si el detector falla, se desactiva y el bloque corre por el
    camino vigente: el servicio nunca se rompe."""
    tmp = tempfile.mkdtemp()
    probs = problemas_homogeneos(2)
    m = MotorFase1(os.path.join(tmp, "m"), backend=BackendFalso(probs),
                   budget_usd=1.0, usar_skills=False, seed=0)
    det = m.detector_het
    det.modo = ENCOGIDO  # forzar la rama encogida...

    def _roto(_b):
        raise RuntimeError("detector roto")
    det.iniciar_bloque_encogido = _roto  # ...que falla al arrancar
    tel = m.correr_bloque(0, probs[0:BLOQUE])
    check("bloque completo pese al detector roto",
          tel["bloque"] == 0 and "regret_bloque" in tel)
    check("detector desactivado para la sesión",
          m.detector_het is None and m._detector_roto is True)
    check("sin marca de encogido", tel.get("encogido") is not True)
    # El camino vigente sigue funcionando en el bloque siguiente.
    tel1 = m.correr_bloque(1, probs[BLOQUE:2 * BLOQUE])
    check("bloque siguiente normal", tel1.get("encogido") is not True)
    m.cerrar()


def test_trazas():
    """Las transiciones del detector van al event log 2.2."""
    tmp = tempfile.mkdtemp()
    probs = problemas_homogeneos(4)
    log = EventLog(db_path=os.path.join(tmp, "eventos.db"))
    m = MotorFase1(os.path.join(tmp, "m"), backend=BackendFalso(probs),
                   budget_usd=1.0, usar_skills=False, seed=0, trazas=log)
    for b in range(4):
        m.correr_bloque(b, probs[b * BLOQUE:(b + 1) * BLOQUE])
    enc = log.ciclo(tipo="detector_encoge")
    check("transición encoge asentada",
          len(enc) == 1 and enc[0]["actor"] == "detector"
          and enc[0]["detalle"].get("brazo") == "single")
    m.cerrar()


if __name__ == "__main__":
    test_deshabilitado_es_identico()
    test_encoge_tras_k_unanimes()
    test_spot_check()
    test_skip_no_alimenta()
    test_empate_reinicia()
    test_fail_safe()
    test_trazas()
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if all(PASSOS) else 1)
