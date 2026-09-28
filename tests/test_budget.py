"""Tests del BudgetManager: presupuestos separados que cortan al excederse."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alma.budget import BudgetManager, BudgetExceeded, RESOLUCION, EXPERIMENTACION


def test_carga_normal():
    b = BudgetManager({RESOLUCION: 1.0, EXPERIMENTACION: 0.5})
    b.charge(RESOLUCION, 0.4)
    b.charge(RESOLUCION, 0.6)
    assert b.gastado[RESOLUCION] == 1.0


def test_corta_al_exceder():
    b = BudgetManager({RESOLUCION: 1.0})
    b.charge(RESOLUCION, 0.9)
    try:
        b.charge(RESOLUCION, 0.2)
        raise AssertionError("no cortó")
    except BudgetExceeded as e:
        assert e.bucket == RESOLUCION


def test_buckets_independientes():
    b = BudgetManager({RESOLUCION: 0.1, EXPERIMENTACION: 5.0})
    try:
        b.charge(RESOLUCION, 1.0)
        raise AssertionError("no cortó")
    except BudgetExceeded:
        pass
    b.charge(EXPERIMENTACION, 1.0)  # este bucket sigue con crédito
    assert b.remaining(EXPERIMENTACION) == 4.0


def test_bucket_desconocido():
    b = BudgetManager({RESOLUCION: 1.0})
    try:
        b.charge("imprimir_dinero", 1.0)
        raise AssertionError("aceptó bucket desconocido")
    except ValueError:
        pass


if __name__ == "__main__":
    test_carga_normal()
    test_corta_al_exceder()
    test_buckets_independientes()
    test_bucket_desconocido()
    print("test_budget: 4/4 OK")
