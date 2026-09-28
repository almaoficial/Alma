# Auditoría seed 1822 — 2026-09-28

## Motivo
Reintento aprobado por el usuario (~US$0,10, key Anthropic) bajo la premisa de que
el seed 1822 "abortó por Connection refused sin veredicto".

## Hallazgo
La premisa estaba desactualizada. El seed 1822 YA tiene veredicto completo y válido:

- Oráculo re-medido por seed: 720 pulls (12A-oracle-r1: 360 + 12A-oracle-r2: 360),
  almacenados en el store propio del seed (experiencias.jsonl). El assert de 360
  celdas pasó. El oráculo se midió en el intento abortado y se reutilizó
  idempotentemente en la corrida que completó (mismo patrón sancionado que el
  reintento del seed 1824).
- Política completa: probe + re-probe + Thompson (veredicto en seed1822.log,
  2026-09-27 14:23, 125.6s).
- Veredicto: **FAIL** — regret alma=6.11 vs mejor fija (cot)=5.02 (diff=+1.09).

## Decisión
No se ejecutó el reintento. Gastar US$0,10 en re-correr un seed completo y válido
sería ritual, no ciencia. Gasto del reintento: US$0.0000.

Nota adicional: un reintento con la key de Anthropic (modelo distinto) violaría el
preregistro del EXP18 ("modo: api real (gpt-4o-mini vía VaultBackend)").

## Estado global EXP18 (verificado 2026-09-28)
- seed1821: FAIL (alma=6.79 vs fija=4.43)
- seed1822: FAIL (alma=6.11 vs fija=5.02)
- seed1823: FAIL (alma=8.57 vs fija=5.48)
- seed1824: FAIL (alma=5.97 vs fija=4.74)
- Veredicto global pre-registrado: **FAIL** (alguna seed no pasa el criterio).
  Rango del regret ALMA = 2.60 > 1.0 → además NO CONFIABLE por la regla de
  confiabilidad pre-registrada.
