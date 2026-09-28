# SPEC — Respondedor de Mercado Libre

**Fecha:** 28/9/2026 · **Estado:** diseño de producto (Fase 1/10)
**Costo de producción:** US$0 (documento de diseño, sin llamadas a API)
**Dependencia externa:** el MVP real espera una cuenta vendedora activa en MeLi y el conector OAuth completado — el spec no.

---

## 1. Qué hace

El respondedor es un asistente que **responde las preguntas de los compradores en tus publicaciones de Mercado Libre**, 24/7, en tu tono y con tu información.

Flujo:

1. Un comprador deja una pregunta en una publicación.
2. El sistema toma el contexto de esa publicación (título, precio, stock, descripción, respuestas anteriores).
3. La IA redacta una respuesta corta (1–3 oraciones), cordial y orientada a cerrar la venta.
4. **Vos la aprobás, editás o descartás** desde el panel. Solo se publica lo que aprobaste.

No es un chatbot de WhatsApp ni un CRM: es la capa de atención en la propia plataforma, donde se juega la venta.

## 2. Para quién

Foco inicial: **vendedores argentinos** (site MLA).

Tres segmentos, en orden de ataque:

| Segmento | Perfil | Dolor |
|---|---|---|
| **A. Unipersonal activo** | 10–200 publicaciones, él mismo responde desde el celular | Pierde ventas de noche, fin de semana o cuando está en el local; responder lo mismo 40 veces al día lo quema |
| **B. Tienda chica con equipo** | 200–2.000 publicaciones, 1–3 personas en atención | Tiempos de respuesta dispares, tono inconsistente entre empleados, rotación de personal |
| **C. Catálogo grande** | Multi-cuenta, volumen alto de preguntas | Costo de atención escala linealmente con las preguntas |

El orden de ataque es A → B → C: el segmento A decide solo, paga de su bolsillo y se gana con precio bajo y simplicidad. El C ya lo tiene GoBots.

## 3. Propuesta de valor vs. la competencia

| | GoBots | JaimeBot (Ventiapp) | KanamAI | Nosotros |
|---|---|---|---|---|
| Trayectoria | 7 años, +1.000 tiendas, Platinum Partner MeLi | Establecido en México | Proyecto argentino en etapa temprana (landing + demo) | En diseño |
| Precio de entrada | Desde US$150/mes (escalonado por facturación) | Tokens: 1 token = 1 respuesta | Por definir | **Muy por debajo de US$150** (ver §4) |
| Modo de respuesta | Automático directo | Automático directo | Sugerencia (etapa 5, pendiente) | **Sugerencia primero**: nada se publica sin tu "sí" |
| Costo marginal | Incluido en el plan | Cobrado por respuesta | — | **Medido y transparente** (ver §4) |
| Motor | IA propia | IA propia | Gemini 2.5 Flash Lite | **Router por reward/USD** (EXP69): elige el proveedor/modelo más barato que resuelve cada pregunta |
| Aprendizaje | Reglas/IA genérica | Reglas/IA genérica | Prometido | **Loop ALMA**: memoriza qué respuestas aprobás, con olvido temporal; mejora con el uso |

**Diferencias que importan:**

1. **Modo sugerencia.** Las respuestas en MeLi son públicas y es tu reputación la que está en juego. GoBots y JaimeBot publican directo; nosotros proponemos, vos publicás. Es más lento en el minuto 1 y más seguro en el año 1. Cuando la tasa de aprobación pase el umbral (§5), el automático se vuelve opcional por publicación.
2. **Costo marginal casi cero.** EXP69 midió que el router elige el ganador ex post por reward/USD en 3/3 slices: el modelo barato le gana al caro. Con el router, el costo de una respuesta ronda los **décimos de centavo** (el oráculo de EXP67 midió ~US$0,0003 por llamada de DeepSeek), no los centavos que justifican los US$150 de GoBots. Eso permite precio de entrada bajo con margen sano.
3. **Ataque por abajo.** GoBots cobra por facturación: el vendedor chico paga por ser grande. Nosotros cobramos por uso real. El que tiene 50 preguntas al mes no debería pagar US$150.
4. **Foco argentino primero.** Voseo, tono, moneda, y en el roadmap contabilidad con AFIP (lo que KanamAI promete en etapa 7 y nadie tiene hoy).
5. **Honestidad medible.** El panel muestra costo por respuesta, tiempo de respuesta y tasa de aprobación con números, no promesas. La disciplina del laboratorio se traslada al producto.

## 4. Pricing

Tres opciones. Los números son de referencia para la discusión, no precios finales: se validan con el piloto.

**Opción A — Suscripción plana (estilo GoBots, pero barata)**

| Plan | Respuestas/mes | Precio ref. |
|---|---|---|
| Starter | hasta 300 | US$19–29 |
| Pro | hasta 1.500 | US$49–69 |
| Tienda | ilimitado razonable (fair use) | US$99–149 |

Ventaja: predecible para el vendedor. Riesgo: el heavy user subsidia al light.

**Opción B — Por respuesta (estilo JaimeBot, pero barato)**

- US$0,10 por respuesta publicada; packs (500 respuestas = US$45; 2.000 = US$160).
- Costo marginal propio medido: centésimas de centavo a ~US$0,01 por respuesta según el modelo que elija el router → margen bruto >90%.

Ventaja: el que vende poco paga poco. Riesgo: ingresos impredecibles; el vendedor teme el "contador corriendo".

**Opción C — Híbrido (recomendado)**

- Base US$15/mes (incluye 200 respuestas) + US$0,05 por respuesta extra, o packs recargables.
- Combina ingreso recurrente con precio alineado al uso.

**Recomendación:** lanzar con el híbrido. El segmento A necesita ver que "vende poco = paga poco", y el negocio necesita ingreso recurrente para cubrir infra fija (servidor, OAuth, soporte).

## 5. MVP

**Decisión fundacional: modo sugerencia primero.** Ninguna respuesta se publica sin aprobación explícita del vendedor. Es la diferencia entre un asistente y un riesgo reputacional.

### Alcance del MVP

- **OAuth MeLi:** integración oficial, scopes de lectura de preguntas/publicaciones y publicación de respuestas. Multi-cuenta desde el día 1 (muchos vendedores tienen más de una).
- **Cola de preguntas:** las preguntas pendientes aparecen en un panel, cada una con su borrador de respuesta.
- **Borrador automático:** redactado con contexto de la publicación (título, precio, stock verificado antes de prometer nada). Reglas duras:
  - Nunca teléfonos, mails, redes ni links externos (MeLi suspende publicaciones por eso).
  - Solo se afirma lo que los datos confirman; si no hay dato, la respuesta lo dice y ofrece alternativa.
  - 1–3 oraciones; tono cordial, cierre que invite a comprar.
- **Aprobar / editar / descartar:** un gesto por respuesta. Lo editado también entrena al sistema.
- **Notificaciones:** el vendedor se entera al instante (push) de que hay una sugerencia lista, para que el "modo sugerencia" no degrade el tiempo de respuesta.

### Métricas del MVP

| Métrica | Definición | Objetivo MVP |
|---|---|---|
| Tiempo de respuesta | pregunta → sugerencia lista | < 60 s (p50) |
| Tiempo de aprobación | sugerencia → publicada | medido, sin objetivo aún (depende del vendedor) |
| Costo por respuesta | costo de modelo medido por el registry de proveedores | < US$0,01 |
| Tasa de aprobación | sugerencias aprobadas (sin edición o con edición leve) / total | ≥ 80% en el piloto |
| Tasa de descarte | sugerencias descartadas / total | ≤ 10% (las descartadas se analizan: ¿error de datos o de tono?) |

### Puertas de calidad

- Piloto cerrado de 5–10 vendedores reales (segmento A) antes de cualquier cobro.
- Sin modo automático en el MVP. El automático se habilita por publicación solo cuando su tasa de aprobación supera el 95% en 100+ sugerencias, y siempre reversible.
- Presupuesto de gasto en modelos con tope duro, apagado por default (misma doctrina de la fase 2 de ALMA).

## 6. Roadmap

| Fase | Contenido | Puerta |
|---|---|---|
| **F0** | Conector OAuth MeLi + demo en seco (respuestas simuladas sobre publicaciones reales, sin publicar) | Demo funcional ante 3 vendedores |
| **F1** | MVP en modo sugerencia + piloto 5–10 vendedores + métricas | Tasa de aprobación ≥80%, costo/respuesta <US$0,01 |
| **F2** | Modo automático opcional por publicación (umbral 95%/100) + notificaciones push | Cero publicaciones automáticas con quejas en 30 días |
| **F3** | Postventa: mensaje preventivo, contexto de orden, detección de temas sensibles → deriva a humano | Piloto F3 sin aumento de reclamos |
| **F4** | Loop ALMA completo: memoria por vendedor con olvido, minería de debilidades sobre las sugerencias descartadas, validador de dos splits antes de adoptar cambios de prompt | Mejora medida en tasa de aprobación, sin regresión |
| **F5** | Expansión: Mercado Shops, otros países (MX, BR), contabilidad AFIP | A definir con tracción |

## 7. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| **Reputación del vendedor:** una mala respuesta es pública e irreversible | Modo sugerencia como default permanente; el automático solo con umbral medido y reversible; reglas duras de redacción |
| **Políticas de MeLi:** suspensión por datos de contacto o spam | Las reglas de redacción prohíben contactos/links por construcción; test automatizado que lo verifica; integración solo por API oficial |
| **Dependencia de MeLi:** cambios en la API o en las reglas de apps | Seguir la vía oficial OAuth (la que ya está en curso); mantener la capa de integración aislada para adaptarse rápido |
| **Seguridad de tokens OAuth:** son credenciales de terceros | Vault, sin secretos en código ni logs; test que verifica cero secretos por construcción (doctrina de la fase 2.x) |
| **Preguntas ambiguas o reclamos encubiertos** | El borrador no improvisa: si es reclamo, sugiere revisar la orden y deriva al humano; las descartadas alimentan el minero de debilidades (F4) |
| **Competencia reacciona:** GoBots baja el precio de entrada; KanamAI sale gratis | El foso no es el precio sino el loop que aprende del vendedor (F4) + el costo marginal más bajo por el router; el precio se defiende con números, no con promesas |
| **Costo de modelos sube** | El router existe para eso: reelige el proveedor más barato que resuelve; registry con failover y precios medidos, no estimados |
| **El vendedor no aprueba a tiempo y el TMR no mejora** | Push instantáneo + sugerencias en lote; si el segmento A no aprueba, el producto no sirve y el piloto lo va a mostrar antes de cobrar |

---

**Nota de gobierno:** el laboratorio ALMA y este producto comparten la misma doctrina — vara pre-registrada, costo medido antes de gastar, nada automático sin umbral. El respondedor es el cliente #1 del router, no un experimento más.
