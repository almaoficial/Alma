# ALMA-EXP63 — veredicto: FAIL

**Fecha:** 2026-09-27 · **Costo:** US$0 (mock) · **Pre-registro:**
`resultados/exp63-passk-20260927/preregistro.json` (escrito antes de
cualquier réplica)

## Pregunta

De Shunyu Yao (τ-bench): el éxito se mide como pass^k — fracción de
tareas que salen bien en k intentos — no como media de un intento.
¿Gana el Thompson del probe si su señal de aprendizaje pasa a puntaje
de consistencia pass^3, en vez de la media cruda de un intento?

## Diseño

- Control: tratamiento EXP51 verbatim (señal cruda).
- Tratamiento: copia bit-idéntica salvo los 4 call sites de la señal
  de aprendizaje (bandit.update / rep_hist → puntaje pass^3, k=3).
  Contabilidad de regret intacta (sorteo único crudo, mismas seeds) →
  comparación pareada honesta.
- 5 réplicas, scaffold = DEFAULT_SCAFFOLD (n0=4, umbral_base=1).
- Puerto verificado: con k=None reproduce EXP51 bit-idéntico en 5/5
  (`python3 passk.py`).

## Hipótesis pre-registrada

El Thompson alimentado con consistencia elige brazos estables y baja
el regret: efecto_medio < 0 (efecto = reg_trat − reg_ctrl).

## Resultado

| réplica | reg_ctrl | reg_trat | efecto |
|---|---|---|---|
| 0 | 71 | 87 | +16 |
| 1 | 83 | 97 | +14 |
| 2 | 90 | 89 | −1 |
| 3 | 84 | 100 | +16 |
| 4 | 81 | 91 | +10 |

**efecto_medio = +11.0, IC95 [4.74, 17.26] — FAIL.**
4/5 réplicas en contra; el IC95 no toca el 0.

Secundario (tasa de bloques consistentes, reg_bloque==0 en 3 seeds):
0.0 en ambos brazos — la métrica quedó demasiado estricta para ser
informativa; se reporta como medida, no decide nada.

## Diagnóstico post-hoc (no pre-registrado, hipótesis para archivo)

pass^3 binariza la señal: un brazo que acierta 2/3 puntúa 0, igual que
uno que acierta 0/3. El Thompson pierde el gradiente que necesita para
separar brazos medios (p~0.6–0.8, los típicos brazos ganadores de este
stream): sus posteriores se vuelven pesimistas y ruidosos, y la
selección intra-bloque empeora. La consistencia es un proxy más
estricto Y más ruidoso que la media cruda — optimizar el proxy no
optimiza el objetivo cuando el reward es por intento.

## Consecuencia pre-registrada

Se CONSERVA el objetivo anterior (media de un intento). La señal cruda
sigue siendo la del sistema. La variante pass^k queda archivada en
`integracion_fase21/passk.py` (k=None = control verbatim para futuros
experimentos de señal).
