# Frente 9/10 — ALMA por voz/llamadas: research de opciones + diseño de integración

**Fecha:** 2026-09-28 · **Costo de este research:** US$0 (solo web pública; ningún signup pago, ningún contacto comercial, nada contratado ni configurado; el servicio vivo no se tocó).
**Estado:** solo research y diseño. Ninguna de las opciones listadas está contratada.

## En criollo

- Una llamada de 3 minutos con ALMA hablando sale **entre US$0,12 y US$0,42** según cómo la armes; lo más barato es armar la cadena por piezas (Twilio + Deepgram + Cartesia ≈ US$0,13), lo más caro son las plataformas todo-en-uno (Bland ≈ US$0,42).
- El cerebro (el loop de ALMA) es **lo más barato de la llamada** (~US$0,003); lo caro es la voz: telefonía + transcribir + sintetizar.
- El riesgo real no es el precio: es la **latencia**. Si ALMA tarda más de ~0,7 segundos en responder, la conversación se siente rota. El probe del loop (que llama al modelo varias veces por turno) puede no entrar en ese presupuesto: hay que medirlo en mock antes de gastar un centavo.
- En español rioplatense hay que validar dos cosas por separado: que el transcriptor entienda el voseo y el yeísmo, y que la voz sintética **suene argentina** (existen voces es-AR reales: hay que probarlas, no asumirlas).
- Recomendación: prototipo US$0 en dos pistas (pipeline de texto con presupuesto de latencia simulado + audio local sin telefonía), y recién después decidir si se contrata número y plataforma.

## 1. Alcance

Este frente evalúa el canal que le falta a ALMA: **llamadas de voz**. Dos casos de uso:

1. **Vendedores que atienden por teléfono** (conexión con el SaaS para vendedores de Mercado Libre): un comprador llama, ALMA responde preguntas de stock/precio/envío.
2. **Vos operando ALMA por voz**: consultas al sistema habladas, sin pasar por texto.

Cubre: proveedores (telefonía, plataformas, STT, TTS), costos por llamada con números, latencia, calidad en español rioplatense y diseño de integración con el loop actual. No cubre: contratación, configuración de cuentas, ni cambios al servicio vivo.

## 2. Opciones de proveedores

### 2.1 Telefonía (el caño: llevar la llamada hasta tu servidor)

| Proveedor | Inbound US local | Outbound US | Número local US/mes | Audio streaming a tu stack |
|---|---|---|---|---|
| **Twilio** | US$0,0085/min | US$0,014/min | US$1,15 | Media Streams US$0,004/min |
| **Telnyx** | ~US$0,007/min | ~US$0,004–0,007/min | ~US$1 | Nativo |
| **Plivo** | similar a Twilio | similar a Twilio | ~US$1–2 | AudioStream **gratis** |
| **Vonage / Sinch / Bandwidth** | enterprise, precio no publicado | — | — | — |

Notas:
- Twilio da **US$15 de crédito de prueba** (no es un plan gratis permanente, pero alcanza para testear).
- Si algún día el volumen justifica, Twilio permite BYOC (traer tu propio carrier): US$0,004/min.
- Para llamadas dentro de Argentina haría falta número local AR: otra lista de precios, queda como caveat (ver §7).

### 2.2 Plataformas todo-en-uno (telefonía + STT + LLM + TTS empaquetados)

| Plataforma | Precio/min | Qué incluye | Español | Crédito gratis |
|---|---|---|---|---|
| **Retell AI** | US$0,07–0,31 (llamada realista mínima ~US$0,087) | Infra + TTS + LLM + telefonía (por líneas) | Sí, modo multilingüe | US$10 |
| **Vapi** | US$0,05 hosting + passthrough (realista US$0,08–0,31) | Orquestación; STT/LLM/TTS/telefonía por separado o con tu key | Sí | Plan Build con minutos incluidos |
| **ElevenLabs Conversational AI** | US$0,08 + LLM + telefonía (+ US$0,003 por mensaje de texto) | Agente + voz ElevenLabs | Sí | Plan gratis con ~15 min |
| **Twilio ConversationRelay** (GA) | US$0,07 + telefonía + tokens | STT/TTS/telefonía de Twilio; **vos ponés el cerebro por WebSocket** | Sí | — |
| **Bland AI** | US$0,14 (Individual); US$0,12 + US$299/mes (Build); US$0,11 + US$499/mes (Scale) | Todo incluido | Requiere acuerdo enterprise | Tier gratis limitado |
| **Telnyx Voice AI Agent** | US$0,05 todo incluido + tokens | Stack sobre su propia red | Sí | — |
| **Plivo Voice AI Agents** | ~US$0,04/min | Integrado a su telefonía | Sí | — |
| **xAI Grok Voice** (speech-to-speech) | US$0,05/min todo incluido | Un solo modelo, sin cadena | — | — |

Dato clave para ALMA: **Vapi, Retell y Twilio ConversationRelay permiten traer tu propio LLM** (el cerebro sigue siendo ALMA). Bland y Synthflow usan LLM gestionado por ellos: no servirían sin entregar el loop.

### 2.3 STT por separado (transcripción en streaming)

| Proveedor / modelo | Precio streaming | Latencia típica | Español |
|---|---|---|---|
| **Deepgram Nova-3** | US$0,0077/min (US$200 de crédito para cuentas nuevas) | ~175 ms p50 | `es` y `es-419` (latinoamérica); code-switching ES/EN |
| **AssemblyAI Universal-Streaming Multilingual** | US$0,15/hora = US$0,0025/min | sub-segundo | ES + 5 idiomas más, con detección |
| **AssemblyAI Universal-3.5 Pro Realtime** | US$0,45/hora = US$0,0075/min | ~150 ms p50 | 18 idiomas, code-switching; mejor WER medido (6,99% en benchmark independiente de Pipecat) |
| **OpenAI Whisper** | US$0,006/min | mayor | 99+ idiomas |
| **Soniox** | US$0,002/min | baja | multilingüe |
| **Cartesia Ink-2** | — | 100 ms (declarado) | — |

### 2.4 TTS por separado (síntesis en streaming)

Precio por 1M de caracteres; el agente habla ~450 caracteres/minuto en una conversación típica.

| Proveedor / modelo | Precio | Costo/min aprox. | Latencia primer audio | Español |
|---|---|---|---|---|
| **Cartesia Sonic-3** | US$50/1M | US$0,0225 | ~40 ms (declarado) | Multilingüe; verificar voz por voz |
| **ElevenLabs Flash v2.5** | US$50/1M | US$0,0225 | ~125 ms p50 | 500+ voces en español (acento mexicano documentado; rioplatense a verificar) |
| **ElevenLabs Multilingual v2** | US$100/1M | US$0,045 | mayor | Mejor calidad, más caro |
| **OpenAI tts-1** | US$15/1M | US$0,0068 | ~250–500 ms | Voces fijas, español correcto pero genérico |
| **Deepgram Aura-2** | US$30/1M | US$0,0135 | baja | — |
| **edge-tts (Microsoft, no oficial)** | **US$0** | US$0 | — | **`es-AR-TomasNeural` y `es-AR-ElenaNeural`: voces argentinas reales** |
| **Piper TTS (open source, MIT, offline)** | **US$0** | US$0 | local | Voz `es_AR-daniela-high` (argentina) |

## 3. Cuánto sale una llamada típica (con números)

### 3.1 Supuestos explícitos

- **Llamada típica de vendedor:** 3 minutos, ~8 intercambios, inbound a número local US.
- El agente habla ~450 caracteres/min → ~1.350 caracteres por llamada.
- El costo del LLM sale de **mediciones propias**: el oráculo EXP67 midió US$0,3609 en 1.080 pulls de deepseek-flash → **~US$0,00033 por turno**; 8 turnos ≈ US$0,003 por llamada. El cerebro es dos órdenes de magnitud más barato que la voz.

### 3.2 Cadena armada por nosotros (DIY, el loop de ALMA como cerebro)

| Capa | Proveedor elegido | US$/min |
|---|---|---|
| Telefonía inbound | Twilio | 0,0085 |
| Audio hacia tu stack | Twilio Media Streams | 0,0040 |
| STT | Deepgram Nova-3 streaming | 0,0077 |
| LLM (loop ALMA) | deepseek-flash, medido EXP67 | ~0,0010 |
| TTS | Cartesia Sonic-3 (US$50/1M) | 0,0225 |
| **Total** | | **~US$0,044/min → US$0,13 por llamada de 3 min** |

Variantes:
- Con ElevenLabs Multilingual v2 (mejor voz): ~US$0,066/min → **US$0,20/llamada**.
- Con AssemblyAI Multilingual (US$0,0025/min) en vez de Deepgram: ~US$0,038/min → **US$0,115/llamada**.
- Número telefónico: +US$1,15/mes (fijo, despreciable por llamada).

### 3.3 Plataformas todo-en-uno (llamada de 3 min)

| Plataforma | US$/llamada (3 min) |
|---|---|
| Telnyx Voice AI Agent (~US$0,055/min) | ~US$0,17 |
| Twilio ConversationRelay (~US$0,085/min) | ~US$0,26 |
| Retell AI (config mínima ~US$0,087/min) | ~US$0,26 |
| Vapi (defaults US$0,08–0,13/min) | ~US$0,25–0,39 |
| ElevenLabs Conversational AI (~US$0,10/min todo) | ~US$0,30 |
| Bland AI Individual (US$0,14/min) | ~US$0,42 |

### 3.4 A volumen (1.000 llamadas/mes × 3 min = 3.000 min)

| Opción | Costo mensual |
|---|---|
| DIY (Twilio + Deepgram + Cartesia) | ~US$132 + US$1,15 del número |
| Retell AI | ~US$261 |
| Bland AI | ~US$420 (más plataforma en planes Build/Scale) |

Lectura honesta: la diferencia DIY vs plataforma es ~2–3× por minuto. A 3.000 min/mes son ~US$130 de diferencia: **no es la plata lo que decide, es el tiempo de ingeniería**. Armar la cadena DIY lleva semanas; la plataforma, días. Como todavía no hay ni un minuto de tráfico real, la decisión de plataforma se posterga hasta que el mock valide que el loop entra en el presupuesto de latencia (§6.3).

### 3.5 Tu caso personal (operar ALMA por voz)

Si sos vos hablando con ALMA, no necesitás número telefónico: alcanza **WebRTC desde el navegador/app**. Twilio Client cobra US$0,004/min por ese tramo, y con LiveKit self-hosted el transporte es US$0. El mock de audio local (§6.3) cubre este caso sin gastar nada.

## 4. Latencia: el presupuesto que manda

El número que decide si la voz funciona: **tiempo desde que terminás de hablar hasta que se escucha la primera sílaba de la respuesta**.

- **< 680 ms:** no se nota (medido en 14.000 llamadas reales, benchmark vox-bench 2026).
- **680–800 ms:** se empieza a sentir raro.
- **> 1,5 s:** aumentan los cuelgues.
- Una cascada típica (STT → LLM → TTS) hoy mide **450–1.500 ms**; bien optimizada con streaming en cada etapa, **~360–580 ms**.
- Twilio ConversationRelay declara mediana < 0,5 s y p95 de 0,725 s.

**El problema específico de ALMA:** el loop con probe hace varias llamadas al modelo por turno para elegir el brazo. En texto eso es gratis en tiempo percibido; en voz, cada llamada extra al modelo suma 200–500 ms al turno. El diseño tiene que contemplar un **modo voz** del loop: skip agresivo (responder con el brazo ganador del régimen, sin probe) en turnos fáciles, probe solo en turnos marcados difíciles, y cache de respuestas frecuentes (en benchmarks reales, ~62% de los turnos de voz no necesitan inferencia del LLM). Esto se valida en mock antes de gastar (M1/M4, §6.3).

## 5. Español rioplatense: STT y TTS

### 5.1 STT: ¿entiende el voseo y el yeísmo?

- Deepgram Nova-3 y AssemblyAI cubren "español" (`es-419` = latinoamérica en Deepgram), con code-switching ES/EN útil para Miami.
- **Ningún benchmark público mide rioplatense específicamente.** El voseo ("tenés", "querés"), el yeísmo ("ll" → /ʃ/, "y" → /ʃ/) y el lunfardo/productos de MeLi son el riesgo concreto: un STT entrenado mayormente con mexicano/neutro puede errar justo donde importa (nombres de productos, direcciones).
- Mitigación: *keyterm prompting* (Deepgram y AssemblyAI lo soportan: lista de ~100 términos del dominio MeLi para forzar el vocabulario) y, sobre todo, **medir WER con grabaciones reales tuyas** antes de comprometer (M3, §6.3). Los US$200 de crédito de Deepgram alcanzan de sobra.

### 5.2 TTS: ¿suena argentino?

- Acá el riesgo es más visible: una voz "español neutro" o mexicana atendiendo a un vendedor argentino **rompe la confianza en 10 segundos**.
- Existen voces argentinas reales: `es-AR-TomasNeural` / `es-AR-ElenaNeural` (Microsoft, gratis vía edge-tts para prototipo) y `es_AR-daniela-high` en Piper (open source, offline, licencia MIT).
- Un experimento documentado en agosto 2026 sobre voces argentinas concluyó que el problema es **regional, no de idioma**: un modelo puede "hablar español" y aun así fallar el acento argentino; hay que elegir la voz por test ciego, no por lista de idiomas soportados.
- ElevenLabs y Cartesia tienen calidad superior, pero el acento rioplatense **hay que verificarlo voz por voz** con hablantes reales antes de pagar.

## 6. Diseño de integración

### 6.1 Flujo propuesto

```
Llamada entrante (PSTN)
  │
  ▼
Carrier (Twilio / Telnyx / Plivo) ── número + transporte de audio
  │  (Twilio: Media Streams por WebSocket; Plivo: AudioStream gratis)
  ▼
voice-gateway (NUEVO, proceso persistente, Pipecat)
  │  endpointing / detección de fin de turno, barge-in (interrupciones),
  │  buffers de audio, cancelación de eco
  ▼
STT streaming (Deepgram Nova-3 `es-419` o AssemblyAI multilingual)
  │  texto del turno + keyterms del dominio (MeLi: "envío", "cuotas", SKUs…)
  ▼
alma-voice-adapter (NUEVO)
  │  traduce turno de voz → turno de texto del loop
  │  MODO VOZ del loop: gate/skip agresivo; probe solo en turnos difíciles;
  │  cache de respuestas frecuentes; presupuesto duro de latencia (680 ms)
  │  y de costo por llamada (freno, apagado por default como en fase 2)
  ▼
Loop ALMA (EXISTENTE, como librería — igual que lo usa el harness de fase 0)
  │  Thompson + probe + skip + memoria con olvido
  │  Router por reward/USD (EXP69): elige proveedor/modelo por turno
  ▼
TTS streaming (Cartesia Sonic-3 / ElevenLabs Flash / voz es-AR validada)
  │
  ▼
Audio de vuelta al carrier → el que llama escucha la respuesta

Transversal: cada turno genera una TRAZA (fase 2.2) con latencia por etapa,
costo medido y veredicto → el meta-loop y el minero de debilidades (EXP66)
las consumen igual que las trazas de texto.
```

### 6.2 Dónde vive cada pieza

| Pieza | Dónde | Estado |
|---|---|---|
| Carrier + número | Twilio/Telnyx/Plivo (tercero) | No contratado (decisión futura) |
| `voice-gateway` (Pipecat, endpointing, barge-in) | Nuevo proceso persistente, separado del servicio | No existe; prototipo en mock |
| `alma-voice-adapter` (turno voz ↔ loop, modo voz, frenos) | Nuevo módulo, importa el loop como librería | No existe; prototipo en mock |
| Loop ALMA (Thompson + probe + skip + memoria + router) | `alma_service/` existente | Existe; **no se toca el servicio vivo del puerto 8471** — se usa como librería |
| Registro de proveedores (`proveedores.yaml`) | Existente | Se extiende con celdas de voz: STT y TTS entran como proveedores con `{calidad_medida, costo}` y el router por reward/USD ya sabe compararlos |
| Trazas unificadas (fase 2.2) | Existente | Las llamadas emiten trazas con el mismo formato |
| Meta-loop / auto-adopción | Existente (gobernanza 27/9) | **La config de voz NO se auto-adopta**: aplica el freno humano (tu "sí"), porque la voz gasta por minuto en producción |

### 6.3 Qué se puede prototipar en mock (US$0)

Todo lo de abajo corre sin contratar nada y sin tocar el servicio vivo:

- **M1 — Pipeline en texto con presupuesto de latencia simulado.** Harness que simula turnos de voz (texto) contra el loop real y mide latencia y costo por turno. Pre-registro mock con vara (ej: p95 de latencia del loop en modo voz < 700 ms en turnos fáciles). Responde: ¿el probe entra en el presupuesto o hay que ir a skip agresivo?
- **M2 — Audio local sin telefonía.** Pipecat + faster-whisper (local, gratis) + edge-tts con `es-AR-TomasNeural` (gratis) + micrófono. Mide latencia real por etapa, prueba endpointing y barge-in. Cubre tu caso personal (operar ALMA por voz) sin número telefónico.
- **M3 — WER en rioplatense real.** Grabás ~50 frases tuyas (voseo, yeísmo, términos de MeLi) → batch contra Deepgram Nova-3 (US$200 de crédito gratis) y AssemblyAI → WER medido sobre tu dialecto real. Es la pregunta abierta que solo datos reales responden; sale US$0 de bolsillo con los créditos.
- **M4 — Test ciego de acento.** Las voces candidatas (es-AR, ElevenLabs, Cartesia) leen el mismo guion de vendedor; hablantes rioplatenses reales eligen sin saber cuál es cuál. Solo la ganadora pasa a cualquier fase con gasto.

## 7. Riesgos

1. **Costo por minuto en producción.** A US$0,04–0,14/min, 10.000 min/mes son US$440–1.400. Mitigación: freno duro de costo por llamada y mensual (igual que el presupuesto de fase 2, apagado por default); el router por reward/USD ya optimiza este eje.
2. **Latencia que rompe la experiencia.** El probe del loop es el principal sospechoso. Mitigación: modo voz con skip agresivo + cache; validación en M1/M4 antes de cualquier gasto.
3. **STT flojo en rioplatense.** Mitigación: keyterm prompting + WER medido en M3; si no da, se cambia de proveedor de STT sin tocar el resto (el diseño por piezas lo permite).
4. **TTS con acento equivocado.** Mitigación: test ciego M4; no asumir "soporta español" = "suena argentino".
5. **Gobernanza.** La voz gasta por minuto en vivo: la auto-adopción del meta-loop no toca config de voz; toda promoción espera tu "sí" (freno humano vigente).
6. **Dependencia de plataforma.** El mercado se está consolidando (compras y cierres en 2026). Mitigación: números y SIP trunk propios como hedge; el adapter habla con el loop en texto, así que cambiar de plataforma de voz no toca a ALMA.
7. **Regulatorio.** Grabar llamadas exige consentimiento (varios estados de USA son *two-party consent*); varios estados exigen declarar que el interlocutor es una IA. Nada de esto se activa en mock, pero bloquea el lanzamiento real hasta resolverse.
8. **Llamadas a Argentina.** Los precios de esta tabla son para numeración US. Un número local AR o llamadas salientes a AR tienen otra lista de precios: cotizar antes de prometerle nada a un vendedor.

## 8. Recomendación

**Por dónde arrancar (todo US$0, sin tu "sí" de gasto porque no hay gasto):**

1. **M1** — harness de texto con presupuesto de latencia simulado (pre-registro mock, vara: p95 < 700 ms en turnos fáciles). Es la pregunta que decide todo: si el probe no entra en el presupuesto de voz, el diseño cambia a skip agresivo antes de mirar proveedores.
2. **M2** — prototipo de audio local (Pipecat + faster-whisper + edge-tts es-AR), sin telefonía. Te da algo para probar con tu voz esta misma semana.
3. **M3** — WER rioplatense con tus grabaciones (créditos gratis de Deepgram/AssemblyAI).
4. **M4** — test ciego de acento con hablantes reales.

**Qué NO hacer todavía:**

- No contratar número ni plataforma (Twilio, Vapi, Retell, Bland) hasta que M1 diga si el loop entra en el presupuesto de latencia.
- No exponer llamadas a vendedores reales sin el test ciego de acento (M4).
- No permitir que el meta-loop auto-adopte configuración de voz (freno humano; la voz gasta por minuto).
- No usar voces "español neutro" para público argentino sin validar.
- No prometer latencia sub-500 ms sin medir con el loop real.

## 9. Decisiones que te quedan a vos (pendientes, no urgentes)

1. **Ámbito:** ¿solo inbound para vendedores de MeLi, solo vos operando ALMA por voz, o ambos? (El caso 2 no necesita telefonía.)
2. **Tope mensual en US$ para voz** — se suma a tus dos pendientes: dónde corre 24/7 y el tope mensual general.
3. **Acento objetivo:** ¿rioplatense cerrado para vendedores AR, o neutro latam si el público se amplía? (Define el M4.)

## 10. Fuentes

Precios y comparativas (consultadas 2026-09-28; los precios cambian, re-chequear antes de contratar):

- Telefonía: https://www.idtexpress.com/blog/twilio-pricing-explained-how-to-reduce-voice-costs/ · https://quiq.com/blog/twilio-voice-pricing/ · https://max-productive.ai/blog/twilio-alternatives/
- Plataformas: https://www.getmacha.com/blog/vapi-ai-pricing-explained · https://www.getmacha.com/blog/retell-ai-complete-guide · https://www.cloudzero.com/blog/elevenlabs-pricing/ · https://www.layer3labs.io/guides/openai-realtime-api-pricing · https://www.firecrawl.dev/blog/ai-voice-agent-platforms · https://www.plivo.com/blog/ccaas-platforms-built-in-ai-voice-agents-compared/
- STT: https://tech-insider.org/speech-to-text-api-comparison-2026/ · https://devtoollab.com/blog/best-speech-to-text-apis · https://www.assemblyai.com/products/streaming-speech-to-text · https://www.assemblyai.com/blog/multilingual-speech-to-text-api
- TTS: https://github.com/mahimailabs/voice-prices/blob/HEAD/docs/tts/cartesia.mdx · https://www.marktechpost.com/2026/08/18/cartesia-ships-sonic-3-6-a-streaming-tts-model-that-now-leads-both-artificial-analysis-speech-arenas/ · https://github.com/patterai/patter/blob/HEAD/docs/python-sdk/metrics.mdx
- Latencia: https://www.evalgent.com/blog/voice-agent-stack-guide · https://dev.to/autor_tech/4-months-of-vox-bench-in-production-what-14000-benchmark-runs-taught-us-about-voice-ai-latency-2n9k · https://www.webpronews.com/the-hidden-layer-that-makes-voice-ai-sound-human/
- Arquitectura open source: https://tenx.studio/blog/voice-ai-frameworks · https://github.com/aws-samples/sample-voice-agent-on-aws/blob/HEAD/README.md · https://github.com/shauryalowkeygotaura/voicezero (patrón US$0: faster-whisper + edge-tts) · https://github.com/outsourcetel/dreamteam-ai/blob/HEAD/docs/42-voice-channel-build-vs-partner.md
- Español rioplatense: https://github.com/nicochunger/neuralcast/blob/HEAD/docs/tts_model_experiment_2026-08-29.md (experimento de acento argentino, ago-2026) · https://github.com/nicolasramos/odooclaw/blob/HEAD/odooclaw/workspace/skills/edge-tts/SKILL.md (voces es-AR)

---
*Frente 9/10. Research US$0, sin signups pagos ni contactos comerciales. Servicio vivo intacto.*
