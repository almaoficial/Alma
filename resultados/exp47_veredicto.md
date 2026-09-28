# ALMA-EXP47 — Veredicto: PASS + ESCALA (fase mock)

**Fecha:** 2026-09-27 ~15:10 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Pre-registro:** `resultados/exp47-20260927/preregistro.json` (escrito antes de correr)

## Qué se testea

La única pregunta abierta tras EXP45 (−1,0) y EXP46 (−0,6): ¿el efecto de
las skills **escala** con recurrencia más larga? Un solo moving part
respecto a EXP46: el horizonte (3 regímenes × 8 recurrencias = 24 bloques ×
10 items = 240 items).

**Diseño de extensión estricta:** los bloques 0–11 son bit-idénticos a
EXP46 (mismo orden de regímenes, misma secuencia de sorteo de categorías
con `random.Random(45)`, mismo namespace de RNG del oráculo `exp45-...`).
Los bloques 12–23 agregan 4 recurrencias más por régimen (orden con
`random.Random(47).shuffle`). El segmento temprano reproduce EXP46 por
construcción; el test de escala vive en el segmento tardío.

**Políticas** (verbatim EXP46):
- Control: skills condicionan el prior de Thompson; probe Q1 + re-probe Q2
  siempre.
- Tratamiento ("skip"): idéntica, salvo que con soporte fuerte (≥2
  victorias pareadas pasadas) se salta el probe y se juega el brazo de la
  skill en los 10 items. Contabilidad honesta: el probe saltado cuesta 0.
- 5 réplicas pareadas, RNG común.

## Criterio pre-registrado (dos partes)

- (a) PASS si media sobre réplicas de `regret(skip) − regret(control)` < 0
  (misma vara que EXP46).
- (b) ESCALA si media(efecto) < −0,60 (más negativo que el efecto medio de
  EXP46; comparación entre experimentos, documentada como tal).
- Regla de cierre: si NO se cumplen (a) y (b) a la vez, la línea de skills
  se cierra.

## Números

| Réplica | efecto total | early b0–11 | late b12–23 | skips | misfires |
|---|---|---|---|---|---|
| 0 | −12,00 | +1,00 | −13,00 | 9/24 | 3 |
| 1 | −1,00 | 0,00 | −1,00 | 5/24 | 1 |
| 2 | +4,00 | 0,00 | +4,00 | 7/24 | 4 |
| 3 | −3,00 | −1,00 | −2,00 | 8/24 | 3 |
| 4 | −5,00 | −3,00 | −2,00 | 9/24 | 3 |

**Efecto medio total: −3,40 → (a) PASS** (−3,40 < 0).
**Segmento temprano: −0,60** (reproduce EXP46 bit-idéntico ✓).
**Segmento tardío: −2,80.**
**(b) ESCALA: SÍ** (−3,40 < −0,60).

Regret medio: control 93,20 · skip 89,80 · mejor fija 84,20.
Skips totales: 38 en 120 bloques (media 7,6/réplica). Misfires: 14 (~37%).
Reproducibilidad vs EXP46 (bloques 0–11 bit-idénticos): **True** — el
pipeline es determinista y la extensión es limpia.

Detalle de saltos y diagnóstico por bloque (rep 0):
`resultados/exp47-20260927/report.json`.

## Honestidad incómoda

1. **La escala la maneja una réplica.** Sin rep 0 (−12), el efecto medio
   sería −1,25 (sigue pasando (a) y (b), pero justo) y el segmento tardío
   caería a −0,25 — menos negativo que EXP46. La afirmación "el efecto
   escala" es cierta en la media pre-registrada pero frágil: vive en
   1–2 réplicas de 5, igual que en EXP45/46.
2. **Los misfires escalaron con los saltos.** 14/38 (~37%) vs 1/4 en EXP46.
   Con más historia, el umbral fijo (≥2 victorias) se alcanza con victorias
   ruidosas y el brazo de la skill se vuelve *stale*: en rep 0/b18 y b23 la
   firma tech saltó con titular y contexto respectivamente mientras el mejor
   ex post era otro. El mecanismo dispara más pero con peor puntería — el
   umbral de soporte no se endurece con el horizonte.
3. **Una réplica en contra** (+4,00, con 4 misfires): cuando la skill agarra
   el brazo equivocado en un mundo ruidoso, el salto multiplica el daño en
   10 items sin red.
4. **No mueve el diagnóstico estructural.** Skip 89,80 vs mejor fija 84,20:
   ~5,6 puntos abajo en media. En 2/5 réplicas el skip le ganó a la mejor
   fija, pero el promedio sigue diciendo lo mismo que EXP44: ninguna
   maquinaria con exploración le gana sistemáticamente a la mejor fija en
   un mundo que rota.
5. **Condición de alcance intacta:** todo esto ocurre en un mundo diseñado
   con recurrencia garantizada. En el feed real (rotación 8/8) el mecanismo
   seguiría sin activarse ni una vez.

## Veredicto

**PASS + ESCALA.** El efecto de saltar el probe con soporte fuerte crece
con la recurrencia (−0,60 con 4 recurrencias → −3,40 con 8), y la
reproducibilidad bit-idéntica del segmento temprano confirma que el diseño
mide lo que dice medir.

**La línea de skills sigue abierta** (regla pre-registrada: se cumplían (a)
y (b) a la vez, no corresponde el cierre).

## Recomendación

Si la línea continúa, el próximo mock no debería agregar más horizonte sino
atacar el problema que EXP47 dejó visible: los misfires escalan con los
saltos. Candidatos: umbral de soporte que se endurezca con el horizonte
(≥3 victorias con 8 recurrencias), o re-validación barata del brazo de la
skill antes de saltar (1 item en vez de 5). El techo estructural (~5–6
puntos bajo la mejor fija) no lo va a mover ningún tuneo del mecanismo.

No correr fase con key: el mock responde la pregunta; medir con plata lo
que ya se diagnosticó gratis no tiene sentido.
