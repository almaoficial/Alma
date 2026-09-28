# ALMA-EXP46 — Veredicto: PASS marginal (fase mock)

**Fecha:** 2026-09-27 ~15:05 EDT · **Modo:** mock (US$0,00 — la key no se tocó)
**Pre-registro:** `resultados/exp46-20260927/preregistro.json` (escrito antes de correr)

## Qué se testea

La recomendación del veredicto de EXP45: las skills mejoraban el Thompson
pero no tocaban el costo estructural (el probe: 5 items/bloque con scoring
ciego). Acá la skill, cuando tiene **soporte fuerte**, **salta el probe** y
juega directo su brazo.

**Diseño A/B pareado** (único moving part):
- Control: el tratamiento de EXP45 (skills condicionan el prior; probe Q1 +
  re-probe Q2 siempre). Bit-idéntico al tratamiento de EXP45 (mismos seeds
  de oráculo, mismo stream seed 45, mismo código).
- Tratamiento ("skip"): idéntico, salvo que con soporte fuerte se salta el
  probe (Q1 y Q2) y se juega el brazo de la skill en los 10 items.
  Contabilidad honesta: el probe saltado cuesta 0.
- Soporte fuerte (pre-registrado): skill_arm = argmax de la media con olvido
  0.5^d sobre la historia de la skill; ≥2 victorias pareadas en bloques
  pasados no-saltados con la misma firma (victoria = media en los 5 items de
  probe estrictamente mayor que cada otro brazo, margen implícito ≥ 0.2).
- Stream idéntico a EXP45: 120 items, 12 bloques × 10, 3 regímenes × 4
  recurrencias. RNG común por (réplica, bloque, item, brazo); 5 réplicas.

## Números

| Réplica | efecto (reg_skip − reg_control) | reg control | reg skip | mejor fija | saltos |
|---|---|---|---|---|---|
| 0 | +1,00 | 46,0 | 47,0 | titular (38,0) | 1 |
| 1 | +0,00 | 50,0 | 50,0 | contexto (45,0) | 0 |
| 2 | +0,00 | 50,0 | 50,0 | titular (45,0) | 0 |
| 3 | −1,00 | 51,0 | 50,0 | titular (37,0) | 2 |
| 4 | −3,00 | 45,0 | 42,0 | titular (38,0) | 1 |

**Efecto medio: −0,60 → PASS** (vara pre-registrada: media < 0).
Regret medio: control 48,40 · skip 47,80 · mejor fija 40,60.
Probes saltados: 4 en 60 bloques (media 0,8/réplica). Misfires: 1.

Detalle de los 4 saltos (diagnóstico ex post con RNG común; la política no
lo usa para decidir):
- rep0/b11 (firma dinero → contexto): acc 0,8, mejor ex post contexto 0,8. OK.
- rep3/b8 (firma deportes → titular): acc 0,8, mejor ex post titular 0,8. OK.
- rep3/b11 (firma dinero → contexto): acc 0,6, mejor ex post estable 0,7.
  **Misfire** (−1 punto en el bloque).
- rep4/b8 (firma deportes → titular): acc 0,9, mejor ex post titular 0,9. OK.

**Reproducibilidad:** el control salió bit-idéntico al tratamiento de EXP45
(verificación automática: True). El pipeline es determinista y el número de
EXP45 se sostiene.

## Honestidad incómoda

1. **El PASS es técnico, no contundente**: −0,60 sobre un regret de ~48
   (≈1,2%). Una réplica en contra (+1,0), dos neutras (0,0). El efecto vive
   en 2 réplicas de 5.
2. **El mecanismo dispara poco por diseño**: la vara (≥2 victorias pareadas)
   más 4 recurrencias por régimen hace que el salto solo pueda activarse en
   la 3ª/4ª ocurrencia de cada régimen. 4 saltos en 60 bloques es el techo de
   este mundo, no un accidente.
3. **Cuando dispara, mayormente acierta** (3/4 sin misfire), pero el misfire
   existe y cuesta: firma ruidosa o brazo stale → se juega el brazo
   equivocado en 10 items sin red.
4. **No mueve el diagnóstico estructural**: skip 47,80 vs mejor fija 40,60 —
   ~7 puntos abajo. Ni el prior condicionado (EXP45) ni el salto de probe
   (EXP46) cambian que en un mundo que rota ninguna maquinaria con
   exploración le gana a la mejor fija.
5. **Condición de alcance** (pre-registrada): en el feed real (EXP44:
   rotación 8/8) las skills nunca alcanzarían soporte fuerte — el mecanismo
   no se activaría ni una vez.

## Veredicto

**PASS marginal.** Saltar el probe con soporte fuerte ahorra costo de
exploración real y el misfire es infrecuente (1/4), pero el efecto es ~1%
del regret y el mecanismo casi no tiene dónde operar con recurrencia corta.

## Recomendación

No seguir tuneando el mock de skills en este mundo: dos PASS marginales
seguidos (EXP45 −1,0, EXP46 −0,6) dibujan el techo — la ganancia visible del
loop de skills es ~1–2% del regret en el mejor mundo posible para él.
No correr fase con key: mediría con plata lo que el mock ya diagnosticó.

La única pregunta abierta que este experimento deja: ¿el efecto escala con
recurrencia más larga? (6–8 ocurrencias por régimen le darían al salto más
bloques donde operar). Si se quiere responder, es un EXP47 mock (US$0) con
el mismo diseño y horizonte más largo. Si no, cerrar la línea de skills: el
problema no es el mecanismo, es el mundo — en rotación rápida, explorar
cuesta más de lo que rinde, con o sin skills.
