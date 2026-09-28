# ARENA ALMA-trading — Preregistro (papel, US$0)

**Escrito antes de la primera corrida de la arena. No se mueve.**

## Pregunta
¿Alguna versión de ALMA (v1, v2) le quita el título a la reversión fija,
campeona del período 2021–2026 (+265,9%), compitiendo en varias ventanas
independientes con calibración estrictamente causal?

## Competidores
- **Retadores (calibran por ventana):** ALMA v1, ALMA v2.
  - v1 = loop con prior mapless "mejor global desde el día 0" (sin
    decaimiento) + EVI sin penalidad por churn + detección de cambios.
  - v2 = loop con prior con decaimiento (vida media 252d, fijada) + EVI con
    penalidad por churn + detección de cambios.
- **Baselines fijos (sin calibrar):** hold (SPY), momentum, reversión, cash.
  La reversión fija arranca como **campeona defensora** por su +265,9% en
  2021–2026. Los baselines no pueden tomar el título (no son retadores);
  figuran en la tabla como referencia.

## Ventanas (no solapadas, fijadas antes de correr)
1. 2016-01-01 → 2017-12-31
2. 2018-01-01 → 2019-12-31
3. 2020-01-01 → 2021-12-31
4. 2022-01-01 → 2023-12-31
5. 2024-01-01 → 2026-09-25 (hasta el último dato disponible)

## Calibración causal (por ventana, por retador)
- Datos de calibración: [2015-01-02, inicio_ventana). Nada posterior.
- Regla de selección: mayor retorno neto in-sample (igual que v1/v2).
- Grilla v1 (espacio nativo, 18 combos): ventana_probe ∈ {42, 63},
  umbral_evi ∈ {2, 3, 5}, umbral_cd ∈ {1.5, 2.0, 2.5}.
- Grilla v2 (espacio nativo, 54 combos): lo mismo +
  penalidad_churn ∈ {0.0, 0.005, 0.01}.
- La ventana 1 calibra solo con 2015 (252 días): ruidoso pero honesto,
  declarado acá.

## Período efectivo de evaluación (igual para todos)
Cada ventana se evalúa en [inicio + 126 días hábiles, fin]. Los primeros
126 días son calentamiento común (warmup máximo del loop). Todos los
competidores se miden sobre el mismo tramo.

## Métricas por ventana y competidor
Retorno neto, Sharpe anualizado (rf=0), máximo drawdown (pico/p − 1).
Capital inicial US$10.000 en papel. Costos 10bps/pata, sin apalancamiento
ni cortos. Todo causal: en el día t solo se usa información hasta t.

## Criterio de campeonato (numérico, no se mueve)
Un retador **destrona al campeón** si y solo si en **≥3 de las 5 ventanas**
cumple simultáneamente:
1. retorno_neto(retador) > retorno_neto(campeón), **y**
2. max_drawdown(retador) ≤ 1.2 × max_drawdown(campeón)
   (si maxDD(campeón) = 0, la condición 2 es maxDD(retador) ≤ 0.02).

Orden de los asaltos (fijado): v1 reta primero al campeón vigente; luego
v2 reta al campeón vigente en ese momento. Si nadie cumple, el título no
se mueve.

## Tabla de posiciones
`ARENA.md`: filas = competidores, columnas = ventanas + agregado
(retorno medio, drawdown medio, ventanas ganadas vs campeón). Diseñada
para que v3, v4, ... entren como filas nuevas sin reescribir nada
(ver "Cómo entra un retador nuevo" en ARENA.md).

## Riesgos declarados (antes de correr)
1. 5 ventanas × 2 años: muestra chica; el veredicto es por ventana, no
   un número único.
2. El universo sigue siendo 7 nombres large-cap USA líquidos (SPY, QQQ,
   AAPL, MSFT, TSLA, XLE, GE): no es "la bolsa".
3. La calibración maximiza retorno in-sample: riesgo de sobreajuste por
   ventana, mitigado por grillas chicas y ventanas out-of-sample.
4. Costos de 10bps optimistas para retail; papel ≠ real (sin impacto de
   mercado, impuestos ni emociones). Ningún resultado autoriza dinero
   real. El guardián de `banco_papel.py` sigue vigente.

---

# ADDENDUM v3 (2026-09-27) — escrito ANTES de correr la arena con v3. No se mueve.

## Qué cambia
- **Tercer retador:** "ALMA v3" (orden 3: reta al campeón vigente en último
  lugar, después de v1 y v2).
- **Criterio de destronamiento:** idéntico al pre-registrado (≥3/5 ventanas
  con retorno_neto > campeón Y max_drawdown ≤ 1.2× campeón). Sin mover.
- **Ventanas, calibración causal, período efectivo, métricas, costos:** idénticos.

## Diseño v3 (fijado por principio, no tuneado a las ventanas)
La v3 encarna tres lecciones del transcript:
1. El meta-loop "elegir la mejor estrategia reciente" ES momentum sobre
   estrategias (whipsaw v1/v2: ~28 cambios, compra techos / vende pisos).
2. Lo que ALMA sí hace bien: control del drawdown, no el retorno.
3. Estudiar no CUÁL va ganando sino CUÁNDO gana cada uno (mapa clima→brazo).

Constantes, todas fijadas por principio antes de ver ninguna ventana:
- **Régimen diario observable y causal:** tendencia = signo del retorno SPY
  trailing 63d (un trimestre; "alcista"/"bajista"); vol = vol realizada 21d
  (un mes) vs mediana trailing (máx 252d, mín 63d; "alta"/"baja"). Sin
  umbrales tuneados: signo y mediana. → 4 climas.
- **Mapa clima→brazo con decaimiento (EXP9):** cada brazo corre en sombra
  (papel, con costos) desde el día 0; por celda (clima, brazo) se acumulan
  retornos diarios con decaimiento exponencial de vida media 252d (la misma
  constante principista de v2). Score = Sharpe decayed; cada clima elige el
  brazo con mejor score. Lo reciente pesa más que lo viejo.
- **Objetivo riesgo-ajustado:** el score es Sharpe (retorno/vol), no retorno
  puro — apostar a la fortaleza demostrada (control del riesgo).
- **Anti-sobrecalentamiento (histéresis):** el régimen oficial cambia solo si
  la lectura mensual nueva se confirma 2 meses seguidos; el brazo cambia SOLO
  cuando cambia el régimen oficial. Sin persecución del ganador de turno.
- **Freno de emergencia principista:** si el brazo actual rinde a z < -3.0
  en 21d (cola extrema ~0.13%), cambio forzado al mejor del mapa para el
  régimen vigente. Se cuenta cada disparo (si dispara mucho, es un dato en
  contra del diseño).
- **Sin brazo inicial arbitrario:** si el mapa no tiene evidencia suficiente
  en un clima (peso decayed < 21d), elige "hold".
- Paso de decisión 21d y warmup 126d: alineados con v1/v2 y la arena.

## Grilla de calibración v3
Vacía por diseño: todas las constantes están fijadas por principio (lista
arriba). La calibración corre trivialmente (1 combo). Esto es intencional:
la pregunta es si un diseño principista le gana a diseños tuneados por
ventana.

## Chequeo de robustez pre-registrado
Se reporta sí o sí, gane o no la v3:
1. Estabilidad del mapa clima→brazo entre ventanas: ¿el mismo clima mapea al
   mismo brazo en las 5 ventanas, o cambia arbitrariamente? (fracción de
   acuerdo por clima; 5/5 = estable, ~2/5 = arbitrario).
2. Cambios de brazo por ventana (el anti-churn debe mostrar pocos cambios
   vs los ~28 de v1/v2).
3. Disparos del freno de emergencia por ventana.

## Riesgo declarado
Sobreajuste al meta-nivel: la v3 se diseña DESDE las lecciones (whipsaw,
fortaleza en drawdown, clima vs ganador), no tuneando parámetros hasta
ganarle a la reversión en estas ventanas. El chequeo (1) es la defensa: un
mapa inestable entre ventanas invalida la historia aunque el número gane.
