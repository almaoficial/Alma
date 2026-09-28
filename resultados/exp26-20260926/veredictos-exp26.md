# ALMA-EXP26 — veredictos

**Pregunta:** ¿el probe-transfer de ALMA v2 aporta algo sobre Thompson pelado
desde cero, o es peso muerto?

**Veredicto por horizonte: NO CONFIABLE en ambos.**

| Horizonte | regret(a) ALMA v2 | regret(b) Thompson cero | diffs a−b | Veredicto |
|---|---|---|---|---|
| 120 | 5,625 | 4,125 | −1,55 / +0,2 / +1,95 / +8,45 / −0,55 / +0,5 | NO CONFIABLE |
| 240 | 8,725 | 8,250 | +7,83 / +1,9 / +1,05 / +1,6 / −5,85 / −3,68 | NO CONFIABLE |

**Hipótesis propia: no sostenida.** Esperaba (a) ganando en 120 y (b) en 240.
Los datos no la acompañan: las medias (no confiables) favorecen a (b) en
ambos horizontes.

## Lo que sí es sólido (mecánica, 48 celdas clase×seed)

- **El probe acierta ~al azar: 13/24 (h120) y 12/24 (h240).** Con la trampa
  (la clase conocida más cercana tiene mejor brazo distinto), pedir prestado
  por parecido es una moneda cargada en contra, y 8 pulls no alcanzan para
  dar vuelta el prior equivocado.
- **El daño se concentra donde muerde la trampa:** N1 (a−b = +3,43 en h120)
  y N3 (+3,13 en h120, +8,10 en h240). Donde el probe acierta, (a) empata o
  gana apenas (N0 −0,20, N2 −0,37).
- **Los compromisos duros (11/24 y 8/24) son la factura:** cuando el probe
  elige mal y el gap cruza el umbral, el compromiso duro multiplica el error.

## Lectura honesta

El probe-transfer no repara un prior de similitud engañoso; le suma costo de
medición. La transferencia por parecido es el eslabón débil, no el probe:
cuando el vecino más cercano miente, ningún presupuesto de medición razonable
lo corrige (EXP25 ya mostró que medir más cuesta linealmente). Thompson pelado
no necesita que el mapa sea correcto — por eso nunca pierde feo.

La herida sigue abierta, pero ahora con diagnóstico de causa: **el problema no
es cuánto medir, es a quién pedirle prestado.** El fingerprint de parecido es
el que hay que refutar o reemplazar, no el probe.

## Archivos

- `preregistro.json` — hipótesis, criterio por horizonte (escrito antes de correr)
- `report.json` — horizonte × seed × clase, diffs, gaps, compromisos
- `run_experiment26.py` — script re-ejecutable

Costo: US$0 (mock). EXP18 no tocado.
