"""Tests fase 2.5: detector de drift de régimen (mock, US$0).

Detector puro y determinista (alma_service/drift.py): sin key, sin
red, sin RNG. Verifica diseño (ventana/umbral/señal), determinismo
y casos borde.

Correr: python3 test_fase25_drift.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.drift import (
    DetectorDrift, VENTANA_DRIFT, CONTRADICCIONES_DRIFT,
    ACCION_RE_PROBE,
)

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def secuencia(d, veredictos, inicio=1):
    """Alimenta una lista de (bloque, ganador); retorna la lista de
    valores de retorno de registrar."""
    return [d.registrar(b, g) for b, g in enumerate(veredictos, start=inicio)]


def test_determinismo():
    """Dos instancias frescas con la misma alimentación dan la misma
    señal, el mismo detalle y el mismo historial."""
    veredictos = ["single", "single", "cot", "single", "cot", "cot",
                  "single"]
    ds = []
    for _ in range(2):
        d = DetectorDrift()
        d.anclar_baseline(0, "single", {"single": 0.8, "cot": 0.6})
        secuencia(d, veredictos)
        ds.append(d)
    a, b = ds
    check("determinismo: misma señal",
          a.hay_drift() == b.hay_drift() and a.senial() == b.senial())
    check("determinismo: mismo historial",
          a.historial == b.historial)
    check("determinismo: misma ventana",
          a.ventana_actual == b.ventana_actual)


def test_estable_no_dispara():
    d = DetectorDrift()
    d.anclar_baseline(0, "single")
    secuencia(d, ["single"] * 8)
    check("mundo estable: no dispara", not d.hay_drift())
    check("mundo estable: 0 contradicciones",
          d.contradicciones_en_ventana() == 0)
    check("mundo estable: accion None", d.senial()["accion"] is None)


def test_flip_dispara():
    d = DetectorDrift()
    d.anclar_baseline(10, "single")
    secuencia(d, ["cot", "cot"], inicio=11)
    check("flip: dispara con M=2 contradicciones", d.hay_drift())
    s = d.senial()
    check("flip: senial detalla baseline y conteo",
          s["baseline"] == "single" and s["contradicciones"] == 2
          and s["umbral"] == 2)
    check("flip: accion re_probe", s["accion"] == ACCION_RE_PROBE)
    check("flip: bloque_drift registrado", s["bloque_drift"] == 12)


def test_una_contradiccion_no_dispara():
    d = DetectorDrift()
    d.anclar_baseline(0, "single")
    secuencia(d, ["single", "cot", "single", "single"])
    check("1 contradicción aislada: no dispara", not d.hay_drift())
    check("1 contradicción contada",
          d.contradicciones_en_ventana() == 1)


def test_ventana_no_racha():
    """El detector es por ventana, no por racha: contradicciones no
    consecutivas también cuentan (diseño deliberado, ver DRIFT.md)."""
    d = DetectorDrift()
    d.anclar_baseline(0, "single")
    secuencia(d, ["cot", "single", "cot"])
    check("contradicciones no consecutivas: dispara", d.hay_drift())


def test_empate_no_cuenta():
    """Un empate (ganador None) no es contradicción ni entra a la
    ventana: no hay veredicto."""
    d = DetectorDrift()
    d.anclar_baseline(0, "single")
    secuencia(d, [None, None])
    check("empates: ventana vacía", d.ventana_actual == [])
    secuencia(d, ["cot"])
    check("empate + 1 contradicción: no dispara", not d.hay_drift())


def test_ventana_desliza():
    """Las contradicciones viejas salen de la ventana: el ruido
    antiguo no dispara tarde."""
    d = DetectorDrift()
    d.anclar_baseline(0, "single")
    secuencia(d, ["cot"] + ["single"] * 6)
    check("contradicción vieja sale de la ventana",
          d.contradicciones_en_ventana() == 0 and not d.hay_drift())
    secuencia(d, ["cot"])
    check("1 contradicción nueva: no dispara", not d.hay_drift())
    secuencia(d, ["cot"])
    check("2da contradicción nueva: dispara", d.hay_drift())


def test_enclavado():
    """Tras disparar, la señal se mantiene aunque la ventana se
    calme: solo el re-anclaje la libera."""
    d = DetectorDrift()
    d.anclar_baseline(0, "single")
    secuencia(d, ["cot", "cot"])
    check("disparó", d.hay_drift())
    secuencia(d, ["single"] * 6)
    check("enclavado pese a calma posterior", d.hay_drift())


def test_reanclaje_libera():
    d = DetectorDrift()
    d.anclar_baseline(0, "single")
    secuencia(d, ["cot", "cot"])
    check("disparó", d.hay_drift())
    d.anclar_baseline(20, "cot", {"cot": 0.9, "single": 0.4})
    check("re-anclaje: señal liberada", not d.hay_drift())
    check("re-anclaje: ventana limpia", d.ventana_actual == [])
    check("re-anclaje: nuevo baseline",
          d.senial()["baseline"] == "cot")
    secuencia(d, ["cot"] * 3)
    check("post re-anclaje: estable no dispara", not d.hay_drift())


def test_sin_baseline_falla():
    d = DetectorDrift()
    try:
        d.registrar(1, "single")
        check("registrar sin baseline: RuntimeError", False)
    except RuntimeError:
        check("registrar sin baseline: RuntimeError", True)


def test_baseline_none_falla():
    d = DetectorDrift()
    try:
        d.anclar_baseline(0, None)
        check("baseline con None: ValueError", False)
    except ValueError:
        check("baseline con None: ValueError", True)


def test_params_invalidos():
    for kwargs in ({"ventana": 0}, {"contradicciones": 0},
                   {"ventana": 3, "contradicciones": 4}):
        try:
            DetectorDrift(**kwargs)
            check(f"params inválidos {kwargs}: ValueError", False)
        except ValueError:
            check(f"params inválidos {kwargs}: ValueError", True)


def test_medias_se_copian():
    """El baseline guarda copia de las medias: mutar el dict de
    entrada después no lo contamina."""
    d = DetectorDrift()
    medias = {"single": 0.8, "cot": 0.6}
    d.anclar_baseline(0, "single", medias)
    medias["single"] = 0.0
    check("medias: copia defensiva",
          d.baseline["medias"]["single"] == 0.8)


def test_historial_auditoria():
    d = DetectorDrift()
    d.anclar_baseline(5, "single", {"single": 0.8})
    secuencia(d, ["cot", "cot"], inicio=6)
    tipos = [e["evento"] for e in d.historial]
    check("historial: anclaje + drift", tipos == ["anclaje", "drift"])
    ev = d.historial[-1]
    check("historial drift: campos de auditoría",
          ev["bloque"] == 7 and ev["baseline"] == "single"
          and ev["contradicciones"] == 2
          and ev["accion"] == ACCION_RE_PROBE)


def test_retorno_registrar():
    """registrar retorna True solo en el registro que dispara."""
    d = DetectorDrift()
    d.anclar_baseline(0, "single")
    rets = secuencia(d, ["single", "cot", "cot", "cot"])
    check("retorno: True solo al disparar",
          rets == [False, False, True, False])


def test_defaults_documentados():
    d = DetectorDrift()
    check("defaults = constantes del módulo",
          d.ventana == VENTANA_DRIFT == 6
          and d.contradicciones == CONTRADICCIONES_DRIFT == 2)


if __name__ == "__main__":
    test_determinismo()
    test_estable_no_dispara()
    test_flip_dispara()
    test_una_contradiccion_no_dispara()
    test_ventana_no_racha()
    test_empate_no_cuenta()
    test_ventana_desliza()
    test_enclavado()
    test_reanclaje_libera()
    test_sin_baseline_falla()
    test_baseline_none_falla()
    test_params_invalidos()
    test_medias_se_copian()
    test_historial_auditoria()
    test_retorno_registrar()
    test_defaults_documentados()
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if all(PASSOS) else 1)
