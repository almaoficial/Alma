"""Ruteo por tier — paso 3 del protocolo anti-quema.

Un solo punto de decisión para elegir modelo por tarea:
barato por default, caro SOLO si el evaluador barato dice que la salida
del barato no sirve.

Tiers (modelos que ALMA puede llamar hoy vía VaultBackend):
  barato: gpt-4o-mini  (US$0.15/1M in, US$0.60/1M out)
  caro:   gpt-4o       (US$2.50/1M in, US$10.00/1M out)

El caro sale ~17x el barato por token de entrada: cada llamado que no
escala es plata que no se quema.

Reglas:
- elegir_modelo() devuelve el tier barato, siempre. `forzar="..."` es el
  pin explícito para experimentos controlados (el pin queda visible como
  decisión, no como string hardcodeado perdido en el código).
- necesita_escalado(salida_barata, evaluador) es True ssi el evaluador
  barato reprueba la salida del barato. `evaluador` es un callable que
  recibe la salida y devuelve True si la aprueba, False si no.
  Sin evaluador no se escala: fail-closed hacia lo barato.
- modelo_escalado() devuelve el nombre del tier caro cuando corresponde
  escalar, None cuando no.

Nota honesta: el evaluador barato como componente (foco intensivo) aún no
existe en código. El hook está listo para cuando llegue; mientras tanto,
el default es no escalar. Cuando exista backend de OpenRouter, el tier
barato natural es DeepSeek :free (US$0).
"""

from alma.backends import PRECIOS

TIER_BARATO = "gpt-4o-mini"
TIER_CARO = "gpt-4o"

TIERS = {
    "barato": {"modelo": TIER_BARATO,
               "precio_in": PRECIOS[TIER_BARATO][0],
               "precio_out": PRECIOS[TIER_BARATO][1]},
    "caro": {"modelo": TIER_CARO,
             "precio_in": PRECIOS[TIER_CARO][0],
             "precio_out": PRECIOS[TIER_CARO][1]},
}


def elegir_modelo(tarea=None, forzar=None):
    """Modelo para una tarea. Barato por default; `forzar` lo pinea.

    `tarea` queda reservado para ruteo por características de la tarea
    cuando haya evidencia de qué tier rinde por clase (hoy: siempre barato).
    """
    if forzar is not None:
        return forzar
    return TIER_BARATO


def necesita_escalado(salida_barata, evaluador_barato):
    """True ssi el evaluador barato reprueba la salida del tier barato.

    Sin evaluador no se escala: el default fail-closed es no gastar.
    """
    if evaluador_barato is None:
        return False
    try:
        aprobada = bool(evaluador_barato(salida_barata))
    except Exception:
        # Un evaluador roto no autoriza gasto: se queda en barato y el
        # llamador decide con su propio criterio.
        return False
    return not aprobada


def modelo_escalado(tarea, salida_barata, evaluador_barato):
    """Tier caro si hay que escalar, None si el barato alcanza."""
    if necesita_escalado(salida_barata, evaluador_barato):
        return TIER_CARO
    return None
