# Resultados — Corrida del generador con los tres ajustes del estudio externo

**Fecha:** 2026-10-16 · **Documentos rectores:**
`preregistro-generador-sakana-2026-10-16.md` +
`adenda-preregistro-generador-2026-10-16.md` (commit `79208b6`,
escrita y commiteada ANTES de cualquier ejecución, como la adenda
manda). **Autorización:** Alejandro, «Corre» del 16/10/2026.

## Veredicto en una línea

**La corrida NO se realizó: bloqueo de plataforma (HTTP 429 del
tier gratuito sobre el modelo designado), según §7 del
pre-registro — precedente El Probador 002b: «bloqueada por la
plataforma, no desaprobada».** Los dos ajustes que no dependen de
la plataforma quedaron aplicados y medidos (cortafuegos y
screening); el panel de confirmación quedó declarado y **sin
consumir**. Freno de estancamiento **sin cambios: 1/3** (no hubo
corrida evaluada). Costo total: **US$0**.

---

## 1. Ajuste 1 — Cortafuegos del proponente: APLICADO y probado

**Qué extraía el prompt antes:** `historial_desde_ledger`
proyectaba solo campos de etapa train (`clave/anterior/nuevo/
delta_in/aceptado`) desde eventos `audit_propuesta`, y jamás abría
los eventos de la puerta (`audit_propuesta_e3`,
`corrida_finalizada`). Ningún número held-out/E3 llegó nunca al
prompt. **Pero** el historial (11 filas) incluía un evento heredado
de la etapa puerta: la corrida seed 23 (código del 28/9) asentó la
auditoría de su candidato final como `audit_propuesta` con
`delta_ho: 0,0` poblado y motivo de puerta — su fila entraba al
historial del proponente con veredicto de puerta.

**Qué extrae ahora:** guarda estructural — un `audit_propuesta`
con `delta_ho` no-None o con `delta_e3` presente se **excluye
entero**. Historial real tras el cambio: **10 filas** (sale el
evento heredado; la tabla de la corrida 87859 intacta, 8/8).

**La prueba:** ledger envenenado en la suite (sección 2b) con
puntajes plantados en el `delta_ho` de un `audit_propuesta`, en un
`audit_propuesta_e3` completo, en el `corrida_finalizada` y en
textos libres: **ningún valor plantado llega al historial ni al
prompt**, y las filas solo traen los campos train declarados.
Suite del generador: **77/77 checks** (57 previos + 20 nuevos).

---

## 2. Ajuste 3 — Screening factorial: CORRIDO (diagnóstico asentado)

Diseño declarado en la adenda: 2^(5−1) resolución V, E = A·B·C·D,
niveles extremos de SPACES, 16 configuraciones + centro +
incumbente = 18 evaluaciones con el validador congelado sobre el
panel train [400..417]. SE(efecto) = **1,1935**; umbral de
detectable = **2,3869** totales. Ancla de consistencia: el
incumbente midió **85,2222** — idéntico a la media train asentada
en el recableado. El centro midió 88,2222 (peor que el incumbente).

**Efectos principales** (efecto = Δ del regret medio al pasar de
nivel − a +; negativo = mejora):

| parámetro | efecto | detectable |
|---|---|---|
| umbral_base | **+3,2569** | **SÍ** |
| umbral_divisor | −1,8542 | no |
| decay | −0,5625 | no |
| n0 | −0,0764 | no |
| gate_margin | −0,0069 | no |

**Interacciones de a pares:** las 10 medidas, **ninguna
detectable**. Las mayores: umbral_base × umbral_divisor +1,5625 ·
n0 × umbral_base −0,9653 · n0 × umbral_divisor +0,5625 — todas bajo
el umbral 2,3869.

**Veredicto del screening: SIN interacciones detectables** a esta
resolución y niveles. Interpretación asentada: el paisaje entre
los extremos de la caja se comporta de forma esencialmente
**aditiva**; la única señal firme es el efecto principal de
`umbral_base` (subirlo empeora ~3,26 en promedio — consistente con
las mutaciones medidas hoy: 1→3 dio +3,0556 de regret y 1→2,
+3,1667). Esto **debilita la hipótesis fundante del generador**
(las interacciones coordinadas) sin refutarla: el factorial solo
sondea las esquinas de la caja a niveles extremos, y el generador
propone también combinaciones interiores. Como la adenda declaró,
el screening interpreta, no veta: la corrida procedió igual — y su
desenlace (§3) no depende de esta sonda. Datos crudos y script:
`data_screening_factorial_2026-10-16/`.

---

## 3. Ajuste 2 — Panel de confirmación: DECLARADO, NO consumido

Panel declarado en la adenda antes de correr —
confirmación-train **[5000..5017]** (18) y confirmación-held-out
**[5100..5111]** (12), vírgenes verificados con barrido amplio
(379 archivos, cero hits de cualquier categoría). Al no haber
adopción (ni siquiera hubo corrida), **el panel no se evaluó**: los
rangos siguen vírgenes y declarados para la próxima corrida que
los necesite, tal como la adenda prescribe.

---

## 4. La corrida — NO REALIZADA (bloqueo de plataforma)

**Verificación de modelo (§4 del pre-registro):** catálogo
OpenRouter consultado sin costo (467 modelos; snapshot en
`data_corrida_generador_2026-10-16/catalogo_snapshot.json`). El
tier gratuito **rotó de nuevo**: el primario declarado
`inclusionai/ling-3.1-flash:free` **no figura**, y tampoco hay
ningún `deepseek/*:free`. Aplicada la regla de reemplazo hasta su
paso (3): el primer `*:free` de chat no-reasoning del catálogo, en
su orden, es **`xingchen-agi/xing4.0-29b-a4b:free`** (índice 0,
text→text, serie TeleChat; criterio de clasificación asentado en
el snapshot: «reasoning» = diseñado como tal según id/nombre/
descripción — la mera presencia del parámetro API `reasoning` no
clasifica; excluido por no-chat el guardrail
`nemotron-3.5-content-safety`). Ese es el modelo designado.

**Generación: tres 429 consecutivos** (evidencia completa en
`data_corrida_generador_2026-10-16/evidencia_429.txt`):

1. El intento real de generación (`correr_generador.py --generar`,
   ~22:24 EDT) murió en el primer llamado: `or_chat` salió con
   error y stderr vacío (reporta el error como JSON en stdout).
   Sin tanda escrita, sin candidatos, sin evaluación.
2. Sonda inmediata con prompt mínimo al mismo modelo: **HTTP 429
   Too Many Requests**.
3. Sonda espaciada (+4 minutos): **HTTP 429** otra vez.

**Veredicto:** §7 del pre-registro, «bloqueo de plataforma» — la
corrida **no se realizó**. No se sustituyó el modelo por fuera de
la regla declarada (la regla se agotó en su paso 3; cambiar de
modelo tras el 429 sería improvisar otra ruta) y no se pagó
ninguna ruta. La tanda nunca existió: no hay candidatos que
reportar, ni Δ por candidato, ni veredicto de adopción — cualquier
número ahí sería inventado.

**Estado tras el bloqueo (verificado):**

- **Freno de estancamiento: 1/3, inactivo — sin cambios** (el
  freno cuenta corridas evaluadas; no hubo ninguna).
- **Ledger: 23 eventos, cadena de hashes recomputada e íntegra**,
  último hash `91c8e0ddc518` — idéntico al estado posterior a la
  corrida RSO de hoy. La generación fallida no asentó nada.
- **Scaffold vigente: sin cambios** (la base de siempre).
- **Suites de gobernanza al cierre: 45/45 PASS** (las 44 previas +
  la del generador con el cortafuegos, 77/77 checks internos).
- **Costo: US$0.** Duración de la tarea completa: ~40 minutos de
  reloj, incluida la espera declarada de 4 minutos entre sondas.

**Lo que queda listo para el reintento:** el precedente 002b se
reintentó en fecha posterior bajo el mismo pre-registro. Esta
corrida queda igual: pre-registro + adenda vigentes, generador con
cortafuegos probado, panel de confirmación declarado y virgen,
screening asentado. Cuando el tier gratuito responda, la corrida
se lanza tal cual — verificar el catálogo de ese día (el tier
rota: el modelo efectivo puede cambiar por la misma regla),
generar, congelar la tanda y correr. Ninguna parte de este
documento necesita rehacerse.
