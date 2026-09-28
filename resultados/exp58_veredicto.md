# ALMA-EXP58 — Veredicto: FAIL → el proponente que analiza fallos no supera al aleatorio (mock)

**Fecha:** 2026-09-27 ~16:05 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Serie:** "ideas orientales" (RSO; continúa EXP56 PASS / EXP57 PASS-atenuado)
**Pre-registro:** `exp58_proposer/preregistro.md` (escrito antes de correr; heurística
R1/R2/R3 + tabú documentada, criterio y bins de interpretación vinculantes)
**Validez del harness:** el puerto instrumentado con SC_INIT reproduce EXP51
**bit-idéntico** en las 5 réplicas ([78.0, 86.0, 93.0, 95.0, 80.0]) ✓ — el loop
corrió sobre una base válida. El experimento es determinista (el proponente no
usa RNG): una re-corrida daría la trayectoria idéntica.

## Qué se testea

La recomendación pre-registrada de EXP57: si la serie RSO continúa, que sea con
proponente que analice fallos, no más seeds aleatorios. EXP58 implementa ese
proponente como heurística explícita: después de cada ronda analiza atribución
de regret por bloque en train (misfires del skip, skips perdidos, errores del
probe, y si el prior sabía o engañaba) y propone la mutación direccional
correspondiente (R1 endurecer skip, R2 ablandar skip, R3 ajustar prior n0),
con memoria tabú de 3 rondas. Mismo espacio, mismo protocolo keep/revert, mismo
held-out [3,4] que EXP56.

## Números

| Split | Inicial (EXP51) | Evolucionado (proponente analítico) | Mejora |
|---|---|---|---|
| Train [0,1,2] | 85.67 ([78, 86, 93]) | 80.00 ([67, 84, 89]) | **+5.67** (−11, −2, −4) |
| Held-out [3,4] | 87.50 ([95, 80]) | 87.00 ([93, 81]) | +0.50 (−2, +1) |

- **Criterio: 87.00 < 83.00 (EXP56) → FAIL.**
- Rondas: 24 · keeps: **2/24** · abstenciones: 10 · reglas disparadas: R2×7, R3×5, R1×2.
- Scaffold final: `{umbral_base: 1, umbral_divisor: 2, gate_margin: 0.0, n0: 2, decay: 0.5}`.
- Trayectoria: r01 R2 ub 2→1 **KEEP** (85.67→85.33); r02 R1 ub 1→2 rechazado;
  r03 R1 ud 3→2 **KEEP** (85.33→80.00); r04–r24: el proponente re-propuso
  cíclicamente `ud 2→3` (R2, rechazado 5 veces) y `n0 2→1` (R3, rechazado 4
  veces) con abstenciones en las rondas de tabú. A partir de r03 las señales
  quedaron fijas (mf=12.0, op=14.0, pc=53.0): el proponente llegó a un punto
  fijo, no a una convergencia lenta.

## Aplicación de la interpretación pre-registrada

**FAIL con held-out < 87.50** → el loop con proponente inteligente no supera al
aleatorio: **no hay evidencia de que el análisis de fallos ayude en este
espacio/régimen**. La mejora en train (+5.67, 3/3 réplicas) no transfirió al
held-out (+0.50, una réplica en contra) — el mismo mini-Goodhart del keep
`ud→2` que EXP57 ya había identificado como ruido de entrenamiento.

## Disección: por qué falló el proponente (el hallazgo útil)

1. **El análisis del skip funcionó.** R2/R1 re-descubrieron por análisis (no por
   azar) la dirección "más confianza en la skill": ub→1 en r01 y ud→2 en r03.
   El proponente inteligente encontró en 3 rondas lo que al azar le tomó 14.
2. **El análisis del prior apuntó exactamente al revés.** R3 midió
   `prior_mal > prior_bien` y propuso **debilitar** el prior (n0 2→1) cuatro
   veces — rechazado siempre (+4.00 en train). Nunca intentó n0→4, el keep
   load-bearing de EXP57 (Δ+4.00). El error está en la señal, no en la regla:
   R3 mide el `fav` del prior **no condicionado**, pero el prior que importa en
   esta política es el **condicionado a la skill** (lección de EXP50: el valor
   está en elegir bien). La atribución midió el prior equivocado y concluyó lo
   contrario de lo correcto.
3. **Una heurística mal atribuida es peor que el azar.** El azar exploró y por
   suerte probó n0→4; el proponente "inteligente" se convenció con números de
   que la dirección correcta era la opuesta y jamás la exploró. La moraleja no
   es "el análisis no sirve" sino "el análisis es tan bueno como su modelo de
   atribución" — y un modelo de atribución erróneo dirige con confianza hacia
   el lugar equivocado.
4. **El tabú de 3 rondas no rompió el punto fijo.** El proponente re-propuso
   las mismas dos mutaciones rechazadas cada 4 rondas (al expirar el tabú):
   9 de 24 rondas fueron reintentos condenados. Un tabú más largo o una
   diversificación forzada habrían ahorrado cómputo, pero no habrían encontrado
   n0→4: el problema era la dirección, no la persistencia.

## Honestidad incómoda

1. **El held-out sigue siendo n=2.** El +0.50 es ruido (una réplica −2, otra
   +1); el FAIL no es "el proponente es malo por medio punto" sino "no hay
   mejora distinguible de cero donde el azar logró +4.50".
2. **La heurística se diseñó con conocimiento de EXP57 y aun así falló** — lo
   cual es informativo, no vergonzoso: muestra que diseñar un buen proponente
   analítico es difícil incluso con las respuestas a la vista, porque la
   atribución correcta (qué prior medir) no era obvia.
3. **24 rondas sobraron, no faltaron.** El proponente se estancó en r03; más
   rondas no habrían ayudado. El límite no fue el presupuesto sino el modelo
   de atribución.
4. **Lo refutado es esta heurística, no el RSO con proponente inteligente.**
   Un proponente que midiera el prior condicionado (o un LLM que analizara
   fallos de verdad, como el de MiniMax) podría hacerlo mejor. Pero la vara
   quedó alta: tendría que superar 83.00 en este held-out.

## Veredicto

**FAIL por el criterio pre-registrado (held-out 87.00 vs 83.00 de EXP56).**
El proponente con análisis de fallos encontró rápido la dirección del skip pero
erró la dirección del prior por medir el prior equivocado, y terminó en un
punto fijo sin mejora real (+0.50 en held-out, indistinguible de cero).

## Recomendación (pre-registrada)

**La serie RSO se archiva en este espacio.** El keep/revert queda como
mecanismo de tuning validado (EXP56/57: fijar n0=4 y umbral_base=1 como
defaults); el proponente analítico no aportó. Siguiente idea oriental: SPELL
para el probe. Si alguna vez se retoma un proponente inteligente, la lección
de EXP58 es su especificación mínima: la atribución debe medir el prior
condicionado a la skill, no el prior global — y debe validarse la dirección de
la señal antes de confiar en ella.
