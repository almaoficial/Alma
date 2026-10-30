# ALMA como sistema de control

Un agente que se mejora a sí mismo es, en criollo, un termostato:
mide, compara contra el objetivo, corrige — y tiene frenos duros
para no pasarse de rosca.

```
                ┌──────────────────────────────────────────────────┐
                │   OUTER LOOP (lento, semanal): ALEJANDRO          │
                │   corrige el setpoint, aprueba frenos, recibe     │
                │   telemetría («avísame cada evolución»)           │
                └───────────────┬──────────────────────────────────┘
                                │ setpoint / ajustes
                                ▼
  SETPOINT ──► COMPARADOR ──► ACTUADOR ──► SISTEMA ──► salida
  mejora       «mejora        adopción     agente       rendimiento
  medible del   medida o se   de la skill  (ALMA)       medido
  rendimiento   rechaza»      en el núcleo    ▲
               (puerta de                     │
                dos splits)                   │
                                SENSOR ───────┘
                                experimentos,
                                benchmarks, probes

  SATURACIÓN DEL ACTUADOR: topes de gasto · tiempo · presupuesto de corridas
  PERTURBACIONES: mundo no estacionario · cambios de API · decisiones humanas
```

## Las piezas, una por una

| Pieza del loop | En ALMA |
|---|---|
| **Setpoint (objetivo)** | Mejora medible del rendimiento |
| **Sensor** | Experimentos, benchmarks, probes |
| **Comparador** | «Mejora medida o se rechaza» (puerta de dos splits) |
| **Actuador** | Adopción de la skill en el núcleo |
| **Saturación del actuador** | Topes de gasto, tu tiempo, presupuesto de corridas |
| **Telemetría** | El «avísame cada evolución» |
| **Perturbaciones** | Mundo no estacionario, cambios en las APIs, tus propias decisiones |

## Tres reglas que la teoría de control le regala a la gobernanza

1. **Anti-windup:** si el actuador está saturado (no hay presupuesto para
   probar), se congelan las propuestas. Nada de acumular «mejoras pendientes»
   que después se adoptan todas juntas y nadie sabe cuál funcionó.
2. **Cascada:** el loop rápido (experimentos, minutos/horas) va adentro;
   el loop lento (la revisión humana semanal) va afuera y corrige al de
   adentro. El humano no es un trámite: es el outer loop, diseñado a propósito.
3. **Compensación de retardo:** la puerta de dos splits funciona porque
   medir tarda; exigir la mejora dos veces, en datos distintos, es cómo
   un controlador serio no se deja engañar por su propio retardo de medición.
