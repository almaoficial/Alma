# ALMA-EXP51 — Veredicto: PASS + HUECO ACHICADO (mock)

**Fecha:** 2026-09-27 ~15:35 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Pre-registro:** `resultados/exp51-20260927/preregistro.json` (escrito antes de correr)

## Qué se testea

El residuo que seis experimentos no movieron: ~4 puntos bajo la mejor fija,
viviendo en el PROBE de los bloques no saltados. Un solo moving part sobre
la base (skip-endurecido de EXP49/50, verbatim como control): **probe
adaptativo** — en bloques no saltados con firma conocida, si los 3 items de
Q1 ya deciden a favor del brazo de la skill (media estricta sobre cada otro
brazo), se salta el re-probe Q2 y los items 6,7 se juegan con Thompson.

Variante elegida: (a). Descartadas: (b) probe corto por firma — proxy grueso
que salta Q2 use la evidencia o no; (c) warm-start con el bloque anterior —
ya dominada por el prior con olvido 0.5^d (EXP9).

**Criterio pre-registrado:** pasa_1 = media(reg_trat − reg_ctrl) < 0 →
PASS/FAIL (misma vara de refutación). **Objetivo de línea:** distancia a la
mejor fija d_trat = reg_trat − reg_fija < 2,5 (el hueco estaba en ~3,8).

## Números

| Réplica | efecto | reg trat | reg ctrl | Q2 saltados | skips trat (mis) | skips ctrl (mis) |
|---|---|---|---|---|---|---|
| 0 | −3,00 | 78,0 | 81,0 | 3 | 5 (1) | 4 (1) |
| 1 | −2,00 | 86,0 | 88,0 | 8 | 0 (—) | 0 (—) |
| 2 | +1,00 | 93,0 | 92,0 | 3 | 2 (2) | 0 (—) |
| 3 | −2,00 | 95,0 | 97,0 | 3 | 6 (1) | 5 (0) |
| 4 | −2,00 | 80,0 | 82,0 | 3 | 5 (1) | 5 (1) |

**Efecto medio: −1,60 → PASS** (pasa_1: −1,60 < 0 ✓).
Media sin la mejor réplica: −1,25 → no cargado por una sola.
**Distancia a la mejor fija:** tratamiento 86,40 − 84,20 = **2,20** < 2,5 ✓
(control: 88,00 − 84,20 = 3,80). **El hueco se achicó** (3,8 → 2,2).
Gate: Q2 saltado en 20 bloques con probe (3, 8, 3, 3, 3 por réplica).
Reproducibilidad del control vs EXP49: bit-idéntico (True).

**Costo del probe medido** (totales sobre 5 réplicas × 24 bloques):
- Q1: control 126,00 vs tratamiento 121,00 (ver punto 1 de honestidad).
- Items Q2: control 81,00 (scoring ciego) vs tratamiento 69,00 (Thompson
  cuando el gate dispara) → **ahorro del gate: +12,00**.

**Descomposición del efecto** (dónde se gana y dónde se pierde):
- Bloques NO saltados: el tratamiento gana en las 5 réplicas
  (−5, −2, −8, −7, −2 = **−24 total**). El gate funciona donde opera.
- Bloques saltados: el tratamiento pierde (+2, 0, +9, +5, 0 = **+16
  total**). Neto: −24 + 16 = −8 → −1,60/réplica.

Detalle por bloque (rep 0): `resultados/exp51-20260927/report.json`.

## Honestidad incómoda

1. **El chequeo de sanidad del pre-registro estaba mal planteado, no el
   código.** Pre-registré que el costo Q1 debía ser "bit-idéntico" entre
   políticas. Dio 126 vs 121. La razón: los sorteos del oráculo en Q1 sí
   son idénticos, pero el *scoring* usa el favorito ciego del prior, y los
   priors divergen una vez que las historias divergen (el tratamiento
   explota más, su fav es mejor). Es un efecto downstream genuino del
   tratamiento —el fav del tratamiento es mejor porque el tratamiento
   juega mejor— no un bug. Pero la afirmación del pre-registro era
   incorrecta y la corrijo aquí en vez de esconderla.
2. **Dos tercios del ahorro se fugan por el canal del skip.** El gate
   ahorra 24 puntos en bloques no saltados, pero deja `probe_obs` con 3
   items en vez de 5 en los bloques con gate, y la cuenta de victorias de
   la skill se vuelve más ruidosa → el tratamiento salta MÁS (18 vs 14
   skips) y esos skips extra misfirean: tasa de misfires 5/18 (27,8%) vs
   2/14 (14,3%) del control. El moving part tiene un efecto colateral
   sobre el *otro* mecanismo (el soporte del skip). El riesgo estaba
   anticipado en la nota de refutación del pre-registro ("Q1 decisivo pero
   ruidoso") y se materializó, sobre todo en la réplica 2 (+1,00: 2 skips
   extra, los 2 misfires).
3. **El hueco se achicó pero no se cerró.** 2,20 < 2,5 cumple el objetivo
   pre-registrado, pero quedan 2,2 puntos y el mecanismo que ahora manda
   es el efecto colateral del punto 2, no el probe. La próxima variante
   tendría que atacar la interacción gate↔soporte (p. ej., que los bloques
   con gate no cuenten para victorias, o exigir margen en Q1), no el
   probe en sí.
4. **1 de 5 réplicas en contra** (+1,00 en rep 2). El PASS no es unánime;
   la fragilidad entre réplicas sigue siendo el perfil de la línea.
5. **Condición de alcance intacta:** todo ocurre en el mundo construido
   con recurrencia garantizada. En el feed real el mecanismo no se
   activaría.

## Veredicto

**PASS + HUECO ACHICADO.** Se cumplieron las dos marcas pre-registradas:
efecto medio −1,60 < 0 y distancia a la mejor fija 2,20 < 2,5 (desde 3,80).
El probe adaptativo ataca el residuo donde vive —en los bloques no
saltados gana en las 5 réplicas (−24 total)— pero su efecto colateral
sobre el soporte del skip devuelve +16. Neto: −1,6/réplica.

## Recomendación

No más variantes sobre el probe: el costo del probe ya está
sustancialmente atacado (−24 donde opera). Lo que queda del hueco (2,2)
vive en la **interacción** entre el gate y la evidencia del skip. El
próximo mock debería probar UNA de: (i) los bloques con gate no aportan
victorias al soporte (evidencia solo de probes completos); (ii) el gate
exige margen mínimo en Q1, no solo victoria estricta. Si ninguna mueve el
neto, el techo ~2 puntos es estructural del mundo (ruido 2/10 por bloque)
y la línea se cierra con el mejor punto alcanzado.
