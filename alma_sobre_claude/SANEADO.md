# Saneamiento del programa «ALMA sobre Muse» para publicación

Este directorio es la batería de pantalla del programa que aplica la
gobernanza de ALMA a la configuración del propio asistente, sobre la vida
real de su dueño. Esa vida no se publica. Qué se hizo, con el mismo criterio
que `data_exp44/SANEADO.md`:

**Se publica (código y resultados numéricos):**
- `validador_plan.py` — el validador congelado v1 (7 chequeos deterministas).
- `construir_corpus.py`, `puntuar.py`, `puntuar_ciclo1.py`, `ledger.py` —
  la batería completa, sin cambios.
- `resultados_v0.json` y `resultados_ciclo1.json` — las mediciones reales
  del programa. Sus filas contienen **solo puntajes** (fecha, repetición,
  variante, C1–C7, puntaje): ningún texto de plan, ningún dato personal.
  Son el registro de las corridas sobre el corpus privado.

**Se reemplaza por sintético:**
- `corpus_datos.py` — el original reconstruye 15 días reales (planes,
  vencimientos, montos y situaciones de su vida) desde sus registros. La
  versión publicada trae **3 días completamente inventados** con el mismo
  esquema, marcados como sintéticos en su encabezado.
- `corpus_planes.jsonl` y `planes_reales.jsonl` — regenerados desde el
  corpus sintético con `construir_corpus.py`.
- `planes_v0.jsonl` y `planes_v1.jsonl` — el original trae 60 instancias
  por variante generadas sobre los paquetes reales. La versión publicada
  trae instancias de ejemplo (2 por día) escritas sobre los días sintéticos.

**Se excluye:**
- `planes_v0_datos.py` y `planes_v1_datos.py` — las instancias generadas
  en forma de módulo, derivadas de los paquetes reales (ningún archivo
  publicado los importa).

**Advertencia de método:** si corrés `puntuar.py` en este repositorio,
regenera `resultados_v0.json` con los puntajes del corpus sintético de
ejemplo. Los valores archivados en el archivo publicado (línea de base
v0 = 0,9828 · ancla de planes reales = 0,8511 · δ del ciclo 1 = 0,1000) se
midieron sobre el corpus privado de 15 días, que no sale de la máquina
del dueño. La batería pública reproduce el método, no esos datos.
