# MAPA — qué pieza es qué

Una página para entrar al código sin arqueología. El detalle y los números
viven en el [README](../README.md); este mapa solo dice dónde está cada cosa,
qué rol cumple y qué papel la respalda.

## Los paquetes

| Paquete | Qué es | Piezas clave |
|---|---|---|
| `alma_service/` | **El sistema.** El meta-loop con gobernanza medida: propone cambios sobre sí mismo, los evalúa y decide adopciones. | `metaloop.py` (el loop), `gate.py` (la puerta de adopción), `juez_barato.py` / `evaluador_barato.py` (el filtro barato), `verificacion.py` (el verificador), `presupuesto.py` (topes de gasto), `generador_candidatos.py` y `crossover.py` (instrumentos de búsqueda del 16/10/2026) |
| `alma/` | **El prototipo original** (septiembre 2026): selector, backends, evaluador y registro. Lo importan los runners históricos y el servicio en vivo; no es donde vive el sistema actual. | `backends.py`, `evaluator.py`, `gates.py`, `registry.py` |
| `servicio/` | **El árbol del servicio fase 2 en vivo**: servidor, motor y memoria, ejercitado de punta a punta por varias suites. | `server.py`, `motor.py`, `store_sqlite.py` |
| `alma_sobre_claude/` | **El segundo marco** (abierto el 17/10/2026): la misma gobernanza aplicada a la configuración del propio asistente. Batería de pantalla con validador de planes congelado; el corpus publicado es un ejemplo sintético (ver su `SANEADO.md`). Su ledger de eventos es `alma-sobre-claude-ledger.jsonl`, en la raíz. | validador de planes, puntuadores, constructor de corpus |

Superficies de apoyo: `scripts/run_test_suites.py` (el runner de las 47
suites), `demo/` (la demo del verificador, 2 minutos), `test_*.py` en la raíz
(las suites de gobernanza), `preregistros/` (el papel, antes de correr),
`resultados/` (el informe, después de correr), `data_*/` (los datos de cada
corrida) y `experimentos/` (corridas clave y una copia del ledger del
meta-loop; la copia que leen las suites nuevas es la de la raíz:
`metaloop_ledger.jsonl`).

## Las dos puertas (no son la misma)

Este proyecto tiene **dos** puertas de gobernanza distintas, con roles que no
se mezclan:

| | Puerta de adopción (meta-loop) | Puerta de evidencia (ReviewBench) |
|---|---|---|
| **Nombre** | la puerta de `alma_service/gate.py` | `alma-evidence-gate/1.0.0` |
| **Dónde vive** | Este repo: `alma_service/gate.py` + `alma_service/metaloop.py` | Repo [alma-reviewbench](https://github.com/almaoficial/alma-reviewbench): `agent/alma_gate.py` |
| **Qué decide** | Si una auto-modificación del sistema se **adopta** | Si un finding de code review se **emite** |
| **Regla** | Efecto positivo en dos splits independientes **y** mayor que el piso de ruido medido del sistema: `max(Δ_in, Δ_ho) > δ`, con **δ = 0,1141** — cableado en `gate.py` (línea 89) como `PISO_RUIDO_DELTA = 2.7391` totales ≡ 0,1141 × 24 | Cada claim debe traer evidencia verificable en el diff: el archivo y las líneas citadas existen, el texto citado coincide exactamente y contiene el soporte específico del claim. Claim desconocido o sin evidencia → rechazado, **fail-closed**. Huella de la política: `policy_sha256 = 3ad514ede02e6eefc9b2ed0dceed144bdc6aafe21cab57aa6746c44190689f35` |
| **Su papel** | Pre-registros y resultados en `preregistros/` y `resultados/` (arco de δ: 0,53 → 0,2283 → 0,1141; cierre L1) | `PREREGISTRO-REVIEWBENCH.md` y `MANIFIESTO-CORRIDA.md` del repo alma-reviewbench |

## El flujo completo

El meta-loop (este repo):

```text
experiencia / tarea
      │
      ▼
el loop PROPONE un cambio (mutación, generador LLM o crossover)
      │
      ▼
PRE-REGISTRO ya escrito: qué se espera, qué contaría como raro,
qué resultado cambia el veredicto
      │
      ▼
medición en DOS splits independientes contra el validador CONGELADO
      │
      ▼
PUERTA DE ADOPCIÓN ── max(Δ_in, Δ_ho) ≤ 0 ──────────► RECHAZADO
      │              ── 0 < efecto ≤ δ (banda de ruido) ► espera al HUMANO
      │              ── efecto > δ en ambos splits ────► ADOPTADO
      ▼
LEDGER con cadena de hashes: qué se propuso, qué se midió, qué se decidió
      │
      ▼
freno de estancamiento (3 ciclos sin adopción → alto total;
el desbloqueo exige el token humano ALMA_TOKEN_HUMANO, fail-closed)
```

El brazo ALMA de ReviewBench (repo
[alma-reviewbench](https://github.com/almaoficial/alma-reviewbench)):

```text
diff de un PR ──► el revisor PROPONE findings candidatos
                        │
                        ▼
              PUERTA DE EVIDENCIA (alma-evidence-gate/1.0.0)
                        ├── evidencia verificable en el diff ──► se EMITE
                        └── sin evidencia / claim desconocido ─► RECHAZADO
                              (queda en el ledger con motivo)
```

La diferencia entre las dos puertas es la diferencia entre los dos problemas:
la de adopción protege al sistema de **adoptar ruido como mejora**; la de
evidencia protege al revisor de **emitir afirmaciones que el código citado no
sostiene**. Ninguna de las dos inventa contenido: la primera no propone
cambios y la segunda no propone findings; ambas solo deciden.
