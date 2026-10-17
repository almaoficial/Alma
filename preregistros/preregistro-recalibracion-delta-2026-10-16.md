# Pre-registro: recalibración del piso de ruido δ (piso de auto-adopción)

**Fecha:** 2026-10-16 · **Estado:** aprobado por Alejandro («Completar el pre-registro de δ», 16/10/2026), US$0, sin código, sin corridas — este documento es la única excepción autorizada al congelamiento del laboratorio
**Origen:** diagnóstico de la segunda revisión externa de Claude (16/10/2026, conversación compartida f289a78c), que dejó un borrador de este pre-registro; acá se completa con los datos reales de los archivos y se corrige lo que los archivos contradicen
**Regla que se toca (solo el número, no la forma):** `alma_service/gate.py` — `PISO_RUIDO_DELTA = 0.53`; auto-adopción solo si `Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(Δ_in, Δ_ho) > δ` (la puerta pura `> 0` y el E3 quedan intactos)

---

## 1. Por qué se recalibra (el hueco medido)

δ vigente = **0,5331** (cableado como 0,53), calibrado en EXP-piso-ruido
(30/9/2026, `data_exppisorruido/`): bootstrap por bloques B=2000, z=2,0,
estadístico `s = max(Δ_in, Δ_ho)`; `sd(s*) = 0,2665`, `sd(Δ_in*) = 0,2969`,
`sd(Δ_ho*) = 0,3411`; semilla 12345.

Tres hechos, todos con recibo en los archivos:

1. **Ningún efecto real medido por el sistema alcanza el piso.** El ledger
   del meta-loop registra **0 adopciones históricas** (las propuestas
   asentadas tienen Δ 0,0/0,0 o fueron rechazadas en train). El efecto
   positivo más grande medido en una puerta del sistema es el de EXP76
   (puerta de admisión de skills, su propia regla): Δ_down = +0,3636,
   Δ_ref = +0,3807 — adoptó bajo su regla y **no pasaría** el piso de
   auto-adopción del meta-loop. EXP82 midió +0,089 / +0,142 / +0,101.
2. **El método que produjo δ no coincide con el protocolo que juzga.**
   El bootstrap original (`data_exppisorruido/mock_piso_ruido.py`) sortea
   por réplica **dos remuestras de bloques independientes** (base* y
   cand*), como si base y candidato se midieran por separado. La
   evaluación real del meta-loop es **pareada**: base y candidato corren
   las **mismas réplicas** [0,1,2]/[3,4], el mismo stream, y el RNG por
   (réplica, bloque, ítem, brazo) se siembra por identidad
   (`random.Random(f"exp45-r{rep}-b{b}-q{q}-{a}")` en
   `exp56_rso/run_experiment56.py`) — números aleatorios comunes. El
   nulo independiente cuenta dos veces una varianza que el diseño real
   cancela: hay motivo técnico, anterior a cualquier candidato, para
   sospechar que 0,5331 **sobreestima** el piso relevante.
3. **El split que manda es el más ruidoso.** `sd(Δ_ho*) = 0,3411` >
   `sd(Δ_in*) = 0,2969`, consistente con los paneles actuales:
   train = 3 réplicas, held-out = 2.

**Corrección al diagnóstico externo (registrada, no escondida):** la
revisión externa razonó con un score «0 a 1» y leyó δ como «medio
punto de escala». Los archivos dicen otra cosa: Δ se mide en **puntos
de regret del validador congelado** (regret por réplica = suma sobre
24 bloques, escala 0–240; el held-out de partida histórico es 82,5 —
`metaloop_ledger.jsonl`). La conclusión de fondo se sostiene por los
hechos 1–3 (el piso supera todo efecto real medido y su método no
matchea el protocolo), pero la frase «de 0,30 a 0,83 en una escala
0–1» no describe este validador y no se usa en este documento.

**Dato de gobernanza que se hereda con honestidad:** el veredicto del
EXP-piso-ruido original fue **INCONCLUSO** (su simulación produjo 0
aceptaciones y el re-juicio del ledger no cambió ninguna decisión);
δ se cableó igual el 11–12/10/2026 como endurecimiento preventivo
(`metaloop_preregistro_piso_ruido_puerta.json`). Esta recalibración no
hereda una validación que nunca existió: produce la primera
calibración con el método alineado al protocolo real.

## 2. El instrumento, tal como está hoy (verificado en archivos)

- **Validador congelado:** `run_experiment47` (stream + tasas de
  `data_exp44/tasas.json`) + `run_experiment56.correr_replica_param`.
  **No hay ningún LLM en el camino del Δ**: es un simulador mock
  determinista. Verificado el 30/9: misma réplica corrida dos veces →
  regret idéntico (83,0 = 83,0).
- **Batería:** stream fijo de **240 ítems = 24 bloques × 10**
  (`BLOQUE = 10`), construido con semilla fija; cada bloque: 8 ítems
  de su régimen + 2 de ruido. La batería de ítems está **congelada**
  (regla de oro del meta-loop: el loop nunca edita al validador) — el
  único eje de ampliación sin tocar el validador es el **panel de
  réplicas**, porque el validador acepta ids de réplica arbitrarios
  (el E3 ya usa [500, 501]).
- **Evaluación por candidato (hoy):** A/B pareado, train réplicas
  [0,1,2], held-out [3,4], E3 ciego [500,501] (exigido siempre desde
  el 28/9). 5 evaluaciones de stream completo por candidato (+2 de E3
  si pasa la puerta). Repeticiones por caso: **1 por réplica** —
  repetir la misma réplica no cambia el número (determinismo).
  Rondas por corrida del meta-loop: 8 (`RONDAS_DEFAULT`).
- **Duración/costo registrados:** costo **US$0** siempre (mock, sin
  keys). Corridas del ledger de 2 rondas: 0,37 s y 0,26 s. La duración
  total de la calibración original **no quedó registrada** → ver §6.
- **El «juez» del plan externo, aclarado:** el juez LLM del sistema es
  otro componente (evaluador barato): `mistralai/mistral-nemo` vía
  OpenRouter, **ya cableado a temperatura 0**
  (`alma_service/juez_barato.py`, `backend_openrouter`), max_tokens
  10 (20 en EXP-JUEZ-001). Su batería de selección (EXP-JUEZ-001,
  `dataset_juez_30.py`, n=30): nemo acordó **28/30** (0,9333),
  heurístico **17/30**. Ese juez **no participa** en Δ_in/Δ_ho ni en
  esta recalibración; el ítem «temperatura del juez en 0» del plan
  externo se resuelve así: ya es 0 donde existe un juez, y donde se
  decide la adopción no hay juez.

## 3. Pregunta e hipótesis (escritas antes de correr)

**Pregunta:** ¿cuánto del δ = 0,5331 actual es varianza estructural
del diseño de medición (método del nulo + panel chico) y cuánto es el
piso que queda cuando el nulo se calcula como el protocolo realmente
evalúa?

- **H1 (dominancia del diseño):** el nulo pareado entre paneles (B,
  §4) y/o el panel ampliado (C, §4) reducen el piso al menos un 50%
  respecto a 0,5331 (es decir, ≤ 0,2666). Si H1 se cumple, la mayor
  parte del piso actual era método, no mundo.
- **H2 (juez/medición repetida = 0):** la varianza por repetición de
  la medición es exactamente cero en este camino (determinismo del
  validador). No se asume: se verifica en el Paso 0, y si falla, H2
  cae y todo lo demás se detiene.
- **H3 (el held-out manda el ruido):** en todos los diseños,
  `sd(Δ_ho*) > sd(Δ_in*)` mientras el panel held-out sea más chico
  que el de train; con paneles 6/4 la brecha se achica respecto a 3/2.

## 4. Protocolo

Todo mock, local, US$0, sobre copias — no se toca el servicio ni
`gate.py` durante la calibración (mismo alcance que EXP-piso-ruido).

**Paso 0 — Auditoría de determinismo (el «corré el sistema sin
cambios 10 veces» del plan externo, con su resultado esperado
declarado de antemano).** Evaluar el scaffold base
(`DEFAULT_SCAFFOLD`) sobre [0,1,2] + [3,4] **10 veces** y comparar
los 5 reg_pol y los 120 reg_pol_bloques entre corridas.
Esperado: identidad exacta en las 10. **Cualquier diferencia es un
hallazgo** (no-determinismo oculto): se detiene el protocolo, se
asienta, y no se recalibra nada hasta explicar la fuente.
En este paso se **mide y se asienta la duración** de una evaluación
completa y del protocolo entero estimado (dato que hoy no existe en
los archivos).

**Paso 1 — Descomposición de fuentes.** Con la matriz réplica×bloque
del scaffold base (5 réplicas × 24 bloques) y el pool fresco del
Paso 2, reportar por separado:
- varianza entre bloques dentro de réplica (la que midió el
  bootstrap original);
- varianza entre réplicas del reg_pol medio;
- varianza de medición repetida: la del Paso 0 (esperada: 0);
- varianza «del juez» en el camino del Δ: **0 por construcción**
  (no hay LLM en este camino; §2) — se declara, no se estima.
El generador/proposer no entra en el nulo (el nulo es base contra
base); su varianza afecta qué candidatos llegan a la puerta, no el
piso, y queda fuera de esta descomposición por diseño.

**Paso 2 — Tres pisos candidatos.** Mismo estadístico y criterio que
la calibración original: `s = max(Δ_in, Δ_ho)`, `δ = z · sd(s*)` con
**z = 2,0**. Bootstrap con **B = 5000** (sube desde los 2000
originales solo por resolución de Monte Carlo; se declara el cambio)
y **semilla fija 12345** (la misma de la calibración original, por
comparabilidad; se declara antes de correr).

- **A — Control (método original, panel actual).** Réplicas
  [0,1,2]/[3,4]; por réplica, dos remuestras de 24 bloques con
  reemplazo, independientes (base* y cand*); Δ* por split como
  diferencia de medias entre remuestras. Debe **reproducir**
  δ ≈ 0,5331 con tolerancia Monte Carlo declarada: |δ_A − 0,5331| ≤
  0,02. Si A no reproduce, el pipeline cambió desde el 30/9: se
  detiene todo y se investiga antes de mirar B o C (validez interna
  primero).
- **B — Nulo pareado entre paneles (A/A, panel actual).** Pool de
  **20 réplicas frescas, ids [1000..1019]**, nunca usadas por la
  puerta ni por el E3 (sin contaminación de splits históricos). Por
  draw: sortear del pool dos paneles **disjuntos** con los tamaños
  actuales (train 3, held-out 2 por panel); Δ_in* = media_train
  (base, panel P) − media_train(base, panel Q); Δ_ho* análogo;
  s* = max(Δ_in*, Δ_ho*). δ_B = 2,0 · sd(s*). Este nulo mide cuánto
  se mueve el estadístico de la puerta entre muestras independientes
  de problemas, con la estructura de comparación que la puerta usa
  de verdad (ambos lados de una comparación real comparten panel;
  lo incierto es el panel, no la medición).
- **C — A/A con panel ampliado.** Idéntico a B pero con paneles
  **train 6 / held-out 4** por lado (desde el mismo pool, disjuntos
  entre sí: 20 réplicas alcanzan justo para 2 paneles de 10; si el
  sorteo exige más, se sortea con reposición de paneles completos,
  nunca compartiendo réplicas entre los dos lados de un mismo draw).
  δ_C = 2,0 · sd(s*). Si se adopta C, adoptar C significa adoptar
  también el panel 6/4 como panel de evaluación de la puerta (ver
  §5): el número y el panel son un solo paquete.

## 5. Reglas de decisión y congelamiento (fijadas antes de correr)

- Si **δ_C ≤ 0,20** → **δ_nuevo = δ_C**, con panel de evaluación 6/4.
- Si δ_C > 0,20 pero **δ_B ≤ 0,20** → **δ_nuevo = δ_B**, panel actual
  3/2.
- Si el menor piso cae en **(0,20 ; 0,30]** → **INCONCLUSO con
  dirección**: no se adopta ningún número; δ vigente queda; el paso
  obligado siguiente sería ampliar la batería de ítems, lo cual
  exige descongelar el validador — decisión de gobernanza aparte,
  **fuera de este pre-registro**.
- Si **todos > 0,30** → el problema es estructural (validador/panel):
  se archiva el intento con el diagnóstico completo y no se buscan
  adopciones hasta rediseñar la medición.
- **Qué contaría como raro** (del borrador externo, adaptado):
  δ_B ≥ δ_A (el nulo pareado no ayuda nada) → raro: no se adopta
  ningún número hasta entender por qué; cualquier piso **< 0,05** →
  sospecha de bug de medición (en este sistema indicaría que los
  paneles del A/A no son independientes — p. ej. RNG compartido
  entre ids de réplica —, un hallazgo sobre el validador, no un piso
  usable): se detiene y se investiga.
- **Congelamiento:** producido el resultado, δ_nuevo (y su panel)
  quedan asentados en el documento de resultados de esta
  recalibración y en el commit correspondiente **antes de que se
  evalúe cualquier candidato nuevo del meta-loop**. Entre el
  congelamiento y el recableado no se corre el meta-loop con fines
  de adopción. La **forma** de la regla no cambia:
  `Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(Δ_in, Δ_ho) > δ`, puerta pura y E3
  intactos. El recableado en `gate.py` sigue el precedente del
  11/10/2026 (su propio pre-registro de gobernanza si hiciera falta,
  como `metaloop_preregistro_piso_ruido_puerta.json`), pero el
  número ya no se toca ahí: cualquier cambio posterior de δ o del
  panel exige **otro pre-registro**. Recalibrar después de ver
  candidatos es mover el arco y está prohibido por este documento.

## 6. Qué invalida la recalibración o archiva el intento

- Paso 0 con cualquier diferencia entre repeticiones → invalidada
  hasta explicar el no-determinismo.
- δ_A fuera de la tolerancia de reproducción (±0,02) → invalidada
  hasta explicar qué cambió en el pipeline desde el 30/9.
- δ_B ≥ δ_A, o cualquier piso < 0,05 → no se adopta; se archiva el
  intento con el diagnóstico (no se «arregla» el método hasta que dé
  el número deseado: eso sería mover el arco con otros pasos).
- Los tres pisos > 0,30 → intento archivado por estructural (§5).
- Descubrir que algún id del pool [1000..1019] fue usado antes por
  cualquier corrida (contaminación) → el A/A queda invalidado y se
  rehace con ids verificados como vírgenes, asentando el error.
- Si algún paso exigiera tocar el validador congelado, el stream o
  las tasas → fuera de alcance: se detiene y se registra.

## 7. Presupuesto y alcance

- **US$0.** Todo el protocolo es mock/local sobre el validador
  congelado; no usa keys, no usa el juez LLM, no toca el servicio.
- **Duración:** a fijar con medición del Paso 0 antes de ejecutar
  los Pasos 1–2 (referencias registradas: corrida de 2 rondas =
  0,26–0,37 s en el ledger; evaluación de una réplica = 1 pasada de
  240 ítems). Si la duración medida del protocolo completo supera
  lo razonable para CPU local (umbral: 1 hora), se asienta y se
  reduce B antes de correr — reducir B es un cambio de resolución,
  no de criterio, y queda asentado en el documento de resultados.
- Si el protocolo exigiera gasto con key en cualquier punto, eso
  queda **fuera** de este pre-registro y requiere otro, con
  presupuesto y «sí» explícito con costo y tiempo.

## 8. Limitaciones declaradas (sin maquillar)

1. **Sin holdout independiente para el juez barato:** la batería de
   selección del juez (n=30) es el mismo conjunto con el que se
   eligió a mistral-nemo y con el que se cita su 28/30; no existe un
   set holdout independiente para ese número. Se registra tal cual,
   como ya declara el README del repo. (El juez no entra en esta
   recalibración, pero es la limitación viva del sistema de medición
   y este documento no la esconde.)
2. **El piso vale solo para este validador y esta batería:** δ se
   calibra sobre el mismo stream congelado de 240 ítems que después
   juzga a los candidatos — no hay holdout de ítems posible sin
   descongelar el validador. δ_nuevo no se exporta a otro validador,
   otra batería ni otra escala.
3. **Muestras chicas:** los paneles actuales son 3/2 réplicas y el
   pool A/A es de 20 réplicas del mismo generador; los sd resultantes
   son estimaciones con su propio error (mitigado solo en parte por
   B=5000, que reduce el error de Monte Carlo del bootstrap, no el
   de la muestra de réplicas).
4. **Comparación entre escalas:** el argumento «EXP76 no pasaría»
   (§1, hecho 1) compara el piso con efectos medidos por **otras**
   puertas del sistema en **sus** escalas; se usa como evidencia de
   orden de magnitud (ningún efecto real del sistema llega a 0,53 en
   su propia métrica), no como una resta en unidades idénticas.
5. **El nulo A/A asume** que réplicas con ids distintos son muestras
   independientes del mismo generador de problemas; el Paso 0 y el
   criterio de rareza «< 0,05» son los controles declarados de ese
   supuesto.

## 9. Entregables (cuando se corra, con otro «sí» o dentro de este)

- Documento de resultados junto a este pre-registro: Paso 0 (10/10
  idénticas o el hallazgo), descomposición de fuentes, δ_A / δ_B /
  δ_C con sus sd por split, veredicto según §5, y δ_nuevo congelado
  con su panel — o el archivo del intento con su diagnóstico.
- Asiento en el ledger del meta-loop del evento «recalibración de δ»
  con el número viejo, el nuevo y la referencia a este documento.

---

*Fuentes de cada dato: `data_exppisorruido/PRE-REGISTRO.md` y
`resultados.json` (calibración original); `alma_service/gate.py`
(PISO_RUIDO_DELTA y la regla); `alma_service/metaloop.py` y
`alma_service/puerta_e3.py` (splits, A/B pareado, E3 [500,501]);
`run_experiment47.py` (stream 240 = 24×10) y
`exp56_rso/run_experiment56.py` (reg_pol_bloques, RNG por identidad);
`alma_service/juez_barato.py` y `alma_service/exp_juez_001_resultados.json`
(juez nemo, temperatura 0, 28/30, heurístico 17/30);
`data_exp76/resultados_exp76.json` (Δ +0,3636/+0,3807);
`metaloop_ledger.jsonl` (0 adopciones; duraciones 0,26–0,37 s);
borrador externo: conversación de Claude f289a78c (16/10/2026).*
