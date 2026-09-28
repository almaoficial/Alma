# Veredicto: fase1-puerta-proveedor-real

Hipótesis: El proveedor real genera skills válidas desde experiencias, las refina ante contradicción, y la ejecución guiada por la skill cambia el comportamiento del modelo (pregunta de comportamiento del modelo, no aritmética del mecanismo).

## Números
- réplicas: 3
- skills generadas por réplica: [2, 2, 2]
- refinamientos por réplica: [1, 1, 1]
- skills_usadas por réplica: [4, 4, 4]
- diferencia conductual (guiada−raw): 0.000 IC95 [0.000, 0.000]
  por firma: {'aritmetica': {'n': 20, 'dif_media': 0.0, 'raw_ok': 20.0, 'guiada_ok': 20.0}, 'razonamiento': {'n': 20, 'dif_media': 0.0, 'raw_ok': 17.0, 'guiada_ok': 17.0}}
- costo total: US$0.0412 (tope autorizado 0.50, duro 0.40)

## Criterios pre-registrados
- 1_generacion: ✓
- 2_refinamiento: ✓
- 3_proveedor_consultado: ✓
- 4_modo_skills: ✓
- 5_costo: ✓
- 6_conductual: ✗

## Veredicto

**FAIL**

Criterio: PASS ssi se cumplen TODAS: (1) >=1 skill generada válida (SKILL.md parsea, registrada en índice, estado active) en >=2/3 réplicas; (2) >=1 refinamiento a v2 en >=1 réplica; (3) el proveedor real fue consultado por el resolver en las 3 réplicas y skills_usadas >= 1 en >=1 réplica; (4) el detector de recurrencia operó en modo 'skills' (la compuerta no bloqueó el loop); (5) costo total <= US$0.50 y el corte duro de presupuesto no se disparó por error; (6) la diferencia pareada media (guiada - raw) en Parte B es > 0 en el agregado de las 2 firmas (40 pares).

Falla: FAIL si cualquiera de (1)-(6) no se cumple. El reporte dirá exactamente qué parte falló. Si falla solo (6): el loop funciona mecánicamente pero los procedimientos generados no mejoran al modelo — se rediseña antes de fase 2 (diseño §5: mejor generación o skills como priors).
