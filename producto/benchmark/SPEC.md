# SPEC — Benchmark de modelos por tarea

**Estado:** borrador de producto (frente 3/10)
**Fecha:** 2026-09-28
**Registro:** español, voseo
**Costo de elaboración:** US$0 (doc; cero llamadas a API, cero contacto con terceros)

---

## 1. Qué es

**En criollo:** cuando tenés que elegir un modelo de IA para una tarea concreta —responder preguntas de clientes, resumir documentos, generar código—, los rankings públicos te dicen cuál es "el mejor" en general. Este producto te dice cuál es **el más barato que funciona para TU tarea**, con números medidos, no con promesas del proveedor.

**Técnico:** un servicio de medición independiente que evalúa modelos comerciales (por proveedor y por configuración de esfuerzo/brazo) sobre tareas reales del cliente, y produce una tabla de decisión: **reward por dólar gastado** por tarea, por modelo y por brazo. La unidad de medición es la *celda* (tarea × modelo × brazo) con n suficiente para intervalos de confianza.

---

## 2. Qué mide

### 2.1 La métrica

```
reward = 0.75 · éxito + 0.25 · (1 − costo_rel / 5)
```

- **éxito:** 1 si la respuesta es correcta según un evaluador determinista (tests, respuesta exacta, juicio verificado); 0 si no.
- **costo_rel:** costo de la llamada relativizado a una baseline del benchmark.
- **costo medio por llamada:** medido en USD reales, con precios verificados contra la documentación oficial del proveedor el día de la medición.
- **reward/USD:** la métrica de decisión. Maximizarla es el criterio que usa el router de ALMA.

Medimos las tres porque cada una miente por separado: el éxito crudo ignora el precio, el costo ignora la calidad, y el reward/USD te dice qué comprar.

### 2.2 La unidad de medición: la celda

Cada combinación (tipo de tarea × modelo × brazo) se mide con:

- **n llamadas reales** a la API del proveedor (mínimo pre-registrado por celda; pilotos con n=20, oráculos con n=120).
- **RNG pareado por posición:** todos los modelos responden los mismos problemas en el mismo orden — la comparación es manzana con manzana.
- **Evaluador idéntico** para todas las celdas.
- **Freno duro de gasto** por campaña: si el costo proyectado supera el freno, la corrida se detiene y se declara medición parcial (ver EXP70: el freno cortó en 63/72 pulls y quedó registrado como parcial, no como completo).

### 2.3 La metodología ya existe (prueba)

No es un diseño en papel. La metodología corrió tres veces con dinero real y veredictos pre-registrados:

| Campaña | Proveedor / modelo | Pulls | Costo medido | Qué probó |
|---|---|---|---|---|
| EXP67 oráculo | DeepSeek / deepseek-flash | 1080 (180 problemas frescos: matemática, conocimiento, código) | US$0,3609 | La metodología a escala: oráculo completo + fase de políticas (918 llamadas más, US$0,2667) |
| EXP69 piloto | OpenAI / gpt-4o-mini | 180 (30 problemas) | US$0,0276 | El criterio de decisión: el router por reward/USD eligió al ganador ex post en 3/3 slices |
| EXP70 piloto | Anthropic / claude-haiku-4-5 | 63 (parcial, freno US$0,10) | US$0,1028 | Precios verificados en vivo ($1/$5 por MTok); hallazgo de verbosidad: Claude cuesta ~10,7× gpt-4o-mini por llamada, no ~7× como sugería el ratio de precios |

**Hallazgos que el producto vende** (todos medidos, no opinados):

1. **El brazo más barato le gana al más inteligente en eficiencia.** En EXP69, deepseek/single dominó los 3 slices por reward/USD (gsm8k: 47.782; mmlu: 36.630; mbpp: 2.821 R/USD) aunque en reward crudo gsm8k lo ganaba cot (0,967 vs 0,633). El thinking cuesta 10–40× más por una ganancia marginal.
2. **La regla generaliza.** La elección del router, entrenada en el piloto de 30 problemas, coincidió 3/3 con el ganador ex post en el oráculo de 180 problemas frescos que el router nunca vio.
3. **La verbosidad es un costo oculto.** Los precios de lista no bastan: hay que medir tokens reales de salida por tarea. Claude genera 2–4× más tokens de salida que gpt-4o-mini en los mismos brazos.
4. **Hay tareas donde ningún modelo rinde.** mbpp (código con tests): reward ≈ 0 en los 3 proveedores medidos. Un benchmark honesto también dice "no compres nada para esto todavía".

Los datos crudos viven en `integracion_fase21/resultados/exp67-benchmark-real-20260927/`, `exp69-router-proveedores-20260927/` y `exp70-claude-pilot-20260928/`; el registry con metadata medida en `integracion_fase21/alma_service/proveedores.yaml`.

---

## 3. Para quién

1. **Equipos de ML / ingeniería que eligen modelos.** Necesitan responder "¿qué modelo uso para este endpoint?" con números auditables, no con el leaderboard de moda. El reporte les da la tabla por tarea y el punto de corte donde pagar más deja de rendir.
2. **Compradores de IA (procurement, CTOs).** Negocian contratos por volumen con proveedores. Un benchmark independiente por tarea les da palanca: "para el 80% de nuestro tráfico, el modelo barato rinde igual".
3. **FinOps / finanzas de empresas con gasto alto en APIs.** Ven la factura agregada pero no saben qué parte es desperdicio. El benchmark les muestra el costo por tarea y cuánto se ahorraría cambiando de modelo o de brazo.

**No es para:** investigadores académicos (ya tienen MMLU), ni hobbyists (el costo de medición no se justifica para volúmenes chicos).

---

## 4. Diferenciación vs benchmarks públicos

| | MMLU / HumanEval / leaderboards | Este producto |
|---|---|---|
| Qué mide | Puntaje genérico (accuracy) | **Costo-beneficio en tu tarea** (reward/USD) |
| Tareas | Fijas, públicas, saturables | Las del cliente (privadas, con sus datos) |
| Costo | Ignorado | Medido en USD reales, con precios verificados |
| Configuración | Un prompt, un setting | Por brazo: single / cot / reflexion (el esfuerzo también se optimiza) |
| Resultado | Ranking | **Tabla de decisión**: qué comprar, para qué tarea, con qué ahorro |
| Contaminación | Los modelos entrenan sobre los tests públicos | Problemas frescos del cliente; el oráculo se mide sobre datos que el modelo no vio |

**En criollo:** MMLU te dice quién saca mejor nota en el examen. Nosotros te decimos cuánto te sale cada punto de nota en tu trabajo real — y casi siempre el que saca 10 sale 40 veces más caro que el que saca 9.

**Ventaja defensible:** el loop completo ya existe y está medido — oráculo con freno de gasto + evaluador determinista + RNG pareado + registry con metadata y failover. No es una planilla; es maquinaria que ya corrió con plata real.

---

## 5. Formato de entrega

### 5.1 Reporte (entrega base)

- **Tabla por tarea:** modelo × brazo con reward medio, costo medio/llamada, reward/USD e IC95.
- **Recomendación:** el ganador por tarea y el ahorro proyectado vs la configuración actual del cliente (en USD/mes, con su volumen).
- **Caveats:** n por celda, fecha de medición, precios verificados ese día, tareas donde ningún modelo rinde.
- **Trazabilidad:** pre-registro de la campaña, pulls crudos disponibles para auditoría, freno de gasto aplicado.

### 5.2 API (para equipos que integran la decisión)

- `GET /benchmark/tareas/{id}/recomendacion` → ganador actual por tarea con reward/USD y fecha de medición.
- `GET /benchmark/matriz` → la tabla completa en JSON.
- Webhook o polling cuando un refresh cambia una recomendación (el modelo ganador de una tarea cambió).

### 5.3 Refresh periódico

Los precios y los modelos cambian; un benchmark de hace 6 meses miente. Planes:

- **Refresh trimestral** incluido en suscripción: se re-miden las celdas con los precios vigentes y se actualiza la tabla.
- **Refresh por evento:** si un proveedor cambia precios >10% o lanza un modelo nuevo en una categoría cubierta, se re-mide esa categoría y se avisa.
- Cada refresh conserva el historial: el cliente ve la evolución del reward/USD por tarea en el tiempo (esto, con el tiempo, vale más que la foto instantánea).

---

## 6. Pricing (opciones)

Tres modelos, a elegir según el segmento. Números a validar con los primeros clientes; la lógica es: **el benchmark se paga solo si el ahorro que encuentra supera su costo**.

**Opción A — Por campaña (reporte único).**
Precio fijo por categoría de tarea medida (ej: 3 categorías × 3 modelos × 3 brazos). El cliente paga la medición; se lleva el reporte y los datos crudos. Sin suscripción. Ideal para la primera venta: riesgo bajo para el cliente, prueba de valor inmediata.

**Opción B — Suscripción con refresh (recomendada).**
Mensualidad por N tareas cubiertas: incluye el benchmark inicial + refresh trimestral + API de recomendaciones + alertas por evento. Es el modelo que construye el activo real: el historial de reward/USD por tarea.

**Opción C — Benchmark privado + revenue share del ahorro.**
Para clientes con volumen alto: medición sobre sus tareas con sus datos (NDA), y el precio atado a una fracción del ahorro medido en los primeros 3 meses vs su configuración anterior. Más fricción comercial, pero alinea incentivos: si no encontramos ahorro, cobramos poco.

**Regla de honestidad comercial:** si la medición muestra que la configuración actual del cliente ya es la óptima, se le dice y se le cobra igual — el valor es la certeza, no el cambio. Esto se declara por escrito antes de medir.

---

## 7. MVP

**Alcance mínimo que demuestra el valor con un cliente real:**

1. **3 categorías de tarea** del cliente (elegidas con él; si no tiene tareas claras, se usan las 3 del oráculo: matemática/razonamiento, conocimiento/preguntas, código).
2. **3 proveedores × 3 brazos** por categoría (los ya medidos: DeepSeek, OpenAI, Anthropic; brazos single/cot/reflexion o equivalentes por proveedor).
3. **Metodología EXP67/EXP69 tal cual:** pre-registro, RNG pareado, evaluador determinista, freno de gasto por campaña, precios verificados el día de la medición.
4. **Entrega:** reporte con tabla por tarea, recomendación y ahorro proyectado en USD/mes con el volumen del cliente. Sin API todavía; el reporte es el producto.
5. **Costo de la campaña MVP:** del orden de US$0,50–1,50 en llamadas a API (medido: oráculo completo de 1080 pulls costó US$0,36 en DeepSeek; el piloto de Anthropic, US$0,10). El costo de medición es un orden de magnitud menor que cualquier ahorro que valga la pena perseguir.

**Criterio de éxito del MVP:** el cliente cambia al menos una decisión de modelo/proveedor basándose en el reporte, o renueva para el refresh. Si el reporte no mueve ninguna decisión, el producto no tiene mercado — mejor saberlo con un cliente que con diez.

**Lo que el MVP no incluye:** API, refresh automático, benchmarks privados con datos del cliente bajo NDA (eso es opción C, fase posterior), más de 3 proveedores.

---

## 8. Roadmap

- **Fase 1 (MVP):** reporte por campaña, 3×3×3, metodología de los oráculos. Un cliente piloto.
- **Fase 2:** API de recomendaciones + registry de proveedores como servicio (el `proveedores.yaml`/`registro.py` d
...[truncated 2546 chars]