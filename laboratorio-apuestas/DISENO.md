# Laboratorio de apuestas deportivas — diseño v1

> Proyecto de modelado con CERO dinero real. La pregunta no es "cómo ganar plata apostando".
> La pregunta es: ¿puede un modelo simple encontrar edge contra las cuotas de las casas
> usando solo datos históricos? Refutación primero, como siempre.

**Estado:** diseño pendiente de tu sí. Nada corre hasta que lo apruebes.

---

## 1. La pregunta

¿Un modelo estadístico entrenado solo con resultados pasados puede batir
consistentemente a las cuotas de cierre del mercado en las 5 ligas top de Europa?

Hipótesis nula (la que intentamos NO refutar): **no hay edge**. El mercado
ya tiene toda la información y cualquier "ventaja" del modelo es ruido.

---

## 2. Datos (gratuitos, verificados el 26/9/2026)

### Fuente principal: football-data.co.uk
- **Qué es:** el clásico. CSVs directos con resultados, estadísticas y cuotas
  de hasta 10 casas, con cuotas de **cierre** desde 2019/20.
- **URL base:** https://www.football-data.co.uk/data.php
- **Patrón de descarga:** `https://www.football-data.co.uk/mmz4281/{temporada}/{liga}.csv`
  (ejemplo: https://www.football-data.co.uk/mmz4281/2425/E0.csv)
- **Ligas (top 5, las más líquidas = la vara más dura):**
  `E0` Premier League, `SP1` La Liga, `I1` Serie A, `D1` Bundesliga, `F1` Ligue 1
- **Temporadas:** 2019/20 a 2024/25 (códigos `1920` a `2425`) — 6 temporadas,
  ~380 partidos × 5 ligas × 6 = **~11.400 partidos**.
- **Columnas clave (verificadas en el CSV real):**
  - `FTR` resultado (H/D/A), `FTHG`/`FTAG` goles
  - `HS`/`AS` tiros, `HST`/`AST` tiros al arco (para features)
  - Cuotas tomables: `B365H/D/A`, `AvgH/AvgD/AvgA`, `MaxH/MaxD/MaxA`
  - Cuotas de **cierre**: `B365CH/CD/CA`, `AvgCH/AvgCD/AvgCA`, `MaxCH/MaxCD/MaxCA`
  - Pinnacle cierre: `PSCH/PSCD/PSCA` (ojo: el sitio avisa que desde julio 2025
    los datos de Pinnacle llegan desactualizados — usar con cautela)
- **Tamaño:** cada CSV pesa ~100–300 KB. 30 archivos = unos pocos MB. Descarga liviana.
- **Términos:** uso privado/personal, no comercial. Nuestro uso calza.

### Alternativas (no necesarias para v1, anotadas por si querés ampliar)
- **Kaggle — European Soccer Database** (https://www.kaggle.com/datasets/hugomathien/soccer):
  25.979 partidos, 11 ligas, 2008–2016, con cuotas de 10 casas. Requiere cuenta
  de Kaggle (gratis). Útil como set extra, pero es viejo.
- **Kaggle — mirror de football-data** (https://www.kaggle.com/datasets/mexwell/historical-football-resultsbetting-odds-data):
  31 temporadas de resultados. También requiere cuenta.
- **ClubElo** (http://clubelo.com/): ratings Elo diarios por club, API gratuita
  sin key (`http://api.clubelo.com/YYYY-MM-DD`). Útil como feature externa.
- **The Odds API** (https://the-odds-api.com/): 500 requests/mes gratis, pero
  el histórico real va por plan pago. No la necesitamos: trabajamos con histórico.

---

## 3. Metodología

### Brazos (como en los experimentos ALMA)
1. **Mercado** (baseline): cuotas de cierre promediadas (`AvgCH/CD/CA`) sin
   margen (devigged). Es "la sabiduría de las casas". El modelo tiene que
   ganarle a esto, no a un rival de juguete.
2. **Elo simple**: rating por equipo actualizado solo con resultados pasados.
3. **Dixon-Coles**: el modelo académico clásico (Poisson bivariado con
   corrección para empates). Parámetros por liga, ajustados con ventana móvil.

### Protocolo anti-trampa (walk-forward estricto)
- Cada partido se predice usando **solo datos anteriores a su fecha**. Nada de
  mirar el futuro.
- Split temporal congelado antes de correr:
  - Entrenamiento/ajuste: 2019/20 – 2021/22
  - Validación (para elegir el umbral de apuesta): 2022/23
  - **Test (el que decide el veredicto): 2023/24 – 2024/25**

### Regla de apuesta simulada (plata ficticia, stake plano de 1 unidad)
- Se "apuesta" solo si `prob_modelo × mejor_cuota_tomable ≥ 1.05`
  (edge estimado ≥ 5%).
- Precio tomable: columnas **sin** "C" (ej. `MaxH`, `AvgH`) — lo que había
  disponible antes del partido. Usar el cierre para apostar sería mirar el
  futuro; el cierre se usa solo para medir.
- No se apuesta a empates en v1 (el modelo Dixon-Coles los trata peor;
  simplifica y se declara).

### Métricas
- **ROI**: ganancia / total apostado (en unidades ficticias).
- **n**: cantidad de apuestas simuladas.
- **CLV** (closing line value): % de apuestas donde el precio tomado fue mejor
  que el precio de cierre. Es la métrica que usan los profesionales: si batís
  el cierre de forma consistente, tenés algo real.
- **Log-loss / Brier** del modelo vs el mercado devigged (calibración pura,
  sin apuestas).

---

## 4. Criterios pre-registrados (congelados ANTES de correr)

**PASS** ⟺ en el set de test (2023/24–2024/25, 5 ligas) se cumplen LAS DOS:
1. ROI > **+2%** con n ≥ **200** apuestas simuladas
2. CLV ≥ **55%** (más de la mitad de las apuestas baten el cierre)

**FAIL** en cualquier otro caso. Sin mover el arco después.

**Honestidad incómoda pre-registrada** (se reporta pase lo que pase):
- ROI por liga separada (¿el edge viene de una sola liga?)
- Drawdown máximo (¿cuánto "perderías" en la peor racha?)
- ROI apostando a TODO sin filtro de edge (¿el filtro agrega algo o es maquillaje?)
- n por temporada (¿el edge se achica con el tiempo, como sugiere la literatura?)

---

## 5. Costo y tiempo estimados

- **API de OpenAI: US$0.** Todo el modelado es Python local (Dixon-Coles,
  Elo). El LLM solo se usaría, si querés, para redactar el análisis final
  (< US$0,10). Por defecto: nada de key.
- **Tiempo:** descarga ~15 min, limpieza ~30 min, modelado walk-forward
  1–3 hs de cómputo local, análisis y veredicto ~1 h. Total: una tarde/noche,
  corriendo en segundo plano.

---

## 6. Qué NO incluye (límites duros)

- ❌ Crear cuentas en casas de apuestas
- ❌ Apostar dinero real (ni un dólar)
- ❌ APIs pagas ni suscripciones
- ❌ Scraping agresivo (respetar los términos del sitio: uso privado)

---

## 7. Pasos pendientes de tu aprobación

1. **Tu "sí" a este diseño** (o correcciones — es tu loop).
2. Descarga de los 30 CSVs (~5–10 MB total). Liviana, pero no la hago sin tu sí.
3. Opcional: cuenta de Kaggle si después querés el dataset 2008–2016 como
   ampliación. No hace falta para v1.

---

## 8. Nota honesta antes de empezar

Las 5 ligas top son los mercados más eficientes del planeta: miles de
profesionales y syndicates los mastican a diario. Lo esperable, por base rate,
es **FAIL**. Y que quede claro: un PASS acá significaría "el modelo encontró
una ineficiencia en datos pasados", NO "salí a apostar". Entre un backtest y
plata real hay un abismo (overfitting, varianza, límites de cuenta, cuotas que
se mueven). Este laboratorio es para estudiar, como pediste.
