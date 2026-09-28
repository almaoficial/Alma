# ALMA-EXP52 — Veredicto: FAIL + LÍNEA CERRADA (mock)

**Fecha:** 2026-09-27 ~15:45 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Pre-registro:** `resultados/exp52-20260927/preregistro.json` (escrito antes de correr)

## Qué se testea

La interacción gate↔soporte que EXP51 dejó al descubierto: los bloques con
gate dejan `probe_obs` de 3 items, esa evidencia ruidosa alimenta la cuenta
de victorias del skip, el tratamiento salta de más (18 vs 14) y los skips
extra misfirean (5/18 vs 2/14). Un solo moving part sobre la base
(probe-barato de EXP51, verbatim como control): **los bloques con gate NO
aportan victorias al soporte** — solo los probes completos (Q1+Q2, 5 items)
cuentan para K y wins. El gate sigue abaratando el probe; su ruido ya no
alimenta la decisión de saltar.

Variante elegida: (a). Descartada (b) exigir margen en Q1: ataca el gate
mismo (lo que funciona: −24 en EXP51) en vez de la interacción, y un margen
sobre medias de 3 items es a su vez ruidoso. Mi juicio fue que (a) era la
más limpia porque restauraba el significado original del soporte. **Ese
juicio quedó refutado por los números de abajo.**

**Criterio pre-registrado:** pasa_1 = media(reg_trat − reg_ctrl) < 0 →
PASS/FAIL. **Regla de cierre pre-registrada:** la línea CONTINÚA solo si
(i) efecto medio < −2,0 Y (ii) d_trat < 1,8; si no, **SE CIERRA** con
dictamen explícito de techo estructural.

## Números

| Réplica | efecto | reg trat | reg ctrl | skips trat (mis) | skips ctrl (mis) | Q2 gate trat | Q2 gate ctrl |
|---|---|---|---|---|---|---|---|
| 0 | +14,00 | 96,0 | 82,0 | 0 (—) | 5 (1) | 6 | 3 |
| 1 | +0,00 | 88,0 | 88,0 | 0 (—) | 0 (—) | 8 | 8 |
| 2 | −3,00 | 89,0 | 92,0 | 0 (—) | 2 (2) | 3 | 3 |
| 3 | +9,00 | 104,0 | 95,0 | 0 (—) | 6 (1) | 5 | 3 |
| 4 | +5,00 | 80,0 | 75,0 | 0 (—) | 5 (1) | 5 | 3 |

**Efecto medio: +5,00 → FAIL** (pasa_1: +5,00 < 0 ✗).
Media sin la mejor réplica: +7,00 → cargado por una sola réplica (SÍ, la +14).
**Distancia a la mejor fija:** tratamiento 91,40 − 84,20 = **7,20**
(control: 86,40 − 84,20 = 2,20). El hueco no se achicó: se **triplicó**.
**Regla de cierre:** (i) +5,00 < −2,0 ✗ | (ii) 7,20 < 1,8 ✗ →
**LA LÍNEA SE CIERRA.**
Reproducibilidad del control vs EXP51: bit-idéntico (True).

**El dato que lo explica todo: el tratamiento saltó 0 bloques en 120
oportunidades** (control: 18). El moving part no redujo los skips: los
eliminó.

## Honestidad incómoda

1. **Mi elección de variante estaba mal, y el mecanismo de la falla es más
   interesante que "menos skips".** La nota de refutación anticipó que K
   caería y el umbral se volvería más difícil — pero lo que ocurrió es
   **selección adversa en el pool de evidencia**, no simple escasez: el
   gate dispara *exactamente cuando Q1 es decisivo a favor del brazo de la
   skill*, es decir, en los bloques donde la skill se ve fuerte. Los
   bloques con probe completo son, por construcción, los bloques donde Q1
   NO fue decisivo — donde la skill se ve débil. Al excluir los bloques
   con gate, me quedé solo con la evidencia adversamente seleccionada:
   en la réplica 0 (dinero), wins quedó clavado en 2 mientras K crecía
   3→4→5 y el umbral subía 3→4. Espiral de muerte: cada probe completo que
   no suma una victoria *sube la vara* (2+floor(K/3)) sin acercar el salto.
   La evidencia de 3 items no era solo ruido: era evidencia *seleccionada*
   (Q1-decisiva), y contenía las victorias más fuertes del soporte. La
   quité y maté el mecanismo.
2. **El +5,0 es, post-hoc, una medición limpia del valor del skip.**
   Tratamiento = control menos el skip (el gate es idéntico en ambos;
   el gate disparó 27 vs 20 veces justamente porque al no saltar nunca hay
   más bloques con probe). Los 5 puntos que pierde el tratamiento son los
   5 puntos que el skip aportaba. El skip es load-bearing: sin él, la
   política vuelve a 7,2 puntos bajo la mejor fija, peor que EXP49.
3. **El FAIL no es ruidoso: es unánime en el mecanismo.** 4 de 5 réplicas
   en contra (+14, 0, +9, +5); la única a favor (−3, rep 2) es la réplica
   donde el control más misfireaba (2/2), es decir, donde *no saltar*
   evitó dos errores — no una vindicación del moving part sino del azar
   de esa réplica.
4. **La línea muere con las botas puestas, no por accidente.** Siete
   experimentos (EXP45–51) dibujaron el mismo perfil: efecto real, chico
   (~1–2% del regret), frágil entre réplicas, y ~2 puntos bajo la mejor
   fija que ningún moving part movió de forma material. EXP52 fue el
   intento directo de reparar la interacción que mandaba, y la reparó
   matando al paciente. El dictamen pre-registrado se aplica sin
   ambigüedad.
5. **Condición de alcance intacta:** todo ocurre en el mundo construido con
   recurrencia garantizada. En el feed real el mecanismo no se activaría.

## Dictamen de cierre (pre-registrado, sin ambigüedad)

**LA LÍNEA DE SKILLS SE CIERRA.** No se cumplieron ni (i) ni (ii): efecto
medio +5,00 (lejos del < −2,0 exigido) y distancia a la mejor fija 7,20
(lejos del < 1,8 exigido). El techo ~2 puntos bajo la mejor fija es
**estructural del mundo** (regímenes con 2/10 de ruido por bloque, 10
items por bloque, 30 categorías rotando), no del mecanismo: siete
variantes atacaron el probe, el soporte, el umbral, la selectividad y la
interacción, y ninguna movió el neto de forma material. El mejor punto
alcanzado queda en EXP51 (efecto −1,60, hueco 2,20).

Lo que la línea deja como conocimiento reutilizable: (a) el valor de la
skill está en *elegir bien* (EXP50, dirimente vs azar); (b) el gate
adaptativo abarata el probe donde opera (−24 en EXP51); (c) el skip es
load-bearing (−5,0 medido en EXP52); (d) la evidencia ruidosa pero
*seleccionada* (Q1-decisiva) vale más que la evidencia limpia pero
adversamente seleccionada — lección contra-intuitiva para cualquier
diseño futuro de soporte de skills.
