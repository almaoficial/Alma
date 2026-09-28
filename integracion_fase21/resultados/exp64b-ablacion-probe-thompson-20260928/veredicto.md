# EXP64b — Veredicto: el probe ayuda pero no pasa la vara; Thompson es decorativo

**Fecha**: 2026-09-28. **Costo**: US$0 (mock, cero llamadas API).
**Sanidades**: determinismo OK; copia extendida bit-idéntica a
`r64.correr_replica_ablacion` con flags apagados en 200/207/219.
`run_exp64.py` no se modificó.

## Resultado

Efectos de QUITAR cada componente (d = reg_sin_X − reg_control),
n=20 held-out (réplicas 200..219), t=2,093, gl=19. Control medio: 83,75.

### (b) sin_probe — probe

- **Efecto medio: +3,55** — IC95 [**−0,064**, +7,164] (ancho 7,23)
- Peor sin probe: **14/20** · mejor: 5/20 · empate: 1/20
- Rango de diffs: −10,0 a +18,0

Criterio pre-registrado:
1. d̄ > 0 → ✓ (+3,55)
2. IC95 no cruza el 0 → ✗ (**cruza por 0,064**)
3. d_r > 0 en ≥14/20 → ✓ (exactamente 14/20)

**Veredicto: SIN EFECTO DETECTABLE con n=20.** No es load-bearing por
la vara pre-registrada, no es nocivo. No se poda, no se declara útil.

### (c) sin_thompson — Thompson sampling

- **Efecto medio: −0,35** — IC95 [−3,139, +2,439] (ancho 5,58)
- Peor sin Thompson: 8/20 · mejor sin Thompson: **12/20**
- Rango de diffs: −13,0 a +12,0

Criterio pre-registrado: media < 0 pero el IC95 cruza el 0 con holgura
→ ni load-bearing ni nocivo.

**Veredicto: SIN EFECTO DETECTABLE con n=20.** Quitar el Thompson y
explotar al ganador del probe da −0,35 de media — indistinguible de
cero. La exploración por muestreo posterior no aporta nada medible
sobre la explotación greedy del ganador del probe en este mundo.

## Diagnóstico honesto

1. **El probe falla la vara por 6 centésimas.** El IC95 es
   [−0,064, +7,164]: si el límite inferior hubiera sido +0,001 en vez
   de −0,064, el veredicto sería load-bearing. Dicho sin anestesia:
   la evidencia apunta a que el probe ayuda (+3,55, 14/20 peor sin
   él), pero con n=20 no alcanza el 95%. No se mueve el arco.
2. **No contradice a EXP64.** El n=5 había medido +9,8 con IC95
   [+2,59, +17,01]; el punto estimado de este n=20 (+3,55) cae DENTRO
   de ese intervalo. La estimación de n=5 era ruidosa y salió alta;
   la de n=20 es más precisa y sale más chica. Misma dirección, menos
   drama. La evidencia combinada sugiere efecto positivo real pero
   modesto — sin el 95% en esta muestra.
3. **Thompson no hace fuerza en el mock.** 12/20 réplicas MEJORAN al
   quitarlo (−0,35 de media). La dirección favorece la Hipótesis A del
   pre-registro (en un mundo de regímenes limpios, la exploración es
   puro costo — cf. lección EXP44), pero el IC incluye el 0 con margen:
   no se puede afirmar que sobre, solo que no se detecta que aporte.
   El probe identifica al ganador; el resto es explotación.
4. **Alta varianza por réplica en ambos.** Diffs de −10 a +18
   (probe) y de −13 a +12 (Thompson): el valor de cada componente
   depende del régimen/bloque, no es uniforme.
5. **Mundo mock.** Regímenes sintéticos limpios, rewards binarias.
   Esto mide la maquinaria, no el rendimiento con modelos reales.

## Qué parte del loop hace la fuerza (ranking medido)

| Componente | Efecto de quitarlo | IC95 | Veredicto |
|---|---|---|---|
| skip | **+6,55** | [+2,19, +10,92] | LOAD-BEARING (EXP64-skip, n=20) |
| probe | +3,55 | [−0,064, +7,164] | sin efecto detectable (n=20); +9,8 [+2,59, +17,01] en EXP64 n=5 |
| Thompson | −0,35 | [−3,139, +2,439] | sin efecto detectable (n=20) |

Lectura: en el mock, la fuerza del loop vive en **medir una vez
(probe) y no volver a medir (skip)**. El Thompson sampling —
la pieza "inteligente" del loop — es el componente más decorativo:
reemplazarlo por explotar al ganador del probe no cambia el regret de
forma detectable. El ranking es descriptivo (los IC se solapan entre
componentes); la comparación formal entre componentes no fue un test
pre-registrado.

## Decisión

- **No se poda nada.** Ningún componente cumplió el criterio nocivo.
- **Se conserva el skip** (load-bearing confirmado en EXP64-skip).
- **Probe y Thompson quedan en "sin evidencia con n=20"**: se
  conservan por defecto — quitar piezas sin evidencia de nocividad
  sería tan arbitrario como declararlas útiles sin evidencia.
- **Follow-up honesto si se quiere más certeza**: el probe está a
  0,064 de pasar la vara; otras 20 réplicas held-out (300..319)
  dirimirían si el +3,55 se sostiene. Para Thompson, ni siquiera hay
  señal que perseguir en el mock — la pregunta interesante sería si
  aporta algo con modelos reales (E3), no más réplicas sintéticas.
