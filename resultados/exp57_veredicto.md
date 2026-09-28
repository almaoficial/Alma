# ALMA-EXP57 — Veredicto: ablación + replicación del loop RSO (mock)

**Fecha:** 2026-09-27 ~16:05 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Serie:** "ideas orientales" (RSO estilo MiniMax; continúa EXP56 PASS)
**Pre-registro:** `exp57_rso2/preregistro.md` (escrito antes de correr; con
hipótesis por parte, criterios numéricos e interpretación vinculante)
**Validez del harness:** el loop con seed 56 reproduce la trayectoria de EXP56
**bit-idéntica** (3 keeps r06/r10/r14, scaffold final, train 79.33, held-out
83.00) ✓ — lo que sigue se mide sobre una base válida.

## Parte A — ablación: ¿qué dimensión carga la mejora?

Scaffold evolucionado EVO = `{ub:1, ud:2, gm:0.0, n0:4, decay:0.5}`
(mejora held-out EXP56: +4.50). Cada variante revierte UN keep:

| Variante | Train [0,1,2] | Held-out [3,4] | Mejora ho | Δ vs EVO |
|---|---|---|---|---|
| INIT (manual) | 85.67 | 87.50 ([95, 80]) | — | — |
| EVO | 79.33 | 83.00 ([86, 80]) | **+4.50** | — |
| V1 (revert n0→2) | 80.00 | 87.00 ([93, 81]) | +0.50 | **+4.00** |
| V2 (revert ub→2) | 84.00 | 91.00 ([95, 87]) | **−3.50** | **+8.00** |
| V3 (revert ud→3) | 81.33 | 82.50 ([84, 81]) | +5.00 | −0.50 |

Aplicación de la interpretación pre-registrada:

- **Δ_n0 = +4.00 ≥ 3.0 → n0→4 es load-bearing.** Sin el prior warm más fuerte,
  casi toda la ganancia se evapora (EVO +4.50 → V1 +0.50).
- **Δ_ub = +8.00 ≥ 3.0 → umbral_base→1 es load-bearing, y más:** mejora(V2) =
  **−3.50 < 0** → el keep es *activamente protector*: sin el skip más fácil
  temprano, el scaffold queda **peor que el manual** en las dos réplicas
  held-out ([95,87] vs [95,80] del INIT).
- **Δ_ud = −0.50 → umbral_divisor→2 no aporta en held-out.** Revertirlo *mejora*
  levemente el held-out (82.50 < 83.00). En train sí ayudaba (+2.0:
  79.33→81.33) — el keep de r14 fue **ruido de entrenamiento que no transfirió**:
  un mini-Goodhart dentro del propio loop.

**Hipótesis A (las tres dimensiones contribuyen): refutada en su forma fuerte.**
La mejora vive en dos dimensiones (n0, umbral_base); la tercera es lastre en
held-out. El "RSO" aquí se reduce en gran parte a: **el tuning manual erró dos
parámetros y el loop los encontró**. Conclusión más humilde y más útil, tal
como anticipaba el pre-registro.

## Parte B — convergencia: ¿replica con otro seed?

Mismo protocolo, RNG de propuestas **seed 57**, 24 rondas, keep estricto en
train [0,1,2], held-out [3,4] nunca visto por el loop.

- **Keeps: 5/24.** Trayectoria: r02 ud 3→6, r03 decay 0.5→0.25, r09 n0 2→4,
  r10 ub 2→1, r13 ud 6→2 (neto ud 3→2, igual que EXP56 pero en dos pasos).
- **Scaffold final B:** `{ub:1, ud:2, gm:0.0, n0:4, decay:0.25}` — difiere del
  de EXP56 en **exactamente una dimensión** (decay 0.25 vs 0.5).

| Split | INIT | evo_B | Mejora |
|---|---|---|---|
| Train [0,1,2] | 85.67 ([78, 86, 93]) | 81.00 ([73, 81, 89]) | **+4.67** (3/3 réplicas) |
| Held-out [3,4] | 87.50 ([95, 80]) | 84.50 ([88, 81]) | **+3.00** (−7, +1) |

- **Criterio: 84.50 < 87.50 → PASS_B.** El efecto replica.
- **Convergencia:** vecino a 1 mutación del scaffold de EXP56 → bin
  pre-registrado "el efecto replica y el óptimo es robusto al orden de
  propuestas".

**Dirección confirmada:** B re-descubrió los mismos tres keeps de EXP56
(n0↑, ub↓, ud↓) — la dirección "más confianza en la skill, menos probe" no
depende del seed. La dimensión que flipa (decay) es la que EXP56 había
declarado "siempre peor": evaluada desde otro orden de propuestas, decay→0.25
fue keep en r03 (85.33→85.00) y luego 0.25→0.5 se rechazó dos veces. Es un
**óptimo local alternativo genuino**, path-dependence en forma leve: mismo
vecindario, una dimensión flipa según el camino.

## Honestidad incómoda

1. **El held-out sigue siendo n=2 y delgado.** B mejora +3.00 pero la réplica 4
   *empeora* +1 ([80]→[81]); toda la ganancia la carga la réplica 3 (−7).
   Igual que en EXP56: el PASS se sostiene por consistencia con train (3/3),
   no por el n=2.
2. **El held-out [3,4] ya se usó para el veredicto de EXP56** (comparación
   múltiple leve, advertida en el pre-registro). Para el loop de B sigue siendo
   no visto, así que la medición es válida, pero el umbral se lee con cautela.
3. **La ganancia de B (+3.00) es menor que la de EXP56 (+4.50).** El efecto
   replica pero atenuado; el seed 56 tuvo además la mejor realización del
   ruido held-out.
4. **La ablación es condicional, no independiente** (advertido): Δ mide el
   aporte marginal *dado* los otros dos keeps. Que ud→2 sea lastre condicional
   no dice qué haría solo.
5. **Sigue siendo propuestas aleatorias**, no el RSO real de MiniMax. Un
   proponente inteligente podría ganar más — o sobreajustar más.

## Veredicto

- **Parte A:** dos dimensiones load-bearing (n0→4, umbral_base→1; esta última
  activamente protectora), una es ruido de train (umbral_divisor→2).
- **Parte B: PASS** — el loop RSO replica con seed 57 (+3.00 en held-out) y
  converge al mismo vecindario (1 mutación de distancia), con path-dependence
  leve en `decay`.

## Recomendación (pre-registrada)

A mostró dimensiones load-bearing **y** B replicó → **fijar `n0=4` y
`umbral_base=1` como defaults** (son tuning validado en dos seeds, no
emergencia del loop); descartar el keep de `umbral_divisor` (no transfiere).
El loop keep/revert queda validado como mecanismo de tuning, no como
descubridor de novedades. Si la serie RSO continúa: proponente con análisis de
fallos (aunque sea heurístico) en lugar de más seeds aleatorios — lo aleatorio
ya dio lo que tenía para dar.
