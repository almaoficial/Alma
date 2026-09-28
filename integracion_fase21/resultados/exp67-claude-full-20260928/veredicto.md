# EXP67-Claude-Full — Veredicto de medición: MEDICIÓN PARCIAL

Fecha: 2026-09-28 (madrugada). Pre-registro en `preregistro.md` (vara sagrada,
escrita antes de gastar).

## Veredicto
**MEDICIÓN PARCIAL** — el freno duro cortó la corrida en **790/1080 pulls
(73,1%)**. No se declara MEDICIÓN COMPLETA. No hay veredicto comparativo:
la comparación vs DeepSeek/OpenAI queda como tabla descriptiva
(pre-registrada), sin test de hipótesis y sin vara — es medición, insumo para
el registry y el router.

## Ejecución (recuperación)
- Modelo: `claude-haiku-4-5-20251001` (pineado, mismo que EXP70).
- Key: solo por surrogate del vault (`custom.anthropic`); ping
  `GET /v1/models` gratuito OK, cero 401/403 en toda la corrida.
- El worker anterior murió a las ~05:07 por error de infraestructura del
  runtime ("submission rejected during restart drain") con 125/1080 pulls
  (US$0,1564) en disco, sin reporte. La recuperación auditó: preregistro
  intacto, pulls válidos (125 únicos, 0 líneas malas), resume idempotente
  por (pid, brazo, intento). Nada se re-gastó.
- Dry-run de scorers: VERDE antes de la reanudación. 180 problemas del
  stream, orden pre-registrado (9 bloques × 20).
- Duración total de la corrida de recuperación: ~40 min (~27 pulls/min;
  mbpp más lento por max_tokens 2048 + sandbox).
- Bloques completos: 6 (gsm8k, mmlu, mbpp, mmlu, gsm8k, mbpp) + 70 pulls del
  bloque 7 (gsm8k). No se alcanzó el bloque 8 (mmlu) ni el 9 (mbpp).

## Presupuesto: freno respetado, sin overshoot
- Frente oráculo: **gastado US$1,3865 vs freno US$1,3972** → US$0,0107 de
  margen. (Freno interno más estricto que el preregistro: US$1,50 − US$0,1028
  del EXP70, para que el TOTAL no exceda US$1,50.)
- **Total del frente Claude: US$1,3865 + US$0,1028 (EXP70) = US$1,4893 ≤
  freno duro US$1,50** → margen US$0,0107.
- La regla anti-overshoot funcionó: parada limpia por proyección
  (gastado $1,3865 + pull estimado $0,002224 + slack $0,01 > freno),
  exit 2, parcial conservado. El miss del EXP70 (+2,8%) no se repitió.
- Proyección final del total: US$1,95 (medida, por encima de los US$1,83 del
  pre-registro: mbpp salió más caro que el prior del piloto).

## Medición por celda (Claude, n real)

| celda | n | reward medio | costo medio/llamada | reward/USD |
|---|---|---|---|---|
| gsm8k/single | 104 | 0,6154 | US$0,000150 | 4115,5 |
| gsm8k/cot | 104 | 0,9808 | US$0,001335 | 734,9 |
| gsm8k/reflexion | 102 | 0,9706 | US$0,002224 | 436,5 |
| mmlu/single | 80 | 0,8500 | US$0,000298 | 2848,6 |
| mmlu/cot | 80 | 0,9000 | US$0,002281 | 394,7 |
| mmlu/reflexion | 80 | 0,9000 | US$0,002995 | 300,5 |
| mbpp/single | 80 | 0,0750 | US$0,000756 | 99,1 |
| mbpp/cot | 80 | 0,1000 | US$0,002454 | 40,8 |
| mbpp/reflexion | 80 | 0,1125 | US$0,003783 | 29,7 |

Global: reward 0,6329, costo medio US$0,001755/llamada, 360,6 reward/USD.

## Comparación descriptiva (formato pre-registrado, sin veredicto)

Reward medio por (slice, brazo). DeepSeek: oráculo EXP67 completo
(n=120/celda, mismos 180 problemas). OpenAI: piloto EXP69 (n=20/celda,
**otros 30 problemas — caveat de comparabilidad**). Claude: esta corrida
(n real arriba, mismos 180 problemas que DeepSeek).

| slice/brazo | Claude (n) | DeepSeek (n=120) | OpenAI (n=20) |
|---|---|---|---|
| gsm8k/single | 0,6154 (104) | 0,6333 | 0,3000 |
| gsm8k/cot | 0,9808 (104) | 0,9667 | 1,0000 |
| gsm8k/reflexion | 0,9706 (102) | 0,9500 | 1,0000 |
| mmlu/single | 0,8500 (80) | 0,9167 | 0,6000 |
| mmlu/cot | 0,9000 (80) | 0,8000 | 0,5000 |
| mmlu/reflexion | 0,9000 (80) | 0,8000 | 0,7000 |
| mbpp/single | 0,0750 (80) | 0,1083 | 0,0000 |
| mbpp/cot | 0,1000 (80) | 0,0583 | 0,0000 |
| mbpp/reflexion | 0,1125 (80) | 0,0500 | 0,0000 |

Costo medio por llamada (US$): DeepSeek 0,000014–0,001009 (total oráculo
US$0,3609); OpenAI 0,000018–0,000251 (total piloto US$0,0276);
Claude 0,000150–0,003783 (total parcial US$1,3865).

Ganador por reward/USD con la regla EXP69 verbatim (descriptivo):
**deepseek/single en los 3 slices** (gsm8k 44522,6; mmlu 37722,9;
mbpp 2874,2). El patrón del EXP69 se mantiene: el brazo más barato le gana
al más inteligente en reward/USD, en los tres proveedores.

## Lecturas honestas (no veredicto)
1. El perfil de debilidad se replica entre los tres proveedores: single
   flojo en gsm8k (0,62–0,63 Claude/DeepSeek), cot/reflexion ~0,95–1,00;
   mmlu alto en todos los brazos; **mbpp débil en todos**
   (Claude 0,075–0,113, DeepSeek 0,05–0,108, OpenAI 0,000) — la debilidad en
   código parece independiente del modelo, con n=80/celda ya no es evidencia
   débil.
2. Claude cuesta ~8–10× por llamada que DeepSeek en celdas equivalentes
   (verbosidad: out largo en cot/reflexion), con rewards similares.
3. Sonnet: diferido (condición pre-registrada no cumplida: no hubo 1080
   pulls con gastado ≤ US$1,20).

## Registry
Entrada `anthropic` sembrada en `alma_service/proveedores.yaml` con dos
campañas (`exp70-piloto`, 63 pulls; `exp67-claude-full`, 790 pulls, caveat
de parcial). Validación de schema OK. `test_registro.py` 16/16 en verde
(3 expectativas de inventario actualizadas a la nueva entrada legítima;
semántica de failover intacta), `test_router_stub.py` 15/15 en verde.
Cero secretos por construcción. Servicio vivo (puerto 8471) y núcleo
intactos.
