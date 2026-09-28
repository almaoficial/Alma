#!/bin/bash
# Puerta de calidad: corre la suite mock antes de aceptar cambios en el motor.
# Uso: ./puerta_calidad.sh
# Sale 0 si todo pasa, 1 si algo falla. No toca la API ni la DB real.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
echo "=== Puerta de calidad ALMA-servicio v2 ==="
python3 chequeo_motor.py
RC=$?
if [ $RC -eq 0 ]; then
  echo "=== PASS: el motor puede cambiarse con confianza ==="
else
  echo "=== FAIL: no aceptar cambios hasta arreglar ==="
fi
exit $RC
