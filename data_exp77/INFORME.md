# EXP77 — Auditoría de handoff de skills

Fecha: 2026-10-01 · Regla: `delta_down>0 & delta_ref>=0` · Rúbrica: `traductor-exp77-v1` · Costo: US$0 (mock)

> Nota honesta: los veredictos son **condicionales a la rúbrica**
> (predicados mecánicos sobre el contenido, versionada y
> documentada en `run_exp77.py`). Lo exacto es `q` (calidad de
> interfaz) y los deltas dada la rúbrica. Auditoría de **solo
> lectura**: cero adopciones, cero modificaciones.

## Inventario

7 archivos SKILL.md (los DBs de skills están vacíos; las variantes de `resultados/fase1-puerta` son skills distintas: distinto brazo recomendado y distinto cuerpo).

## Hallazgos

| Skill | q | ayuda | rigidez | Δ_down | Δ_ref | Veredicto | Estab. | Predicados |
|---|---|---|---|---|---|---|---|---|
| `rep0/skills/firmas` | 0.8 | 0.6 | 0.5 | +0.2978 | +0.3064 | **pasa** | 9/9 | TECNICA, PRESCRIBE, RESTRINGE |
| `rep0/skills/firmas` | 0.8 | 0.3 | 0.5 | +0.1429 | +0.1764 | **pasa** | 7/9 | GENERICO, PRESCRIBE, RESTRINGE |
| `rep1/skills/firmas` | 0.8 | 0.7 | 0.5 | +0.3188 | +0.3359 | **pasa** | 9/9 | PROCEDIMIENTO, PRESCRIBE, RESTRINGE |
| `rep1/skills/firmas` | 0.8 | 0.7 | 0.5 | +0.3188 | +0.3359 | **pasa** | 9/9 | PROCEDIMIENTO, PRESCRIBE, RESTRINGE |
| `rep2/skills/firmas` | 0.8 | 0.7 | 0.5 | +0.3188 | +0.3359 | **pasa** | 9/9 | PROCEDIMIENTO, PRESCRIBE, RESTRINGE |
| `rep2/skills/firmas` | 0.8 | 0.3 | 0.5 | +0.1429 | +0.1764 | **pasa** | 7/9 | GENERICO, PRESCRIBE, RESTRINGE |
| `hola-mundo/SKILL.md` | 0.8 | 0.7 | 0.0 | +0.3725 | +0.3896 | **pasa** | 6/6 | INSTRUCCION_CONCRETA |

## Resumen

- pasan: 7
- restan (peor que nada): 0
- bloat (Δ=0): 0

## Limitación honesta del instrumento

Las 7 skills tienen q=0.8 (interfaces prolijas: descripción de
longitud media + firma de un parámetro). Con q=0.8 la puerta
rechaza solo si ayuda < rigidez/4; el piso de ayuda de la rúbrica
es 0.3, así que ninguna variante del set actual puede caer en
rechazo. La auditoría establece el baseline (todo pasa, nada
resta, nada es bloat) y la capacidad de rechazo de la puerta quedó
probada en EXP76 con mocks calibrados. La discriminación real
aparecerá cuando el meta-loop proponga skills nuevas.

## Decisión pendiente (humana)

Este informe no adopta, cuarentena ni modifica nada. Qué hacer con las que restan o son bloat lo decide él.

