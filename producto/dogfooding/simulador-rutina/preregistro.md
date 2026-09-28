# SIM-RUTINA — Pre-registro: el loop ALMA sobre la rutina diaria (mock, US$0)

**Fecha:** 2026-09-28 ~01:20 EDT. **Costo:** mock, US$0, sin API keys, sin datos reales del usuario.
**Estado:** escrito ANTES de construir el simulador y de cualquier medición.
Pregunta, diseño, parámetros, criterio y protocolo congelados a partir de acá.
La vara no se mueve después de ver los números.

## 1. Pregunta e hipótesis

**Pregunta:** en un mundo sintético con regímenes de energía realistas y no-estacionariedad
(rotación de la frecuencia de turnos por bloque + deriva de la efectividad de cada brazo,
análogo a los flips del EXP44), ¿el loop ALMA-full (Thompson por régimen + probe + skip,
memoria con olvido) logra mayor energía promedio que la **mejor rutina fija**?

**Hipótesis de trabajo (escéptica):** no. El prior honesto, viniendo del EXP44
(la exploración era puro costo cuando el mundo rota) y del EXP62 (la ventaja del loop
era condicional al perfil del mundo, no intrínseca), es que con ruido diario σ≈1,1
dominando sobre perturbaciones de bloque σ≈0,35, la adaptación no compensa el costo
del probe. Un FAIL es informativo (delimita dónde el loop sirve y dónde no), no una
decepción. La vara es deliberadamente dura (ver §6) y no se negocia después.

## 2. Propiedades del stream sintético (registradas por cuenta propia)

Regla AGENTS.md 27/9: el pre-registro declara la selección/curado del stream.

1. **Mundo sintético, no datos reales.** Ningún número de acá describe al usuario:
   las distribuciones están calibradas a sus reportes típicos (energía media ~6,5,
   sueño 6–7,5 h, turnos nocturnos en Orilla) pero son inventadas. Los resultados NO
   dicen si el loop le serviría a él; dicen si la maquinaria puede batir a una
   rutina fija en un mundo con esta estructura.
2. **La teoría del mundo la pone el diseño, no la evidencia.** Las interacciones
   de racha (§4: en racha de energía baja el descanso rinde más) vienen de la
   teoría del propio RUTINA.md ("venís de 3 días de energía < 5..."), no de datos
   medidos. Si el loop gana, gana por explotar una ventaja que el diseño le regaló;
   se reporta como caveat, no como descubrimiento.
3. **El baseline fijo es oráculo (peor caso para el loop).** La "mejor rutina fija"
   se computa conociendo las perturbaciones realizadas del mundo. Ninguna rutina
   fija real podría saber eso; la vara es más dura que la realidad.
4. **No-estacionariedad moderada por diseño.** La frecuencia de turnos rota por
   bloque (análogo EXP44) y la efectividad de cada brazo deriva; no hay flips
   totales de qué brazo es mejor dentro de un régimen. Si el mundo real fuese más
   volátil, el loop rendiría peor que acá, no mejor.

## 3. Diseño del simulador

- **Unidad de tiempo:** 1 día. **Horizonte:** 120 días por split.
  **Ventana de evaluación:** días 61–120 (60 días, como pide RUTINA.md §3);
  días 1–60 = burn-in de aprendizaje (no puntúan).
- **Brazos:** `playa`, `gym`, `descanso`, `mixto` (RUTINA.md §3).
- **Firma del régimen** (conocida a la mañana del día t, nunca preguntada):
  `(tipo_día ∈ {libre, turno}, racha_sueño_corto ∈ {0,1}, racha_energía_baja ∈ {0,1})`
  → 8 firmas. `tipo_día` sale del "calendario" (sorteo del mundo);
  `racha_sueño_corto` ⟺ promedio de sueño de las últimas 2 noches < 6 h;
  `racha_energía_baja` ⟺ últimos 3 días con energía < 5.
- **Reward del día t** (RUTINA.md §3, se observa en t+1):
  `r_t = 0,7 × (energía_{t+1} − 1)/9 + 0,3 × cumplimiento_t`,
  donde `cumplimiento_t` = 1 si el brazo jugado coincide con el sugerido.
- **Cumplimiento:** el brazo jugado = el sugerido con p=0,8; si no, uniforme
  entre los otros 3 (igual para las tres políticas: comparación simétrica).

### Mundo (fijado antes de correr)

Bloques de longitud U{15,…,25} días. Por bloque b:
- `p_turno(b)` ∈ {0,35; 0,50; 0,65; 0,80} sorteado (rotación del régimen
  dominante, análogo a los flips del EXP44).
- Perturbación `δ(b, tipo, brazo)` ~ N(0; 0,35) (deriva de efectividad).

Calidades base (efecto sobre energía del día siguiente):

| tipo \ brazo | playa | gym | descanso | mixto |
|---|---|---|---|---|
| libre | +1,25 | +0,80 | +0,15 | +0,65 |
| turno | +0,10 | −0,55 | +0,60 | −0,10 |

Interacciones de racha (teoría del diseño, ver caveat §2.2):
- racha_energía_baja: `descanso` +0,8; `gym` −0,6 (cualquier tipo de día).
- racha_sueño_corto: `descanso` +0,5; `gym` −0,4.

Generación:
- `tipo_t` ~ Bernoulli(p_turno(bloque)) → turno / libre.
- `sueño_t`: turno → N(6,2; 0,9); libre → N(7,2; 0,8); +0,15 si el brazo
  jugado ∈ {playa, gym}; clip [3,5; 10].
- `energía_{t+1} = 5,6 + q(tipo_t, brazo_jugado_t, bloque) + interacciones_racha
  + 0,45 × (sueño_t − 6,5) + N(0; 1,1)`; clip [1, 10]. `energía_1 = 6,5`.

### La maquinaria (transplante fiel, parámetros congelados)

Scaffold: `DEFAULT_SCAFFOLD` (n0=4, umbral_base=1, umbral_divisor=3, decay=0,5).
Sin detector EXP68 (RUTINA.md §3 no lo incluye: Thompson + probe + skip + olvido).

- **Posterior:** por firma s y brazo a: Beta(α, β). Init neutral:
  α = β = 1 + n0×0,5 = 3 (cold start honesto, prior 0,5 para todos).
- **Update** (al observar r_t para la firma s_t y brazo jugado a_t):
  primero olvido α ← 0,5α, β ← 0,5β; luego α += r_t, β += (1 − r_t).
- **Decisión** (mañana del día t, solo historia ≤ t−1):
  1. μ_a = media posterior por brazo en la firma s_t; f = argmax μ
     (empates → orden alfabético, determinista).
  2. **Skip:** si μ_f − μ_2do ≥ 1/3 (= umbral_base/umbral_divisor, transplante
     EXP51/EXP71 a unidades de reward) → jugar f (no hay probe).
     Nota pre-registrada: con diferencias típicas ~0,1–0,2 el skip disparará
     rara vez; el loop es esencialmente Thompson por régimen con olvido.
  3. Si no hay skip → **Thompson sampling** (θ_a ~ Beta, RNG sembrado);
     día de probe ⟺ el muestreo elige un brazo ≠ f.

### Baselines (misma información, congelados)

- **Mejor fija (oráculo):** mapeo fijo tipo_día → brazo que maximiza la energía
  media verdadera sobre el horizonte del split, computado del ground truth del
  mundo (conoce las perturbaciones realizadas; ignora términos endógenos de
  racha). Es el techo de cualquier política fija por tipo de día.
- **Thompson global:** mismo scaffold pero una sola firma (ignora el régimen).
  Descriptivo: mide cuánto aporta condicionar por régimen.

Las tres políticas corren sobre el **mismo mundo** (misma realización de bloques,
tipos de día y perturbaciones) pero con RNGs independientes para ruido,
cumplimiento y muestreo — los regímenes endógenos (rachas) divergen por política,
como en la realidad.

## 4. Puerta de dos splits (protocolo ciego)

- **Split A:** mundo seed 101. Se corre ALMA-full (seed 1001), mejor fija,
  Thompson global (seed 1002). Se computa ΔA = media(loop) − media(fija) en la
  ventana de evaluación, con IC 95% bootstrap por percentiles (10.000 réplicas).
- **Veredicto A** con la vara del §5. Se congela: ningún parámetro, semilla o
  línea de código cambia después del veredicto A.
- **Split B:** mundo seed 202 (nunca visto), ALMA-full seed 2001, Thompson
  global seed 2002. Mismo cómputo → ΔB, IC 95%.
- **PASS global ⟺ PASS en A ∧ PASS en B.** Si A da FAIL, B se corre igual como
  replicación honesta (sin tocar nada) y el veredicto global es FAIL.
- "Ciego" acá significa: cero tuning entre A y B; el código y los parámetros
  son idénticos, solo cambian las semillas.

## 5. Criterio pre-registrado (congelado)

Métrica primaria: **energía media en días 61–120** (no el reward compuesto:
la vara de RUTINA.md §3 pide energía promedio; el reward compuesto es
secundario/descriptivo).

> **PASS en un split ⟺ el IC 95% bootstrap de Δ = media_loop − media_fija
> está completamente por encima de 0 (límite inferior > 0).**
> **PASS global ⟺ PASS en split A ∧ PASS en split B.**

Sin regresión: el criterio ya lo exige (si el límite inferior > 0 en ambos
splits, no hay regresión en ninguno).

Secundarias (descriptivas, no deciden): reward compuesto medio, tasa de
cumplimiento, tasa de días de probe, energía del Thompson global,
medias por split y política, ancho del IC.

Nota de potencia honesta: con n=60 y σ≈1,1, SE(Δ)≈0,2 → el IC 95% tiene
semi-ancho ≈0,39. Efecto mínimo detectable ≈ **0,4 puntos de energía**.
Diferencias menores no pueden distinguirse del azar en este diseño;
un FAIL con Δ∈(−0,4; +0,4) significa "sin evidencia de mejora", no
"evidencia de que no sirve".

## 6. Compromisos

- Pregunta, mundo, parámetros (n0=4, decay=0,5, skip ≥1/3, p_cumplimiento=0,8),
  semillas, ventana de evaluación, criterio y protocolo **no se tunean** después
  de este pre-registro.
- Mock US$0. Ninguna key, ningún gasto real, ningún dato real del usuario.
- No se importa ni toca `alma_service`; el simulador es un script autocontenido.
  Nada del servicio vivo (puerto 8471), crons o jobs se modifica.
- Todo veredicto sale de lo medido (energía observada en la ventana), nunca de
  posteriores, re-análisis post-hoc ni re-sorteos de semillas.
- Si el código crashea: se re-corre con las mismas semillas (determinista).
