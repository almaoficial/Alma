# ALMA — Informe v2: la serie real (25–28/9/2026)

**Fecha:** 2026-09-28 · **Costo total del laboratorio:** registrado por experimento, regla mock-first en toda la serie
**Alcance:** v1 cubría EXP1–EXP4 (mundo sintético, 25/9). Este informe incorpora la serie completa: EXP5–EXP70, fases 0–2 del servicio, y el cierre de cada línea de trabajo con su veredicto.

> **Criterio de escritura:** todo número de este informe sale de un veredicto en disco
> (`~/workspace/alma-prototype/resultados/` y `~/workspace/alma-prototype/integracion_fase21/resultados/`).
> Nada está redondeado para que suene mejor. Cuando la vara no se pasó, el veredicto es FAIL y la vara no se movió.

---

## 1. Síntesis ejecutiva

La serie validó el loop mínimo en márgenes finos y luego **salió del mundo sintético**: con un modelo real (deepseek-flash) y tareas reales (GSM8K, MMLU, MBPP), el loop con probe por régimen le ganó a las políticas fijas y al aprendiz global con margen amplio (EXP67: 3,445 vs 10,945 de la mejor fija). Pero la misma serie demostró que esa ventaja es **condicional al mundo, no intrínseca al loop**: con otro modelo real (deepseek-flash en EXP62) el mundo colapsó a un solo brazo y el loop adaptativo perdió contra la política fija obvia.

El balance honesto en una línea: **el mecanismo funciona (detectar por régimen + skip + Thompson con prior condicionado), pero solo cobra cuando hay heterogeneidad que explotar; cuando no la hay, la exploración es puro costo.** La serie agregó la meta-regla que faltaba —un detector de heterogeneidad que achica la exploración cuando el probe es unánime— y cerró con un router por eficiencia (reward/USD) validado en held-out.

**En criollo:** el sistema aprende cuál de sus modos usar según el tipo de problema, y eso le gana a usar siempre el mismo modo —siempre que los modos sean realmente distintos entre sí. Cuando un modo gana en todo, aprender a elegir es gasto al pedo, y el sistema ya sabe reconocer ese caso y frenar.

### Marcador de la serie

| Experimento | Veredicto | Esencia |
|---|---|---|
| EXP62 (réplica DeepSeek) | **FAIL** | El mundo colapsó a single 117/120; alma-full 4,82 vs fija −0,03 |
| EXP66 (minero de debilidades) | **STAND DOWN** | Fix refutado en simulador gratis; US$0,00 de US$0,08 aprobados |
| EXP67 (benchmark real) | **PASS** | alma-full 3,445 vs mejor fija 10,945; primera evidencia fuera del mock |
| EXP68 (detector heterogeneidad) | **PASS** | +6,00 en mundo homogéneo, 0 regresión en heterogéneo; integrado al servicio |
| EXP69 (router por R/USD) | **PASS** | Elige al ganador ex post 3/3 slices; generaliza en held-out |
| EXP64-skip (n=20) | **LOAD-BEARING** | Quitar el skip: +6,55 IC95 [+2,19,+10,92], pasa por el umbral justo (14/20) |
| EXP70 (piloto Claude) | **PARCIAL** | 63/72 pulls; mbpp 0,000 en los 3 brazos; overshoot de freno +2,8% admitido |
| EXP18 (4 seeds, api real) | **FAIL global** | 4/4 FAIL; 9/10 bloques correctos pero el costo del probe supera el beneficio |
| EXP20 (errores correlacionados) | **PASS** | La selección sobrevive a rho=0,5; margen idéntico a EXP19 |
| EXP11b (puerta de diseño) | **FAIL DE DISEÑO** | No hay flip real que detectar con estos brazos; US$0 gastados |

---

## 2. Qué se probó realmente

La serie completa (EXP1–EXP70) combina tres tipos de evidencia:

1. **Mock puro (US$0):** mundos sintéticos con oráculo conocido — sirve para aritmética del mecanismo (¿el skip carga? ¿el detector engancha?), nunca para declarar que algo "funciona en la realidad".
2. **Oráculo medido + replay:** se mide el reward real de cada brazo en cada problema una vez (con costo), y después las políticas se evalúan sobre esos datos con RNG pareado. Es lo más cercano a campo sin gastar por réplica.
3. **API real con freno duro:** corridas con modelos reales (gpt-4o-mini, deepseek-flash, claude-haiku), pre-registro antes de gastar, freno en dólares que corta la corrida.

La regla mock-first rigió toda la serie: **ningún gasto de key en una pregunta que el mock ya respondió.** El caso de libro es el EXP66 —tenía US$0,08 aprobados y se gastó US$0,00 porque el simulador gratis refutó el fix antes de tocar la key.

**En criollo:** primero lo barato, después lo caro. Y si lo barato ya te dijo que no, lo caro ni se prueba.

---

## 3. EXP67 — el PASS que cambió el estatus de la evidencia

**Veredicto: PASS** (pre-registrado 27/9). 918 llamadas, US$0,2667 (freno US$0,45), ~51 min. Cinco políticas × 180 problemas frescos del stream (9 bloques × 20, orden pre-registrado), RNG pareado por posición, evaluador idéntico al EXP62.

| Política | Regret |
|---|---|
| **alma-full** | **3,445** |
| fija-cot | 10,945 |
| thompson-global | 10,995 |
| fija-single | 19,645 |
| fija-reflexion | 36,895 |

La vara exigía las dos condiciones: regret(alma-full) < mejor fija (3,445 < 10,945 ✓, menos de un tercio) y < thompson-global (3,445 < 10,995 ✓).

**Por qué importa:** es la **primera evidencia de que la ventaja del loop no es un artefacto del mundo sintético**. Tareas reales, modelo real (deepseek-flash), oráculo medido de 1080 pulls (US$0,3609) sobre problemas que el piloto nunca vio. Costo total del experimento: ~US$0,69 (piloto + oráculo + políticas).

**Diagnóstico:** el probe eligió bien en los 3 bloques iniciales (gsm8k→cot, mmlu→single, mbpp→single — coincide con el oráculo medido) y el skip funcionó 6/6 sin misfires: a partir del bloque 3 el loop ya sabía qué brazo usar por slice y no gastó más en probar. 27 pulls de probe en vez de 81. thompson-global (10,995) no le gana a la mejor fija (10,945): **aprender sin distinguir regímenes no alcanza — la memoria por slice es load-bearing.** alma-full tocó regret 0,0 en 3 bloques; su peor bloque fue 0,87.

El oráculo dejó los perfiles de debilidad medidos (reward medio DeepSeek): gsm8k — cot 0,967 / reflexion 0,95 / single 0,633; mmlu — single 0,917 / cot y reflexion 0,80; mbpp — single 0,108 / cot 0,058 / reflexion 0,05. Código con tests en sandbox sigue siendo el slice más duro.

**En criollo:** con problemas de verdad y un modelo de verdad, el sistema que primero prueba qué modo anda mejor para cada tipo de problema y después se acuerda, le sacó 3× de ventaja al mejor plan fijo. La memoria por tipo de problema es lo que hace la diferencia, no "aprender en general".

**Honestidad incómoda:** el piloto (puerta) quedó ABIERTA con US$0,0623 y el oráculo se midió antes que las políticas — el diseño es replay, no corrida en vivo. La comparación es pareada y honesta, pero no es "el loop corriendo solo en producción".

---

## 4. EXP62 — el FAIL que le puso techo a la ambición

**Veredicto: FAIL** (pre-registrado 27/9). Réplica fiel del EXP5 con `deepseek-flash` como motor. Costo US$0,2559 (freno US$1,00 nunca tocado), 1743 llamadas, 3 crashes con resume idempotente (la API de DeepSeek estuvo muy inestable esa noche).

| Política | Regret |
|---|---|
| fija-single | **−0,030** (mejor fija) |
| thompson-global | 3,680 |
| **alma-full** | **4,820** |
| fija-cot | 7,170 |
| fija-reflexion | 26,220 |

Criterio: alma-full < mejor fija (−0,03 vs 4,82 → diff **+4,85** ✗) y < thompson-global (4,82 vs 3,68 → diff **+1,14** ✗). alma-full ganó **0/10 bloques**.

**El hallazgo central:** el oráculo re-medido con deepseek-flash (3 intentos/celda) colapsó: **single 117/120, cot 3/120, reflexion 0/120** (éxito medio: single 0,744 · cot 0,675 · reflexion 0,669). Con gpt-4o-mini el oráculo era heterogéneo por bloques —había algo que descubrir—. Con deepseek-flash, el modo non-thinking gana casi en todo: **no hay heterogeneidad que explotar, y el loop no tiene de qué alimentarse.**

**Lo que este FAIL refuta:** el agnosticismo al modelo. La ventaja del EXP5 era condicional al perfil de debilidad de gpt-4o-mini, no una propiedad intrínseca del loop. Con un modelo donde un brazo domina, el loop adaptativo es peor que la política fija obvia.

**Diagnóstico honesto:** el probe **no** es el problema —eligió single en los 10/10 bloques—. El problema es arquitectónico: el probe solo controla 3/12 problemas por bloque y los 9 restantes van a Thompson con warm-start, que exploró caro (single 40/90 · cot 35/90 · reflexion 15/90) cuando la ventaja entre brazos era de apenas 0,06 con rewards ruidosos. Peor: alma-full perdió contra el thompson-global frío —el prior warm con las medias del oráculo alentó exploración en vez de explotación.

**En criollo:** cambiamos el motor por uno más parejo y el sistema perdió contra la opción más tonta ("usá siempre el modo barato"). No porque el detector ande mal —detectó perfecto 10 de 10— sino porque cuando no hay nada que descubrir, explorar es tirar plata. La lección no es "el loop no sirve"; es "el loop sirve donde hay variedad, y hay que enseñarle a reconocer cuando no la hay".

**Costos y misses (no se esconden):**
- La estimación de costo que se dio (~US$0,02–0,05) quedó corta por 5–10×; el real fue US$0,2559. El smoke ya mostraba el costo por llamada (~US$0,0005) y la proyección debió recalcularse ahí. Miss registrado.
- 1 llamada de smoke (~US$0,0001) se perdió sin registrar por un crash antes del primer append. Va al veredicto, no se esconde.
- Bug en `report.json`: los flags de victoria quedaron hardcodeados en `True`; corregidos a `False` (los números siempre estuvieron bien).
- El "dial de esfuerzo 1–100" del anuncio no existe en chat/completions: niveles reales `none`/`high`/`max` (mapeados a single/cot/reflexion). Documentado en el pre-registro.

**Pregunta abierta que deja EXP62:** ¿hay mundos reales donde el oráculo sea heterogéneo *para un modelo fuerte*? Si no, el loop solo agrega valor sobre modelos débiles — un techo incómodo para ALMA, y la pregunta honesta que la próxima fase tiene que contestar.

---

## 5. EXP66 — el minero que se autorrefutó (US$0,00)

**Veredicto: STAND DOWN.** US$0,00 gastados de US$0,08 aprobados. Aprobado el 27/9 ~18:35: minar firmas deterministas de fallo de las trazas reales del oráculo de EXP62, proponer una edición del scaffold y validarla con la puerta de dos splits.

**Fase A (US$0):** firmas minadas — la dominante: `(alma-full, *, cot|reflexion, fallo)`: Thompson elige el brazo caro ~50/90 contra un oráculo single 117/120. Hallazgo extra: 2 de las 3 celdas no-single del oráculo son un único intento afortunado (0,94) — **el argmax sobre 3 intentos premia outliers.**

**La edición propuesta y pre-registrada:** prior de Thompson anclado al ganador del probe (N_ANCLA=8). **El pre-test mock la mató antes de gastar:**

| Variante | Regret medio | vs baseline |
|---|---|---|
| baseline (alma-full real) | 5,42 | — |
| **ancla al probe (la edición)** | **5,92** | **peor** |
| probe-only (sin warm) | 6,75 | peor |
| bandit global frío | 4,90 | ruido |
| warm con decaimiento | 5,38 | ruido |

Y lo decisivo (30 seeds): alma-full vs thompson-global dif = **0,44 ± 1,72** (dif>0 en 16/30). La "derrota del Thompson warm contra el frío" que reportó el EXP62 (+1,14) **es ruido** — dentro de 1 sd. No hay señal load-bearing que una edición pueda explotar. Causa raíz del daño del ancla: en el bloque 0 el probe midió single=0,45 (ruidoso-bajo) y el ancla arrastró el posterior del ganador hacia abajo en vez de concentrarlo.

**Decisión de gasto: NO CORRER.** La regla dura lo autorizaba (estimado US$0,0432 ≤ US$0,08), pero la regla mock-first tiene prioridad: **nunca gastar key en una pregunta que el mock ya respondió.** Gastar US$0,04 habría sido ritual, no ciencia. Razón adicional: la puerta de dos splits no puede detectar sobreajuste al mundo cuando ambos splits vienen del mismo stream colapsado —un PASS acá sería el artefacto del EXP42 con otro nombre.

**Lectura: ¿puede el loop aprender de este FAIL? No — porque no hay defecto aprendible.** El FAIL de EXP62 no es un bug del loop: es la ausencia de heterogeneidad. Ningún tweak de Thompson le gana al ruido en un mundo single-dominante; la única política que gana ("jugar single siempre") es la respuesta, no una regla aprendible — y sería catastrófica en un mundo heterogéneo como el del EXP5.

**En criollo:** el sistema intentó arreglar solo su derrota, y antes de gastar un centavo se probó el arreglo en el simulador gratis: el arreglo empeoraba las cosas. Entonces no se gastó nada. Eso es la disciplina funcionando: la plata aprobada quedó intacta porque la evidencia gratis dijo que no.

La lección accionable real que dejó EXP66 (trabajo futuro, no de este experimento): ALMA necesita un **detector de heterogeneidad** — una meta-regla que encoja la exploración cuando el probe es unánime K bloques seguidos — **validada en un mundo heterogéneo**, para verificar que no rompe la adaptación donde sí hay algo que aprender. → Eso es el EXP68.

---

## 6. EXP68 — el detector que sí pasó (y ya está en el servicio)

**Veredicto: PASS** (pre-registrado 27/9, mock US$0, sin fase con key — la pregunta era aritmética del mecanismo y el mock la respondió).

| Mundo | Δ medio | IC95 | Enganches |
|---|---|---|---|
| A (homogéneo, estilo EXP62) | **+6,00** | [+2,17, +9,83] | 5/5, todos en `contexto` (correcto), 0 restauraciones |
| B (heterogéneo, estilo EXP5) | **+0,00** | [+0,00, +0,00] | 1/5 (bloque 23, último; efecto neto 0) |

Δ = regret(baseline) − regret(detector), pareado por réplica. Criterio: media(Δ_B) ≥ 0 ∧ media(Δ_A) > 0. Se cumple. Deltas por réplica — A: +6, +8, +1, +9, +6 (los 5 positivos). B: 0, 0, 0, 0, 0.

**Lectura:** el loop ahora sabe cuándo no hay nada que descubrir. En el mundo homogéneo el detector engancha (mediana bloque 9) y banca al ganador unánime, ahorrando ~6 puntos de regret sobre 240 items (~2,5%) sin una sola falsa salida en validación. En el mundo heterogéneo no interviene: el skip del scaffold sigue haciendo su trabajo y el detector no lo estorba.

**El mecanismo clave que emergió de la calibración:** el veredicto tiene que ser el **probe** (argmax de lo medido), no el brazo comprometido del posterior. El posterior con decay=0,5 se enganchó 18 bloques al brazo equivocado — es una señal pésima para rachas.

**Caveats honestos:** Δ_B = 0 por inacción, no por acción (el detector casi nunca engancha en B; la pata de restauración quedó poco ejercitada: 1 restore en 25 réplicas). El mundo A es estilizado. n=5 réplicas, aunque el IC95 de A excluye el 0 con margen.

**Consecuencia:** primera promoción aprobada bajo la nueva gobernanza ("vamos nomas") — el detector vive en `alma_service/heterogeneidad.py` y está integrado al servicio.

**En criollo:** el arreglo que el EXP62 pedía a gritos ya existe y funciona: cuando el sistema ve que un modo gana siempre, deja de probar los otros y ahorra. Y cuando el mundo sí varía, no se mete. Es la respuesta directa al techo que marcó el FAIL.

---

## 7. EXP69 — el router por eficiencia (y su generalización)

**Veredicto: PASS** (pre-registrado 27/9). Idea del usuario: que ALMA elija qué llave usar por tarea; refinamiento: maximizar **reward/USD**, no minimizar precio del token. Piloto OpenAI (180 llamadas, gpt-4o-mini) en paralelo al oráculo DeepSeek. Costo US$0,0276 (freno US$0,25). 180/180 pulls, sin incidentes.

| Slice | Elección del router | R/USD |
|---|---|---|
| gsm8k | deepseek/single | 47.782 |
| mmlu | deepseek/single | 36.630 |
| mbpp | deepseek/single | 2.821 |

Criterio 1: router == ganador ex post en 3/3 slices (vara ≥2/3) ✓. Criterio 2: IC95 bootstrap (10.000 réplicas) de la diferencia de R/USD global (OA−DS) = **[+585, +1925]**, no incluye el 0 ✓.

**Hallazgo:** el ganador de eficiencia es el brazo más barato (single), no el más inteligente: el thinking cuesta 10–40× más por ganancia marginal de reward. Eco del colapso de EXP62 (lo barato gana cuando el mundo es fácil). Global: OpenAI 2.970 R/USD vs DeepSeek 1.702 R/USD (OpenAI más barato por llamada: US$0,000153 vs US$0,000346), pero por slice domina deepseek/single.

**Generalización (la parte que importa):** en el oráculo de 180 problemas frescos —datos que el router nunca vio— el ganador ex post por R/USD es deepseek/single en los 3 slices (44.523, 37.723, 2.874). La elección del router coincide 3/3 en held-out: **la regla generaliza.** Matiz honesto: en reward crudo, gsm8k lo gana cot (0,967 vs 0,633) — el router optimiza eficiencia, no accuracy cruda; es el objetivo pre-registrado. Caveat: el criterio 1 es casi tautológico (router y ganador ex post usan los mismos números); la señal real es el criterio 2, que pasó.

**Consecuencia de diseño:** nació el **registry de proveedores** (`alma_service/proveedores.yaml` + `registro.py`, 16/16 tests verdes): el único lugar donde el router mira para decidir, con metadata medida, failover por 401/403/404 con motivo y fecha, fail-closed sin proveedores, y cero secretos por construcción (test que lo verifica). No toca el servicio vivo (puerto 8471).

**En criollo:** el sistema ahora sabe elegir no solo el modo, sino también el proveedor más rendidor por dólar —y lo que eligió con pocos datos se confirmó con datos nuevos que nunca había visto. Es la pata que convierte al loop en producto: el respondedor de Mercado Libre entra como cliente #1 del router.

---

## 8. EXP64-skip — el skip carga peso, por el umbral justo

**Veredicto: LOAD-BEARING** (follow-up n=20 held-out del EXP64, mock US$0, 28/9). Efecto de QUITAR el skip (d = reg_sin_skip − reg_control):

- **Efecto medio: +6,55** — IC95 **[+2,19, +10,92]** (t=2,093, gl=19)
- Peor sin skip: **14/20** réplicas · mejor sin skip: 4/20 · empates: 2/20
- Rango de diffs: −11,0 a +23,0 (alta varianza entre réplicas)

Criterio pre-registrado: d̄ > 0 ✓ · IC95 no cruza el 0 ✓ · ≥14/20 ✓ (**exactamente 14/20** — el mínimo).

**Diagnóstico honesto:** pasa por el umbral justo. Una réplica que diera vuelta (13/20) y el veredicto habría sido "sin efecto detectable". Dicho sin anestesia. Pero el punto estimado es estable: EXP64 (n=5) había medido +6,00; este follow-up (n=20, seeds held-out) mide +6,55 — dos muestras independientes, mismo orden de magnitud. La varianza por réplica es alta (−11 a +23): en 4/20 réplicas quitar el skip MEJORA. El skip ayuda en media pero no siempre; su valor vive en la interacción con el régimen.

**Caveat de alcance:** mundo mock. Esto mide ahorro de costo de probe en un mundo sintético con regímenes limpios — no es evidencia de que el skip pague igual con modelos reales; eso lo diría un E3 con datos frescos.

**En criollo:** la pieza que salta el testeo cuando el sistema ya sabe la respuesta realmente ahorra — medido dos veces, con números parecidos. Pero pasó raspando el mínimo: una réplica más en contra y no se podía afirmar. Se conserva, sin declarar victoria definitiva.

---

## 9. EXP70 — piloto Claude, medición parcial

**Veredicto: MEDICIÓN PARCIAL** (28/9). El freno duro cortó la corrida en **63/72 pulls (87,5%)**. No se declara medición completa ni veredicto comparativo.

- Modelo: `claude-haiku-4-5-20251001`. Costo global medido: **US$0,001632/llamada** (63 llamadas).
- **Overshoot admitido:** gastado US$0,1028 vs freno US$0,10 → **+2,8%**. Causa: el freno se chequea antes de cada pull y un pull caro puede pasarlo; la regla de parada por proyección del pre-registro NO se aplicó durante la corrida en background. Miss de ejecución, no de diseño. Consta para no repetirlo.
- Pricing verificado en vivo: haiku-4-5 = $1/$5 por MTok, igual que el estimado. La diferencia de costo efectivo (~10,7× gpt-4o-mini por llamada vs ~7× estimado) viene de **verbosidad**: Claude genera más tokens de salida en cot/reflexion.
- Lecturas (no veredicto): en gsm8k y mmlu el patrón replica a los otros proveedores (cot/reflexion perfectos, single flojo en gsm8k 0,375, perfecto en mmlu 1,000). En mbpp (n=5, parcial), **0,000 en los 3 brazos**: la hipótesis "Claude programa mejor y puede dar vuelta el slice de código" NO se sostiene en este subset — la debilidad en código parece independiente del modelo. Con n=5 es evidencia débil, no refutación.
- Follow-ups pendientes de aprobación: completar los 9 pulls (~US$0,02, resume idempotente); réplica completa del oráculo (~US$1,20) no recomendada sin aprobación separada.

**En criollo:** medimos al tercer proveedor a medias —el freno cortó antes de terminar y encima nos pasamos 2,8% por un descuido en la regla de parada—. Lo que se alcanzó a medir dice que en código ningún modelo levanta cabeza, pero con tan pocos datos es una pista, no una conclusión.

---

## 10. EXP18 — FAIL global en 4/4 seeds (api real)

**Veredicto: FAIL global** (auditado 28/9). El test del flip real con oráculo completo (fases 12A, gpt-4o-mini vía VaultBackend):

| Seed | alma | mejor fija (cot) | diff |
|---|---|---|---|
| 1821 | 6,79 | 4,43 | +2,36 |
| 1822 | 6,11 | 5,02 | +1,09 |
| 1823 | 8,57 | 5,48 | +3,09 |
| 1824 | 5,97 | 4,74 | +1,23 |

**Patrón estructural, no mala suerte:** el seed 1824 acertó 9/10 bloques, pero el costo del probe supera el beneficio — el mismo patrón del EXP44. El loop detecta bien y pierde igual: explorar cuesta más de lo que rinde cuando la ventaja entre brazos es chica.

**Dos notas de disciplina:** (1) el seed 1822 "abortado sin veredicto" resultó tener veredicto completo y válido al auditarlo — **no se gastaron los US$0,10 del reintento** (habría sido ritual, y además con otra key violaría el pre-registro); (2) el seed 1824 murió dos veces por Connection refused en fase B y el reintento solo-fase-B reutilizó el oráculo idempotente con cero gasto nuevo.

**En criollo:** cuatro intentos con plata real, cuatro derrotas con el mismo diagnóstico: el sistema adivina bien qué modo usar, pero lo que gasta en averiguarlo es más de lo que gana usándolo. Cuando la diferencia entre modos es chica, el que no prueba nada y usa siempre el mejor promedio gana.

---

## 11. EXP20 — la selección sobrevive a errores correlacionados

**Veredicto: PASS** (mock US$0, 4 seeds 2021–2024). La refutación del PASS de EXP19: ¿la ventaja de la selección era un artefacto de la independencia de errores? Con errores correlacionados (latente gaussiana, rho=0,5; correlación binaria medida 0,31 — nivel realista para LLMs):

| Brazo | F1 | Llamadas | E (F1/llamadas×1000) |
|---|---|---|---|
| Enjambre CON probe | 0,5393 | 5112 | **0,1055** |
| Individual (azar) | 0,3352 | 5000 | 0,0670 |
| Voto ×7 | 0,3639 | 35000 | 0,0104 |

Diffs E_probe − E_individual por seed: +0,0535 / +0,0428 / +0,0548 / +0,0028 — siempre positivos, sin cambio de signo (regla de confiabilidad EXP16). El probe eligió al mejor agente (F) en **4/4 seeds**. Margen de eficiencia: 0,0385, **prácticamente idéntico** al de EXP19 (0,0386). La ventaja de la selección no se movió con la correlación.

**Lo que sí rompió la correlación fue el voto ingenuo:** su F1 crudo cayó 0,5164 → 0,3639. El voto vive de la diversidad de errores; con errores correlacionados, escalar sin selección pierde su ventaja de calidad Y mantiene su costo 7×. Esto endurece la tesis: **la selección es lo que vuelve eficiente al enjambre, y cada vez más cuando los agentes se parecen entre sí.**

Caveats: rho=0,5 es un nivel, no el espectro; los agentes son tablas fijas de TPR/TNR, no LLMs reales. Y un bug documentado: la primera corrida parametrizó mal `q` en label=0, se detectó por números absurdos, se corrigió y se re-corrió — solo la corrida corregida cuenta.

**En criollo:** intentamos romper el resultado anterior metiéndole el peor caso (que los agentes se equivoquen todos juntos, como pasa en la vida real) y no se rompió: elegir bien a quién escucharle sigue ganando por el mismo margen.

---

## 12. EXP11b — FAIL de diseño: el flip que no existía

**Veredicto: FAIL DE DISEÑO** (puerta offline, US$0,00 — la key no se tocó). EXP11 había dado FAIL pero con el test rengo (el flip no estacionario diseñado no se materializó). EXP11b debía re-testear con el flip VERIFICADO antes de correr. La puerta se ejecutó sobre el oráculo completo ya medido (1200 pulls, gpt-4o-mini): estrictamente más potente y costo cero.

Oráculo global (200 problemas): **cot 0,753 · single 0,442 · reflexion 0,581** — cot domina por +0,31. Intento 1 (GSM8K vs MMLU): cot gana en ambas mitades → no hay flip. Intento 2 (techo por single−cot): flip *nominal* (single gana por 0,059), pero 0,059 < SE del probe con 5 problemas (0,070) → **indetectable por la maquinaria**; y la partición se eligió sobre medias ruidosas (winner's curse: el margen real es plausiblemente ~0). **La puerta FALLA tras 2 intentos. No se corre el stream.**

**La honestidad incómoda de fondo:** no es solo que "el mundo no se movió" — es que **con estos brazos el mundo casi no puede moverse.** cot gana en 9 de 10 materias MMLU; solo 10/200 problemas tienen a single superando a cot por ≥0,1; reflexion supera a ambos en 4/200. El set {single, cot, reflexion} sobre gpt-4o-mini tiene un brazo dominante. Esto re-encuadra el FAIL de EXP11: la pregunta "¿se adapta cuando el mejor brazo cambia?" es **incontestable** con brazos donde uno domina siempre. Para cerrarla hay que rediseñar los brazos (reward con costo, o brazos = modelos distintos), no los problemas — y eso merece pre-registro propio.

**En criollo:** quisimos probar si el sistema se adapta cuando cambia el mejor modo, pero resulta que con estos modos el mejor casi nunca cambia. No se puede probar la adaptabilidad en un mundo que no varía — hay que cambiar los modos, no el test.

---

## 13. Lo que la serie refutó, lo que archivó, lo que sigue abierto

### Refutado (con números, vara intacta)
1. **La transferencia ciega** (EXP2, v1): el mapa manual eligió la familia equivocada en todos los folds; costo 3,7× el oráculo.
2. **El agnosticismo al modelo** (EXP62): la ventaja del loop era condicional al perfil de debilidad de gpt-4o-mini. Con deepseek-flash en mundo colapsado, el loop pierde 4,85 contra la fija obvia.
3. **El fix del minero** (EXP66): el ancla al probe empeora (5,92 vs 5,42) y la "derrota del warm" era ruido (0,44 ± 1,72).
4. **La selección como artefacto de independencia** (EXP20): la refutación fracasó — el margen sobrevive idéntico con rho=0,5.
5. **Brazos con flip real en el pool actual** (EXP11b): el flip no existe a resolución del probe; el set de brazos tiene un dominante estructural.

### Archivado (no se reabre sin evidencia nueva)
- **La vía del proveedor generativo** (EXP61): ni un prior con las medias VERDADERAS del oráculo supera al scaffold tuneado (+0,40, 3/5 en contra). Ningún LLM genera skills que mejoren al modelo — ni en prosa (fase 1: diferencia conductual 0,000) ni en parámetros. La fase 1b con key no se propone (regla mock-first).
- **La serie BTC EXP36–42:** 7 FAIL; a escala horaria manda el ruido — ninguna política adaptativa le gana a buy&hold de forma generalizable. La pregunta pasó de *qué regla* a *dónde*.
- **EXP44:** el mundo (feed real, 94 noticias) se mueve más rápido de lo que cualquier maquinaria con probe puede seguir; la exploración es puro costo. Lección de diseño permanente: el oráculo mock debe calibrarse a las categorías reales ANTES del pre-registro.
- **El veto permanente a auto-edición de código** fue revertido por decisión explícita (27/9 ~22:50) y reemplazado por la gobernanza de auto-adopción (§14). La línea roja original queda como historia, no como regla.

### Sigue abierto
1. **¿Hay mundos reales heterogéneos para un modelo fuerte?** (pregunta de EXP62). Si la respuesta es no, el loop solo agrega valor sobre modelos débiles.
2. **¿El skip paga con modelos reales?** EXP64-skip es mock; hace falta un E3 con datos frescos. El margen en la condición de conteo fue de una réplica.
3. **Calibración del E3** por benchmark (margen_min=2,0 está calibrado en el harness mock) y decisión de integración al servicio vivo — pendiente del usuario.
4. **Dónde corre 24/7 y tope mensual en US$** — las dos decisiones pendientes desde fase 2.
5. **Completar EXP70** (9 pulls, ~US$0,02) y decidir la réplica completa del oráculo en Claude (~US$1,20).

---

## 14. Gobernanza: "mejora a mis espaldas y avísame, pero no peor"

El 27/9 ~22:50, por decisión explícita del usuario, la gobernanza cambió: **el meta-loop auto-adopta mejoras sin esperar el "sí", pero solo ante mejora medida** — Δ_ho > 0 estricto, Δ_in ≥ 0, frenos sanos. Lo que mide igual o peor se rechaza, se registra con números y no se adopta. Nada de cambios laterales.

El **núcleo es intocable**: topes de gasto, la puerta de validación y la obligación de notificar. Si el loop pudiera silenciar sus avisos, el "avísame" no valdría nada — por eso el núcleo se protege con `NucleoProtegidoError` (raise + log + aviso), no con una promesa. Toda adopción es reversible y notificada; el digest dominical reporta las evoluciones auto-adoptadas.

La fase 2.3 (toda promoción esperaba el "sí" humano en staging) quedó superada por esta regla. La primera promoción bajo el régimen anterior fue el EXP68 ("vamos nomas").

**E3 — el tercer split ciego** (28/9, implementado y testeado 16/16 en mock, **no integrado al servicio vivo** a propósito): responde al caveat de que el split held-out participa en la puerta y hay presión de selección sobre el gate a lo largo de rondas. Regla: aceptar ssi min(Δ_in, Δ_ho, Δ_e3) ≥ 0 ∧ max > 0. El E3 es un **veto**, no un tercer obstáculo. Se exige cuando la superficie es maquinaria/núcleo, cuando el margen es fino (<2,0 puntos), o cuando el auditor lo pide; si se exige y no hay Δ_e3, fail-closed. La integración al promotor vivo requiere decisión del usuario: dónde corre el split ciego y con qué costo.

**En criollo:** el sistema ahora puede mejorarse solo cuando demuestra con números que mejoró —y te avisa cada vez—. Pero hay tres cosas que nunca puede tocar: cuánto puede gastar, las reglas que validan las mejoras, y la obligación de avisarte. Y hay un tercer examen sorpresa (E3) para las mejoras que pasan raspando.

---

## 15. Del laboratorio al producto: el router y el paquete único

Tres piezas de la serie ya son producto, no experimento:

1. **El router por reward/USD** (EXP69): regla validada en piloto y generalizada en held-out. El **registry de proveedores** es su base de datos viva: metadata medida por campaña, failover con motivo y fecha, fail-closed, cero secretos por construcción.
2. **El detector de heterogeneidad** (EXP68): integrado al servicio como meta-regla aditiva.
3. **El paquete único autogestionado** (diseño aprobado 27/9 ~18:56, `DISENO_PAQUETE_UNICO.md`): trazas unificadas del servicio → minero sobre operación real → validador con puerta de dos splits (+E3 donde aplique) → promotor con auto-adopción gobernada. Decisiones ya tomadas: toda promoción de código sigue la gobernanza del §14; alcance primero los 5 hiperparámetros del scaffold; fase 2.2 (trazas unificadas) primero.

**El cliente #1:** el respondedor de Mercado Libre. El router elige proveedor por eficiencia medida; el respondedor consume esa decisión. Es la primera vez que una pieza de ALMA tiene un usuario que no es el laboratorio.

**En criollo:** lo que empezó como experimentos para ver si el sistema aprende, ahora tiene tres piezas usables de verdad —y la primera que las va a usar en serio es la herramienta para vendedores de Mercado Libre—.

---

## 16. Próxima refutación

La agenda, en orden de honestidad (primero lo que más puede romper la tesis):

1. **Mundos heterogéneos para modelos fuertes.** Diseñar un benchmark donde el oráculo sea heterogéneo *para el mejor modelo disponible* (brazos con trade-off real: reward con costo, o brazos = modelos distintos). Si no existe, el techo de EXP62 es estructural y hay que decirlo.
2. **E3 con datos frescos para el skip.** Re-test del EXP64-skip fuera del mock, con el tercer split ciego, para cerrar si el skip paga con modelos reales.
3. **El detector en el mundo real.** EXP68 es mock; la validación que importa es sobre trazas del servicio (fase 2.2) con heterogeneidad real.
4. **Completar el mapa de proveedores.** Terminar EXP70 y sembrar el registry con celdas limpias; el router es tan bueno como sus mediciones.
5. **Las dos decisiones pendientes:** dónde corre 24/7 y el tope mensual en US$. Sin eso, el paquete único no sale del diseño.

---

## Apéndice: trazabilidad

| Experimento | Veredicto en disco |
|---|---|
| EXP62 | `resultados/exp62_veredicto.md` (+ `exp62_deepseek/`) |
| EXP66 | `integracion_fase21/resultados/exp66-minero-20260927/veredicto.md` |
| EXP67 | `integracion_fase21/resultados/exp67-benchmark-real-20260927/veredicto.md` |
| EXP68 | `integracion_fase21/resultados/exp68-heterogeneidad-20260927/veredicto.md` |
| EXP69 | `integracion_fase21/resultados/exp69-router-proveedores-20260927/veredicto.md` |
| EXP64-skip | `integracion_fase21/resultados/exp64-ablacion-skip-20260928/veredicto.md` |
| EXP70 | `integracion_fase21/resultados/exp70-claude-pilot-20260928/veredicto.md` |
| EXP18 | `resultados/exp18-20260926/seed182{1,2,3,4}/` + `seed1822/auditoria-20260928.md` |
| EXP20 | `resultados/exp20-20260926/veredictos-exp20.md` |
| EXP11b | `resultados/exp11b_veredicto.md` |
| Gobernanza | `test_gobernanza_auto_adopcion.py`, `integracion_fase21/resultados/e3-tercer-split-20260928/E3.md` |
| Registry | `integracion_fase21/alma_service/proveedores.yaml` |
| Paquete único | `integracion_fase21/DISENO_PAQUETE_UNICO.md` |
| Informe v1 (EXP1–4) | `../informe-alma-cuatro-experimentos/informe-alma-cuatro-experimentos.pdf` |

*La vara pre-registrada es sagrada. Los FAILs se aceptan sin moverla. La key solo se mueve con números antes.*
