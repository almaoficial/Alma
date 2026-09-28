# Auditoría de costo de IA — oferta del servicio

*Documento de oferta. Versión 1.0 — 28/9/2026. Precios indicativos, a confirmar antes de cotizar.*

## El servicio, en una oración

Medimos cuánto te cuesta cada tarea que resuelve tu IA, qué tan bien la resuelve cada modelo disponible, y te decimos —con números, no con opiniones— dónde estás pagando de más.

## Para quién es

Para productos que **facturan plano y absorben el costo de la IA por uso**: respondedores automáticos, asistentes de venta, bots de atención, cualquier servicio donde cada llamada al modelo sale de tu margen.

Si tu precio no se mueve cuando tu costo de tokens sube, este servicio es para vos.

## Qué se audita

Cinco bloques, todos medidos sobre **tus trazas reales** (datos agregados y anonimizados; nunca pedimos tus keys ni tocamos tu producción):

1. **Stack de IA actual.** Qué proveedores y modelos usás, con qué prompts y qué nivel de "esfuerzo" (respuesta directa, razonamiento paso a paso, reflexión). Lo mapeamos completo: ningún costo se esconde en un default.
2. **Costo por tarea, no por token.** El precio por token no te dice nada. Lo que importa es cuánto cuesta una respuesta resuelta: tokens de entrada + salida × precio, por tipo de consulta. Una pregunta de "¿tenés stock?" no cuesta lo mismo que una disputa de garantía, y hoy probablemente las pagás igual.
3. **Calidad por modelo y por tarea.** Re-ejecutamos tus tipos de consulta reales contra varios proveedores y medimos dos cosas por separado: *reward* (¿resolvió bien la tarea?) y *costo por llamada*. Sin esta separación, cualquier comparación de precios es humo.
4. **Routing actual.** Si usás un solo modelo para todo, medimos cuánto perdés. Si ya ruteás por reglas, medimos si las reglas aciertan. La pregunta es siempre la misma: ¿la consulta difícil va al modelo caro y la fácil al barato, o van todas al mismo?
5. **Fugas.** Reintentos que no agregan calidad, prompts inflados que se repiten en cada llamada, consultas que un cache o una respuesta templada resolverían sin llamar al modelo. Son los ahorros más baratos: no requieren cambiar de proveedor.

## Metodología: medición, no opinión

1. **Instrumentación.** Nos pasás una muestra de trazas reales (anonimizadas): tipo de consulta, tokens in/out por llamada, latencia, y el resultado que te importa (¿se resolvió? ¿escaló a humano? ¿el cliente repreguntó?). Firmamos acuerdo de confidencialidad si lo necesitás.
2. **Vara pre-registrada.** Antes de medir, escribimos qué cuenta como "resuelto" para cada tipo de consulta y qué umbral de ahorro justifica un cambio. Los criterios no se mueven después de ver los números.
3. **Oráculo de proveedores.** Replicamos tus tipos de consulta en varios proveedores/modelos con distintos niveles de esfuerzo y medimos reward y costo por llamada de cada combinación. Esto ya lo hacemos con protocolo propio: en nuestras últimas mediciones (1.323 llamadas reales, tres proveedores), el patrón se repite — el modo "razonamiento" cuesta entre 10× y 40× más por llamada que la respuesta directa, con ganancia marginal de calidad en las tareas que el modelo ya resuelve.
4. **Router ex post.** Con los números medidos, simulamos qué habría elegido un router que maximiza *calidad por dólar* en lugar de minimizar el precio del token. En nuestra validación, ese criterio eligió al ganador real en 3 de 3 categorías de tarea.
5. **Estimación de ahorro.** Traducimos los resultados a tu volumen: si el X% de tus consultas se mueve al modelo más barato sin pérdida de calidad medida, el ahorro mensual es tal, con intervalo de confianza. Sin redondeos optimistas.

## Entregable

Un informe con:

- **Tabla de costo por tarea por modelo**, con reward medido e intervalos de confianza. Los números crudos, no un resumen.
- **Mapa de routing recomendado**: qué tipo de consulta va a qué modelo, con el ahorro esperado de cada movimiento.
- **Recomendaciones priorizadas por ROI**: quick wins (cache, prompts, reintentos) primero; cambios de proveedor o de arquitectura después.
- **Plan de implementación** en fases, con qué medir en cada fase para verificar que el ahorro se materializa.

Todo el informe se entrega con los datos y el criterio pre-registrado adjuntos, para que puedas auditar la auditoría.

## Lo que no hacemos (límites honestos)

- No vendemos software ni licencias. La auditoría termina en el informe y el plan; la implementación la hacés vos o la cotizamos aparte.
- No tocamos tu producción durante la auditoría. Cero riesgo operativo.
- No te pedimos keys de tus proveedores. Trabajamos con trazas anonimizadas y nuestras propias cuentas de medición.
- No prometemos un porcentaje de ahorro antes de medir. Si tus números ya están bien ruteados, el informe lo dice y te ahorrás el cambio.

## Pricing

| Opción | Alcance | Tiempo | Precio indicativo |
|---|---|---|---|
| **Diagnóstico inicial** | Muestra chica de trazas (hasta 2 tipos de consulta). Estimación de orden de magnitud del ahorro posible. | 1 semana | **Gratis** — a cambio, tus datos agregados y anónimos calibran nuestro registry de proveedores (te lo decimos de frente, sin letra chica) |
| **Auditoría Express** | Hasta 3 tipos de consulta. Oráculo en 2–3 proveedores. Informe + quick wins. | 2 semanas | US$ 750 |
| **Auditoría Completa** | Workload completo. Oráculo en 3+ proveedores, router ex post, fugas, informe + plan de implementación por fases. | 3–4 semanas | US$ 2.500 |
| **Completa + Piloto de router** | Todo lo anterior, más un piloto del router en vivo sobre una fracción de tu tráfico, con guardrails y rollback. Solo se factura el piloto si la auditoría encontró ahorro medido ≥ 15%. | 6–8 semanas | US$ 5.000 |

Precios en dólares, indicativos. La cotización final se fija después del diagnóstico inicial, cuando ya conocemos el volumen y la complejidad de tu workload.

## Por qué nosotros

No somos consultores que leyeron los precios de las APIs. Medimos: nuestro registry de proveedores se alimenta de oráculos reales que corremos nosotros (DeepSeek, OpenAI y Claude medidos llamada por llamada, con reward y costo por tarea). La auditoría que te vendemos es el mismo protocolo que usamos para decidir dónde corre nuestra propia IA.

---

*Contacto y siguientes pasos: se definen en la propuesta específica de cada cliente. Este documento describe el servicio; no es una cotización.*
