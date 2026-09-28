# ALMA-EXP45 — Veredicto: PASS marginal (fase mock)

**Fecha:** 2026-09-27 ~15:00 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Pre-registro:** `resultados/exp45-20260927/preregistro.json` (escrito antes de correr)

## Qué se testea

Incorporar el mecanismo de Hermes Agent (Nous Research) a ALMA: la
experiencia pasada de un régimen persiste como "skill" reutilizable — el
prior de Thompson arranca condicionado por régimen en vez de ciego.

**Diseño A/B pareado** (único moving part):
- Control: maquinaria EXP44 (probe Q1 + Thompson + re-probe Q2 + Thompson;
  prior warm con olvido 0.5^d, N0=2; probe con contabilidad honesta EXP43).
- Tratamiento: idéntica, salvo que tras el probe Q1 el prior se reconstruye
  condicionado a la firma del régimen (warm olvido solo sobre bloques
  pasados con la misma firma; fallback a ciego si no hay skill).
- Firma = grupo mayoritario entre las categorías de los 3 items del probe.
- Stream construido: 120 items, 12 bloques × 10, 3 regímenes × 4
  recurrencias (orden seed 45, no alternante); 8 items del régimen + 2 de
  ruido por bloque; categorías con frecuencias empíricas del feed real;
  tasas mock calibradas (titular gana en tech/deportes, contexto en dinero).
- RNG común por (réplica, bloque, item, brazo): ambas políticas ven el mismo
  oráculo; 5 réplicas pareadas.

## Números

| Réplica | efecto (reg_skills − reg_control) | reg control | reg skills | mejor fija |
|---|---|---|---|---|
| 0 | +0,00 | 46,0 | 46,0 | titular (38,0) |
| 1 | +2,00 | 48,0 | 50,0 | contexto (45,0) |
| 2 | −4,00 | 54,0 | 50,0 | titular (45,0) |
| 3 | −2,00 | 53,0 | 51,0 | titular (37,0) |
| 4 | −1,00 | 46,0 | 45,0 | titular (38,0) |

**Efecto medio: −1,00 → PASS** (vara pre-registrada: media < 0).
Regret medio: control 49,40 · skills 48,40 · mejor fija 40,60.
Skills usadas en 9/12 bloques (la primera ocurrencia de cada régimen no
tiene skill todavía).

## Honestidad incómoda

1. **El efecto es chico**: −1,0 sobre un regret de ~49 (≈2%). Una réplica de
   5 sale en contra (+2,0). El PASS es técnico, no contundente.
2. **Las skills a veces misfirean**: la firma sale del probe (3 items,
   ruidoso). En rep0/bloque3 el régimen era deportes pero la firma dio tech
   y se aplicó la skill equivocada (acc 0,4 vs 0,5 del control). Firma
   ruidosa → skill equivocada: el mecanismo no es gratis.
3. **No cambia la conclusión de EXP44**: ambas políticas pierden contra la
   mejor fija por ~8-9 puntos. El costo del probe (5 items/bloque con
   scoring ciego) domina; las skills mejoran el Thompson pero no tocan ese
   costo estructural.
4. El mundo fue diseñado para que las skills *puedan* ayudar (recurrencia
   garantizada 4×). Aun así, el aporte es marginal. En el feed real (EXP44:
   rotación 8/8 sin recurrencia estable) el mecanismo no tendría de qué
   agarrarse.

## Veredicto

**PASS marginal.** La idea de Hermes tiene señal real: persistir experiencia
condicionada por régimen mejora (un poco) la puntería del Thompson cuando
los regímenes recurren. Pero la magnitud es chica, frágil a firmas ruidosas,
y no mueve la aguja contra el costo estructural del probe.

## Recomendación

No seguir tuneando el mock de skills: el techo visible es bajo. Si la
pregunta es si el loop de skills vale la pena en serio, el próximo paso
tiene que cambiar el problema, no el mecanismo — p. ej. firmas menos
ruidosas (más probe), o medir si la skill reduce el *costo del probe*
(saltar el probe cuando la skill tiene soporte fuerte), que es donde está
casi todo el regret.
