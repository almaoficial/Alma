# Integración E3 al servicio vivo — 2026-09-28

**Decisión del usuario**: "hacelo" (chat 28/9 ~00:32). El mecanismo E3
(tercer split ciego) queda integrado al promotor vivo del servicio
(puerto 8471).

## Qué se integró

1. **`alma_service/puerta_e3.py`** (nuevo): la implementación validada
   en mock (16/16 tests, `resultados/e3-tercer-split-20260928/`) con la
   configuración del servicio. La regla pura no cambió.
2. **`alma_service/metaloop.py`**: nuevo método `_puerta_e3()` cableado
   en `_correr_bg` entre la puerta de dos splits y la auto-adopción.
   El audit record final usa `audit_record_e3`; la evidencia, el ciclo
   `metaloop_puerta`, el evento `corrida_finalizada` y el pre-registro
   llevan los campos E3 (`delta_e3`, `e3_exigido`, `e3_evaluado`).
3. **`servicio/server.py`**: el bloque `gobernanza` de `/fase2/estado`
   ahora incluye `e3` con la configuración vigente.

**No tocado (núcleo intocable)**: `gate.py` (definición de la puerta),
`presupuesto.py` (topes), mecanismo de notificaciones. El E3 solo
endurece la puerta; nunca la relaja (si los dos splits rechazan, el E3
ni se evalúa).

## Los dos defaults (delegados por el usuario, documentados)

1. **Qué datos corren el split ciego** → `E3_REPS = [500, 501]`:
   réplicas del stream mock reservadas para auditorías, nunca usadas en
   E1 (train [0,1,2]), E2 (held-out [3,4]), benchmark ([0..4]) ni ningún
   experimento (EXP64 usó 100-119). **Provisional**: hasta que el
   servicio tenga datos de operación real, el E3 corre sobre mock
   held-out reservado.
2. **`margen_min = 5.0`** puntos de regret. El benchmark propio tiene una
   sola corrida (mejora 0.0: el vigente es el baseline) → sin variación
   Δ split-a-split observable → dato insuficiente → default conservador
   ("E3 exigido ante la duda"). Los efectos ganadores validados son
   ~5-10 puntos (EXP56: 6.20, EXP64: 6.55); margen < 5 en algún split es
   duda → E3. **Recalibrar** cuando haya datos propios split-a-split.

Superficie del meta-loop: `"parametro"` (muta hiperparámetros, no la
maquinaria probe/skip/gate/prior).

## Tests (mock, US$0, antes de tocar el vivo)

- `test_puerta_e3` 16/16 contra el módulo integrado (copia
  comportamiento-idéntica).
- `alma_service/test_e3_integracion.py` 17/17: defaults, regla pura,
  cableado (short-circuit, veto, fail-closed, kill switch).

## Estado del servicio

- Reinicio controlado 28/9 ~00:35 (parar.sh → arrancar.sh), pid 6775.
- `/fase2/estado` 200: sano; `gobernanza.e3` visible con la config.
- Integración asentada en el ledger (`integracion_e3`,
  hash a70ede9b6b70bd62…) y en el event log.
- Gasto API: US$0.

## Cómo revertir

**Revert rápido (vuelve a la puerta de dos splits)**:
1. En `alma_service/puerta_e3.py`: `E3_HABILITADO = False`.
2. Reiniciar: `cd servicio && ./parar.sh && ./arrancar.sh`.
3. Verificar: `gobernanza.e3.habilitado == false` en `/fase2/estado`.

**Revert total**: restaurar los backups
(`/tmp/metaloop.py.bak`, `/tmp/server.py.bak`), borrar
`alma_service/puerta_e3.py` y `alma_service/test_e3_integracion.py`,
reiniciar. El ledger conserva el registro de la integración.
