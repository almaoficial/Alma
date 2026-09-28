# Vara pre-registrada — plantilla del diagnóstico inicial

*Completar ANTES de recibir las trazas y ANTES de correr `diagnostico.py`.*
*Enviar copia al cliente junto con el pedido de trazas: los criterios no se mueven después de ver los números.*

---

- **Cliente:** [CLIENTE]
- **Fecha de registro:** [FECHA]
- **Responsable:** [FIRMANTE]
- **Alcance:** diagnóstico inicial (hasta 2 tipos de consulta, 1 semana) — ver `../OFERTA.md`

## 1. Tipos de consulta incluidos

| # | `tipo_consulta` (exacto como vendrá en el CSV) | Descripción en lenguaje del negocio | Clase para el router* |
|---|---|---|---|
| 1 | [TIPO_1] | [DESCRIPCIÓN] | simple / razonamiento |
| 2 | [TIPO_2] | [DESCRIPCIÓN] | simple / razonamiento |

*\* `simple`: respuesta directa sin cadena de razonamiento. `razonamiento`: requiere razonamiento paso a paso o reflexión. Determina qué rewards de referencia usa el script.*

## 2. Qué cuenta como "resuelta" (por tipo)

- **[TIPO_1]:** [DEFINICIÓN OPERATIVA — p. ej. "el usuario no repregunta ni escala en las 24 h siguientes"].
  Fuente del dato: columna `resultado` = `resuelta` en el CSV.
- **[TIPO_2]:** [DEFINICIÓN OPERATIVA].
  Fuente del dato: columna `resultado` = `resuelta` en el CSV.

## 3. Umbral de ahorro que justifica recomendar un cambio

Se recomendará evaluar un cambio de ruteo **solo si** se cumplen las tres condiciones:

1. El ahorro mensual estimado es **≥ [X]%** del costo mensual actual de los tipos auditados, **o** ≥ US$ [Y] mensuales en términos absolutos (aplica el que se alcance primero).
2. El **límite inferior del intervalo de confianza 95%** (bootstrap, ver informe del script) es **> 0**.
3. El modelo recomendado tiene un reward de referencia **≥** el del modelo actual (sin pérdida de calidad medida).

Si no se cumplen, el informe dirá literalmente: *"con los datos disponibles, no se recomienda ningún cambio de ruteo"*.

## 4. Criterios de exclusión (qué se deja afuera y por qué)

- Tipos de consulta con **menos de 200 llamadas** en la muestra: se excluyen del cálculo y se listan como "muestra insuficiente".
- Filas con datos inválidos: las rechaza el script; se reporta la cantidad, no se imputan.
- Período atípico (incidentes, picos promocionales): [INDICAR SI APLICA / N/A].

## 5. Supuestos declarados

- Los precios por token son los de la tabla `PRECIOS` del script, vigentes al [FECHA]; se verifican contra el pricing publicado antes de correr.
- Los rewards de referencia son medidos en **nuestros** oráculos (no en el workload del cliente); la Auditoría Completa los re-mide sobre sus consultas.
- La estimación mensual escala linealmente el ahorro por llamada según el volumen mensual declarado por el cliente: [VOLUMEN MENSUAL POR TIPO, si se conoce / "a confirmar"].

## 6. Firma del registro

| | Responsable |
|---|---|
| Nombre | [FIRMANTE] |
| Fecha | [FECHA] |
| Hash/versión del archivo | [OPCIONAL] |

*Este documento se congela en esta fecha. Cualquier cambio posterior invalida el diagnóstico y obliga a re-registrar.*
