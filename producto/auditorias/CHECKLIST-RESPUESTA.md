# Checklist — el cliente dijo sí al diagnóstico inicial

*Qué hacer, en orden, cuando GoBots u otro prospecto acepta el diagnóstico gratuito.*
*Precios y alcance: ver `OFERTA.md` (no se negocian en este checklist).*

## 0. Antes de responder

- [ ] El "sí" llegó por el canal correcto (respuesta al email enviado). No hacer follow-up insistente: un recordatorio a los 5 días hábiles si no hay respuesta, después se archiva.

## 1. Mandar el NDA

- [ ] Completar `NDA-MODELO.md`: `[FIRMANTE]`, `[CLIENTE]`, `[FECHA]`, `[JURISDICCIÓN A DEFINIR]`.
  - ⚠️ **[FIRMANTE] está pendiente de definir**: nombre personal o marca. Decisión del responsable antes del primer envío real.
- [ ] Enviarlo al contacto y pedir devolución firmada **antes** de recibir trazas.
- [ ] Guardar la copia firmada en `producto/auditorias/clientes/[CLIENTE]/`.

## 2. Pedir las trazas

- [ ] Enviar `diagnostico/FORMATO-TRAZAS.md` (o su contenido en el cuerpo del email) + la vara pre-registrada completada (paso 3).
- [ ] Recordar explícitamente: **nunca** keys, nunca texto de clientes finales, nunca accesos.
- [ ] Plazo sugerido: 5 días hábiles.

## 3. Llenar la vara pre-registrada

- [ ] Completar `diagnostico/VARA-PRE-REGISTRADA-TEMPLATE.md` **antes de abrir el CSV**: tipos incluidos, definición de "resuelta", umbral de ahorro ([X]% o US$ [Y]), criterios de exclusión.
- [ ] Congelar el archivo (fecha + responsable). Si cambia algo después, se re-registra y se avisa al cliente.

## 4. Correr el diagnóstico

- [ ] Verificar la tabla `PRECIOS` arriba de `diagnostico/diagnostico.py` contra el pricing publicado de cada proveedor.
- [ ] Validar el CSV (el script rechaza columnas/valores/modelos inválidos; no arreglar datos a mano).
- [ ] Correr, por ejemplo:
  ```bash
  python3 diagnostico/diagnostico.py trazas.csv \
    --tipo-mapa '{"tipo_1":"simple","tipo_2":"razonamiento"}' \
    --volumen '{"tipo_1":12000,"tipo_2":800}' \
    --cliente "[CLIENTE]" --salida informe-[CLIENTE].md
  ```
- [ ] Leer el informe completo, **incluida la sección 4 (supuestos y límites)**, antes de la llamada.
- [ ] Si el diagnóstico dice que ya están bien ruteados: el informe lo dice y no hay segunda llamada. Eso también es un buen resultado (honestidad = reputación).

## 5. Llamada de 20 minutos — agenda

1. **5'** — Criterios: qué se midió, con qué vara (la pre-registrada, ya en su poder).
2. **10'** — Números: costo por tipo hoy, qué recomendaría el router ex post, ahorro estimado con su intervalo de confianza. Sin redondeos optimistas.
3. **5'** — Siguientes pasos: si los números cierran → cotizar; si no → cerrar con el informe.

## 6. Cotizar el siguiente paso (según `OFERTA.md`)

| Opción | Cuándo ofrecerla | Precio |
|---|---|---|
| Auditoría Express | Hasta 3 tipos de consulta, quick wins claros | US$ 750 |
| Auditoría Completa | Workload completo, oráculo en 3+ proveedores | US$ 2.500 |
| Completa + Piloto de router | Solo si el diagnóstico mostró ahorro con IC95 > 0 | US$ 5.000 |

Reglas:
- La cotización final se fija **después** del diagnóstico, con volumen y complejidad conocidos.
- El piloto **solo se factura si la auditoría mide ahorro ≥ 15%** (condición de `OFERTA.md`).
- **No prometer ningún % de ahorro antes de medir.** La vara pre-registrada es sagrada también acá.

## 7. Cierre administrativo

- [ ] Guardar en `producto/auditorias/clientes/[CLIENTE]/`: NDA firmado, vara congelada, CSV recibido, informe generado.
- [ ] Eliminar las trazas del cliente al cerrar el caso (o a su requerimiento), conservando solo agregados anónimos si el NDA lo autoriza.
