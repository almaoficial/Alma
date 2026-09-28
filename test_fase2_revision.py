"""Tests fase 2: revisión de background con gate de aprobación.

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_fase2_revision.py
"""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.revision import RevisionBackground

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


def main():
    d = tempfile.mkdtemp(prefix="alma_fase2_rev_")
    db = os.path.join(d, "rev.db")
    # La tabla experiencias la crea el store del servicio (producción:
    # siempre existe). Acá la creamos igual que el servicio.
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "servicio"))
    from store_sqlite import SQLiteStore
    SQLiteStore(db)

    # 1. Cada N interacciones dispara (en background, sin bloquear).
    rb = RevisionBackground(db, cada_n=3)
    t0 = time.time()
    rb.registrar_interaccion()
    rb.registrar_interaccion()
    rb.registrar_interaccion()  # dispara
    check("registrar no bloquea", time.time() - t0 < 5)
    time.sleep(1.0)  # deja correr el hilo
    check("hilo terminó", rb.estado()["en_curso"] is False)

    # 2. Gate: nada se aplica solo. Sembramos una propuesta a mano.
    rid = rb._proponer("nota_memoria", {"texto": "nota de prueba"})
    check("pendiente listada",
          any(p["id"] == rid for p in rb.pendientes()))
    n_antes = rb._con().execute(
        "SELECT COUNT(*) FROM experiencias").fetchone()[0]
    r = rb.rechazar(rid)
    check("rechazar ok", r["ok"] is True)
    check("rechazada sale de pendientes",
          not any(p["id"] == rid for p in rb.pendientes()))
    n_despues = rb._con().execute(
        "SELECT COUNT(*) FROM experiencias").fetchone()[0]
    check("rechazar no escribe nada", n_antes == n_despues)

    rid2 = rb._proponer("nota_memoria", {"texto": "nota aprobada"})
    r2 = rb.aprobar(rid2)
    check("aprobar ok", r2["ok"] is True)
    n_final = rb._con().execute(
        "SELECT COUNT(*) FROM experiencias").fetchone()[0]
    check("aprobar aplica la escritura", n_final == n_despues + 1)
    fila = rb._con().execute(
        "SELECT origen FROM experiencias ORDER BY id DESC LIMIT 1"
    ).fetchone()
    check("origen auditado", fila[0] == "revision_background")

    # 3. Doble aprobación no duplica.
    r3 = rb.aprobar(rid2)
    check("re-aprobar no duplica", r3["ok"] is False)

    ok = all(PASSOS)
    print(f"\n{sum(PASSOS)}/{len(PASSOS)} checks en verde")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
