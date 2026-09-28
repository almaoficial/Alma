# ALMA-EXP31 — ¿el orden TRIZ abarata el probe?

Mock, US$0. Probe secuencial con parada temprana; números aleatorios comunes por problema.

| seed | pulls triz | pulls fijo | pulls aleat | prec triz | prec fijo | prec aleat | win |
|------|------------|------------|-------------|-----------|-----------|------------|-----|
| 3121 | 1.670 | 1.975 | 1.990 | 0.870 | 0.815 | 0.825 | ✓ |
| 3122 | 1.550 | 1.900 | 2.070 | 0.905 | 0.825 | 0.830 | ✓ |
| 3123 | 1.560 | 1.945 | 1.890 | 0.855 | 0.820 | 0.845 | ✓ |
| 3124 | 1.640 | 2.080 | 2.040 | 0.865 | 0.815 | 0.790 | ✓ |
| 3125 | 1.645 | 1.995 | 2.015 | 0.870 | 0.815 | 0.760 | ✓ |
| 3126 | 1.555 | 1.970 | 2.025 | 0.920 | 0.825 | 0.790 | ✓ |
| 3127 | 1.640 | 2.020 | 2.120 | 0.860 | 0.785 | 0.770 | ✓ |
| 3128 | 1.695 | 2.075 | 2.115 | 0.870 | 0.815 | 0.815 | ✓ |

**Veredicto: PASS**

W=8/8 seeds con pulls(TRIZ)<pulls(FIJO) y <pulls(ALEATORIO); precision media triz=0.877 fijo=0.814 aleatorio=0.803 (guarda <=3pp: ok).

Sensibilidad exploratoria (correlación debilitada): W=8/8.
