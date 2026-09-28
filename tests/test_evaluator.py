"""Tests del evaluador: exact-match, equivalencia numérica y tests de código."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alma.evaluator import exact_match, run_code_tests, Evaluator


def test_exact_match_normalizado():
    assert exact_match("  Hola, Mundo! ", "hola mundo")
    assert exact_match("Dióxido de carbono", "dioxido de carbono")
    assert not exact_match("París", "Londres")


def test_equivalencia_numerica():
    assert exact_match("200", 200)
    assert exact_match("200.0", "200")
    assert not exact_match("201", 200)
    assert exact_match("8/(3-8/3)", "8 / (3 - 8 / 3)")


def test_codigo_correcto_pasa():
    ok, _detalle = run_code_tests(
        "```python\ndef suma(a, b):\n    return a + b\n```",
        "assert suma(2, 3) == 5",
    )
    assert ok


def test_codigo_erroneo_falla():
    ok, detalle = run_code_tests(
        "def suma(*args, **kwargs):\n    return None",
        "assert suma(2, 3) == 5",
    )
    assert not ok and detalle


def test_timeout_ante_loop_infinito():
    ok, detalle = run_code_tests("while True:\n    pass", "assert True", timeout=2)
    assert not ok and "timeout" in detalle


def test_reward_combina_exito_y_costo():
    ev = Evaluator()
    p = {"enunciado": "x", "esperado": "42", "verificador": "exact"}
    m_barato = ev.score(p, "42", "single")
    m_caro = ev.score(p, "42", "debate")
    assert m_barato["exito"] == 1.0 and m_caro["exito"] == 1.0
    assert m_barato["reward"] > m_caro["reward"], "a igual éxito, gana el más barato"
    m_mal = ev.score(p, "43", "single")
    assert m_mal["exito"] == 0.0 and m_mal["reward"] < m_barato["reward"]
    assert m_barato["evaluator_version"] == "eval-v1"


if __name__ == "__main__":
    test_exact_match_normalizado()
    test_equivalencia_numerica()
    test_codigo_correcto_pasa()
    test_codigo_erroneo_falla()
    test_timeout_ante_loop_infinito()
    test_reward_combina_exito_y_costo()
    print("test_evaluator: 6/6 OK")
