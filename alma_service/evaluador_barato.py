"""Evaluador barato — el gate del ruteo por tier (idea 1 de la revisión 7/10).

Filosofía: lo determinista primero (US$0 siempre), el juez con modelo solo
cuando lo determinista no alcanza y solo si alguien lo configura.

Se enchufa directo al hook de ruteo:
    from alma_service.ruteo import modelo_escalado
    from alma_service.evaluador_barato import EvaluadorBarato
    ev = EvaluadorBarato()
    modelo = modelo_escalado(tarea, salida_barata, ev)  # "gpt-4o" o None

Semántica: aprueba(salida) True = el barato alcanza, quedarse.
False = escalar al tier caro. Fail-closed en las dos direcciones:
- sin evaluador, ruteo no escala (ver ruteo.necesita_escalado);
- con evaluador roto (el juez con modelo falla), el juez se abstiene y
  vale el veredicto determinista: nunca se autoriza gasto por un error.

Los verificadores deterministas son conservadores a propósito: solo
reprueban basura evidente (vacío, truncado, desborde, formato roto).
Un falso rechazo escala de más y quema plata; un falso aprobado deja
pasar algo mediocre pero barato. El sesgo elegido es no quemar.
"""

import json


# -- verificadores deterministas (US$0) ------------------------------------

def no_vacia(salida):
    """Reprueba salidas vacías o solo espacios."""
    return isinstance(salida, str) and len(salida.strip()) > 0


def dentro_de_cota(salida, min_chars=1, max_chars=20000):
    """Reprueba truncados (muy corto) y desbordes (muy largo).

    Las cotas son parámetros, no constantes mágicas: cada tarea define
    las suyas. El default solo atrapa lo patológico.
    """
    if not isinstance(salida, str):
        return False
    n = len(salida)
    return min_chars <= n <= max_chars


def formato_esperado(salida, formato=None):
    """Reprueba formato roto cuando el llamador declara el esperado.

    formato="json": la salida tiene que parsear como JSON.
    formato=None (default): no se asume nada, siempre aprueba.
    """
    if formato is None:
        return True
    if formato == "json":
        try:
            json.loads(salida)
            return True
        except (ValueError, TypeError):
            return False
    raise ValueError(f"formato desconocido: {formato!r}")


VERIFICADORES_DEFAULT = (no_vacia, dentro_de_cota)


# -- el evaluador ------------------------------------------------------------

class EvaluadorBarato:
    """Gate barato: deterministas primero, juez con modelo después (opt-in).

    juez: callable opcional (salida, contexto) -> bool. Se consulta SOLO si
    todos los verificadores deterministas aprobaron. Si el juez falla, se
    abstiene y vale el veredicto determinista (fail-closed: sin gasto por
    error). contexto es un dict opcional (ej: {"pregunta": ...}) que viaja
    desde aprueba() hasta el juez.
    """

    def __init__(self, verificadores=None, juez=None, formato=None,
                 min_chars=1, max_chars=20000):
        self.verificadores = list(verificadores or VERIFICADORES_DEFAULT)
        self.juez = juez
        self.formato = formato
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.rechazos = {"determinista": 0, "juez": 0, "aprobadas": 0}

    def _determinista(self, salida):
        if not no_vacia(salida):
            return False
        if not dentro_de_cota(salida, self.min_chars, self.max_chars):
            return False
        if not formato_esperado(salida, self.formato):
            return False
        for v in self.verificadores:
            if v in (no_vacia, dentro_de_cota):
                continue  # ya evaluados arriba con las cotas configuradas
            if not v(salida):
                return False
        return True

    def aprueba(self, salida, contexto=None):
        """True = el tier barato alcanza. False = escalar."""
        if not self._determinista(salida):
            self.rechazos["determinista"] += 1
            return False
        if self.juez is not None:
            try:
                veredicto = self.juez(salida, contexto)
            except Exception:
                veredicto = True  # el juez se abstiene; vale lo determinista
            if not bool(veredicto):
                self.rechazos["juez"] += 1
                return False
        self.rechazos["aprobadas"] += 1
        return True

    def __call__(self, salida, contexto=None):
        return self.aprueba(salida, contexto)

    def resumen(self):
        total = sum(self.rechazos.values())
        return {"evaluadas": total, **dict(self.rechazos)}


# -- medición del propio evaluador (estilo EXP, US$0) -------------------------

def medir(evaluador, pares):
    """Tasa de acuerdo del evaluador sobre pares o ternas.

    pares: (salida, deberia_aprobar) o (salida, contexto, deberia_aprobar).
    Mide al gate, no al modelo: cuántas veces el evaluador decide lo mismo
    que el label. Reporta acuerdo total y falsos rechazos (los que escalan
    de más y queman plata).
    """
    ok = 0
    falsos_rechazos = 0
    for item in pares:
        if len(item) == 3:
            salida, contexto, deberia_aprobar = item
        else:
            (salida, deberia_aprobar), contexto = item, None
        decision = bool(evaluador(salida, contexto))
        if decision == bool(deberia_aprobar):
            ok += 1
        elif not decision and deberia_aprobar:
            falsos_rechazos += 1
    n = len(pares)
    return {
        "n": n,
        "acuerdo": round(ok / n, 4) if n else 0.0,
        "falsos_rechazos": falsos_rechazos,
        "tasa_falso_rechazo": round(falsos_rechazos / n, 4) if n else 0.0,
    }
