"""Minería de debilidades por firmas deterministas — de Self-Harness §3.2.

El paper agrupa fallos por FIRMA de fallo verificador-anclada con
coincidencia EXACTA, deliberadamente sin agrupación difusa por LLM,
para no confundir síntomas superficiales con mecanismos reutilizables.

Este módulo hace lo mismo para ALMA, en dos niveles:

1. Nivel meta (metaloop): firma de cada keep/revert histórico =
   (parámetro_mutado, dirección, veredicto). El miner describe qué
   direcciones fallaron antes; NO prescribe mutaciones (principio del
   paper: el paquete de evidencia no prescribe la edición — lección del
   EXP58: una heurística que atribuye y prescribe es peor que el azar).

2. Nivel servicio (revisión): firma de cada feedback negativo =
   (clase, arch_id, tramo_reward). Coincidencia exacta, US$0, sin LLM.

Todo es determinista y auditable. Sin LLM en ningún punto.
"""

from collections import Counter


def firma_meta(clave_mutada, valor_anterior, valor_nuevo, veredicto):
    """Firma de un evento keep/revert del metaloop.

    veredicto: "keep" | "revert_train" | "revert_ho" | ...
    dirección: "sube" | "baja" | "cambia" (numérico) u "otro".
    """
    try:
        a, b = float(valor_anterior), float(valor_nuevo)
        direccion = "sube" if b > a else ("baja" if b < a else "igual")
    except (TypeError, ValueError):
        direccion = "otro" if valor_anterior != valor_nuevo else "igual"
    return (str(clave_mutada), direccion, str(veredicto))


def firma_feedback(clase, arch_id, reward):
    """Firma de un feedback del servicio. tramo: fallo si reward < 0.5."""
    try:
        tramo = "fallo" if float(reward) < 0.5 else "ok"
    except (TypeError, ValueError):
        tramo = "desconocido"
    return (str(clase), str(arch_id), tramo)


class MineroDebilidades:
    """Acumula firmas exactas y las clusteriza por coincidencia.

    El cluster es la firma misma (tupla hashable): no hay centroides ni
    similitud difusa. `clusters()` retorna los top-N ordenados por
    soporte, cada uno con firma, n y fracción.
    """

    def __init__(self):
        self._conteo = Counter()
        self._total = 0

    def alimentar(self, firma):
        self._conteo[tuple(firma)] += 1
        self._total += 1

    def alimentar_varias(self, firmas):
        for f in firmas:
            self.alimentar(f)

    def clusters(self, n=5, minimo_soporte=2):
        """Top-N clusters con soporte >= minimo_soporte."""
        out = []
        for firma, c in self._conteo.most_common(n):
            if c < minimo_soporte:
                break
            out.append({
                "firma": list(firma),
                "n": c,
                "fraccion": round(c / self._total, 4) if self._total else 0.0,
            })
        return out

    def paquete_evidencia(self, n=5, minimo_soporte=2):
        """Evidence bundle (Self-Harness §3.2): describe, NO prescribe.

        Incluye la advertencia explícita: estos clusters son contexto
        para audit records, no instrucciones de qué mutar.
        """
        return {
            "tipo": "paquete_evidencia",
            "clusters": self.clusters(n=n, minimo_soporte=minimo_soporte),
            "total_firmas": self._total,
            "advertencia": ("descriptivo, no prescriptivo: los clusters"
                            " auditan contexto, no dirigen mutaciones"),
        }

    def estado(self):
        return {"total_firmas": self._total,
                "firmas_distintas": len(self._conteo)}


# -- puente con el event log unificado (fase 2.2) ---------------------------
# Firmas sobre OPERACIÓN REAL del servicio, no sobre experimentos.
# Contrato DISENO_PAQUETE_UNICO.md §4.2: el minero lee solo eventos con
# reward medido y agrupa por firma exacta
# (firma_regimen, brazo_elegido, tramo_reward). Describe, no prescribe.


def firma_decision(firma_regimen, brazo, reward):
    """Firma de una decisión del servicio. tramo: fallo si reward < 0.5."""
    try:
        tramo = "fallo" if float(reward) < 0.5 else "ok"
    except (TypeError, ValueError):
        tramo = "desconocido"
    return (str(firma_regimen), str(brazo), tramo)


def minar_decisiones(filas, minimo_soporte=2):
    """Paquete de evidencia desde decisiones del event log.

    `filas`: dicts con firma_regimen, brazo_elegido, reward (como los
    que retorna EventLog.decisiones()). Solo entran filas con reward
    medido — sin señal no hay firma.
    """
    m = MineroDebilidades()
    m.alimentar_varias([
        firma_decision(f.get("firma_regimen"), f.get("brazo_elegido"),
                       f.get("reward"))
        for f in filas if f.get("reward") is not None
    ])
    return m.paquete_evidencia(minimo_soporte=minimo_soporte)
