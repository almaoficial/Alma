#!/usr/bin/env bash
# Puerta de fase 0 de ALMA-servicio (US$0, sin red, sin key).
#
# Criterio de salida (doble condición):
#   1. Todos los tests de fase 0 pasan.
#   2. El harness corre `fase0-scaffold-evolucionado` y el veredicto es PASS:
#      bit-identidad vs la implementación independiente
#      exp56_rso/run_experiment56.py con el scaffold validado por EXP56/57
#      (n0=4, umbral_base=1) — reg_trat_bloques por réplica —
#      Y media(efecto) < 0.
#
# Nota 27/9: la puerta validaba bit-identidad vs EXP51 (n0=2,
# umbral_base=2). La integración de los defaults validados cambió la
# política a propósito; la puerta ahora valida la política evolucionada.
#
# Uso: bash fase0_puerta.sh

set -euo pipefail
cd "$(dirname "$0")"

echo "=== FASE 0: tests unitarios ==="
for t in test_fase0_memoria test_fase0_skills test_fase0_recurrencia \
         test_fase0_curator test_fase0_resolver test_fase0_harness; do
  python3 "$t.py" > /tmp/fase0_$t.log 2>&1
  if grep -q "^FAIL" /tmp/fase0_$t.log; then
    echo "FAIL en $t:"; grep "^FAIL" /tmp/fase0_$t.log; exit 1
  fi
  echo "ok: $t"
done

echo "=== FASE 0: experimento de la puerta (harness) ==="
python3 - <<'EOF'
import json, os, sys
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("exp56_rso"))
import run_experiment47 as e47
import run_experiment56 as e56
from alma_service.harness import experimento_fase0, correr_experimento
from alma_service.scaffold import DEFAULT_SCAFFOLD

tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
items = e47.construir_stream()  # bit-idéntico al stream de EXP47-51
# Referencia independiente: el runner de EXP56 con el scaffold validado
# (n0=4, umbral_base=1, umbral_divisor=3). Implementación distinta del
# mismo scaffold que el servicio; la bit-identidad verifica el cableado.
sc = dict(DEFAULT_SCAFFOLD)
referencia = {
    "reg_trat_bloques": [
        e56.correr_replica_param(r, items, tasas, dict(sc))["reg_pol_bloques"]
        for r in range(5)
    ],
}

exp = experimento_fase0()
report, veredicto = correr_experimento(
    exp, "resultados/fase0-puerta", tasas, items,
    report_referencia=referencia)
print(veredicto)
sys.exit(0 if "**PASS**" in veredicto else 1)
EOF

echo "=== PUERTA FASE 0: PASS ==="
