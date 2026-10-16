# ALMA v2 — Especificación corregida (humano en el loop)

Generada por el motor de ALMA (exp 665/668) y corregida por el humano: el punto 3 de la v1
invertía el hallazgo — las BATERÍAS colapsan la varianza, los persistentes son la lotería.

## V2.1 — Baterías como control de varianza (corrige v1-p3)
El motor distingue horizonte corto vs largo por clase de problema.
- Horizonte largo (tareas con deriva / muchas rondas / riesgo de cola): agentes-batería
  descartables — nacen por tarea, recolectan, reportan compacto al centro, mueren.
- Horizonte corto: agentes persistentes (más baratos por llamada).
Justificación: EXP22/23 — las baterías no ahorran costo medio, colapsan la varianza
(persistentes 0,06–0,47 según seed; baterías 0,06–0,10 planas).

## V2.2 — Probe consciente de ruido (v1-p2 revisada)
Antes del compromiso duro, el probe estima el gap entre candidatos.
- Si gap > umbral de ruido → compromiso (la selección funciona: EXP19/20).
- Si gap < umbral → SIN compromiso duro: exploración adaptativa continua con re-probe
  (lección EXP7: el re-probe corrigió 2 de 3 errores sistemáticos).
Justificación: EXP21/EXP6 — con gap 0,12 y 8 pulls, medir no le gana a adaptarse.

## V2.3 — Selección con contradicción TRIZ (v1-p4 revisada)
Antes de elegir brazo, el motor formula la contradicción del problema
(qué parámetro mejora / cuál empeora) y la usa para ordenar los brazos candidatos
que el probe evalúa. La selección sigue siendo el motor (EXP19/20); la contradicción
la enfoca.
Justificación: P5 (TRIZ) + EXP19/20.

## V2.4 — Transferencia sin mapa (noche 26→27/9, EXP21–EXP29)
Decisión de diseño: NO construir mapa de parecido ni fingerprint. La evidencia:
- EXP27: el mapa es una apuesta — cuando acierta, copiar al vecino es lo mejor
  (regret 1,25); cuando erra es catastrófico (21,65 vs 8,90 sin mapa).
  Acierto del probe: 14/16 sin mapa vs 8/16 con mapa.
- EXP29: el gate de distancia que haría seguro al mapa es angosto
  (d ≲ 0,22, ~10% de cobertura, ~74% de precisión). No justifica construir
  fingerprint + mapa + gate todavía.
- EXP28: la unión ingenua (híbrido vecino+global) paga el seguro dos veces.
Mecanismo: para una clase nueva o fina (< 5 experiencias con reward),
el probe evalúa el shortlist mapless = top-2 brazos por frecuencia global
de "mejor brazo de su clase" (sobre clases con ≥5 experiencias).
Orden: frecuencia global desc, desempate por contradicción TRIZ.
El resto no cambia: gap > umbral → compromiso; si no → Thompson adaptativo
restringido al shortlist. La transferencia es un problema de riesgo,
no de información: el shortlist global nunca es catastrófico.
No incluye: fingerprint, mapa de parecido, gate de distancia, copia directa
al vecino (investigación futura si datos reales muestran estructura).

## Alcance de implementación
- Modificar `~/workspace/alma-prototype/servicio/motor.py`: agregar modo batería,
  probe con umbral de ruido, paso de contradicción previo a la selección.
- API compatible: `GET /salud`, `GET /estado`, `POST /resolver`, `POST /feedback`
  siguen funcionando igual. Nuevos parámetros opcionales en `/resolver`:
  `horizonte` ("corto"|"largo"|"auto"), `umbral_ruido` (float, default del preregistro).
- Cada experiencia guarda: brazo, modo (batería/persistente), gap estimado,
  contradicción formulada, decisión de compromiso.
- Tests: extender `chequeo_motor.py`; la puerta `puerta_calidad.sh` debe pasar.
- No tocar credenciales ni logs con secrets. Backend default sigue `demo`;
  `vault` solo con la key del usuario.
