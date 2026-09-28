#!/bin/bash
# Arranca el servicio ALMA v1 en segundo plano.
# Uso: ./arrancar.sh   (respeta ALMA_PORT, ALMA_DB, ALMA_BACKEND del entorno)
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
PIDF="$DIR/servicio.pid"
LOGF="$DIR/servicio.log"

if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "El servicio ya está corriendo (pid $(cat "$PIDF"))."
  exit 0
fi

cd "$DIR"
nohup python3 -u server.py >> "$LOGF" 2>&1 &
echo $! > "$PIDF"
sleep 1
if kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "Servicio arrancado (pid $(cat "$PIDF")). Log: $LOGF"
else
  echo "ERROR: no arrancó. Mirá $LOGF"
  exit 1
fi
