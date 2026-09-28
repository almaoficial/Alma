# ALMA-EXP55 — Veredicto: FAIL + FAIL → TTRL archivado (mock)

**Fecha:** 2026-09-27 ~16:20 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Serie:** "ideas orientales" (EXP53 SkillRL refutado, EXP54 TTRL PASS frágil)
**Pre-registro:** `exp55_ablacion/preregistro.md` (escrito antes de correr; incluye la regla de interpretación vinculante)

## Qué se testea

La ablación pre-registrada de EXP54: ¿el valor del TTRL está en el **voto** (los rollouts de consenso identifican el brazo) o en el **commit** (jugar greedy temprano en vez de Thompson)?

- **Variante A ("consenso-sin-commit"):** consenso round-robin en 3,4,5 idéntico a EXP54 (mismos candidatos top-2, mismos sorteos, bandit informado), pero el ganador se IGNORA — se calcula solo para diagnóstico. El juego posterior es idéntico al control (gate + Thompson / re-probe + Thompson).
- **Variante B ("commit-sin-consenso"):** sin rollouts de consenso; commit greedy inmediato al top-1 post-probe (el mismo c1 que EXP54 elegiría) en todos los items que el control juega con Thompson (3,4,5; 6,7,8,9 con gate; 8,9 sin gate; 6,7 sin gate = re-probe idéntico al control).
- **Control:** EXP51 verbatim, importado. **Reproducibilidad bit-idéntica vs tratamiento de EXP51: True.**
- Bloques saltados, Q1, Q2, gate, probe_obs: idénticos al control por construcción en ambas variantes.

**Criterio pre-registrado (por variante):** PASS ssi media(reg_X − reg_ctrl) < 0.

## Números

| Réplica | efecto A | efecto B | reg ctrl | mejor fija |
|---|---|---|---|---|
| 0 | −8,00 | −6,00 | 78,0 | 84,0 |
| 1 | +7,00 | +13,00 | 86,0 | 89,0 |
| 2 | +7,00 | +8,00 | 93,0 | 88,0 |
| 3 | −6,00 | −8,00 | 95,0 | 80,0 |
| 4 | +2,00 | +7,00 | 80,0 | 80,0 |

- **Variante A: efecto medio +0,40 → FAIL** (criterio: < 0). Sin la mejor réplica (rep 0): **+2,50**.
- **Variante B: efecto medio +2,80 → FAIL.** Sin la mejor réplica (rep 0): **+5,50**.
- **Regret medio:** A 86,80 vs B 89,20 vs control 86,40, mejor fija 84,20.
- **Distancia a la mejor fija:** A 2,60 | B 5,00 (control 2,20; EXP54 0,00).
- **A:** el ganador ignorado habría sido el mejor ex-post en **41/77 votos (53,2%)** — una moneda, igual que en EXP54 (48,7%).
- **B:** el c1 post-probe fue el mejor ex-post en **33/101 bloques con probe (32,7%)** — peor que una moneda entre 2 candidatos.

## Aplicación de la regla de interpretación pre-registrada

Cuadrante 4: **A FAIL + B FAIL → EXP54 no era un mecanismo: fue fragilidad entre réplicas. TTRL se archiva como refutado en este mundo.**

## Disección

- **El voto no compra identificación.** 41/77 (53,2%) con 3 rollouts en un mundo con ~2/10 de ruido por bloque: indistinguible de azar. La variante A —que conserva la información del consenso pero no el commit— es indistinguible del control (+0,40, distancia 2,60 vs 2,20 del control). La información simplemente no está ahí.
- **El commit temprano a una conjetura mala destruye.** B compromete 5–7 items greedy a un c1 que acierta el mejor brazo solo el 32,7% de las veces. Resultado: +2,80, el peor efecto de toda la serie oriental, y el hueco a la mejor fija se agranda de 2,20 a 5,00. Comprometer temprano multiplica el error en vez de ahorrar exploración.
- **EXP54 (−2,20) no se reproduce por partes.** Ni la información (A: +0,40) ni la explotación (B: +2,80) explican el −2,20. La diferencia EXP54−A (−2,6) vive dentro del rango de swing entre réplicas (±10): es varianza, no sinergia. El −2,20 lo cargaban las reps 0 (−10) y 3 (−12), y ninguna de las dos réplicas "buenas" se repite en la misma variante (rep 0 es la mejor de A y B a la vez, rep 3 la segunda).
- **Simetría reveladora:** en A, las réplicas que ganan son 0 y 3 (las mismas que ganaban en EXP54); en B también 0 y 3. Los mundos donde "algo" funciona son los mismos mundos, no el mecanismo: cuando el bloque es fácil, cualquier variante que toque menos el Thompson gana; cuando es difícil, todas pierden.

## Honestidad incómoda

1. **El cuadrante 4 era el más probable desde el pre-registro de EXP54** y aun así duele: el "empate con la mejor fija" (0,00) de EXP54 —el titular más lindo de toda la línea— queda oficialmente clasificado como varianza. No se rompió ningún techo.
2. **B es una advertencia para el diseño real:** comprometer jugadas a la conjetura del bandit sin evidencia fresca es la peor política testeada en la serie (+2,80). Si el sistema real alguna vez hace "commit temprano", necesita una tasa de acierto del identificador muy por encima del 33% — y este mundo no la da.
3. **Lo testeado fue voto+commit de 3 rollouts, no TTRL real** (aprendizaje de pesos en test-time). La refutación alcanza al mecanismo testeado, no a la idea oriental en general. La serie oriental no se cierra: se archiva esta instanciación.
4. **Costo de la lección: US$0.** La ablación pre-registrada funcionó exactamente para lo que fue diseñada: impedir que un PASS frágil se convirtiera en una conclusión.

## Veredicto

**FAIL + FAIL por el criterio pre-registrado (A: +0,40; B: +2,80).** La regla de interpretación vinculante dictamina: EXP54 fue fragilidad entre réplicas, no un mecanismo. La adaptación intra-bloque por consenso+voto se archiva como refutada en este mundo, junto a la SkillRL de EXP53.

## Recomendación

La serie "ideas orientales" pasa a la siguiente idea del catálogo sin reintentar TTRL en este mundo. Candidatas con aplicabilidad alta restante: SPELL (self-play questioner/responder/verifier para el probe), RSO/Darwin-GM (evolución del scaffold con keep/revert), CodeAct (pendiente de fase 1). Cada una con su ablación pre-registrada antes de concluir, como hoy.
