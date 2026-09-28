# ALMA-EXP21 — Veredicto: NO CONFIABLE (la revancha no se consumó)

**Pregunta:** ¿la selección por probe repara la transferencia? (EXP2/EXP3: ALMA pidió
prestada la experiencia al vecino equivocado.)

**Diseño:** 5 clases conocidas con fingerprint; trampa C1 = la más cercana a la clase
nueva N (d=0.04) pero con mejor brazo distinto (single vs cot). Tres estrategias en
N, 120 pulls, 4 seeds [2121–2124], 100% mock, US$0.
- (a) vecino manual (baseline EXP2): explota single ×120.
- (b) probe-transfer: 8 pulls × {single, cot, reflexion}, elige por media, explota ×96.
- (c) desde cero: Thompson sampling ×120.

**Números (regret medio):** probe-transfer **10,0** · vecino manual **13,5** · desde cero **7,5**.
Diffs probe−vecino por seed: **−17, +14, +2, −13** → cambio de signo → **NO CONFIABLE**
(regla EXP16, pre-registrada). `pasa: false` de todos modos (10,0 > 7,5).

**Detalle por seed:**
| seed | probe eligió | regret probe | regret vecino | regret cero |
|------|--------------|--------------|---------------|-------------|
| 2121 | cot ✓ | 4,0 | 21,0 | 2,0 |
| 2122 | reflexion ✗ | 28,0 | 14,0 | 16,0 |
| 2123 | cot ✓ | 8,0 | 6,0 | 4,0 |
| 2124 | cot ✓ | 0,0 | 13,0 | 8,0 |

**Lectura honesta:**
1. La trampa funcionó 4/4: el vecino manual cayó siempre en C1 (single, el brazo
   equivocado). El modo de fallo de EXP2 quedó fielmente reconstruido — el setup es válido.
2. El probe acertó 3/4 veces, pero la 4ª fue catastrófica: 8 pulls de suerte con
   reflexion (el peor brazo) → 96 pulls de explotación ciega → regret 28. Un solo
   error de selección borró las tres victorias.
3. Lo incómodo: **empezar de cero con Thompson (7,5) le ganó al probe-transfer (10,0)
   en media.** La exploración adaptativa sin compromiso duro supera al probe chico con
   compromiso de 96 pulls, en este régimen.
4. El mapa de la frontera: en EXP19/20 el probe funcionó porque los gaps eran grandes
   (0,85 vs 0,60, 16 pulls). Acá el gap es 0,12 con 8 pulls → el ruido del probe
   domina. La selección por probe funciona cuando la señal supera al ruido del probe;
   con candidatos cercanos y presupuesto chico, medir no le gana a adaptarse.
   Eco directo de EXP6: los errores del probe no se arreglan con pocos pulls.
5. Bug detectado y corregido ANTES de correr (documentado en el script): el regret del
   probe sorteaba los pulls dos veces; se unificó para que el regret incluya los mismos
   pulls que informaron la decisión. Solo la corrida corregida cuenta.

**Comparación explícita vs EXP2:** EXP2 FAIL (reward_ratio 0,97, cost_ratio 3,72×,
2/5 clases) por transferir al vecino equivocado. EXP21 reconstruyó ese fallo y
preguntó si la selección lo repara: **no, no de forma confiable.** La transferencia
sigue siendo la herida abierta de ALMA.

**Puerta que esto abre (no pre-registrada, solo nota):** EXP7 mostró que el re-probe
continuo corrige errores sistemáticos del probe. Un EXP22 natural: probe-transfer CON
re-probe (sin compromiso duro de 96 pulls).
