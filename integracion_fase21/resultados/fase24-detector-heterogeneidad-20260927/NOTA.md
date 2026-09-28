# Fase 2.4 — Detector de heterogeneidad (EXP68) integrado al servicio

**Fecha:** 2026-09-27 ~19:05 EDT. **Costo:** US$0, sin keys.
**Aprobación:** el usuario ("vamos nomas", ~19:02 EDT) — primera promoción
bajo el freno humano de fase 2.3, asentada en el event log como
`promocion_aprobada` con actor `humano` (evento id 5 en `alma_eventos.db`).

## Qué se integró

`servicio/motor_fase1.py` — el driver de bloques con problemas reales —
ahora corre el `DetectorHeterogeneidad` de `alma_service/heterogeneidad.py`
como meta-regla aditiva, con el cableado validado en EXP68 (modo "probe"):

- **Veredicto** = argmax estricto de las medias del probe MEDIDO (Q1+Q2
  efectivamente medidos). Nunca el fav del posterior (hallazgo de
  calibración EXP68: con decay=0,5 el posterior se enganchó al brazo
  equivocado).
- **K=3, J=3** congelados del pre-registro (`K_EXP68`/`J_EXP68` en el
  módulo; no se tunean).
- **Bloque saltado** (skip de skill): no alimenta al detector — no extiende
  ni reinicia la racha. **Empate** en el probe: reinicia la racha.
- **ENCOGIDO**: juega el brazo comprometido RAW en los 6 ítems (sin guía
  de skill — el veredicto se midió raw; el contrafáctico no se mide, misma
  honestidad que el skip). Cada J=3 bloques: **spot-check** — Q1+Q2=(0,1,3)
  miden los 3 brazos, se banca al comprometido; `resolver_spot_check` con
  margen de salida puede restaurar la exploración.
- **Fail-safe**: el detector es opcional (`detector_heterogeneidad=False`
  lo apaga) y si falla se desactiva para la sesión (`detector_desactivado`
  en el log) — el servicio sigue con la política vigente, que es el camino
  validado.
- **Trazas**: `detector_encoge` / `detector_restaura` / `detector_spot_ok`
  van al event log 2.2 (vía `trazas`, cableado externo como en motor.py).
- **No se tocó**: el scaffold vigente, la política del `Resolver`, ni el
  validador. Línea roja anti-auto-edición intacta.

## Docstring sincerado

`heterogeneidad.py` describía el diseño viejo (veredicto = fav del
posterior / brazo de skill). Se actualizó a lo validado: veredicto del
probe medido, skip sin veredicto, K/J congelados como constantes.

## Bug latente encontrado (y fixeado)

Los tests nuevos forzaron el camino de skip real y encontraron que
`Resolver.cerrar_bloque_saltado` crasheaba con `round(None, 4)` cuando el
contrafáctico no se mide (`acc_mejor=None`) — el skip real nunca había
disparado en tests. Fix mínimo en `alma_service/resolver.py`: `acc_mejor`
admite None y `misfire` queda None (desconocido, no 0). Sin cambio de
comportamiento para los llamadores existentes (bit-identidad intacta).

## Tests

- Nuevo `test_fase24_detector.py`: **26/26** — aditividad (sin disparo es
  bit-idéntico), enganche tras K unánimes, spot-check cada J, skip que no
  alimenta, empate que reinicia, fail-safe con detector roto, trazas.
- Suite completa: **28/28 archivos en verde** (incluida bit-identidad
  fase 0 y `test_fase1_motor.py` 12/12).

## Estado del servicio

Reiniciado sano en puerto 8471, `/salud` OK (verificado tras la
integración).
