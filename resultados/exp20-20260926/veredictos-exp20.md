# ALMA-EXP20 — Veredicto: PASS

**Pregunta:** ¿sobrevive la selección con errores correlacionados, o el PASS de EXP19 era un artefacto de la independencia?

**Respuesta: sobrevive. La refutación fracasó.**

## Diseño (pre-registrado antes de correr)
- Misma tarea de filtrado que EXP19: 5000 candidatos/seed, HIT ⟺ (f1∧f4∧¬f7), prevalencia 12,5%.
- 4 seeds nuevas: 2021–2024 (distintas de EXP19).
- Mismos 7 agentes heterogéneos (F: 0,85/0,82 la estrella).
- **Errores correlacionados**, modelo exacto en `preregistro.json`: latente gaussiana por candidato,
  `Z_a = sqrt(0.5)·C + sqrt(0.5)·eps_a`, C compartida; el agente predice 1 sii `Phi(Z_a) < q_a(label)`
  con `q_a = TPR_a` (label=1) / `(1-TNR_a)` (label=0). Marginales idénticas a EXP19.
- Brazos: (a) individual al azar, (b) voto ×7, (c) enjambre ×7 con probe (16 etiquetados).
- Métrica: `E = F1/llamadas×1000`. Criterio: `E_probe > E_individual` Y `E_probe > E_voto` en la media.
- Regla de confiabilidad: cambio de signo entre seeds → NO CONFIABLE.
- 100% mock, US$0, cero llamadas a API.

## Números (media 4 seeds)

| Brazo | F1 | Llamadas | E |
|---|---|---|---|
| Enjambre CON probe | 0,5393 | 5112 | **0,1055** |
| Individual (azar) | 0,3352 | 5000 | 0,0670 |
| Voto ×7 | 0,3639 | 35000 | 0,0104 |

Diffs `E_probe − E_individual` por seed: +0,0535 / +0,0428 / +0,0548 / +0,0028.
Siempre positivos, sin cambio de signo → veredicto confiable (regla EXP16).
Sanity check del modelo: correlación media de errores binarios por pares = **0,31**
(esperado ~0,2–0,35 para rho=0,5 en la latente — el modelo hace lo que dice).
El probe seleccionó al mejor agente (F) en **4/4 seeds**.

## Comparación explícita vs EXP19

| | EXP19 (errores indep.) | EXP20 (rho=0,5) |
|---|---|---|
| E_probe | 0,0940 | 0,1055 |
| E_individual | 0,0554 | 0,0670 |
| E_voto | 0,0148 | 0,0104 |
| F1_probe | 0,4807 | 0,5393 |
| F1_voto | **0,5164** | **0,3639** |
| Probe elige a F | 2/4 | 4/4 |
| Veredicto | PASS | **PASS** |

Margen de eficiencia `E_probe − E_individual`: 0,0386 (EXP19) → 0,0385 (EXP20).
**Prácticamente idéntico.** La ventaja de la selección no se movió con la correlación.

## Lectura honesta
1. **La refutación fracasó.** Con errores correlacionados (nivel realista para LLMs), la selección
   sigue ganando en F1-por-costo al individuo y al voto ingenuo, en las 4 seeds, sin cambio de signo.
   El PASS de EXP19 no era un artefacto de la independencia.
2. **Lo que sí rompió la correlación fue el voto ingenuo**: su F1 crudo cayó 0,5164 → 0,3639.
   Era predecible —el voto vive de la diversidad de errores— pero ahora está medido: con errores
   correlacionados, escalar sin selección pierde su ventaja de calidad Y mantiene su costo 7×.
   Esto endurece la tesis: la selección es lo que vuelve eficiente al enjambre, y cada vez más
   cuando los agentes se parecen entre sí.
3. **No sobre-interpretar el 4/4 vs 2/4** en la selección de F: las seeds son distintas entre
   experimentos, así que esa comparación está confundida por seed. Lo comparable es el veredicto: PASS y PASS.
4. **Bug y corrección (documentado en `preregistro.json`):** la primera corrida parametrizó mal
   `q` en `label=0` (TNR en vez de 1−TNR), violando las marginales de EXP19. Se detectó por los
   números absurdos (F con accuracy 0,25 en el probe, F1 0,22 vs teórico 0,55), se corrigió el código
   y la documentación, y se re-corrió. Criterio, seeds, rho y diseño sin cambios. Solo la corrida
   corregida cuenta; la bugueada se descartó.

## Caveats que quedan
- rho=0,5 es UN nivel de correlación, no todos. Robustez a un punto, no al espectro.
- Los agentes siguen siendo tablas fijas de TPR/TNR, no LLMs reales.
- El brazo voto sigue desfavorecido en eficiencia por diseño (7× costo); la comparación real es probe vs individual.

## Archivos
- `preregistro.json` — hipótesis, modelo de correlación exacto, criterio, nota de corrección del bug
- `report.json` — tabla numérica por seed + comparación EXP19
- `run_experiment20.py` — script re-ejecutable y determinista
