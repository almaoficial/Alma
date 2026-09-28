# ALMA-EXP55 — Pre-registro: ablación TTRL (¿voto o commit?)

**Fecha**: 2026-09-27. **Modo**: mock, US$0. Sin API key.

## Estado de la serie

- EXP53 (SkillRL): FAIL, efecto +5,20. El banco versionado con scoring no reemplaza la memoria plana.
- EXP54 (TTRL): PASS **frágil** — efecto medio −2,20 (por réplica: −10, +10, −1, −12, +2).
  Sin la mejor réplica el efecto es +0,25 = FAIL. El voto de consenso acierta
  48,7% y su accuracy NO predice el efecto (rep 4 acierta 61% y pierde;
  rep 2 acierta 22% y gana). Regret: 84,20 vs 86,40, mejor fija 84,20.
- Lo testeado en EXP54 fue voto+commit juntos, no sus partes.

## Pregunta abierta

¿El valor de EXP54 está en el **voto** (los rollouts de consenso identifican
mejor el brazo) o en el **commit** (jugar greedy temprano en vez de Thompson)?

## Diseño

- **Mundo**: stream de 24 bloques bit-idéntico a EXP49/51/53/54
  (`run_experiment47.construir_stream`), 5 réplicas pareadas, RNG común
  (namespaces `exp45-r{rep}-b{b}-q{q}-{a}` idénticos; el oráculo es el mismo).
- **Control**: la política de EXP51 VERBATIM
  (`run_experiment51.correr_replica_probe_barato`, importada). Se verifica
  reproducibilidad bit-idéntica contra el tratamiento de EXP51
  (`resultados/exp51-20260927/report.json`, columna `reg_trat_bloques`).
- **Variante A ("consenso-sin-commit")**: COPIA de EXP54 salvo UN moving part:
  el consenso round-robin en 3,4,5 es idéntico (mismos candidatos top-2,
  mismos sorteos, el bandit queda informado por las observaciones del
  consenso), pero el ganador del voto se IGNORA — se calcula solo para
  diagnóstico. El juego post-consenso es idéntico al control: gate + Thompson
  en (6,7,8,9) con gate, re-probe 6,7 + Thompson en (8,9) sin gate.
  La ablación aísla el comportamiento de commit, no la información.
- **Variante B ("commit-sin-consenso")**: COPIA del control salvo UN moving
  part: sin rollouts de consenso; commit greedy inmediato al top-1 post-probe
  (c1 = el mismo candidato #1 que EXP54 elegiría, por media del bandit
  post-probe con desempate por índice) en todos los items que el control
  juega con Thompson: 3,4,5 siempre; 6,7,8,9 con gate; 8,9 sin gate
  (6,7 sin gate = re-probe con scoring fav, idéntico al control).
  Probe, gate, Q2, skips y probe_obs idénticos al control por construcción.
- Bloques saltados: idénticos al control en ambas variantes.

## Hipótesis

- H_A: si el valor está en la **información del voto** (identificar el brazo
  con 3 rollouts baratos), A gana al control aunque ignore el commit.
- H_B: si el valor está en **explotar temprano** la conjetura del bandit,
  B gana al control sin necesidad del voto.
- H_0 (refutación): si ninguna gana, el PASS de EXP54 fue ruido/interacción
  frágil, no un mecanismo real.

## Criterio PRE-REGISTRADO (por variante, misma vara de la línea)

- efecto_X = media sobre réplicas pareadas de regret(X) − regret(control).
- **PASS_X ⟺ efecto_X < 0**. Sin margen adicional: la vara es refutación.

## Regla de interpretación (pre-registrada, vinculante)

1. **A PASS + B FAIL** → el valor está en el voto (identificación), no en el
   commit greedy. Próximo: mejorar el voto, no el commit.
2. **B PASS + A FAIL** → el valor está en el commit temprano; el consenso es
   lastre (3 items gastados sin comprar información útil). Próximo: commit
   más barato, sin rollouts.
3. **Ambos PASS** → ambos componentes aportan. Comparar magnitudes y contra
   EXP54 (−2,20): si EXP54 supera a ambos, hay sinergia voto×commit;
   si una variante empata a EXP54, la otra sobra.
4. **Ambos FAIL** → EXP54 no era un mecanismo: fue fragilidad entre réplicas.
   La serie oriental pasa a la siguiente idea; TTRL se archiva como refutado
   en este mundo.

## Diagnósticos auxiliares (no cambian el veredicto)

- Efecto sin la mejor réplica por variante (fragilidad, estándar de la línea).
- Distancia de cada variante a la mejor fija (¿se achica el hueco 2,20?).
- A: accuracy del ganador ignorado vs mejor ex-post en items de commit
  (¿el voto identifica aunque no se use?).
- B: el commit es total por construcción en bloques con probe (sin fallback).
- Referencia EXP54 (−2,20) como techo a batir, no como control.
