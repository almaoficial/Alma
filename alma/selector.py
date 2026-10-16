"""Architecture Selector — la política π (sección 8 del informe).

Es EL objeto de aprendizaje del sistema: un bandit independiente por
clase con Thompson sampling sobre posteriors Beta del reward normalizado
en [0,1] (reward = 0.75*éxito + 0.25*eficiencia, ver evaluator.py).

El reward continuo se incorpora como pseudo-observación Bernoulli
(alpha += r, beta += 1 - r): práctica estándar para bandits con rewards
acotados, documentada aquí como decisión de diseño, no como teorema.

- select(clase, rng): Thompson sampling (exploración durante aprendizaje).
- select_greedy(clase): argmax de la media posterior (evaluación).
- update(clase, arch_id, reward): actualización bayesiana conjugada, barata.
- snapshot()/restore(): para el rollback de los safety gates.
"""

import copy
import random

from .registry import list_archs

PRIOR_ALPHA = 1.0
PRIOR_BETA = 1.0


class BanditPorClase:
    """Un bandit Beta-Bernoulli por clase de problema."""

    def __init__(self, arch_ids=None):
        self.arch_ids = arch_ids or list_archs()
        self.alpha = {a: PRIOR_ALPHA for a in self.arch_ids}
        self.beta = {a: PRIOR_BETA for a in self.arch_ids}
        self.pulls = {a: 0 for a in self.arch_ids}

    def select(self, rng):
        """Thompson sampling: samplea cada posterior y elige el máximo."""
        muestras = {
            a: rng.betavariate(self.alpha[a], self.beta[a]) for a in self.arch_ids
        }
        return max(self.arch_ids, key=lambda a: muestras[a])

    def select_greedy(self):
        """Explotación pura: la media posterior más alta. Para evaluación."""
        return max(self.arch_ids, key=lambda a: self.mean(a))

    def update(self, arch_id, reward):
        """Actualización conjugada con reward en [0,1]."""
        if arch_id not in self.alpha:
            raise KeyError(f"arquitectura desconocida: {arch_id}")
        r = max(0.0, min(1.0, float(reward)))
        self.alpha[arch_id] += r
        self.beta[arch_id] += 1.0 - r
        self.pulls[arch_id] += 1

    def mean(self, arch_id):
        a, b = self.alpha[arch_id], self.beta[arch_id]
        return a / (a + b)

    def means(self):
        return {a: round(self.mean(a), 4) for a in self.arch_ids}

    def total_pulls(self):
        return sum(self.pulls.values())

    def posterior_gap(self):
        """Brecha entre las dos mejores medias: chica = incertidumbre alta."""
        ordenadas = sorted((self.mean(a) for a in self.arch_ids), reverse=True)
        return ordenadas[0] - ordenadas[1] if len(ordenadas) > 1 else 0.0


class SelectorArquitecturas:
    """π: dict clase → BanditPorClase. Priors uniformes (no sabe nada al inicio)."""

    def __init__(self, clases=None, arch_ids=None):
        self.clases = list(clases) if clases else []
        self.arch_ids = arch_ids or list_archs()
        self.bandits = {}

    def _bandit(self, clase):
        if clase not in self.bandits:
            self.bandits[clase] = BanditPorClase(self.arch_ids)
            if clase not in self.clases:
                self.clases.append(clase)
        return self.bandits[clase]

    def select(self, clase, rng=None):
        rng = rng or random.Random()
        return self._bandit(clase).select(rng)

    def select_greedy(self, clase):
        return self._bandit(clase).select_greedy()

    def update(self, clase, arch_id, reward):
        self._bandit(clase).update(arch_id, reward)

    def means(self, clase):
        return self._bandit(clase).means()

    def snapshot(self):
        """Foto profunda para rollback."""
        return copy.deepcopy({"bandits": self.bandits, "clases": self.clases})

    def restore(self, snap):
        self.bandits = copy.deepcopy(snap["bandits"])
        self.clases = list(snap["clases"])
