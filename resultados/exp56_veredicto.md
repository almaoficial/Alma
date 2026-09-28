# ALMA-EXP56 — Veredicto: PASS → el loop RSO mejora el scaffold en held-out (mock)

**Fecha:** 2026-09-27 ~16:25 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Serie:** "ideas orientales" (EXP53 SkillRL refutado, EXP54/55 TTRL archivado)
**Pre-registro:** `exp56_rso/preregistro.md` (escrito antes de correr; incluye la regla de oro y la interpretación vinculante)

## Qué se testea

RSO estilo MiniMax en miniatura: el "scaffold" = 5 hiperparámetros de la política de probe de EXP51
(`umbral_base`, `umbral_divisor`, `gate_margin`, `n0`, `decay`; 324 combinaciones).
Loop greedy de linaje único, 24 rondas: UNA mutación propuesta por ronda (RNG dedicado seed 56) →
evaluar en split train (réplicas [0,1,2]) → keep si mejora estrictamente, revert si no.
Medición final en held-out [3,4], que el loop nunca ve.

**Regla de oro (pre-registrada):** el loop NUNCA edita al validador — oráculo, stream, cómputo de
regret, held-out y evaluador congelados; solo mutan los 5 hiperparámetros.

**Sanidad pre-registrada:** el puerto parametrizado con parámetros iniciales reproduce EXP51
**bit-idéntico** en las 5 réplicas ([78.0, 86.0, 93.0, 95.0, 80.0]) ✓ — el loop corrió sobre una
base válida.

**Criterio pre-registrado:** PASS ssi media_heldout(evolucionado) < media_heldout(inicial).

## Números

| Split | Inicial (EXP51) | Evolucionado | Mejora |
|---|---|---|---|
| Train [0,1,2] | 85.67 ([78, 86, 93]) | 79.33 ([67, 82, 89]) | **+6.33** (−11, −4, −4 por réplica) |
| Held-out [3,4] | 87.50 ([95, 80]) | 83.00 ([86, 80]) | **+4.50** (−9, 0 por réplica) |

- **Criterio: 83.00 < 87.50 → PASS.**
- Rondas: 24 · keeps: **3/24** (r06: n0 2→4; r10: umbral_base 2→1; r14: umbral_divisor 3→2).
- Scaffold final: `{umbral_base: 1, umbral_divisor: 2, gate_margin: 0.0, n0: 4, decay: 0.5}`.
- Las 21 mutaciones rechazadas incluyen: todo lo probado con `decay ≠ 0.5` (siempre peor),
  `n0 → 1` (peor), y `gate_margin ∈ {0.05, 0.10}` (métrica idéntica — el margen no mueve
  ninguna decisión en este mundo).

Contexto contra la mejor fija (las 5 réplicas, no pre-registrado como criterio):

| Réplica | evo | mejor fija | dif |
|---|---|---|---|
| 0 | 67.0 | 84.0 | −17.0 |
| 1 | 82.0 | 89.0 | −7.0 |
| 2 | 89.0 | 88.0 | +1.0 |
| 3 | 86.0 | 80.0 | +6.0 |
| 4 | 80.0 | 80.0 | 0.0 |

- Media evolucionado: **80.80** vs mejor fija **84.20** → distancia **−3.40**.
- Primera vez en toda la línea (EXP45–56) que una política queda **por debajo** de la mejor fija
  en media (EXP51 estaba en +2.20).

## Aplicación de la interpretación pre-registrada

**PASS → el loop RSO encontró un scaffold mejor en datos no vistos durante la evolución.**
Evidencia (en mock) de que la auto-optimización recursiva del scaffold aporta sobre el tuning
manual: 3 mutaciones greedy sobre 5 hiperparámetros movieron el regret −4.5 en held-out y
−3.4 de distancia a la mejor fija.

## Disección

- **Qué aprendió el loop:** (1) `n0 2→4` — prior warm más fuerte: la historia con olvido merece
  más peso del que le dábamos; (2) `umbral_base 2→1` — skip más fácil temprano: con el prior
  más fuerte, la evidencia necesaria para saltar baja; (3) `umbral_divisor 3→2` — el umbral se
  endurece más rápido con K: compensa el base bajo en el horizonte largo. Las tres van en la
  misma dirección: **más confianza en la skill, menos probe**. Es coherente con la lección de
  EXP50 (el valor está en elegir bien) llevada al extremo por el loop.
- **Qué rechazó el loop:** `decay ≠ 0.5` siempre empeoró (el olvido 0.5^d de EXP9 sigue siendo
  el punto dulce en este espacio); `gate_margin` no mueve nada (las medias de Q1 nunca caen
  en la franja 0–0.10: el gate es binario en este mundo, no hay margen que afinar).
- **Eficiencia del loop:** 3 keeps en 24 rondas; el scaffold final se alcanzó en la ronda 14 y
  las últimas 10 rondas no movieron nada (óptimo local greedy o convergencia real — indistinguible
  con un solo seed de propuestas).

## Honestidad incómoda

1. **El held-out es delgado (2 réplicas) y la mejora la carga una sola** (rep 3: −9; rep 4: 0).
   El pre-registro lo advertía. Lo que sostiene el PASS no es el n=2 sino la consistencia:
   en train la mejora fue **3/3 réplicas** (−11, −4, −4), y la dirección se mantuvo en held-out.
   Pero un PASS con n=2 es sugestivo, no sólido: la réplica 4 no se movió un punto.
2. **La distancia −3.40 a la mejor fija mezcla train y held-out** (las réplicas 0 y 1, que más
   ganan, estaban en el split de entrenamiento). La comparación limpia es la pre-registrada
   (held-out +4.50). El −3.40 es contexto, no veredicto.
3. **Lo testeado fue keep/revert con propuestas aleatorias, no el RSO real.** MiniMax propone
   con un LLM que analiza fallos y edita código; aquí el "análisis" es `random.Random(56)`.
   Si con propuestas aleatorias se gana +4.5, el espacio tenía margen que el tuning manual dejó
   en la mesa — pero no prueba nada sobre un proponente inteligente (podría ganar más, o
   sobreajustar más).
4. **24 rondas greedy sobre 324 combos** es una caminata corta a un óptimo local. Otro seed de
   propuestas podría llegar a otro scaffold (pre-registrado como EXP57).
5. **Costo de la lección: US$0.** El loop completo corrió en 1.4 segundos.

## Veredicto

**PASS por el criterio pre-registrado (held-out 83.00 < 87.50, mejora +4.50).**
El scaffold evolucionado `{umbral_base: 1, umbral_divisor: 2, gate_margin: 0.0, n0: 4, decay: 0.5}`
gana al scaffold manual de EXP51 en datos no vistos durante la evolución, y es la primera
política de la línea que queda por debajo de la mejor fija en media (−3.40).

## Recomendación (pre-registrada)

**EXP57 = ablación del scaffold evolucionado + replicación con otro seed.**
(1) ¿Qué dimensión aportó? — las 3 mutaciones por separado contra el scaffold inicial, para
separar señal de lastre (¿umbral_base→1 solo, sin n0→4, también gana?). (2) Repetir la evolución
con otro seed de propuestas: ¿converge al mismo scaffold o a otro óptimo local? Si la ablación
muestra que una sola dimensión carga la mejora, el "RSO" se reduce a "el tuning manual erró un
parámetro" — conclusión más humilde y más útil.
