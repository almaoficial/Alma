"""Batería de validación del mock de finanzas — 8 tests pre-registrados.

Vara sellada en preregistro.md. Si un test falla, se rediseña la regla,
no la vara.
"""
import re
from motor import (generar, detectar_anomalias, detectar_deriva,
                   detectar_fugas, detectar_duplicados, detectar_fantasmas,
                   semaforo, mediana_gasto_diario, redactar_informe,
                   E1_INICIO, E2_DIA, E3_INICIO, E3_FIN, DIAS_POR_MES)

movs = generar()

# "Hoy" del mock: día 20 del mes 7 (índice 199). Cierre del mes 7: día 209.
HOY = 6 * DIAS_POR_MES + 19
FIN_MES7 = 7 * DIAS_POR_MES - 1

resultados = []


def test(nombre, ok, detalle):
    resultados.append((nombre, ok, detalle))
    print(f"{'PASS' if ok else 'FAIL'}  {nombre}: {detalle}")


# --- T1: fuga E1 con ≤ 2 semanas de lag
# Medición operativa: se barre día a día desde el inicio de la fuga y se toma
# la primera señal (el baseline de cada evaluación es previo a la fuga).
primera = None
for hd in range(E1_INICIO + 1, E1_INICIO + 45):
    fugas = detectar_fugas(movs, hd)
    fd = next((f for f in fugas if f["categoria"] == "delivery"), None)
    if fd is not None:
        primera = fd["primera_senal"]
        conf = fd["confirmada"]
        break
lag = (primera - E1_INICIO) if primera is not None else None
test("T1 fuga", primera is not None and lag <= 14,
     f"primera señal día {primera} (lag {lag} días desde día {E1_INICIO}, "
     f"vara ≤ 14); confirmada a 14 días: {conf if primera else '—'}")

# --- T2: anomalía puntual E2, ≤ 2 falsas en todo el historial
anoms = detectar_anomalias(movs)
es_e2 = [a for a in anoms if a["mov"]["dia"] == E2_DIA
         and a["mov"]["monto"] == 400.00]
falsas = [a for a in anoms
          if not (a["mov"]["dia"] == E2_DIA and a["mov"]["monto"] == 400.00)
          and not (E1_INICIO <= a["mov"]["dia"] <= 134)   # parte de E1
          and not (E3_INICIO <= a["mov"]["dia"] <= E3_FIN  # parte de E3
                   and a["mov"]["categoria"] == "salidas")]
test("T2 anomalía puntual", len(es_e2) == 1 and len(falsas) <= 2,
     f"E2 marcada: {len(es_e2) == 1}; falsas adicionales: {len(falsas)} "
     f"(vara ≤ 2)")

# --- T3: E3 = deriva, E2 = puntual (no al revés)
# Medición operativa: se barre día a día durante E3 y se toma la primera
# detección (el detector corre a diario en producción).
deriva_salidas = None
for hd in range(E3_INICIO + 1, E3_FIN + 1):
    d = detectar_deriva(movs, "salidas", hd)
    if d is not None:
        deriva_salidas = d
        break
deriva_otros = detectar_deriva(movs, "otros", 90)
# tolerancia −14/+0 días: la mm cubre 3 semanas, el inicio reportado tiene
# incertidumbre de esa magnitud; lo esencial es la clasificación correcta
es_deriva_e3 = (deriva_salidas is not None
                and E3_INICIO - 14 <= deriva_salidas["inicio"] <= E3_FIN)
e2_es_puntual = len(es_e2) == 1 and deriva_otros is None
test("T3 deriva vs pico", es_deriva_e3 and e2_es_puntual,
     f"salidas→{'deriva' if es_deriva_e3 else 'NO deriva'} "
     f"(inicio día {deriva_salidas['inicio'] if deriva_salidas else '—'}, "
     f"E3 = días {E3_INICIO}–{E3_FIN}); E2→puntual: {e2_es_puntual}")

# --- T4: duplicado E4, cero falsos
dups = detectar_duplicados(movs)
es_e4 = [d for d in dups if d["mov1"]["comercio"] == "CINEPOLIS"
         and d["mov1"]["monto"] == 18.50 and d["delta_h"] == 26]
test("T4 duplicado", len(es_e4) == 1 and len(dups) == 1,
     f"E4 detectado (Δt=26 h): {len(es_e4) == 1}; "
     f"duplicados totales: {len(dups)} (vara: 1, cero falsos)")

# --- T5: fantasma STREAMPLUS en ≤ 2 ciclos, cero falsos en declaradas
fants = detectar_fantasmas(movs)
sp = next((f for f in fants if f["comercio"] == "STREAMPLUS"), None)
ciclos = len(sp["dias"]) if sp else 99
falsos_decl = [f for f in fants
               if f["comercio"] in ("NETFLIX", "SPOTIFY", "GYM")]
test("T5 fantasma", sp is not None and ciclos <= 2 and not falsos_decl,
     f"STREAMPLUS detectada con {ciclos} cargos (vara ≤ 2 ciclos); "
     f"falsos sobre declaradas: {len(falsos_decl)}")

# --- T6: semáforo mes 7 en 🟡/🔴 con ≥ 10 días de anticipación
med_diaria = mediana_gasto_diario(movs, HOY)
sem = semaforo(saldo_inicial=2900.0, mediana_diaria=med_diaria,
               dias_restantes=FIN_MES7 - HOY + 1, cuota=1300.0,
               ingresos_declarados=0.0)
anticipacion = FIN_MES7 - HOY
test("T6 semáforo", sem["color"] in ("🟡", "🔴") and anticipacion >= 10,
     f"{sem['color']} margen US${sem['margen']:.2f} "
     f"(gasto proy. US${sem['gasto_proyectado']:.2f}, "
     f"mediana diaria US${med_diaria:.2f}); "
     f"anticipación {anticipacion} días (vara ≥ 10)")

# --- T7: < 1 alerta espuria/mes en meses 1–3 (máx 2 en total)
# Espuria = anomalía falsa o fuga falsa o duplicado falso o fantasma falso
# con día en meses 1–3 (días 0–89), excluyendo E2 (día 69, evento real).
espurias = 0
for a in falsas:
    if 0 <= a["mov"]["dia"] < 3 * DIAS_POR_MES:
        espurias += 1
fugas_tempranas = [f for f in detectar_fugas(movs, 3 * DIAS_POR_MES)
                   if f["deteccion"] < 3 * DIAS_POR_MES]
espurias += len(fugas_tempranas)
espurias += sum(1 for d in dups if d["mov1"]["dia"] < 3 * DIAS_POR_MES)
espurias += sum(1 for f in fants
                if any(dd < 3 * DIAS_POR_MES for dd in f["dias"]))
test("T7 falsos positivos", espurias <= 2,
     f"{espurias} alertas espurias en meses 1–3 (vara: máx 2)")

# --- T8: capa 3 — 0 números inventados en 20 informes
hallazgos = []
fugas_hoy = detectar_fugas(movs, HOY)
for f in fugas_hoy:
    hallazgos.append({"tipo": "fuga", **f})
for a in anoms:
    hallazgos.append({"tipo": "anomalia", **a})
if deriva_salidas:
    hallazgos.append({"tipo": "deriva", **deriva_salidas})
for d in dups:
    hallazgos.append({"tipo": "duplicado", **d})
for f in fants:
    hallazgos.append({"tipo": "fantasma", **f})
hallazgos.append({"tipo": "semaforo", **sem})

def numeros_de_hallazgos(hs):
    nums = set()
    def rec(o):
        if isinstance(o, dict):
            for v in o.values():
                rec(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                rec(v)
        elif isinstance(o, float):
            nums.add(f"{o:.2f}")
            nums.add(f"{abs(o):.2f}")  # el informe puede mostrar el signo suelto
            nums.add(f"{o:.1%}" if 0 <= o <= 2 else None)
        elif isinstance(o, int):
            nums.add(str(o))
    rec(hs)
    nums.discard(None)
    return nums

permitidos = numeros_de_hallazgos(hallazgos)
# también se permiten números estructurales de la plantilla
permitidos |= {"7"}
inventados = 0
for i in range(20):
    txt = redactar_informe(hallazgos)
    for num in re.findall(r"\d+(?:\.\d+)?%?", txt):
        base = num.rstrip("%")
        ok_num = (base in permitidos or num in permitidos
                  or f"{float(base):.1%}" in permitidos)
        if not ok_num:
            inventados += 1
test("T8 redacción", inventados == 0,
     f"{inventados} números no trazables a la capa 2 en 20 informes "
     f"(vara: 0)")

# --- veredicto
pasados = sum(1 for _, ok, _ in resultados if ok)
print(f"\n{pasados}/8 tests PASS")
