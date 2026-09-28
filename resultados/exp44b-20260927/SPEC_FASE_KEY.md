# ALMA-EXP44b — SPEC de la fase con key (NO CORRER sin aprobación)

Estado: spec escrita el 2026-09-27. **No se gastó nada. No correr hasta que el
usuario apruebe costo y tiempo explícitamente.**

## Qué es

La misma pregunta de EXP44-fase-mock, pero con los brazos implementados de
verdad con `gpt-4o-mini` (prompts distintos por brazo) sobre el stream real
de noticias del feed. El oráculo sigue siendo la etiqueta publicada (gratis).

## Precondición

`~/workspace/alma-prototype/data_exp44/feed_units.json` exportado con datos
reales (ver `data_exp44/README.md`). La fase mock debe haber corrido primero.

## Brazos (implementación real)

| Brazo | Implementación | Costo |
|---|---|---|
| `titular` | gpt-4o-mini, prompt: "Clasificá esta noticia en una de estas categorías: [lista]. Basate SOLO en el titular. Respondé únicamente la categoría." + titular | 1 llamada |
| `contexto` | gpt-4o-mini, prompt: "Clasificá esta noticia en una de estas categorías: [lista]. Leé el texto completo. Respondé únicamente la categoría." + titular + texto | 1 llamada |
| `estable` | gpt-4o-mini, prompt genérico corto (mismo formato, sin énfasis) | 1 llamada |
| `mayoria` | determinista: categoría más frecuente vista hasta el momento | US$0 |

La [lista] de categorías se fija a las observadas en el stream (evita
respuestas fuera del vocabulario). Temperatura 0.

## Llamadas y costo estimado

Por bloque de 10 items: 5 de probe (se miden los 3 brazos LLM) + 5 Thompson
(solo el brazo elegido). Total por item: 5×3 + 5×1 = 20 llamadas/bloque.

Fórmula: `llamadas ≈ n_items × 2` (2 llamadas por item en promedio).

Supuestos (a verificar al momento de aprobar):
- ~400 tokens input + ~10 output por llamada (titular + excerpt).
- Precio gpt-4o-mini: US$0,15 / 1M input, US$0,60 / 1M output.

| n_items | llamadas | tokens aprox | costo estimado |
|---|---|---|---|
| 100 | ~200 | ~82K | **~US$0,02** |
| 200 | ~400 | ~164K | **~US$0,04** |

Tiempo estimado: ~1,5 s/llamada secuencial → ~5 min (n=100), ~10 min (n=200).
Paralelizable si hace falta.

**Freno duro:** si la proyección supera US$1,00, detener antes de la política
(precedente: EXP11).

## Criterio (igual que la fase mock, pre-registrar antes de correr)

`media sobre réplicas de [regret(ALMA) − regret(mejor brazo fijo)] < 0` →
PASS. Réplicas: 5 (el ruido LLM entre réplicas se mide, no se ignora).

## Diferencias honestas vs. la fase mock

1. En la fase mock las tasas por brazo/categoría son supuestos documentados;
   acá el acierto real de cada brazo se mide.
2. El brazo `mayoria` no cambia (determinista, gratis).
3. La no-estacionariedad del stream es la misma (datos reales en ambas fases).

## Aprobación requerida

Costo y tiempo confirmados por el usuario ANTES de gastar. La key se usa vía
el mismo mecanismo que EXP11 (VaultBackend); nunca se muestra ni se guarda.
