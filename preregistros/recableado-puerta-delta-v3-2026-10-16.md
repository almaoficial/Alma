# Recableado de la puerta de adopción — tras la recalibración de δ v3

**Fecha:** 2026-10-16 · **Autorización:** Alejandro («Vamos a
hacerlo») · **Fuentes rectoras:** `preregistro-recalibracion-delta-v3-2026-10-16.md`
(§5.5: el paquete δ+panel se adopta junto y la base se evalúa sobre
el panel nuevo como parte del recableado; §8: congelamiento y
recableado son pasos separados, el recableado compara en una sola
escala) y `resultados-recalibracion-delta-v3-2026-10-16.md`
(congelamiento: par **(0,2283 escala δ ; 5,4781 totales)**, panel
18/12 train [400..417] · held-out [600..611] · E3 [500,501]) ·
**Commit de la calibración:** `b834e3d` · **Presupuesto:** US$0,
todo local · **Scripts:** `data_recableado_puerta_v3/run_recableado_base.py`,
`data_recableado_puerta_v3/asentar_evento_ledger.py` · **Datos:**
`data_recableado_puerta_v3/resultados_base.json`

**Veredicto: RECABLEADO COMPLETO.** La puerta compara desde hoy
con **5,4781 totales (δ = 0,2283)** sobre el **panel 18/12**, el
scaffold base quedó evaluado sobre el panel nuevo antes de
cualquier candidato (§5.5), las 44 suites de gobernanza dan el
mismo resultado que antes del cambio, y el evento quedó asentado
en el ledger (hash `fa633044…`, cadena de 12 eventos verificada).
**Ningún candidato fue evaluado; el meta-loop no se corrió con
fines de adopción; el validador congelado no se tocó. Nada se
subió a GitHub.**

---

## 1. La escala, determinada desde el código (paso crítico)

La cadena que alimenta la comparación, leída en el código:

1. `metaloop.MetaLoop._evaluar(scaffold, replicas, cache)` devuelve
   la **media de `reg_pol`** entre réplicas. `reg_pol` es el regret
   **total** de la réplica (suma sobre los 24 bloques; base ≈ 71–90).
2. `gate.PuertaDosSplits.decidir` resta esas medias:
   Δ_in/Δ_ho quedan en **totales**.
3. `metaloop.correr` pasa esos Δ a `gate.decidir_auto_adopcion`,
   que compara `max(Δ_in, Δ_ho) > PISO_RUIDO_DELTA`.

Evidencia empírica en el propio ledger: los audit records históricos
asientan `delta_in = −4,6667` y `−0,6667` — magnitudes de totales
(diferencias de medias de panel), no de escala δ.

**Conclusión:** la escala real de la comparación es **totales**, y
el valor cableado es el miembro en totales del par congelado:
**`PISO_RUIDO_DELTA = 5,4781`**, con la equivalencia declarada en
el código: 5,4781 totales ≡ 0,2283 escala δ (media por bloque,
totales ÷ 24). La comparación queda homogénea (totales contra
totales) con un único valor — no hubo que forzar equivalencias: el
par congelado trae ambos miembros y el código consume uno solo.
Queda asentado además el diagnóstico histórico: el 0,53 anterior
era el δ de EXP-piso-ruido (0,5331, **escala δ**, panel 3/2)
cableado sin convertir contra Δ en totales — la mezcla de escalas
que la recalibración v1 expuso (factor 24).

## 2. Cambios, archivo por archivo

- **`alma_service/gate.py`** — `PISO_RUIDO_DELTA`: 0,53 → **5,4781**;
  `REGLA_AUTO_ADOPCION`: «…>0.53» → «…>5.4781». Docstring y
  comentarios reescritos con la escala cableada, el par congelado,
  su procedencia (pre-registro/resultados v3, commit b834e3d) y la
  historia del valor anterior, incluida la nota de redondeo del par
  (0,2283 × 24 = 5,4792 ≠ 5,4781; manda el par asentado).
- **`alma_service/metaloop.py`** — `TRAIN_REPS`/`HELDOUT_REPS`:
  dejan de ser alias de e56 ([0,1,2]/[3,4]) y quedan en el panel
  congelado **[400..417]/[600..611]**, con comentario de procedencia.
  `e56` conserva sus réplicas (maquinaria del EXP56) y
  `puerta_e3.py` no se tocó: E3 sigue en [500,501]. La línea del
  protocolo en el docstring del módulo refleja el panel nuevo.
- **`test_piso_ruido_puerta.py`** — la suite del piso: sus casos
  estaban escritos en escala δ contra el 0,53; se re-escalaron a
  totales contra 5,4781 (banda 3,0/2,0 · borde exacto 5,4781 ·
  sobre la banda 6,0/1,0 y 0,0/9,0 · constantes y string de regla ·
  grilla «solo endurece» ampliada a la escala nueva). 11/11.
- **`test_fase23_freno_humano.py` y `test_gobernanza_auto_adopcion.py`** —
  ver §4: sus fakes de `_evaluar` reconocían el split train por el
  panel viejo y sus Δ de fixture (5,0) caían en la banda nueva; se
  actualizaron al panel cableado y a Δ = 6.

## 3. Evaluación del scaffold base sobre el panel nuevo (§5.5)

Vía `MetaLoop._evaluar` (validador congelado), scaffold =
`DEFAULT_SCAFFOLD`. Primero, ancla de identidad: sobre el panel
histórico [0..4] reproduce **reg_pol = [71, 83, 90, 84, 81]**,
idénticos al Paso 0 de las calibraciones v1/v2/v3 — mismo scaffold,
mismo validador.

| Split | Réplicas | Media `reg_pol` (totales) |
|---|---|---|
| Train 18 | [400..417] | **85,2222** |
| Held-out 12 | [600..611] | **80,6667** |
| E3 (contexto, sin cambio) | [500,501] | 85,0000 (reg_pol 83, 87) |

- **Determinismo:** segunda evaluación con caché fresco idéntica
  por réplica en ambos splits.
- **Δ base contra base** (por `PuertaDosSplits.decidir` sobre las
  medias nuevas): **Δ_in = 0,0 · Δ_ho = 0,0** — bajo el piso nuevo,
  sin anomalía (la puerta responde «sin mejora estricta», como
  corresponde a compararse consigo misma).
- Detalle por réplica en `data_recableado_puerta_v3/resultados_base.json`.
  Duración de la evaluación completa: 1,14 s. US$0.

## 4. Suites de gobernanza: 44/44 antes, 44/44 después

Baseline previo al recableado (árbol tal como estaba): **44 PASS ·
0 FAIL · 0 BLOCKED**. Tras el recableado: **44 PASS · 0 FAIL ·
0 BLOCKED** — sin diferencias.

En el camino aparecieron dos regresiones, ambas diagnosticadas
como fixtures atados a la configuración vieja, no como defectos del
recableado:

- `test_fase23_freno_humano` (30/33) y `test_gobernanza_auto_adopcion`
  (44/48): sus fakes de `_evaluar` detectaban el split train con
  `tuple(replicas) == (0, 1, 2)` — con el panel nuevo ningún split
  coincidía, y el Δ de fixture (5,0 totales) quedaba **dentro de la
  banda nueva** (5,0 ≤ 5,4781): las corridas semilla aceptaban en
  la puerta pero ya no auto-adoptaban, que es exactamente el
  comportamiento que el piso nuevo manda. Corrección: los fakes
  reconocen el train por `TRAIN_REPS` cableado y la «mejora medida»
  de fixture sube a Δ = 6 en ambos splits (sobre el piso nuevo);
  el caso lateral queda Δ_in = 6, Δ_ho = 0. Ambas suites volvieron
  a verde completo (33/33 y 48/48) y la corrida total lo confirmó.
- La actualización de estas tres suites está contemplada por los
  documentos rectores: son las suites que verifican el valor del
  piso y el panel de la puerta, y §5.5/§8 ordenan adoptar el
  paquete (δ + panel) en esta ruta. Ninguna otra suite se tocó.

## 5. Registro

- **Ledger del meta-loop:** evento `recableado_puerta_delta_v3`
  asentado con la cadena de hash de `metaloop.py` — hash
  **`fa6330440ac3bb3da3b5334203c257aa2683a4eb05ea7f978b74aef4c76b2a26`**,
  cadena completa de 12 eventos reverificada tras el asiento.
  Contiene: escala declarada y su equivalencia, δ anterior y
  cableado, panel anterior y nuevo, evaluación base, suites,
  archivos cambiados y los dos avisos de §6.
- **Commit local** en `~/workspace/alma-prototype` con este
  documento, los datos del recableado, el ledger y los cinco
  archivos de código/tests. Nada a GitHub: actualizar el repo
  público con el recableado es decisión aparte de Alejandro.

## 6. Avisos (quedan asentados)

1. **El documento de resultados de la v3 está truncado en disco.**
   `resultados-recalibracion-delta-v3-2026-10-16.md` mide 9.563
   bytes y corta a mitad de frase en §Congelamiento, con el
   marcador literal `...[truncated 5474 chars]` grabado en el
   archivo (el mismo modo de falla que truncó la primera redacción
   del pre-registro v3). Lo perdido es la cola del documento
   (limitaciones/estado final). El recableado no depende de esa
   cola: los valores congelados se verificaron contra **tres**
   anclas que coinciden — las secciones intactas del propio
   documento, el evento `recalibracion_delta_v3` del ledger y el
   mensaje del commit `b834e3d`. Reparar el documento (reescribir
   su cola desde los datos crudos de `data_recalibracion_delta_v3/`)
   queda como pendiente menor, fuera de este paso.
2. **El commit consolida capas que vivían sin commitear.** En el
   árbol de trabajo, `gate.py` y `metaloop.py` diferían de HEAD
   por capas enteras ya vivas (auto-adopción del 11/10, E3 del
   28/9, freno de estancamiento, archivo de variantes): la constante
   misma que se recableó existía solo en el árbol. El commit de
   este paso incluye esos dos archivos completos — con las capas
   previas verificadas coherentes por las suites antes (44/44) y
   después (44/44) — y lo declara acá y en el evento del ledger.
   El resto de archivos modificados del árbol (harness, server,
   datos de experimentos, etc.) queda fuera del commit, como estaba.

## 7. Estado final

- Puerta viva: **max(Δ_in, Δ_ho) > 5,4781 totales (δ 0,2283)**,
  panel **18/12** [400..417]/[600..611], E3 [500,501] intacto,
  forma de la regla sin cambio.
- Scaffold base evaluado sobre el panel nuevo y asentado
  (85,2222 / 80,6667; Δ base/base = 0).
- Adopciones del meta-loop: siguen en **0**. Este paso termina con
  la puerta recableada — el primer candidato que se evalúe contra
  ella es un paso posterior, con su propio pre-registro si lo
  requiere, y queda fuera de esta autorización.
