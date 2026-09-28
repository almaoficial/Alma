# EXP71 — Pre-registro: el loop sobre el feed real durante 1 semana

**Fecha:** 2026-09-28 ~01:30 EDT. **Costo:** mock, US$0, sin API keys.
**Estado:** escrito ANTES de correr el setup y de cualquier medición.
Parámetros, criterio y protocolo congelados a partir de acá.

## 1. Pregunta e hipótesis

El EXP44 (mock, FAIL) mostró que, a granularidad de bloque (~10 noticias),
la categoría dominante del feed real rota en 8/8 transiciones y la
exploración del loop era puro costo: el mundo se movía más rápido de lo
que cualquier maquinaria con probe podía seguir.

**Pregunta:** a granularidad DIARIA (n=7 días), ¿la maquinaria del loop
(Thompson por régimen + probe + skip + detector de heterogeneidad EXP68)
anticipa la categoría dominante del feed mejor que predictores triviales?

**Hipótesis de trabajo (escéptica):** no. El prior es que el feed diario
rota igual que los bloques del EXP44 y el loop no le gana a lo trivial.
Un FAIL acá es informativo (confirma la lección del EXP44 a otra escala),
no una decepción. La vara no se mueve después.

## 2. Curación del stream (propiedades registradas por cuenta propia)

Regla AGENTS.md 27/9: el pre-registro declara la selección/curado del
stream sin esperar a que nadie lo señale.

1. **El feed filtra por interés personal.** No es "todas las noticias" ni
   una muestra aleatoria de la agenda: es un stream curado para el usuario
   (IA, agentes, finanzas, fútbol, etc.). La distribución de categorías
   refleja SUS intereses, no la agenda general. Los resultados NO
   generalizan a "predicción de noticias" en general.
2. **~18% del contenido es fabricado por el stream.** Medido el 27/9 sobre
   94 unidades: ~18% no tiene fuente real en la web. Es ruido de síntesis
   independiente del loop: puede mover la categoría dominante de un día
   por razones ajenas a la agenda real. Se reporta como caveat, no se
   corrige (corregirlo sería un grado de libertad del investigador).
3. **Las categorías las asigna el generador del feed.** La taxonomía puede
   derivar (ej: en EXP44 conviven "Inteligencia artificial", "AI research"
   e "IA investigación" como etiquetas distintas). NO se normaliza:
   se compara string exacto (recortado). Los casi-duplicados cuentan como
   categorías distintas y se reportan como caveat.
4. **Cadencia propia.** El feed genera en su propio ritmo; un día puede
   traer pocas unidades. Día válido ⟺ ≥ 5 unidades con categoría.

## 3. Diseño

- **Unidad de tiempo:** 1 día calendario (America/New_York) = 1 bloque.
- **Brazos:** las categorías del feed. Taxonomía inicial: las 30
  categorías observadas en EXP44 (`data_exp44/feed_units.json`).
  Categorías nuevas que aparezcan en un inbox se agregan como brazos con
  prior Beta(1,1) ANTES de computar el dominante de ese día (nunca pueden
  ser predichas el día que debutan: la predicción ya estaba congelada).
- **Oráculo:** la categoría publicada por el feed para cada unidad
  (verdad barata y real, misma convención del EXP44).
- **Observación del día D:** conteo de categorías del inbox de D.
  Dominante(D) = argmax estricto; si hay empate, el dominante es el
  CONJUNTO empatado (se registra el empate).
- **Recompensa:** 1 si la predicción ∈ dominante(D), 0 si no.

### Qué cuenta como "anticipar" (definición operativa)

La predicción para el día D se computa a la mañana de D usando SOLO
historia observada hasta D−1, y queda congelada en `predicciones.jsonl`
antes de que exista el inbox de D. Anticipar = predicción congelada ∈
dominante observado de D. Sin excepciones, sin reescrituras.

## 4. La maquinaria (transplante fiel, parámetros congelados)

Scaffold: `DEFAULT_SCAFFOLD` (n0=4, umbral_base=1, umbral_divisor=3,
decay=0,5, gate_margin=0,0). Detector: K=3, J=3 (EXP68, validado).

**Posterior:** por categoría c, Beta(a_c, b_c) = P(c es el dominante del día).
- Init (setup, solo con datos semilla 22–23/9): a_c = 1 + w·n_c,
  b_c = 1 + w·(94 − n_c), con w = n0/94 = 4/94 (la semilla aporta peso
  total exactamente n0=4, la fuerza del prior del scaffold).
- Update por día observado D (dominante estricto d): primero olvido
  a_c ← 0,5·a_c, b_c ← 0,5·b_c (decay congelado); luego b_c += 1 ∀c,
  a_d += 1 (cada día es un trial Bernoulli por brazo).
- Empate en D: NO actualiza el posterior (evidencia ambigua; decisión
  conservadora pre-registrada). El día igual se puntúa (§6).

**Predicción para D (a la mañana de D):**
1. **Detector de heterogeneidad** (state machine, semántica EXP68):
   - En modo ENCOGIDO: predecir el comprometido; cada J=3 días encogidos
     el día es spot-check → predecir por Thompson sampling en vez del
     comprometido.
   - Veredicto del día (modo EXPLORAR) = dominante estricto observado;
     empate o día SKIP → reinicia la racha (convención EXP68: sin
     medición no hay unanimidad; el empate no es veredicto).
   - K=3 veredictos estrictos iguales seguidos → ENCOGIDO.
   - Salida (adaptación de granularidad, pre-registrada): el spot-check
     original medía 3 ítems y exigía margen ≥2 para salir. Acá 1 día =
     1 observación: se sale ⟺ el dominante observado del spot-check es
     estricto Y distinto del comprometido. Empates no expulsan
     (histéresis EXP68). Al salir, racha reseteada.
   - En ENCOGIDO el posterior SIGUE actualizándose (solo la predicción
     está comprometida).
2. **Skip/gate** (transplante de umbral_base/umbral_divisor a unidades
   de probabilidad): sea f el favorito (argmax de medias; empates →
   orden alfabético, determinista). Si μ_f − μ_2do ≥ 1/3 → predecir f
   (se saltea el probe). Si no → Thompson sampling.
3. **Thompson sampling:** θ_c ~ Beta(a_c, b_c) con RNG sembrado por la
   fecha (`random.Random(int(AAAAMMDD))` — determinista, auditable,
   fijado antes de ver resultados). Predecir argmax θ. Es "día de probe"
   ⟺ el muestreo elige un brazo ≠ f.

**Baselines** (misma información, congelados a la misma hora):
- **Persistencia:** predecir el dominante de D−1 (para D=2026-09-28: el
  dominante semilla).
- **Moda histórica:** moda de dominantes observados hasta D−1 (incluye
  día 0 semilla; empates → el más reciente).
- **Azar:** referencia 1/C (C = categorías vistas); no compite.

## 5. Protocolo (fechas congeladas)

- **Setup (hoy lun 2026-09-28):** computar dominante semilla de
  `feed_units.json`, inicializar posterior, computar y CONGELAR la
  predicción para el 2026-09-28 (loop + baselines). No se lee el feed
  del 28/9 en el setup.
- **Runs 1–7 (mar 29/9 → lun 5/10, 11:00 EDT aprox):** el run de la
  mañana T: (a) lee el inbox de T−1; si falta/ilegible o <5 unidades →
  día SKIP (no puntúa, no actualiza, no alimenta al detector);
  (b) puntúa la predicción congelada de T−1 vs dominante(T−1);
  (c) actualiza posterior + detector con lo observado;
  (d) computa y congela la predicción para T.
- **Días puntuados:** 28/9, 29/9, 30/9, 1/10, 2/10, 3/10, 4/10 → n=7.
- **Veredicto:** al cerrar el run 7 (lun 5/10 ~11:00) con 7 días
  puntuados → `VEREDICTO.md`, se desactiva el cron.
- **Extensión por SKIP:** si hubo SKIP, la ventana se extiende día a
  día hasta 7 puntuados, con tope de 10 runs. Si a los 10 runs hay <7
  puntuados → veredicto INCONCLUSO (la falta de datos no es refutación).

## 6. Criterio pre-registrado (congelado)

Métrica primaria: accuracy = correctos / 7 (loop, persistencia, moda).

> **PASS ⟺ acc_loop > acc_persistencia ∧ acc_loop > acc_moda.**

Empates con un baseline no cuentan como superarlo. FAIL en cualquier
otro caso con 7 días puntuados. INCONCLUSO si <7 puntuados tras 10 runs.

Secundarias (descriptivas, no deciden): hit-rate en días de probe,
enganches del detector (cuántos, falsos/restaurados), rotación del
dominante día a día (X/6 transiciones; EXP44: 8/8), n° de empates,
categorías nuevas aparecidas.

Nota de potencia honesta: con n=7 la potencia es baja; es un piloto.
La vara es deliberadamente dura (batir a AMBOS triviales) porque la
pregunta es si el loop anticipa DE VERDAD, no si empata con la moda.

## 7. Fuente de datos diaria y fallback (sin inventar datos)

1. El worker del cron intenta `feed.unit_list` para el día T−1 (defensivo;
   documentado que desde automatizaciones agendadas no funciona).
2. Si no, lee `data_exp71/inbox/feed_<T−1>.json` (volcado desde el chat
   principal; formato en `inbox/README.md`). Hook sugerido: el cron
   `feed-veracidad-diaria` (09:23) ya lee el feed a diario.
3. Si no hay inbox → día SKIP con motivo registrado. El primer SKIP por
   falta de inbox genera UN aviso al chat principal; los siguientes, no.
4. Jamás se sintetizan categorías ni se reutiliza otro día como
   sustituto.

## 8. Compromisos

- K, J, n0, umbrales, decay, regla de skip, criterio, protocolo y
  semilla RNG **no se tunean** después de este pre-registro.
- Mock US$0. Ninguna key. Ningún gasto real.
- No se toca el servicio vivo del puerto 8471 (el harness es un script
  autocontenido; no importa `alma_service`).
- `resultados.jsonl` acumula un registro por día puntuado/SKIP;
  `predicciones.jsonl` congela cada predicción con su timestamp.
- Todo veredicto sale de lo medido, nunca del posterior ni de
  re-análisis post-hoc.
