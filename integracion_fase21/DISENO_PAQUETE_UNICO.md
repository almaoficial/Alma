# Paquete único autogestionado — diseño de arquitectura (US$0, sin código)

**Fecha:** 2026-09-27. **Estado:** solo diseño, nada construido, nada gastado.
Aprobado por él: "Lo hagamos" (diseño del paquete donde ALMA gestiona todo).

## 1. La idea en una frase

Hoy ALMA es un **servicio que corre** (`alma_service/`, puerto 8471) más un
**laboratorio suelto** (`integracion_fase21/`, scripts de experimentos) más un
**observador aparte** (`servicio/trazas.py`). El paquete único los junta en un
solo sistema donde el ciclo de mejora —minar debilidades de las trazas reales,
proponer ediciones, validarlas con el harness congelado, promoverlas con
aprobación humana— corre **dentro** del servicio, no en scripts sueltos.

Lo que NO cambia: el loop sigue sin poder tocar al validador, las reglas de
seguridad siguen siendo código determinístico fuera del modelo, y ninguna
promoción entra sin evidencia falsable.

## 2. Lo que existe hoy (verificado en el código, no asumido)

**Núcleo operativo** — queda tal cual:
- `memoria.py`: experiencias en SQLite con olvido 0,5^días + evicción +
  cuarentena de procedencia (fail-closed con allowlist de orígenes internos).
- `skills.py`: índice AgentSkills con presupuesto duro de contexto.
- `recurrencia.py`: detector compuerta entre modo adaptativo y loop de skills.
- `resolver.py`: la política validada (probe → Thompson con prior n0=4 →
  skip con umbral 1+floor(K/3) → gate Q1). Defaults en `scaffold.py`.
- `curator.py`: active → stale → archived + ablación por evidencia.
- `harness.py`: puerta de calidad (pre-registro en disco ANTES de correr,
  réplicas pareadas, veredicto contra criterio).
- `benchmark.py`: informe independiente en mundo congelado.
- `revision.py`: revisión heurística de background con **gate de
  consentimiento** (todo queda en pendientes hasta aprobación explícita).
- `presupuesto.py`: topes duros por bucket; sin `ALMA_PRESUPUESTO_MENSUAL`
  configurado, la key arranca **apagada** (modo barato forzado).
- `heterogeneidad.py`: detector de unanimidad del probe (EXP68, en
  validación — aún no integrado al servicio).

**Ciclo de mejora (existe, pero sobre experimentos, no sobre el servicio):**
- `metaloop.py`: RSO semanal — muta 5 hiperparámetros del scaffold, keep/revert,
  adopción solo si pasa `PuertaDosSplits`, audit record por propuesta, ledger
  con hash encadenado. **Hoy auto-adopta** (sin freno humano en la promoción).
- `debilidades.py`: `MineroDebilidades` por firmas exactas — **describe, no
  prescribe** (lección EXP58: el que atribuye y prescribe es peor que el azar).
  Hoy se alimenta de keeps/reverts del metaloop, no de trazas del servicio.
- `gate.py`: `PuertaDosSplits` — Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max > 0. Pura,
  determinista, sin LLM. No evalúa: recibe números del validador congelado.

**Seguridad (frenos determinísticos, ya en vivo, 9/9 ataques bloqueados):**
- `politicas.py`: default-deny sobre herramientas, `verificar_ruta` con
  realpath, allowlist de aprobadores = ("humano",).
- `procedencia.py`: lo no-propio nace en cuarentena y no alimenta decisiones.
- `verificacion.py`: loops con criterio de parada declarado a priori.
- `confianza.py` + `versiones.py` + `admision.py`: provisional → trusted solo
  con ≥3 éxitos **verificados por fuente independiente** (auto no vale); scan
  determinista del SKILL.md en la admisión.

**Lo suelto (fuera del servicio):**
- `integracion_fase21/`: scripts EXP63–68, resultados, `DISENO.md`.
- `servicio/trazas.py` + `trazas.db`: observador que registra
  tarea → estrategia → resultado → feedback del **asistente**, no del servicio.
  Es otro mundo: no lo ve el minero ni el metaloop.

## 3. Diagrama del paquete único

```
┌─────────────────────────────────────────────────────────────┐
│                    PAQUETE ALMA (puerto 8471)                 │
│                                                             │
│  ┌──────────────┐   decisiones    ┌──────────────────────┐   │
│  │   NÚCLEO     │ ─────────────▶  │   TRAZAS UNIFICADAS  │   │
│  │  operativo   │   (probe, brazo, │  event log SQLite    │   │
│  │ (resolver,   │    reward, costo,│  único y estructurado│   │
│  │  memoria,    │    latencia)     │                      │   │
│  │  skills,     │                  └──────────┬───────────┘   │
│  │  curator)    │                              │ firmas exactas│
│  └──────────────┘                              ▼               │
│                                   ┌──────────────────────┐    │
│  ┌──────────────┐   propone       │  MINERO DEBILIDADES  │    │
│  │  PROMOTOR    │ ◀────────────── │  (describe, nunca    │    │
│  │ (staging →   │   paquete de    │   prescribe)         │    │
│  │  aprobación  │   evidencia     └──────────────────────┘    │
│  │  humana →    │                                             │
│  │  commit)     │   ┌──────────────────────┐                  │
│  └──────┬───────┘   │  PROPONENTE          │                  │
│         │ commit    │  (mutación acotada   │                  │
│         ▼           │   sobre espacio      │                  │
│  ┌──────────────┐   │   pre-registrado)    │                  │
│  │  VERSIONES   │   └──────────┬───────────┘                  │
│  │ (DAG + hash, │              │ candidato                    │
│  │  rollback)   │              ▼                              │
│  └──────────────┘   ┌──────────────────────┐                  │
│                     │  VALIDADOR CONGELADO │ ◀── NUNCA lo     │
│                     │  harness + 2 splits  │     toca el loop │
│                     │  + puerta de 2 splits│                  │
│                     └──────────┬───────────┘                  │
│                                │ PASS → staging               │
│                                │ FAIL → se descarta           │
│                                ▼                              │
│                     ┌──────────────────────┐                  │
│                     │  FRENO HUMANO        │                  │
│                     │  (aprueba / rechaza) │                  │
│                     └──────────────────────┘                  │
│                                                             │
│  FRENOS (todo el perímetro, código determinístico):         │
│  políticas default-deny · procedencia+cuarentena ·           │
│  presupuesto con topes duros · verificación a priori ·      │
│  scan de admisión · audit ledger con hash                    │
└─────────────────────────────────────────────────────────────┘
```

## 4. Contratos entre piezas (qué le entrega cada una a la otra)

1. **Núcleo → Trazas**: cada decisión del resolver asienta un evento
   `(ts, firma_régimen, veredicto_probe, brazo_elegido, reward, costo_usd,
   latencia_ms, scaffold_versión)`. El núcleo no sabe quién lo lee.
2. **Trazas → Minero**: el minero lee solo eventos con `reward` medido y
   agrupa por **firma exacta** `(firma_régimen, brazo, tramo_reward)`.
   Entrega `paquete_evidencia()`: clusters con soporte, sin prescripción.
3. **Minero → Proponente**: el paquete de evidencia va al **pre-registro**
   como contexto auditado. El proponente NO lo usa para dirigir mutaciones
   (EXP58); propone del espacio acotado pre-registrado.
4. **Proponente → Validador**: un candidato + pre-registro escrito en disco
   antes de la primera réplica. El validador corre réplicas pareadas y
   devuelve `(Δ_in, Δ_ho)`.
5. **Validador → Puerta**: los dos deltas. La puerta devuelve
   aceptado/rechazado + motivo. Si FAIL, el candidato se descarta y queda en
   el ledger como rechazado (evidencia, no basura).
6. **Puerta → Promotor**: solo los PASS llegan a staging. El promotor
   versiona (DERIVED/FIX según `versiones.py`), deja el cambio en
   `staging` y **pide aprobación humana**.
7. **Humano → Promotor**: aprueba o rechaza (allowlist: "humano"). Si
   aprueba, commit + audit record con lineage; si rechaza, el staging se
   archiva con el motivo. Rollback disponible por el DAG de versiones.

## 5. Trazas unificadas (lo que falta construir)

Hoy hay dos mundos: `trazas.db` del observador (estrategias del asistente)
y los ledgers sueltos del servicio. El diseño:

- **Un event log** en SQLite dentro del servicio: tabla `eventos_decision`
  (el contrato del punto 1) + tabla `eventos_ciclo` (propuestas, veredictos
  de puerta, aprobaciones — hoy dispersos en `metaloop_ledger.jsonl` y
  `revisiones_pendientes`).
- **El observador no se mezcla**: `servicio/trazas.py` registra conducta
  del asistente con feedback del usuario; el event log registra decisiones
  del servicio con reward medido. Son señales distintas con semántica
  distinta. Se mantienen separados pero consultables juntos (mismo
  directorio, prefijo distinto). Mezclarlos contaminaría al minero.
- **Retención**: el event log rota con la misma política de olvido de la
  memoria (lo viejo pesa menos, lo en cuarentena se archiva primero).

## 6. El ciclo de autogestión, paso a paso

1. **Minar** (semanal, o a pedido): el minero reconstruye clusters desde el
   event log. Solo describe.
2. **Proponer**: el proponente genera UN candidato del espacio acotado
   vigente (hoy: los 5 hiperparámetros del scaffold). Escribe el pre-registro.
3. **Validar**: el harness corre el candidato contra el validador congelado;
   la puerta de dos splits decide. Sin regresión en ningún split.
4. **Staging**: el PASS se versiona y queda pendiente.
5. **Aprobar (humano)**: él aprueba o rechaza desde un endpoint de solo
   lectura + acción explícita. **Default: sin su "sí" no hay commit.**
6. **Promover o archivar**: commit con audit record, o archivo con motivo.
   Todo queda en el ledger con hash encadenado.

## 7. Frenos: qué protege cada paso

| Paso del ciclo | Freno determinístico | Qué evita |
|---|---|---|
| Minar | Firmas exactas, sin LLM; minero describe, no prescribe | Heurísticas que atribuyen mal y prescriben peor (EXP58) |
| Proponer | Espacio de mutación acotado y pre-registrado | El loop inventando arquitectura (anti-DGM) |
| Validar | Validador congelado; el loop no lo toca ni lo importa como editable | Goodhart contra el propio examen |
| Puerta | Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max > 0; trade-offs rechazados | Sobreajuste que mejora un split y rompe otro (EXP65) |
| Staging | `verificar_ruta` (realpath), políticas default-deny | Escrituras fuera de la raíz, herramientas no listadas |
| Aprobar | Allowlist de aprobadores = ("humano",); sin aprobación no hay commit | Auto-promoción del loop |
| Commit | Versionado FIX/DERIVED + DAG con hash; rollback | Cambios sin lineage ni vuelta atrás |
| Todo | Presupuesto con topes duros; key apagada sin tope | Gasto no autorizado |
| Memoria/skills | Procedencia + cuarentena fail-closed; scan de admisión | Inyección vía memoria o skills de terceros |
| Revisión bg | Gate de consentimiento (pendientes) | Escrituras silenciosas del loop |

## 8. Plan de migración por fases

**Fase 2.2 — Trazas unificadas (primero, es el cimiento).**
Construir el event log del servicio; el minero empieza a leer trazas reales
en vez de solo keeps/reverts del metaloop. El observador del asistente queda
separado (decisión de diseño §5). El metaloop sigue igual por fuera: por
dentro, sus audit records ya citan evidencia de trazas reales. US$0.

**Fase 2.3 — Autogestión con freno humano.**
Cablear el ciclo completo §6 dentro del servicio: proponente → validador →
puerta → staging → aprobación humana → commit. **Cambio de contrato
deliberado**: el metaloop deja de auto-adoptar; toda promoción espera su
"sí". El laboratorio suelto (`integracion_fase21/`) pasa a ser archivo
histórico: los experimentos nuevos se corren desde el servicio. US$0.

**Fase 2.4 — Ampliación del espacio (solo con evidencia).**
Si el EXP68 pasa su validación a dos puntas, el detector de heterogeneidad
entra como meta-regla del servicio y sus parámetros (K, J) entran al espacio
de mutación con pre-registro nuevo. El espacio de mutación **solo crece**
con experimento pre-registrado que lo justifique. Las ediciones de código
siguen vetadas.

## 9. Lo que NO se toca (líneas rojas)

- **El validador congelado**: oráculo, stream, cómputo de regret, splits.
  Ninguna regla, ningún loop, ningún humano apurado lo edita para que un
  experimento "pase".
- **Fase 0/1 intactas**: los cambios son aditivos; la puerta bit-idéntica
  sigue verde.
- **Generación de skills por LLM**: archivada con números (fase 1: 0,000).
  La admisión de skills sigue siendo humana/aprobada.
- **Las reglas de seguridad no tocan el espacio de hipótesis**: frenan
  acciones, no ideas (principio del 27/9).
- **Detector LLM = telemetría, nunca control** (doctrina Song).

## 10. Decisiones que requieren su criterio

1. **Aprobación humana**: ¿todas las promociones, o auto-promoción si el
   Δ_ho supera un umbral que él fije?
2. **Ámbito del ciclo**: ¿solo hiperparámetros del scaffold, o también
   skills y el detector de heterogeneidad cuando estén validados?
3. **Dónde corre 24/7** de forma permanente (pendiente de fase 2).
4. **Tope mensual en US$** (pendiente de fase 2) — habilita el proveedor real.
5. **Tercer split ciego (E3)**: ¿entra al paquete o queda como trabajo futuro?
6. **Idioma del observador**: el event log registra en inglés técnico por
   defecto — ¿se mantiene así o se bilingüiza?
