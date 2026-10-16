"""Experimenter — STUB HONESTO (sección 7 del informe, componente 11).

Lo que el informe pide a futuro: proponer configuraciones nuevas con BO /
mutación de grafos cuando ninguna arquitectura del repertorio funciona.

Lo que este prototipo hace (y no más): detectar *dónde* el selector tiene
incertidumbre epistémica alta — posteriors solapadas (gap chico entre las
dos mejores medias con suficientes pulls) o clases sin datos — y reportar
esos casos como *candidatos a experimentación*, con chequeo de presupuesto.

NO inventa arquitecturas. NO modifica el repertorio. Disparar un
experimento real queda como próximo paso, con acto humano versionado.
"""

from .budget import EXPERIMENTACION


class Experimenter:
    def __init__(self, umbral_gap=0.15, min_pulls=5):
        """
        umbral_gap: si la brecha entre las dos mejores medias posteriores
                    es menor, las posteriors están "solapadas".
        min_pulls:  pulls mínimos antes de hablar de incertidumbre (antes
                    es simplemente falta de datos).
        """
        self.umbral_gap = umbral_gap
        self.min_pulls = min_pulls

    def analizar(self, selector, clases):
        """Devuelve la lista de clases candidatas a experimentación."""
        candidatos = []
        for clase in clases:
            bandit = selector.bandits.get(clase)
            if bandit is None or bandit.total_pulls() == 0:
                candidatos.append({
                    "clase": clase,
                    "motivo": "sin datos: el selector nunca probó nada acá",
                    "gap": None,
                    "pulls": 0,
                })
                continue
            pulls = bandit.total_pulls()
            if pulls < self.min_pulls:
                continue  # muy pronto para concluir; no es incertidumbre, es frío
            gap = bandit.posterior_gap()
            if gap < self.umbral_gap:
                candidatos.append({
                    "clase": clase,
                    "motivo": (
                        "incertidumbre epistémica alta: las dos mejores "
                        f"arquitecturas están solapadas (gap={gap:.3f})"
                    ),
                    "gap": round(gap, 4),
                    "pulls": pulls,
                })
        return candidatos

    def puede_experimentar(self, budget):
        """True si queda presupuesto de experimentación."""
        return budget.remaining(EXPERIMENTACION) > 0

    def proponer(self, selector, clases, budget):
        """Stub de la propuesta: reporta candidatos, no crea arquitecturas.

        Devuelve dict con candidatos y una nota explícita de que la
        invención de configuraciones no está implementada.
        """
        if not self.puede_experimentar(budget):
            return {"candidatos": [], "nota": "sin presupuesto de experimentación"}
        return {
            "candidatos": self.analizar(selector, clases),
            "nota": (
                "STUB: este prototipo detecta dónde experimentar, pero no "
                "inventa configuraciones nuevas (problema abierto N3 del "
                "informe). La propuesta real requeriría BO/mutación + canary "
                "y un acto humano versionado."
            ),
        }
