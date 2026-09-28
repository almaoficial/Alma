#!/bin/bash
# Para el servicio ALMA v1.
# Uso: ./parar.sh
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
PIDF="$DIR/servicio.pid"

if [ ! -f "$PIDF" ]; then
  echo "No hay pid guardado; nada que parar."
  exit 0
fi
PID="$(cat "$PIDF")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  sleep 1
  if kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID"
  fi
  echo "Servicio detenido (pid $PID)."
else
  echo "El proceso $PID ya no corría."
fi
rm -f "$PIDF"
