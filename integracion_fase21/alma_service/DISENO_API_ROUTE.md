# Diseño: POST /route — el router ALMA como API (fase 2.x)

Versión: 0.1 (diseño + stub mock). Estado: **diseño aprobado para revisión,
NO desplegado** — ver "Qué falta para el deploy" al final.

## 1. Qué es

El producto es el **router** (el loop de ALMA como motor adentro): un servicio
que, dada una tarea y un presupuesto, decide **qué proveedor, qué modelo y
qué brazo** usar para maximizar **reward por dólar** (regla pre-registrada
del EXP69), con failover automático ante credenciales rotas.

Este endpoint es la superficie comercial del sistema: un cliente manda la
tarea y el presupuesto; el router devuelve la decisión con su costo
estimado y el motivo medido. El cliente después ejecuta la llamada él mismo
o por otro endpoint — `/route` solo decide, no gasta.

## 2. Contrato

### POST /route

Request (JSON):

| Campo             | Tipo    | Requerido | Reglas                                   |
|-------------------|---------|-----------|------------------------------------------|
| `tarea`           | string  | sí        | slice conocido (`gsm8k`, `mmlu`, `mbpp`) o descripción libre clasificable |
| `presupuesto_usd` | number  | sí        | > 0. Tope duro por llamada               |
| `latencia_max_ms` | number  | no        | > 0 si se envía                          |

Response 200 (JSON):

```json
{
  "proveedor": "deepseek",
  "modelo": "deepseek-flash",
  "brazo": "single",
  "costo_estimado_usd": 0.0000142,
  "motivo": "regla EXP69 (max reward/USD): deepseek/single, reward 0.6333 / costo US$0.0000142 -> 44,600 reward/USD (n=120, campaña exp67-oraculo); presupuesto US$0.0100000 OK"
}
```

Semántica de cada campo:

- `proveedor`: `id` del registry (`proveedores.yaml`). Nunca un secreto.
- `modelo`: el modelo medido de la campaña ganadora (`modelos[0]` del
  proveedor). El `brazo` es la variante de esfuerzo/prompting sobre ese
  modelo (p.ej. `single`/`cot`/`reflexion` en deepseek-flash fueron niveles
  de esfuerzo del EXP67; en gpt-4o-mini fueron variantes de prompting del
  piloto EXP69).
- `brazo`: el brazo elegido por la regla de reward/USD.
- `costo_estimado_usd`: `costo_medio_usd` de la celda ganadora (media medida,
  no promesa). El cliente puede presupuestar N llamadas como N × este valor.
- `motivo`: explicación auditable — regla usada, números de la celda
  (reward, costo, n, campaña) y chequeo de presupuesto. Es el "recibo" de
  la decisión.

### Clasificación de `tarea` → slice

1. Si `tarea` es exactamente un slice conocido, se usa directo.
2. Si no, clasificador por keywords determinista (es/en): matemáticas →
   `gsm8k`, conocimiento/preguntas → `mmlu`, código → `mbpp`.
3. Si no mapea → `422 unknown_task` (falla ruidoso; el router no adivina).

El stub implementa esto en `clasificar_tarea()`. En producción el
clasificador puede evolucionar (embeddings, etc.) sin cambiar el contrato.

### `latencia_max_ms`

Se acepta y se valida (> 0), pero **el stub no la usa para elegir**: el
registry aún no tiene mediciones de latencia. El diseño prevé celdas con
`latencia_media_ms` en el futuro; cuando existan, la elección filtrará por
latencia antes de maximizar reward/USD. Documentar la limitación es mejor
que fingir que se cumple.

## 3. Catálogo de errores

| Status | `codigo`              | Cuándo                                                        |
|--------|-----------------------|---------------------------------------------------------------|
| 400    | `invalid_request`     | `tarea` vacía/no-string, `presupuesto_usd` ≤ 0 o no numérico, `latencia_max_ms` inválida |
| 402    | `budget_exceeded`     | el costo estimado del ganador supera `presupuesto_usd` (fail-closed: no hay proveedor que quepa) |
| 422    | `unknown_task`        | `tarea` no mapea a ningún slice; o el slice no tiene mediciones en el registry |
| 503    | `no_provider_available` | ningún proveedor disponible (fail-closed del registry)      |
| 500    | `internal_error`      | cualquier otra falla                                          |

Cuerpo de error:

```json
{"codigo": "budget_exceeded",
 "detalle": "costo estimado US$0.0000142 supera el presupuesto US$0.0000000 (fail-closed: ningún proveedor cabe en el presupuesto)"}
```

`codigo` es estable para que los clientes programen contra él; `detalle` es
humano y puede cambiar.

### Nota sobre 402

Hoy el 402 es fail-closed simple: si el argmax de reward/USD no cabe en el
presupuesto, se rechaza. Una versión futura podría buscar el mejor
reward/USD *dentro* del presupuesto (restringido). Se deja como está a
propósito: el rechazo explícito es más honesto que una degradación
silenciosa, y el cliente siempre puede reintentar con más presupuesto.

## 4. Failover

En cada llamada a `/route`, el router re-chequea disponibilidad con el ping
gratuito (`GET` a `ping_url`, auth por surrogate del vault — la credencial
la reemplaza authd al salir, el código nunca la ve):

- **2xx** → disponible.
- **401/403/404** → proveedor a `no_disponible` con motivo y fecha
  (persiste en el YAML en el deploy real; en el stub mock no se persiste).
  No voltea a los demás proveedores.
- **Otro error** (timeout, 500, red) → excluido solo de esa ronda, sin
  voltear el estado persistido (no se castiga un hipo transitorio).

Si no queda ningún proveedor → `503 no_provider_available`. El router nunca
inventa un proveedor.

El stub (`router_stub.py`) recibe `ping_fn` inyectable: por defecto un doble
que simula "todos disponibles" (cero red, US$0). Los tests simulan 401 para
verificar el failover: con deepseek en 401, `gsm8k` rutea a
`openai`/`gpt-4o-mini`/`single`.

## 5. Seguridad

- El endpoint y el registry **jamás ven secretos**: solo IDs de proveedor/
  conector y estadísticas. Hay tests que lo verifican en ambos módulos.
- El ping de disponibilidad usa el patrón surrogate del vault (igual que
  los skills): la credencial real solo existe en el vault y la reemplaza
  authd al salir.
- En el deploy real, `/route` debe ir detrás de autenticación (API key del
  cliente o el mecanismo que se defina) — el stub no la implementa.
- Rate limiting y topes de gasto por cliente: pendientes del deploy
  (relacionado con la decisión del usuario sobre el tope mensual).

## 6. Archivos (stub mock, US$0)

En `integracion_fase21/alma_service/` (separado del servicio vivo del
puerto 8471 — no se toca nada en ejecución):

- `router_stub.py` — `RouterStub` + `clasificar_tarea()` + `RouterError`.
  Lógica de decisión sin HTTP. Default: ping mock, `persistir=False` (no
  muta `proveedores.yaml`).
- `test_router_stub.py` — 15 tests, todos en verde, cero red, cero gasto.
- `DISENO_API_ROUTE.md` — este documento.

Verificación:

```
cd ~/workspace/alma-prototype/integracion_fase21/alma_service
python3 test_router_stub.py   # 15 tests OK
python3 test_registro.py      # 16 tests OK (sin regresión)
```

## 7. Qué falta para el deploy (NO HACER sin su "sí")

**Decisiones del usuario (pendientes, bloquean todo):**

1. **Dónde corre 24/7** de forma permanente (la regla dura de esta tarea:
   no desplegar, no exponer puertos, no tocar el servicio del puerto 8471).
2. **Tope mensual en US$** — el presupuesto por llamada existe (`presupuesto_usd`),
   pero falta el freno agregado (por cliente / global / mensual).

**Ingeniería pendiente (después de sus decisiones):**

3. Capa HTTP real (`POST /route` con el contrato de §2; framework a elegir:
   el servicio actual es Python, lo natural es extenderlo o un microservicio
   aparte que importe `router_stub`/`registro`).
4. Autenticación del endpoint + rate limiting por cliente.
5. Ping real con surrogate del vault (hoy solo existe como código no
   ejercitado en `registro._ping_surrogate`; validarlo requiere red y
   conectores).
6. `persistir=True` en el deploy para que el failover 401/403/404 quede
   registrado en el YAML con motivo y fecha.
7. Mediciones de latencia por celda en el registry (para que
   `latencia_max_ms` filtre de verdad en vez de solo validarse).
8. Observabilidad: log de cada decisión (tarea→slice, ganador, costo
   estimado, motivo) para alimentar `actualizar_medicion` y cerrar el loop.
9. Versionado del contrato (`/v1/route`) antes del primer cliente externo.

**No es parte de este diseño:** ejecutar la llamada al LLM (el endpoint
solo decide), facturación al cliente final, ni SLA de disponibilidad.
