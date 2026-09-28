# Datasets del prototipo ALMA

## Qué hay acá

Fixtures **sintéticos** (inventados, 12 problemas × 5 clases = 60) con
verificación 100% automática:

| Archivo | Clase | Verificador | Campo extra |
|---|---|---|---|
| `calculo.json` | aritmética multi-paso | exact-match numérico | — |
| `codigo.json` | escribir funciones Python | tests ejecutados en subprocess | `tests`, `funcion`, `codigo_correcto` |
| `qa_multihop.json` | preguntas factuales | exact-match normalizado | — |
| `herramientas.json` | responder usando contexto | exact-match | `contexto` (simula lo que devolvería una herramienta de búsqueda) |
| `puzzles.json` | Game-of-24 | exact-match normalizado | — |

Son datos de juguete a propósito: sirven para validar que la *maquinaria*
del experimento funciona (fases A/B/C, bandit, veredicto). Un PASS en modo
`--mock` significa "el experimento está bien instrumentado", **no**
"ALMA está validado". La validación real requiere los sets de abajo.

## Schema de cada problema

```jsonc
{
  "id": "calculo-01",        // único
  "clase": "calculo",        // una de las 5 de la taxonomía v1
  "enunciado": "...",        // texto del problema
  "esperado": "...",         // respuesta canónica (o número)
  "verificador": "exact",    // "exact" | "codigo"
  // solo codigo:
  "funcion": "suma",
  "tests": "assert suma(2, 3) == 5",
  "codigo_correcto": "def suma(a, b):\n    return a + b\n",
  // solo herramientas:
  "contexto": "..."          // lo que "devolvería" la herramienta
}
```

## Cómo traer los datasets reales

El protocolo del informe pide 5 clases × 30 problemas de benchmarks
reales. Fuentes y cómo adaptarlos al schema:

- **GSM8K** (cálculo): `openai/gsm8k` en Hugging Face (`datasets`). Respuesta:
  el número tras `####`. → `verificador: "exact"`.
- **HumanEval** (código): github.com/openai/human-eval (`data/HumanEval.jsonl`).
  Cada tarea trae `prompt` y `test`. → `verificador: "codigo"`,
  `tests` = el campo `test`, `funcion` = nombre en `entry_point`.
- **HotpotQA** (multi-hop): hotpotqa.github.io (formato JSON con
  `question` y `answer`). Usar el split de validación, filtrar respuestas
  cortas. → `verificador: "exact"`.
- **GAIA** (herramientas): Hugging Face `gaia-benchmark/GAIA`, nivel 1.
  Requiere herramientas reales (navegador); en este prototipo el runner
  `plan_tools_verify` solo simula la herramienta con `contexto`.
- **Game-of-24** (puzzles): repo del paper "Tree of Thoughts"
  (github.com/princeton-nlp/tree-of-thoughts), `data/24.csv`. Respuesta:
  expresión que evalúa a 24 (verificar con `eval` restringido en vez de
  exact-match).

Muestrear 30 por clase con seed fija y estratificar por dificultad si hay
metadata. Registrar seed y split en el pre-registro antes de correr.
