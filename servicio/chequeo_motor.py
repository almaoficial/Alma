"""Puerta de calidad del motor: falla si el mock no pasa.

Tres partes:
  1. Roundtrip del motor en modo demo (sin API key, sin red):
     problema → respuesta → experiencia guardada → el segundo problema
     usa el prior warm (el bandit refleja lo aprendido) → feedback
     explícito mueve el posterior → cadena de hashes intacta.
  2. Mini-runner de tests/: ejecuta todas las funciones test_* de los
     módulos tests/test_*.py (sin pytest, solo stdlib).
  3. ALMA v2: baterías vs persistentes según horizonte, probe consciente
     de ruido, contradicción TRIZ previa a la selección.

Salida: 0 si todo pasa, 1 si algo falla (con detalle).
"""

import importlib.util
import json
import os
import sys
import tempfile
import traceback

SERVICIO = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(SERVICIO, "..")
sys.path.insert(0, SERVICIO)
sys.path.insert(0, BASE)

from motor import Motor  # noqa: E402


def afirma(cond, mensaje):
    if not cond:
        raise AssertionError(mensaje)
    print(f"  ok: {mensaje}")


def test_roundtrip():
    print("[1] roundtrip del motor (demo, DB temporal)")
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        m = Motor(db, backend_kind="demo", seed=7)

        # Problema 1 con ground truth: el demo devuelve el esperado,
        # el evaluador exact-match da reward real y el bandit aprende.
        r1 = m.resolver("¿Cuánto es 20 + 22?", clase="calculo",
                        esperado="42")
        afirma(r1["respuesta"].strip().endswith("42"),
               f"respuesta correcta (brazo={r1['brazo']})")
        afirma(r1["reward"] is not None and r1["reward"] > 0.9,
               f"reward alto con esperado (reward={r1['reward']})")
        afirma(m.store.contar() == 1, "experiencia guardada en SQLite")
        brazo1 = r1["brazo"]
        media_antes = m.selector.means("calculo")[brazo1]
        afirma(media_antes > 0.5,
               f"el bandit aprendió: media({brazo1})={media_antes}")

        # Problema 2, misma clase: el prior warm ya pesa (pulls > 0).
        r2 = m.resolver("¿Cuánto es 10 + 5?", clase="calculo",
                        esperado="15")
        pulls = m.selector._bandit("calculo").pulls
        afirma(sum(pulls.values()) == 2,
               f"segundo problema sumó al prior warm (pulls={pulls})")
        afirma(r2["experiencia_id"] != r1["experiencia_id"],
               "cada resolución es una experiencia nueva (append-only)")

        # Feedback explícito mueve el posterior hacia abajo.
        fb = m.feedback(r1["experiencia_id"], 0.0, nota="prueba")
        media_desp = m.selector.means("calculo")[brazo1]
        afirma(media_desp < media_antes,
               f"feedback 0.0 baja el posterior "
               f"({media_antes} → {media_desp})")
        afirma(fb["feedback_id"] > 0, "feedback guardado encadenado")

        # Modo probe: corre los 3 brazos y elige el mejor.
        r3 = m.resolver("¿Cuánto es 3 + 3?", clase="calculo",
                        esperado="6", modo="probe")
        afirma(r3["modo"] == "probe" and r3["reward"] is not None,
               f"probe elige por reward (brazo={r3['brazo']})")

        # Integridad de la cadena.
        afirma(m.store.verify_chain(), "cadena de hashes intacta")
        m.store.close()
    print("  roundtrip: TODO OK")


def test_existentes():
    print("[2] tests existentes del prototipo")
    tests_dir = os.path.join(BASE, "tests")
    total, fallos = 0, []
    for nombre in sorted(os.listdir(tests_dir)):
        if not (nombre.startswith("test_") and nombre.endswith(".py")):
            continue
        ruta = os.path.join(tests_dir, nombre)
        spec = importlib.util.spec_from_file_location(
            f"t_{nombre[:-3]}", ruta)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            fallos.append((nombre, "<import>", traceback.format_exc(limit=3)))
            continue
        for attr in sorted(dir(mod)):
            if not attr.startswith("test_"):
                continue
            total += 1
            try:
                getattr(mod, attr)()
                print(f"  ok: {nombre}::{attr}")
            except Exception:
                fallos.append(
                    (nombre, attr, traceback.format_exc(limit=5)))
    if fallos:
        print(f"\nFALLARON {len(fallos)} de {total}:")
        for n, a, tb in fallos:
            print(f"--- {n}::{a}\n{tb}")
        raise SystemExit(1)
    print(f"  tests existentes: {total} OK")


def test_v2_baterias():
    print("[3] ALMA v2: baterías vs persistentes según horizonte")
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        m = Motor(db, backend_kind="demo", seed=11)

        # Horizonte largo → batería: responde pero NO entrena al bandit.
        r = m.resolver("Resumí el día de hoy", clase="analisis_diario",
                       esperado="ok", horizonte="largo")
        afirma(r["modo_agente"] == "bateria",
               f"horizonte largo → batería (modo={r['modo_agente']})")
        afirma(r["horizonte"] == "largo", "horizonte resuelto registrado")
        fila = m.store.por_id(r["experiencia_id"])
        met = json.loads(fila["metricas"])
        afirma(met["modo_agente"] == "bateria"
               and met["compromiso"] == "thompson"
               and met["gap_estimado"] is None
               and "contradiccion" in met,
               "experiencia guarda modo/gap/contradicción/compromiso")
        afirma(sum(m.selector._bandit("analisis_diario").pulls.values()) == 0,
               "la batería muere sin entrenar al bandit")

        # Ni el feedback explícito resucita a la batería en el bandit.
        fb = m.feedback(r["experiencia_id"], 1.0, nota="sirvió")
        afirma(fb["aplico_al_bandit"] is False,
               "feedback en batería no toca el bandit")
        afirma(sum(m.selector._bandit("analisis_diario").pulls.values()) == 0,
               "bandit intacto tras feedback en batería")

        # Horizonte corto → persistente: entrena como v1.
        r2 = m.resolver("¿Cuánto es 1 + 1?", clase="calculo",
                        esperado="2", horizonte="corto")
        afirma(r2["modo_agente"] == "persistente",
               "horizonte corto → persistente")
        afirma(sum(m.selector._bandit("calculo").pulls.values()) == 1,
               "persistente entrena al bandit")

        # auto: analisis_diario → largo; calculo → corto.
        r3 = m.resolver("otro resumen", clase="analisis_diario",
                        esperado="ok")
        afirma(r3["modo_agente"] == "bateria" and r3["horizonte"] == "largo",
               "auto: analisis_diario → largo")
        r4 = m.resolver("¿Cuánto es 2 + 2?", clase="calculo", esperado="4")
        afirma(r4["modo_agente"] == "persistente",
               "auto: calculo → corto")

        # Horizonte inválido se rechaza.
        try:
            m.resolver("x", horizonte="eterno")
            afirma(False, "horizonte inválido debería fallar")
        except ValueError:
            print("  ok: horizonte inválido rechazado")

        # El prior warm reconstruido ignora las baterías.
        m2 = Motor(db, backend_kind="demo", seed=11)
        afirma(sum(m2.selector._bandit("analisis_diario").pulls.values()) == 0,
               "prior warm reconstruido ignora experiencias batería")
        afirma(sum(m2.selector._bandit("calculo").pulls.values()) == 2,
               "prior warm conserva experiencias persistentes")
        m.store.close()
        m2.store.close()
    print("  baterías vs persistentes: TODO OK")


def test_v2_probe_ruido():
    print("[4] ALMA v2: probe consciente de ruido")
    from motor import decidir_compromiso, UMBRAL_RUIDO_DEFAULT
    afirma(abs(UMBRAL_RUIDO_DEFAULT - 0.15) < 1e-12,
           "umbral default documentado = 0.15 (EXP21 falla / EXP19 gana)")
    ganador, gap, comp = decidir_compromiso(
        {"single": 0.9, "cot": 0.5, "reflexion": 0.4}, 0.15)
    afirma(ganador == "single" and comp == "duro"
           and abs(gap - 0.4) < 1e-9,
           "gap 0.4 > 0.15 → compromiso duro con el ganador")
    ganador2, gap2, comp2 = decidir_compromiso(
        {"single": 0.9, "cot": 0.85, "reflexion": 0.4}, 0.15)
    afirma(ganador2 == "single" and comp2 == "adaptativo"
           and abs(gap2 - 0.05) < 1e-9,
           "gap 0.05 < 0.15 → sin compromiso duro (adaptativo)")

    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        m = Motor(db, backend_kind="demo", seed=13)
        # En demo los brazos difieren apenas por formato de respuesta
        # (gap ≈ 0.01: ruido puro) → adaptativo. Eso es exactamente lo
        # que el umbral debe filtrar.
        r = m.resolver("¿Cuánto es 5 + 5?", clase="calculo",
                       esperado="10", modo="probe")
        afirma(r["compromiso"] == "adaptativo",
               f"gap chico → adaptativo (compromiso={r['compromiso']})")
        afirma(r["gap_estimado"] is not None
               and abs(r["gap_estimado"]) < 0.05,
               f"gap estimado chico = ruido (gap={r['gap_estimado']})")
        afirma(r["contradiccion"]["mejora"] == "velocidad",
               "la contradicción viaja en la respuesta del probe")
        fila = m.store.por_id(r["experiencia_id"])
        met = json.loads(fila["metricas"])
        afirma(met["compromiso"] == "adaptativo"
               and met["gap_estimado"] == r["gap_estimado"]
               and met["umbral_ruido"] == 0.15,
               "experiencia final guarda gap, compromiso y umbral")
        # umbral_ruido personalizado viaja hasta la decisión: con umbral
        # 0.0 hasta el gap mínimo (0.01) supera el umbral → duro.
        r2 = m.resolver("¿Cuánto es 6 + 6?", clase="calculo",
                        esperado="12", modo="probe", umbral_ruido=0.0)
        afirma(r2["compromiso"] == "duro",
               "con umbral 0.0 cualquier gap positivo → duro")
        met2 = json.loads(m.store.por_id(r2["experiencia_id"])["metricas"])
        afirma(met2["umbral_ruido"] == 0.0,
               "umbral personalizado queda registrado")
        # Umbral inválido se rechaza.
        try:
            m.resolver("x", clase="calculo", esperado="1",
                       modo="probe", umbral_ruido=-1)
            afirma(False, "umbral negativo debería fallar")
        except ValueError:
            print("  ok: umbral_ruido negativo rechazado")
        m.store.close()
    print("  probe consciente de ruido: TODO OK")


def test_v2_contradiccion():
    print("[5] ALMA v2: contradicción TRIZ previa a la selección")
    from motor import formular_contradiccion
    brazos = ("single", "cot", "reflexion")
    c1 = formular_contradiccion("¿Cuánto es 2 + 2?", "calculo", brazos)
    afirma(c1["mejora"] == "velocidad"
           and c1["empeora"] == "sobre_razonamiento",
           "cálculo corto → velocidad vs sobre-razonamiento")
    afirma(c1["brazos_ordenados"][0] == "single",
           "en cálculo simple el probe evalúa single primero")
    c2 = formular_contradiccion(
        "Analizá en profundidad el informe trimestral y detectá los tres "
        "riesgos principales con su probabilidad estimada", "analisis",
        brazos)
    afirma(c2["mejora"] == "calidad" and c2["empeora"] == "costo",
           "problema largo → calidad vs costo")
    afirma(c2["brazos_ordenados"][0] == "reflexion",
           "en problema profundo el probe evalúa reflexion primero")
    afirma(set(c2["brazos_ordenados"]) == set(brazos),
           "el orden incluye todos los brazos candidatos")

    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        m = Motor(db, backend_kind="demo", seed=17)
        r = m.resolver("¿Cuánto es 7 + 7?", clase="calculo", esperado="14")
        afirma(r["contradiccion"]["mejora"] == "velocidad",
               "toda resolución formula contradicción (thompson)")
        afirma(r["compromiso"] == "thompson",
               "sin probe el compromiso es 'thompson'")
        fila = m.store.por_id(r["experiencia_id"])
        met = json.loads(fila["metricas"])
        afirma(met["contradiccion"]["empeora"] == "sobre_razonamiento",
               "la contradicción queda guardada en la experiencia")
        m.store.close()
    print("  contradicción TRIZ: TODO OK")


def test_v2_transferencia_mapless():
    print("[6] ALMA v2.4: transferencia sin mapa (shortlist global)")
    from transferencia import (es_clase_fina, frecuencias_globales,
                               shortlist_mapless)
    from store_sqlite import SQLiteStore
    brazos = ("single", "cot", "reflexion")

    def sembrar(store, clase, brazo_ganador, n=6):
        for i in range(n):
            for b in brazos:
                r = 0.9 if b == brazo_ganador else 0.3
                store.append_experiencia({
                    "problema_id": f"t-{clase}-{i}-{b}",
                    "clase": clase,
                    "arch_id": b,
                    "metricas": {"reward": r},
                })

    with tempfile.TemporaryDirectory() as d:
        store = SQLiteStore(os.path.join(d, "test.db"))
        sembrar(store, "a", "cot")
        sembrar(store, "b", "cot")
        sembrar(store, "c", "single")

        votos = frecuencias_globales(store, brazos)
        afirma(votos["cot"] == 2 and votos["single"] == 1,
               f"votos globales: cot=2, single=1 ({dict(votos)})")

        sl = shortlist_mapless(store, brazos)
        afirma(sl == ["cot", "single"],
               f"shortlist top-2 por frecuencia global: {sl}")
        afirma("reflexion" not in sl,
               "el brazo globalmente peor queda fuera del shortlist")

        afirma(es_clase_fina(store, "clase_nueva"),
               "clase sin historia → fina")
        afirma(not es_clase_fina(store, "a"),
               "clase con 18 experiencias → no fina")

        # Empate: el desempate TRIZ decide el orden.
        store2_db = os.path.join(d, "test2.db")
        s2 = SQLiteStore(store2_db)
        sembrar(s2, "x", "cot")
        sembrar(s2, "y", "single")
        sl2 = shortlist_mapless(s2, brazos,
                               orden_desempate=["single", "cot", "reflexion"])
        afirma(sl2[0] == "single",
               f"empate 1-1 → gana el desempate TRIZ: {sl2}")

        # Store vacío: no falla, devuelve los primeros k en orden dado.
        s3 = SQLiteStore(os.path.join(d, "test3.db"))
        sl3 = shortlist_mapless(s3, brazos)
        afirma(sl3 == ["single", "cot"],
               f"sin historia → fallback determinista: {sl3}")

        store.close(); s2.close(); s3.close()
    print("  transferencia mapless: TODO OK")


def test_v2_probe_mapless_end_to_end():
    print("[7] ALMA v2.4: el probe usa el shortlist en clase fina")
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        m = Motor(db, backend_kind="demo", seed=21)
        brazos = ("single", "cot", "reflexion")
        # Siembra: 2 clases donde "cot" es el mejor (6 experiencias c/u).
        for clase in ("a", "b"):
            for i in range(6):
                for b in brazos:
                    m.store.append_experiencia({
                        "problema_id": f"s-{clase}-{i}-{b}",
                        "clase": clase,
                        "arch_id": b,
                        "metricas": {"reward": 0.9 if b == "cot" else 0.3},
                    })
        antes = m.store.contar()
        r = m.resolver("¿Cuánto es 9 + 9?", clase="nueva",
                       esperado="18", modo="probe")
        afirma(r["transferencia"] == "mapless",
               "clase fina → transferencia mapless "
               f"(fue {r['transferencia']})")
        cur = m.store._db.execute(
            "SELECT DISTINCT arch_id FROM experiencias WHERE clase='nueva'")
        vistos = {f[0] for f in cur.fetchall()}
        afirma(vistos == {"cot", "single"},
               f"el probe evaluó solo el shortlist: {sorted(vistos)}")
        afirma(m.store.contar() - antes == 3,
               "3 experiencias nuevas: 2 del probe + 1 final")
        # La experiencia final registra la transferencia usada.
        met = json.loads(m.store.por_id(r["experiencia_id"])["metricas"])
        afirma(met["transferencia"] == "mapless",
               "la transferencia queda guardada en la experiencia")
        # Clase con historia: probe completo como antes.
        r2 = m.resolver("¿Cuánto es 8 + 8?", clase="a",
                        esperado="16", modo="probe")
        afirma(r2["transferencia"] == "completa",
               "clase con historia → probe completo")
        m.store.close()
    print("  probe mapless end-to-end: TODO OK")


if __name__ == "__main__":
    try:
        test_roundtrip()
        test_existentes()
        test_v2_baterias()
        test_v2_probe_ruido()
        test_v2_contradiccion()
        test_v2_transferencia_mapless()
        test_v2_probe_mapless_end_to_end()
    except (AssertionError, SystemExit):
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
    print("\nPUERTA DE CALIDAD: PASS")
