# ⛔ DRAFT — NO ENVIAR — Propuesta para GoBots

*Estado: borrador interno. No contactar a GoBots ni a terceros bajo ningún concepto. Este documento existe solo para draftear la propuesta.*

---

## La propuesta

**Para:** GoBots (gobots.ai) — IA conversacional para vendedores de Mercado Libre: responde preguntas de preventa y posventa, integrada por API oficial, ~60 segundos por respuesta, 24/7.

**De:** [nombre/remitente a definir] — auditoría de costo de IA.

### El pitch

Ustedes cobran suscripción plana y absorben el costo de la IA. Cada respuesta que genera su bot sale de su margen: la pregunta simple de "¿tenés stock?" y la disputa compleja de garantía hoy probablemente pasan por el mismo modelo y cuestan lo mismo.

Nuestra tesis es directa: **no todas las consultas valen el mismo modelo**. Si medimos qué tipo de consulta resuelve igual de bien cada modelo, podemos rutear cada pregunta al modelo más barato que la resuelve bien — y la diferencia va directo a su margen, sin tocar la experiencia del vendedor ni del comprador.

Esto no es teoría: es lo que medimos todas las semanas en nuestro laboratorio. Algunos números reales, medidos por nosotros llamada por llamada:

| Proveedor / modelo | Tarea simple, respuesta directa | Tarea con razonamiento |
|---|---|---|
| DeepSeek | reward 0,63 — **US$ 0,0000142** por llamada | reward 0,97 — US$ 0,0002122 por llamada |
| OpenAI (gpt-4o-mini) | reward 0,30 — US$ 0,0000177 por llamada | reward 1,00 — US$ 0,0001827 por llamada |
| Claude (haiku) | reward 0,38 — US$ 0,000178 por llamada | reward 1,00 — US$ 0,001475 por llamada |

*(Oráculos reales: 1.323 llamadas, sep-2026. El "reward" es la fracción de tareas resueltas correctamente por el verificador.)*

Dos lecturas que importan para ustedes:

1. **El modo "razonamiento" cuesta 10× a 40× más por llamada que la respuesta directa**, con ganancia marginal en las tareas que el modelo ya resuelve. Si una fracción de sus consultas no necesita razonamiento, ahí hay margen puro.
2. El modelo más barato por token no siempre es el más barato por respuesta resuelta — y viceversa. En nuestras mediciones, el router que maximiza *calidad por dólar* eligió al ganador real en 3 de 3 categorías. La única forma de saberlo para *su* workload es medirlo sobre *sus* consultas.

### Qué les medimos gratis

El **diagnóstico inicial** (ver `OFERTA.md`): con una muestra de sus trazas anonimizadas —tipo de consulta, tokens por llamada, si se resolvió o escaló— estimamos el orden de magnitud del ahorro posible en una semana, sin costo.

A cambio les pedimos una sola cosa, dicha de frente: los datos agregados y anónimos calibran nuestro registry de proveedores. Nada identificable, nada de sus clientes, y con acuerdo de confidencialidad si lo necesitan.

No les pedimos sus keys, no tocamos su producción, no hay integración en esta fase.

### Qué reciben

- Costo real por tipo de consulta hoy (probablemente la primera vez que lo ven desagregado).
- Estimación del ahorro mensual si cada tipo de consulta fuera al modelo más barato que la resuelve igual de bien — con intervalo de confianza, sin redondeos optimistas.
- Los criterios de medición por escrito *antes* de medir, para que puedan auditar la auditoría.

### Qué sigue (si los números cierran)

La **Auditoría Completa** (US$ 2.500, 3–4 semanas): oráculo completo sobre sus tipos de consulta en 3+ proveedores, mapa de routing recomendado y plan de implementación por fases. Y si quieren, un **piloto del router en vivo** sobre una fracción del tráfico, con guardrails y rollback — solo se factura si la auditoría encontró ahorro medido ≥ 15%.

### Call to action

Una llamada de 20 minutos para definir qué muestra de trazas nos pasan y firmar la confidencialidad. Sin compromiso: si el diagnóstico dice que ya están bien ruteados, se los decimos y no hay segunda llamada.

---

## Notas internas (no forman parte de la propuesta)

- **No prometer** un % de ahorro antes de medir. La vara pre-registrada es sagrada también acá.
- **No prometer** integración ni tiempos de implementación en esta fase.
- El gancho "gratis" es honesto solo si se explicita el intercambio de datos agregados — ya está explicitado arriba, mantenerlo.
- Antes de cualquier envío real: definir remitente, canal y quién firma. Este draft no tiene ninguno de los tres a propósito.
- Verificar el contacto correcto de GoBots (partnerships/comercial) solo cuando se apruebe el envío. Hoy: PROHIBIDO contactar.
