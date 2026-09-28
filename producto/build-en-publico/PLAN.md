# Plan de contenido: construyendo ALMA en vivo

> **ESTADO: PLAN — NO PUBLICAR.** Este documento planifica la comunicación pública. Nada de lo que hay acá fue publicado ni se publica sin tu sí explícito, pieza por pieza.

---

## 1. Tesis

Documentás la construcción de ALMA como vía de distribución: audiencia antes que clientes. El build en público no es vanidad — es el canal por el que llegan los primeros usuarios del router y los primeros lectores del paper. Cada pieza cuenta trabajo real con números reales, incluidos los FAILs. La diferenciación es exactamente la misma que la del proyecto: refutación primero, vara pre-registrada, costo declarado.

## 2. Audiencia objetivo (en ese orden)

1. **Círculo cercano técnico-curioso** (ej: Agustín) — primeros testigos, feedback honesto, amplificación orgánica.
2. **Builders y founders de IA** — gente que construye agentes y sufre los mismos problemas (ruteo, costos, loops que no aprenden).
3. **Early adopters potenciales del router** — empresas/devs con facturas grandes de IA (el dato de LLMRouterBench 2026: ~32% de ahorro ruteando bien).

No apuntás a "viralidad". Apuntás a 100 personas que entienden lo que hiciste antes que a 10.000 que scrollean.

## 3. Canales: opciones con pros y contras

| Canal | Pros | Contras | Recomendación |
|---|---|---|---|
| **X (Twitter)** | Donde están los builders de IA; los hilos técnicos viajan; fácil de empezar | Ruido alto; exige constancia; algoritmo premia polémica, no rigor | **Principal.** 2 hilos/semana. |
| **Threads** | Conexión directa con tu Instagram (audiencia existente); formato hilo nativo; menos tóxico | Menos audiencia técnica de IA; alcance orgánico incierto | **Secundario.** Republicar versiones cortas de los hilos de X. |
| **Blog propio (estático, ej: GitHub Pages)** | SEO duradero; casa propia; el paper vive acá; nadie te saca la cuenta | Cero distribución inicial; requiere trabajo de montaje | **Sí, pero simple.** Una página estática donde viven las notas largas y el paper. Sin plataforma de pago. |
| **LinkedIn** | Profesional; los compradores B2B del router están acá; formato artículo nativo | Tono corporativo; los FAILs pueden leerse mal | **Terciario.** Solo piezas de producto/negocio (router, paper), no el lab crudo. |
| **YouTube / video corto** | Formato que mejor explica sistemas; reusable | Producción cara en tiempo; no sos youtuber todavía | **No en el arranque.** Reevaluar en el mes 2 si hay tracción. |
| **Newsletter** | Lista propia; el paper como imán necesita un lugar donde entregarse | Mantenerla viva es un compromiso semanal | **Sí, mínima.** Solo como canal de entrega del paper + digest mensual. No como canal de contenido aparte. |

**Resumen operativo:** X como frente, Threads como espejo, blog como archivo, LinkedIn solo para negocio, newsletter solo para entregar el paper.

## 4. Formatos y frecuencia

Frecuencia realista con tu rutina (trabajo, fútbol martes, informe 10am, chequeo 23:00): **2 piezas/semana** como máximo sostenible.

1. **Hilo técnico en X** (lunes o martes): un hito, un experimento o un FAIL. Estructura fija: pregunta → diseño/variable → número → veredicto → lección. Siempre con el costo declarado.
2. **Nota de blog** (quincenal): la versión larga del hilo que más tracción tuvo. Acá viven los gráficos y la metodología (pre-registro, puerta de dos splits).
3. **Post de decisión** (X, cuando ocurra): decisiones de gobernanza o diseño, contadas como se tomaron — con la tensión incluida ("revertí mi propio veto").
4. **Digest mensual** (newsletter): qué se auto-adoptó, qué se rechazó, números del mes. Espejo público del digest dominical interno.

Formato visual mínimo: un gráfico por pieza importante (regret, costo, o comparación). Nada de memes ni clickbait. Los números son el gancho.

## 5. Calendario de arranque (2 semanas, hitos ya ocurridos)

Todo el material ya existe en tus logs. No hay que inventar nada: es contar lo que pasó.

### Semana 1

**Pieza 1 — Manifiesto (hilo X): "Estoy construyendo ALMA en vivo"**
- Qué es: un sistema que aprende de sus experiencias qué configuración de inteligencia necesita por problema.
- Las reglas del juego, declaradas de entrada: refutación primero (intento demostrar que ya existe antes que demostrar que es revolucionario), vara pre-registrada que no se mueve, FAILs aceptados sin cambiar criterios, costo de cada experimento declarado.
- Cierre: "Si en algún momento esto se vuelve humo, decímelo. Los números están para eso."

**Pieza 2 — EXP67 (hilo X + gráfico): la primera validación con modelos reales**
- El setup: 180 problemas reales (gsm8k, mmlu, mbpp), 3 brazos (single/cot/reflexion), oráculo con DeepSeek.
- El número: alma-full regret **3,445** vs mejor brazo fijo (cot) **10,945** vs aprendiz global **10,995**.
- El costo total: **~US$0,69** (oráculo US$0,3609 + políticas US$0,2667).
- La lección: aprender por régimen le gana a planes fijos y al aprendiz global — con tareas reales, no sintéticas.
- Honestidad incluida: el probe eligió bien (gsm8k→cot, mmlu→single, mbpp→single) y el skip funcionó 6/6.

**Pieza 3 — El router (hilo X): de experimento a producto**
- La idea fue tuya: ALMA elige qué proveedor usar por tarea.
- EXP69: el router por **reward/USD** (no por precio de token — si no, elegiría el más barato y más tonto) eligió al ganador ex post en **3/3 slices**; IC95 de la diferencia **[+585, +1925]**, costo US$0,0276.
- El hallazgo incómodo: el brazo más barato le gana al más inteligente (thinking 10–40× más caro por ganancia marginal).
- Puente a producto: esto es lo que se convierte en el router comercial. Validación en 3 etapas: motor → dogfood con uso propio → un extraño paga. Estamos en la etapa 1.

### Semana 2

**Pieza 4 — Los FAILs que acepté (hilo X): la serie BTC EXP36–42**
- 7 FAILs seguidos en replay sobre 720 velas horarias reales. El único PASS (EXP42) era un artefacto de medición: con contabilidad honesta, **−4,40%**.
- La conclusión que quedó: a escala horaria manda el ruido — la pregunta pasó de *qué regla* a *dónde* (escala diaria/semanal o el dominio original).
- Por qué se cuenta: es la prueba de que la vara no se mueve. Aceptaste 7 FAILs sin cambiar los criterios.

**Pieza 5 — Gobernanza (hilo X): "el sistema mejora a mis espaldas (pero no peor)"**
- La secuencia real: primero veto permanente a que el loop edite su código (línea roja) → fase 2.3 (toda promoción espera tu sí) → **revertiste tu propio veto** el 27/9 a las 22:50.
- La regla nueva: el meta-loop auto-adopta mejoras que pasen la puerta de dos splits, y te **avisa** cada evolución (qué cambió, efecto medido).
- El núcleo fuera de su alcance: topes de gasto y la obligación de notificar — si pudiera silenciar sus avisos, el "avísame" no valdría nada.
- El refinamiento del 22:52: solo ante **mejora medida**. Lo que mida igual o peor se rechaza y se registra. Nada de cambios laterales.

**Pieza 6 — El paper (post X + nota de blog): anuncio del imán**
- Qué es: el whitepaper con los experimentos (EXP67, EXP69, gobernanza, series de FAILs) — el documento que acredita el trabajo.
- Cómo se consigue: email a cambio (newsletter mínima). Este es el mecanismo de captura: del hilo al paper, del paper a la waitlist del router.
- Compromiso público: el paper se actualiza con cada experimento nuevo. Versión viva, no PDF muerto.

## 6. Qué se muestra y qué NUNCA

### Se muestra
- Hitos con números reales: regrets, costos por experimento, IC95, tasas de PASS/FAIL.
- FAILs aceptados y lo que refutaron (la refutación es contenido, no vergüenza).
- Decisiones de diseño y gobernanza, con la tensión real de cómo se tomaron.
- Metodología: pre-registro, mock-first, puerta de dos splits, frenos de gasto.
- Gráficos agregados de resultados (regret, costos, comparaciones).

### NUNCA
- **Keys, secrets, tokens, credenciales** — de ningún proveedor, bajo ningún formato (ni parciales, ni "tapados", ni en capturas de pantalla).
- **Datos personales y financieros tuyos** — saldos, movimientos bancarios, deudas, montos de ingresos, datos de Zelle/Plaid. El plan de contenido no toca tu vida financiera.
- **Terceros identificables** — nombres, fotos, chats o datos de roommates, familia o amigos, salvo que esa persona lo haya aprobado explícitamente.
- **Detalles de seguridad interna** — defensas del sistema, arquitectura del vault, allowlists, topes exactos de gasto, rutas de archivos del servicio vivo.
- **Código sensible** — nada del servicio en ejecución (puerto 8471), nada que permita replicar tu infraestructura de seguridad. Pseudocódigo y conceptos sí; implementación de seguridad no.
- **Promesas sobre el producto** — el router se cuenta como apuesta en validación (etapa 1 de 3), nunca como producto terminado. Cero humo también aplica al futuro.

## 7. Cómo conecta con la adquisición de clientes

El embudo es simple y honesto:

1. **Hilos en X** → atención de builders (etapa: audiencia).
2. **Paper** → captura de email; el lector que descarga el paper ya demostró interés serio (etapa: leads).
3. **Waitlist del router** → al final del paper y en el blog: "si tu factura de IA es grande, anotate" (etapa: prospectos).
4. **Dogfood público** → cuando el router corra sobre tu propio uso, los números de ahorro reales son la demo (etapa: prueba).
5. **Un extraño paga** → la validación final, contada también en público.

El paper es el imán porque es lo único que un comprador técnico respeta: no un landing con promesas, sino experimentos con números y FAILs incluidos. Nadie vende el loop completo (Thompson + probe + memoria con olvido + minería de debilidades + validación en dos splits) como capa embebible — el paper documenta exactamente esa brecha.

Regla de separación: el lab se cuenta de noche, el producto se vende de día. En el contenido no se mezclan: las piezas de lab hablan de ciencia, las de producto hablan de ahorro medido.

## 8. Qué necesita tu sí antes de publicar cada pieza

Nada se publica sin tu aprobación explícita, pieza por pieza. Es el mismo freno humano que diseñaste para el meta-loop (fase 2.3): staging inspeccionable, commit solo con tu sí. El pipeline por pieza:

1. **Borrador** — te lo presento en el chat, completo, con los números y el gráfico propuesto.
2. **Checklist de verificación** (la corro yo, la ves vos):
   - [ ] Números verificados contra los logs del experimento (no de memoria).
   - [ ] Grep de secretos: ninguna key, token o credencial en texto, imagen o metadata.
   - [ ] Cero datos financieros/personales tuyos.
   - [ ] Cero terceros identificables sin aprobación.
   - [ ] Nada del servicio vivo ni de seguridad interna.
   - [ ] Tono: sobrio, voseo, números reales, cero humo.
3. **Tu sí** — explícito, por pieza y por canal ("sí, publicá el hilo en X"). Un sí general no vale para la pieza siguiente.
4. **Registro** — qué se publicó, dónde, cuándo, con qué números. Si un número publicado después se corrige, se corrige en público.

## 9. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Alguien copia las ideas | Las ideas sin ejecución no valen; lo que te diferencia es el loop corriendo y los datos. El paper con fecha es además prueba de prioridad. |
| El tiempo del contenido roba tiempo del lab | Tope: 2 piezas/semana. Si una semana el lab pide todo, el contenido espera. El lab manda. |
| Un FAIL público se lee como fracaso | Es el punto: la refutación primero ES la marca. Quien no lo entienda no es tu audiencia. |
| Exponer de más por accidente | Checklist de la sección 8, siempre. Ante la duda, se corta la pieza y se te pregunta. |
| Prometer de más sobre el router | Regla fija: etapa 1 de 3 hasta que un extraño pague. Sin excepciones en el copy. |

## 10. Reglas de operación

- **US$0.** Planificar y redactar no cuesta nada. Si alguna pieza futura necesitara gasto (diseño, herramienta), se presupuesta y se aprueba antes.
- **Nada publicado desde este plan.** Cada pieza vuelve a vos antes de salir.
- **Ningún contacto con terceros** en esta fase: no se escribe a nadie, no se piden permisos, no se anuncian colaboraciones.
- **No se toca el servicio vivo** (puerto 8471): el contenido se escribe desde logs y documentos, nunca desde el sistema en ejecución.
- **El plan se revisa al mes**: si después de 8 piezas no hay tracción (ni respuestas, ni descargas del paper), se cambia el canal o el formato, no la honestidad.
