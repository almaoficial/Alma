# Formato del inbox diario — EXP71

El worker del cron NO puede leer el feed con `feed.unit_list` desde una
automatización agendada (solo `feed.unit_create` funciona fuera de la
conversación principal). Por eso el feed del día entra por acá: un volcado
hecho desde el chat principal (que sí tiene acceso al feed).

## Archivo esperado

`~/workspace/alma-prototype/data_exp71/inbox/feed_YYYY-MM-DD.json`

```json
{
  "fecha": "2026-09-28",
  "fuente": "volcado manual desde el chat principal",
  "unidades": [
    {"id": "unit-abc123", "categoria": "Inteligencia artificial"},
    {"id": "unit-def456", "categoria": "Finanzas"}
  ]
}
```

## Reglas

- `fecha`: día calendario (America/New_York) al que pertenecen las unidades.
- `unidades`: una entrada por unidad del feed de ese día, con la categoría
  tal cual la publica el feed (sin normalizar: se compara string exacto,
  solo se recorta espacio en blanco a los extremos).
- Unidades sin categoría se descartan y se cuentan (`n_sin_categoria`).
- Día válido ⟺ ≥ 5 unidades con categoría. Si no, el día queda SKIP.
- El volcado ideal es a la mañana siguiente (el feed del día D se vuelca
  la mañana de D+1, antes del cron de las 11:00).
- Hook sugerido: el cron `feed-veracidad-diaria` (09:23) ya lee el feed
  a diario desde un contexto con acceso — puede escribir este archivo.
