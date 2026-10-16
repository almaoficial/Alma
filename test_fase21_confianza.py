"""Tests fase 2.1: ciclo de confianza provisional→trusted (OpenSpace).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase21_confianza.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.confianza import (
    ConfianzaSkills, intervalo_wilson, UMBRAL_EXITOS,
    CONFIANZA_PROVISIONAL, CONFIANZA_TRUSTED)

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def main():
    d = tempfile.mkdtemp(prefix="alma_fase21_conf_")
    cs = ConfianzaSkills(os.path.join(d, "confianza.db"))

    # 1. Nace provisional.
    cs.registrar("skills/a/SKILL.md")
    check("nace provisional",
          cs.confianza_de("skills/a/SKILL.md") == CONFIANZA_PROVISIONAL)
    check("desconocida default provisional",
          cs.confianza_de("skills/zzz/SKILL.md") == CONFIANZA_PROVISIONAL)

    # 2. El auto-reporte NO promueve (Fix A5b): solo certifica una
    # fuente independiente.
    for _ in range(UMBRAL_EXITOS):
        r = cs.marcar_uso("skills/a/SKILL.md", exito=True)
    check("auto-reporte x3 NO promueve",
          r["confianza"] == CONFIANZA_PROVISIONAL)
    check("auto-reporte cuenta como telemetría",
          cs.metricas("skills/a/SKILL.md")["exitos"] == UMBRAL_EXITOS
          and cs.metricas("skills/a/SKILL.md")["exitos_verificados"] == 0)

    # 2b. Certificación con fuente no verificadora → rechazada.
    r = cs.certificar_exito("skills/a/SKILL.md", fuente="auto")
    check("fuente 'auto' rechazada",
          r["ok"] is False
          and cs.confianza_de("skills/a/SKILL.md")
          == CONFIANZA_PROVISIONAL)

    # 2c. Certificación independiente ×3 → trusted.
    for _ in range(UMBRAL_EXITOS - 1):
        r = cs.certificar_exito("skills/a/SKILL.md", fuente="validador")
    check("aún provisional antes del umbral verificado",
          r["confianza"] == CONFIANZA_PROVISIONAL)
    r = cs.certificar_exito("skills/a/SKILL.md", fuente="harness")
    check("trusted al llegar al umbral verificado",
          r["ok"] is True and r["confianza"] == CONFIANZA_TRUSTED)

    # 3. Métricas con intervalo de Wilson (crítica OMNEX).
    m = cs.metricas("skills/a/SKILL.md")
    check("métricas: tasa e IC presentes",
          m["tasa_exito"] == 1.0
          and m["ic95"] is not None and m["ic95"][0] <= 1.0 <= m["ic95"][1]
          and m["exitos_verificados"] == UMBRAL_EXITOS)
    m0 = cs.metricas("skills/zzz/SKILL.md")
    check("sin usos: tasa e IC son None",
          m0["tasa_exito"] is None and m0["ic95"] is None)
    ic = intervalo_wilson(1, 2)
    check("Wilson(1/2) es intervalo válido",
          ic is not None and 0.0 <= ic[0] < 0.5 < ic[1] <= 1.0)

    # 4. Uso sin veredicto no inventa métrica.
    antes = cs.metricas("skills/a/SKILL.md")
    cs.marcar_uso("skills/a/SKILL.md", exito=None)
    m = cs.metricas("skills/a/SKILL.md")
    check("uso sin veredicto no cambia exitos ni verificados",
          m["exitos"] == antes["exitos"]
          and m["exitos_verificados"] == antes["exitos_verificados"])

    # 5. Degradación SOLO ante fallo atribuible explícito (reversible).
    r = cs.marcar_fallo("skills/a/SKILL.md", atribuible=False)
    check("fallo no atribuible no degrada",
          r["confianza"] == CONFIANZA_TRUSTED and not r["degradada"])
    r = cs.marcar_fallo("skills/a/SKILL.md", atribuible=True)
    check("fallo atribuible degrada a provisional",
          r["confianza"] == CONFIANZA_PROVISIONAL and r["degradada"])
    for _ in range(UMBRAL_EXITOS):
        cs.certificar_exito("skills/a/SKILL.md", fuente="benchmark")
    check("degradación reversible: re-gana trusted con verificados",
          cs.confianza_de("skills/a/SKILL.md") == CONFIANZA_TRUSTED)
    check("degradaciones contadas",
          cs.metricas("skills/a/SKILL.md")["degradaciones"] == 1)

    # 6. Skills externas: cuarentena (trust nunca se hereda).
    r = cs.importar_externa("skills/ext/SKILL.md")
    check("externa nace provisional en cuarentena",
          r["confianza"] == CONFIANZA_PROVISIONAL
          and r["origen"] == "externa_cuarentena")

    # 7. Resumen por estado.
    res = cs.resumen()
    check("resumen cuenta por estado",
          res.get(CONFIANZA_TRUSTED, 0) >= 1
          and res.get(CONFIANZA_PROVISIONAL, 0) >= 1)

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
