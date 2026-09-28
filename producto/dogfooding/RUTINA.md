# Dogfooding de ALMA en tu rutina diaria

**Diseño — mock primero, US$0, nada toca tu rutina sin tu "sí".**

La idea: ALMA se entrena primero con vos. El loop que aprende por régimen (Thompson + probe + skip, memoria con olvido) se aplica a tu rutina diaria antes de ofrecerse a nadie. Acá está qué mediría, qué decidiría, cómo se valida en simulador y qué te pediría.

---

## 1. Qué mediría el loop

### Lo que ya existe (cero costo extra)
Del chequeo nocturno de las 23:00 ya reportás:
- **Energía 1–10** — el reward principal ya está medido.
- **Chispa 1–5** — señal secundaria, correlaciona con energía pero mide otra cosa (ánimo/curiosidad).
- **Qué hizo del día** — narrativa libre, el loop la usaría solo para contexto.

### Lo nuevo que te pediría (máximo 2 datos, liviano)
1. **Qué actividad hiciste** — una palabra: `playa` / `gym` / `descanso` / `otra`. Esto es el *brazo que se jugó* y mide cumplimiento. Sin este dato el loop no puede aprender: energía sin saber qué la causó es ruido.
2. **Horas de sueño aprox.** — una cifra (ej. `6,5`). Una sola, sin obsesión, sin sermón: el sueño entra como *firma del régimen*, no como juicio.

### Lo que NO te pide
- El régimen del día (día libre vs. día con turno en Orilla) se infiere del calendario y de tus patrones de reporte, no se pregunta.
- Nada de listas de hábitos, ni de puntajes nuevos, ni de "¿meditaste?". Dos datos, 10 segundos.

---

## 2. Qué decidiría

**Una sugerencia por día en el informe matutino:** la rutina recomendada para hoy.

El loop elige entre rutinas candidatas según:
- el régimen detectado (día libre / día de trabajo nocturno / racha de poco sueño),
- lo que rindió en regímenes parecidos en el pasado (memoria con olvido: lo de hace 3 meses pesa menos),
- y cada tanto *prueba* algo distinto a propósito (probe) para no quedarse estancado en lo que funcionaba antes.

No es una orden ni un coach. Es: *"hoy conviene descanso — venís de 3 días de energía < 5 y mañana tenés turno; el gym rindió mal en ese régimen"*. La decisión final siempre es tuya; el loop aprende de lo que hagas igual.

---

## 3. Diseño de brazos y reward

### Brazos (rutinas candidatas)
| Brazo | Qué es |
|---|---|
| **playa** | La mañana en el mar (tu mejor parte del día) |
| **gym** | Fuerza / flexiones, día de entrenamiento |
| **descanso** | Recuperación activa, sin actividad física fuerte |
| **mixto** | Playa corta + gym liviano (brazo intermedio) |

Cuatro brazos es el techo razonable: más brazos = más exploración = más días "pagando" el probe.

### Reward
```
reward_día = 0,7 × energía_normalizada(t+1) + 0,3 × cumplimiento
```
- **Energía del día siguiente** (normalizada a 0–1): el efecto real de la rutina se mide al día siguiente, no el mismo día. Es el 70%.
- **Cumplimiento** (0/1): ¿hiciste lo que el loop sugirió —o la actividad que hiciste coincide con la rutina del día? El 30%. Sin cumplimiento el reward se desacopla de la decisión.

La chispa queda como señal de diagnóstico (para detectar que el loop está optimizando energía pero matando el ánimo), no entra al reward hasta que haya evidencia de que vale la pena.

### Regímenes (la firma que condiciona el prior)
- **Día libre** vs. **día de turno en Orilla** (noche larga, acostarse tarde).
- **Racha de sueño corto** (≤ 2 noches de < 6 h).
- **Racha de energía baja** (≥ 3 días con energía < 5).

El prior de Thompson se condiciona a la firma del régimen —igual que en los experimentos de skills EXP45/49/51—: *qué brazo rindió en días como hoy*, no en general. Y el **skip del probe**: cuando el régimen es claro (ej. turno largo anoche → hoy descanso), el loop no "prueba" nada: explora solo cuando la incertidumbre lo justifica.

### Vara pre-registrada (antes de medir nada con vos)
El loop tiene que batir a la **mejor rutina fija** (ej. "siempre playa en día libre, siempre descanso en día de turno") en energía promedio a 60 días, con la diferencia fuera del intervalo de confianza del azar. Si no la bate, la sugerencia no sale del simulador.

---

## 4. Cómo arranca en mock (antes de tocar tu rutina real)

Fase 0 — **simulador, US$0**, ningún dato tuyo real:
1. Generar 120–180 días sintéticos con distribuciones calibradas a tus reportes típicos (energía, chispa, cumplimiento), incluyendo **no-estacionariedad**: flips de régimen como los del EXP44 (la categoría dominante rota), porque tu vida real también cambia.
2. Correr: ALMA-full vs. mejor rutina fija vs. Thompson global. Pre-registro con la vara del punto 3.
3. **Puerta de dos splits**: el ajuste que gane en el split A tiene que ganar también en el split B (días nunca vistos) antes de proponerse siquiera para piloto.

Fase 1 — **piloto pasivo con tus datos reales** (solo lectura de lo que ya reportás):
- El loop observa 30–60 días de tus chequeos sin sugerir nada. Mide si sus predicciones ("hoy este brazo rinde") aciertan mejor que el azar. US$0, ningún cambio a crons ni al informe.

Fase 2 — **sugerencia visible, solo con tu "sí"**:
- El informe matutino agrega una línea con la rutina sugerida y el porqué. No se toca el cron: es texto extra dentro del informe que ya recibís. Si la sugerencia no te sirve, se ignora y el loop lo registra.

Fase 3 — **auto-adopción bajo tu regla de gobernanza** (del 27/9):
- El meta-loop solo auto-adopta mejoras que pasen la puerta de dos splits con mejora medida y sin regresión; te avisa cada evolución (qué cambió, efecto medido). Nunca edita el núcleo: topes y la obligación de avisarte quedan fuera de su alcance.

**Regla dura:** ningún cambio a tus crons, jobs o al servicio vivo (puerto 8471) en ninguna fase. El dogfooding corre en paralelo, en su propio espacio.

---

## 5. Qué necesita de vos, explícitamente

1. **El dato nuevo**: qué actividad hiciste (una palabra) en el chequeo nocturno. Opcional: horas de sueño aprox. Todo lo demás ya lo reportás.
2. **Tu "sí" para la Fase 1** (piloto pasivo, solo lectura) — cuando el mock dé PASS.
3. **Tu "sí" para la Fase 2** (la sugerencia en el informe matutino) — cuando el piloto confirme que predice mejor que el azar.

Nada más. Ni tope de gasto (es US$0), ni cambios a tu rutina, ni acceso a nada nuevo.

---

## 6. Lo que este diseño NO es

- No es un coach de hábitos ni una app de productividad: es ALMA comiéndose su propia comida.
- No opina sobre tu sueño: lo usa como variable del régimen, punto. Sin sermones.
- No promete que vas a tener más energía: promete medir honestamente si la sugerencia rinde más que tu rutina actual, y apagarse si no.
