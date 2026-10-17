# Adenda 3 al pre-registro del generador — excepción única de ruta paga (mistral-nemo)

**Fecha:** 2026-10-16 · **Documentos madre:**
`preregistro-generador-sakana-2026-10-16.md` +
`adenda-preregistro-generador-2026-10-16.md` (commit `79208b6`) +
`adenda2-preregistro-generador-2026-10-16.md` (commit `16f81c0`)
— los tres siguen vigentes en todo lo que esta adenda no toca.
**Origen:** los tres movimientos previos del día quedaron sin
corrida: la corrida y su reintento, NO REALIZADAS por bloqueo
de plataforma (429 sostenido del designado gratuito); la forma
buscada (adenda 2), con la **generación ejecutada** pero la
tanda **insuficiente** — el único gratuito que respondió
(`nvidia/nemotron-3.5-super-vl:free`) no sostuvo el formato
(0/14 válidos, 3× `respuesta_no_parseable`). El informe de ese
movimiento (`resultados-corrida-generador-forma-2026-10-16.md`,
§6) dejó tres rutas con precio puesto para Alejandro; él eligió
la (b).
**Autorización:** Alejandro, 16/10/2026 — «sí» explícito a la
opción **«Nemo pago: US$0,0004 con papel nuevo»**, con el costo
declarado antes de elegir.
**Presupuesto: excepción dura de hasta US$0,01** (ver §2) —
reemplaza al «US$0» solo para esta corrida y solo en lo que
esta adenda declara.

**Orden obligatorio declarado:** (A) esta adenda escrita y
commiteada → (B) generación con mistral-nemo →
(C) la corrida tal cual el pre-registro y las adendas 1–2.
Ningún llamado pago precede a este documento.

---

## 1. La excepción (qué cambia)

El §4, paso (5), del pre-registro madre prohíbe sustituir por un
modelo pago bajo ese papel, y el §7 trata la ruta paga como no
habilitada. Esta adenda declara una **excepción única** a esa
prohibición, con alcance cerrado:

- **Modelo:** `mistralai/mistral-nemo` (OpenRouter, pago).
  Motivo asentado, no opinado: es el modelo que este sistema ya
  midió obedeciendo formatos estrictos — **28/30 veredictos
  utilizables** en la batería de juez de EXP-JUEZ-001, contra
  17/30 de la heurística y el 0/30 del tier gratuito de su
  momento. La falla que frenó los tres movimientos de hoy no
  fue de criterio: fue de formato (y antes, de plataforma).
- **Precio verificado hoy** (snapshot del catálogo consultado
  sin costo, 2026-10-16 ~23:12 UTC, 467 modelos; en la carpeta
  de evidencia de esta corrida): **US$0,029 por millón de
  tokens de prompt · US$0,03 por millón de tokens de salida**.
- **Alcance temporal:** la excepción cubre **una** generación
  (el protocolo de hasta 3 llamados del §4) para **esta**
  corrida. Cumplida o agotada la tanda, la excepción muere: no
  habilita segundas tandas pagas, ni otros modelos pagos, ni
  ninguna corrida futura. Cualquier nuevo gasto requiere papel
  nuevo y «sí» nuevo.

## 2. Presupuesto duro y medición del costo

- **Máximo 3 llamados de generación** — el protocolo del §4,
  sin cambios: el 1º pide la tanda completa; los siguientes
  reciben motivos de descarte y aceptados, y piden solo los que
  faltan.
- **Tope total: US$0,01.** La estimación de peor caso con el
  prompt real de la tanda (~1.000 tokens el mayor) y el tope de
  salida declarado (`max_tokens` 4000) es
  3 × (1.000 × 0,029 + 4.000 × 0,03) / 1.000.000 ≈ **US$0,0004**.
  Con el protocolo declarado, el tope es **estructuralmente
  inalcanzable** (habría que multiplicar por ~20 el consumo
  máximo posible por llamado): cualquier llamado por fuera del
  protocolo está prohibido por el papel madre, con tope o sin
  tope. Si aun así el costo real asentado se acercara al tope,
  la generación se frena y el hecho se asienta como resultado.
- **Medición:** el costo real se calcula por llamado desde el
  **uso que devuelve OpenRouter** (tokens de prompt y de salida
  de cada respuesta, registrados por la ruta `or_chat.py` en su
  ledger de uso) costeado al precio del catálogo del día (§1),
  y se asienta por llamado y en total en el informe de la
  corrida y en la carpeta de evidencia
  (`data_corrida_generador_nemo_2026-10-16/`).

## 3. Lo que NO cambia

Todo el resto del protocolo queda idéntico al pre-registro madre
y las adendas 1–2:

- **Temperatura 0,7**, `max_tokens` 4000, el mismo prompt (config
  base, SPACES, tabla medida de fracasos de train, reglas duras,
  formato JSON) y el **cortafuegos del proponente** (adenda 1:
  solo resultados de etapa train llegan al prompt; held-out y
  E3, nunca).
- **Tanda objetivo 14 / mínimo 8** para lanzar, validación
  mecánica y piso de diversidad sin cambios; la tanda completa
  se congela a disco **antes** de evaluar a nadie (§6).
- **Puerta 5,4781 totales**, panel **18/12** (train [400..417],
  held-out [600..611], E3 [500,501]), validador congelado:
  intocables.
- **Panel de confirmación** [5000..5017]/[5100..5111] (adenda
  1): solo se consume si hay auto-adopción; la ganancia oficial
  es el Δ de confirmación y el de puerta queda como «Δ de
  selección». Sin adopción, el panel no se toca y sigue virgen.
- **Contabilidad del freno** (§8 del papel madre): corrida
  evaluada sin adopción → racha **1/3 → 2/3**; con adopción →
  0; si la corrida no se lanza (tanda insuficiente también con
  nemo), la racha no se mueve y el desenlace es el «tanda
  insuficiente» del §7.
- **Destino de la tanda:** adoptada o no, población inicial
  para el futuro crossover (que sigue requiriendo su propia
  autorización).

## 4. Sin circularidad, declarado

nemo **propone**; no juzga nada en esta corrida. El Δ de la
puerta lo produce el simulador determinista con el validador
congelado, como siempre: el modelo pago no toca gate, panel,
piso ni validador, y su historial como juez medido (28/30) se
cita solo como evidencia de obediencia de formato — la calidad
de sus propuestas sigue **sin medir**, y el fracaso informativo
(§7) sigue siendo un resultado válido de esta corrida.

## 5. Invocación declarada

`correr_generador.py` ya admite el modelo por parámetro, sin
tocar código:

```
python3 correr_generador.py --generar --modelo "mistralai/mistral-nemo"
python3 correr_generador.py --tanda <archivo de tanda congelada>
```
