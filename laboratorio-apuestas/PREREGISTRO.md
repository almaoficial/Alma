# Pre-registro — Laboratorio de apuestas v1 (congelado 26/9/2026, ANTES de correr)

Aclaración operativa del criterio de DISENO.md §4 (no lo cambia, lo hace evaluable):

- **Brazos que apuestan:** Elo simple y Dixon-Coles. El brazo "mercado devigged"
  es solo baseline de calibración (log-loss/Brier); no apuesta.
- **Evaluación por brazo:** el criterio se evalúa por separado en cada brazo
  apostador sobre el test (temporadas 2023/24–2024/25, 5 ligas).
- **PASS global** ⟺ al menos un brazo cumple LAS DOS condiciones en test:
  1. ROI > +2% con n ≥ 200 apuestas simuladas
  2. CLV ≥ 55%
  Ambos brazos se reportan completos (se anota el efecto de comparaciones múltiples).
- **Umbral de apuesta:** por brazo, elegido en validación (2022/23) de la grilla
  {1.03, 1.05, 1.08, 1.10} maximizando ROI con n ≥ 50; se congela y se aplica al test.
  Si ningún umbral llega a n ≥ 50 en validación, se usa 1.05 por defecto.
- **Apuesta:** 1 unidad ficticia, solo H o A (no empates), precio = MaxH/MaxA
  (columnas sin "C"), si prob_modelo × precio ≥ umbral.
- **CLV:** precio tomado (MaxH/MaxA) > cierre Pinnacle (PSCH/PSCA).
- **Walk-forward estricto:** toda predicción usa solo partidos con fecha anterior.
  Elo actualizado por fecha (sin leakage intra-fecha); Dixon-Coles reajustado
  mensualmente por liga solo con pasado; splits por temporada (train 1920–2122,
  val 2223, test 2324–2425).
- **Honestidad incómoda (se reporta siempre):** ROI por liga, drawdown máximo,
  ROI sin filtro de edge, n por temporada, y log-loss/Brier vs mercado devigged.
