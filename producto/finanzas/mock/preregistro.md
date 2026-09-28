# Pre-registro — Mock de finanzas

**Fecha:** 2026-09-28 · **Costo: US$0** · **Determinista, sin Plaid, sin datos reales.**
Escrito ANTES de implementar el generador y los módulos. La vara queda sellada acá; si un test falla, se rediseña la regla, no la vara.

## 1. Perfil sintético (100% inventado)

- "Usuario tipo": ingreso mensual ~US$3.000 irregular (picos declarados de US$4.000 en dos meses).
- Alquiler US$3.015 debitado día 15, con reembolsos parciales simulados por Zelle.
- Tarjeta con límite US$1.000 (fondo, no usada como decisión).
- Ventana: 6 meses de historia diaria + mes 7 corriente (el "ahora" del mock).
- Semilla fija: `SEED = 2809`. Todo el generador es determinista (PRNG con semilla fija); la misma semilla produce bit-idénticos los movimientos.

## 2. Eventos inyectados (ground truth)

| # | Evento | Parámetros exactos |
|---|---|---|
| E1 | Fuga de delivery | Categoría `delivery`: mediana base ~US$120/mes; del día 1 del mes 4 al día 15 del mes 6 (6 semanas) la mediana se duplica a ~US$240/mes. |
| E2 | Anomalía puntual | Un cargo único de US$400 en `otros`, mes 3, día 10 — fuera de cualquier banda razonable. |
| E3 | Deriva en salidas | Categoría `salidas`: +30% sostenido sobre su mediana durante los meses 5 y 6 completos (8 semanas). |
| E4 | Gasto duplicado | Dos cargos idénticos: comercio `CINEPOLIS`, US$18,50, con 26 h de diferencia, mes 4. |
| E5 | Suscripción fantasma | Cargo mensual nuevo `STREAMPLUS` US$12,99, aparece los días 3 de los meses 5 y 6; NO está en la lista declarada de suscripciones (`NETFLIX`, `SPOTIFY`, `GYM`). |
| E6 | Mes en rojo | Mes 7 (corriente): ritmo de gasto diario tal que la proyección NO llega a la cuota simulada del mes (cuota mes 7 = US$1.300, saldo inicial simulado US$2.900, sin ingresos declarados en el mes). |
| E7 | Ruido limpio | Meses 1, 2 y 3 sin ningún otro evento inyectado (E2 vive en mes 3 pero es puntual y aislado): sirven para medir falsos positivos. |

Lista declarada de suscripciones (mock): `NETFLIX` US$15,49, `SPOTIFY` US$10,99, `GYM` US$29,99 — cargos mensuales fijos días 1–5.

## 3. Tests pre-registrados (8)

| # | Test | Vara (sellada) |
|---|---|---|
| T1 | Detección de fuga | Encuentra E1 con ≤ 2 semanas de lag desde el inicio de la fuga (mes 4, día 1 → detección a más tardar mes 4, día 15). |
| T2 | Anomalía puntual | Marca E2; y en todo el historial de 7 meses genera ≤ 2 anomalías falsas adicionales (eventos marcados que no son E2 ni parte de E1/E3). |
| T3 | Deriva vs. pico | Clasifica E3 como **deriva** y E2 como **puntual**; no al revés. Criterio operativo: deriva = mediana móvil de la categoría fuera de banda ≥ 3 semanas consecutivas; puntual = 1 movimiento fuera de banda sin persistencia. |
| T4 | Duplicado | Detecta E4 con la regla de 48 h (mismo comercio normalizado, mismo monto exacto, Δt < 48 h). Cero duplicados falsos en el resto del historial. |
| T5 | Suscripción fantasma | Lista `STREAMPLUS` como "no declarada" en ≤ 2 ciclos desde su primera aparición (mes 5 → detectada a más tardar con el cargo del mes 6). Cero fantasmas falsos sobre las 3 declaradas. |
| T6 | Semáforo de deudas | El mes 7 da 🟡 o 🔴 con ≥ 10 días de anticipación al cierre del mes (detección a más tardar el día 20 del mes 7). |
| T7 | Tasa de falsos positivos | < 1 alerta espuria por mes en los meses 1–3 (E7): como máximo 2 alertas espurias en total en los 3 meses limpios. No cuenta E2 (es un evento inyectado real). |
| T8 | Capa 3 (redacción) | El redactor es determinista en el mock: plantilla fija que inserta solo números de la capa 2. Se generan 20 informes; 0 números que no vengan de la capa 2 (verificación automática: todo número del texto debe aparecer en el dict de hallazgos). |

## 4. Parámetros deterministas sellados (capa 2)

- Baseline por categoría: mediana y MAD con ventana móvil de 90 días.
- Anomalía: `|gasto − mediana| > 3 × MAD`, y además `|gasto| > US$50` (banda anti-ruido).
- Fuga: categoría discrecional (`delivery`, `salidas`, `comida_fuera`) con share mensual > mediana de share de 3 meses + 2 × MAD del share, durante ≥ 2 semanas consecutivas.
- Deriva: mediana móvil (21 días) de la categoría fuera de `mediana ± 3×MAD` por ≥ 3 semanas consecutivas.
- Duplicado: mismo comercio (normalizado a mayúsculas, sin espacios) + mismo monto exacto + Δt < 48 h.
- Semáforo: proyección día a día hasta fin de mes con mediana de gasto diario últimos 30 días. 🟢 margen ≥ US$200 sobre la cuota; 🟡 margen US$0–200; 🔴 no llega. Sin ingresos declarados en el mes → proyección solo con saldo y gasto.
- Tope de ruido: máximo 1 alerta no crítica por día; críticas (cuota en riesgo, saldo bajo) sin tope pero agrupadas por tema.
- Saldo bajo (días 5 y 10): proyección al día 15 < US$2.500 → alerta crítica.

## 5. Veredicto

**PASS** si y solo si se cumplen los 8 tests. Un solo FAIL → rediseño de la regla correspondiente, se re-corre la batería completa, se registra el cambio. La vara no se toca.
