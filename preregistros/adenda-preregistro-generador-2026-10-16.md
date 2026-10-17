# Adenda al pre-registro del generador — tres ajustes del estudio externo

**Fecha:** 2026-10-16 · **Documento madre:**
`preregistro-generador-sakana-2026-10-16.md` (sigue vigente en
todo lo que esta adenda no toca). **Origen:** auditoría web externa
del 16/10/2026 sobre este diseño (análisis adaptativo y reutilización
de holdouts — Dwork et al.; maldición del ganador en selección de
candidatos; práctica de evaluación de agentes 2025–2026).
**Autorización:** Alejandro, «Corre» del 16/10/2026 — la corrida del
generador se ejecuta con esta adenda ya escrita y commiteada.
**Presupuesto: US$0**, sin cambios.

**Orden obligatorio declarado:** (A) esta adenda escrita y
commiteada → (B) screening factorial (diagnóstico, no veta) →
(C) la corrida del generador tal cual el pre-registro. Ninguna
ejecución de B o C precede a este documento.

---

## Ajuste 1 — Cortafuegos del proponente

**Regla:** el prompt del generador solo puede contener la
configuración base, resultados de la etapa **train** (Δ_train y
keep/revert por propuesta) y categorías de fracaso. **Nunca**
puntajes ni resultados de held-out o E3 de ninguna propuesta,
pasada o futura. Motivo: un split ciego cuyos resultados lee el
proponente deja de ser ciego — cada puntaje que el generador ve
entrena su próxima tanda.

**Estado previo, verificado en el código y el ledger (hoy):**
la extracción (`historial_desde_ledger`) ya proyectaba solo campos
de etapa train — de cada `audit_propuesta` leía únicamente
`clave/anterior/nuevo/delta_in/aceptado`, y los resultados de la
puerta viven en eventos que jamás abría (`audit_propuesta_e3`,
`corrida_finalizada`). Ningún número held-out o E3 llegó nunca al
prompt por esa vía. **Pero** el historial incluía un evento
heredado de la etapa puerta: la corrida seed 23 (código del 28/9)
registró la auditoría de su candidato final como `audit_propuesta`
con `delta_ho: 0,0` poblado y motivo de puerta («sin mejora
estricta»). Su fila entraba al historial del proponente con un
veredicto de puerta disfrazado de fila train.

**Cambio aplicado (estructural, no de buena voluntad):**
`historial_desde_ledger` ahora acepta solo eventos
`audit_propuesta` **sin carga de puerta** (`delta_ho is None` y sin
clave `delta_e3`); un evento contaminado se **excluye entero** del
historial en vez de leerse parcialmente. Efecto medido sobre el
ledger real: el historial pasa de 11 a 10 filas — sale el evento
heredado de la seed 23; la tabla de la corrida 87859 (las 8
mutaciones medidas) queda intacta, 8/8.

**Prueba (en `test_generador_candidatos.py`, sección 2b):** un
ledger envenenado con puntajes plantados — `delta_ho` en un
`audit_propuesta`, un `audit_propuesta_e3` completo con
`delta_ho/delta_e3/e3_base/e3_cand`, el `corrida_finalizada` con
`delta_heldout`, y textos libres con números plantados — demuestra
que **ningún** valor plantado llega al historial ni al prompt, que
las filas solo traen los campos train declarados
(`CAMPOS_TRAIN`), y que la fila train limpia sí llega. Suite del
generador tras el cambio: **77/77 checks** (57 previos + 20 del
cortafuegos).

---

## Ajuste 2 — Panel de confirmación (la ganancia oficial se mide en panel fresco)

**Regla:** si la corrida produce una **auto-adopción**, la ganancia
que se asienta como **oficial** no es el Δ que pasó la puerta (ese
número está sesgado hacia arriba por selección — maldición del
ganador: es el máximo de una tanda, elegido por ser grande). La
ganancia oficial es el Δ medido **post-adopción** en un panel de
confirmación **fresco**, contra el incumbente anterior, y se asienta
en el ledger junto al Δ de puerta, que queda registrado como
**«Δ de selección»**.

**Panel declarado (antes de correr):** espejo del panel de puerta
en tamaño —

- **confirmación-train: réplicas [5000..5017]** (18)
- **confirmación-held-out: réplicas [5100..5111]** (12)

E3 no forma parte del panel de confirmación: el tercer split sigue
siendo el de la puerta ([500,501], intacto).

**Evidencia de virginidad (barrido amplio, hoy, criterio
estructural del §5.6 de la recalibración v3):** 379 archivos
JSON/JSONL del árbol completo, 377 parseados; los 2 no parseables
(`resultados/exp35-20260927/report.json`,
`producto/router-puro/mvp/shadow/mediciones.jsonl`) inspeccionados
por texto con búsqueda de ids con borde de palabra: ninguna
aparición como id (las coincidencias de subcadena resultaron ser
partes de floats y de marcas de tiempo ISO). Para los rangos
declarados: **cero hits de cualquier categoría** — ni como réplicas,
ni como seeds, ni en secuencias de enteros. (Los rangos alternativos
[700..717]/[800..811] se descartaron: solo colisionaban con índices
de ítems GSM8K de `data_exp11/seleccion.json` y
`data_exp12/seleccion.json` — maquinaria ajena, la misma clase de
hit declarada en la v3 — pero para un panel de confirmación se
eligen los rangos sin ninguna colisión.)

**Protocolo de medición (solo si hay auto-adopción):** terminada la
corrida, se evalúan el incumbente anterior (`scaffold_anterior` de
la corrida) y el scaffold adoptado sobre ambos paneles de
confirmación con el validador congelado (`MetaLoop._evaluar`):
Δ_conf_train = media(incumbente) − media(adoptado) en
[5000..5017]; Δ_conf_heldout análogo en [5100..5111]. Se asienta un
evento `confirmacion_adopcion` en el ledger (vía el append con
cadena de hash del propio meta-loop) con: Δ de selección (los
`delta_in/delta_ho` de la puerta), Δ de confirmación por split, y
las medias de ambos paneles. La ganancia oficial reportada es la
de confirmación (ambos splits, con su máximo como titular, espejo
del estadístico de la puerta).

**Si no hay auto-adopción, el panel NO se consume:** nadie lo
evalúa, y los rangos quedan declarados y vírgenes para la próxima
corrida que los necesite. El caso «banda» del piso de ruido (la
puerta acepta pero no auto-adopta) no es adopción a estos efectos:
no consume el panel.

---

## Ajuste 3 — Screening factorial (sonda diagnóstica previa; interpreta, no veta)

**Motivo:** la lectura «la base es un óptimo local» descansa sobre
8 mutaciones de un parámetro y un solo tamaño de paso: eso no
distingue óptimo local de pasos chicos, ni prueba que existan las
interacciones que el generador fue construido a explotar. Antes de
la corrida, una sonda factorial mide directamente si hay efectos
principales e interacciones de a pares en este paisaje.

**Diseño declarado:** factorial fraccionado **2^(5−1)**,
resolución V, generador **E = A·B·C·D**, sobre los 5 parámetros del
scaffold, con niveles extremos del espacio declarado (SPACES):

| factor | parámetro | nivel − | nivel + |
|--------|-----------|---------|---------|
| A | decay | 0.25 | 0.75 |
| B | gate_margin | 0.0 | 0.1 |
| C | n0 | 1 | 4 |
| D | umbral_base | 1 | 3 |
| E | umbral_divisor | 2 | 6 |

16 configuraciones del diseño + **punto central**
{decay 0.5, gate_margin 0.05, n0 2, umbral_base 2, umbral_divisor 4}
+ el **incumbente** como referencia = **18 evaluaciones**.

**Medición:** cada configuración se evalúa con el validador
congelado (`MetaLoop._evaluar`, sin tocarlo) sobre el panel train
cableado [400..417]. Respuesta: regret medio en totales (menor =
mejor). Efectos por contrastes sobre las 16 del diseño:
efecto = media(y | nivel +) − media(y | nivel −); un efecto
negativo reduce el regret (dirección de mejora). Incertidumbre:
varianza agrupada intra-configuración de las réplicas de las 16
configuraciones; SE(efecto) = √(s²_agrupada · 4/(16·18)) — fórmula
de réplicas independientes, **conservadora** bajo números aleatorios
comunes (la correlación pareada solo puede achicar el error real).
**Criterio declarado: un efecto es «detectable» si
|efecto| > 2·SE.** Aliasing de la resolución V, declarado: efectos
principales aliasados con interacciones de 4 factores; interacciones
de a pares, con las de a 3 — la lectura estándar es que los alias
altos son despreciables frente a los bajos.

**Veredicto que se asienta:** si ≥ 1 interacción de a pares es
detectable según el criterio («hay interacciones detectables») o
ninguna lo es, con la tabla completa de efectos (principales y de
a pares) y sus SE. **El screening NO es puerta de la corrida:** la
corrida del generador procede igual en ambos casos, y el informe
final interpreta la tanda a su luz (si no hay interacciones y la
tanda tampoco encuentra nada, la conclusión «óptimo local» gana
evidencia real; si las hay y la tanda las explota, también).

---

## Contabilidad y cierre de la adenda

- El freno de estancamiento se rige por el pre-registro madre (§8):
  la corrida de la tanda cuenta una vez; el screening **no** es una
  corrida del meta-loop y no mueve la racha.
- Todo lo demás del pre-registro madre queda **sin cambios**: tanda
  objetivo 14 / mínimo 8, modelo y regla de reemplazo, temperatura
  0.7, máximo 3 llamados, criterios de éxito / señal parcial /
  fracaso informativo / tanda insuficiente / bloqueo de plataforma,
  destino de la tanda, fronteras (piso 5,4781, panel 18/12 + E3,
  validador congelado: intocables).
- Los resultados del screening y de la corrida se asientan en un
  documento de resultados propio, con la tanda congelada, el ledger
  verificado y las suites de gobernanza al cierre.
