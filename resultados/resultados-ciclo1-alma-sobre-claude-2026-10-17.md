# Resultados del ciclo 1 — «ALMA sobre Muse»: v1 (ranuras fijas + horario obligatorio) en pantalla

**Fecha:** 17/10/2026. **Autorización:** Alejandro, 17/10/2026 («Vamos con
alma sobre Muse»), sobre el pre-registro
`preregistro-alma-sobre-claude-2026-10-17.md` (md5
5fc4af7fe10344a4ed9eccbb2ffe0301). **Costo:** US$0. **Alcance:** solo la
arena de pantalla. Ninguna configuración vigente cambió; ningún dato en
vivo alimentó la selección; la confirmación (§9 del pre-registro) no corre
porque no hubo adopción en pantalla.

## 1. El protocolo, tal como se ejecutó

- **Variante:** v1 = v0 + el único cambio declarado en §6.3 del
  pre-registro — ranuras fijas (punto 2 siempre el ancla de rutina
  factible, nunca un frente; punto 3 siempre la guarda de plata si hay
  hecho crítico, o la condición de cierre del día si no) y **horario
  obligatorio del compromiso en el punto 1**.
- **Generación:** los mismos 15 paquetes-día del corpus congelado
  (sha256 d527f50b4ed1…), 4 pasadas por día en distinto orden de días,
  n = 60 instancias, cada plan escrito **solo desde el paquete de ese
  día**, sin mirar la verdad de terreno ni el plan real — el mismo
  protocolo de la línea de base. Archivo: `alma_sobre_claude/planes_v1.jsonl`
  (sha256 d31dc8becf33…), datos en `planes_v1_datos.py`.
- **Validador:** el congelado v1 (7 chequeos C1–C7, determinista, sin
  juez LLM). Su sha256 se verificó **antes y después** de puntuar:
  a52fe837798d… en ambos casos — no se tocó una línea.
- **Limitación declarada antes de puntuar:** la ventana horaria del
  punto 1 solo puede escribirse si el paquete la trae. En **9 de los 15
  días (36/60 instancias)** el paquete no trae ninguna ancla temporal
  para el compromiso (2, 3, 5, 7, 9, 10, 11, 12 y 15/10: vencimientos
  «hoy», movimientos «antes de que postee», pendientes sin hora). En
  esos ítems el punto 1 nombra el compromiso **sin horario** — fabricar
  uno violaría el paquete. La ventana sí salió del paquete en 6 días
  (4: 6:45–14:00 · 6: a las 10 · 8: esta mañana · 13: a las 10 · 14:
  9 a 18 · 16: 10:23). La letra de v1 presume que los compromisos
  traen hora; el corpus muestra que la mayoría no trae. Queda asentado
  como hallazgo de diseño del ciclo, no como excusa: así se corrió.
- **Juicio de aplicación declarado:** en 4 y 11/10 (C4 no aplicable,
  sin ancla de rutina factible a la mañana por el turno 6:45–14) la
  ranura 2 llevó el bloque estructurado del día (estudio 16–19; revisión
  de las 16 secciones), el mismo criterio con que la v0 generada llenó
  esa ranura en la Fase 2.

## 2. El resultado de pantalla

**v1: media 0,9972 · desvío 0,0215 · n = 60** (mínimo 0,8333 · máximo
1,0000). Contra la línea de base asentada: **v0: media 0,9828 · desvío
0,0523 · n = 60**.

| Chequeo | v0 | v1 | Δ | n |
|---|---|---|---|---|
| C1 formato (3 puntos, sin preguntas) | 1,000 | 0,983 | −0,017 | 60 |
| C2 cobertura del compromiso | 1,000 | 1,000 | 0,000 | 60 |
| C3 horario del compromiso | 1,000 | 1,000 | 0,000 | 20 |
| C4 ancla factible, ninguna infactible | 0,904 | **1,000** | **+0,096** | 52 |
| C5 sin invenciones de montos | 1,000 | 1,000 | 0,000 | 60 |
| C6 guarda de plata (días críticos) | 0,975 | **1,000** | **+0,025** | 40 |
| C7 el compromiso lidera (punto 1) | 1,000 | 1,000 | 0,000 | 60 |

59 de 60 instancias puntúan 1,0000. La única por debajo es 12/10 rep 1
(0,8333), por C1 — y su causa está identificada: el plan cita la etiqueta
«(banco · 11/10 23:23)» y el segmentador congelado lee el «3)» final de
«23:23)» como un cuarto marcador de punto. Es un artefacto del
instrumento, nombrado como tal en §4; **no se corrigió ni el plan ni el
validador**, y el veredicto no depende de él (cuenta en §3).

Lo que la pantalla sí midió, sin artefactos: la ranura fija eliminó la
única ambigüedad real de la v0 codificada. En la línea de base, C4 caía
en 5 instancias porque la v0 permite «ancla **o** frente» en el punto 2
y el generador a veces ponía el frente; v1 no lo permite, y C4 fue
52/52. C6 subió por la misma vía: la guarda de plata, al tener ranura
propia obligatoria, dejó de quedar implícita (la única caída de v0 en
C6 era una guarda sin palabras de guarda; v1 la escribe siempre).

## 3. El veredicto, con su cuenta explícita

Reglas del pre-registro §10, δ del §8 congelado antes de generar v1:

- Δ = media(v1) − media(v0) = 0,9972 − 0,9828 = **+0,0144**.
- SE de la diferencia: 0,0095 con la fórmula del papel (s₀ congelado);
  0,0073 usando los desvíos de ambas variantes. Δ equivale a ~1,5–2,0 SE.
- δ congelado = **0,1000** (manda el efecto mínimo de interés).
- Techo posible contra esta línea de base: 1,0000 − 0,9828 = 0,0172.
  Δ consumió el **84 %** de todo el margen que la batería puede ver.

**Cuenta:** 0 < +0,0144 < 0,1000 → no alcanza ADOPCIÓN y no es ≤ 0.

### Veredicto del ciclo 1: **SEÑAL PARCIAL**

(asentado en el ledger, evento `ciclo1_veredicto`). Hay dirección —
la mejora cae exactamente donde el cambio apuntaba (C4 y C6, las dos
ranuras fijadas) — sin la resolución que el δ exige para adoptar. No
se ajustó nada tras ver los números: ni δ, ni el validador, ni el
corpus, ni la definición de v1. La cuenta es invariante al artefacto
de C1: aun puntuando 1,0000 esa instancia, v1 sería 1,0000 y Δ =
+0,0172 — el techo entero — y seguiría debajo de δ.

Consecuencia por las reglas: v0 sigue siendo la configuración vigente,
no hay ventana de confirmación en vivo (no hubo adopción en pantalla),
y el freno del programa queda en **1 de 3 ciclos sin adopción**.

## 4. Análisis de modos de falla vividos: la brecha que la pantalla no ve

El informe de línea de base dejó la brecha central del programa: los 15
planes **reales vividos** puntúan 0,8511 con esta misma vara, contra
0,9828 de la v0 generada con cuidado offline — una brecha de **0,132**,
concentrada en C4 en vivo (6/13: la mañana real se comía el ancla) y C6
en vivo (8/10: guardas implícitas o ausentes). ¿Qué dice el ciclo 1
sobre esa brecha? Con los números de este ciclo:

- **Lo que la pantalla midió:** si la *letra* de la política mejora su
  propia aplicación cuidadosa. Respuesta: sí, por +0,0144, llevando C4
  y C6 de pantalla a su techo (1,000 en ambos). Si la v1 se adoptara,
  la política «aplicada con cuidado» quedaría en 0,9972.
- **Lo que la pantalla sigue sin medir:** la aplicación bajo carga
  real. Nada en este ciclo corrió a las 07:30 con otras tareas
  compitiendo, que es donde la brecha vive. Aun con la letra perfecta,
  el ancla de los planes vividos falló 7 de 13 días aplicables — y el
  mecanismo de esa falla (el frente se come la ranura) es exactamente
  el que la v1 prohíbe en el papel y la pantalla confirma en frío. La
  pantalla **no puede distinguir** entre «la letra nueva se aplicará
  mejor en vivo» y «en vivo pasará lo mismo con letra nueva»: esa
  pregunta solo la responde la arena de confirmación, y la
  confirmación solo corre tras una adopción que este ciclo no produjo.
- **La lectura honesta:** el ciclo 1 cerró la pregunta chica (¿la
  letra v1 supera a la letra v0 bajo la vara?) con «dirección sí,
  magnitud bajo el piso», y dejó intacta la pregunta grande (¿por qué
  la mañana vivida pierde 0,132 contra su propia política?). El
  instrumento que podría ver esa brecha no es esta batería: es una
  batería v2 cuyos ítems fuercen los modos de falla vividos (mañanas
  con frentes compitiendo por la ranura), o puntuar los planes vividos
  futuros contra la vara con la misma cadencia. Diseñar eso es papel
  nuevo — decisión de Alejandro, no de este ciclo (§6).

## 5. Informe de auto-evaluación de Muse (estructura fija §12)

1. **Qué se midió:** la superficie 1 (estructura del plan matutino);
   la variante v1 (ranuras fijas + horario obligatorio en el punto 1)
   contra la v0 codificada; panel de pantalla de 60 instancias por
   variante (15 días × 4 pasadas) sobre el corpus congelado de días
   reales 2–16/10; validador determinista v1 de 7 chequeos, sha256
   a52fe837798da4786473b7d0cfbb0d08efb1933f469bc8cc33d6d24308c5b627,
   verificado antes y después.
2. **Número central:** v1 = 0,9972 (desvío 0,0215) contra v0 = 0,9828
   (desvío 0,0523); Δ = +0,0144, contra el δ congelado de 0,1000.
   La mejora se concentra en los dos chequeos que el cambio tocaba:
   C4 0,904 → 1,000 y C6 0,975 → 1,000.
3. **Veredicto:** SEÑAL PARCIAL (§10). Sin adopción en pantalla; la
   confirmación en vivo no corrió y sigue sin gastar (ventana fresca
   intacta, líneas de base vivas bit 0,909 / planificados 0,846).
4. **Qué es ruido — dicho antes de que lo lea otro:** (a) la única
   instancia bajo 1,00 es el artefacto del segmentador con la etiqueta
   «23:23)» — no es una falla de la política ni del plan, y el
   veredicto es el mismo con o sin ella; (b) Δ = +0,0144 es ~1,5–2,0
   errores estándar: dirección consistente en los dos chequeos
   apuntados, magnitud indistinguible de «casi todo el margen que la
   vara permite» — con la base a 0,0172 del techo, esta batería ya no
   puede separar una letra mejor de una letra perfecta; (c) el C3 en
   1,000 no prueba que el horario obligatorio «funcione»: solo 5 de 15
   días tenían hora en la verdad de terreno y en 9 días el mandato fue
   incumplible desde el paquete — la pantalla no midió el horario, midió
   su ausencia de costo donde existía; (d) nada de este ciclo dice
   algo sobre las mañanas vividas: la brecha de 0,132 sigue medida
   solo por el ancla de la Fase 2.
5. **Estado de la serie del programa:** adopciones **0** · señales
   parciales **1** (este ciclo) · nulos 0 · reversiones 0. Freno:
   **1 de 3** ciclos sin adopción.

## 6. Estado del freno y qué queda para un eventual ciclo 2

- **Freno del programa:** 1 de 3. Dos ciclos más sin adopción y el
  programa se detiene a esperar la revisión de Alejandro (§10). Este
  ciclo no estuvo cerca de mover ninguna vara: δ, validador, corpus y
  ventana quedaron como se firmaron.
- **Qué queda listo:** la batería v1 congelada y reutilizable tal
  cual; la línea de base y el δ asentados; la confirmación en vivo sin
  gastar; y un hecho nuevo y duro para decidir: **la pantalla actual
  está agotada como instrumento de adopción para esta superficie** —
  su techo (0,0172) es menor que su propio δ (0,1000), así que ningún
  ciclo 2 con esta batería y esta base puede adoptar, corra lo que
  corra. Seguir corriendo variantes contra ella solo puede producir
  señales parciales y nulos, y consumir el freno.
- **La decisión que le toca a Alejandro** (sin diseñar acá el ciclo 2):
  si el programa sigue sobre esta superficie, el papel nuevo tiene
  que cambiar el instrumento contra los modos de falla **vividos** —
  p. ej., una batería v2 con ítems adversariales que fuercen la
  competencia por la ranura del ancla, o medir la serie de planes
  vividos contra la vara como pantalla — o cambiar de superficie
  (roadmap §6.4 del pre-registro). Repetir el ciclo 1 con otra letra
  contra la misma batería no es una opción que este informe recomiende:
  mediría el techo, no la mejora.

## 7. Recibos

- Ledger del programa (`alma-sobre-claude-ledger.jsonl`): **8 eventos**
  (preregistro · corpus_construido · validador_congelado ·
  linea_base_v0 · ciclo1_apertura · ciclo1_generacion · ciclo1_puntaje
  · ciclo1_veredicto), cadena verificada íntegra al cierre, hash final
  **62fc0822a359…**.
- Archivos del ciclo: `alma_sobre_claude/planes_v1_datos.py`,
  `alma_sobre_claude/planes_v1.jsonl`,
  `alma_sobre_claude/puntuar_ciclo1.py`,
  `alma_sobre_claude/resultados_ciclo1.json`, este informe.
- Nada se publicó ni salió de la máquina. La configuración vigente de
  Muse no cambió en ningún punto: v1 existe solo como instancias
  medidas en pantalla.

---

*Ciclo 1 cerrado el 17/10/2026 bajo el pre-registro fundacional del
programa «ALMA sobre Muse». Primera entrada de la serie de
auto-evaluación (§12): el asistente midió una variante de su propia
configuración, no alcanzó el piso para adoptarla, y lo asienta.*
