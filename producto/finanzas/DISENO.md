# Detector de patrones de gasto — Diseño

**Fecha:** 2026-09-28 · **Frente 7/10** · **Costo: US$0** · **Fase: solo diseño**
**Idioma:** español rioplatense (voseo).

Esto no es un producto que mueve plata. Es un espejo: te muestra en qué se va, antes de que te des cuenta solo. Todo lo que sigue es diseño + plan de mock; acá no se toca ni un dato real, ni Plaid, ni el servicio vivo.

---

## 1. Qué patrones detectaría

Cuatro módulos, en orden de valor para vos:

### 1.1 Fugas por categoría
La pregunta "¿en qué se me va la plata" tiene una respuesta técnica: categorías que chupan más de lo que creés. El detector:

- Agrupa gastos en categorías (comida fuera, súper, transporte, suscripciones, etc.) con reglas de mapeo deterministas a partir de la descripción del movimiento.
- Calcula **share por categoría** (qué % de tu gasto mensual se va en cada una) y su **tendencia** (¿sube o baja mes a mes?).
- Marca una **fuga** cuando una categoría discrecional (ej. delivery, salidas) supera un umbral relativo que vos mismo definís o que se calibra con tu baseline (ej. > 2 desvíos sobre tu mediana de 3 meses).
- Reporta siempre en tus términos: "este mes el delivery te comió US$X, que es US$Y más que tu promedio".

**No hay juicio de valor.** El sistema no te dice "gastás mucho en X" como sermón: te muestra el número y la comparación. Vos decidís.

### 1.2 Anomalías vs. baseline
- Construye un **baseline personal**: mediana y dispersión por categoría con ventana móvil de 90 días (robusto a outliers, sin suponer normalidad).
- Un gasto es **anomalía** si queda fuera de la banda esperada: `|gasto − mediana| > k × MAD` (MAD = desviación absoluta mediana; `k` pre-registrado, default 3).
- Distingue **anomalía puntual** (una compra grande un día) de **deriva** (la mediana de la categoría se movió de forma sostenida 3+ semanas). La deriva importa más que el pico.
- **Regla anti-falsos-positivos:** un movimiento solo genera alerta si también es relevante en magnitud absoluta (ej. > US$50) — no te va a molestar por un café de US$4,20 que se salió 10 centavos de la banda.

### 1.3 Proyección del plan de deudas
Tu plan es concreto: US$1.300 oct / US$2.200 nov / US$2.200 dic → deuda cero a fin de año (US$5.700: 2.400 Joaco + 2.400 Bauti + Mundial 3×300). El detector lo convierte en un semáforo:

- **Inputs:** saldo actual (Plaid), gasto diario registrado, ingresos esperados que vos declares (ej. US$4.000 nov/dic).
- **Proyección:** simula el flujo día a día hasta fin de mes con tu ritmo de gasto actual (mediana de gasto diario de los últimos 30 días, no el promedio — los picos no tienen que distorsionar).
- **Semáforo:**
  - 🟢 Vas encaminado: la proyección deja margen ≥ US$200 sobre la cuota del mes.
  - 🟡 Ajuste fino: margen entre US$0 y US$200 — te dice cuánto tendrías que recortar por día para volver a verde.
  - 🔴 Riesgo: la proyección no llega a la cuota — te lo dice con días de anticipación, no el día 30.
- **Colchón US$300:** el mismo motor proyecta si llegás al primer objetivo del colchón; si el plan de deudas y el colchón compiten por el mismo peso, te muestra el trade-off en números, no te elige por vos.

### 1.4 Alertas
Solo las que importan, con umbrales configurables por vos:

| Alerta | Dispara cuando |
|---|---|
| Saldo bajo (días 5 y 10) | Proyección al día 15 < US$2.500 antes del alquiler |
| Fuga nueva | Una categoría discrecional rompe su banda 2 semanas seguidas |
| Cuota en riesgo | Semáforo del plan de deudas en 🟡 o 🔴 |
| Gasto duplicado sospechoso | Dos cargos idénticos (mismo comercio, mismo monto) en < 48 h |
| Suscripción fantasma | Cargo recurrente mensual que no aparece en tu lista declarada |

**Regla de ruido:** máximo 1 alerta no crítica por día; las críticas (cuota en riesgo, saldo bajo) no tienen tope pero se agrupan por tema. Un detector que spamea es un detector que se ignora.

---

## 2. Arquitectura

### 2.1 Reglas deterministas primero — siempre

Principio innegociable: **ningún LLM decide sobre tu plata.** Ni categoriza movimientos que disparan alertas, ni interpreta tu situación financiera, ni recomienda acciones con plata.

La arquitectura es en capas:

```
┌─────────────────────────────────────────────┐
│ CAPA 1 — Ingesta (determinista)              │
│ Plaid read-only + gastos registrados en chat │
│ Normalización: fecha, monto, comercio,       │
│ categoría por reglas de mapeo               │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ CAPA 2 — Detección (determinista)           │
│ Baselines (mediana/MAD), fugas, anomalías,  │
│ proyección del plan, alertas.               │
│ TODO acá es código con umbrales explícitos. │
│ Un LLM jamás toca esta capa.                │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ CAPA 3 — Redacción (LLM, solo texto)        │
│ Recibe los HALLAZGOS ya calculados y los    │
│ redacta en tu idioma, en criollo.           │
│ No calcula, no interpreta, no decide.       │
│ Si no hay hallazgos, no hay texto.          │
└─────────────────────────────────────────────┘
```

El LLM de la capa 3 es un redactor con los números ya cerrados: recibe "delivery: US$180 este mes vs mediana US$110, +63%" y lo escribe lindo. Si el redactor alucina un número, el número no existe en ningún lado porque la capa 2 es la única fuente de verdad y sus salidas son auditables.

**Trazabilidad:** cada alerta guarda qué regla la disparó, con qué umbral y con qué datos. Podés preguntar "¿por qué me avisaste esto?" y la respuesta es una regla, no una vibra.

### 2.2 El loop de ALMA, después, solo como detector

Cuando el sistema determinista esté validado en mock, el loop de ALMA puede entrar **solo en rol de detector de segundo orden**, nunca como decisor:

- **Qué haría:** minar firmas de tus propios patrones (ej. "los meses que el gasto en salidas sube en la primera quincena, la cuota de la deuda llega ajustada"), proponer *candidatos* de reglas nuevas.
- **Puerta de calidad:** toda regla candidata pasa por validación en dos splits de tus datos históricos (mock primero, reales después) — solo se adopta si mejora la precisión de detección sin aumentar falsos positivos, y **solo con tu "sí"** (freno humano vigente).
- **Qué NO haría jamás:** cambiar umbrales solo, ejecutar acciones, "optimizar" tu gasto, ni tocar la capa 2 sin pasar la puerta.

En criollo: ALMA puede sugerirte "che, mirá que este patrón se repite", pero la que decide si eso se convierte en una alerta sos vos, y la que dispara la alerta es una regla con tu aprobación.

---

## 3. Qué datos necesita y de dónde

| Dato | Fuente | Cómo llega | Frecuencia |
|---|---|---|---|
| Movimientos y saldos | Plaid (Bank of America) | **Solo lectura**, vía conector existente | Diaria (batch nocturno) |
| Gastos en el momento | Vos en el chat ("35 supermercado") | Registro manual con fecha/hora | En el momento |
| Ingresos esperados | Vos (US$4.000 nov/dic, etc.) | Declarado, no inferido | Cuando cambian |
| Cuotas del plan | Pre-registrado (1.300/2.200/2.200) | Configuración | Fijo hasta que vos lo cambies |
| Categorías | Mapeo determinista comercio→categoría | Reglas + tu corrección ("esto fue laburo, no salida") | Continuo |

**Reglas de datos:**

- **Nunca se infiere un ingreso** de los movimientos para proyectar: si no lo declaraste, la proyección trabaja solo con lo medido y te avisa qué supuesto está usando.
- **El efectivo se cuenta aparte**, como ya hacés: el detector suma tu registro de efectivo, no intenta adivinarlo del banco.
- **Corrección del usuario manda:** si categorizaste algo a mano, esa etiqueta vale más que la regla. El sistema aprende tu mapeo, no al revés.
- **Retención:** los datos crudos viven donde ya viven (Plaid, tu chat); el detector guarda solo agregados y eventos de alerta. Nada de data lake con tu vida financiera.

**En esta fase: nada de esto se toca.** El diseño se valida con el mock de la sección 4 antes de pedirle permiso a ningún dato real.

---

## 4. Diseño del mock (validación US$0 antes de datos reales)

### 4.1 Generador de datos sintéticos

Un script genera un historial financiero ficticio pero realista, calibrado a tu situación **sin usar tus datos reales**:

- **Perfil sintético "usuario tipo":** ingreso mensual ~US$3.000 (irregular, con picos declarados de US$4.000 en dos meses), alquiler US$3.015 debitado día 15 con reembolsos parciales por Zelle simulados, tarjeta con límite US$1.000.
- **Categorías con distribuciones:** súper (US$200–350/mes), delivery/comida fuera (US$80–200/mes, con deriva programada en un trimestre), transporte, suscripciones fijas (3–4 cargos mensuales idénticos), salidas (alta varianza), "otros".
- **Eventos inyectados a propósito** (el mock tiene que contener lo que el detector debe encontrar):
  1. Una **fuga**: el delivery duplica su mediana durante 6 semanas.
  2. Una **anomalía puntual**: un cargo único de US$400 fuera de banda.
  3. Una **deriva**: la categoría "salidas" sube 30% sostenido por 2 meses.
  4. Un **gasto duplicado**: dos cargos idénticos en 24 h.
  5. Una **suscripción fantasma**: cargo mensual nuevo no declarado.
  6. Un **mes en rojo**: ritmo de gasto que no llega a la cuota simulada del plan de deudas.
  7. **Ruido**: 3 meses limpios sin eventos, para medir falsos positivos.

### 4.2 Batería de validación (criterios pre-registrados)

| Test | Vara |
|---|---|
| Detección de fuga | Encuentra el evento 1 con ≤ 2 semanas de lag |
| Anomalía puntual | Marca el evento 2 sin marcar > 2 falsos positivos en todo el historial |
| Deriva vs. pico | Clasifica 3 como deriva y 2 como puntual (no al revés) |
| Duplicado | Detecta el evento 4 con la regla de 48 h |
| Suscripción fantasma | La lista como "no declarada" en ≤ 2 ciclos |
| Semáforo de deudas | El mes 6 da 🟡/🔴 con ≥ 10 días de anticipación al cierre |
| Tasa de falsos positivos | < 1 alerta espuria por mes en los 3 meses limpios |
| Capa 3 (redacción) | 0 números inventados en 20 informes generados (revisión manual) |

**Veredicto:** PASS si cumple las 8; si falla cualquiera, se rediseña la regla, no se baja la vara. Recién con el mock en verde se habla de conectar datos reales — y esa conexión es otra decisión tuya, en otro momento.

### 4.3 Lo que el mock NO valida (límites honestos)

- No valida que las categorías te sirvan a vos (eso se calibra con tus correcciones reales).
- No valida montos ni umbrales absolutos (el baseline real lo pone tu historial).
- No valida la proyección de ingresos irregulares más allá del perfil sintético.

---

## 5. Límites explícitos — qué NO haría nunca

1. **Nunca mueve plata.** Ni pagos, ni transferencias, ni "optimizaciones" automáticas. Solo lectura, siempre.
2. **Nunca promete pagos.** No te dice "llegás a pagar"; te dice "con este ritmo, la proyección da X".
3. **Ningún LLM decide sobre plata.** La capa 2 es código determinista con umbrales explícitos; el LLM solo redacta hallazgos ya calculados.
4. **Nunca infiere ingresos** de tus movimientos para proyectar. Lo no declarado no se inventa.
5. **Nunca comparte ni exporta** tus datos financieros fuera de tu workspace. Sin terceros, sin "insights" en la nube.
6. **Nunca te sermonea.** Muestra números y comparaciones; las decisiones de gasto son tuyas.
7. **Nunca se auto-adopta una regla nueva** sin pasar la puerta de dos splits **y** sin tu "sí".
8. **Nunca toca el servicio vivo** (puerto 8471) ni ningún otro frente: esto es un diseño en un archivo, nada más.
9. **Nunca accede a Plaid en esta fase.** El mock primero; los datos reales solo cuando el mock esté en verde y vos lo apruebes.
10. **Si el detector no aporta, se apaga.** Un espejo que miente o que molesta es peor que no tener espejo.

---

## 6. Próximos pasos (cuando vos digas)

1. Construir el generador sintético + la batería de validación (US$0, mock).
2. Correr la batería, iterar reglas hasta el PASS pre-registrado.
3. Recién ahí: propuesta de conexión a datos reales, con tu "sí" explícito.
4. Calibración con tus correcciones de categorías (las primeras 2–4 semanas mandás vos).
5. ALMA como detector de segundo orden, solo después de validado lo anterior.

Nada del paso 3 en adelante ocurre sin que lo pidas.
