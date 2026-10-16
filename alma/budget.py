"""Budget Manager — núcleo FIJO (sección 9 del informe).

Presupuestos separados para resolución / selección / experimentación.
Sin presupuestos fijos, el meta-nivel canibaliza al nivel objeto
(sección 5.4 del informe). Exceder un presupuesto corta con excepción:
no hay "un poco más".
"""

RESOLUCION = "resolucion"
SELECCION = "seleccion"
EXPERIMENTACION = "experimentacion"

BUCKETS = (RESOLUCION, SELECCION, EXPERIMENTACION)


class BudgetExceeded(Exception):
    """Se intentó gastar más del presupuesto asignado a un bucket."""

    def __init__(self, bucket, limite, gastado, intento):
        self.bucket = bucket
        self.limite = limite
        self.gastado = gastado
        self.intento = intento
        super().__init__(
            f"presupuesto excedido en '{bucket}': "
            f"límite ${limite:.4f}, gastado ${gastado:.4f}, intento ${intento:.4f}"
        )


class BudgetManager:
    """Controla gasto en USD por bucket. Todo gasto pasa por charge()."""

    def __init__(self, limites):
        """limites: dict bucket -> USD. Buckets desconocidos → ValueError."""
        for b in limites:
            if b not in BUCKETS:
                raise ValueError(f"bucket desconocido: {b!r}")
        self.limites = dict(limites)
        self.gastado = {b: 0.0 for b in BUCKETS}

    def charge(self, bucket, monto_usd, descripcion=""):
        """Carga un gasto. Si excede el límite, corta con BudgetExceeded."""
        if bucket not in BUCKETS:
            raise ValueError(f"bucket desconocido: {bucket!r}")
        if monto_usd < 0:
            raise ValueError("el monto no puede ser negativo")
        limite = self.limites.get(bucket, 0.0)
        nuevo = self.gastado[bucket] + monto_usd
        # Tolerancia de punto flotante: 1e-9
        if nuevo > limite + 1e-9:
            raise BudgetExceeded(bucket, limite, self.gastado[bucket], monto_usd)
        self.gastado[bucket] = nuevo
        return nuevo

    def remaining(self, bucket):
        return self.limites.get(bucket, 0.0) - self.gastado[bucket]

    def report(self):
        return {
            b: {
                "limite_usd": self.limites.get(b, 0.0),
                "gastado_usd": self.gastado[b],
                "restante_usd": self.remaining(b),
            }
            for b in BUCKETS
        }
