# Adenda 2 al pre-registro del generador — completación de la regla de reemplazo por descenso de la tabla gratuita

**Fecha:** 2026-10-16 · **Documentos madre:**
`preregistro-generador-sakana-2026-10-16.md` +
`adenda-preregistro-generador-2026-10-16.md` (ambos siguen
vigentes en todo lo que esta adenda no toca). **Origen:** la
corrida y su reintento quedaron NO REALIZADAS por bloqueo de
plataforma — el modelo designado por la regla de reemplazo del
§4, `xingchen-agi/xing4.0-29b-a4b:free` (paso 3), devolvió tres
HTTP 429 en el intento de la tarde (~22:24 UTC) y otros tres en
el reintento (~22:37–22:42 UTC): bloqueo **sostenido** del
designado, verificado con el protocolo de sondas en dos intentos
separados por ~40 minutos (evidencia en
`data_corrida_generador_2026-10-16/` y
`data_corrida_generador_reintento_2026-10-16/`).
**Autorización:** Alejandro, 16/10/2026 («busquemos la forma»).
**Presupuesto: US$0**, sin cambios — esta completación solo
desciende dentro del tier gratuito; no habilita ninguna ruta
paga ni ninguna sustitución por fuera de la tabla gratuita.

**Orden obligatorio declarado:** (A) esta adenda escrita y
commiteada → (B) generación con el modelo designado por la
completación → (C) la corrida tal cual el pre-registro y la
adenda 1. Ninguna generación precede a este documento.

---

## 1. La completación (qué cambia y qué no)

La regla de reemplazo del §4 del pre-registro madre se agota en
su paso (3): designa el primer `*:free` de chat no-reasoning del
catálogo y no declara qué hacer si ese modelo está
**sostenidamente bloqueado** (429 repetido en dos intentos con
sondas). Esta adenda completa la regla, sin tocar sus pasos
(1)–(5):

> **Paso (6) — descenso por la tabla gratuita:** si el modelo
> designado por los pasos (1)–(3) devuelve bloqueo sostenido
> (429 en el intento real y en las sondas, en dos intentos
> separados), la designación desciende por la tabla de modelos
> `*:free` de chat no-reasoning **en el orden del catálogo**,
> aplicando el mismo criterio de clasificación ya asentado en
> los snapshots de ambos intentos («reasoning» = diseñado o
> comercializado como modelo de razonamiento según
> id/nombre/descripción del catálogo; la mera presencia del
> parámetro API `reasoning` en `supported_parameters` no
> clasifica, porque lo lista casi todo el catálogo; excluido por
> no-chat el guardrail `nemotron-3.5-content-safety`). A cada
> candidato del descenso se le hace **una sonda diagnóstica
> mínima** («Respondé solo: OK», tokens mínimos, temperatura 0).
> **El primer modelo que responde a la sonda queda designado**
> y genera la tanda. Máximo 6 sondas de diagnóstico. Si ningún
> modelo responde, la corrida queda NO REALIZADA por bloqueo de
> plataforma (§7 del pre-registro madre) y se frena: no se
> genera, no se paga, no se sustituye por fuera de la tabla.

Nota de procedencia de la tabla: el descenso se hace sobre el
snapshot del catálogo consultado sin costo hoy (467 modelos,
16 `:free`, idéntico en lo relevante a los snapshots de ambos
intentos previos), que queda en la carpeta de evidencia de esta
corrida. El modelo ya bloqueado (`xing4.0-29b-a4b:free`) no se
vuelve a sondar: su 429 sostenido está probado dos veces hoy.

## 2. Sondas realizadas (asentadas antes de generar)

Carpeta de evidencia: `data_corrida_generador_forma_2026-10-16/`
(snapshot del catálogo + `sondas.jsonl` con hora UTC y resultado
de cada sonda).

| # | modelo (orden del catálogo) | hora UTC | resultado |
|---|------------------------------|----------|-----------|
| 1 | `nvidia/nemotron-3.5-super-vl:free` | 2026-10-16T22:48:45Z | **responde** (HTTP 200, texto devuelto) |

La primera sonda respondió → el descenso se detuvo ahí, como la
completación declara. **Modelo designado por completación de la
regla: `nvidia/nemotron-3.5-super-vl:free`.** Ficha del catálogo
de hoy: modelo multimodal de mezcla de expertos de NVIDIA (texto
+ imagen + video → texto; 12B activos de 120B); su descripción
**no** lo presenta como modelo de razonamiento (no clasifica
como «reasoning» bajo el criterio asentado), y soporta
`structured_outputs`/`response_format`. Que obedezca el formato
estricto de la tanda es exactamente lo que el protocolo de
validación mecánica y los llamados con feedback están para
medir: si no lo obedece, el desenlace declarado es «tanda
insuficiente» (§7), no un error a tapar.

## 3. Invocación declarada

`correr_generador.py` ya admite el modelo por parámetro, sin
tocar código:

```
python3 correr_generador.py --generar --modelo "nvidia/nemotron-3.5-super-vl:free"
python3 correr_generador.py --tanda <archivo de tanda congelada>
```

## 4. Lo que NO cambia

Todo el resto del protocolo queda idéntico al pre-registro madre
y la adenda 1: máximo **3 llamados** de generación, temperatura
**0,7**, `max_tokens` 4000, cortafuegos del proponente (solo
resultados train en el prompt), tanda **objetivo 14 / mínimo 8**
para lanzar, validación mecánica y piso de diversidad, puerta
**5,4781** totales con panel **18/12** (train [400..417],
held-out [600..611], E3 [500,501]), validador congelado, panel
de confirmación [5000..5017]/[5100..5111] que solo se consume si
hay auto-adopción (la ganancia oficial es el Δ de confirmación;
el de puerta queda como «Δ de selección»), contabilidad del
freno según §8 del pre-registro madre (sin adopción en corrida
evaluada → racha 2/3; con adopción → 0; si la corrida no se
lanza, la racha no se mueve), destino de la tanda como población
inicial del crossover, y la prohibición de segunda tanda bajo
este papel: lo que salga, queda asentado.
