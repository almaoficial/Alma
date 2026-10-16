# ALMA — Fase 1: proveedor de skills real + motor cableado (2026-09-27)

Fase 0 construyó el scaffolding con un proveedor mock (la skill vivía en
el historial simulado). Fase 1 implementa la costura `ProveedorSkills`
sobre componentes reales y cablea el motor persistente al `Resolver`.

Costo de la fase: solo la validación con key (~US$0.03 estimado, tope
duro US$0.40, autorizado US$0.50). Todo lo demás (código, tests) US$0.

## Lo que se construyó

| Módulo | Qué hace | Origen |
|---|---|---|
| `alma_service/llm.py` | `ClienteMedido` (contabilidad tokens→USD por llamado) + `Presupuesto` (corte DURO previo al exceso). La key nunca se ve: el backend es `VaultBackend` (surrogate). | Diseño §4.3 (regla dura) |
| `alma_service/proveedor_real.py` | `ProveedorSkillsReal` (existe/brazo/soporte sobre `SkillIndex` + `MemoriaExperiencias`), `GeneradorSkills` (crea/refina SKILL.md con el modelo), `BackendConSkill` (la skill guía la ejecución vía system prompt), `ProveedorSkillsNulo` (modo adaptativo). | Diseño §1.1, §2 |
| `alma_service/memoria.py` (+tablas) | `probe_bloques`: resumen de probes por bloque para el soporte pareado; `experiencias_detalle()`: evidencia con enunciados para el generador. | Soporte del proveedor |
| `servicio/motor_fase1.py` | `MotorFase1`: loop persistente resolver→feedback. Bloques de 6 (Q1/probe, Thompson, Q2/re-probe, gate), decisiones del `Resolver` de fase 0, ejecución con `alma.executors`, reward exact-match binario, experiencias en SQLite, generación/refinamiento por bloque, compuerta de recurrencia. | Diseño §2, §2.1, §4.1 |
| `problemas_fase1.py` | Generador determinista de problemas (2 firmas, ground truth entero). | Validación |
| `run_fase1_puerta.py` | Validación con pre-registro previo. | Puerta de fase |

## Decisiones de diseño (fase 1)

1. **La skill es procedimiento, no solo prior.** `BackendConSkill`
   inyecta el cuerpo del SKILL.md en el system prompt cuando se juega el
   brazo recomendado. Los probes miden brazos raw (medición limpia); la
   explotación usa la guía. Sin esto, la skill real no agregaría nada
   sobre el prior condicionado del mock.
2. **El cuerpo no nombra el brazo.** La recomendación vive solo en el
   frontmatter (`recomienda_brazo`); el proveedor decide el brazo live
   desde memoria con decaimiento. El refinamiento dispara cuando ambos
   divergen.
3. **Skip sin contrafáctico.** En el camino de skip no se miden los otros
   brazos (medirlos anularía el ahorro): el misfire queda desconocido,
   no 0. Diferencia honesta vs el mock.
4. **Regla mock-first (AGENTS.md 27/9).** La validación NO compara
   tratamiento vs control en regret (EXP45–52 ya respondieron la
   aritmética del mecanismo; sería repetir EXP18). Cada dólar responde
   una pregunta que solo modelos reales pueden responder: calidad de
   generación, refinamiento, efecto conductual de la guía, operación
   mecánica end-to-end.
5. **Meta-loop sigue stub** (`alma_service/metaloop_stub.py`, fase 2+).

## La prueba (puerta de fase)

Pre-registro: `resultados/fase1-puerta/preregistro.json` — escrito ANTES
de gastar un centavo (disciplina del harness).

- **Parte A** (loop): 3 réplicas × 8 bloques × 6 problemas, seeds 11/22/33.
- **Parte B** (conductual): 20 problemas frescos por firma, brazo raw vs
  guiado, pareado.

Criterio PASS (pre-registrado): (1) skill válida en ≥2/3 réplicas,
(2) ≥1 refinamiento v2, (3) proveedor consultado (skills_usadas ≥ 1),
(4) detector en modo "skills", (5) costo ≤ US$0.50,
(6) diferencia pareada (guiada−raw) > 0.

## Resultado

**Veredicto: FAIL** (pre-registrado; reporte completo en
`resultados/fase1-puerta/`). Corrida 2026-09-27 ~16:15–16:45 EDT,
gpt-4o-mini, 3 réplicas × 8 bloques + probe conductual de 40 pares.
Costo total US$0.0412 (más ~US$0.007 entre el intento previo que
expuso un bug y el smoke test: total fase ≈ US$0.048, muy bajo el
tope US$0.50).

| Criterio | Resultado |
|---|---|
| (1) skill válida en ≥2/3 réplicas | ✓ — 2/2 firmas en las 3 réplicas |
| (2) ≥1 refinamiento v2 | ✓ — 1 por réplica (disparado por contradicción evidencia↔frontmatter) |
| (3) proveedor consultado | ✓ — skills_usadas = 4/réplica |
| (4) detector en modo "skills" | ✓ — la compuerta habilitó el loop |
| (5) costo ≤ US$0.50 | ✓ — US$0.0412 |
| (6) diferencia conductual (guiada−raw) > 0 | ✗ — **0.000, IC95 [0.000, 0.000]** |

### Honestidad incómoda

El loop funciona mecánicamente (genera, refina, consulta, mide, no se
pasa del presupuesto), pero **los procedimientos generados no cambian el
comportamiento del modelo**: en 40 pares, la ejecución guiada por la
skill dio exactamente el mismo resultado que el brazo raw.

Dos matices que no salvan el veredicto pero informan el rediseño:

1. **Efecto techo en aritmética**: el brazo raw ya acertó 20/20, así que
   el probe no podía detectar mejora ahí. Falla de diseño del probe
   (necesita headroom: problemas más duros o brazo raw más débil).
2. **Inercia real en razonamiento**: 17/20 en ambos brazos. Y las skills
   generadas explican por qué: son consejo genérico ("identificá los
   datos relevantes", "verificá cada paso") — lo que el modelo ya hace.
   El prompt de generación no exige procedimientos *discriminativos*
   (qué hacer distinto al brazo raw), así que produce obviedades.

Dato adicional: el brazo recomendado fue **inestable entre réplicas**
(aritmética→cot en rep0, →reflexión en rep1, →cot en rep2): con 6–11
experiencias por firma, el "ganador" es ruido. El refinamiento disparó
correctamente ante cada contradicción — el mecanismo anti-stale
funciona — pero también revela que las skills churnean con poca
evidencia.

### Qué implica (diseño §5, rama de rediseño)

La hipótesis "la skill como procedimiento en el prompt cambia la
conducta" quedó **refutada** en esta forma. Antes de fase 2, rediseñar:

- (a) generación que exija procedimientos discriminativos (contrastar
  contra el brazo raw, no consejo genérico), o
- (b) volver a skills como priors (lo que los mocks EXP45–52 validaron),
  sin pretensión conductual.

El bug que la corrida expuso y se arregló: `bandit_con_skill`/`gate_q1`
del resolver asumían el layout viejo de EXP47 (`PROBE_Q1=(0,1,2)`);
ahora son agnósticas al layout (la bit-identidad de fase 0 vs EXP51
sigue pasando en las 5 réplicas).

## Tests

- `test_fase1_proveedor.py`: 21 checks (presupuesto duro, generación,
  refinamiento, soporte, inyección de guía). Sin key.
- `test_fase1_motor.py`: 12 checks (loop completo con backend falso
  heterogéneo). Sin key.

## Qué sigue (fase 2, pendiente de decisiones)

- Tope mensual de gasto fijado por él (diseño §7.1).
- Dónde corre el servicio 24/7 y qué datos toca (§7.6).
- Ámbito real primero: había elegido inglés, a confirmar (§7.7).
- Meta-loop: propuestas de política validadas por harness (§3).
- Consolidación LLM del Curator: opt-in con aprobación (§7.4).
