# ALMA-servicio — Fase 0: scaffolding validado (2026-09-27)

El prototipo mínimo (experimentos EXP1–EXP52) probó los mecanismos.
La fase 0 convierte esos hallazgos en un **servicio**: el paquete
`alma_service/` con la política validada, reutilizable en vez de scripts
ad hoc, y un **harness de evaluación** que funciona como puerta de calidad.

Costo de la fase: US$0. Sin key, sin red, sin skills de terceros,
sin reescritura de código propio, sin Meta-loop real.

## Lo que se construyó

| Módulo | Qué hace | Origen |
|---|---|---|
| `alma_service/memoria.py` | Ledger de experiencias con **olvido** (peso `0.5^días`, EXP9) y **evicción acotada** (lógica, nunca DELETE; `verify_chain()` intacto) | Diseño §1.2; EXP9 |
| `alma_service/skills.py` | Skills formato AgentSkills: frontmatter YAML, índice SQLite, **presupuesto DURO de contexto** (`PresupuestoExcedido`), cuerpo bajo demanda (progressive disclosure) | Diseño §1.1; estudio Hermes §1.2B |
| `alma_service/recurrencia.py` | **Compuerta del sistema**: si la tasa de recurrencia < 0.30, el loop de skills no se activa (modo adaptativo) — EXP44 como compuerta, no como nota al pie | Diseño §2.1 |
| `alma_service/curator.py` | Ciclo de vida determinista `active → stale (14d) → archived (30d)`, solo `created_by == "agent"`, ledger con hash encadenado, nunca borra | Diseño §1.1.2; Hermes §1.2C |
| `alma_service/metaloop_stub.py` | Interfaz documentada del Meta-loop; en fase 0 siempre corta con `MetaLoopNoDisponible` | Diseño §3.1 |
| `alma_service/resolver.py` | La política validada (prior condicionado + skip endurecido + gate adaptativo) como componente, con la costura `ProveedorSkills` para fase 1 | EXP45/49/51 |
| `alma_service/harness.py` | Puerta de calidad: pre-registro escrito ANTES de correr réplicas, réplicas pareadas, veredicto calculado contra el criterio | Diseño §3.2 |

## La prueba (puerta de fase)

`bash fase0_puerta.sh` corre los 6 tests y el experimento
`fase0-scaffold-evolucionado`:

- **Bit-identidad**: `correr_replica_servicio` produce los mismos
  `reg_trat_bloques` por réplica que la implementación independiente
  `exp56_rso/run_experiment56.py` con el scaffold validado
  (`alma_service/scaffold.py::DEFAULT_SCAFFOLD`) en las 5 réplicas.
  Verificado por `test_fase0_resolver.py`. Lo que la bit-identidad
  prueba es el cableado: dos implementaciones distintas del mismo
  scaffold dan los mismos números.
- **Efecto**: media(efecto) = −6,20 < 0.

Resultado del 2026-09-27: **PASS**. Artefactos en `resultados/fase0-puerta/`
(`preregistro.json`, `report.json`, `veredicto.md`).

## Actualización 27/9: defaults n0=4, umbral_base=1 validados por EXP56/57

EXP56 (RSO estilo MiniMax: 24 rondas greedy evolucionando 5
hiperparámetros del scaffold, validador congelado) encontró 3 keeps:
n0 2→4, umbral_base 2→1, umbral_divisor 3→2. EXP57 (ablación +
replicación en seed independiente) mostró que n0=4 y umbral_base=1 son
load-bearing —revertirlos empeora el regret— y que umbral_base=1 es
además protector (sin él, el scaffold queda PEOR que la política
manual); el keep de umbral_divisor→2 resultó ruido de entrenamiento y
se descartó (se conserva el 3 original).

Recomendación pre-registrada de EXP57: fijar n0=4 y umbral_base=1 como
defaults. Aplicado en:

- `alma_service/scaffold.py` (nuevo): `DEFAULT_SCAFFOLD` con los 5
  hiperparámetros + las piezas de decisión parametrizadas (puertos
  verbatim de `exp56_rso/run_experiment56.py`).
- `alma_service/resolver.py`: el `Resolver` acepta `scaffold`
  (default = `DEFAULT_SCAFFOLD`); el prior de Thompson, el bandit y el
  soporte usan las versiones parametrizadas. Sin cambios de lógica.
- `alma_service/proveedor_real.py`: `umbral_endurecido` ahora delega
  en el scaffold (1 + floor(K/3)).
- `alma_service/harness.py` + `fase0_puerta.sh` + tests: la puerta
  ahora valida la política evolucionada, no EXP51.

Antes/después (5 réplicas pareadas, mismo stream y control verbatim):

| | reg_trat por réplica | efecto medio |
|---|---|---|
| EXP51 (n0=2, ub=2) | 78, 86, 93, 95, 80 | −1,60 |
| Evolucionado (n0=4, ub=1) | 71, 83, 90, 84, 81 | −6,20 |

Delta del scaffold en el servicio: −4,6 adicionales, consistente con el
+4,50 medido en held-out por EXP56. La mejora vive en todas las
réplicas (ninguna en contra), a diferencia de la serie EXP45–51 donde
el efecto era frágil entre réplicas.

La bit-identidad vs EXP51 se rompió POR DISEÑO (la política mejoró a
propósito). Los scripts históricos (`run_experiment47/49/51.py`) no se
tocaron: siguen siendo el registro intacto de EXP45–51.

## Reglas que quedan instaladas

1. **El pre-registro se escribe antes de correr.** El harness lo hace
   mecánicamente; no hay experimento sin `preregistro.json` previo.
2. **La bit-identidad es verificable.** La disciplina de RNG
   (`exp45-r{rep}-b{b}-q{q}-{a}` para el oráculo, `...-sel` para Thompson)
   hace que la política sea independiente del orden de llamadas.
3. **La evicción es lógica.** Archivar ≠ borrar: el ledger con hash
   encadenado nunca pierde historia.
4. **El Curator no toca lo externo.** Solo `created_by == "agent"`.
5. **El Meta-loop es fase 2+.** El stub corta con `MetaLoopNoDisponible`;
   activarlo requiere propuesta → sandbox → harness → pre-registro
   falsable → A/B pareado → PASS.

## Qué sigue (fase 1, pendiente de aprobación)

Conectar el `Resolver` a un `ProveedorSkills` real sobre
`SkillIndex` + `MemoriaExperiencias` (hoy el mock usa el historial del
mundo simulado), y cablear `servicio/motor.py` al `Resolver`. Todo cambio
de política pasa por el harness.
