# ALMA-EXP11b — Veredicto: FAIL DE DISEÑO (puerta de verificación no pasada)

**Fecha:** 2026-09-27 · **Modo:** puerta offline (US$0,00 gastados — la key no se tocó)
**Pre-registro:** `resultados/exp11b-20260927/preregistro.json` (escrito antes de gastar)

## Qué se hizo

EXP11 (26/9) dio FAIL — regret alma 9,32 vs mejor fija (cot) 6,82 — pero el test quedó
rengo: el oráculo mostró que los 10 bloques los ganaba cot; el flip no estacionario
diseñado no se materializó. EXP11b debía re-testear con el flip VERIFICADO antes de correr.

La puerta de verificación se ejecutó sobre el oráculo completo ya medido en EXP11
(1200 pulls, 600 celdas × 2 intentos, gpt-4o-mini, mismos 200 problemas) en lugar de una
muestra nueva: estrictamente más potente y costo US$0.

## Números de la puerta

Oráculo global (200 problemas): **cot 0,753 · single 0,442 · reflexion 0,581**.
cot domina por +0,31 sobre single.

| Intento | Mitad A | Mitad B | Ganador A (margen) | Ganador B (margen) | ¿Flip real? |
|---|---|---|---|---|---|
| 1 (interpretable: GSM8K vs MMLU) | 100 GSM8K | 100 MMLU | cot (0,196) | cot (0,114) | **NO** |
| 2 (techo: top-100 por single−cot) | bottom-100 | top-100 | cot (0,204) | single (0,059) | **NO** |

Criterio de "flip real" pre-registrado: distinto ganador por mitad **y** margen ≥ 0,10 en
ambas (barra principista: el probe decide con ~5 problemas/bloque y la regla exige
> 0,05; bajo 0,10 el flip queda bajo la resolución del probe).

El intento 2 da un flip *nominal* (single gana por 0,059), pero:
- 0,059 < SE del probe con 5 problemas (0,070) → **indetectable por la maquinaria**;
- la partición se eligió sobre medias ruidosas (2 pulls/celda) → winner's curse: el
  margen real es plausiblemente ~0.

**→ La puerta FALLA tras 2 intentos. No se corre el stream completo. Gasto: US$0,00.**

## Veredicto

**FAIL DE DISEÑO** (no es un FAIL de la política: la política nunca corrió porque el
mundo que el test necesita no existe en este pool).

## Honestidad incómoda

1. **El problema no es solo que "el mundo no se movió" — es que con estos brazos el
   mundo CASI NO PUEDE moverse.** cot gana globalmente por +0,31; gana en 9 de 10
   materias MMLU (la décima la empata single por 0,01, ruido); solo 10/200 problemas
   tienen a single superando a cot por ≥ 0,1; reflexion supera a ambos en 4/200.
   El set {single, cot, reflexion} sobre gpt-4o-mini tiene un brazo dominante.
2. **Esto re-encuadra el FAIL de EXP11:** no fue solo mala suerte de diseño (GSM8K→MMLU);
   es estructural — la pregunta "¿se adapta cuando el mejor brazo cambia?" es
   incontestable con brazos donde uno domina siempre.
3. **La maquinaria del probe necesita brazos con trade-offs reales para que la
   pregunta tenga sentido.** Sin trade-off, "adaptarse" es ruido.

## Recomendación (para decisión del parent/usuario)

No re-correr EXP11b con este diseño. Para cerrar la pregunta 1 de la agenda finita
(¿rinde en problemas duros reales?) hace falta **rediseñar los brazos**, no los
problemas. Candidatos con trade-off real:
- **Reward con costo**: single gana en problemas fáciles (misma precisión, menos
  tokens), cot en difíciles → flip interpretable y medible;
- **Brazos = modelos distintos** (trade-off costo/precisión).

Cualquiera de los dos cambia el criterio (ya no es el de EXP11) y merece pre-registro
propio. Es una decisión de diseño, no un reintento.

## Archivos

- Pre-registro: `~/workspace/alma-prototype/resultados/exp11b-20260927/preregistro.json`
- Oráculo reutilizado: `~/workspace/alma-prototype/resultados/exp11-20260926/experiencias.jsonl`
- Costo real: **US$0,0000** (puerta 100% offline; VaultBackend nunca instanciado)
