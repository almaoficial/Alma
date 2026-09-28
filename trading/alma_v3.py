"""ALMA v3: selector por régimen (mapa clima→brazo).

Lecciones que encarna (del transcript):
1. El meta-loop "elegir la mejor estrategia reciente" ES momentum sobre
   estrategias: falla donde falla el momentum (whipsaw v1/v2: ~28 cambios,
   compra techos / vende pisos entre estrategias).
2. Lo que ALMA sí hace bien: control del drawdown, no el retorno.
3. Estudiar no CUÁL va ganando sino CUÁNDO gana cada uno: mapa clima→brazo.

Diseño (constantes fijadas por principio, ver addendum en
ARENA_PREREGISTRO.md — escritas ANTES de correr):
- Régimen diario observable y causal: tendencia = signo del retorno SPY
  trailing 63d; vol = vol realizada 21d vs mediana trailing (máx 252d,
  mín 63d). Sin umbrales tuneados: signo y mediana. → 4 climas.
- Mapa clima→brazo con decaimiento (lección EXP9): cada brazo corre en
  sombra (papel, con costos) desde el día 0; por celda (clima, brazo) se
  acumulan retornos diarios con decaimiento exponencial (vida media 252d).
  Score = Sharpe decayed. Lo reciente pesa más que lo viejo.
- Objetivo riesgo-ajustado: el score es Sharpe, no retorno puro.
- Anti-sobrecalentamiento (histéresis): el régimen oficial cambia solo si
  la lectura mensual nueva se confirma 2 meses seguidos; el brazo cambia
  SOLO cuando cambia el régimen oficial.
- Freno de emergencia principista: z < -3.0 en 21d → cambio forzado al
  mejor del mapa para el régimen vigente. Se cuenta cada disparo.
- Sin evidencia suficiente en un clima → "hold".

Papel, siempre. Todo causal: en el día t solo se usa información hasta t.
"""
import math

from banco_papel import BancoPapel, verificar_solo_papel
from estrategias import BRAZOS

# --- Constantes fijadas por principio (addendum ARENA_PREREGISTRO.md) ---
VIDA_MEDIA_DECAY = 252          # misma constante principista de v2 (EXP9)
_LAMBDA = 0.5 ** (1.0 / VIDA_MEDIA_DECAY)
VENTANA_TENDENCIA = 63          # un trimestre bursátil
VENTANA_VOL = 21                # un mes bursátil
MAX_HIST_VOL = 252              # un año para la mediana trailing
MIN_HIST_VOL = 63               # mínimo un trimestre de historia
PESO_MIN_CELDA = 21.0           # un mes de evidencia en-régimen
Z_EMERGENCIA = -3.0             # cola extrema (~0.13%)
PASO_DECISION = 21              # mensual, igual que v1/v2
WARMUP = 126                    # alineado con el período efectivo de la arena

CLIMAS = ["alcista-baja", "alcista-alta", "bajista-baja", "bajista-alta"]


def _clima_de(t, spy, vol21):
    """Régimen del día t, causal. None si no hay historia suficiente."""
    if t < VENTANA_TENDENCIA or t < VENTANA_VOL:
        return None
    hist = vol21[max(VENTANA_VOL, t - MAX_HIST_VOL):t]
    if len(hist) < MIN_HIST_VOL:
        return None
    med = sorted(hist)[len(hist) // 2]
    tend = "alcista" if spy[t] / spy[t - VENTANA_TENDENCIA] - 1.0 > 0 else "bajista"
    vol = "alta" if vol21[t] > med else "baja"
    return f"{tend}-{vol}"


def correr_alma_v3(precios, fechas, capital_inicial=10000.0, **params):
    """Corre el loop v3. Devuelve (banco, decisiones).

    Firma compatible con el registro RETADORES de arena.py:
    f(precios, fechas, **params) -> (banco, decisiones).
    params se ignora: la v3 no tiene parámetros tuneados (grilla vacía).
    La última entrada de decisiones es {"tipo": "mapa_final", ...} con el
    mapa clima→brazo aprendido, para el chequeo de robustez.
    """
    verificar_solo_papel()
    n = len(fechas)
    spy = precios["SPY"]

    # --- Indicadores causales precomputados ---
    rets_spy = [0.0] + [spy[i] / spy[i - 1] - 1.0 for i in range(1, n)]
    vol21 = [0.0] * n
    for t in range(VENTANA_VOL, n):
        seg = rets_spy[t - VENTANA_VOL + 1:t + 1]
        mu = sum(seg) / len(seg)
        var = sum((x - mu) ** 2 for x in seg) / max(1, len(seg) - 1)
        vol21[t] = math.sqrt(var)

    # --- Brazos en sombra: papel continuo desde el día 0, con costos ---
    ret_sombra = {}
    for nombre, brazo in BRAZOS.items():
        b = BancoPapel(capital_inicial=1.0)
        rs = []
        for t in range(n):
            if t % PASO_DECISION == 0:
                eq = b.ejecutar(brazo(precios, t), precios, t, fechas[t])
            else:
                eq = b.valuar(precios, t, fechas[t])
            prev = b.equity[-2][1] if len(b.equity) >= 2 else 1.0
            rs.append(eq / prev - 1.0 if prev > 0 else 0.0)
        ret_sombra[nombre] = rs

    # --- Mapa clima→brazo: celdas con decaimiento exponencial ---
    # celda[(clima, brazo)] = [sum_ret_decayed, sum_ret2_decayed, peso_decayed]
    celdas = {(c, b): [0.0, 0.0, 0.0] for c in CLIMAS for b in BRAZOS}

    def mejor_brazo(clima):
        cand = []
        for b in BRAZOS:
            s1, s2, w = celdas[(clima, b)]
            if w < PESO_MIN_CELDA:
                continue
            mu = s1 / w
            var = max(s2 / w - mu * mu, 1e-12)
            sharpe = mu / math.sqrt(var) * math.sqrt(252)
            cand.append((sharpe, b))
        if not cand:
            return "hold", None
        cand.sort()
        return cand[-1][1], cand[-1][0]

    # --- Loop principal ---
    banco = BancoPapel(capital_inicial=capital_inicial)
    decisiones = []
    ret_real = []          # retornos diarios del portafolio real
    regimen_oficial = None
    lectura_anterior = None
    brazo_actual = "hold"
    cambios = 0
    emergencias = 0

    for t in range(n):
        cl = _clima_de(t, spy, vol21)
        # Actualizar el mapa con los retornos sombra de hoy (decaimiento
        # diario global + aporte a la celda del clima de hoy).
        for b in BRAZOS:
            r = ret_sombra[b][t]
            for c in CLIMAS:
                s = celdas[(c, b)]
                s[0] *= _LAMBDA
                s[1] *= _LAMBDA
                s[2] *= _LAMBDA
            if cl is not None:
                s = celdas[(cl, b)]
                s[0] += r
                s[1] += r * r
                s[2] += 1.0

        es_decision = (t >= WARMUP and (t - WARMUP) % PASO_DECISION == 0)
        if es_decision:
            # --- Histéresis del régimen: la lectura nueva se confirma ---
            cambio_regimen = False
            motivo_reg = ""
            if cl is not None:
                if regimen_oficial is None:
                    regimen_oficial = cl
                    cambio_regimen = True
                    motivo_reg = f"régimen inicial {cl}"
                elif cl != regimen_oficial and cl == lectura_anterior:
                    regimen_oficial = cl
                    cambio_regimen = True
                    motivo_reg = f"régimen confirmado {cl} (histéresis 2m)"
                lectura_anterior = cl

            # --- Freno de emergencia: cola extrema del brazo actual ---
            emergencia = False
            if len(ret_real) >= VENTANA_VOL:
                rec = ret_real[-VENTANA_VOL:]
                hist = ret_real[max(0, len(ret_real) - MAX_HIST_VOL):-VENTANA_VOL]
                if len(hist) >= MIN_HIST_VOL:
                    mu = sum(hist) / len(hist)
                    var = sum((x - mu) ** 2 for x in hist) / max(1, len(hist) - 1)
                    sd = math.sqrt(var) if var > 0 else 1e-9
                    z = (sum(rec) / len(rec) - mu) / (sd / math.sqrt(len(rec)))
                    if z < Z_EMERGENCIA:
                        emergencia = True
                        emergencias += 1

            # --- Selección: solo ante cambio de régimen o emergencia ---
            if cambio_regimen or emergencia:
                elegido, score = (mejor_brazo(regimen_oficial)
                                  if regimen_oficial else ("hold", None))
                if elegido != brazo_actual:
                    cambios += 1
                    motivo = (f"{'EMERGENCIA(z<-3)' if emergencia else 'régimen'}: "
                              f"{brazo_actual}->{elegido} (clima {regimen_oficial})")
                    brazo_actual = elegido
                else:
                    motivo = (f"{'emergencia' if emergencia else 'régimen'}: "
                              f"mapa confirma {brazo_actual} (clima {regimen_oficial})")
            else:
                motivo = "mantener (sin cambio de régimen)"

            banco.ejecutar(BRAZOS[brazo_actual](precios, t), precios, t,
                           fechas[t])
            decisiones.append({"fecha": fechas[t], "brazo": brazo_actual,
                               "regimen": regimen_oficial, "motivo": motivo})
            eq = banco.equity
            prev = eq[-2][1] if len(eq) >= 2 else capital_inicial
            ret_real.append(eq[-1][1] / prev - 1.0 if prev > 0 else 0.0)
        else:
            prev = banco.equity[-1][1] if banco.equity else capital_inicial
            nuevo = banco.valuar(precios, t, fechas[t])
            ret_real.append(nuevo / prev - 1.0 if prev > 0 else 0.0)

    mapa_final = {}
    for c in CLIMAS:
        b, s = mejor_brazo(c)
        mapa_final[c] = {"brazo": b,
                         "sharpe_decayed": round(s, 4) if s is not None else None,
                         "peso": round(celdas[(c, b)][2], 1)}
    decisiones.append({"tipo": "mapa_final", "mapa": mapa_final,
                       "cambios_brazo": cambios, "emergencias": emergencias,
                       "regimen_final": regimen_oficial})
    return banco, decisiones
