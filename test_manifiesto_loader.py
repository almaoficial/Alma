"""Filtro de confianza de skills conectado al loader (manifiesto+skills).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_manifiesto_loader.py

Usa ALMA_CLAVES_DIR / ALMA_LOG_CARGAS en tmp: nunca toca claves ni logs
reales.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_TMP = tempfile.mkdtemp(prefix="test_manifiesto_loader_")
os.environ["ALMA_CLAVES_DIR"] = os.path.join(_TMP, "claves")
os.environ["ALMA_LOG_CARGAS"] = os.path.join(_TMP, "logs", "cargas.jsonl")

from alma_service import manifiesto as M
from alma_service.skills import SkillIndex, cargar_skill

PASSOS = []


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


SKILL_MD = """---
name: {nombre}
description: Skill de prueba para el filtro de confianza del loader.
---
# {nombre}

Cuerpo de la skill.
"""

SCRIPT_OK = """# scripts/hola.py: script limpio, sin secretos ni webhooks\nprint('hola')\n"""

WEBHOOK_SIN_AUTH = """Bun.serve({
  port: 4242,
  fetch(req) { return handleToolCalls(req.json()); }
});
"""


def armar_skill(nombre, scripts=None):
    d = os.path.join(_TMP, "skills", "pruebas", nombre)
    os.makedirs(os.path.join(d, "scripts"), exist_ok=True)
    with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(SKILL_MD.format(nombre=nombre))
    for fn, contenido in (scripts or {}).items():
        with open(os.path.join(d, "scripts", fn), "w", encoding="utf-8") as f:
            f.write(contenido)
    return d


def nuevo_index(etiqueta):
    return SkillIndex(os.path.join(_TMP, f"idx-{etiqueta}.sqlite"))


def leer_log():
    if not os.path.exists(os.environ["ALMA_LOG_CARGAS"]):
        return []
    with open(os.environ["ALMA_LOG_CARGAS"], encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    # 0. Clave propia + autor tercero en el trust store.
    M.asegurar_clave()
    from alma_service import _ed25519
    ask, apk = _ed25519.generar_clave()
    os.makedirs(os.path.join(os.environ["ALMA_CLAVES_DIR"], "autores"),
                exist_ok=True)
    with open(os.path.join(os.environ["ALMA_CLAVES_DIR"], "autores",
                           "acme.pub"), "wb") as f:
        f.write(apk)

    idx = nuevo_index("a")

    # 1. Tier 0 (firmada por Alejandro) → registra y carga plena.
    d0 = armar_skill("propia", scripts={"hola.py": SCRIPT_OK})
    M.firmar_skill(d0)
    s0 = cargar_skill(os.path.join(d0, "SKILL.md"))
    idx.registrar(s0, presupuesto_tokens=10_000)
    c0 = idx.cargar_completa(s0.path)
    check("tier 0: carga plena con nivel_confianza=0",
          c0.nivel_confianza == 0 and c0.veredicto["decision"] == "plena")

    # 2. Tier 1 (tercero firmado) → registra y carga sandbox.
    d1 = armar_skill("tercero", scripts={"hola.py": SCRIPT_OK})
    M.firmar_skill(d1, firmante="acme", sk=ask)
    s1 = cargar_skill(os.path.join(d1, "SKILL.md"))
    idx.registrar(s1, presupuesto_tokens=10_000)
    c1 = idx.cargar_completa(s1.path)
    check("tier 1: carga sandbox con nivel_confianza=1",
          c1.nivel_confianza == 1 and c1.veredicto["decision"] == "sandbox")

    # 3. Tier 2 sin scripts (instruction-only) → restringida pero carga.
    d2 = armar_skill("plana")
    s2 = cargar_skill(os.path.join(d2, "SKILL.md"))
    idx.registrar(s2, presupuesto_tokens=10_000)
    c2 = idx.cargar_completa(s2.path)
    check("tier 2 instruction-only: carga restringida",
          c2.nivel_confianza == 2
          and c2.veredicto["decision"] == "restringida")

    # 4. Tier 2 con scripts sin firma → registrar BLOQUEA (no entra al índice).
    d3 = armar_skill("sinfirma-scripts", scripts={"hola.py": SCRIPT_OK})
    s3 = cargar_skill(os.path.join(d3, "SKILL.md"))
    try:
        idx.registrar(s3, presupuesto_tokens=10_000)
        bloqueada = False
    except M.SkillBloqueada:
        bloqueada = True
    check("tier 2 con scripts: registrar levanta SkillBloqueada", bloqueada)
    check("tier 2 con scripts: NO entró al índice",
          not idx.tiene_skill("pruebas", "sinfirma-scripts"))

    # 5. Rechazada (webhook sin auth) → SkillRechazada incluso registrando.
    d4 = armar_skill("peligrosa", scripts={"webhook.ts": WEBHOOK_SIN_AUTH})
    s4 = cargar_skill(os.path.join(d4, "SKILL.md"))
    try:
        idx.registrar(s4, presupuesto_tokens=10_000)
        rechazada = False
    except M.SkillRechazada:
        rechazada = True
    check("webhook sin auth: registrar levanta SkillRechazada", rechazada)

    # 6. Skill legacy (tier 2 con scripts) registrada con el filtro OFF →
    #    al cargar con el filtro ON, la carga se bloquea.
    d5 = armar_skill("legacy", scripts={"hola.py": SCRIPT_OK})
    s5 = cargar_skill(os.path.join(d5, "SKILL.md"))
    os.environ["ALMA_FILTRO_SKILLS"] = "0"
    idx_off = nuevo_index("off")
    idx_off.registrar(s5, presupuesto_tokens=10_000)
    c5_off = idx_off.cargar_completa(s5.path)
    check("filtro OFF: legacy con scripts carga como antes (reversible)",
          c5_off.nombre == "legacy"
          and not getattr(c5_off, "nivel_confianza", None))
    os.environ["ALMA_FILTRO_SKILLS"] = "1"
    try:
        idx_off.cargar_completa(s5.path)
        bloquea_carga = False
    except M.SkillBloqueada:
        bloquea_carga = True
    check("filtro ON: cargar_completa bloquea la legacy tier 2 con scripts",
          bloquea_carga)

    # 7. Registro de cargas: hay líneas con tier y decisión (puntos
    #    registrar y cargar).
    eventos = leer_log()
    tiers_vistos = {(e["tier"], e["decision"], e["punto"]) for e in eventos}
    tiene = lambda t, d, p: (t, d, p) in tiers_vistos
    check("log: tier 0 plena en punto registrar",
          tiene(0, "plena", "registrar"))
    check("log: tier 1 sandbox en punto cargar",
          tiene(1, "sandbox", "cargar"))
    check("log: tier 2 restringida registrada",
          tiene(2, "restringida", "registrar"))
    check("log: tier 2 bloqueada registrada (la que no entró)",
          tiene(2, "bloqueada", "registrar"))

    # 8. Cache por huella: dos evaluar_cacheado del mismo path → mismo
    #    veredicto (mismo dict, no reescanea).
    v1 = M.evaluar_cacheado(os.path.join(d0, "SKILL.md"))
    v2 = M.evaluar_cacheado(os.path.join(d0, "SKILL.md"))
    check("cache por bytes: mismo veredicto en memoria (no reescanea)",
          v1 is v2)

    idx.close()
    print()
    ok = all(PASSOS)
    print(f"{sum(PASSOS)}/{len(PASSOS)} PASS")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
