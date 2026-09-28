# ALMA-EXP62 — Pre-registro: test de agnosticismo al modelo

**Fecha:** 2026-09-27T21:30:00Z (domingo, fuera de pico)
**Estado:** escrito ANTES de gastar el primer centavo. La key de DeepSeek se usa
solo vía variable de entorno transitoria; nunca en disco.

## Pregunta

¿El loop de ALMA replica su ventaja con otro modelo como motor? Réplica fiel
de EXP5 (mundo no estacionario H3) con `deepseek-flash` en vez de gpt-4o-mini.

## Diseño (réplica de EXP5, diferencias marcadas con *)

- **Stream:** 120 problemas = 10 clases × 12, bloques ordenados, seed 999.
  Se regenera con la misma función de EXP5 y se ABORTA si el orden difiere del
  `orden_bloques` de `resultados/exp5-20260926/report.json` (chequeo de fidelidad).
- **Brazos (*)**: {single, cot, reflexion} — 3 en vez de 2. Mapeo al dial de
  esfuerzo de la API de DeepSeek (verificado en docs oficiales hoy):
  - `single` → `reasoning_effort: "none"` (non-thinking), max_tokens 256,
    prompt conciso directo.
  - `cot` → `reasoning_effort: "high"`, max_tokens 1024, prompt paso a paso
    con línea final `Respuesta: <...>`.
  - `reflexion` → `reasoning_effort: "max"`, max_tokens 2048, prompt paso a
    paso + auto-crítica explícita ("cuestioná tu razonamiento, verificá cada
    paso, corregí antes de responder") con línea final `Respuesta: <...>`.
  - Nota de honestidad: la API expone niveles efectivos none/high/max
    (`low`→`high` por compatibilidad); el dial continuo 1–100 del anuncio no
    existe en el endpoint chat/completions. El mapeo bajo/medio/alto →
    none/high/max es la implementación fiel posible.
- **Oráculo (*)**: RE-MEDIDO completo con deepseek-flash (no se reutiliza el de
  gpt-4o-mini). Disciplina EXP8: 3 intentos por celda (problema, brazo);
  vara = max sobre brazos del promedio de 3. 120×3×3 = 1080 llamadas.
- **Políticas:** fija-single, fija-cot, fija-reflexion, thompson-global
  (1 bandit, prior uniforme), alma-full:
  - bandit por clase + warm-start repertorio hacia adelante (n0=2, valor EXP5),
  - probe 3 problemas × 3 brazos al entrar a cada bloque (9 llamadas),
  - regla de elección generalizada de EXP3 (default barato + margen 0.05):
    empieza en single; sube a cot si mean(cot)−mean(single) > 0.05;
    sube a reflexion si mean(reflexion)−mean(actual) > 0.05.
  - RNG pareado por posición de stream entre políticas (seed "exp62").
- **Evaluador:** sin cambios (eval-v1, verificadores deterministas exact/código;
  StubJudge; reward = 0.75·exito + 0.25·(1 − costo_rel/5), costo_rel del registry:
  single 1.0, cot 1.2, reflexion 4.0 — independiente del proveedor).

## Criterio de éxito (el de EXP5, sin tocar)

PASS necesita AMBAS:
- regret(alma-full) < regret(mejor fija entre las 3)
- regret(alma-full) < regret(thompson-global)

Diagnóstico: bloques donde alma-full le gana a la mejor fija.

## Presupuesto (freno duro)

- **Tope total: US$1,00** (bucket RESOLUCION; `BudgetExceeded` aborta limpio).
- Sub-presupuestos orientativos: smoke US$0,01 · oráculo US$0,65 · políticas US$0,34.
- Orden de fases: smoke → oráculo → políticas (si hay que abortar, el oráculo
  completo es el artefacto más valioso).
- Precios de contabilidad (verificados en vivo hoy en
  https://api-docs.deepseek.com/quick_start/pricing): deepseek-flash off-peak
  US$0,15 / US$0,60 por 1M tokens (in/out). Ahora es domingo → off-peak.
- Gasto real medido por llamada desde `usage` de la API y registrado.

## Protocolo técnico (pre-registrado)

0. `GET /models` con la key (gratis, 0 tokens): valida auth + conectividad.
1. **Smoke test** (3 llamadas, ~US$0,001): problema stream[0] × 3 brazos.
   Valida: HTTP 200, `usage` presente, texto no vacío, extracción de
   `Respuesta:` en cot/reflexion, contabilidad de costo sana.
   Si falla → abortar antes del oráculo.
2. Oráculo 1080 llamadas, idempotente por (fase, problema, brazo, intento).
3. Políticas con pulls idempotentes por (fase, problema, brazo).
4. Reintentos: `con_reintento` (3 intentos, backoff) ante errores transitorios
   (la página de estado de DeepSeek no es confiable; hubo caída el 14-sep).

## Veredicto posible

- PASS: el loop es agnóstico al modelo (al menos en esta réplica).
- FAIL: la ventaja de EXP5 no replica con deepseek-flash → la ventaja era
  específica del modelo o del oráculo medido, y se reporta como tal.
- ABORTO: si el freno de US$1,00 corta antes de completar → se reporta parcial
  con lo medido, sin veredicto.
