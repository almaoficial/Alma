# ALMA EXP23 — Veredicto: NO CONFIABLE (pero con hallazgo)

**Pregunta:** a horizonte largo (R=50), ¿morir después de reportar PAGA el renacimiento?
**Respuesta corta:** en la media sí (M_bat 52,71 < M_pers 54,35), pero el signo cambia entre seeds → **NO CONFIABLE** por la regla pre-registrada. La pregunta sigue abierta en la métrica M.

## Números (8 seeds nuevas 2321–2328, mock, US$0)

| Brazo | MSE crudo (rango) | Llamadas | M (media) |
|---|---|---|---|
| Persistentes | 0,061 – 0,467 | 350 | 54,35 |
| Baterías (s=1) | 0,060 – 0,098 | 700 | 52,71 |

Diffs M_pers−M_bat: −3,96 / −5,50 / −29,23 / **+1,64** / **+111,47** / −8,93 / −47,18 / −5,25 → cambio de signo → NO CONFIABLE.

Break-even del costo de spawn: **s* mediana 0,80, media 1,12** (consistente con el diagnóstico de EXP22: ~1,15). Curva: con s≤1 ganan las baterías en la media; con s≥1,5 ganan los persistentes.

## Lectura honesta: el hallazgo no es la media, es la varianza

1. **El brazo persistente a horizonte largo es una lotería.** Su MSE va de 0,061 a 0,467 según la seed (7,6× de spread). Las baterías: 0,060 a 0,098 — planas. La deriva no solo baja la media: **explota la varianza**. En la seed 2325 los sesgos se alinearon por azar y el MSE se fue a 0,47; en la 2327 el azar favoreció a los persistentes. Las baterías no dependen del azar de la deriva.
2. **Lo que las baterías compran no es media, es colapso de varianza** — y la métrica M = MSE×llamadas no lo precia. Si lo que importa es el peor caso (el caso de los agentes rogue de las noticias: una corrida que se desboca), las baterías dominan. La intuición del usuario ("no crean más ruido") queda validada como **control de varianza**, no como victoria en costo×media.
3. **El borde no se movió:** s*≈0,8–1,1 vs ~1,15 del diagnóstico. Con spawn barato (s<0,8) las baterías pagan; con spawn caro, no. A s=1 estamos en el filo exacto.
4. Sanity check con drift=0: MSEs del mismo orden (0,072 vs 0,083) — el simulador no está roto; el seed 2325 es un evento de cola real del random walk (~2σ), no un bug.

## Comparación explícita vs EXP22

| | EXP22 (R=10) | EXP23 (R=50) |
|---|---|---|
| Veredicto | FAIL (confiable) | **NO CONFIABLE** (la media pasa) |
| M_pers vs M_bat | 4,69 vs 12,88 | 54,35 vs 52,71 |
| s* | ~1,15 (diagnóstico) | 0,80 / 1,12 |
| Historia | la deriva apenas muerde, el costo domina | el costo empata con la calidad en la media, pero la deriva vuelve lotería a los persistentes |

## Archivos
- `preregistro.json` — hipótesis, parámetros exactos, criterio, análisis de break-even (escrito ANTES de correr)
- `report.json` — tabla por seed + curva M(s) + sanity check
- Script re-ejecutable: `~/workspace/alma-prototype/run_experiment23.py`

Costo US$0. Nada pendiente.
