# EXP67 — Veredicto: PASS (pre-registrado 2026-09-27)

Fase de políticas completa: 918 llamadas, US$0,2667 (freno US$0,45), ~51 min.
5 políticas × 180 problemas del stream (9 bloques × 20, orden pre-registrado),
RNG pareado por posición, evaluador idéntico al EXP62.

## Regret total por política

| Política | Regret |
|---|---|
| alma-full | **3,445** |
| fija-cot | 10,945 |
| thompson-global | 10,995 |
| fija-single | 19,645 |
| fija-reflexion | 36,895 |

## Vara pre-registrada (necesita AMBAS)
- regret(alma-full) < regret(mejor fija): 3,445 < 10,945 ✓ (menos de un tercio)
- regret(alma-full) < regret(thompson-global): 3,445 < 10,995 ✓

**PASS.** Primera evidencia de que la ventaja del loop NO es un artefacto del
mundo sintético: con tareas reales y el modelo real, aprender por régimen le
gana a los planes fijos y al aprendiz global.

## Diagnóstico
- El probe eligió bien en los 3 bloques iniciales (gsm8k→cot, mmlu→single,
  mbpp→single — coincide con el oráculo) y el skip funcionó 6/6 sin misfires:
  a partir del bloque 3 el loop ya sabía qué brazo usar por slice y no gastó
  más en probar. 27 pulls de probe en vez de 81.
- thompson-global (10,995) no le gana a la mejor fija (10,945): aprender sin
  distinguir regímenes no alcanza — la memoria por slice es load-bearing.
- fija-reflexion (36,895) confirma el patrón: el brazo caro sangra en el
  evaluador que pondera costo.
- alma-full tocó regret 0,0 en 3 bloques; su peor bloque fue 0,87.

## Trazabilidad
Oráculo: 1080 pulls, US$0,3609. Piloto: puerta ABIERTA, US$0,0623.
Costo total del experimento: ~US$0,69 (piloto + oráculo + políticas).
