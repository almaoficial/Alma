"""Tests fase 0: memoria con olvido + evicción acotada.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase0_memoria.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.memoria import MemoriaExperiencias

PASSOS = []


def check(nombre, cond):
    PASSOS.append(cond)
    print(("PASS" if cond else "FAIL"), "-", nombre)


def reg(m, i, ts):
    return m.append_experiencia({
        "problema_id": f"p{i}", "clase": "clase-a", "arch_id": "exp1",
        "metricas": {"reward": 1.0}, "timestamp": ts,
    })["id"]


def test_decaimiento():
    m = MemoriaExperiencias(":memory:")
    reg(m, 1, 1000.0)
    reg(m, 2, 1000.0 + 86400.0)  # un día después
    ahora = 1000.0 + 2 * 86400.0
    rec = m.recuperar_con_decaimiento("clase-a", ahora=ahora)
    rec.sort(key=lambda x: -x[2])
    check("recupera 2 experiencias", len(rec) == 2)
    w_nueva, w_vieja = rec[0][2], rec[1][2]
    check("la nueva pesa más (0.5^1 > 0.5^2)",
          abs(w_nueva - 0.5) < 1e-9 and abs(w_vieja - 0.25) < 1e-9)
    check("recompensas intactas", all(x[1] == 1.0 for x in rec))


def test_eviccion():
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "mem.sqlite")
    m = MemoriaExperiencias(path, tasa_olvido=0.5)
    base = 1000.0
    ids = []
    for i in range(10):
        eid = reg(m, i, base + i * 3600.0)
        ids.append(eid)
        m.registrar_uso(eid, reward=1.0, ahora=base + 10 * 3600.0)
    arch = m.aplicar_eviccion(5, ahora=base + 10 * 3600.0)
    check("archiva hasta el tope (5 de 10)",
          len(arch) == 5 and m.contar_activas() == 5)
    check("verify_chain intacto tras evicción", m.verify_chain())
    rec = m.recuperar_con_decaimiento("clase-a",
                                      ahora=base + 10 * 3600.0)
    check("recupera solo las activas", len(rec) == 5)
    rec_all = m.recuperar_con_decaimiento("clase-a",
                                          ahora=base + 10 * 3600.0,
                                          incluir_archivadas=True)
    check("las archivadas siguen en el ledger", len(rec_all) == 10)
    arch2 = m.aplicar_eviccion(5, ahora=base + 10 * 3600.0)
    check("evicción idempotente", arch2 == [])


if __name__ == "__main__":
    test_decaimiento()
    test_eviccion()
    sys.exit(0 if all(PASSOS) else 1)
