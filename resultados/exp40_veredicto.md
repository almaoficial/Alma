# EXP40 — Veredicto: FAIL

**Fecha:** 2026-09-27 · **Modo:** mock, replay puro, US$0 · **Duración:** <1s
**Pre-registro:** `resultados/exp40-20260927/preregistro.json` (escrito antes de correr)
**Código:** `run_experiment40.py` · **Datos:** idénticos a EXP36–39 (Kraken XBTUSD 1h, 720 velas, 719 retornos)
**Réplicas:** 6 · **Comparación:** common random numbers contra regla36 (EXP36) y buyhold

## Diseño
Test de régimen previo al probe: exponente de Hurst por R/S sobre los
retornos logarítmicos de las 72h previas al bloque (umbral pre-registrado
H ≥ 0.55 → tendencia). Política condicional sin probe: tendencia →
momentum todo el bloque; lateral → flat todo el bloque. Bloque 0 (sin
historia) → lateral por defecto.

## Criterio pre-registrado
efecto = P&L_exp40(réplica) − P&L_buyhold. PASS si media(efecto) > 0 y
media(efecto) − 1×desvío > −0.01. Sin mover la vara.

## Números

| Política | P&L total | efecto vs buyhold (media ± desvío) |
|---|---|---|
| **EXP40** (test de régimen → momentum/flat) | **−10,7313%** | **−19,24% ± 0,00** (determinista) |
| regla36 (EXP36, CRN, 6 réplicas) | +8,52% … +15,71% | +3,43% ± 3,61% |
| buyhold (referencia fija) | +8,5041% | — |

**→ FAIL.** Media del efecto −19,24%, muy lejos del umbral.

### Secundario honesto: ¿clasifica bien el régimen?
Definición pre-registrada de verdad ex-post: |retorno del bloque| > 0,02.
Medido en bloques 1–29:

- Acierto: **14/29 = 48,3%** (moneda cargada apenas).
- Clasificó tendencia en **20** bloques; verdad ex-post: **7**.
- Precisión 6/20 = **30%** · Recall 6/7 = **86%**: sobre-detecta tendencia.

### Diagnóstico por bloques (post-hoc, descriptivo)
- En los 6 bloques de tendencia **bien** clasificados: momentum **+2,92%**
  vs buyhold **+5,29%**. Aun con el régimen correcto, el brazo elegido
  pierde contra no hacer nada: a escala horaria, "retornos persistentes"
  no implica que el momentum horario gane (el hallazgo de microestructura
  de EXP36 sigue en pie).
- En los 14 **falsos positivos**: momentum **−13,63%** vs buyhold −6,63%.
  La sobre-detección puso el brazo perdedor en bloques laterales.
- Contrafactual post-hoc (NO pre-registrado, NO es un resultado):
  tendencia→buyhold / lateral→flat con este clasificador habría dado
  **−1,44%**. El clasificador —no solo el brazo— es la restricción
  activa: sus falsos positivos destruyen el valor de cualquier mapeo.

## Corrección metodológica durante el experimento (declarada)
El **run 1** usó un estimador de Hurst mal implementado (R/S sobre
*niveles* de log-precios con S = desvío de niveles): da H ≈ 0,91 para un
random walk sintético, es decir, no estima nada; clasificó "tendencia"
en 29/29 bloques y el run dio −16,82%. Se detectó, se corrigió a R/S
sobre *retornos* (verificado en sintéticos: RW → 0,49; AR persistente →
0,58; AR anti-persistente → 0,47) y se re-corrió como corrida oficial.
Archivos del run buggy preservados:
`report_run1_hurst_levels_bug.json`, `preregistro_run1.json`.
**El criterio pre-registrado no cambió**; solo se arregló el instrumento
para que mida lo que el diseño decía que medía.

## Honestidad incómoda
1. **El FAIL se sostiene con el instrumento corregido**, pero la serie
   arrastra el pecado original: el umbral H ≥ 0,55 se pre-registró sin
   calibrar (el mismo pecado del 0,02 de EXP37, solo que declarado).
2. **regla36 con estas 6 semillas le gana a buyhold** (+3,43% ± 3,61%).
   No es un efecto-regla: es la lotería de semillas que EXP39 documentó
   (±10 pts). Con otras 6 semillas el ranking se invierte. No leer nada
   en ese número.
3. **n=1, drift +8,55%**: todo el ranking vive dentro de una ventana que
   favorece a buyhold, como en toda la serie 36–40.
4. **El clasificador se evaluó contra una verdad ex-post cruda**
   (|retorno| > 2%): un bloque puede ser "tendencia" en sentido Hurst y
   no superar el 2%, o superarlo por un salto discreto sin persistencia.
   La métrica secundaria mide *utilidad*, no *verdad*.

## Conclusión
La pregunta de EXP40 ("¿un test de régimen previo al probe cambia el
juego?") recibe un **no** con esta implementación: el test no discrimina
(48%) y el mapeo de brazos es wrong aun cuando acierta. El régimen sigue
siendo la pregunta correcta; el instrumento y el umbral, no.

## Próxima idea servida
EXP41: calibrar el test **fuera de muestra** — estimar el umbral de Hurst
(y la ventana) en un período *distinto* (p. ej. los 30 días previos de BTC
u otro activo), pre-registrarlo, y testearlo en este stream. Si la
calibración no sobrevive al cambio de período, la conclusión es que el
Hurst-72h no tiene señal explotable a esta escala y hay que cambiar de
familia de test (p. ej. ADX, varianza realizada, o test de "¿hay señal?"
antes de clasificar dirección).
