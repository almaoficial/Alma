#!/usr/bin/env python3
"""Fase 2.1 (Cherny d): ablación por evidencia del Curator.

Checks: notificar_uso_exitoso registra evitación solo si el fallo se
repitió (≥2); ablacion_por_evidencia archiva skills curables viejas sin
evidencia y perdona las recientes y las con evidencia; las externas no
se tocan; todo queda en el ledger.
"""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alma_service.skills import Skill, SkillIndex  # noqa: E402
from alma_service.curator import (  # noqa: E402
    Curator, UMBRAL_EVIDENCIA, GRACIA_CREACION_DIAS, ESTADO_ACTIVE,
    ESTADO_ARCHIVED)

CHECKS = []


def check(nombre, cond):
    CHECKS.append((nombre, bool(cond)))
    print(("PASS " if cond else "FAIL ") + nombre)


DIA = 86400
AHORA = time.time()

d = tempfile.mkdtemp(prefix="alma_abl_")
idx = SkillIndex(os.path.join(d, "skills.db"))
cur = Curator(idx)


def alta(nombre, created_by="agent", hace_dias=0):
    p = os.path.join(d, nombre, "SKILL.md")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(f"---\nname: {nombre}\ndescription: d\n---\n# {nombre}\n")
    sk = Skill(path=p, categoria="t", nombre=nombre, descripcion="d",
               cuerpo="x", created_by=created_by, version=1,
               estado=ESTADO_ACTIVE, referencias=[])
    idx.registrar(sk, 10 ** 9)
    idx._db.execute("UPDATE skills SET created_at=? WHERE path=?",
                    (AHORA - hace_dias * DIA, p))
    idx._db.commit()
    return p


# Tres skills curables: (a) vieja con evidencia, (b) nueva sin evidencia
# (gracia), (c) vieja sin evidencia (ablable).
pa = alta("con_evidencia", hace_dias=100)
pb = alta("nueva", hace_dias=5)
pc = alta("sin_evidencia", hace_dias=100)
# Una externa vieja sin evidencia: no curable → no se toca.
pe = alta("externa", created_by="externo", hace_dias=100)

# 1. notificar_uso_exitoso: con 3 fallos previos (≥2) → registra.
ok = cur.notificar_uso_exitoso(pa, "firma-x", lambda f: 3, ahora=AHORA)
check("evitacion registrada si fallo repetido", ok)
# 2. Con 1 fallo previo (<2) → no registra.
ok = cur.notificar_uso_exitoso(pb, "firma-y", lambda f: 1, ahora=AHORA)
check("sin evitacion si no hubo repeticion", not ok)

# 3. Ablación: solo archiva la vieja sin evidencia.
archivadas = cur.ablacion_por_evidencia(ahora=AHORA)
paths = [e["skill"] for e in archivadas]
check("abla solo la vieja sin evidencia", paths == [pc])
check("motivo en el ledger",
      any(e["evento"].get("tipo") == "ablacion_archivada"
          and "sin registro" in e["evento"].get("motivo", "")
          for e in cur.ledger.leer()))

# 4. Estados finales: pc archived; las demás active.
est = {f["path"]: f["estado"]
       for f in list(idx.listar(estado=ESTADO_ACTIVE))
       + list(idx.listar(estado=ESTADO_ARCHIVED))}
check("estados finales correctos",
      est.get(pc) == "archived" and est.get(pa) == ESTADO_ACTIVE
      and est.get(pb) == ESTADO_ACTIVE and est.get(pe) == ESTADO_ACTIVE)

# 5. correr_ciclo sigue retornando la lista de transiciones (compat).
check("correr_ciclo retorna lista",
      isinstance(cur.correr_ciclo(ahora=AHORA), list))

# 6. Constantes documentadas.
check("umbral=2 gracia=30", UMBRAL_EVIDENCIA == 2
      and GRACIA_CREACION_DIAS == 30)

n_fails = sum(1 for _, c in CHECKS if not c)
print(f"\n{len(CHECKS) - n_fails}/{len(CHECKS)} checks en verde")
sys.exit(1 if n_fails else 0)
