# Convención de commits — el historial como paper vivo

Cada auto-adopción del meta-loop (una mejora que pasa la puerta de dos splits
con efecto positivo y sin regresión) se registra como **un commit** con:

- **qué cambió** (una línea)
- **efecto medido** (números: diff, intervalo, costo)
- **experimento que lo validó** (EXPnn)

Nada de cambios laterales: solo se auto-adopta ante **mejora medida**
("pero no peor"). Lo que mida igual o peor se rechaza y se registra.

**Núcleo intocable por auto-adopción:** topes de gasto y obligación de
notificar. Si el loop pudiera silenciar sus avisos, el "avísame" no valdría nada.

**Formato del mensaje:**

```
auto-adopcion: <qué cambió> (<efecto medido>, <EXPnn>)
```

Ejemplo:

```
auto-adopcion: detector de heterogeneidad K=3 J=3 (+6,00 en mundo homogéneo IC95 [+2,17,+9,83], EXP68)
```
