"""Detector de recurrencia — fase 0.

Honestidad estructural del diseño §2.1 (lección EXP44): en un mundo sin
recurrencia, el mecanismo de skills no tiene de qué agarrarse — en el feed
real la categoría dominante rotó en 8/8 transiciones y el efecto fue +6.80
(FAIL). La condición de alcance de los mocks se convierte en una COMPUERTA
del sistema, no en una nota al pie.

El detector mide, sobre una ventana deslizante de firmas recientes, qué
fracción ya había aparecido antes:
    tasa = #{firmas en ventana vistas previamente} / #{firmas en ventana}
- tasa >= umbral → modo "skills": se activa el loop completo
  (prior condicionado, skip endurecido, gate adaptativo).
- tasa < umbral  → modo "adaptativo": Thompson + re-probe (EXP7), sin
  invertir en crear ni curar skills. Explorar ya es caro; no se le suma el
  costo de un loop que no puede rendir.

Nota: trabaja sobre firmas de problemas que el sistema resolvió, no sobre
unidades sin ground truth (el feed además fabrica ~18% de su contenido —
hallazgo del 27/9).
"""

MODO_SKILLS = "skills"
MODO_ADAPTATIVO = "adaptativo"


class DetectorRecurrencia:
    def __init__(self, ventana=20, umbral=0.30):
        if ventana < 1:
            raise ValueError("ventana debe ser >= 1")
        if not 0.0 <= umbral <= 1.0:
            raise ValueError("umbral debe estar en [0,1]")
        self.ventana = int(ventana)
        self.umbral = float(umbral)
        self.historial = []  # firmas en orden de observación

    def observar(self, firma):
        self.historial.append(firma)

    def tasa_recurrencia(self):
        """Fracción de las firmas en la ventana que ya habían aparecido
        antes de su ocurrencia en la ventana."""
        n = len(self.historial)
        if n == 0:
            return 0.0
        inicio = max(0, n - self.ventana)
        ventana = self.historial[inicio:]
        previas = set(self.historial[:inicio])
        vistas = set()
        recurren = 0
        for firma in ventana:
            if firma in previas or firma in vistas:
                recurren += 1
            vistas.add(firma)
        return recurren / len(ventana)

    def modo(self):
        """Compuerta del sistema: 'skills' o 'adaptativo'."""
        return MODO_SKILLS if self.tasa_recurrencia() >= self.umbral \
            else MODO_ADAPTATIVO
