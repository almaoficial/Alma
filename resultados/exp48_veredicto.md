# ALMA-EXP48 — Veredicto: PASS (fase mock)

**Fecha:** 2026-09-27 ~15:15 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Pre-registro:** `resultados/exp48-20260927/preregistro.json` (escrito antes de correr)

## Qué se testea

El problema que dejó EXP47: los misfires del skip escalaron a ~37% (14/38)
— el umbral fijo de soporte (≥2 victorias) se alcanza con victorias ruidosas
y el brazo de la skill se vuelve stale.

**Variante elegida: (a) re-validación barata.** Descartada (b) umbral
endurecido con el horizonte: endurecer el umbral ataca las victorias ruidosas
pero no la staleness (el brazo deja de matchear el bloque actual); la
re-validación mide evidencia fresca del bloque en curso, el antídoto directo
contra un brazo stale. Un solo moving part respecto al tratamiento "skip" de
EXP47: el gate de confirmación.

**Diseño:** control = tratamiento "skip" de EXP47 verbatim (misma función
importada de `run_experiment47.py`), mismo stream de 24 bloques bit-idéntico,
réplicas pareadas con RNG común. Tratamiento ("skip-confirm"): idéntico,
salvo que antes de saltar se gasta 1 item (q=0) en re-validación — se miden
los 4 brazos (seeds de oráculo idénticas a las del Q1 del control), la política
juega el brazo de la skill (costo honesto = 1 item). Se confirma ssi
reward(skill_arm) == 1.0. Si confirma: skip en items 1–9 sin probe. Si no
confirma: probe completo en items 1–9 (Q1'=(1,2,3), Q2=(6,7), Thompson en el
resto), con la observación del item 0 ya incorporada a la historia.

## Criterio pre-registrado (dos partes)

- (1) tasa de misfires del tratamiento < 14/38 (~0,368, EXP47), con
  n_skips_tratamiento > 0. Definición operativa de misfire idéntica a EXP47:
  en un bloque saltado (confirmado), el brazo de la skill no es el mejor
  ex post (accuracy sobre los 10 items con RNG común).
- (2) media sobre réplicas pareadas de regret(skip-confirm) − regret(skip) < 0
  (misma vara que EXP46/47).
- PASS ssi (1) y (2).

## Números

| Réplica | efecto | reg control | reg trat | skips ctrl (mis) | skips trat (mis) | conf int/ok/no |
|---|---|---|---|---|---|---|
| 0 | +4,00 | 81,0 | 85,0 | 9 (3) | 8 (3) | 9/8/1 |
| 1 | −1,00 | 87,0 | 86,0 | 5 (1) | 3 (0) | 4/3/1 |
| 2 | −2,00 | 96,0 | 94,0 | 7 (4) | 6 (3) | 9/6/3 |
| 3 | −6,00 | 102,0 | 96,0 | 8 (3) | 6 (3) | 8/6/2 |
| 4 | −1,00 | 83,0 | 82,0 | 9 (3) | 4 (0) | 7/4/3 |

**Efecto medio: −1,20 → (2) SÍ** (−1,20 < 0).
**Misfires tratamiento: 9/27 (tasa 0,333) vs EXP47 14/38 (0,368) → (1) SÍ.**
Misfires control (sanidad): 14/38 (0,368) — reproduce EXP47 exacto.
Confirmaciones: 37 intentos / 27 confirmadas / 10 rechazadas.
Regret medio: control 89,80 · tratamiento 88,60 · mejor fija 84,20.
Reproducibilidad del control vs EXP47 (bit-idéntico): **True** — el control es
literalmente la misma función sobre el mismo stream.

Detalle de saltos y diagnóstico por bloque (rep 0):
`resultados/exp48-20260927/report.json`.

## Honestidad incómoda

1. **El PASS de (2) lo carga una sola réplica.** Sin rep 3 (−6,00), el efecto
   medio sería 0,00 (+4 −1 −2 −1) y (2) fallaría. Patrón ya visto en
   EXP45/46/47: el efecto vive en 1–2 réplicas de 5. La media pre-registrada
   pasa, pero la fragilidad entre réplicas no se movió.
2. **La baja de misfires es modesta: 0,368 → 0,333 (−3,5 pp).** El gate
   rechazó 10/37 saltos candidatos; de los 27 confirmados, 9 igual misfirearon.
   La regla "confirma ssi hit" es débil por construcción: un brazo stale al
   0,5 confirma el 50% de las veces con 1 solo item. La re-validación barata
   filtra algo, pero 1 item de evidencia no alcanza para distinguir un brazo
   stale de uno bueno con ruido.
3. **Los rechazos también cuestan.** Los 10 bloques rechazados pagaron 1 item
   jugado con el brazo de la skill (a veces el equivocado) + el probe
   completo. Y la regla de hit rechaza un brazo bueno al 0,7 el 30% de las
   veces: parte de los 10 rechazos fueron skills sanas asesinadas por el gate.
4. **No mueve el diagnóstico estructural.** Tratamiento 88,60 vs mejor fija
   84,20: ~4,4 puntos abajo. Igual que en toda la línea: ninguna maquinaria
   con exploración le gana sistemáticamente a la mejor fija en un mundo que
   rota; el gate achica el daño, no revierte la aritmética.
5. **Condición de alcance intacta:** todo ocurre en el mundo construido con
   recurrencia garantizada. En el feed real (rotación 8/8) el mecanismo
   seguiría sin activarse ni una vez.

## Veredicto

**PASS.** Las dos partes pre-registradas se cumplen: los misfires bajan de
0,368 a 0,333 y el efecto medio es −1,20. La re-validación barata funciona,
pero poco: el gate de 1 item es demasiado ruidoso para distinguir staleness
de mala suerte, y el efecto agregado sigue siendo frágil entre réplicas.

## Recomendación

La línea de skills acumula cuatro veredictos seguidos con el mismo perfil:
efecto real, chico (~1–3% del regret), frágil entre réplicas, y ~4–7 puntos
abajo de la mejor fija. El anti-misfire ayudó en la dirección correcta pero
no cambió el perfil. Si la línea continúa, el próximo mock debería probar la
variante (b) descartada acá — umbral de soporte que se endurezca con el
horizonte — o, mejor, dejar de pulir el gate y preguntar si el problema es
la firma ruidosa (el 2/10 de ruido por bloque contamina firma y victorias).
Si ninguna de esas mueve el perfil, cerrar la línea: el techo es del mundo,
no del mecanismo.

No correr fase con key: el mock responde la pregunta; medir con plata lo que
ya se diagnosticó gratis no tiene sentido.
