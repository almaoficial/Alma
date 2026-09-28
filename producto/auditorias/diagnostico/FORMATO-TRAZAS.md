# Formato de trazas para el diagnóstico inicial

*Especificación del CSV que se le pide al cliente. Versión 1.0 — 28/9/2026.*
*Se usa con `diagnostico.py` (mismo directorio).*

## El archivo

Un único archivo CSV, codificación UTF-8, con encabezado. Una fila por llamada al modelo.

## Columnas (exactas, en este orden)

| Columna | Tipo | Descripción |
|---|---|---|
| `tipo_consulta` | texto | Categoría de la consulta, definida por el cliente (p. ej. `consulta_stock`, `estado_pedido`, `disputa_garantia`). Sin espacios; usar snake_case. |
| `tokens_in` | entero ≥ 0 | Tokens de entrada de la llamada. |
| `tokens_out` | entero ≥ 0 | Tokens de salida de la llamada. |
| `latencia_ms` | entero o vacío | Latencia total de la llamada en milisegundos. Puede ir vacía si no la miden. |
| `resultado` | uno de: `resuelta` \| `escalada` \| `repregunta` | `resuelta`: la respuesta cerró la consulta. `escalada`: pasó a un humano. `repregunta`: el usuario tuvo que repreguntar. |
| `modelo_usado` | texto | Modelo que atendió la llamada (p. ej. `gpt-4o-mini`, `deepseek`, `claude-haiku`). Debe coincidir con la tabla de precios del script. |
| `fecha` | texto `AAAA-MM-DD` | Fecha de la llamada. |

## Ejemplo (3 filas)

```csv
tipo_consulta,tokens_in,tokens_out,latencia_ms,resultado,modelo_usado,fecha
consulta_stock,42,18,900,resuelta,gpt-4o-mini,2026-09-20
estado_pedido,55,31,1100,resuelta,gpt-4o-mini,2026-09-20
disputa_garantia,380,210,4200,escalada,gpt-4o-mini,2026-09-21
```

## Tamaño mínimo de muestra

- **Mínimo por tipo de consulta: 200 llamadas.** Con menos de 200, el intervalo de confianza no es informativo y el tipo se excluye del diagnóstico (queda registrado en la vara pre-registrada).
- **Recomendado: 500 o más llamadas por tipo.**
- Ventana temporal sugerida: los últimos 30 días de operación normal (sin incidentes ni picos atípicos; si los hubo, indicarlo).

## Qué NO pedir (nunca)

- ❌ Claves de API, secrets o credenciales de ningún proveedor.
- ❌ Texto libre de las preguntas o respuestas (nada que identifique al cliente final).
- ❌ Nombres, emails, documentos, direcciones o cualquier dato personal.
- ❌ Acceso a producción, dashboards internos o repositorios.
- ⚠️ Los prompts del sistema son opcionales: si el cliente quiere compartirlos ayuda a detectar prompts inflados, pero no son requisito.

## Validación

`diagnostico.py` rechaza el archivo si faltan columnas, hay valores fuera de rango o aparece un modelo sin precio en su tabla. Corregir del lado del cliente y reenviar: nunca "arreglar a mano" los datos.
