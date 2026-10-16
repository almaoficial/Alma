"""Safety Gates — núcleo FIJO (sección 9 del informe).

Tres garantías mínimas:

1. Separación de privilegios: el selector y el experimentador reciben una
   vista de SOLO LECTURA del Experience Store (ReadOnlyStore). Intentar
   escribir corta con PrivilegeError. El evaluador, el store y los
   presupuestos no son modificables por el que aprende (análogo a la
   Gödel Machine: el que se modifica no puede reescribir su verificador).

2. Núcleo versionado: registry, evaluator y taxonomía tienen versiones
   fijas. verificar_nucleo() detecta si algo del sustrato de verdad cambió.

3. Rollback: auditar_no_regresion() compara el regret por clase entre la
   política vieja y la nueva en validación; si alguna clase empeora más
   de ε, se restaura el snapshot del selector.
"""

from . import registry
from . import evaluator as evaluator_mod
from . import featurizer


class PrivilegeError(Exception):
    pass


class ReadOnlyStore:
    """Vista de solo lectura del Experience Store para el selector/experimentador."""

    def __init__(self, store):
        self._store = store

    def read_all(self):
        return self._store.read_all()

    def __len__(self):
        return len(self._store)

    def verify_chain(self):
        return self._store.verify_chain()

    def append(self, row):
        raise PrivilegeError(
            "el selector/experimentador no puede escribir en el Experience Store "
            "(separación de privilegios: solo el harness de ejecución agrega filas)"
        )


class SafetyGates:
    def __init__(self):
        self._nucleo = {
            "registry": registry.REGISTRY_VERSION,
            "evaluator": evaluator_mod.EVALUATOR_VERSION,
            "taxonomia": featurizer.TAXONOMY_VERSION,
        }

    def verificar_nucleo(self):
        """True si el sustrato de verdad no fue modificado."""
        actual = {
            "registry": registry.REGISTRY_VERSION,
            "evaluator": evaluator_mod.EVALUATOR_VERSION,
            "taxonomia": featurizer.TAXONOMY_VERSION,
        }
        return actual == self._nucleo

    def auditar_no_regresion(self, regret_viejo, regret_nuevo, epsilon=0.05):
        """Compara regret por clase (menor = mejor).

        regret_viejo/nuevo: dict clase -> regret medio.
        Devuelve (ok: bool, detalle: str). Si alguna clase empeora más de
        ε, ok=False y el llamador debe hacer rollback del selector.
        """
        problemas = []
        for clase, nuevo in regret_nuevo.items():
            viejo = regret_viejo.get(clase)
            if viejo is None:
                continue
            if nuevo - viejo > epsilon:
                problemas.append(
                    f"{clase}: regret {viejo:.3f} → {nuevo:.3f} "
                    f"(empeora {nuevo - viejo:.3f} > ε={epsilon})"
                )
        if problemas:
            return False, "REGRESIÓN: " + "; ".join(problemas)
        return True, "sin regresión por clase (todas dentro de ε)"

    def rollback_selector(self, selector, snapshot):
        """Restaura el selector a un snapshot previo."""
        selector.restore(snapshot)
