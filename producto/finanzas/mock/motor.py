"""Mock de finanzas — motor determinista (US$0, sin Plaid, sin datos reales).

Secciones:
  1. Generador sintético (semilla fija 2809, bit-idéntico).
  2. Capa 2 — detección determinista: fugas, anomalías, semáforo, alertas.
  3. Capa 3 — redactor determinista (plantilla; solo inserta números de la capa 2).

Ningún LLM decide sobre plata: la capa 3 solo formatea texto.
"""
import random
from statistics import median

SEED = 2809
DIAS_POR_MES = 30
N_MESES = 7
N_DIAS = N_MESES * DIAS_POR_MES  # 210

# ---------------------------------------------------------------- generador
COMERCIO_CATEGORIA = {
    "COTO": "super", "DISCO": "super", "CARREFOUR": "super",
    "RAPPI": "delivery", "PEDIDOSYA": "delivery", "UBEREATS": "delivery",
    "SUBE": "transporte", "UBER": "transporte", "CABIFY": "transporte",
    "CINEPOLIS": "salidas", "BAR_OCHO": "salidas", "TEATRO": "salidas",
    "LIBRERIA": "otros", "FERRETERIA": "otros", "TIENDA_UNICA": "otros",
    "MCDONALDS": "comida_fuera", "STARBUCKS": "comida_fuera",
    "NETFLIX": "suscripciones", "SPOTIFY": "suscripciones",
    "GYM": "suscripciones", "STREAMPLUS": "suscripciones",
    "ALQUILER": "alquiler",
    "ZELLE_AGUS": "ingreso", "ZELLE_JOACO": "ingreso",
    "ZELLE_CLIENTE": "ingreso",
}
DISCRECIONALES = {"delivery", "salidas", "comida_fuera"}
SUSCRIPCIONES_DECLARADAS = {"NETFLIX", "SPOTIFY", "GYM"}

# Eventos inyectados (coinciden con preregistro.md)
E1_INICIO, E1_FIN = 90, 134      # fuga delivery: mes 4 día 1 -> mes 5 día 15
E2_DIA = 69                       # anomalía puntual US$400, mes 3 día 10
E3_INICIO, E3_FIN = 120, 179      # deriva salidas +30%, meses 5-6
E4_DIAS = (100, 101)              # duplicado CINEPOLIS 18.50 (26 h de diferencia)
E5_MESES = (5, 6)                 # STREAMPLUS meses 5 y 6
E6_MES = 7                        # mes en rojo (sin ingresos declarados)


def generar():
    rng = random.Random(SEED)
    movs = []
    _id = 0

    def add(dia, hora, comercio, monto, tipo="gasto"):
        nonlocal _id
        _id += 1
        movs.append({
            "id": _id, "dia": dia, "hora": hora, "comercio": comercio,
            "categoria": COMERCIO_CATEGORIA[comercio],
            "monto": round(monto, 2), "tipo": tipo,
        })

    for dia in range(N_DIAS):
        mes = dia // DIAS_POR_MES + 1
        dia_mes = dia % DIAS_POR_MES + 1
        fuga = E1_INICIO <= dia <= E1_FIN
        deriva = E3_INICIO <= dia <= E3_FIN

        # súper
        if rng.random() < 0.35:
            add(dia, 12, rng.choice(["COTO", "DISCO", "CARREFOUR"]),
                rng.uniform(8, 18))
        # delivery: 2 por semana (días fijos). E1: DUPLICA la mediana
        # (mismos días, montos U(32,48) vs U(16,24)) durante 6 semanas.
        if dia % 7 in (2, 6):
            add(dia, 20, rng.choice(["RAPPI", "PEDIDOSYA", "UBEREATS"]),
                rng.uniform(32, 48) if fuga else rng.uniform(16, 24))
        # transporte
        if rng.random() < 0.30:
            add(dia, 8, rng.choice(["SUBE", "UBER", "CABIFY"]),
                rng.uniform(3, 8))
        # salidas: 2 por semana (días fijos), montos estables (E3: +30%)
        if dia % 7 in (4, 5):
            m = rng.uniform(24, 36) * (1.3 if deriva else 1.0)
            add(dia, 22, rng.choice(["CINEPOLIS", "BAR_OCHO", "TEATRO"]), m)
        # E6 (mes en rojo): ritmo de gasto diario elevado en el mes 7.
        # 5 gastos/día de US$25-40 (< US$50: no disparan la banda anti-ruido
        # de anomalías puntuales; solo mueven el ritmo diario).
        if mes == E6_MES:
            for comercio in ["RAPPI", "CINEPOLIS", "MCDONALDS", "COTO",
                             "STARBUCKS"]:
                add(dia, rng.choice([12, 14, 19, 21]),
                    comercio, rng.uniform(25, 40))
        # otros (goteo base)
        if rng.random() < 0.10:
            add(dia, 15, rng.choice(["LIBRERIA", "FERRETERIA"]),
                rng.uniform(5, 25))
        # comida fuera
        if rng.random() < 0.12:
            add(dia, 13, rng.choice(["MCDONALDS", "STARBUCKS"]),
                rng.uniform(10, 30))
        # suscripciones fijas
        if dia_mes == 2:
            add(dia, 9, "NETFLIX", 15.49)
        if dia_mes == 3:
            add(dia, 9, "SPOTIFY", 10.99)
            if mes in E5_MESES:                      # E5 fantasma
                add(dia, 10, "STREAMPLUS", 12.99)
        if dia_mes == 5:
            add(dia, 9, "GYM", 29.99)
        # alquiler + reembolsos parciales simulados
        if dia_mes == 15:
            add(dia, 9, "ALQUILER", 3015.00)
        if dia_mes == 18:
            add(dia, 12, "ZELLE_AGUS", 1000.00, tipo="ingreso")
            movs[-1]["categoria"] = "ingreso"
        if dia_mes == 22:
            add(dia, 12, "ZELLE_JOACO", 1080.00, tipo="ingreso")
            movs[-1]["categoria"] = "ingreso"
        # ingresos (mes 7 sin ingresos: E6)
        if mes != E6_MES and dia_mes in (1, 15):
            add(dia, 11, "ZELLE_CLIENTE", rng.uniform(1300, 1700),
                tipo="ingreso")
            movs[-1]["categoria"] = "ingreso"

    # E2: anomalía puntual
    add(E2_DIA, 16, "TIENDA_UNICA", 400.00)
    # E4: duplicado (26 h de diferencia)
    add(E4_DIAS[0], 10, "CINEPOLIS", 18.50)
    add(E4_DIAS[1], 12, "CINEPOLIS", 18.50)

    movs.sort(key=lambda m: (m["dia"], m["hora"], m["id"]))
    return movs


# ------------------------------------------------------------------ capa 2
def _mad(vals):
    if not vals:
        return 0.0
    med = median(vals)
    return median([abs(v - med) for v in vals])


def baseline_categoria(movs, categoria, hasta_dia, ventana=90):
    """Mediana y MAD de montos de gastos de la categoría en ventana previa."""
    vals = [m["monto"] for m in movs
            if m["tipo"] == "gasto" and m["categoria"] == categoria
            and hasta_dia - ventana <= m["dia"] < hasta_dia]
    if len(vals) < 5:
        return None, None
    return median(vals), _mad(vals)


def detectar_anomalias(movs, k=3, min_monto=50.0, ventana=90):
    """Anomalía puntual: |gasto − mediana| > k×MAD y monto > min_monto."""
    out = []
    for m in movs:
        if m["tipo"] != "gasto" or m["monto"] <= min_monto:
            continue
        med, mad = baseline_categoria(movs, m["categoria"], m["dia"], ventana)
        if med is None or mad == 0:
            continue
        if abs(m["monto"] - med) > k * mad:
            out.append({"mov": m, "mediana": med, "mad": mad,
                        "desvio": abs(m["monto"] - med)})
    return out


def gasto_diario_categoria(movs, categoria, dia_ini, dia_fin):
    return [sum(m["monto"] for m in movs
                if m["tipo"] == "gasto" and m["categoria"] == categoria
                and m["dia"] == d)
            for d in range(dia_ini, dia_fin)]


def detectar_deriva(movs, categoria, hasta_dia, k=3, sem_mm=3,
                    min_semanas=3, ventana_base=90):
    """Deriva: mediana móvil de 3 semanas (= 21 días de cobertura) del gasto
    semanal de la categoría fuera de `mediana ± k×MAD` (baseline: gasto
    semanal de los 90 días previos) por ≥ 3 semanas consecutivas.

    La serie semanal evita que la intermitencia día a día (días en cero)
    colapse la mediana a 0.
    """
    # serie semanal: semana i = días [i*7, i*7+7)
    n_sem = hasta_dia // 7
    serie = []
    for i in range(n_sem):
        serie.append(sum(
            m["monto"] for m in movs
            if m["tipo"] == "gasto" and m["categoria"] == categoria
            and i * 7 <= m["dia"] < (i + 1) * 7))
    n_base = ventana_base // 7
    base = serie[:max(0, n_sem - sem_mm - 1)][-n_base:]
    if len(base) < 8:
        return None
    med, mad = median(base), _mad(base)
    if mad == 0:
        return None
    # mediana móvil de `sem_mm` semanas sobre la cola de la serie
    cola = serie[max(0, n_sem - sem_mm - min_semanas - 2):]
    racha, inicio = 0, None
    for j in range(len(cola) - sem_mm + 1):
        mm = median(cola[j:j + sem_mm])
        if abs(mm - med) > k * mad:
            if racha == 0:
                inicio = (n_sem - len(cola) + j) * 7
            racha += 1
            if racha >= min_semanas:
                return {"categoria": categoria, "inicio": inicio,
                        "fin": inicio + (racha + sem_mm - 1) * 7 - 1,
                        "mediana": med, "mad": mad, "mm_final": mm}
        else:
            racha, inicio = 0, None
    return None


def detectar_fugas(movs, hasta_dia, ventana_det=28, ventana_base=90,
                   k=2, min_dias=14):
    """Fuga: share de categoría discrecional en ventana móvil (≈ mensual) >
    mediana de 3 meses + k×MAD.

    Devuelve por categoría: `primera_senal` (primer día sobre el umbral,
    para medir el lag) y `confirmada` (persiste ≥ 14 días consecutivos).
    """
    fugas = []
    # El share se mide sobre el gasto operativo: se excluye el alquiler
    # (monto fijo, no discrecional) porque su presencia/ausencia en la
    # ventana distorsionaría el share de las categorías discrecionales.
    EXCLUIDAS_SHARE = {"alquiler"}
    for cat in sorted(DISCRECIONALES):
        # baseline: shares en ventanas de `ventana_det` de los 90 días previos
        base_ini = hasta_dia - ventana_base - ventana_det
        shares_base = []
        for ini in range(base_ini, hasta_dia - ventana_det):
            tot = sum(m["monto"] for m in movs
                      if m["tipo"] == "gasto"
                      and m["categoria"] not in EXCLUIDAS_SHARE
                      and ini <= m["dia"] < ini + ventana_det)
            if tot == 0:
                continue  # ventana sin historia: no aporta al baseline
            sh = (sum(m["monto"] for m in movs
                      if m["tipo"] == "gasto" and m["categoria"] == cat
                      and ini <= m["dia"] < ini + ventana_det) / tot)
            shares_base.append(sh)
        if len(shares_base) < 10:
            continue
        med, mad = median(shares_base), _mad(shares_base)
        umbral = med + k * mad
        # detección día a día
        racha, primera, share_max = 0, None, 0.0
        for fin in range(hasta_dia - ventana_det, hasta_dia):
            ini = fin - ventana_det
            tot = sum(m["monto"] for m in movs
                      if m["tipo"] == "gasto"
                      and m["categoria"] not in EXCLUIDAS_SHARE
                      and ini <= m["dia"] < fin)
            sh = (sum(m["monto"] for m in movs
                      if m["tipo"] == "gasto" and m["categoria"] == cat
                      and ini <= m["dia"] < fin) / tot) if tot else 0
            if sh > umbral:
                if racha == 0:
                    primera = fin
                racha += 1
                share_max = max(share_max, sh)
            else:
                if racha > 0:
                    fugas.append({"categoria": cat, "primera_senal": primera,
                                  "deteccion": primera,
                                  "confirmada": racha >= min_dias,
                                  "dias_sobre_umbral": racha,
                                  "share": share_max, "umbral": umbral,
                                  "mediana_base": med})
                racha, primera, share_max = 0, None, 0.0
        if racha > 0:
            fugas.append({"categoria": cat, "primera_senal": primera,
                          "deteccion": primera,
                          "confirmada": racha >= min_dias,
                          "dias_sobre_umbral": racha,
                          "share": share_max, "umbral": umbral,
                          "mediana_base": med})
    return fugas


def detectar_duplicados(movs, horas=48):
    """Dos cargos idénticos (mismo comercio, mismo monto) en < 48 h."""
    out, vistos = [], {}
    for m in sorted(movs, key=lambda x: (x["dia"], x["hora"])):
        if m["tipo"] != "gasto":
            continue
        key = (m["comercio"], m["monto"])
        h_actual = m["dia"] * 24 + m["hora"]
        if key in vistos:
            h_prev, m_prev = vistos[key]
            if 0 < h_actual - h_prev < horas:
                out.append({"mov1": m_prev, "mov2": m,
                            "delta_h": h_actual - h_prev})
        vistos[key] = (h_actual, m)
    return out


def detectar_fantasmas(movs, declaradas=SUSCRIPCIONES_DECLARADAS,
                       min_rep=2, lo=27, hi=33):
    """Cargo recurrente mensual no declarado: mismo comercio+monto con
    intervalo 27–33 días, ≥ 2 ocurrencias."""
    grupos = {}
    for m in movs:
        if m["tipo"] != "gasto" or m["categoria"] != "suscripciones":
            continue
        grupos.setdefault((m["comercio"], m["monto"]), []).append(m["dia"])
    out = []
    for (comercio, monto), dias in grupos.items():
        if comercio in declaradas:
            continue
        dias = sorted(dias)
        ok = sum(1 for a, b in zip(dias, dias[1:]) if lo <= b - a <= hi)
        if len(dias) >= min_rep and ok >= min_rep - 1:
            out.append({"comercio": comercio, "monto": monto,
                        "ocurrencias": len(dias), "dias": dias})
    return out


def semaforo(saldo_inicial, mediana_diaria, dias_restantes, cuota,
             ingresos_declarados=0.0, margen_verde=200.0):
    """Proyección día a día; devuelve color, margen y números."""
    gasto_proy = mediana_diaria * dias_restantes
    margen = saldo_inicial + ingresos_declarados - gasto_proy - cuota
    color = "🟢" if margen >= margen_verde else ("🟡" if margen >= 0 else "🔴")
    recorte_dia = (margen_verde - margen) / dias_restantes if color == "🟡" else 0.0
    return {"color": color, "margen": round(margen, 2),
            "gasto_proyectado": round(gasto_proy, 2),
            "recorte_diario": round(recorte_dia, 2)}


def mediana_gasto_diario(movs, hasta_dia, ventana=30):
    vals = [sum(m["monto"] for m in movs
                if m["tipo"] == "gasto" and m["dia"] == d)
            for d in range(hasta_dia - ventana, hasta_dia)]
    return median(vals)


# ------------------------------------------------------------------ alertas
def emitir_alertas(hallazgos_por_dia):
    """Aplica tope de ruido: máx 1 no crítica por día; críticas agrupadas."""
    emitidas = []
    for dia, hallazgos in sorted(hallazgos_por_dia.items()):
        criticas = [h for h in hallazgos if h["critica"]]
        no_crit = [h for h in hallazgos if not h["critica"]]
        temas = {}
        for h in criticas:
            temas.setdefault(h["tema"], []).append(h)
        for tema, hs in temas.items():
            emitidas.append({"dia": dia, "tema": tema, "critica": True,
                             "n": len(hs), "detalle": hs})
        if no_crit:
            h = no_crit[0]  # tope: solo la primera no crítica del día
            emitidas.append({"dia": dia, "tema": h["tema"], "critica": False,
                             "n": 1, "detalle": [h]})
    return emitidas


# ------------------------------------------------------------------ capa 3
def redactar_informe(hallazgos):
    """Redactor determinista: plantilla fija, solo números de la capa 2."""
    lineas = ["INFORME DE FINANZAS (mock)"]
    for h in hallazgos:
        t = h["tipo"]
        if t == "fuga":
            lineas.append(
                f"Fuga en {h['categoria']}: share {h['share']:.1%} vs "
                f"baseline {h['mediana_base']:.1%} (umbral {h['umbral']:.1%}), "
                f"detectada el día {h['deteccion']}.")
        elif t == "anomalia":
            m = h["mov"]
            lineas.append(
                f"Anomalía puntual: {m['comercio']} US${m['monto']:.2f} el día "
                f"{m['dia']} (mediana {h['mediana']:.2f}, desvío "
                f"{h['desvio']:.2f}).")
        elif t == "deriva":
            lineas.append(
                f"Deriva en {h['categoria']}: mediana móvil fuera de banda "
                f"desde el día {h['inicio']} hasta el {h['fin']} "
                f"(mediana base {h['mediana']:.2f}).")
        elif t == "duplicado":
            lineas.append(
                f"Posible duplicado: {h['mov1']['comercio']} "
                f"US${h['mov1']['monto']:.2f} dos veces en {h['delta_h']} h.")
        elif t == "fantasma":
            lineas.append(
                f"Suscripción no declarada: {h['comercio']} US${h['monto']:.2f} "
                f"mensual ({h['ocurrencias']} cargos).")
        elif t == "semaforo":
            lineas.append(
                f"Semáforo de deudas: {h['color']} margen US${h['margen']:.2f}, "
                f"gasto proyectado US${h['gasto_proyectado']:.2f}.")
    return "\n".join(lineas)
