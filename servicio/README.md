# ALMA-servicio v2

El prototipo convertido en sistema persistente: un proceso siempre corriendo
que recibe problemas, elige cómo pensarlos (probe → Thompson con prior warm
+ olvido → ejecución), guarda cada experiencia y aprende de ellas.

v2 (spec: `ALMA_V2_SPEC.md`): modo agentes-batería vs persistentes según
horizonte, probe consciente de ruido (sin compromiso duro si el gap no
supera el umbral), y formulación de contradicción TRIZ previa a la
selección. Cada experiencia guarda brazo, modo batería/persistente, gap
estimado, contradicción y decisión de compromiso (en `metricas`).

## Piezas

| Archivo | Qué hace |
|---|---|
| `server.py` | Servidor HTTP (solo stdlib). Endpoints: `GET /salud`, `GET /estado`, `POST /resolver`, `POST /feedback`. |
| `motor.py` | El motor v2: contradicción TRIZ → clasificación → horizonte (batería/persistente) → probe con umbral de ruido o Thompson → ejecución → evaluación → guardado → aprendizaje. Reutiliza `alma/` sin modificarlo. |
| `store_sqlite.py` | Memoria persistente en SQLite (`~/workspace/alma-prototype/alma_store.db`): tabla `experiencias` y tabla `feedback`, append-only con hash encadenado (misma filosofía que `alma/store.py`). |
| `cliente_chequeo.py` | Cliente del chequeo nocturno: manda el log del día al servicio como problema de clase `analisis_diario` y guarda el análisis. |
| `chequeo_motor.py` | Test de roundtrip + runner de los tests existentes. |
| `puerta_calidad.sh` | Puerta de calidad: corre `chequeo_motor.py`; sale 1 si algo falla. |
| `arrancar.sh` / `parar.sh` | Arranca / para el servicio en segundo plano (guarda el pid en `servicio.pid`, log en `servicio.log`). |

## Cómo arrancar y parar

```bash
cd ~/workspace/alma-prototype/servicio
./arrancar.sh   # arranca en segundo plano
./parar.sh      # lo detiene
curl localhost:8471/salud   # {"ok": true}
```

## Variables de entorno

| Variable | Default | Qué hace |
|---|---|---|
| `ALMA_BACKEND` | `demo` | `demo` = sin modelo real, no gasta nada (el reward solo existe si se pasa `esperado` o llega `/feedback`). `vault` = modelo real vía Secure Vault (gasta la API key del usuario). `openai` = `ALMA_API_KEY` del entorno. |
| `ALMA_PORT` | `8471` | Puerto del servidor (solo escucha en 127.0.0.1). |
| `ALMA_DB` | `~/workspace/alma-prototype/alma_store.db` | Ruta de la memoria SQLite. |
| `ALMA_URL` | `http://127.0.0.1:8471` | URL que usa `cliente_chequeo.py`. |

Nunca hay claves en el código ni en los logs.

## Cómo se usa

Resolver un problema:

```bash
curl -X POST localhost:8471/resolver -H 'Content-Type: application/json' \
  -d '{"texto":"¿Cuánto es 12 por 12?","clase":"calculo","esperado":"144","modo":"thompson"}'
# → {"respuesta":..., "brazo":"single", "reward":0.95, "experiencia_id":661, ...}
```

- `modo` puede ser `thompson` (elige por Thompson sampling, default) o
  `probe` (prueba los 3 brazos y se queda con el mejor; necesita `esperado`
  o un backend real).
- Si no se pasa `clase`, el motor clasifica solo con el featurizer.
- Sin `esperado` y sin backend real, el reward queda en `None` y el motor
  **no aprende** hasta que llegue feedback explícito:

```bash
curl -X POST localhost:8471/feedback -H 'Content-Type: application/json' \
  -d '{"experiencia_id":662,"reward":0.8,"nota":"sirvió el análisis"}'
```

Ver el estado (medias por clase, integridad de la cadena):

```bash
curl localhost:8471/estado
```

## El prior warm con olvido

Al arrancar, el motor reconstruye los priors desde SQLite: cada experiencia
pasada pesa `0.5^días` (maquinaria del EXP9). Nada se borra; lo viejo pesa
menos. Hay un tope anti-fosilización de 200 pseudo-observaciones por brazo.
La DB arranca con las 660 experiencias históricas migradas del JSONL
(`resultados/experiencias.jsonl`).

## Cableado con el chequeo nocturno

`cliente_chequeo.py` deja el cableado listo **sin tocar los crons**:

```bash
python3 cliente_chequeo.py /ruta/al/diario.txt
# o:  cat diario.txt | python3 cliente_chequeo.py
```

Envía el log como clase `analisis_diario`, imprime el análisis y guarda la
respuesta completa en `ultimo_analisis.json` con su `experiencia_id`. El
aprendizaje se cierra al día siguiente con `/feedback` ("¿sirvió?"). Para
usar el modelo real en el análisis: `ALMA_BACKEND=vault ./arrancar.sh`.

## Puerta de calidad

Antes de aceptar cualquier cambio en el motor:

```bash
./puerta_calidad.sh   # PASS → se puede cambiar; FAIL → arreglar primero
```

Corre el roundtrip completo en modo demo (problema → respuesta →
experiencia guardada → el segundo problema usa el prior warm → el feedback
mueve el posterior) más los 33 tests existentes del prototipo. No toca la
API ni la DB real.

## Lo que v1 NO hace (para v2)

- Re-probe continuo automático (hoy el probe es por llamada, no por stream).
- Clases descubiertas por el sistema (la taxonomía sigue siendo la fija v1).
- El juez LLM en modo demo (sin `esperado`, el reward espera feedback).
- Autenticación en el HTTP (escucha solo en localhost: es para uso local).
