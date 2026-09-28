# ALMA-EXP34 — ¿EVI + detección de cambios con flips ralos?

**Veredicto: FAIL** (confiable — sin cambio de signo en ninguna comparación).

## Números (regret medio/episodio, mock US$0, 8 seeds 3421–3428 × 50 episodios/régimen, números aleatorios comunes vía potential outcomes)

| Régimen | siempre | evi | evi-cd |
|---|---|---|---|
| Estacionario | 54,01 | **13,52** | 14,02 |
| Flip ralo (1/episodio) | 55,08 | 53,46 | **43,63** |
| Pooled | 54,54 | 33,49 | 28,82 |

Criterio pre-registrado: PASS solo si evi-cd < ambos controles en AMBOS regímenes.
- Flip ralo: vs_siempre ✓ (−11,45), vs_evi ✓ (−9,83) — 8/8 seeds en ambas.
- Estacionario: vs_siempre ✓ (−40 aprox.), vs_evi ✗ (+0,50) — 8/8 seeds, signo consistente.

## Diagnóstico del mecanismo

1. **La hipótesis central se confirma donde importa**: con flips ralos, la detección paga. El evi-cd recupera el flip vía detección forzada y evita el 75% de los probes del control siempre-activo (tasa probe 25,4% vs 100%).
2. **El FAIL viene del mundo calmo**: en estacionario el detector casi no dispara (falsos positivos 0,06/episodio), pero cada probe forzado innecesario cuesta ~3,6 de regret; neto +0,50/episodio vs evi-puro, consistente en las 8 seeds (rango +0,26/+0,72). Efecto real, no ruido.
3. **El detector funciona**: P(detección en F+1) = 0,50; la otra mitad de los flips los atrapa el probe EVI regular en el propio bloque del flip (tasa probe en flip_ralo 20,3% vs 15,0% en estacionario). Detección tardía 15% del resto; lag medio 0,2 bloques.
4. **Lectura para decisión**: el detector es un seguro — ahorra ~10/episodio cuando hay flips, cuesta ~0,5/episodio cuando no. Si la tasa base de cambios del mundo real justifica el seguro es una pregunta de base-rate, no de mecanismo. En pooled (50/50) el evi-cd ya gana (28,82 vs 33,49).

## Archivos
- `preregistro.json` (escrito antes de correr)
- `report.json`
- Script: `~/workspace/alma-prototype/run_experiment34.py`

Costo: US$0,00. Ninguna llamada a API real.
