"""ALMA servicio — fase 0 (scaffolding del sistema real, US$0, sin key).

Componentes:
  memoria      → experiencias en SQLite con timestamp, decaimiento temporal
                  y evicción acotada (el olvido que Hermes no tiene, EXP9).
  skills       → skills en formato AgentSkills (SKILL.md + progressive
                  disclosure) con índice SQLite y presupuesto duro de contexto.
  recurrencia  → detector de recurrencia: compuerta entre modo adaptativo
                  puro y loop de skills (honestidad estructural, EXP44).
  resolver     → probe → selección → ejecución + aprendizaje; la política
                  validada por los mocks (EXP45/49/51) como componente
                  reutilizable, con bit-identidad verificada vs EXP51.
  curator      → ciclo de vida determinista active → stale → archived
                  (nunca borra); la consolidación LLM es opt-in de fase 2+.
  harness      → puerta de calidad: experimentos mock con pre-registro
                  escrito antes de correr y veredicto PASS/FAIL.
  metaloop_stub → stub documentado del Meta-loop (fase 2+).
"""

import os
import sys

_BASE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_BASE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

__version__ = "0.1.0-fase0"
