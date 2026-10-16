"""Detector de heterogeneidad — EXP68.

Meta-regla aditiva sobre la política con probe (no toca el scaffold
vigente): observa el veredicto del probe MEDIDO bloque a bloque. Si el
probe es unánime (mismo ganador estricto) K bloques seguidos, encoje la
exploración: compromete el brazo unánime y saltea probe+Thompson, con
spot-checks cada J bloques para no quedar ciego ante un flip del mundo
(lección EXP9: el mundo puede flipear).

Nace de la lección del EXP66 (stand down 27/9): el FAIL del EXP62 no
tenía defecto aprendible — el mundo era single-dominante y el costo de
exploración fue el precio de verificar que no había nada que descubrir.
Este detector es la respuesta: el loop aprende cuándo no hay nada que
descubrir, sin romper la adaptación donde sí lo hay (validación a dos
puntas, EXP68).

Histéresis deliberada: entrar exige unanimidad estricta repetida (caro
de activar por ruido); salir exige contradicción estricta en el
spot-check (los empates no expulsan). Puro, determinista, sin LLM.

Hallazgo de calibración (EXP68, validado a dos puntas): el veredicto
tiene que ser el probe MEDIDO (argmax estricto de las medias de los
ítems que la política efectivamente midió), NUNCA el brazo
comprometido del posterior (fav): con decay=0,5 el posterior se
enganchó al brazo equivocado (Δ=-34 en calibración) y en mundos
heterogéneos es ciego a regímenes por construcción.

Convenciones con el harness (EXP68, validadas):
- Solo los bloques CON probe alimentan la racha. Un bloque saltado
  (probe_obs None) no la extiende ni la reinicia: no hay veredicto
  (no se llama a registrar_veredicto).
- Un empate en el probe (sin ganador estricto) REINICIA la racha:
  "K bloques seguidos unánimes" se lee en sentido estricto
  (registrar_veredicto con ganador=None).
- El spot-check exige margen (>=MARGEN_SALIDA items de ventaja) para
  salir: la contradicción estricta en 3 items ocurre ~24% por azar
  cuando el comprometido sigue siendo el mejor; el margen la baja
  a ~5% manteniendo la detección de flips reales.
"""

EXPLORAR = "explorar"
ENCOGIDO = "encogido"

# K/J congelados por el pre-registro EXP68 (validación a dos puntas
# PASS, 2026-09-27). No tunear: cualquier cambio requiere pre-registro
# nuevo (DISENO_PAQUETE_UNICO.md, fase 2.4).
K_EXP68 = 3
J_EXP68 = 3

# Margen de salida del spot-check: otro brazo debe superar al
# comprometido por al menos esta cantidad de items (enteros) en el
# spot-check para restaurar la exploración. Calibrado en EXP68:
# margen 2 en 3 items => ~5% de falsas salidas cuando el comprometido
# sigue siendo el mejor, con detección útil de flips reales.
MARGEN_SALIDA = 2


def ganador_estricto(medias):
    """Brazo con media estrictamente mayor que todos los demás.

    Retorna None si hay empate en el primer puesto (sin veredicto).
    """
    orden = sorted(medias.items(), key=lambda kv: kv[1], reverse=True)
    if len(orden) >= 2 and orden[0][1] == orden[1][1]:
        return None
    return orden[0][0]


class DetectorHeterogeneidad:
    """State machine del detector. Pura: sin RNG, sin I/O, sin LLM."""

    def __init__(self, K=4, J=3):
        if K < 2:
            raise ValueError("K debe ser >= 2")
        if J < 2:
            raise ValueError("J debe ser >= 2")
        self.K = K
        self.J = J
        self.modo = EXPLORAR
        self._racha_ganador = None
        self._racha_n = 0
        self.comprometido = None
        self._n_encogido = 0
        self.historial = []  # auditoría de eventos

    # -- modo explorar --------------------------------------------------------

    def registrar_veredicto(self, bloque, ganador):
        """Veredicto de un bloque con probe (modo explorar).

        ganador: brazo ganador estricto del probe, o None si hubo empate.
        Solo un ganador estricto igual al de la racha la extiende;
        cualquier otra cosa (ganador distinto o empate) la reinicia.
        Al alcanzar K, encoje: compromete el brazo y pasa a ENCOGIDO.
        En modo ENCOGIDO no hace nada (ahí mandan los spot-checks).
        """
        if self.modo != EXPLORAR:
            return
        if ganador is not None and ganador == self._racha_ganador:
            self._racha_n += 1
        elif ganador is not None:
            self._racha_ganador = ganador
            self._racha_n = 1
        else:
            self._racha_ganador = None
            self._racha_n = 0
        if self._racha_n >= self.K:
            self.modo = ENCOGIDO
            self.comprometido = self._racha_ganador
            self._n_encogido = 0
            self.historial.append({
                "evento": "encoge", "bloque": bloque,
                "brazo": self.comprometido, "racha": self._racha_n,
            })

    # -- modo encogido --------------------------------------------------------

    def iniciar_bloque_encogido(self):
        """Al inicio de un bloque en modo ENCOGIDO.

        Retorna True si este bloque toca spot-check (cada J bloques).
        """
        if self.modo != ENCOGIDO:
            raise RuntimeError("iniciar_bloque_encogido fuera de ENCOGIDO")
        self._n_encogido += 1
        return self._n_encogido % self.J == 0

    def resolver_spot_check(self, bloque, aciertos):
        """Veredicto del spot-check con histéresis.

        aciertos: dict brazo -> items ganados en el spot-check (enteros).
        El comprometido se mantiene salvo que otro brazo lo supere por
        MARGEN_SALIDA items o más. El margen es lo que hace al spot-check
        un test de hipótesis en vez de una moneda ruidosa: una
        contradicción estricta en 3 items ocurre ~24% por azar cuando el
        comprometido sigue siendo el mejor (calibración EXP68); exigir
        >=2 items la baja a ~5%, manteniendo la detección de flips reales.

        Retorna True si se restaura la exploración completa.
        """
        if self.modo != ENCOGIDO:
            raise RuntimeError("resolver_spot_check fuera de ENCOGIDO")
        c_w = aciertos[self.comprometido]
        contradicho = any(c - c_w >= MARGEN_SALIDA
                          for a, c in aciertos.items()
                          if a != self.comprometido)
        if contradicho:
            self.historial.append({
                "evento": "restaura", "bloque": bloque,
                "brazo": self.comprometido,
                "aciertos": dict(aciertos),
            })
            self.modo = EXPLORAR
            self._racha_ganador = None
            self._racha_n = 0
            self.comprometido = None
            self._n_encogido = 0
            return True
        self.historial.append({"evento": "spot_ok", "bloque": bloque,
                               "brazo": self.comprometido})
        return False

    # -- introspección --------------------------------------------------------

    @property
    def racha(self):
        return (self._racha_ganador, self._racha_n)
