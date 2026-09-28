"""Tests de la vara externa: las métricas no mienten y los baselines corren."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alma.evals import base
from alma.evals import finanzas, rutina
from alma.evals.base import (
    EvalResult, EvalSuite, accuracy, precision_recall_f1, mae, mape, brier,
    leer_historial,
)
from alma.evals import EVALS_VERSION


def test_accuracy():
    assert accuracy([1, 0, 1], [1, 1, 1]) == 2 / 3
    assert accuracy([], []) == 0.0


def test_prf():
    m = precision_recall_f1([True, True, False, False], [True, False, False, False])
    assert m["precision"] == 1.0 and m["recall"] == 0.5
    assert abs(m["f1"] - 2 / 3) < 1e-3


def test_mape():
    assert mape(100, 110) == 0.1
    assert mape(0, 10) is None


def test_brier():
    assert brier([1.0, 0.0], [1, 0]) == 0.0
    assert brier([0.5, 0.5], [1, 0]) == 0.25


def test_result_firmado_con_version():
    r = EvalResult(eval_id="x", score=1.0)
    assert r.to_dict()["version"] == EVALS_VERSION


def test_historial_ida_y_vuelta():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as f:
        path = f.name
    try:
        EvalResult(eval_id="x", score=0.5, metodo="t").guardar(path)
        filas = leer_historial("x", path)
        assert len(filas) == 1 and filas[0]["score"] == 0.5
        assert leer_historial("otro", path) == []
    finally:
        os.unlink(path)


def test_suite_registra_y_corre():
    s = EvalSuite()
    s.registrar("doble")(lambda: EvalResult(eval_id="doble", score=2.0))
    res = s.correr(guardar=False)
    assert len(res) == 1
    assert isinstance(res[0], EvalResult)


def test_categorizar_baseline_supera_azar():
    r = finanzas.eval_categorizar_gastos()
    assert r.eval_id == "categorizar_gastos"
    assert r.score > 0.5, f"baseline peor que moneda: {r.score}"
    assert r.detalle["n"] >= 25


def test_categorizar_acepta_predict_fn():
    r = finanzas.eval_categorizar_gastos(predict_fn=lambda n, m: "otros")
    assert r.metodo == "llm" and r.score < 0.5


def test_detectar_anomalia_encuentra_casos():
    r = finanzas.eval_detectar_anomalia()
    assert r.detalle["anomalias_reales"] >= 2
    assert r.score > 0.0, "no detectó ninguna anomalía real"


def test_gasto_semanal_sin_fuga():
    # la predicción solo puede usar historia hasta fin_historia
    r = finanzas.eval_gasto_semanal(fin_historia="2026-09-18")
    assert r.detalle["semana"].startswith("2026-09-19")
    assert r.detalle["real_usd"] >= 0
    assert 0.0 <= r.score <= 1.0


def test_rutina_manana_evalua_pasado():
    r = rutina.eval_rutina_manana(fecha_objetivo="2026-09-25")
    assert not r.detalle.get("pendiente")
    assert r.detalle["items_evaluados"] > 0
    assert 0.0 <= r.score <= 1.0


def test_rutina_manana_futuro_queda_pendiente():
    r = rutina.eval_rutina_manana(fecha_objetivo="2026-09-26")
    assert r.detalle.get("pendiente") is True
    # "bici" era null el 25/9: lo desconocido no se predice ni se evalúa
    assert "gym" in r.detalle["prediccion"]
    assert "bici" not in r.detalle["prediccion"]


def test_patron_sostiene_devuelve_fraccion():
    r = rutina.eval_patron_sostiene()
    assert 0.0 <= r.score <= 1.0
    assert r.detalle["patrones"] == 3


if __name__ == "__main__":
    test_accuracy()
    test_prf()
    test_mape()
    test_brier()
    test_result_firmado_con_version()
    test_historial_ida_y_vuelta()
    test_suite_registra_y_corre()
    test_categorizar_baseline_supera_azar()
    test_categorizar_acepta_predict_fn()
    test_detectar_anomalia_encuentra_casos()
    test_gasto_semanal_sin_fuga()
    test_rutina_manana_evalua_pasado()
    test_rutina_manana_futuro_queda_pendiente()
    test_patron_sostiene_devuelve_fraccion()
    print("test_evals: 14/14 OK")
