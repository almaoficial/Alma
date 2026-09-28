# EXP69 — Router de proveedores por reward/USD (pre-registro)

Fecha: 2026-09-27. Idea del usuario: ALMA debe indicar qué llave usar para qué
empresa/tarea — optimizar cada trabajo eligiendo el proveedor más conveniente.
El proveedor pasa a ser una dimensión más de la configuración (el "sexto
hiperparámetro" del scaffold).

## Pregunta
¿Puede una regla de ruteo pre-registrada elegir el proveedor con mejor
reward/USD por slice de tarea, usando solo costos y rewards medidos?

## Regla del router (fijada antes de medir)
Para cada slice, entre las configuraciones c = (proveedor, brazo):
- Métrica: reward/USD esperado = media(reward_c) / media(costo_usd_c),
  con IC95 por bootstrap sobre los pulls del piloto.
- Elección: la configuración con mayor reward/USD esperado; desempate por
  menor costo medio.
- A nivel proveedor: gana el proveedor cuya mejor configuración tenga mayor
  reward/USD global.

Refinamiento del usuario incorporado: NO se minimiza precio del token, se
maximiza reward por dólar (si no, el router elegiría el más barato y más tonto).

## Diseño
- Mismo subset `pilot` del manifiesto (30 problemas: 10 gsm8k / 10 mmlu /
  10 mbpp), mismos 3 brazos × 2 intentos = 180 llamadas por proveedor.
- DeepSeek: datos YA medidos (piloto EXP67, 183 pulls, US$0,0623).
- OpenAI (gpt-4o-mini): 180 llamadas nuevas. Brazos por prompting
  (single/cot/reflexion, disciplina EXP1-9) porque gpt-4o-mini no tiene knob
  de reasoning-effort como deepseek-flash — asimetría documentada, no defecto:
  el router compara configuraciones (proveedor × política), que es la
  abstracción correcta.
- Idempotencia: pulls keyed por (fase="exp69-openai", pid, arm, intento);
  resume limpio; freno duro aborta con parcial sin veredicto.

## Criterio de éxito (vara pre-registrada)
PASS si AMBAS:
1. La elección del router coincide con el ganador ex post en ≥2/3 slices.
2. El IC95 de la diferencia de reward/USD entre proveedores (global) no
   incluye el 0 — la ventaja es real, no ruido.

Diagnóstico: tabla reward/USD por (proveedor, brazo, slice); elección del
router vs ganador ex post; costo total por proveedor para el mismo trabajo.

## Presupuesto
180 llamadas gpt-4o-mini. Estimado US$0,05–0,15 (gpt-4o-mini no paga thinking
tokens; el piloto DeepSeek midió ~US$0,00034/pull con thinking incluido).
Freno duro US$0,25. Lado DeepSeek: US$0 (ya medido).
Tiempo estimado: 10–20 min en segundo plano.

## Gobernanza
Las keys quedan en el vault (conectores `custom.deepseek` / `custom.openai`);
el router solo ve IDs de proveedor y estadísticas medidas, nunca secretos.
El router es telemetría + decisión de configuración — no toca código ni
promociona nada (línea roja vigente).
