# EXP68 — Veredicto: **PASS**

**Fecha:** 2026-09-27 ~23:00 EDT. **Costo:** mock, US$0, sin API keys.
Pre-registro escrito antes de validar; K/J/veredicto/mundos congelados.

## Resultado

| Mundo | Δ medio | IC95 (t, df=4) | Enganches |
|---|---|---|---|
| A (homogéneo, estilo EXP62) | **+6,00** | [+2,17, +9,83] | 5/5, todos en `contexto` (correcto), 0 restauraciones |
| B (heterogéneo, estilo EXP5) | **+0,00** | [+0,00, +0,00] | 1/5 (bloque 23, último; efecto neto 0) |

Δ = regret(baseline) − regret(detector), pareado por réplica (mismo RNG).
Criterio pre-registrado: PASS ⟺ media(Δ_B) ≥ 0 ∧ media(Δ_A) > 0. **Se cumple.**

Deltas por réplica — A: +6, +8, +1, +9, +6 (los 5 positivos). B: 0, 0, 0, 0, 0.

## Lectura

**El loop ahora sabe cuándo no hay nada que descubrir.** En el mundo
homogéneo, el detector engancha (mediana bloque 9) y banca al ganador
unánime, ahorrando ~6 puntos de regret sobre 240 items (~2,5% del total)
sin una sola falsa salida en validación. En el mundo heterogéneo, no
interviene: el skip del scaffold sigue haciendo su trabajo y el detector
no lo estorba (Δ_B exactamente 0).

El mecanismo clave que emergió de la calibración: el veredicto tiene que
ser el **probe** (argmax de lo medido), no el brazo comprometido del
posterior. El fav con decay=0,5 es una señal pésima para rachas — en A se
enganchó al brazo equivocado (Δ=-34 en calibración) y en B es ciego a
regímenes por construcción (rachas falsas estructurales). Con
veredicto=probe, los bloques saltados reinician la racha y B queda limpio.

## Caveats honestos

1. **Δ_B = 0 por inacción, no por acción.** El detector casi nunca engancha
   en B; el "no regresa" es que se queda afuera. Correcto para un detector
   de heterogeneidad, pero el test no ejercita mucho la pata de
   restauración (1 restore en 25 réplicas calibración+validación).
2. **Tasa de falsos enganches en B ~1/25**, contenida por el spot-check
   (margen ≥2 items). En streams más largos habrá más; la red existe.
3. **Mundo A estilizado** (categoría única, firmas únicas por bloque para
   dormir el skip). Un mundo homogéneo real con recurrencias también
   activaría el skip; el detector es para el caso donde no hay
   recurrencias que explotar.
4. n=5 réplicas de validación; el IC95 de A excluye el 0 con margen.

## Recomendación

- **No requiere fase con key** (regla mock-first): la pregunta era
  aritmética del mecanismo y el mock la respondió.
- Candidato a integrar como meta-regla aditiva en `alma_service/`
  (el módulo ya vive ahí). La promoción la decide el humano (freno
  vigente): el veredicto técnico es PASS a dos puntas.

## Archivos

- `preregistro.md` — hipótesis, diseño, K=3/J=3, criterio (congelado).
- `run_exp68.py` — runner (copia bit-idéntica de e56 + hooks) y validador.
- `report.json` — números completos por réplica.
- `alma_service/heterogeneidad.py` — el detector.
