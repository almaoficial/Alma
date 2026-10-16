# EXP82 — Réplica de EXP76 sobre descripciones de tools: ¿la doctrina de la interfaz se sostiene fuera de las skills?

Corrida del 12/10/2026, mock US$0. Pre-registro: `~/workspace/alma-prototype/metaloop_preregistro_exp82.json` (escrito y congelado antes de correr). Runner: `~/workspace/alma-prototype/run_exp82.py`. Resultados crudos: `~/workspace/alma-prototype/data_exp82/resultados_exp82.json`.

## 1. La pregunta

C04 («el toolset como superficie de decisión», idea 3) propuso verificar en casa lo que su §3 afirma de la literatura: **la descripción de una tool es su interfaz** — lo único que el agente que elige ve antes de llamarla — y EXP76 ya lo había medido para skills (interfaz clara Δ_down = +0,3636 adoptada; rígida −0,4145 rechazada). EXP82 pregunta si esa doctrina es una propiedad de las skills o de **cualquier interfaz que un agente lee para decidir**: se toma la misma puerta, el mismo implementador mock y la misma batería, y se cambia solo la superficie — descripciones de tools reales del prototipo.

## 2. Protocolo (réplica fiel de EXP76)

- **La puerta**: `PuertaHandoff` de `alma_service/handoff.py`, sin modificar. Regla: Δ_down > 0 ∧ Δ_ref ≥ 0 («pero no peor»).
- **El implementador**: el mock de EXP76 — 3 implementadores frescos, 40 tareas downstream + 40 de referencia, comparación pareada. Solo ve nombre, descripción y firma de la tarjeta; la interna nunca llega (propiedad verificada en la corrida y en los tests: variar el cuerpo no mueve ningún score).
- **Los brazos**: por cada tool, base = descripción **vieja real** (primera línea del docstring del módulo, extraída por AST — hay un test que lo garantiza contra el código vivo) y candidata = descripción **nueva** reescrita con la doctrina (qué hace + «Ejemplo:» concreto + cuándo usarla + cuándo NO + salida declarada; entradas en la firma). `ayuda`/`rigidez` — propiedades de la tool, no del texto — quedan constantes entre brazos: el Δ mide descripción, no capacidad.
- **Semillas nuevas para EXP82** (tareas 8201/8202; implementadores 7610+k, fijos en handoff.py); baseline sin tool idéntico entre brazos, chequeado por tool.
- **Sin adopciones reales**: la «adopción» es sobre el texto dentro del experimento. `gate.py`, `metaloop.py` y `handoff.py` no se tocaron (los diffs que el árbol de trabajo ya traía en gate/metaloop son del cableado del piso de ruido del 11/10, no de esta corrida).

### Las 3 tools (funciones distintas del prototipo)

| Tool | Entrada real | Descripción vieja (docstring, línea 1) | q vieja |
|---|---|---|---|
| `juez_barato` | `JuezHeuristico.__call__(salida, contexto)` — evaluación | «El juez del evaluador barato — la "lámpara" del enchufe (idea 1, parte 2).» | 0,80 |
| `presupuesto` | `PresupuestoFase2.autorizar(bucket, costo_estimado_usd)` — control de gasto | «Presupuesto fase 2 — topes duros por bucket, modo barato por default.» | 0,80 |
| `trazas` | `EventLog.asentar_decision(...)` — observabilidad | «Trazas unificadas — event log estructurado del servicio (fase 2.2).» | 0,40 |

Las descripciones nuevas (texto completo en el pre-registro): las tres declaran qué hacen, traen un «Ejemplo:» ejecutable, dicen cuándo usarlas y cuándo NO («NO detecta errores fluidos», «NO registra gasto ya hecho», «NO trazas del asistente») y cierran con la salida («Out: bool/id»). La firma de `trazas` es la real, de 10 parámetros: cuesta −0,20 de q en **ambos** brazos — la réplica no la maquilla, porque el experimento cambia descripciones, no firmas.

## 3. Resultados

| Tool | q vieja → nueva | Δ_down | Δ_ref | Puerta |
|---|---|---|---|---|
| `juez_barato` | 0,80 → 1,00 | **+0,0892** | +0,1053 | ADOPTA nueva |
| `presupuesto` | 0,80 → 1,00 | **+0,1416** | +0,1412 | ADOPTA nueva |
| `trazas` | 0,40 → 0,60 | **+0,1006** | +0,1086 | ADOPTA nueva |

Contra el criterio pre-registrado, punto por punto: puerta adopta la nueva en ≥2 de 3 → **3 de 3**. Ninguna empeora (Δ_down ≥ 0 en las 3) → cumple. q_nueva > q_vieja con los valores declarados → cumple exacto (0,80→1,00; 0,80→1,00; 0,40→0,60). Solo-ve-la-interfaz → OK. Baselines pareados idénticos → OK en las 3. Tests: **EXP82 43/43, EXP76 31/31, en verde**.

**Veredicto contra el pre-registro: PASS.**

## 4. Qué significa para la doctrina de C04

**Confirmada — dentro de los límites epistémicos del instrumento, y con una fricción documentada que la matiza.**

1. **La doctrina viaja de skills a tools.** El mismo Δq (+0,20) producido solo por reescribir el texto de la interfaz movió el downstream en las 3 tools y pasó la misma puerta que en EXP76 adoptó/rechazó skills. La descripción-como-interfaz no es una propiedad del formato SKILL.md: es una propiedad de cualquier superficie que un agente lee para decidir — que es exactamente la tesis de C04 §1.
2. **El tamaño del efecto es menor que el titular de EXP76, y eso es consistente, no una debilidad del resultado.** EXP76 comparaba contra *nada* (Δq de 0 a 1,0 → +0,3636). EXP82 compara descripción mala contra buena (Δq +0,20) y obtiene +0,09 a +0,14: el instrumento responde de forma aproximadamente proporcional a Δq y a cuánto la tool puede ayudar/dañar (ayuda+rigidez). `presupuesto` (0,95) > `juez_barato` (0,90) en Δ_down; `trazas` (0,55) quedó en el medio por el término de pasos (al subir q, la rigidez cobra menos pasos extra). Reescribir descripciones de tools que ya existen vale menos que adoptar una skill clara desde cero — pero vale positivo y medible en las tres.
3. **La fricción (pre-registrada como observación de diseño, descubierta en calibración antes de correr): la versión larga de la doctrina es invisible para el instrumento de la casa.** Los primeros borradores, completos según la guía de Anthropic que cita C04 §3.1 (3–4 oraciones, 149–162 caracteres, con ejemplo y exclusiones), midieron **Δq = 0,00**: el bono por «Ejemplo:» (+0,20) queda cancelado con exactitud por la penalidad de largo (>140 caracteres) de `claridad_interfaz`. Las descripciones que pasaron la puerta cumplen toda la doctrina en estilo telegráfico (134–136 caracteres). Lectura honesta: o la banda de 140 caracteres del instrumento propio es demasiado angosta para la doctrina que la literatura recomienda, o la doctrina larga tiene un costo de superficie que el instrumento sí está capturando a su manera (C04 §2.3: cada caracter de definición se paga por turno). EXP82 no resuelve esa tensión; la deja medida y escrita, que es más de lo que había ayer.
4. **Lo que EXP82 no prueba.** El implementador es un instrumento calibrado que lee rasgos de superficie (presencia de ejemplo, tamaño de firma, banda de largo), no un LLM eligiendo tools de verdad: no puede distinguir una descripción con «cuándo NO» semánticamente correcto de uno vacío con el mismo formato. El PASS dice: *la doctrina de la casa, operacionalizada, es consistente al portarla de skills a tools* — el mismo estatuto epistémico que EXP76. La evidencia semántica (un modelo real eligiendo entre descripciones viejas y nuevas) sería otro experimento, de los que requieren pregunta abierta y presupuesto aprobado; este mock no la reemplaza ni la recomienda por sí solo.
5. **La palanca que EXP82 no tocó y C04 sí señala**: la firma de `trazas` (10 parámetros, −0,20 de q en ambos brazos) es el techo de esa tool en el instrumento — ninguna descripción la levanta por encima de 0,60 sin consolidar parámetros (C04 §5.3). Queda como el próximo candidato natural si algún día se mide consolidación de firmas con la misma puerta.

## Recibos

- Pre-registro: `~/workspace/alma-prototype/metaloop_preregistro_exp82.json` (hipótesis, tools, descripciones vieja/nueva, q declarados, criterio PASS/FAIL, observación de diseño — todo anterior a la corrida).
- Runner: `~/workspace/alma-prototype/run_exp82.py`; tests: `~/workspace/alma-prototype/test_exp82_descripciones.py` (43/43) y `test_exp76_handoff.py` (31/31, sin regresión).
- Números crudos: `~/workspace/alma-prototype/data_exp82/resultados_exp82.json`.
- Costo: US$0. Núcleo protegido sin modificar por esta corrida.
