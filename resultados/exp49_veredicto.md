# ALMA-EXP49 — Veredicto: PASS + LÍNEA ABIERTA (fase mock)

**Fecha:** 2026-09-27 ~15:20 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Pre-registro:** `resultados/exp49-20260927/preregistro.json` (escrito antes de correr)

## Qué se testea

La variante (b) descartada en EXP48: el umbral de soporte se **endurece con
el horizonte**. A más recurrencias vistas por la firma (K = bloques pasados
no-saltados con la misma firma que aportaron comparación pareada), más
victorias exige la skill para disparar el skip: `umbral(K) = 2 + floor(K/3)`.
Un solo moving part respecto al control (el skip de EXP47 importado
verbatim): el umbral. Todo lo demás — firma, skill_arm, conteo de victorias,
definición de misfire, diagnóstico ex post, seeds de RNG, contabilidad
honesta — es idéntico.

**Criterio pre-registrado:** (1) media(efecto) < 0; (2) tasa de misfires del
tratamiento < 0.30. PASS ssi (1) y (2).

**Criterio de CIERRE pre-registrado:** la línea se cierra ssi (c1) efecto
medio ≥ −1,5 **Y** (c2) misfires ≥ 30% **Y** (c3) el efecto sigue cargado por
una sola réplica (sin la mejor, la media sería ≥ 0).

## Números

| Réplica | efecto | reg ctrl | reg trat | skips ctrl (mis) | skips trat (mis) | umbrales trat |
|---|---|---|---|---|---|---|
| 0 | +0,00 | 81,0 | 81,0 | 9 (3) | 4 (1) | {3: 4} |
| 1 | +1,00 | 87,0 | 88,0 | 5 (1) | 0 (—) | {} |
| 2 | −4,00 | 96,0 | 92,0 | 7 (4) | 0 (—) | {} |
| 3 | −5,00 | 102,0 | 97,0 | 8 (3) | 5 (0) | {2: 5} |
| 4 | −1,00 | 83,0 | 82,0 | 9 (3) | 5 (1) | {2: 5} |

**Efecto medio: −1,80 → (1) SÍ** (−1,80 < 0).
**Misfires tratamiento: 2/14 (tasa 0,143) → (2) SÍ** (< 0,30; EXP47: 0,368;
EXP48: 0,333).
**Misfires control (sanidad): 14/38 (0,368)** — reproduce EXP47 exacto.
Regret medio: control 89,80 · tratamiento 88,00 · mejor fija 84,20.
Reproducibilidad del control vs EXP47 (bit-idéntico): **True**.
Cierre: (c1) −1,80 ≥ −1,5 → **NO** | (c2) 0,143 ≥ 0,30 → **NO** |
(c3) media sin la mejor réplica = −1,00 ≥ 0 → **NO** →
**la línea sigue abierta** (regla pre-registrada).

Detalle de saltos y diagnóstico por bloque (rep 0):
`resultados/exp49-20260927/report.json`.

## Honestidad incómoda

1. **La baja de misfires viene de saltar mucho menos, no de saltar mejor.**
   El tratamiento saltó 14 bloques contra 38 del control. En 2 de 5 réplicas
   (1 y 2) no saltó ni una vez: el mecanismo estuvo completamente dormido. La
   "mejora" es abstención, no ejecución.
2. **El endurecimiento también mata saltos buenos.** Réplica 1: el control
   saltó 5 bloques con solo 1 misfire (4 saltos buenos); el tratamiento no
   saltó ninguno y perdió 1 punto (+1,00). El umbral más exigente no distingue
   entre victoria ruidosa y skill sana: recorta parejo.
3. **La marcha más dura nunca engranó.** Ningún skip ocurrió con umbral 4
   (K=6,7): con 8 recurrencias por régimen, 4 victorias pareadas sobre ≤7
   oportunidades nunca se materializó. El endurecimiento operó solo entre
   los umbrales 2 y 3; su setting más exigente quedó sin testear en la
   práctica.
4. **No mueve el diagnóstico estructural.** Tratamiento 88,00 vs mejor fija
   84,20: ~3,8 puntos abajo. Quinta marca seguida de la línea en el mismo
   rango (~4–7 puntos bajo la mejor fija): ninguna maquinaria con
   exploración le gana sistemáticamente a la mejor fija en un mundo que rota.
5. **El efecto ya no lo carga una sola réplica** — 4 de 5 réplicas son ≤ 0 y
   sin la mejor (−5,00) la media sigue en −1,00. Es el primer dato
   distributivo de la línea; también es el más chico en magnitud absoluta
   después de EXP46.
6. **Condición de alcance intacta:** todo ocurre en el mundo construido con
   recurrencia garantizada. En el feed real (rotación 8/8) el mecanismo
   seguiría sin activarse ni una vez.

## Veredicto

**PASS.** Las dos partes pre-registradas se cumplen con margen: efecto medio
−1,80 y misfires 14,3% (< 30%). El umbral endurecido funciona en la
dirección correcta y por primera vez el efecto no depende de una sola
réplica.

**Dictamen de cierre: LA LÍNEA SIGUE ABIERTA.** Ninguna de las tres
condiciones de cierre pre-registradas se cumple: el efecto (−1,80) supera la
vara de −1,5, los misfires (14,3%) están bajo el 30%, y el efecto está
distribuido entre réplicas.

## Recomendación

La regla de cierre manda continuar, pero la honestidad manda decir qué
continuar: el próximo mock no debería endurecer más el umbral (la marcha 4
nunca engranó y el recorte ya mata saltos buenos). La pregunta abierta real
es si el valor está en la *selectividad* y no en la *skill*: un control que
salte con la misma tasa (14/38) pero eligiendo bloques al azar — o por una
regla tonta — diría si el −1,80 viene de elegir bien o simplemente de saltar
menos. Si la selectividad aleatoria empata, el mecanismo de skills no aporta
nada que la abstención no aporte: ahí sí, cierre.
