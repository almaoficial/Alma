"""El loop ALMA aplicado a trading en papel.

Decisión cada 21 días hábiles (rebalanceo mensual):
  1. PROBE: cada brazo se re-simula en papel sobre los últimos W días
     (desde cero, con costos). Es la ventana reciente, no toda la historia.
  2. PRIOR CON DECAIMIENTO (lección corrida 1 + EXP9): el brazo inicial es el
     mejor del historial con decaimiento exponencial (vida media ~1 año).
     v1 usaba el mejor global desde el día 0 y ancló en campeones del bull
     antes del bear 2022. Sin mapa de parecidos: ante lo nuevo, empezar por
     lo que mejor funcionó *recientemente*.
  3. EVI - probe con costo + penalidad por churn (lección EXP32 + corrida 1):
     cambiar de brazo solo si la ganancia esperada del probe supera el costo
     de cambiar x UMBRAL_EVI más PENALIDAD_CHURN. Probar por probar es costo
     puro; cambiar por cambiar también (whipsaw: 43 cambios en la corrida 1).
  4. DETECCIÓN DE CAMBIOS (lección EXP32/33/34): si los últimos 21 días del
     portafolio se desvían mucho de lo esperado (z < -UMBRAL_CD), la creencia
     puede estar rancia tras un flip -> re-probe forzado al mejor brazo de
     la ventana, sin pedir permiso al EVI.
  5. OLVIDO: solo se usan ventanas recientes (trailing). Lo viejo no pesa.

Todo es causal: en el día t solo se usa información hasta t.
"""
import math

from banco_papel import BancoPapel, COSTO_POR_PATA
from estrategias import BRAZOS

# v2: vida media del prior con decaimiento (lección EXP9), en días hábiles.
# FIJADA por principio (~1 año de mercado), NO calibrada: un grado de
# libertad menos para el sobreajuste.
VIDA_MEDIA_PRIOR = 252
_LAMBDA_PRIOR = 0.5 ** (1.0 / VIDA_MEDIA_PRIOR)


def _replay_brazo(nombre, precios, t_ini, t_fin, fechas, paso_rebalanceo=21,
                  capital=1.0):
    """Re-simula un brazo en [t_ini, t_fin) desde efectivo, con costos.

    Devuelve el retorno neto del período (puede ser negativo).
    """
    banco = BancoPapel(capital_inicial=capital)
    brazo = BRAZOS[nombre]
    for t in range(t_ini, t_fin):
        if (t - t_ini) % paso_rebalanceo == 0:
            senal = brazo(precios, t)
            banco.ejecutar(senal, precios, t, fechas[t])
        else:
            banco.valuar(precios, t, fechas[t])
    eq0 = banco.equity[0][1]
    eq1 = banco.equity[-1][1]
    return eq1 / eq0 - 1.0


def _mejor_global_decay(precios, fechas, t, paso_rebalanceo=21):
    """Prior con decaimiento (lección EXP9), reemplaza al mapless de v1.

    v1 usaba "mejor global desde el día 0" y ancló en los campeones del bull
    justo antes del bear 2022 (creencia confiadamente equivocada). v2 pesa
    cada retorno diario pasado con decaimiento exponencial de vida media
    VIDA_MEDIA_PRIOR: lo reciente pesa más que lo viejo.
    """
    mejor, mejor_s = None, float("-inf")
    for nombre in BRAZOS:
        banco = BancoPapel(capital_inicial=1.0)
        brazo = BRAZOS[nombre]
        for d in range(0, t):
            if d % paso_rebalanceo == 0:
                banco.ejecutar(brazo(precios, d), precios, d, fechas[d])
            else:
                banco.valuar(precios, d, fechas[d])
        eq = banco.equity
        if len(eq) < 2:
            continue
        s, peso = 0.0, 1.0
        # recorrer hacia atrás: el día más reciente pesa 1, el más viejo menos
        for i in range(len(eq) - 1, 0, -1):
            r = eq[i][1] / eq[i - 1][1] - 1.0 if eq[i - 1][1] > 0 else 0.0
            s += r * peso
            peso *= _LAMBDA_PRIOR
        if s > mejor_s:
            mejor, mejor_s = nombre, s
    return mejor or "hold"


def _mejor_global_simple(precios, fechas, t, paso_rebalanceo=21):
    """Prior v1 (mapless, lección V2.4): mejor brazo global desde el día 0,
    sin decaimiento. La corrida 1 de trading mostró que ancla en campeones
    del bull antes de un bear (creencia confiadamente equivocada)."""
    mejor, mejor_s = None, float("-inf")
    for nombre in BRAZOS:
        banco = BancoPapel(capital_inicial=1.0)
        brazo = BRAZOS[nombre]
        for d in range(0, t):
            if d % paso_rebalanceo == 0:
                banco.ejecutar(brazo(precios, d), precios, d, fechas[d])
            else:
                banco.valuar(precios, d, fechas[d])
        eq = banco.equity
        if len(eq) < 2:
            continue
        r = eq[-1][1] / eq[0][1] - 1.0
        if r > mejor_s:
            mejor, mejor_s = nombre, r
    return mejor or "hold"


def correr_alma(precios, fechas, ventana_probe=63, umbral_evi=3.0,
                umbral_cd=2.0, penalidad_churn=0.0, paso_rebalanceo=21,
                capital_inicial=10000.0, version="v2"):
    """Corre el loop ALMA. Devuelve (banco, historial_decisiones).

    v2 vs v1:
      - EVI con penalidad por churn: cambiar de brazo solo si la ganancia
        esperada supera costo x umbral + penalidad_churn. Cambiar cuesta,
        como en la vida (lección del whipsaw de la corrida 1: 43 cambios).
      - Prior con decaimiento exponencial (vida media 252d) en vez del
        mapless "mejor global desde el día 0" (lección corrida 1: anclaje
        en campeones del bull antes del bear 2022).

    historial_decisiones: lista de dicts con fecha, brazo, motivo.

    version="v2": prior con decaimiento + EVI con penalidad por churn.
    version="v1": prior mapless (mejor global desde el día 0, sin
    decaimiento) + EVI sin penalidad por churn. El resto del loop
    (probe en ventana reciente, detección de cambios, olvido) es idéntico.
    """
    n = len(fechas)
    warmup = ventana_probe * 2  # probe necesita historia; brazos también
    banco = BancoPapel(capital_inicial=capital_inicial)
    decisiones = []

    if version == "v1":
        brazo_actual = _mejor_global_simple(precios, fechas, warmup,
                                            paso_rebalanceo=paso_rebalanceo)
        motivo_ini = "prior-simple (mejor global desde el día 0)"
        churn_efectivo = 0.0
    else:
        brazo_actual = _mejor_global_decay(precios, fechas, warmup,
                                          paso_rebalanceo=paso_rebalanceo)
        motivo_ini = "prior-decay (mejor con decaimiento hasta hoy)"
        churn_efectivo = penalidad_churn
    decisiones.append({"fecha": fechas[warmup], "brazo": brazo_actual,
                       "motivo": motivo_ini})

    # retornos diarios del portafolio para detección de cambios
    rets_diarios = []

    for t in range(warmup, n):
        if t == warmup or (t - warmup) % paso_rebalanceo == 0:
            # --- PROBE sobre ventana reciente ---
            t_ini = t - ventana_probe
            ret_probe = {}
            for nombre in BRAZOS:
                ret_probe[nombre] = _replay_brazo(
                    nombre, precios, t_ini, t, fechas,
                    paso_rebalanceo=paso_rebalanceo)
            mejor_probe = max(ret_probe, key=lambda k: ret_probe[k])

            # --- DETECCIÓN DE CAMBIOS: ¿el mundo flipeó bajo nuestros pies? ---
            cambio = False
            if len(rets_diarios) >= ventana_probe:
                rec = rets_diarios[-21:]
                hist = rets_diarios[-ventana_probe:-21] or rets_diarios[-ventana_probe:]
                mu = sum(hist) / len(hist)
                var = sum((x - mu) ** 2 for x in hist) / max(1, len(hist) - 1)
                sd = math.sqrt(var) if var > 0 else 1e-9
                z = (sum(rec) / len(rec) - mu) / (sd / math.sqrt(len(rec)))
                if z < -umbral_cd:
                    cambio = True

            # --- SELECCIÓN con EVI + penalidad por churn ---
            motivo = None
            if cambio:
                brazo_actual = mejor_probe
                motivo = (f"deteccion-cambio (z<{ -umbral_cd}): re-probe forzado "
                          f"-> {mejor_probe}")
            else:
                ganancia = ret_probe[mejor_probe] - ret_probe[brazo_actual]
                costo_cambio = 2 * COSTO_POR_PATA
                umbral_total = costo_cambio * umbral_evi + churn_efectivo
                if mejor_probe != brazo_actual and ganancia > umbral_total:
                    motivo = (f"EVI: ganancia {ganancia:.4f} > costo x{umbral_evi} "
                              f"+ churn {churn_efectivo:.4f} "
                              f"({brazo_actual}->{mejor_probe})")
                    brazo_actual = mejor_probe

            senal = BRAZOS[brazo_actual](precios, t)
            banco.ejecutar(senal, precios, t, fechas[t])
            decisiones.append({"fecha": fechas[t], "brazo": brazo_actual,
                               "motivo": motivo or "mantener (EVI no justifica)"})
        else:
            prev = banco.equity[-1][1] if banco.equity else capital_inicial
            nuevo = banco.valuar(precios, t, fechas[t])
            rets_diarios.append(nuevo / prev - 1.0)

    return banco, decisiones


def correr_brazo_fijo(nombre, precios, fechas, paso_rebalanceo=21,
                      capital_inicial=10000.0):
    """Corre un brazo fijo (baseline) con la misma maquinaria y costos."""
    n = len(fechas)
    banco = BancoPapel(capital_inicial=capital_inicial)
    brazo = BRAZOS[nombre]
    for t in range(n):
        if t % paso_rebalanceo == 0:
            banco.ejecutar(brazo(precios, t), precios, t, fechas[t])
        else:
            banco.valuar(precios, t, fechas[t])
    return banco
