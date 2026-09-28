# ALMA-EXP22 — Veredicto: FAIL (idea: agentes-batería, del usuario)

**Pregunta:** ¿morir después de reportar produce mejor señal por costo que persistir con ruido acumulado?
**Respuesta pre-registrada: NO — FAIL, confiable (4/4 seeds, sin cambio de signo).**

## Números (R=10, pre-registrado)

| Brazo | MSE medio (calidad cruda) | Llamadas | M = MSE × llamadas |
|---|---|---|---|
| Persistentes | 0,067 | 70 | **4,69** |
| Baterías | 0,092 | 140 | **12,88** |

Diffs (M_pers − M_bat): −7,39 / −7,18 / −3,91 / −14,28 — siempre negativos → veredicto confiable.

## Lectura honesta

1. **El FAIL lo decide el costo, no (solo) la calidad.** Las baterías cuestan 2× por ronda (renacer cuesta lo mismo que reportar, s=1 pre-registrado) y en 10 rondas la deriva de los persistentes apenas muerde: el sesgo acumulado medio en R=10 es 0,41, chico frente al ruido de observación. Morir paga poco cuando nadie vivió lo suficiente para pudrirse.

2. **La diferencia de MSE crudo (0,067 vs 0,092) está dentro del ruido de muestreo.** El sanity check con drift=0 (misma seed de diagnóstico, ambos brazos = mismo proceso) dio 0,082 vs 0,099 a favor de persistentes: con 40 rondas totales, la suerte del RNG mueve los MSE más que la deriva. El diseño R=10 no tenía potencia para detectar el efecto que buscaba — limitación del diseño, declarada en los caveats del preregistro.

3. **Diagnóstico post-hoc R=50 (NO pre-registrado, exploratorio):** con 50 rondas la deriva sí muerde — MSE persistentes 0,145 vs baterías 0,068 (las baterías mantienen su calidad plana; los persistentes se degradan 2×). Pero en M (con costo): 50,8 vs 47,3 de media, **con cambio de signo entre seeds** → NO CONFIABLE. La deriva es un random walk: en algunas seeds se cancela sola y los persistentes zafan baratos.

4. **Análisis de punto de equilibrio (R=50):** las baterías empatan en M cuando el costo de spawn s ≈ 1,15. Con s=1 (pre-registrado) están justo en el borde — por eso el NO CONFIABLE. Si renacer costara la mitad (s=0,5), ganarían con margen.

## Conclusión

La intuición del usuario es **direccionalmente correcta**: sin persistencia no hay deriva — el MSE de las baterías se mantiene plano (~0,068) mientras el de los persistentes crece con el horizonte. "No crean más ruido" es verdad en el modelo.

Pero **"morir paga el renacimiento" no quedó establecido**: a horizonte corto el costo 2× domina y el efecto es indetectable; a horizonte largo la ventaja de calidad es real pero el resultado económico depende de la seed y del costo de spawn. La arquitectura descartable es una apuesta válida solo si renacer es barato o el horizonte es largo y la deriva es el enemigo principal — exactamente el caso de los agentes "rogue" de las noticias de hoy, que se desvían en corridas largas.

**Veredicto oficial: FAIL** (criterio pre-registrado, confiable). La idea no muere: queda caracterizada su frontera.

## Archivos
- `preregistro.json` — hipótesis, modelo de ruido exacto, criterio (escrito ANTES de correr)
- `report.json` — tabla por seed R=10 + sanity check drift=0
- `diagnostico_r50/` — corrida post-hoc R=50 (exploratoria, no pre-registrada) con su report.json
- Script: `~/workspace/alma-prototype/run_experiment22.py`
