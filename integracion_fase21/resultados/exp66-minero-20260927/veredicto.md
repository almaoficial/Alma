# EXP66 — Veredicto: STAND DOWN (US$0,00 gastados de US$0,08 aprobados)

## Qué se hizo

1. **Fase A (US$0)**: firmas minadas con `alma_service/debilidades.py` —
   ver `firmas.md`. Firma dominante: `(alma-full, *, cot|reflexion, fallo)`,
   Thompson elige el brazo caro ~50/90 contra oráculo single 117/120.
   Hallazgo extra: 2 de las 3 celdas no-single del oráculo son un único
   intento afortunado (0.94) — el argmax sobre 3 intentos premia outliers.
2. **Edición propuesta y pre-registrada**: prior de Thompson anclado al
   ganador del probe (N_ANCLA=8) — ver `preregistro.md`.
3. **Pre-test mock de la edición (US$0, evidencia nueva)**: simulador
   offline sobre las rewards medidas del oráculo, antes de gastar.

## El pre-test mató la edición

Simulador offline (rewards = medias medidas por celda, 5–30 seeds):

| variante | regret medio | vs baseline |
|---|---|---|
| baseline (alma-full real) | 5.42 | — |
| **ancla al probe (la edición)** | **5.92** | **peor** |
| probe-only (sin warm) | 6.75 | peor |
| bandit global frío | 4.90 | ruido |
| warm con decaimiento | 5.38 | ruido |
| warm N0=8 | 5.45 | ruido |

Y lo decisivo, 30 seeds: **alma-full vs thompson-global dif = 0.44 ± 1.72**
(dif>0 en 16/30). La "derrota del Thompson warm contra el frío" que el
veredicto de EXP62 reportó (+1.14) **es ruido** — está dentro de 1 sd.
No hay señal load-bearing que una edición pueda explotar.

Causa raíz del daño del ancla: en el bloque 0 el probe midió
single=0.45 (ruidoso-bajo) y el ancla a la media del probe ARRASTRA el
posterior del ganador hacia abajo en vez de concentrarlo.

## Decisión de gasto: NO CORRER

La regla dura autorizaba (estimado US$0.0432 ≤ US$0.08 con costos medidos
+50% margen), pero la regla mock-first (AGENTS.md) tiene prioridad:
**nunca gastar key en una pregunta que el mock ya respondió**.
El mock respondió: la edición no mueve la aguja y ninguna variante chica
lo hace. Gastar US$0.04 sería ritual, no ciencia.

Razón adicional: la puerta de dos splits **no puede detectar
sobreajuste al mundo** cuando ambos splits vienen del mismo stream
colapsado. Un PASS acá sería el artefacto de EXP42 con otro nombre.

## Lectura: ¿puede el loop aprender de este FAIL?

**No — porque no hay defecto aprendible.** El FAIL de EXP62 no es un bug
del loop: es la ausencia de heterogeneidad. El probe hizo su trabajo
(10/10); el costo de exploración es el precio de verificar que no hay
nada que descubrir. Ningún tweak de Thompson le gana al ruido en un
mundo single-dominante; la única política que gana ("jugar single
siempre") es la respuesta, no una regla aprendible — y sería catastrófica
en un mundo heterogéneo como el de EXP5.

La lección accionable real (trabajo futuro, no este experimento): ALMA
necesita un **detector de heterogeneidad** — una meta-regla que encoja la
exploración cuando el probe es unánime K bloques seguidos — **validada en
un mundo heterogéneo**, para verificar que no rompe la adaptación donde
sí hay algo que aprender.

## Artefactos

- `firmas.md` — minería Fase A
- `preregistro.md` — pre-registro (+ addendum del stand-down)
- `run_exp66.py` — script de validación listo (no ejecutado; requiere
  DEEPSEEK_API_KEY en el entorno)
- `veredicto.md` — este archivo
