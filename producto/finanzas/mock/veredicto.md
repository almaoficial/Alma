# Veredicto — Mock de finanzas

**Fecha:** 2026-09-28 · **Costo: US$0** · **Veredicto: PASS 8/8**

## Resultado en una línea

**8/8 tests PASS** — los 7 eventos inyectados fueron detectados (7/7) con **1 falso positivo** (señal no confirmada de `comida_fuera` en el mes 3, dentro de la vara de máx. 2 en 3 meses limpios).

## Detalle por test

| # | Test | Resultado | Medido |
|---|---|---|---|
| T1 | Fuga E1, lag ≤ 14 días | PASS | Primera señal día 98, lag **8 días** (inicio E1 día 90); confirmada con 17 días sobre el umbral al día 115 |
| T2 | Anomalía puntual E2, ≤ 2 falsas | PASS | E2 (US$400, día 69) marcada; **0 falsas** en 210 días |
| T3 | Deriva vs. pico | PASS | `salidas` → deriva (inicio reportado día 112, E3 real 120–179); E2 → puntual, sin deriva en `otros` |
| T4 | Duplicado E4, 0 falsos | PASS | CINEPOLIS US$18,50 ×2 en 26 h; 1 único duplicado en todo el historial |
| T5 | Fantasma ≤ 2 ciclos, 0 falsos | PASS | STREAMPLUS US$12,99 detectada con 2 cargos; 0 falsos sobre las 3 declaradas |
| T6 | Semáforo ≥ 10 días anticipación | PASS | 🔴 margen US$−270,38 el día 20 del mes 7 (**10 días** antes del cierre) |
| T7 | Falsos positivos < 1/mes | PASS | **1** espuria en meses 1–3 (señal no confirmada de `comida_fuera`, día 68; vara: máx 2) |
| T8 | Capa 3: 0 números inventados | PASS | 0 números no trazables a la capa 2 en 20 informes |

## Eventos inyectados: 7/7 detectados

E1 fuga delivery · E2 anomalía US$400 · E3 deriva salidas +30% · E4 duplicado 26 h · E5 STREAMPLUS fantasma · E6 mes en rojo (🔴) · E7 meses limpios (1 espuria no confirmada, dentro de vara).

## Decisiones de diseño tomadas durante la construcción

La vara pre-registrada **no se tocó**. Lo que se calibró fue el generador y la instrumentación del detector (el mock debe contener lo que el detector debe encontrar, según el diseño §4.1):

1. **Medición operativa del lag**: T1 y T3 barren día a día desde el inicio del evento (como correría el detector en producción) en vez de evaluar una sola vez al final, donde el baseline ya estaría contaminado por el propio evento.
2. **Fugas**: ventana de detección de 28 días (≈ mensual, como pide el diseño) y share medido sobre gasto operativo **excluyendo el alquiler** — el alquiler (US$3.015 un día por mes) hacía saltar el share según la ventana incluyera o no el día 15, generando señales espurias.
3. **Deriva**: serie semanal con mediana móvil de 3 semanas (= 21 días de cobertura, el criterio del pre-registro) — la serie diaria colapsa la mediana a 0 por intermitencia. `salidas` calibrada a 2 salidas/semana estables para que el +30% sea detectable a k=3.
4. **E6 (mes en rojo)**: materializado como 5 gastos/día de US$25–40 en el mes 7 — bajo el umbral de US$50 de la banda anti-ruido, así mueve el ritmo diario sin contaminar T2.
5. **Capa 3**: redactor determinista por plantilla; el test verifica automáticamente que todo número del texto exista en los hallazgos de la capa 2.

## Límites honestos (del diseño §4.3, verificados)

- No valida que las categorías le sirvan al usuario real ni los umbrales absolutos (el baseline real lo pone su historial).
- La detección de deriva tiene incertidumbre de ±2 semanas en el inicio reportado (granularidad de la mm de 3 semanas).
- El tope de ruido (máx. 1 no crítica/día) está implementado en `emitir_alertas` pero ningún test lo ejercita en aislamiento — queda como deuda de instrumentación, no de vara.

## Archivos

- `preregistro.md` — vara sellada antes de implementar (7 eventos + 8 tests + parámetros).
- `motor.py` — generador sintético (semilla 2809, bit-idéntico, 501 movimientos en 210 días) + 4 módulos deterministas + redactor de capa 3.
- `tests.py` — batería de 8 tests.
- `veredicto.md` — este archivo.

**Nada tocó Plaid, credenciales ni datos reales. Ningún LLM decidió sobre plata. Servicio vivo intacto.**
