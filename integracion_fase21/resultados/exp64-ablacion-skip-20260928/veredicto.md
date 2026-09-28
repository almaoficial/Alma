# EXP64-skip — Veredicto: el skip SÍ carga peso (por el umbral justo)

**Fecha**: 2026-09-28. **Costo**: US$0 (mock).
**Sanidades**: determinismo OK; bit-identidad OK en réplicas nuevas
(100/107/119).

## Resultado

Efecto de QUITAR el skip (d = reg_sin_skip − reg_control), n=20 held-out:

- **Efecto medio: +6,55** — IC95 [+2,19, +10,92] (t=2,093, gl=19)
- Peor sin skip: **14/20** réplicas · mejor sin skip: 4/20 · empates: 2/20
- Rango de diffs: −11,0 a +23,0 (alta varianza entre réplicas)

Criterio pre-registrado (vara sagrada):
1. d̄ > 0 → ✓ (+6,55)
2. IC95 no cruza el 0 → ✓ ([+2,19, +10,92])
3. d_r > 0 en ≥14/20 → ✓ (**exactamente 14/20**)

**Veredicto: LOAD-BEARING.** El skip se conserva. No es nocivo
(el espejo no se cumple ni de cerca).

## Diagnóstico honesto

1. **Pasa por el umbral justo.** 14/20 es exactamente el mínimo
   pre-registrado: una réplica que diera vuelta (13/20) y el veredicto
   habría sido "sin efecto detectable". La evidencia alcanza, pero sin
   holgura en la condición de conteo. Dicho sin anestesia.
2. **El punto estimado es estable.** EXP64 (n=5) había medido +6,00;
   este follow-up (n=20, seeds held-out) mide +6,55. Dos muestras
   independientes, mismo orden de magnitud — el efecto no era ruido
   de n=5.
3. **Alta varianza por réplica.** Diffs de −11 a +23: en 4/20 réplicas
   quitar el skip MEJORA. El skip ayuda en media pero no siempre; su
   valor vive en la interacción con el régimen (cuando el régimen se
   repite y el probe ya sabe, salta; cuando no, puede saltar de más).
4. **Mundo mock.** Esto mide ahorro de costo de probe en un mundo
   sintético con regímenes limpios. No es evidencia de que el skip
   pague igual con modelos reales — eso lo diría un E3 con datos
   frescos, no este experimento.

## Decisión

- **Se conserva el skip.** Load-bearing por la vara pre-registrada.
- **No se poda nada.** El espejo nocivo no se cumplió.
- **No se declara victoria definitiva.** El margen en la condición 3
  es de una réplica; un re-test con otros 20 seeds held-out sería el
  siguiente paso honesto si alguien quiere más certeza.
