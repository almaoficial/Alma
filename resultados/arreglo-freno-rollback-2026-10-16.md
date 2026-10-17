# Arreglo: desbloqueo del freno sin autorización + rollback que se deshace a sí mismo

Fecha: 2026-10-16 · Autorizado por Alejandro (16/10/2026) · Costo: US$0
Origen: dos hallazgos de una auditoría externa (ChatGPT) sobre
`alma_service/metaloop.py`, verificados en el código por el agente
principal antes de encargar este arreglo.

## Problema 1 — `desbloquear_freno()` no comprueba ninguna autorización

`desbloquear_freno(self, origen="humano")`: el origen viene «humano»
**por defecto** y el cuerpo nunca lo comprueba: resetea el freno de
estancamiento y asienta en el ledger el origen que le pasen. La
docstring promete «solo humano; el loop nunca se desbloquea solo» y el
código no lo garantiza. El freno existe para detener el loop tras 3
corridas planas hasta que una persona revise; hoy cualquier llamador
(una etiqueta, en rigor) lo levanta.

### Semántica elegida

- La autorización es un **token** que el método lee en el momento de
  la llamada de la variable de entorno **`ALMA_TOKEN_HUMANO`**
  (convención del árbol: `ALMA_FILTRO_SKILLS`, `ALMA_APROBACION_CARGA`,
  `ALMA_CURATOR_LLM` en `skills.py`/`curator.py` son configuración por
  entorno; el token nunca vive en el repo ni se commitea).
- Firma: `desbloquear_freno(self, origen="humano", token=None)`. El
  parámetro `origen` queda **solo como etiqueta de auditoría** que se
  asienta en el ledger; nunca autoriza nada.
- **Fail-closed**: si `ALMA_TOKEN_HUMANO` no está configurada (o está
  vacía), todo desbloqueo se rechaza. Si el token presentado falta o no
  coincide (comparación con `hmac.compare_digest`), se rechaza.
- Todo intento se asienta en el ledger: el aceptado con el tipo
  histórico `metaloop_freno_desbloqueado`; el rechazado con el tipo
  nuevo `metaloop_freno_desbloqueo_rechazado` y su motivo
  (`token_no_configurado` / `token_invalido`). Un rechazo no toca la
  fila del freno.
- El valor real del token NO se genera ni se configura en este
  arreglo: queda para cuando Alejandro lo defina en su entorno.
- Llamadores: el único llamador real es `test_metaloop_freno.py`
  (se adapta para configurar un token fixture en el propio test y
  pasarlo). El servicio (`servicio/server.py`) no expone endpoint de
  desbloqueo; no se agrega ninguno.

## Problema 2 — `revertir()` se deshace a sí mismo

`revertir()` restaura `historial[1]` y lo **agrega como versión nueva**
al historial (`_asentar_scaffold`). Una segunda llamada toma las dos
últimas versiones —la restaurada y la mala— y restaura la mala: el
rollback del rollback re-adopta lo que se acababa de sacar. No hay
ninguna prueba de la secuencia adopción → rollback → rollback. El
comportamiento actual es accidental.

### Semántica elegida: rollback caminando adopciones

- Se reproduce el historial de `scaffold_activo` en orden cronológico
  manteniendo la **pila de adopciones en efecto**: la primera entrada
  es la base (nunca deshacible); cada entrada posterior que no es un
  deshacer (auto-adopción, promoción aprobada u otro asentamiento
  hacia adelante) se apila como adopción en efecto, registrando su
  scaffold y el scaffold previo.
- Una entrada de deshacer (origen `rollback_manual` o
  `revertir_adopcion …`, esta última del `Promotor`) desapila las
  adopciones que deshizo: desde el tope, hasta **incluir** la adopción
  cuyo scaffold previo coincide con el scaffold que la entrada
  restauró (así un `revertir_adopcion` del Promotor sobre una adopción
  que no es la última también se refleja bien). Si ninguna coincide
  (entrada heredada inconsistente), no se desapila nada: ante la duda,
  `revertir()` podrá saltar una adopción vieja, pero jamás restaurar
  una ya sacada.
- `revertir()` deshace la adopción en efecto más reciente: restaura
  su scaffold previo asentándolo con origen `rollback_manual` y
  registra el evento `rollback` en el ledger (con la adopción
  deshecha identificada). Si la pila quedó solo con la base, devuelve
  `{"revertido": False, "motivo": "no hay adopción sin revertir"}`.
- Consecuencia clave: un segundo `revertir()` deshace la adopción
  **anterior**, nunca restaura la que el primer rollback sacó.
- La docstring de `revertir()` se reescribe para que la semántica
  escrita sea exactamente esta.

## Pruebas que lo cubren

Suite nueva `test_gobernanza_freno_rollback.py` (convención del repo:
funciones planas, sin pytest, `check()` + conteo PASS):

Freno / token:
1. Sin `ALMA_TOKEN_HUMANO` configurada: desbloqueo rechazado aunque se
   presente un token; el freno sigue activo; rechazo asentado.
2. Token presentado ausente (`None`) → rechazado y asentado.
3. Token incorrecto → rechazado y asentado; freno y racha intactos.
4. Etiqueta `origen="humano"` mentirosa sin token válido → no
   autoriza nada (rechazado).
5. Token correcto → desbloquea (freno limpio, racha 0) y el ledger
   registra el desbloqueo junto a los rechazos previos.

Rollback:
6. Secuencia completa: base → adoptar A → adoptar B → `revertir()`
   vuelve a A → segundo `revertir()` vuelve a la base (NO restaura B)
   → tercer `revertir()` devuelve False con motivo y no toca nada.
7. Intercalado: adoptar A → rollback (base) → adoptar C → rollback
   vuelve a la base deshaciendo C (no resucita A).
8. Deshacer del Promotor en el medio: adoptar A → adoptar B →
   `revertir_adopcion` del Promotor sobre A (restaura la base) →
   `revertir()` devuelve False (no queda adopción en efecto).
9. Sin adopciones: `revertir()` → False con motivo.
10. El ledger registra cada rollback con su restaurado y los pasos
    quedan en el historial con la semántica nueva.

Además se adapta `test_metaloop_freno.py` (token fixture) sin tocar
sus demás chequeos, y al cierre corre la batería completa de suites
de gobernanza (45 previas + la nueva = 46 archivos `test_*.py`).

## Resultados (cierre, 2026-10-16)

- **Arreglo 1 aplicado** en `alma_service/metaloop.py`:
  `desbloquear_freno(origen="humano", token=None)` lee el token
  esperado de `ALMA_TOKEN_HUMANO` en cada llamada, compara con
  `hmac.compare_digest` y rechaza fail-closed sin token configurado
  (`token_no_configurado`) o con token ausente/incorrecto
  (`token_invalido`). Los rechazos se asientan como
  `metaloop_freno_desbloqueo_rechazado` con motivo; el desbloqueo
  válido conserva el tipo histórico `metaloop_freno_desbloqueado`.
  No se generó ni configuró ningún valor de token.
- **Arreglo 2 aplicado**: `revertir()` camina la pila de adopciones
  en efecto (`_pila_adopciones()`), con la semántica de este memo en
  su docstring; el evento `rollback` del ledger suma
  `adopcion_deshecha_id` y `adopcion_deshecha_origen`.
- **Llamador adaptado**: `test_metaloop_freno.py` §7 configura el
  token fixture `token-fixture-freno` en el entorno del propio test
  y lo pasa al desbloquear. Ningún otro llamador de
  `desbloquear_freno` existe (el servicio no expone endpoint de
  desbloqueo). `revertir()` mantiene firma y forma de retorno; su
  llamador en `servicio/server.py` no necesitó cambios.
- **Suite nueva**: `test_gobernanza_freno_rollback.py` — **40/40
  PASS** (matriz de token: sin configurar / etiqueta sola / token
  incorrecto / token correcto, con rechazos asentados; secuencia
  adopción→rollback→rollback sin resucitar la versión sacada;
  intercalado con adopción posterior; deshacer del Promotor en el
  medio; sin adopciones → False).
- **Batería completa**: **46/46 archivos `test_*.py` en verde**
  (las 45 previas, incluida `test_metaloop_freno.py` adaptada, más
  la nueva). Sin regresiones.
