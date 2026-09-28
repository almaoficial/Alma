# EXP67 — Diseño del stream (tarea real)

**Fecha:** 2026-09-27. Todo el trabajo de este documento es US$0 (sin llamadas a API).

## Slices (3, tarea real, ground truth automático)

| Slice | Dataset (HF, verificado hoy) | n | Ground truth | Brazo que la literatura espera que gane |
|---|---|---|---|---|
| `gsm8k` | `openai/gsm8k`, config `main`, split `test` (1319 problemas). Campos: `question`, `answer` (termina en `#### <num>`) | 60 | Exact match numérico sobre `#### <número>` (se normalizan comas/espacios) | **cot** — CoT supera ampliamente a respuesta directa en GSM8K (Wei et al. 2022: ~18% → ~58% en PaLM 540B; replicado en todos los modelos posteriores) |
| `mmlu` | `cais/mmlu`, split `test`, unión de los 59 subjects (~14k problemas). Campos: `question`, `subject`, `choices[4]`, `answer` (índice 0–3) | 60 | Letra A/B/C/D = `choices[answer]`; match exacto de letra | **single** — el eval estándar de MMLU es 5-shot directo; CoT ayuda en algunos subjects pero la respuesta directa es competitiva y mucho más barata |
| `mbpp` | `google-research-datasets/mbpp`, config `full`, split `test` (500 problemas). Campos: `task_id`, `text` (prompt), `code`, `test_list`, `test_setup_code` | 60 | Extraer bloque ```python; ejecutar `test_setup_code` + `test_list` en subprocess con timeout 10 s; éxito = todos los asserts pasan | **reflexion** — auto-crítica y corrección mejoran generación de código (línea Reflexion: 91% HumanEval con verbal RL; el código se beneficia de verificar antes de responder) |

**Caveat honesto:** las expectativas de la columna derecha son priors de la literatura
sobre OTROS modelos. El perfil real de `deepseek-flash` en estos slices es
desconocido — por eso el diseño incluye la **puerta anti-colapso** (§4), no una
suposición.

## Muestreo (seed fija 67, reproducible)

- `gsm8k`: 60 índices del test, `random.Random(67).sample`.
- `mmlu`: 60 pares `(subject, índice)` uniformes sobre la unión de los 59
  subjects del test (evita sesgo hacia subjects grandes).
- `mbpp`: 60 índices del test.
- Sin reemplazo dentro del stream; el manifiesto congela los IDs exactos:
  `stream_manifest.json` (generado con seed 67, verificado sin duplicados).

## Orden de bloques (pre-registrado, inmutable)

9 bloques × 20 problemas = 180 problemas. Orden de slices:

```
B1 gsm8k → B2 mmlu → B3 mbpp → B4 mmlu → B5 gsm8k →
B6 mbpp → B7 gsm8k → B8 mmlu → B9 mbpp
```

Cada slice aparece exactamente 3 veces; ningún bloque repite el slice anterior
(no estacionario por construcción: el régimen cambia en cada bloque).
Cada aparición consume los siguientes 20 problemas del slice en orden de muestreo.

## Puerta anti-colapso (lección del EXP62 soldada en el diseño)

**Problema que evita:** si un slice es single-dominante con el modelo real
(como el mundo sintético del EXP62: single 117/120), el loop no tiene nada que
aprender y el experimento no mide nada.

**Piloto pre-registrado (antes del oráculo):** 10 problemas por slice (muestreados
con seed 67, disjuntos del stream) × 3 brazos × 2 intentos = 180 llamadas.

**Regla:** un slice pasa si ningún brazo gana más del 80% de sus celdas
(win-rate por celda = mejor promedio de 2 intentos). Si un slice colapsa:

1. Se reemplaza por su backup y se re-pilota (máx. 2 reemplazos por slice).
2. Backups pre-registrados: código → `openai/openai_humaneval` (HumanEval, 164
   problemas, eval por tests); conocimiento → `allenai/ai2_arc` config
   `ARC-Challenge` (eval por letra, mismo formato que MMLU).
3. Si el backup también colapsa, el diseño cae a 2 slices y se documenta.

Esto es **validación del mundo, no mover el arco**: el criterio PASS/FAIL
(comparación de regrets) no cambia; solo se garantiza que el mundo tenga la
propiedad que la hipótesis necesita (regímenes donde distintos brazos ganan).

## Brazos (mismo mapeo que EXP62, verificado contra la API)

- `single` → `reasoning_effort: "none"`, max_tokens 256. Prompt directo con
  formato de respuesta por slice.
- `cot` → `reasoning_effort: "high"`, max_tokens 1024. "Pensá paso a paso" +
  línea final `Respuesta: <...>`.
- `reflexion` → `reasoning_effort: "max"`, max_tokens 2048. CoT + auto-crítica
  explícita ("cuestioná tu razonamiento, verificá cada paso") + `Respuesta: <...>`.

Formatos de `Respuesta:` por slice: gsm8k → `#### <número>`; mmlu → una letra
`A/B/C/D`; mbpp → bloque ```python (se extrae el primer bloque de código).

## Políticas

- `alma-full`: Thompson por slice + warm-start con repertorio hacia adelante
  (n0=4), probe 3 problemas × 3 brazos al entrar a cada bloque (9 llamadas),
  skip del probe (EXP52), scaffold vigente
  `{n0: 4, decay: 0.5, umbral_base: 1, umbral_divisor: 3}` (validado EXP56/57/65).
- `fija-single`, `fija-cot`, `fija-reflexion`.
- `thompson-global`: 1 bandit, prior uniforme (control sin memoria ni probe).
- Evaluador: mismo que EXP62 — reward = 0.75·éxito + 0.25·(1 − costo_rel/5),
  costo_rel del registry (single 1.0, cot 1.2, reflexion 4.0), independiente
  del proveedor. RNG pareado por posición de stream entre políticas.
