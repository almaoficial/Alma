# VEREDICTO — Laboratorio de apuestas v2: calibración por shrinkage (26/9/2026)

**Veredicto: FAIL** — ROI −24,3% en test (n=485, CLV 69,1%). No cumple el criterio pre-registrado.

## El resultado central (antes que los números de apuestas)

La búsqueda de λ en validación (2022/23, 1.826 partidos, minimizando log-loss) dio
**λ* = 0.0**: el log-loss crece de forma monótona con λ (0.9779 → 1.0143).

Traducción: **el Dixon-Coles no aporta nada sobre el mercado pre-partido**.
Cualquier peso λ>0 solo agrega ruido. El v2 quedó reducido al mercado puro —
y ese es un hallazgo, no un error: los datos dicen "acá no hay nada".

## Calibración en test (2023/24–2024/25, n=3.504)

| Modelo | Log-loss | Brier |
|---|---|---|
| Dixon-Coles puro | 1.0072 | 0.5964 |
| **Mercado pre-partido (v2 = λ*0)** | **0.9598** | **0.5703** |
| Mercado de cierre (referencia) | 0.9570 | 0.5684 |
| Elo v1 (referencia) | 1.2590 | 0.6290 |

El mercado está mejor calibrado que cualquier modelo, y el cierre apenas supera
al pre-partido (0.9570 vs 0.9598): el mercado es eficiente de apertura a cierre.

## Apuestas v2 en test (umbral fijo 1.05, 1 unidad ficticia, sin empates)

| Métrica | v2 (mercado) | v1 DC (ref) | v1 Elo (ref) |
|---|---|---|---|
| n | 485 | 2.777 | 3.063 |
| ROI | **−24,3%** | −14,1% | −11,6% |
| CLV | 69,1% | 54,7% | 57,3% |
| Drawdown máx | 123,0 u | 403,3 u | 354,8 u |
| Pasa criterio | **NO** | NO | NO |

### Por liga (v2)

| Liga | n | ROI | CLV |
|---|---|---|---|
| D1 Bundesliga | 83 | +16,2% | 63,9% |
| F1 Ligue 1 | 48 | +7,4% | 70,8% |
| E0 Premier | 133 | −35,6% | 73,7% |
| I1 Serie A | 116 | −49,3% | 66,4% |
| SP1 La Liga | 105 | −29,0% | 69,5% |

D1 y F1 en positivo con n=83 y n=48: ruido de muestra chica, no edge.
Ninguna liga muestra ventaja real.

### Resto de la honestidad incómoda
- **n por temporada:** 2324: 250 | 2425: 235 — estable, no se achica (no hay edge que achicarse).
- **Sin filtro** (lado con mayor prob, n=3.504): ROI **+0,98%** ≈ breakeven. Ni la estrategia ingenua más simple pierde plata: el mercado no regala nada.
- **CLV 69% con ROI −24%:** la versión extrema de la paradoja del v1. Batir el cierre no significa nada cuando tu "probabilidad" ES el mercado y tu selección de precio (Max vs Avg) cosecha dispersión de margen, no ineficiencia.

## Por qué pierde el mercado contra sí mismo (interpretación, no número)

La regla `p_market × MaxPrecio ≥ 1.05` selecciona los partidos donde el mejor precio
diverge más del promedio — es decir, **los spots de mayor dispersión/margen entre
casas**. El "edge" medido era margen, no información. Apostar ahí es pagar el
margen con confianza estadística.

## Conclusión

Dos enfoques independientes fallaron por razones distintas y complementarias:
- **v1:** los modelos están mal calibrados vs el mercado (log-loss 1.01–1.26 vs 0.96).
- **v2:** el mercado está bien calibrado, pero no hay edge que extraer de él con
  estas reglas (λ*=0; ROI −24,3%).

El carril queda cerrado por mérito propio, no por falta de intentos. Un v3
honesto necesitaría **información nueva** (movimiento de cuotas en vivo, noticias
de equipos, alineaciones) — no mejor matemática sobre las mismas cuotas.
