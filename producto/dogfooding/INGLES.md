# Dogfooding de ALMA para tu inglés

**Versión:** 1.0 — 28/9/2026
**Estado:** diseño (mock primero; ninguna noche real hasta que el mock dé PASS)
**Costo:** US$0 — no se crean crons nuevos, no se toca el servicio vivo

---

## La idea en una línea

El loop de ALMA (medir → aprender → elegir) ya existe para bandits. Acá lo comés vos en primera persona: **el loop elige qué método de inglés practicás cada noche según lo que midió de vos, no según lo que yo opine que funciona.** El agente oficia de resolver en el chequeo de las 23:00, a mano. Si el loop manual funciona y te resulta útil, recién ahí tiene sentido automatizarlo contra el servicio real.

## Qué problema resuelve

Hoy la recomendación es "frases útiles" porque ALMA lo sugirió una vez. Pero:

- ¿Es realmente el método que más te rinde, o solo el que sonaba razonable?
- ¿Y si la mini-conversación te engancha más y por eso la hacés más noches?
- ¿Y si el método que más te rinde cambia cuando estás cansado vs. cuando estás despierto?

Ninguna de esas preguntas se responde opinando. Se responden midiendo. Eso es este diseño.

---

## Los brazos candidatos (K = 5)

Cada brazo es un método concreto de 5 minutos. Nada de "practicá inglés" vago: cada noche hay un guion.

### Brazo A — Frases útiles
Una frase o expresión de la vida real (trabajo, fútbol, viaje). Yo te la doy con un ejemplo, vos la decís en voz alta 3 veces, y la usás en 2 frases inventadas por vos. Ejemplo: *"I'm tied up"* → "I'm tied up with the dishes" / "I'm tied up Thursday, can we move the game?".

### Brazo B — Mini-conversación
Yo hago de alguien (el mozo de Orilla, un turista, tu roommate) y tenemos un diálogo de 8–10 líneas en inglés. Vos respondés en inglés; yo corrijo lo importante al final, no en el medio. Es el único brazo con ida y vuelta.

### Brazo C — Vocabulario temático
5 palabras de un tema que vos elegís o te propongo (fútbol, cocina, viajes). Pronunciación, una frase de ejemplo cada una, y al final vos me las decís de memoria en cualquier orden. Simple, mecánico, funciona hasta cansado.

### Brazo D — Shadowing (lectura en voz alta)
Yo te paso 3–4 frases cortas; vos las leés en voz alta imitándome ritmo y entonación. Cero creatividad exigida: pura repetición con oído. Es el brazo más liviano cognitivamente.

### Brazo E — Corrección de errores del día
Durante el día yo anoto (o vos me tirás) errores o trabas que tuviste en inglés — un mensaje mal escrito, algo que no supiste decir. A la noche los repasamos: qué estaba mal, por qué, y la versión correcta dicha en voz alta. Es el brazo más personalizado y el único que depende de que haya material del día.

**Regla de material:** si un brazo no tiene material esa noche (ej. E sin errores anotados), se declara "no disponible" y el resolver elige entre los otros. No se fuerza.

---

## El reward: medible sin fricción

Tenés 5 minutos. No hay tests, no hay exámenes. El reward nocturno tiene dos componentes y se registra en el mismo chequeo de las 23:00:

**r = 0.6 · participación + 0.4 · (auto-reporte / 5)**

| Componente | Qué es | Cómo se mide | Fricción |
|---|---|---|---|
| **Participación (p)** | ¿Hiciste los 5 minutos? | 1 sí / 0 no — lo objetivo, no se discute | Cero: se nota solo |
| **Auto-reporte (s)** | "¿Cuánto te sirvió?" | Escala 1–5 que vos tirás en el chat | Una línea |

- Si p = 0 (no se hizo la sesión), el reward es 0 directamente. No hay auto-reporte que inventar.
- Si p = 1, el reward queda entre 0.68 (s=1) y 1.0 (s=5). La participación pesa más que la opinión: un método que hacés siempre con ganas mediocres le gana a uno brillante que salteás.

**Retención semanal (tie-breaker, no entra en el Thompson):** los domingos, en 1 minuto, te pregunto qué recordás de la semana sin mirar. Sirve como señal gruesa de qué método deja huella y como freno contra un brazo que puntúa lindo pero no pega. Si un brazo tiene p = 1 y s alto pero retención cero tres semanas seguidas, se marca para re-probe aunque gane.

**Sesgo honesto:** vos sos a la vez el sujeto y el juez del auto-reporte. Eso mete ruido optimista. Por eso la participación (objetiva) pesa más, y por eso la retención semanal existe. No pretendemos precisión científica: pretendemos un orden de mérito estable entre métodos.

---

## El probe inicial (las primeras semanas)

Un pull = una noche = un brazo. Con 1 pull por noche, explorar es caro: cada noche de prueba es una noche que no hacés lo mejor conocido. Por eso el probe es corto y pre-registrado.

**Fase 0 — Mock (antes de la primera noche real):**
Simulación en el laboratorio, US$0, corre en minutos: 500 mundos sintéticos, cada uno con rewards verdaderos aleatorios por brazo, corriendo el schedule de abajo + Thompson + skip. Vara pre-registrada:

1. En ≥ 70% de los mundos, el mejor brazo verdadero queda rankeado #1 en el posterior a las 4 semanas.
2. Tasa de skip falso (se deja de probar teniendo un brazo mejor sin medir) < 20%.
3. Arrepentimiento total del mock ≤ 1.5× el de un oráculo que conociera los rewards.

Si el mock da FAIL, se rediseña el schedule. Ninguna noche real arranca con un FAIL en el mock. (Regla mock-first, sin excepciones.)

**Fase 1 — Probe rotativo (semanas 1–2, 10 noches):**
Round-robin por los 5 brazos, 2 vueltas completas: A, B, C, D, E, A, B, C, D, E. Cada brazo arranca además con un prior de 2 pseudo-observaciones en 0.5 (prior débil: no decide nada, solo evita ceros). La noche del 28/9 ("frases útiles") cuenta como el pull 1 del brazo A — pero **recién después del PASS del mock**. El mock corre de día; la primera noche del probe es la primera noche posterior al PASS.

**Fase 2 — Thompson + skip (desde la noche 11):**
Cada noche, el agente (como resolver) muestrea del posterior de cada brazo y propone el ganador. El posterior es Beta sobre el reward: nada exótico, la misma maquinaria del scaffold validado (prior condicionado, skip endurecido). La única diferencia es que el oráculo sos vos.

---

## Regla de skip (cuándo dejar de probar)

Copiada de la filosofía EXP49/51/56–57: probar cuesta, así que cuando un brazo gana cómodo, se deja de pagar el costo del probe.

**Skip activo:** si un brazo cumple las tres condiciones, el resolver lo propone todas las noches sin rotar:

1. Tiene ≥ 5 pulls medidos.
2. Su media posterior supera a la del segundo mejor en ≥ 0.15.
3. Sus últimos 3 pulls tuvieron participación = 1 (no solo puntúa bien: se hace).

**Re-probe (cuándo se vuelve a probar):** el skip no es para siempre. Se reabre la exploración si:

- Participación = 0 dos noches seguidas (el ganador dejó de hacerse: algo cambió).
- Pasan 7 días sin probar otro brazo (regla stale: los métodos, como las skills del Curator, se vencen — active → stale → re-probe).
- La retención dominical marca 0 dos semanas seguidas.
- Vos lo pedís, en una palabra ("rotá", "cambiá"). Tu veto es instantáneo y no necesita motivo.

**Régimen de energía (constraint duro, no bandit):** si en el chequeo decís que estás fundido (una palabra alcanza: "cansado"), el resolver solo puede elegir entre los brazos livianos (A, D, y C si el tema es fácil). La energía no se aprende por Thompson: se respeta por regla. Cuando estés cansado no se experimenta con B ni E.

---

## El ledger (dónde queda todo)

Un archivo por mes, formato JSONL, una línea por noche:

```json
{"fecha": "2026-09-28", "brazo": "A", "p": 1, "s": 4, "r": 0.92,
 "energia": "normal", "skip": false, "nota": "frase: I'm tied up"}
```

Vive en `~/workspace/alma-prototype/producto/dogfooding/ledger/`. Es el oráculo real del experimento: si en 3 meses querés ver qué método te rindió, está ahí, noche por noche, sin depender de mi memoria.

---

## Qué necesita de vos

Poco, a propósito. La fricción mata al experimento antes que cualquier brazo malo.

1. **Dos líneas por noche, en el chequeo de las 23:00 que ya existe:** "lo hice" (o "no lo hice") y "me sirvió: N/5". Nada más. Yo registro el resto.
2. **Un minuto los domingos:** te pregunto qué te acordás de la semana. Sin mirar nada.
3. **Tu veto en una palabra:** cualquier noche podés decir "hoy no", "cambiá de método" o "congelá el B por una semana". Se cumple sin discusión y queda registrado como intervención (no como dato del brazo).
4. **Avisame si estás cansado:** una palabra ("cansado") activa el régimen de energía. Sin culpa: es información, no una falta.

**Lo que NO necesita:** ninguna app nueva, ninguna cuenta, ninguna instalación, ningún pago. No se toca tu cron de las 23:00 (el loop vive adentro del chequeo que ya tenés). No se toca el servicio ALMA (esto corre a mano; el servicio sigue en su puerto sin enterarse).

---

## Qué NO es esto (límites honestos)

- **No es un experimento publicable.** n = 1, el sujeto puntúa su propio tratamiento, 1 pull por noche. Es dogfooding: sirve para que el loop muerda datos reales y para que vos tengas un método elegido por medición. Nada más.
- **No mide "cuánto inglés aprendiste".** Mide qué método hacés más y cuál sentís que más te sirve. La retención semanal es un proxy, no un examen.
- **No reemplaza tu criterio.** Si el loop elige algo que te parece una porquería, tu veto vale más que el posterior. El loop aprende de vos; no al revés.
- **El mock manda.** Si la simulación dice que con 1 pull/noche el loop no converge en un tiempo útil, se rediseña antes de gastar tus noches. Tus 5 minutos valen más que mi schedule.

---

## Cronograma

| Cuándo | Qué |
|---|---|
| 28/9 (día) | Mock del schedule + skip en el laboratorio. Veredicto PASS/FAIL con la vara de arriba. |
| 28/9 23:00 (si mock PASS) | Noche 1 del probe: brazo A (frases útiles), como ya estaba recomendado. |
| Semanas 1–2 | Probe rotativo: 10 noches, 2 vueltas por los 5 brazos. |
| Noche 11 en adelante | Thompson + skip. El loop elige; vos vetás si querés. |
| Cada domingo | Retención de 1 minuto + nota semanal en el ledger. |
| Semana 4 | Primera lectura seria: ¿el loop convergió a un ganador? Se revisa el diseño con los datos reales. |
