"""Loop de verificación con criterio de parada a priori — de Boris Cherny.

Doctrina (informe §2.1): "la verificación es lo que casi nadie hace
bien". El loop es producir → observar → comparar → CRITERIO DE PARADA.
Sin verificación el agente se atasca (marca tareas como completas
prematuramente); con verificación corre semanas.

Regla dura de este módulo: el criterio de parada se DECLARA ANTES de
lanzar el loop (va al pre-registro) y el loop para cuando se cumple.
`declarar_criterio` valida los parámetros; sin criterio válido no hay
loop (ValueError).

Criterios soportados:
- rondas_fijas: {"tipo": "rondas_fijas", "n": N} — para tras N rondas.
- sin_mejora: {"tipo": "sin_mejora", "k": K, "max_rondas": M} — para tras
  K iteraciones consecutivas sin mejora estricta (mejora > 0).
- umbral_mejora: {"tipo": "umbral_mejora", "umbral": U,
  "max_rondas": M} — para cuando la mejora acumulada alcanza U.

`correr(producir, observar, comparar, on_paso=None)`:
- producir() -> prop (el candidato)
- observar(prop) -> obs (medición del validador)
- comparar(prop, obs) -> {"mejora": float, "aceptar": bool}
- on_paso(prop, obs, comp, paso) — side effects (audit records, etc.)
Retorna {"parado_por", "iteraciones", "trail"}.
"""

TIPOS = ("rondas_fijas", "sin_mejora", "umbral_mejora")


def declarar_criterio(tipo, **params):
    """Declara y valida el criterio de parada ANTES del loop.

    Va al pre-registro: la parada es una decisión a priori, no un
    juicio post-hoc.
    """
    if tipo not in TIPOS:
        raise ValueError(f"criterio desconocido: {tipo!r} (usar {TIPOS})")
    if tipo == "rondas_fijas":
        n = params.get("n")
        if not isinstance(n, int) or n < 0:
            raise ValueError("rondas_fijas requiere n entero >= 0")
        return {"tipo": tipo, "n": n}
    if tipo == "sin_mejora":
        k, m = params.get("k"), params.get("max_rondas")
        if not isinstance(k, int) or k <= 0:
            raise ValueError("sin_mejora requiere k entero > 0")
        if not isinstance(m, int) or m <= 0:
            raise ValueError("sin_mejora requiere max_rondas entero > 0"
                             " (tope de seguridad)")
        return {"tipo": tipo, "k": k, "max_rondas": m}
    # umbral_mejora
    u, m = params.get("umbral"), params.get("max_rondas")
    if not isinstance(u, (int, float)) or u <= 0:
        raise ValueError("umbral_mejora requiere umbral > 0")
    if not isinstance(m, int) or m <= 0:
        raise ValueError("umbral_mejora requiere max_rondas entero > 0")
    return {"tipo": tipo, "umbral": float(u), "max_rondas": m}


class LoopVerificacion:
    """producir → observar → comparar → parar (criterio a priori)."""

    def __init__(self, criterio):
        self.criterio = dict(criterio)
        if self.criterio.get("tipo") not in TIPOS:
            raise ValueError("criterio no declarado con declarar_criterio")
        self.trail = []
        self.iteraciones = 0

    def correr(self, producir, observar, comparar, on_paso=None,
               tope_seguridad=100000):
        tipo = self.criterio["tipo"]
        sin_mejora = 0
        mejora_acum = 0.0
        parado_por = "tope_seguridad"
        while True:
            if self.iteraciones >= tope_seguridad:
                parado_por = "tope_seguridad"
                break
            if (tipo == "rondas_fijas"
                    and self.iteraciones >= self.criterio["n"]):
                parado_por = f"rondas_fijas n={self.criterio['n']}"
                break
            if (tipo in ("sin_mejora", "umbral_mejora")
                    and self.iteraciones >= self.criterio["max_rondas"]):
                parado_por = (f"max_rondas"
                              f" {self.criterio['max_rondas']}")
                break
            prop = producir()
            obs = observar(prop)
            comp = comparar(prop, obs) or {}
            mejora = float(comp.get("mejora", 0.0))
            aceptado = bool(comp.get("aceptar", False))
            self.iteraciones += 1
            paso = {"iter": self.iteraciones,
                    "mejora": round(mejora, 6),
                    "aceptado": aceptado}
            self.trail.append(paso)
            if on_paso is not None:
                on_paso(prop, obs, comp, paso)
            if mejora > 0:
                sin_mejora = 0
                mejora_acum += mejora
            else:
                sin_mejora += 1
            if tipo == "sin_mejora" and sin_mejora >= self.criterio["k"]:
                parado_por = f"sin_mejora k={self.criterio['k']}"
                break
            if (tipo == "umbral_mejora"
                    and mejora_acum >= self.criterio["umbral"]):
                parado_por = (f"umbral_mejora"
                              f" {self.criterio['umbral']}")
                break
        return {"parado_por": parado_por,
                "iteraciones": self.iteraciones,
                "trail": list(self.trail)}
