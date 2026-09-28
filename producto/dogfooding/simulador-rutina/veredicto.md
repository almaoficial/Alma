# SIM-RUTINA — Veredicto: FAIL (puerta de dos splits cerrada)

**Fecha:** 2026-09-28 ~01:30 EDT. **Costo:** US$0. **Vara:** la pre-registrada
(preregistro.md §5) — no se movió después de ver los números.

## Resultado primario

Métrica: energía media en la ventana de evaluación (días 61–120).
Δ = media(ALMA-full) − media(mejor rutina fija), IC 95% bootstrap (10.000 réplicas).

| Split | Energía loop | Energía mejor fija | Δ | IC 95% | ¿Pasa? |
|---|---|---|---|---|---|
| A (mundo seed 101) | 5,868 | 6,298 | **−0,430** | [−0,904; +0,048] | FAIL |
| B (mundo seed 202) | 6,527 | 6,793 | **−0,267** | [−0,761; +0,220] | FAIL |

**Veredicto global: FAIL.** La vara exigía límite inferior del IC > 0 en AMBOS
splits. Ninguno lo cumple; el loop queda por debajo de la mejor fija en los dos.
La puerta de dos splits **no se abre**: no hay propuesta de piloto (Fase 1).

## Lectura honesta de los números

1. **La exploración fue puro costo — el patrón EXP44 otra vez.** El skip no
   disparó ni una vez en 240 días (el umbral 1/3 quedó inalcanzable con
   diferencias típicas de ~0,1–0,2: el loop fue Thompson puro, como se
   pre-registró). Tasa de probe en evaluación: 55% (A) y 58% (B). Energía en
   días de probe vs. días sin probe: 5,68 vs. 6,10 (A); 6,09 vs. 7,13 (B).
   El loop pagó exploración más de la mitad de los días y no la recuperó.
2. **El condicionamiento por régimen sí aporta algo, pero no alcanza.**
   ALMA-full vs. Thompson global: +0,13 (A) y +0,38 (B), ambos con IC que
   incluye 0. Condicionar por firma ayuda en la dirección correcta; el problema
   no es el régimen, es el costo del probe.
3. **La mejor fija oráculo fue {libre: playa, turno: descanso} en ambos splits**
   — la rutina "natural" del diseño. El mundo sintético premia la estabilidad:
   con deriva de bloque σ=0,35 frente a ruido diario σ=1,1, adaptarse no paga.
4. **Potencia:** el efecto mínimo detectable era ~0,4 puntos. Los Δ medidos
   (−0,43 y −0,27) están en el orden del ruido de medición; lo que sí se puede
   afirmar es que no hay evidencia de mejora, y la dirección apunta en contra.

## Caveats (pre-registrados, se mantienen)

- El baseline fijo es oráculo: conoce las perturbaciones realizadas del mundo.
  Ninguna rutina fija real podría hacer eso; la vara fue más dura que la realidad.
- Las interacciones de racha (el "regalo" de diseño al loop) no alcanzaron para
  compensar el probe. Si el mundo real fuese más volátil que este sintético, el
   loop rendiría peor, no mejor.
- Esto no dice que el loop "no sirve" en general: dice que **en un mundo donde
  la señal estable (tipo de día) domina y la deriva es chica frente al ruido,
  una rutina fija bien elegida le gana a Thompson+probe**. Es el mismo veredicto
  estructural del EXP44 y del EXP62: la ventaja del loop es condicional al
  perfil del mundo, no intrínseca.

## Consecuencia

- **No avanza a Fase 1** (piloto pasivo). La sugerencia diaria no sale del simulador.
- El diseño RUTINA.md queda en espera: si se retoma, el próximo paso honesto
  sería rediseñar el mecanismo de exploración (el skip con umbral 1/3 nunca
  dispara; el probe al 55% es el costo que mata la mejora), no re-correr lo mismo.
- Archivos: `preregistro.md`, `simulador.py`, `resultados/splitA.json`,
  `resultados/splitB.json`, este veredicto — todo en
  `~/workspace/alma-prototype/producto/dogfooding/simulador-rutina/`.
