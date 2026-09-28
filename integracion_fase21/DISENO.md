# Integración fase 2.1 — Self-Harness + OpenSpace → ALMA real

**Fecha:** 2026-09-27. **Costo:** US$0 (sin API key, sin LLM). Todo determinista.

Fuentes: `research_notes/self-harness-shanghai-lab-20260927-2158/report.md`
(Shanghai AI Lab, arXiv:2606.09498) y
`research_notes/openspace-hkuds-skills-20260927-2200/report.md`
(HKUDS, OpenSpace v2).

## Principio rector

ALMA ya archivó con números la vía generativa (fase 1: diferencia
conductual 0,000; EXP61: +0,40 vs oráculo perfecto). Por eso esta
integración toma de los estudios **la disciplina, no el generador**:
gates, firmas deterministas, audit trails y ciclos de confianza. Nada de
lo integrado propone contenido con un LLM.

## Qué se integra, dónde, por qué

### A. Meta-loop — de Self-Harness (`alma_service/gate.py`, `debilidades.py`)

| Hallazgo del estudio | Integración | Dónde |
|---|---|---|
| Regla de aceptación `Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max > 0` (§3.4): sin regresión en ningún split | `PuertaDosSplits.aceptar()` reemplaza la adopción "held-out estrictamente mejor" por la regla de dos splits (estrictamente más exigente: ahora también se exige no-regresión en train) | `metaloop.py::_correr_bg` (adopción final) |
| Audit record por propuesta (§3.3): mecanismo objetivo, superficie, efecto esperado, riesgo | Evento `audit_propuesta` en el ledger por cada mutación (ronda: delta train + keep/revert; adopción final: deltas de ambos splits + veredicto de la puerta) | `metaloop.py::_correr_bg` |
| Weakness mining por **coincidencia exacta** de firmas verificador-ancladas (§3.2), deliberadamente sin LLM | `MineroDebilidades`: clusteriza firmas exactas; el paquete de evidencia **no prescribe ediciones** (principio del paper) — solo audita contexto | `debilidades.py`; el metaloop lo alimenta con sus keeps/reverts históricos y lo asienta en el pre-registro |
| Keep/revert explícito; rechazados no tocan el harness activo (§3.4) | Ya existía; ahora cada decisión pasa por la puerta y queda en el ledger con su veredicto | `gate.py` + ledger existente |

**Por qué así y no de otra forma:** el EXP58 mostró que una heurística que
*atribuye* fallos para *prescribir* cambios es peor que el azar. El paper
resuelve esto separando evidencia de prescripción: el miner describe, el
gate decide. Nuestro proponente sigue siendo mutación aleatoria validada
(EXP56/57) — el miner no la dirige, solo la audita. Además, por
arXiv:2605.30621 la capacidad de proponer es plana entre modelos: nuestro
proponente es el más barato posible (azar), lo que ya satisface la
recomendación de "proposer barato".

### B. Curator — de OpenSpace (`alma_service/confianza.py`, `versiones.py`, `admision.py`)

| Hallazgo del estudio | Integración | Dónde |
|---|---|---|
| Ciclo provisional→trusted con degradación reversible por fallo atribuible | `ConfianzaSkills`: dimensión ortogonal a active/stale/archived (que no se toca). Nace `provisional`; ≥3 usos exitosos independientes → `trusted`; fallo atribuible explícito → vuelve a `provisional` (reversible) | `confianza.py` (tabla propia `skill_confianza`; el schema de `skills.py` no se modifica) |
| Métricas por skill sin intervalos de confianza (crítica OMNEX) | `metricas()` con intervalo de Wilson para la tasa de éxito; `None` si n=0 | `confianza.py` |
| Taxonomía FIX/DERIVED/CAPTURED + version DAG (audit trail) | `VersionadorSkills`: FIX repara in-place (misma identidad, v+1), DERIVED especializa (nuevo path, link al padre), CAPTURED crea de novo con evidencia; DAG con hash encadenado por skill | `versiones.py` (tabla `skill_versiones`) |
| Admission pipeline Trigger→Evidencia→Decisión→Admisión→staging→validación→commit | `PipelineAdmision`: 6 etapas explícitas; la decisión es gate humano (mismo patrón que `revision.py`); la validación es determinista (SKILL.md parsea, frontmatter válido, entra en presupuesto); el commit registra como **provisional** y abre versión CAPTURED | `admision.py` (tabla `admision_casos`) |
| Trigger de degradación de tools en batch | `revision.py::_detectar` ahora clusteriza feedbacks negativos por **firma exacta** (clase, arch_id, tramo) en vez de solo por clase — determinista, US$0 | `revision.py` + `debilidades.py` |

**Cableado entre piezas:** admisión → nace `provisional` → uso con
`marcar_uso(path, exito=...)` → métricas con IC → ≥3 éxitos → `trusted` →
fallo atribuible → `provisional` (reversible). El ciclo active/stale/archived
del Curator sigue intacto y primario contra el bloat (OpenSpace genera
~3.3 skills/tarea sin archivado por desuso documentado; nosotros no
repetimos ese error).

## Qué NO se integra (y por qué)

1. **Proponente/evolver LLM** (Self-Harness §3.3, OpenSpace `evolver.py`):
   la evidencia propia lo veta — fase 1 (0,000) y EXP61 (+0,40). La
   generación de contenido de skills queda humana/aprobada.
2. **Compartir skills entre agentes / heredar trust ajeno** (hub de
   OpenSpace): su evidencia de calidad es auto-atestiguada y el "shared
   brain" propaga errores igual que mejoras. Regla: el trust nunca se
   importa; toda skill externa nace `provisional` + cuarentena local.
3. **Métrica de ahorro warm-vs-cold** sin contar el costo del loop: no se
   mide; el costo se trackea por tarea (presupuesto.py ya lo hace).
4. **Held-out como gate y como reporte final** (presión de selección,
   crítica del estudio): el gate usa held-out como el paper, pero el
   informe independiente lo da `benchmark.py` (mundo congelado, baseline
   fijo). Un tercer split ciego queda como trabajo futuro (experimento E3
   del informe).
5. **Fusión de múltiples ediciones aceptadas sin test de interacción**
   (modo de fallo §5.9 del informe Self-Harness): no aplica por
   construcción — el metaloop adopta UN candidato por corrida (greedy
   secuencial), nunca fusiona varios en paralelo.
6. **Montar OpenSpace como dependencia**: pre-1.0, PyPI colisionado,
   historial opaco. Se usan sus ideas, no su código (recomendación
   literal del informe).

## Garantías preservadas

- **Fase 0/1 intactas**: ningún módulo de fase 0/1 se modifica
  (`skills.py`, `harness.py`, puerta bit-idéntica). Los cambios son
  aditivos: tablas nuevas con `IF NOT EXISTS`, columnas nuevas en tablas
  propias, eventos nuevos en ledgers (los tests existentes no los
  restringen).
- **Validador congelado**: `gate.py` no toca e47/e56; solo aplica la regla
  de aceptación sobre números que el validador ya produjo.
- **Presupuesto duro**: `metaloop.py` sigue gateado por `autorizar()`; la
  admisión no gasta (validación determinista US$0).
- **Sin LLM en ningún camino nuevo**: minería por coincidencia exacta,
  validación por checks deterministas, decisión por gate humano.
- **El servicio sigue en pie**: `server.py` solo suma singletons y una
  sección en `/fase2/estado`; nada del camino crítico cambia.

## Archivos nuevos

- `alma_service/gate.py` — `PuertaDosSplits` (regla + audit record)
- `alma_service/debilidades.py` — `MineroDebilidades` (firmas exactas)
- `alma_service/confianza.py` — `ConfianzaSkills` (provisional→trusted)
- `alma_service/versiones.py` — `VersionadorSkills` (FIX/DERIVED/CAPTURED + DAG)
- `alma_service/admision.py` — `PipelineAdmision` (6 etapas)
- `test_fase21_*.py` — 5 suites nuevas (convención: scripts planos)

## Archivos tocados (solo aditivo)

- `alma_service/metaloop.py` — adopción por `PuertaDosSplits`; evento
  `propuesta_ronda`; evidencia del minero en pre-registro; campos gate en
  `estado()["ultima_corrida"]`
- `alma_service/revision.py` — `_detectar` clusteriza por firma exacta
- `servicio/server.py` — singletons nuevos + sección `curator_fase21` en
  `/fase2/estado`

---

# §2 — Segunda integración: los tres maestros → ALMA fase 2.1 (2026-09-27)

Estudio: `~/workspace/research_notes/tres-maestros-agentes-20260927-2216/report.md`
(Yao / Cherny / Song). Todo US$0, sin API keys. Regla de inclusión: una
idea entra solo si evita repetir un error ya pagado; ninguna toca el
espacio de hipótesis.

## Lo integrado, por maestro

### Dawn Song — seguridad determinista (no probabilística)
- `alma_service/politicas.py` — **puerta determinística de políticas**
  sobre llamadas a herramientas, estilo Progent: política simbólica de
  least privilege evaluada por CÓDIGO, nunca por un LLM. Default-deny
  (lo no listado está prohibido); `verificar_ruta` confina `path` a la
  raíz de skills (deniega escapes `..`); monotonic confinement —
  `estrechar` aplica de inmediato, `solicitar_ampliacion` queda
  pendiente hasta aprobación humana explícita. Ledger con hash
  encadenado. **SIN_CUBRIR** documenta los límites (sin sandbox de
  ejecución, inyección vía memoria mitigada no eliminada, la política
  no se auto-genera con LLM).
- `alma_service/procedencia.py` — **procedencia + cuarentena** para
  memoria y skills (AgentPoison, ClawHavoc): origen
  propio/tercero/importado; lo no-propio nace en cuarentena y NO
  alimenta decisiones hasta graduación explícita. La evicción archiva
  primero lo en cuarentena (el olvido como higiene de seguridad).
- Wiring: `admision.py` — check `politica_allowlist` en la validación
  (cada `herramientas:` declarada debe estar en la allowlist);
  `confianza.py#importar_externa` acepta `procedencia` y registra
  origen tercero; `memoria.py` — cuarentena excluida de
  `recuperar_con_decaimiento`/`experiencias_detalle`, evicción la
  archiva primero.

### Boris Cherny — verificación y rutinas
- `alma_service/verificacion.py` — **loop producir→observar→comparar→
  parar** con criterio de parada DECLARADO A PRIORI
  (`declarar_criterio` valida; sin criterio no hay loop). Tipos:
  rondas_fijas, sin_mejora, umbral_mejora. Trail audita cada paso.
- `metaloop.py` — el loop RSO ahora corre sobre `LoopVerificacion`
  (keep/revert intacto en comparar/on_paso); el criterio va al
  pre-registro. **Rutina**: cada corrida reconstruye el minero desde el
  ledger al inicio (`_reproducir_mineria`) — memoria compartida,
  contexto no compartido; nada in-memory cruza corridas.
- `curator.py` — **ablación por evidencia**: registro de evitaciones
  (`registrar_evitacion` / `notificar_uso_exitoso` — solo si el fallo se
  repitió ≥2 veces en la misma firma); `ablacion_por_evidencia`
  archiva skills curables viejas sin registro de haber evitado un fallo
  repetido (gracia 30 días para las nuevas; externas no curables no se
  tocan). Corre en `correr_ciclo` (que mantiene su contrato: retorna la
  lista de transiciones); el detalle va al ledger y a
  `ciclo_con_ablacion`.

### Shunyu Yao — la interfaz y el loop pesan más que el modelo
- `alma_service/aci.py` — **las 4 reglas ACI como checklist**:
  1. `resumir` (topes en salidas — aplicado a la evidencia de admisión),
  2. `editar_con_guardrails` (validar antes de escribir, atómico —
     aplicado al commit de admisión),
  3. `resultado`/`sin_resultados` (feedback explícito siempre),
  4. `curar_contexto` (dropear errores viejos salvo el primero,
     colapsar observaciones).
- **EXP63 (FAIL)**: variante pass^k del tratamiento — el Thompson se
  alimenta con puntaje de consistencia pass^3 (k=3), contabilidad de
  regret intacta. Puerto verificado bit-idéntico a EXP51 (k=None).
  Resultado: efecto_medio **+11.0**, IC95 [4.74, 17.26], 4/5 réplicas en
  contra. Diagnóstico post-hoc: pass^3 binariza la señal y destruye el
  gradiente que el Thompson necesita. Consecuencia pre-registrada: se
  conserva el objetivo anterior (media de un intento).
  `integracion_fase21/passk.py`, `exp_passk.py`,
  `resultados/exp63-passk-20260927/`.

## Lo que NO se integra (y por qué)

- **Defensas a nivel modelo contra prompt injection** (12/12 caídas a
  >90% ASR ante atacantes adaptativos — la doctrina de Song es
  enforcement determinístico fuera del modelo, que es lo integrado).
- **Auto-reflexión del loop contra su propio juicio** (Yao: la
  auto-reflexión solo funciona contra señal externa; el RSO ya usa el
  validador congelado como señal externa).
- **Ablación del harness por modelo / system prompts mínimos**
  (Cherny lo hizo con Opus 5 y contexto masivo; nuestro harness ya es
  mínimo y determinista — no hay qué podar).
- **Sub-agentes paralelos con memoria compartida** (Cherny f habla de
  loops multi-agente; ALMA corre un loop único — se integra la parte
  aplicable: rutina con estado reconstruido por corrida).
- **Generación de políticas con LLM** (el eslabón probabilístico de
  Progent — deliberadamente no implementado).

## Archivos nuevos (§2)

`alma_service/politicas.py`, `procedencia.py`, `aci.py`,
`verificacion.py`; `integracion_fase21/passk.py`, `exp_passk.py`,
`resultados/exp63-passk-20260927/`; tests `test_fase21_{politicas,
procedencia,aci,verificacion,rutina,ablacion}.py`.

## Archivos tocados (§2, aditivo)

`metaloop.py` (LoopVerificacion + rebuild del minero por corrida),
`curator.py` (evitaciones + ablación + correr_ciclo), `memoria.py`
(cuarentena), `admision.py` (puerta, guardrails, procedencia),
`confianza.py` (hook de procedencia en importar_externa).

## Verificación §2

- Nuevos: 14+13+10+7+6+7 = 57 checks en verde.
- EXP63: FAIL pre-registrado (+11.0, IC95 [4.74, 17.26]).
- Fase 2: 50/50 intactos. Fase 0/1: intactas.
