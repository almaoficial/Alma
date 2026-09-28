# Pre-registro — Laboratorio de apuestas v2: calibración por shrinkage (congelado 26/9/2026, ANTES de evaluar en test)

## Hipótesis
El FAIL del v1 (Elo ROI −11,6%, DC −14,1% en test, n>2700) no es un problema de
umbral: las probabilidades del modelo están **mal calibradas**. Si el
Dixon-Coles se "encoge" (shrinkage) hacia el mercado pre-partido, la calibración
debería mejorar (menor log-loss/Brier) y, si el modelo aporta algo real sobre el
mercado, el ROI debería dejar de ser muy negativo.

Hipótesis nula (la que intentamos NO refutar): el shrinkage no aporta nada; el
mercado pre-partido ya contiene toda la información y cualquier mejora es ruido.

## Variante v2 (un solo brazo nuevo)
- `p_v2 = λ·p_dc + (1−λ)·p_market_pre`, por outcome (H/D/A), renormalizado a suma 1.
- `p_dc`: probs Dixon-Coles walk-forward del v1 (`probs.pkl`, ya calculadas, sin cambios).
- `p_market_pre`: cuotas **pre-partido** devigged — `AvgH/AvgD/AvgA` (columnas SIN "C").
  Usar el cierre como target sería mirar el futuro; el cierre solo se usa para CLV.
- Partidos con `p_dc` o `p_market_pre` NaN/inválidos se excluyen (igual que en v1).

## Selección de λ (SOLO en validación 2022/23, sin tocar test)
- Grilla: λ ∈ {0.0, 0.1, …, 1.0}.
- Criterio: **minimizar log-loss** multiclase en validación (todas las ligas juntas).
  Desempate: menor Brier; luego menor λ (más conservador).
- λ queda congelado antes de evaluar en test. λ=1.0 = DC puro (brazo v1); λ=0.0 = mercado puro.

## Regla de apuesta v2 (fija a priori, sin tuning en validación)
- Umbral **fijo en 1.05** (default del diseño; no se elige por ROI en validación,
  para no repetir el overfitting al umbral del v1).
- 1 unidad ficticia, solo H o A (no empates), precio = MaxH/MaxA (sin "C"),
  si `p_v2(outcome) × precio ≥ 1.05`.
- CLV: precio tomado > cierre Pinnacle (PSCH/PSCA), idéntico al v1.

## Criterio PASS/FAIL (igual que v1, por brazo)
**PASS** ⟺ en test (2023/24–2024/25, 5 ligas): ROI > **+2%** con n ≥ **200** Y CLV ≥ **55%**.
Cualquier otra cosa = **FAIL**. Sin mover el arco después.

## Honestidad incómoda (se reporta siempre)
1. Tabla de calibración en test: log-loss/Brier de DC puro, mercado pre-partido,
   v2 (λ*), y mercado de cierre (referencia, como en v1).
2. ¿El shrinkage mejora la calibración vs el mercado? ¿λ* quedó en 0 (el modelo no aporta)?
3. ROI / n / CLV / drawdown máximo del v2 en test; por liga; n por temporada.
4. ROI sin filtro de edge (lado con mayor p_v2).
5. Comparación v1 vs v2 en la misma tabla.
6. Costo: US$0 (Python local, sin API key).
