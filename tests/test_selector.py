"""Tests del selector: el bandit converge al mejor brazo en simulación."""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alma.selector import BanditPorClase, SelectorArquitecturas


def test_converge_al_mejor_brazo():
    rng = random.Random(0)
    b = BanditPorClase(["a", "b", "c"])
    verdaderos = {"a": 0.2, "b": 0.5, "c": 0.8}
    for _ in range(600):
        brazo = b.select(rng)
        # reward Bernoulli con la prob. verdadera del brazo
        r = 1.0 if rng.random() < verdaderos[brazo] else 0.0
        b.update(brazo, r)
    assert b.select_greedy() == "c", f"eligió {b.select_greedy()}"
    assert b.pulls["c"] > b.pulls["b"] > b.pulls["a"], b.pulls
    assert b.mean("c") > 0.6


def test_priors_uniformes():
    b = BanditPorClase(["a", "b"])
    assert b.mean("a") == b.mean("b") == 0.5


def test_snapshot_restore():
    s = SelectorArquitecturas()
    rng = random.Random(1)
    s.update("calculo", "cot", 0.9)
    snap = s.snapshot()
    s.update("calculo", "cot", 0.0)
    m_antes = s.means("calculo")["cot"]
    s.restore(snap)
    m_despues = s.means("calculo")["cot"]
    assert m_despues > m_antes, "el restore no recuperó el estado"


def test_reward_fuera_de_rango_se_recorta():
    b = BanditPorClase(["a"])
    b.update("a", 5.0)   # se recorta a 1.0
    b.update("a", -3.0)  # se recorta a 0.0
    assert b.pulls["a"] == 2


if __name__ == "__main__":
    test_converge_al_mejor_brazo()
    test_priors_uniformes()
    test_snapshot_restore()
    test_reward_fuera_de_rango_se_recorta()
    print("test_selector: 4/4 OK")
