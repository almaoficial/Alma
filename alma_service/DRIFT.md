# Drift de régimen — diseño del detector (fase 2.5)

**Fecha:** 2026-09-28. **Estado del detector:** implementado y
testeado en mock (ver `test_fase25_drift.py`, todo verde, US$0).
**Estado del cableado:** integrado al servicio vivo el 2026-09-28
como OBSERVABILIDAD (fase 2.5, `alma_service/drift_vivo.py`,
`test_fase25_drift_vivo.py` 39/39 verde) — ver §6. **No** integrado
como política: no fuerza re-probes ni re-ancla solo (eso sigue
pendiente de decisión explícita).

## Qué es

Un detector de cambio de régimen para el loop de ALMA: compara el
régimen actual contra un baseline anclado y dispara una señal cuando
el mundo cambió, para forzar re-probe.

Responde a un hueco real del sistema: el detector de heterogeneidad
(EXP68) aprende cuándo *no hay nada que descubrir* y encoje la
exploración, con spot-checks cada J bloques como red de seguridad.
Pero un flip del mundo en modo explorar (sin encoger) o entre
spot-checks no tiene señal propia: el loop sigue confiando en un
posterior viejo. El detector de drift es esa señal.

## Qué compara, ventana, umbral, señal

- **Qué compara:** el baseline = ganador estricto **medido** del
  probe (lección EXP68: nunca el brazo del posterior) + sus medias
  por brazo, anclado en un momento dado; contra la **ventana
  deslizante** de los últimos `W` veredictos de probe. Solo los
  bloques CON probe alimentan la ventana (convención EXP68): un
  bloque saltado no la extiende ni la diluye; un empate
  (`ganador=None`) no es contradicción.
- **Ventana:** `W = 6` bloques con probe (default provisional).
- **Umbral:** `M = 2` contradicciones estrictas en la ventana
  (otro ganador estricto ≠ baseline). Una sola no dispara (ruido);
  un flip real contradice casi todos los bloques → dispara en 2.
  Falso positivo estimado con p≈5% de contradicción por bloque
  estable: P(≥2 en 6) ≈ 3%.
- **Señal de salida:** `hay_drift()` (bool, **enclavada** hasta
  re-anclar el baseline) y `senial()` con detalle + acción
  recomendada `"re_probe"`. El detector no re-probea ni re-ancla
  solo: informa; el consumidor decide (ver §4).

Histéresis en dos direcciones: entrar exige M contradicciones en
ventana (no basta una); salir exige re-anclaje explícito (no basta
que la ventana vuelva a calmarse sola).

## Ejemplo trabajado

Baseline anclado en bloque 10: ganador medido `"single"`.
Veredictos de probe siguientes:

| bloque | veredicto | ventana | contradicciones | drift |
|---|---|---|---|---|
| 11 | single | [single] | 0 | no |
| 12 | cot | [single, cot] | 1 | no |
| 13 | single | [single, cot, single] | 1 | no |
| 14 | cot | […, cot] | 2 | **sí** → `re_probe` |

En el bloque 14 la señal se enclava. El consumidor fuerza un
re-probe completo; cuando los veredictos se estabilizan en el nuevo
régimen, re-ancla el baseline (`"cot"`) y la señal se libera.

Contra-ejemplo: una sola contradicción aislada
(`single, cot, single, single, single, single`) nunca dispara.

## Calibración pendiente (no congelada)

A diferencia de EXP68, los defaults W=6/M=2 **no están congelados
por pre-registro**: se eligieron por razonamiento sobre ruido, no
por validación. Antes de integrar, validarlos contra trazas de
operación real del servicio o un harness mock con flips
sintéticos (mundo que flipea a mitad del stream, midiendo latencia
de detección y tasa de falsos positivos). Eso es trabajo futuro,
mock, US$0.

## Integración propuesta (NO hecha)

El servicio vivo (puerto 8471) no se toca. La integración, cuando
el usuario la apruebe, seguiría el patrón aditivo de la fase 2.4
(`servicio/motor_fase1.py`):

## Integración al servicio vivo como observabilidad (HECHA, 28/9)

Lo que se cableó (frente 3, US$0) es la pata de OBSERVABILIDAD,
aditiva y sin tocar políticas — la integración como política (puntos
1–4 de la propuesta original: re-probe forzado) sigue NO hecha y
pendiente de decisión explícita:

- `alma_service/drift_vivo.py` — `MonitorDriftVivo`: lee los
  veredictos de probe MEDIDOS del event log unificado (fase 2.2) y
  corre el `DetectorDrift` sobre ellos en operación. Ante un cambio
  de régimen REGISTRA el evento (`drift-ledger.jsonl` en el dir de
  la DB + evento de ciclo `drift_detectado`) y lo EXPONE.
- Mapeo veredicto (lección EXP68): veredicto = argmax estricto de
  los rewards medidos en una decisión modo probe (`veredicto_probe`
  con `gap > 0` en extras); empate = sin veredicto. El detector
  recibe como "bloque" el id del evento de decisión.
- Anclaje: el primer veredicto medido observado ancla el baseline;
  el re-anclaje es explícito por `POST /drift/anclar` (la señal se
  enclava hasta entonces, como en el diseño).
- Endpoints nuevos en `servicio/server.py` (aditivos, el núcleo no
  se toca): `GET /drift/estado` (escanea + informa),
  `POST /drift/escanear` (para crons), `POST /drift/anclar`
  (`{"ganador"?: str}`), y bloque `fase25` en `/fase2/estado`.
  Kill switch: `ALMA_DRIFT_VIVO=0`.
- Fail-safe: cualquier excepción desactiva el monitor para la
  sesión; el servicio sigue igual.
- Núcleo intocable respetado: `motor.py` (resolver), `presupuesto`
  y topes no se modificaron; la notificación al usuario la maneja
  la capa de crons/chat (lee el ledger o `/drift/estado`).
- Calibración honesta: W=6/M=2 siguen siendo provisionales
  (diseñados para bloques, aplicados a decisiones sueltas) — ver
  el caveat en el docstring de `drift_vivo.py`.

Activación: requiere reiniciar el servicio (no se reinició el vivo
del puerto 8471). Ver `arrancar.sh` / comando documentado en el
reporte del frente.

## Archivos

1. `MotorFase1.__init__`: parámetro `detector_drift=False`
   (default off → bit-identidad con el vigente), aceptando `True`
   (crea `DetectorDrift(W=VENTANA_DRIFT, M=CONTRADICCIONES_DRIFT)`)
   o una instancia.
2. Anclaje del baseline: al arranque del motor con el primer
   veredicto de probe medido, y cada vez que el detector de
   heterogeneidad encoja (ahí el baseline natural es el brazo
   comprometido, que ya es un veredicto medido unánime).
3. Alimentación: en `correr_bloque`, después de cada probe medido,
   `detector_drift.registrar(bloque, ganador_estricto(medias))`.
   Bloques saltados o empatados no se registran.
4. Señal: si `hay_drift()`, el bloque siguiente corre con probe
   completo forzado (sin skip, sin encogido) y se asienta el
   evento `drift_re_probe` en el event log 2.2; cuando el loop
   confirme el nuevo régimen, `anclar_baseline` con el nuevo
   veredicto.
5. Telemetría: bloque `detector_drift` en `/fase2/estado` (como el
   de heterogeneidad), sin tocar el resto.
6. Fail-safe: cualquier excepción del detector → se desactiva para
   la sesión y el servicio sigue con la política vigente (mismo
   patrón que `detector_heterogeneidad`).

Núcleo intocable: `presupuesto.py` (topes de gasto) y la obligación
de notificar no se tocan; el detector no gasta, no evalúa con LLM,
no edita código.

## Archivos

- `alma_service/drift.py` — `DetectorDrift`, defaults
  `VENTANA_DRIFT`/`CONTRADICCIONES_DRIFT`. Puro, determinista,
  sin LLM, sin I/O.
- `alma_service/drift_vivo.py` — `MonitorDriftVivo`: envoltura con
  I/O que cablea el detector al servicio vivo (lee el event log,
  escribe `drift-ledger.jsonl`). Observabilidad, no política.
- `alma_service/DRIFT.md` — este documento.
- `test_fase25_drift.py` — suite mock (US$0), checks en verde.
- `test_fase25_drift_vivo.py` — suite del cableado vivo (US$0),
  39/39 en verde: monitor sobre trazas, registro del evento,
  fail-safe y end-to-end HTTP contra `server.py` real.
