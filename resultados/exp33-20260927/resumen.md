# ALMA-EXP33 — resumen

**Pregunta:** ¿EVI + detección de cambios supera al probe siempre-activo?
**Veredicto: NO CONFIABLE** (mock, US$0, 8 seeds 3221–3228, 50 episodios/régimen)

## Números (regret medio por episodio)

| Régimen      | siempre | evi   | evi-cd |
|--------------|---------|-------|--------|
| Estacionario | 55,19   | 13,67 | 14,61  |
| Flip         | 54,35   | 66,92 | 69,29  |
| Pooled       | 54,77   | 40,30 | 41,95  |

Tasa de probe: estacionario {siempre 1,00 / evi 0,147 / evi-cd 0,153};
flip {siempre 1,00 / evi 0,223 / evi-cd 0,383}.
Tasa de detección (evi-cd): estacionario 0,009 (falsos positivos, bien);
flip 0,159.

Criterio pre-registrado: PASS si evi-cd < siempre Y evi-cd < evi en AMBOS
regímenes. En medias: estacionario vs_siempre ✓ / vs_evi ✗ (+0,94);
flip vs_siempre ✗ (+14,94) / vs_evi ✗ (+2,36).

## Por qué NO CONFIABLE y no FAIL

Diffs por seed (evi-cd − control):
- Estacionario vs_evi: [+0,48, +9,10, +0,55, +6,65, +0,26, −4,46, +0,05, −5,14]
  → 6 positivas, 2 negativas: cambio de signo.
- Flip vs_evi: [+3,36, +2,47, +3,72, −0,12, +4,94, −0,84, +3,74, +1,61]
  → 6 positivas, 2 apenas negativas: cambio de signo.
- Flip vs_siempre: las 8 positivas (+10 a +19): evi-cd pierde siempre.

La regla pre-registrada (cambio de signo → NO CONFIABLE) se dispara por
los diffs vs_evi. Parte del ruido viene del diseño: evi-cd usa su propio
stream RNG (vs_evi no está perfectamente pareado); futuros tests deberían
usar números aleatorios comunes entre tratamientos.

## Diagnóstico del mecanismo

El detector tiene lag de 1 bloque por construcción: detecta con los pulls
del bloque anterior. En el régimen flip de EXP32 (alterna CADA bloque),
cuando el detector dispara, el mundo ya volvió a flipear: el probe forzado
llega tarde y es costo puro (~2,4+ por probe). Por eso en flip la detección
suma ~16pp de probes (22%→38%) y el regret sube +2,36 vs evi-puro.
En estacionario el detector se porta bien (0,9% falsos positivos) pero los
probes forzados son costo sin beneficio (+0,94 vs evi).

**Lección:** la detección de cambios vale cuando los flips son ralos
respecto del lag de detección, no cuando cada bloque es un flip. El régimen
flip de EXP32 es adversarial para cualquier detector con lag. Predicción no
testeada → candidata EXP34: flips ralos (1 por episodio).

Replicación de EXP32 verificada automáticamente: igualdad exacta en
siempre/evi (55,185/13,674 estacionario; 54,345/66,924 flip).
