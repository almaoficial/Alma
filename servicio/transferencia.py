"""V2.4 — transferencia sin mapa (mapless).

Para una clase nueva o fina (< UMBRAL_FINA experiencias con reward),
el probe no evalúa todos los brazos: evalúa el shortlist mapless =
top-K brazos por frecuencia global de "mejor brazo de su clase".

Evidencia (noche 26→27/9):
- EXP27: el mapa de parecido es una apuesta — cuando acierta, copiar al
  vecino es lo mejor (regret 1,25); cuando erra es catastrófico
  (21,65 vs 8,90 sin mapa). Acierto del probe: 14/16 sin mapa vs 8/16
  con mapa. La transferencia es un problema de riesgo, no de información.
- EXP28: la unión ingenua (híbrido vecino+global) paga el seguro dos
  veces: 40 vs 24 pulls de probe + selección más ruidosa. No va.
- EXP29: el gate de distancia que haría seguro al mapa es angosto
  (d ≲ 0,22, ~10% de cobertura, ~74% de precisión). No justifica construir
  fingerprint + mapa + gate todavía.

Este módulo es puro (no toca el motor): calcula el shortlist a partir del
store. El enchufe al probe de motor.py queda para la implementación V2.4.
"""

from collections import Counter

# Clase con menos experiencias con reward que esto se trata como "fina".
UMBRAL_FINA = 5
# Una clase vota por su mejor brazo solo si tiene al menos esto.
MIN_EXP_POR_CLASE = 5
# Tamaño del shortlist mapless.
K_SHORTLIST = 2


def mejor_brazo_de_clase(recompensas):
    """recompensas: lista de (arch_id, reward, timestamp).
    Devuelve el arch_id con mayor reward medio, o None si no hay datos.
    Empate → el primero en orden de aparición (determinista)."""
    sumas, n = {}, {}
    orden = []
    for arch_id, reward, _ts in recompensas:
        if arch_id not in sumas:
            sumas[arch_id] = 0.0
            n[arch_id] = 0
            orden.append(arch_id)
        sumas[arch_id] += reward
        n[arch_id] += 1
    if not orden:
        return None
    return max(orden, key=lambda a: sumas[a] / n[a])


def frecuencias_globales(store, brazos):
    """Counter: por cada clase con >= MIN_EXP_POR_CLASE experiencias con
    reward, un voto para su mejor brazo. Solo cuentan brazos conocidos."""
    votos = Counter()
    for clase in store.clases():
        recs = store.recompensas_por_clase(clase)
        if len(recs) < MIN_EXP_POR_CLASE:
            continue
        mejor = mejor_brazo_de_clase(recs)
        if mejor in brazos:
            votos[mejor] += 1
    return votos


def es_clase_fina(store, clase, umbral=UMBRAL_FINA):
    """True si la clase tiene menos de `umbral` experiencias con reward."""
    return len(store.recompensas_por_clase(clase)) < umbral


def shortlist_mapless(store, brazos, k=K_SHORTLIST, orden_desempate=None):
    """Top-k brazos por frecuencia global de mejor-brazo-por-clase.

    orden_desempate: lista opcional de brazos para desempatar igualdades
    (p.ej. el orden de la contradicción TRIZ). Sin votos en el store,
    devuelve los primeros k en el orden dado (nunca falla, nunca vacío
    si hay brazos).
    """
    brazos = list(brazos)
    k = max(1, min(k, len(brazos)))
    votos = frecuencias_globales(store, brazos)
    desempate = list(orden_desempate) if orden_desempate else []
    rank_desempate = {a: i for i, a in enumerate(desempate)}

    def clave(a):
        return (-votos.get(a, 0),
                rank_desempate.get(a, len(desempate)),
                brazos.index(a))

    return sorted(brazos, key=clave)[:k]
