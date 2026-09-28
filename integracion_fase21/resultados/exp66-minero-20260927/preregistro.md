# EXP66 — Pre-registro de validación (escrito ANTES de gastar)

**Fecha**: 2026-09-27. **Pregunta**: ¿puede el loop aprender del FAIL de EXP62
con una sola edición del scaffold?

## Firma objetivo

`(alma-full, *, cot|reflexion, fallo)`: Thompson con warm-start elige el brazo
caro ~50/90 veces contra un oráculo single 117/120. Mecanismo: el probe acierta
10/10 pero `correr_alma_full` no condiciona el bandit al ganador del probe;
el warm-start débil (n0=2, medias 0.758/0.696/0.552) deja posteriores
solapadas y la exploración es puro costo. Ver `firmas.md`.

## Edición propuesta (UNA sola)

**Prior anclado al probe**: al arrancar cada bloque, después del warm-start
estándar y de alimentar las 9 rewards del probe, sumar `N_ANCLA = 8`
pseudo-observaciones en el ganador del probe con su media del probe:

```
b.alpha[elegido] += 8 * media_probe[elegido]
b.beta[elegido]  += 8 * (1 - media_probe[elegido])
b.pulls[elegido] += 8
```

Thompson sigue explorando (no se lo amputa); solo arranca creyéndole al probe.
Si el probe se equivoca, la evidencia posterior lo corrige — el ancla es
derrotable, no un veto.

## Diseño de validación

- **Reutilización honesta** (US$0): stream idéntico (orden EXP5/EXP62), oráculo
  medido, y las 90 rewards del probe de `62B-alma-probe` (el probe no cambia).
- **Nuevo** (gasto real): 90 pulls de Thompson-anclado por réplica
  (9/bloque × 10), fase `66B-alma-edit`, store fresco, 3 réplicas
  (seeds 6601–6603). Sin llamadas de oráculo ni de probe.
- **Baseline**: regret por bloque de `alma-full` ya medido (report.json).
- **Splits**: held-in = bloques 0–4, held-out = bloques 5–9.
  Δ = regret(baseline) − regret(edit) por split (menor regret es mejor).
- **Puerta** (`alma_service/gate.py`): Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(Δ_in,Δ_ho) > 0
  sobre el regret medio de las 3 réplicas.

## Criterio de veredicto

- **PASS**: la puerta acepta → la edición entra al scaffold (documentada).
- **FAIL**: la puerta rechaza → se conserva el scaffold actual; el FAIL de
  EXP62 queda como techo medido del loop en mundos single-dominantes.

## Presupuesto (costos MEDIDOS, no teóricos)

Por llamada medidos en `gasto_por_llamada.jsonl` (n=101):
single US$0.000014 · cot US$0.000139 · reflexion US$0.000278.

Estimado conservador por réplica (mix del baseline: 40 single / 35 cot /
15 reflexion por 90 pulls — la edición debería concentrar MÁS en single,
así que esto es cota superior):
40×0.000014 + 35×0.000139 + 15×0.000278 = **US$0.0096**.

3 réplicas: US$0.0288. **+50% margen por reintentos: US$0.0432 ≤ US$0.08** →
la regla dura AUTORIZA correr. Freno duro del script: US$1.00.

## Addendum post-registro (antes de gastar)

Evidencia nueva del pre-test mock (US$0, simulador offline sobre rewards
medidas, 5–30 seeds): la edición NO supera al baseline (5.92 vs 5.42) y
ninguna variante chica lo hace; la brecha alma-full vs thompson-global es
ruido (0.44 ± 1.72, 16/30). **Stand down**: no se ejecuta la validación
con key. Ver `veredicto.md`. US$0,00 gastados.

## Caveats

- 3 réplicas, mundo sintético, un solo knob (N_ANCLA=8 fijo — no se tunea).
- El warm-start de validación usa el oráculo medido + las propias pulls de la
  réplica (auto-consistente), no el historial del baseline.
- 2/3 celdas no-single del oráculo son outliers de un intento: el mundo es
  aún más single-dominante de lo que dice el argmax.
