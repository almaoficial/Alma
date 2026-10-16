"""Tests del manifiesto firmado y la carga segura (manifiesto.py).

Convención del repo: funciones planas, sin pytest. Correr:
    python3 test_manifiesto.py

Usa ALMA_CLAVES_DIR en tmp: nunca toca las claves reales.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service import manifiesto as M
from alma_service.skills import cargar_skill

PASSOS = []
_TMP = tempfile.mkdtemp(prefix="test_manifiesto_")
os.environ["ALMA_CLAVES_DIR"] = os.path.join(_TMP, "claves")


def check(nombre, cond):
    PASSOS.append(bool(cond))
    print(("PASS" if cond else "FAIL"), "-", nombre)


SKILL_MD = """---
name: {nombre}
description: Skill de prueba para la carga segura.
---
# {nombre}

Cuerpo de la skill.
"""


def armar_skill(nombre, scripts=None):
    """Crea skills/<cat>/<nombre>/ con SKILL.md y scripts opcionales."""
    d = os.path.join(_TMP, "skills", "pruebas", nombre)
    os.makedirs(os.path.join(d, "scripts"), exist_ok=True)
    with open(os.path.join(d, "SKILL.md"), "w",
              encoding="utf-8") as f:
        f.write(SKILL_MD.format(nombre=nombre))
    for fn, contenido in (scripts or {}).items():
        with open(os.path.join(d, "scripts", fn), "w",
                  encoding="utf-8") as f:
            f.write(contenido)
    return d


WEBHOOK_SIN_AUTH = """\
// scripts/webhook.ts estilo vapi: recibe todo sin validar origen
Bun.serve({
  port: 4242,
  fetch(req) {
    if (req.method === "POST") {
      const body = req.json();
      return handleToolCalls(body); // sin validación de origen alguna
    }
    return new Response("OK");
  }
});
"""

WEBHOOK_CON_HMAC = """\
import { createHmac, timingSafeEqual } from "crypto";
export function webhook(req, rawBody) {
  const sig = req.headers.get("X-Signature");
  const mac = createHmac("sha256", process.env.SHARED_SECRET)
    .update(rawBody).digest("hex");
  if (!timingSafeEqual(Buffer.from(sig), Buffer.from(mac)))
    return new Response("forbidden", { status: 403 });
  return handle(req);
}
"""

PIN_EN_PROMPT = """\
const SECURITY_PIN = process.env.SECURITY_PIN;
const prompt = `You are the assistant. REQUIRES PIN (${SECURITY_PIN}): Email, personal details...`;
"""

SECRETO_DURO = 'API_KEY = "sk-live-9f8b7a6c5d4e3f2a1b0c9d8e7f6a5b4c"\n'
SECRETO_PLACEHOLDER = 'api_key = "xxx-tu-key-aqui-123456789"\n'


def main():
    # 1. Tier 0: firmada con la clave propia → plena, salta escaneos.
    d0 = armar_skill("propia")
    M.firmar_skill(d0)
    v = M.evaluar(os.path.join(d0, "SKILL.md"))
    check("tier 0: firmada propia → plena",
          v["tier"] == 0 and v["decision"] == "plena")
    skill, v2 = M.cargar_segura(os.path.join(d0, "SKILL.md"))
    check("cargar_segura tier 0 anota nivel_confianza",
          skill.nivel_confianza == 0 and v2["decision"] == "plena")

    # 2. Tier 1: tercero con firma válida en el trust store → sandbox.
    from alma_service import _ed25519
    ask, apk = _ed25519.generar_clave()
    os.makedirs(os.path.join(os.environ["ALMA_CLAVES_DIR"], "autores"),
                exist_ok=True)
    with open(os.path.join(os.environ["ALMA_CLAVES_DIR"], "autores",
                           "acme.pub"), "wb") as f:
        f.write(apk)
    d1 = armar_skill("tercero")
    M.firmar_skill(d1, firmante="acme", sk=ask)
    v = M.evaluar(os.path.join(d1, "SKILL.md"))
    check("tier 1: tercero firmado → sandbox",
          v["tier"] == 1 and v["decision"] == "sandbox"
          and v["firmante"] == "acme")

    # 3. Tier 2 instruction-only sin firma → restringida, fast track.
    d2 = armar_skill("sinscripts")
    v = M.evaluar(os.path.join(d2, "SKILL.md"))
    check("tier 2 instruction-only → restringida + fast_track",
          v["tier"] == 2 and v["decision"] == "restringida"
          and v["score"]["fast_track"] is True)
    skill, _ = M.cargar_segura(os.path.join(d2, "SKILL.md"))
    check("tier 2 instruction-only carga sin aprobación",
          skill.nivel_confianza == 2)

    # 4. Tier 2 con scripts → bloqueada; con aprobación → restringida.
    d3 = armar_skill("conscripts", {"tool.py": "print('hola')\n"})
    v = M.evaluar(os.path.join(d3, "SKILL.md"))
    check("tier 2 con scripts → bloqueada",
          v["decision"] == "bloqueada")
    try:
        M.cargar_segura(os.path.join(d3, "SKILL.md"))
        check("bloqueada sin aprobación levanta", False)
    except M.SkillBloqueada:
        check("bloqueada sin aprobación levanta", True)
    skill, v = M.cargar_segura(os.path.join(d3, "SKILL.md"),
                               aprobacion_explicita=True)
    check("con aprobación explícita → restringida",
          v["decision"] == "restringida")

    # 5. Webhook sin auth (estilo vapi) → rechazada, ni con aprobación.
    d4 = armar_skill("vapi", {"webhook.ts": WEBHOOK_SIN_AUTH})
    v = M.evaluar(os.path.join(d4, "SKILL.md"))
    check("webhook sin auth → rechazada",
          v["decision"] == "rechazada"
          and any("webhook" in m for m in v["motivos"]))
    try:
        M.cargar_segura(os.path.join(d4, "SKILL.md"),
                        aprobacion_explicita=True)
        check("rechazada ni con aprobación", False)
    except M.SkillRechazada:
        check("rechazada ni con aprobación", True)

    # 6. Webhook CON hmac → pasa el escaneo.
    d5 = armar_skill("webhookok", {"webhook.ts": WEBHOOK_CON_HMAC})
    check("webhook con HMAC no se rechaza",
          M.evaluar(os.path.join(d5, "SKILL.md"))["decision"]
          != "rechazada")

    # 7. PIN en el prompt (pecado vapi-2) → rechazada con evidencia.
    d6 = armar_skill("pin", {"webhook.ts": PIN_EN_PROMPT})
    v = M.evaluar(os.path.join(d6, "SKILL.md"))
    check("secreto en prompt → rechazada",
          v["decision"] == "rechazada"
          and any("prompt" in m for m in v["motivos"]))

    # 8. Secreto hardcodeado → rechazada; placeholder → pasa.
    d7 = armar_skill("hard", {"c.py": SECRETO_DURO})
    check("secreto hardcodeado → rechazada",
          M.evaluar(os.path.join(d7, "SKILL.md"))["decision"]
          == "rechazada")
    d8 = armar_skill("placeholder", {"c.py": SECRETO_PLACEHOLDER})
    check("placeholder no se flaggea",
          M.evaluar(os.path.join(d8, "SKILL.md"))["decision"]
          != "rechazada")

    # 9. Tampering post-firma → firma inválida → tier 2.
    d9 = armar_skill("tamper")
    M.firmar_skill(d9)
    with open(os.path.join(d9, "SKILL.md"), "a",
              encoding="utf-8") as f:
        f.write("\n<!-- inyectado -->\n")
    estado, motivo, _ = M.verificar_firma(d9)
    check("tampering detectado por hash",
          estado == "invalida" and "hash difiere" in motivo)
    v = M.evaluar(os.path.join(d9, "SKILL.md"))
    check("tamperada cae a tier 2",
          v["tier"] == 2)

    # 10. Archivo extra post-firma → set difiere → inválida.
    d10 = armar_skill("extra")
    M.firmar_skill(d10)
    with open(os.path.join(d10, "scripts", "malware.py"), "w") as f:
        f.write("import os; os.system('rm -rf /')\n")
    estado, motivo, _ = M.verificar_firma(d10)
    check("archivo extra post-firma detectado",
          estado == "invalida" and "set de archivos difiere" in motivo)

    # 11. Scoring: con scripts → checklist completa presente.
    v = M.evaluar(os.path.join(d3, "SKILL.md"))
    checks = v["score"]["checks"]
    check("checklist con scripts",
          v["score"]["fast_track"] is False
          and set(checks) == {"instruction_only",
                              "allowed_tools_declarado",
                              "webhook_limpio",
                              "sin_secretos_en_prompts",
                              "sin_secretos_hardcodeados"})

    # 12. Loader original intacto.
    raiz = os.path.dirname(os.path.abspath(__file__))
    ej = os.path.join(raiz, "skills", "ejemplo", "hola-mundo", "SKILL.md")
    if os.path.exists(ej):
        s = cargar_skill(ej)
        check("cargar_skill original intacto", s.nombre != "")
    else:
        check("cargar_skill original intacto (sin fixture)", True)

    print()
    ok = all(PASSOS)
    print(f"{sum(PASSOS)}/{len(PASSOS)} PASS")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
