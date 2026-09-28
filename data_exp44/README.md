# data_exp44 — adapter del stream de noticias del feed

## Handoff pendiente (para el parent / main conversation)

El subagent de EXP44 **no puede leer las unidades del feed**: el namespace `feed`
solo expone `unit_create` en este contexto; `unit_list`, `feed.search` y
`feed.unit_get` funcionan únicamente en la conversación principal.

**Lo que falta para correr el EXP44 real:** exportar las unidades publicadas a
`~/workspace/alma-prototype/data_exp44/feed_units.json` con este esquema:

```json
[
  {
    "id": "unit_id (string)",
    "published_at": "2026-09-20T14:32:00 (ISO, zona del feed)",
    "title": "titular de la unidad",
    "text": "cuerpo / resumen de la unidad (puede ser excerpt)",
    "category": "categoría o kicker tal como la publica el feed (string libre)"
  }
]
```

Requisitos:
- Orden cronológico (el script re-ordena por `published_at` de todos modos).
- `category` es el **oráculo**: la etiqueta real publicada. No normalizar de más;
  el script hace `strip().lower()`.
- Mínimo **40 unidades** con categoría no vacía; si hay menos, el script declara
  stream insuficiente y frena (exit 2) sin veredicto.
- No inventar unidades ni etiquetas.

## Exportación real (2026-09-27, conversación principal)

- `feed_units.json`: 94 unidades de noticias, 2026-09-22 → 2026-09-27, 30 categorías
  distintas (oráculo = categoría tal como la publica el feed, sin normalizar;
  hay duplicados entre idiomas: "Agentes IA"/"Agentes de IA",
  "Finanzas"/"Finances", etc. — eso es el oráculo real).
- Excluidas las 9 unidades "Getting started" (onboarding, no noticias).
- `id` = clave de fila de la exportación (`exp44-001`…`exp44-094`), NO el unit_id
  del feed (se usan claves propias para evitar errores de transcripción).
- `text` = excerpt tal como lo publica el feed (con links markdown reducidos a
  texto plano).
- `published_at`: el feed solo expone granularidad de día + franja
  (mañana/tarde/noche). Las horas son placeholders ordinales que preservan el
  orden newest-first del propio feed (mañana 09:xx, tarde 15:xx, noche 20:xx);
  el orden cronológico entre días es real, dentro del día es el del feed.

## Propiedad conocida del stream (va al pre-registro)

**Sesgo de selección explícito:** el feed es curado — contiene solo noticias que le
interesan al usuario. No es "todas las noticias" ni una muestra aleatoria de la
agenda noticiosa; es un stream filtrado por interés personal. Implicancias:
1. La distribución de categorías refleja SUS intereses, no la agenda general.
2. La no-estacionariedad que se mida = rotación de SUS intereses en el tiempo.
3. Los resultados NO generalizan a "clasificación de noticias" en general.

## Archivos

- `feed_units.json` — el stream real (pendiente, lo pone el parent).
- `tasas.json` — configuración de los brazos mock (tasas por categoría).
- `../generar_smoke_exp44.py` — generador de datos SINTÉTICOS solo para validar
  el pipeline. Nunca usar su salida como veredicto.
