# Veredicto — Simulador mock de dogfooding de inglés (ALMA)

**Fecha:** 2026-09-28
**Pre-registro:** `preregistro.md` (misma carpeta; escrito antes de correr nada)
**Código:** `sim.py` — US$0, 100% mock, sin tocar el servicio vivo
**Mundos:** 500 sintéticos, seed base 20260928, determinista

---

## Resultado por criterio (vara pre-registrada sagrada)

| # | Criterio | Vara | Medido | Veredicto |
|---|----------|------|--------|-----------|
| 1 | Convergencia al mejor brazo verdadero a las 4 semanas | ≥ 70% | **53.4% (267/500)** | **FAIL** |
| 2 | Tasa de skip falso | < 20% | 12.0% (60/500) | PASS |
| 3 | Regret mock ≤ 1.5× baseline round-robin | ≤ 1.5 | **0.769** (2.92 vs 3.79) | PASS |

**Veredicto global: FAIL.** La vara no se mueve. Ninguna noche real arranca con este schedule.

## Diagnóstico (números, no opiniones)

El FAIL del criterio 1 vive en los mundos con empate técnico:

- Conv | gap mejor–segundo < 0.05: **35.0%** (62/177) — 35% de los mundos caen acá.
- Conv | gap ≥ 0.10: **74.3%** (124/167) — por encima de la vara.
- Gap mediano entre los dos mejores: **0.070** (p10 = 0.012, p90 = 0.181).

Lectura: con 1 pull/noche y 28 noches, el posterior **no puede rankear dos brazos cuya diferencia verdadera es menor a ~0.05** — el ruido del auto-reporte (σ≈0.9 en escala 1–5) tapa la señal. El Thompson tampoco concentra pulls (promedio por brazo: A=6.2, B=5.4, C=6.4, D=6.1, E=3.9) porque el skip casi nunca se activa: la condición de gap posterior ≥ 0.15 rara vez se cumple en 4 semanas.

Los criterios 2 y 3 pasan cómodos: el skip falso es 12% y el regret es 23% menor que rotar a ciegas. La maquinaria no es mala — es el schedule el que pide más noches o más señal por noche de las que el diseño actual le da.

## Propuestas de rediseño (solo propuestas, nada lanzado)

1. **Relajar la vara a "top-2 estable"** en lugar de "#1 exacto" — si los dos mejores brazos están a <0.05, cualquiera de los dos sirve en la práctica. (Requiere re-pre-registro.)
2. **Probe más largo:** 3 vueltas (15 noches) en vez de 2, para que el posterior arranque con más señal antes del Thompson.
3. **Skip más agresivo y honesto:** bajar el gap de skip de 0.15 a 0.10 con ≥5 pulls, y medir si el skip falso se mantiene <20%.
4. **Señal por noche más rica:** el auto-reporte 1–5 es el cuello de botella; sin cambiar la fricción no hay más señal — esto es un límite del diseño, no del código.

Cualquiera de estas se corre como mock nuevo con pre-registro propio antes de tocar una noche real.

## Propuesta de piloto real (solo si un rediseño da PASS en mock)

Sin lanzar nada, así arrancaría el piloto real cuando un mock futuro pase la vara:

1. **Dónde:** dentro del chequeo nocturno de las 23:00 que ya existe — 5 minutos por noche, guion del brazo que toque según el schedule (probe o resolver).
2. **Registro:** dos líneas por noche ("lo hice / no lo hice", "me sirvió: N/5") + ledger JSONL en `~/workspace/alma-prototype/producto/dogfooding/ledger/` según el formato de la spec.
3. **Retención dominical:** 1 minuto los domingos — qué recuerda de la semana, sin mirar.
4. **Régimen de energía:** si dice "cansado", solo brazos A/C/D esa noche (regla dura, no bandit).
5. **Veto:** "hoy no" / "cambiá" / "congelá" se cumple sin discusión y se registra como intervención.
6. **Primera lectura seria:** semana 4 — ¿el loop convergió a un ganador? Se revisa el diseño con datos reales.

**Estado:** bloqueado hasta que un mock rediseñado dé PASS. Lo que lo desbloquea: un pre-registro nuevo + mock en verde con la vara que se defina ahí.
