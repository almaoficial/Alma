# Registry de proveedores — nota de diseño (fase 2.x)

Idea del usuario (noche 27/9): ALMA elige qué llave usar por empresa/tarea.
Refinamiento del EXP69: no el token más barato, sino el dólar más barato
*por unidad de calidad* (reward/USD). Este registry es el *dónde* que el
usuario pidió mejorar: el único lugar donde el router busca qué proveedores
existen y qué rinden.

## Archivos

- `proveedores.yaml` — el registry. Un entry por proveedor: `id`, `connector`
  (ID del vault), `modelos`, `hosts_permitidos`, `ping_url`, `habilitado`,
  `estado` (disponibilidad/motivo/fecha), `ultima_medicion` y `mediciones`
  (campañas con celdas `slice/brazo` → n, reward_medio, costo_medio_usd).
- `registro.py` — `RegistroProveedores`: carga+valida, `disponibles()`,
  `elegir(slice)`, `actualizar_medicion(...)`, `guardar()`, `estado(id)`.
- `test_registro.py` — 16 tests, todos con pings simulados (cero red real).

## Decisiones

1. **YAML, no JSON**: los comentarios llevan la procedencia de cada número
   (qué experimento, cuántos pulls, cuánto costó). La trazabilidad es parte
   del diseño, y JSON no la permite.
2. **Solo metadata, jamás secretos**: el registry no tiene ningún campo para
   keys/tokens, y hay un test que lo verifica (`test_sin_secretos_en_registry`).
   La autenticación del ping usa el surrogate del vault (patrón de los skills):
   la credencial la reemplaza authd al salir; este código nunca la ve.
3. **Regla de elección = regla pre-registrada del EXP69**: por slice, mayor
   reward/USD esperado (`reward_medio / costo_medio_usd`); desempate por menor
   costo; determinista ante empates totales (orden por id/brazo).
4. **Campaña con más evidencia**: si hay varias campañas por proveedor, `elegir`
   usa la de mayor n total (desempate: fecha más reciente). Así una medición
   chica nunca tapa un oráculo grande.
5. **Failover ante 401/403/404**: el ping es un GET gratuito a `/models`.
   Auth rota o revocada → proveedor a `no_disponible` con motivo y fecha
   (persiste en el YAML), sin voltear a los demás. Errores transitorios
   (timeout, 500) excluyen al proveedor solo de esa ronda, sin voltear el
   estado persistido — fail-closed para el ruteo, sin castigar un hipo.
6. **Fail-closed total**: si no hay ningún proveedor disponible, `elegir`
   lanza `SinProveedorDisponible`. El router nunca inventa un proveedor.
7. **Campañas de experimento inmutables**: `actualizar_medicion` escribe en una
   campaña separada `acumulada-operativa` (media corrida por celda), no toca
   las campañas de los experimentos.

## Datos sembrados (medidos esta noche, nada inventado)

- **deepseek** (`custom.deepseek`, deepseek-flash): oráculo EXP67 — 1080
  pulls, 180 problemas frescos (60/slice), n=120 por celda, US$0,3609.
- **openai** (`custom.openai`, gpt-4o-mini): piloto EXP69 — 180 pulls,
  30 problemas (10/slice), n=20 por celda, US$0,0276. Caveat registrado en
  el YAML: confianza menor (piloto, no oráculo).
- Con estos datos, `elegir` reproduce el EXP69: `deepseek/single` en los
  3 slices (verificado en `test_reproduce_exp69`).

## Cómo recargar con nuevas mediciones

Opción A (manual, para campañas de experimentos): agregar un bloque bajo
`mediciones` del proveedor con `campana`, `fecha`, `fuente` (quién midió,
cuántos pulls, cuánto costó) y las `celdas`. Al cargar, el schema se valida
ruidoso (`RegistryInvalido` dice proveedor y campo).

Opción B (programática, operación diaria):
`reg.actualizar_medicion("openai", "single", "gsm8k", reward=1.0, costo=0.00002, n=1)`
— acumula en `acumulada-operativa` y persiste.

Opción C (re-sembrar): regenerar el YAML desde los pulls con el mismo
procedimiento que lo creó (agregación en `resultados/...`), manteniendo los
campos `fuente`.

## Verificación (para el padre)

```
cd ~/workspace/alma-prototype/integracion_fase21/alma_service
python3 test_registro.py          # 16 tests, 0 red
python3 -c "
from registro import RegistroProveedores
r = RegistroProveedores('proveedores.yaml', ping_fn=lambda p: None)
print([r.elegir(s, persistir=False) for s in ('gsm8k','mmlu','mbpp')])"
# → [('deepseek', 'single'), ('deepseek', 'single'), ('deepseek', 'single')]
```

El ping real (`_ping_surrogate`) no se ejercita en tests; validarlo requiere
red y conectores del vault y queda para la integración al servicio (fase 2.x).
No se tocó el servicio en ejecución (puerto 8471) ni su DB: esto vive en
`integracion_fase21/alma_service/`, separado del servicio vivo.
