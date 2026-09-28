# EXP62 — Veredicto: FAIL

**Fecha:** 2026-09-27 ~22:45 UTC (18:45 EDT)
**Pregunta:** ¿el loop de ALMA replica su ventaja con `deepseek-flash` como motor en vez de gpt-4o-mini? Réplica fiel de EXP5 (mundo no estacionario H3, stream 120 problemas / 10 bloques).
**Pre-registro:** `exp62_deepseek/preregistro.md` (escrito antes de gastar; criterio intacto de EXP5).

## Veredicto: FAIL

| Política | Regret total |
|---|---|
| fija-single | **−0,030** (mejor fija) |
| thompson-global | 3,680 |
| **alma-full** | **4,820** |
| fija-cot | 7,170 |
| fija-reflexion | 26,220 |

Criterio pre-registrado: regret(alma-full) < regret(mejor fija) **y** < regret(thompson-global).
- vs mejor fija: 4,82 vs −0,03 → diff **+4,85** ✗
- vs thompson-global: 4,82 vs 3,68 → diff **+1,14** ✗
- alma-full gana el bloque en **0/10** (diagnóstico).

## El hallazgo central: el mundo colapsó a un solo brazo

El oráculo re-medido con deepseek-flash (3 intentos/celda, disciplina EXP8, 1080 llamadas):

- **single: 117/120 · cot: 3/120 · reflexion: 0/120**
- Por éxito puro (sin término de costo): single gana 117, cot 3. No es artefacto del reward.
- Éxito medio: single 0,744 · cot 0,675 · reflexion 0,669.

Con gpt-4o-mini (EXP5) el oráculo era heterogéneo por bloques — había algo que descubrir. Con deepseek-flash, el modo non-thinking gana casi en todo: **no hay heterogeneidad que explotar, y el loop no tiene de qué alimentarse.** La ventaja de EXP5 era condicional al perfil de debilidad del modelo, no una propiedad intrínseca del loop. Eso es lo que este test vino a refutar, y refutó.

## Diagnóstico: el probe acertó 10/10, Thompson sangró igual

- El probe eligió **single en los 10 bloques** (medias típicas single 0,95 / cot 0,94 / reflexion 0,80). El mecanismo de detección funcionó perfecto.
- Pero el diseño (fiel a EXP5) solo deja que el probe controle 3/12 problemas por bloque; los 9 restantes van a Thompson con warm-start.
- Thompson eligió: **single 40/90 · cot 35/90 · reflexion 15/90**. El prior warm (n0=2, medias del oráculo 0,758/0,696/0,552) es débil y las distribuciones se solapan: con una ventaja de apenas 0,06 entre single y cot y rewards ruidosos, la exploración es puro costo.
- Peor: alma-full (4,82) perdió contra thompson-global frío (3,68). El warm-start con las medias del oráculo — donde cot/reflexion "se ven decentes" — no concentró en single; la cercanía del prior alentó exploración en vez de explotación.

Regret por bloque (alma-full vs fija-single): ningún bloque ganado; los peores b1 (1,16) y b7 (1,17) son donde Thompson más exploró.

## Costo y honestidad incómoda

- **Costo total medido: US$0,2559** (1743 llamadas registradas, freno de US$1,00 nunca tocado).
- La estimación que le di al usuario (~US$0,02–0,05) quedó corta por ~5–10×. El smoke mostró el costo real por llamada (~US$0,0005 en reflexion-max) y la proyección debió recalcularse ahí. Queda registrado el miss.
- **Dial de esfuerzo:** el "1–100 continuo" del anuncio no existe en chat/completions; niveles reales `none`/`high`/`max` (mapeados a single/cot/reflexion). El pre-registro lo documenta.
- **1 llamada de smoke (~US$0,0001) se hizo y se perdió sin registrar** (crash por `StoreError: config` antes del primer append; fix aplicado). Va al veredicto, no se esconde.
- **3 crashes y resumes:** `IncompleteRead` (red/API de DeepSeek muy inestable esta noche — decenas de reintentos; se subió de 3 a 6 reintentos con backoff), más un `IndexError` en el smoke al resumir (fix). El store idempotente protegió todos los datos: cero llamadas perdidas salvo la del smoke.
- **Bug en report.json:** los flags `gana_a_mejor_fija`/`gana_a_thompson_global` quedaron hardcodeados en `True`; corregidos a `False` (el `pasa: false` y los números siempre estuvieron bien).
- Solo 6 llamadas truncadas por max_tokens: el truncamiento no explica el bajo rendimiento de cot/reflexion.
- Cadena del store verificada OK (`store_chain_ok: true`).

## Qué significa

1. **Agnosticismo al modelo: NO.** Con un modelo donde un brazo domina, el loop adaptativo es peor que la política fija obvia. La ventaja medida en EXP5 vivía en la heterogeneidad del mundo, y esa heterogeneidad la pone el modelo, no el loop.
2. **El probe no es el problema** (10/10). El problema es arquitectónico: el probe decide poco (3/12) y Thompson explora caro cuando la ventaja es chica y ruidosa.
3. **Pregunta abierta que deja:** ¿hay mundos reales donde el oráculo sea heterogéneo *para un modelo fuerte*? Si no, el loop solo agrega valor sobre modelos débiles — un techo incómodo para ALMA.

## Artefactos

- `exp62_deepseek/experiencias.jsonl` — 1743 filas, cadena verificada
- `exp62_deepseek/oraculo.json` — oráculo completo (lo necesita EXP66)
- `exp62_deepseek/report.json` — números y veredicto
- `exp62_deepseek/gasto_por_llamada.jsonl` — contabilidad por llamada
- `exp62_deepseek/preregistro.md` — pre-registro previo al gasto
- `exp62_deepseek/run_exp62.py` — script (con los 3 fixes documentados)

**Resultado: FAIL.** La vara no se movió.
