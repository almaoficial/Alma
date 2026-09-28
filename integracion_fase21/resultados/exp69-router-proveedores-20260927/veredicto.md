# EXP69 — Veredicto: PASS (pre-registrado 2026-09-27)

## Resultado
El router por reward/USD elige al ganador ex post en 3/3 slices, y la ventaja
global entre proveedores es significativa.

| Slice | Elección del router | R/USD |
|---|---|---|
| gsm8k | deepseek/single | 47.782 |
| mmlu | deepseek/single | 36.630 |
| mbpp | deepseek/single | 2.821 |

- Criterio 1: router == ganador ex post en 3/3 slices (vara: ≥2/3) → PASS.
- Criterio 2: IC95 bootstrap (10.000 réplicas) de la diferencia de R/USD
  global (OA−DS) = [+585, +1925], no incluye el 0 → PASS.
- Global: OpenAI 2.970 R/USD vs DeepSeek 1.702 R/USD (OpenAI más barato por
  llamada: US$0,000153 vs US$0,000346), pero por slice domina deepseek/single.

Costo: US$0,0276 (freno US$0,25). 180/180 pulls. Sin incidentes.

## Hallazgos
1. El ganador de eficiencia es el brazo más barato (single), no el más
   inteligente: en estos problemas el thinking cuesta 10–40× más por una
   ganancia marginal de reward. Eco del colapso de EXP62 (lo barato gana
   cuando el mundo es fácil).
2. mbpp ≈ 0 en ambos proveedores (deepseek/single 2/20) — el código con tests
   en sandbox sigue siendo el slice más duro.
3. Caveat honesto: el criterio 1 es casi tautológico (router y ganador ex post
   usan los mismos números observados). La señal real es el criterio 2, que
   pasó. La validación genuina de generalización queda para el oráculo de 180
   problemas: si deepseek/single sigue dominando por slice en problemas
   frescos, la regla generaliza.

## Consecuencia
La regla de decisión del router queda validada en el piloto. Próximo paso de
diseño (fase 2.x, roadmap): registry de proveedores con metadata medida +
failover si un conector da 401, como pidió el usuario.

## Generalización (oráculo 180 problemas frescos, 2026-09-27 ~21:00)
El ganador ex post por R/USD en el oráculo —datos que el router nunca vio— es
deepseek/single en los 3 slices (gsm8k 44.523, mmlu 37.723, mbpp 2.874).
La elección del router (entrenada en el piloto de 30) coincide 3/3 en held-out:
**la regla generaliza**. Matiz: en reward crudo, gsm8k lo gana cot (0,967 vs
0,633) — el router optimiza eficiencia, no accuracy cruda; es el objetivo
pre-registrado.
