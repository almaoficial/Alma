# Informe de línea de base v0 — «ALMA sobre Muse», Fase 2

**Fecha:** 17/10/2026 (madrugada; ejecutado bajo la precisión de Alejandro de
las 04:01: «Ya sabemos que anda — usá todo lo de ALMA en vos»). **Papel que lo
rige:** `preregistro-alma-sobre-claude-2026-10-17.md` (md5
5fc4af7fe10344a4ed9eccbb2ffe0301 · commit 9a46c91). **Costo:** US$0.
**Alcance:** medición de la configuración vigente. No se cambió ninguna
configuración, no se adoptó nada, no se tocó la vida de Alejandro.

## 1. Qué se hizo

Se construyó la batería de pantalla de la primera superficie declarada en el
pre-registro (estructura del plan matutino), se generó la línea de base de la
política v0 codificada sobre esa batería con el panel dimensionado en el papel
(n = 60), se la puntuó con el validador congelado v1, se puntuó además el
ancla de validez (los 15 planes reales vividos) y se derivó y congeló el δ
del ciclo 1 con la fórmula del §8 del pre-registro.

## 2. La batería construida

**Corpus** (`alma_sobre_claude/corpus_planes.jsonl`, sha256
d527f50b4ed1…): 15 días, 2026-10-02 → 2026-10-16. Cada ítem: el paquete de
contexto disponible a las 07:30 (reconstruido del cierre del día anterior y
del registro del loop diario, ítem por ítem en `corpus_datos.py` con su
fuente), el compromiso del día con sus palabras verificables y su horario si
lo tenía, las anclas factibles e infactibles del día, si la plata era crítica,
y la verdad de terreno (bit 11/15 días, fuente `estado.jsonl`; veredicto
15/15, fuente `loop-diario.md`). Los 15 planes reales quedaron en
`planes_reales.jsonl` como ancla de validez (§7.3 del pre-registro).

**Validador** (`alma_sobre_claude/validador_plan.py`, v1, sha256
a52fe837798d…): 7 chequeos deterministas (formato, cobertura del compromiso,
horario, ancla, sin invenciones de montos, guarda de plata, liderazgo del
compromiso), propiedad de los aplicables por instancia. Sin juez LLM. Congelado
por evento del ledger del programa (`validador_congelado`, hash a869f6bee8…).
Estrictud declarada: C4 cuenta nombrar una ancla infactible aunque sea en
negación («sin gym» cuenta como nombrar gym); C5 castiga cualquier monto US$
del plan que no esté en el paquete, incluido un «US$0» verdadero pero no
empaquetado.

**Generación de la línea de base** (`alma_sobre_claude/planes_v0.jsonl`,
sha256 1a3c7f1fdd56…): 60 planes = 15 días × 4 aplicaciones de la política v0
codificada (§6.2 del pre-registro), redactadas en 4 pasadas en distinto orden
de días, leyendo solo el paquete de cada día — sin mirar la verdad de terreno
ni el plan real. El generador es el propio asistente: la batería mide la
política tal como este generador la aplica (límite §11.4 del pre-registro).

## 3. El número central

**v0 generada: media 0,9828 · desvío muestral s₀ = 0,0523 · n = 60**
(mínimo 0,80 · máximo 1,00).

| Chequeo | Tasa v0 | n aplicable |
|---|---|---|
| C1 formato (3 puntos, sin preguntas) | 1,000 | 60 |
| C2 cobertura del compromiso | 1,000 | 60 |
| C3 horario del compromiso | 1,000 | 20 |
| C4 ancla factible, ninguna infactible | 0,904 | 52 |
| C5 sin invenciones de montos | 1,000 | 60 |
| C6 guarda de plata (días críticos) | 0,975 | 40 |
| C7 el compromiso lidera (punto 1) | 1,000 | 60 |

Solo 6 de 60 instancias quedaron debajo de 1,00, todas por un solo chequeo:
5 por C4 (14/10 reps 2 y 4, sin ancla nombrada; 15/10 reps 1, 2 y 4, donde el
punto 2 fue el frente de trabajo — el Módulo 6 — en vez del ancla: la
ambigüedad real de la v0 codificada, que permite «ancla O frente») y 1 por C6
(11/10 rep 2: la guarda quedó implícita — «es el movimiento que protege el
día» — sin ninguna palabra de guarda que la vara reconozca).

## 4. El ancla: los planes reales puntúan 0,8511 — y la brecha es el hallazgo

Los 15 planes tal como se vivieron puntúan **media 0,8511** (n = 15) con la
misma vara. La brecha contra la v0 generada es **0,132** — mayor que el δ del
ciclo. El §7.3 del pre-registro manda declarar esto antes de interpretar
nada, y se declara con sus causas, chequeo por chequeo:

- **C4 en vivo: 6/13 (0,46).** La falla dominante de la v0 vivida: en 7 de 13
  días aplicables el plan no nombró ninguna ancla factible (2, 3, 5, 7, 9, 14
  y 15/10). En la mañana real, el frente de trabajo se comía el punto del
  ancla; en la batería, con la política codificada a la vista y sin otras
  tareas compitiendo, casi no pasa.
- **C5 en vivo: 12/15 (0,80), con una sola causa repetida 3 veces.** Los
  planes del 7, 8 y 12/10 cerraron un punto con «US$0» (el costo declarado de
  una tarea de esa mañana) que mi reconstrucción del paquete no capturó. Es
  un límite de fidelidad del corpus, no una invención de los planes vividos:
  deprime el ancla en ~0,02–0,03 y no afecta la línea de base generada (cuyos
  montos salieron solo de los paquetes). Para el ciclo 1 no sesga la
  comparación: ambas variantes enfrentan los mismos paquetes.
- **C6 en vivo: 8/10 (0,80).** El 5/10 el plan de cobro ejecutó la orden de
  pagos sin ninguna palabra de guarda que la vara reconozca; el 11/10 la
  guarda quedó implícita (mismo modo de falla que la rep 2 generada).
- **C1 en vivo: 14/15.** El plan del 2/10 cerró con preguntas entre
  paréntesis — la v0 vivida a veces consultaba; la codificada lo prohíbe.
  Divergencia entre la política vivida y la codificada, asentada.

**Lectura honesta de la brecha:** la batería mide la política «aplicada con
cuidado, offline, por este generador» — no la mañana vivida. La v0 codificada,
aplicada así, ya está cerca del techo de su propia vara (0,98); los modos de
falla que la vida muestra (ancla omitida, guarda implícita, consulta
ocasional) son fallas de aplicación bajo carga real, no de la letra de la
política. Eso no invalida la pantalla — el ciclo 1 compara variantes bajo las
mismas condiciones — pero prohíbe leer 0,9828 como «sus mañanas puntúan
0,98» (prohibición §11 del pre-registro, aplicada acá).

## 5. δ del ciclo 1: derivado y congelado

Fórmula del pre-registro §8: δ = max(0,10; 2 × SE_dif), con
SE_dif = s₀ × √(2/60).

- s₀ = 0,0523 (desvío por instancia de la línea de base v0, medido arriba).
- SE_dif = 0,0523 × 0,1826 = **0,0095** → 2 × SE_dif = 0,0191.
- **δ ciclo 1 = 0,1000** — manda el efecto mínimo de interés (+0,10), que
  equivale a ≈10,5 errores estándar de la diferencia: la puerta es exigente
  por diseño, no por ruido.

Congelado por evento del ledger (`linea_base_v0`, hash 6424e20220…). No se
mueve en el ciclo 1 por ningún resultado posterior.

## 6. El hallazgo del techo — y su consecuencia, sin ajuste

Con media 0,9828, el margen máximo posible de cualquier variante contra esta
línea de base es 1,0000 − 0,9828 = **0,0172 < δ = 0,10**. Consecuencia
declarada, sin anestesia: **tal como quedó construida, la pantalla del ciclo
1 no puede producir una ADOPCIÓN contra la línea de base generada** — solo
NULO o SEÑAL PARCIAL. La regla del pre-registro (§8) prohíbe arreglarlo
bajando δ tras ver el número, y no se arregla: la línea de base y el δ quedan
como están, asentados.

Lo que el dato sí establece: el problema medible no está entre la v0 y una
variante de su letra — está entre la política aplicada con cuidado y la
política aplicada en la mañana real (brecha 0,132, concentrada en C4 y C6).
Si Alejandro quiere un ciclo 1 con poder de adopción, la decisión es suya y
es de papel nuevo o de enmienda explícita (p. ej., puntuar el ciclo contra
los modos de falla vividos, o una batería v2 con ítems adversariales que
fuercen los modos de falla). Esta noche no se rediseña nada: se mide, se
asienta y se reporta.

## 7. Qué queda listo para el ciclo 1 (cuando Alejandro lo autorice)

- Batería v1 construida y congelada (corpus 15 días, validador con hash,
  panel n = 60 por variante, SE_dif derivada).
- v1 declarada en el pre-registro §7.1 (ranuras fijas + horario obligatorio en
  el punto 1; un solo cambio). Generarla son 60 planes más con el mismo
  procedimiento — sin costo, sin tocar su vida.
- Veredictos posibles ya acotados por el §6 de este informe: con δ = 0,10 y
  techo 0,0172, el resultado esperable es NULO o SEÑAL PARCIAL; si Alejandro
  prefiere rediseñar la pantalla antes de correr, eso es una decisión de
  revisión del papel — el programa la espera, no la improvisa.
- La confirmación en vivo sigue intacta y sin gastar: ventana fresca de 14
  días post-adopción, línea de base viva bit 0,909 / planes planificados
  0,846 (pre-registro §9).

## 8. Estado y recibos

- Ledger del programa: `alma-sobre-claude-ledger.jsonl` — 4 eventos
  (preregistro · corpus_construido · validador_congelado · linea_base_v0),
  cadena verificada íntegra, último hash 6424e20220….
- Archivos: `alma_sobre_claude/` (corpus_datos.py · construir_corpus.py ·
  validador_plan.py · planes_v0_datos.py · puntuar.py · ledger.py ·
  corpus_planes.jsonl · planes_reales.jsonl · planes_v0.jsonl ·
  resultados_v0.json).
- Nada de esto se publicó ni salió de la máquina. La configuración vigente de
  Muse no cambió en ningún punto.
