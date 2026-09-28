# Pre-registro — Simulador mock de dogfooding de inglés (ALMA)

**Fecha:** 2026-09-28
**Spec:** `~/workspace/alma-prototype/producto/dogfooding/INGLES.md` (v1.0, 28/9/2026)
**Costo:** US$0 — mock sintético, sin API, sin tocar el servicio vivo
**Estado:** diseño (mock primero; ninguna noche real hasta que el mock dé PASS)

---

## Hipótesis

El schedule pre-registrado de la spec (probe rotativo de 10 noches + Thompson con skip + reglas de re-probe) converge al mejor brazo verdadero en 4 semanas (28 noches), a 1 pull/noche, en al menos el 70% de los mundos sintéticos — sin que el costo de explorar arruine el regret.

## Diseño

- **500 mundos sintéticos**, cada uno con rewards verdaderos aleatorios por brazo.
- **Modelo de mundo por brazo** (iid entre brazos, sorteado por mundo):
  - Participación verdadera π ~ Uniforme(0.55, 1.00).
  - Auto-reporte verdadero s | p=1: media μ_s ~ Uniforme(2.0, 4.8); muestra redondeada de N(μ_s, 0.9), recortada a [1, 5].
  - Reward verdadero por pull: p=0 → 0; p=1 → 0.6·1 + 0.4·(s/5).
  - Media verdadera del brazo: μ = π·(0.6 + 0.4·μ_s/5).
  - Retención dominical verdadera: ρ ~ Uniforme(0.2, 0.9) (recall semanal ~ Bernoulli(ρ) por brazo con ≥1 pull en la semana).
- **Mundo no estacionario en dos sentidos menores:** noches "cansado" con P=0.15 (solo elegibles A/C/D, por regla dura, no por Thompson); brazo E no disponible con P=0.25 por noche (sin material), otros brazos con P=0.02.
- **Prior:** 2 pseudo-observaciones en 0.5 por brazo → Beta(1, 1). Posterior Beta con actualización fraccional: α += r, β += (1−r) (mismo truco Beta-Bernoulli del scaffold validado).
- **Fase 1 (noches 1–10):** round-robin A,B,C,D,E dos vueltas (2 pulls por brazo). Si el brazo de la rotación no está disponible, se saltea a la noche siguiente sin contar (el probe completa 2 pulls medidos por brazo).
- **Fase 2 (noche 11+):** Thompson — se muestrea θ ~ posterior por brazo elegible+disponible y se propone el máximo.
- **Skip activo** cuando el candidato cumple las tres condiciones de la spec: ≥5 pulls medidos; media posterior ≥ segundo mejor + 0.15; últimos 3 pulls con p=1. El resolver propone el ganador todas las noches (si no está disponible o el régimen de energía lo excluye, se cae a Thompson entre elegibles+disponibles).
- **Re-probe:**
  - p=0 dos noches seguidas en el ganador con skip → se sale del skip, bloqueo de 3 noches sin skip.
  - 7 noches sin probar otro brazo (stale) → una noche de exploración forzada por Thompson entre brazos ≠ ganador.
  - Retención dominical = 0 dos semanas seguidas en el ganador con skip → se sale del skip y se re-explora (se usa la regla de la sección de re-probe de la spec; la de "tres semanas" de la sección de retención es el caso general sin skip).
  - Veto del usuario: no se modela en el mock (asunción: veto no usado; se declara como límite).

## Vara pre-registrada (verbatim de la spec)

1. En ≥ 70% de los mundos, el mejor brazo verdadero queda rankeado #1 en el posterior a las 4 semanas (noche 28). El "mejor verdadero" es el argmax de las medias verdaderas μ entre los 5 brazos.
2. Tasa de skip falso (skip activo en un brazo que NO es el mejor verdadero) < 20% de los mundos.
3. Arrepentimiento total del mock ≤ 1.5× el de un oráculo que conociera los rewards.

### Operacionalización del criterio 3

El oráculo que conoce las rewards verdaderas tiene regret 0 por construcción (elige el mejor disponible cada noche), así que un cociente directo no se define. Lo operacionalizo de forma honesta en dos números:
  - **(a) Regret absoluto** del mock: Σ_noche (mejor μ disponible/elegible − μ del brazo elegido), usando medias verdaderas.
  - **(b) Cociente vs. baseline round-robin** (rotación A–E las 28 noches, misma disponibilidad/energía): regret_mock / regret_roundrobin ≤ 1.5.

El veredicto reporta ambos; la vara se evalúa sobre (b).

## Regla mock-first

Si el mock da FAIL en cualquiera de los tres criterios, se rediseña el schedule. Ninguna noche real arranca con un FAIL en el mock. La vara es sagrada: no se mueve el arco.

## Límites declarados

- n=1 por mundo (un solo "usuario"), rewards sintéticos, retención simplificada a Bernoulli semanal.
- El auto-reporte se modela como N(μ_s, 0.9) recortada; el sesgo optimista del sujeto-juez NO se modela (quedaría como follow-up si el mock pasa cerca del borde).
- No se modela veto del usuario ni cambios de régimen (viajes, semanas atípicas).
- El mock prueba la maquinaria del schedule, no si el inglés mejora.
