"""Manifiesto firmado y carga segura de skills (decisión del usuario 7/10).

Del escaneo de 5 skills (research_notes/skill-scan-5-20261006): ninguna
trae firma, y los huecos reales son de diseño (webhook sin auth, secreto
en el prompt). La regla binaria "sin firma no carga. Punto." es correcta
en dirección pero inútil hoy: 0 de 5 skills reales firman. Por eso:
tiers, no portón.

- TIER 0 (propia): firmada con la clave de Alejandro → carga plena.
  Su firma es su palabra: se salta los escaneos heurísticos.
- TIER 1 (tercero firmada): firma ed25519 válida de un autor en el
  trust store → carga con sandbox según `allowed-tools` declarados.
- TIER 2 (tercero sin firma): el código NO corre. Solo instruction-only
  (sin `scripts/`); con scripts requiere aprobación explícita caso por
  caso (SkillBloqueada si falta).

Para tiers 1 y 2, fail closed ante:
- webhook que acepta requests sin validar origen (lección vapi-1);
- secreto interpolado en un prompt (lección vapi-2);
- secreto hardcodeado en scripts.

Scoring (regla 3 del informe): instruction-only → fast track (revisión
mínima); con scripts → checklist completa de defensas.

Firmas: ed25519 puro-python vendoreado (_ed25519.py, dominio público),
cero dependencias. Manifiesto: MANIFIESTO.json
{name, version, firmante, archivos: {relpath: sha256}} + MANIFIESTO.json.sig
(base64 de la firma sobre el JSON canónico). Se cubre SKILL.md + todo
scripts/ (el set de archivos debe coincidir exacto).

Claves: ~/.config/alma/claves/firma_ed25519.key (0600, nunca sale de
disco ni del chat) + .pub; autores terceros en
~/.config/alma/claves/autores/<id>.pub (env ALMA_CLAVES_DIR en tests).

Complementa a procedencia.py (registro de origen + cuarentena): aquello
rastrea DE DÓNDE vino cada skill; esto verifica QUE lo que llegó sea lo
que el autor firmó, y decide SI entra y CÓMO.
"""

import base64
import hashlib
import json
import os
import re
import time

from .skills import cargar_skill, parse_frontmatter, SkillInvalida
from . import _ed25519

MANIFIESTO = "MANIFIESTO.json"
SIG_EXT = ".sig"

TIER_PROPIA = 0
TIER_FIRMADA = 1
TIER_SIN_FIRMA = 2

NOMBRES_TIER = {0: "propia", 1: "tercero firmada", 2: "tercero sin firma"}

NOMBRE_FIRMANTE_PROPIO = "alejandro"


class SkillBloqueada(SkillInvalida):
    """Tier 2 con scripts: solo carga con aprobación explícita."""


class SkillRechazada(SkillInvalida):
    """Fail closed: hueco de diseño detectado. Ni la aprobación la carga."""


# --- claves ---------------------------------------------------------------

def _dir_claves():
    return os.environ.get(
        "ALMA_CLAVES_DIR",
        os.path.join(os.path.expanduser("~"), ".config", "alma", "claves"))


def _ruta_sk():
    return os.path.join(_dir_claves(), "firma_ed25519.key")


def _ruta_pk():
    return os.path.join(_dir_claves(), "firma_ed25519.pub")


def _dir_autores():
    return os.path.join(_dir_claves(), "autores")


def asegurar_clave():
    """Genera el par de Alejandro si no existe. Retorna (sk, pk).

    La privada queda en 0600 y nunca sale de disco ni del chat."""
    d = _dir_claves()
    os.makedirs(d, exist_ok=True)
    sk_path, pk_path = _ruta_sk(), _ruta_pk()
    if os.path.exists(sk_path) and os.path.exists(pk_path):
        # Las claves son binario crudo de 32 bytes, sin delimitadores:
        # NUNCA .strip() — un byte extremo puede ser whitespace válido
        # (0x09-0x0D, 0x20) y stripearlo acorta la clave, lo que hacía
        # regenerar un par distinto al que firmó (falla intermitente
        # ~9% según el par sorteado; diagnóstico 16/10/2026).
        with open(sk_path, "rb") as f:
            sk = f.read()
        with open(pk_path, "rb") as f:
            pk = f.read()
        if len(sk) == 32 and len(pk) == 32:
            return sk, pk
    sk, pk = _ed25519.generar_clave()
    with open(sk_path, "wb") as f:
        f.write(sk)
    os.chmod(sk_path, 0o600)
    with open(pk_path, "wb") as f:
        f.write(pk)
    os.makedirs(_dir_autores(), exist_ok=True)
    return sk, pk


def clave_publica():
    _, pk = asegurar_clave()
    return pk


# --- manifiesto y firma ---------------------------------------------------

def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def _archivos_cubiertos(dir_skill):
    """SKILL.md + todo lo que cuelgue de scripts/ (rutas relativas)."""
    rels = ["SKILL.md"]
    scripts = os.path.join(dir_skill, "scripts")
    if os.path.isdir(scripts):
        for base, _, ficheros in os.walk(scripts):
            for fn in sorted(ficheros):
                full = os.path.join(base, fn)
                rels.append(os.path.relpath(full, dir_skill))
    return sorted(set(rels))


def _json_canonico(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def firmar_skill(dir_skill, firmante=NOMBRE_FIRMANTE_PROPIO, sk=None):
    """Firma una skill. Por default con la clave de Alejandro; `sk`
    permite firmar como tercero (tests / herramienta del autor)."""
    dir_skill = os.path.abspath(dir_skill)
    skill_md = os.path.join(dir_skill, "SKILL.md")
    if not os.path.isfile(skill_md):
        raise SkillInvalida(f"no hay SKILL.md en {dir_skill}")
    fm, _ = parse_frontmatter(open(skill_md, encoding="utf-8").read())
    manifiesto = {
        "name": fm.get("name", ""),
        "version": str(fm.get("version", "1")),
        "firmante": firmante,
        "archivos": {},
    }
    for rel in _archivos_cubiertos(dir_skill):
        full = os.path.join(dir_skill, rel)
        if not os.path.isfile(full):
            raise SkillInvalida(f"manifiesto: falta {rel}")
        manifiesto["archivos"][rel] = _sha256(full)
    if sk is None:
        sk, _ = asegurar_clave()
    sig = _ed25519.firmar(sk, _json_canonico(manifiesto))
    with open(os.path.join(dir_skill, MANIFIESTO), "w",
              encoding="utf-8") as f:
        f.write(_json_canonico(manifiesto).decode("utf-8"))
    with open(os.path.join(dir_skill, MANIFIESTO + SIG_EXT), "w",
              encoding="utf-8") as f:
        f.write(base64.b64encode(sig).decode("ascii"))
    return manifiesto


def _claves_autores():
    """{id_autor: pk_bytes} del trust store."""
    out = {}
    d = _dir_autores()
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".pub"):
            with open(os.path.join(d, fn), "rb") as f:
                pk = f.read()  # binario crudo: sin .strip() (ver arriba)
            if len(pk) == 32:
                out[fn[:-4]] = pk
    return out


def verificar_firma(dir_skill):
    """Retorna (estado, motivo, firmante).

    estado: "propia" | "tercero" | "ausente" | "invalida".
    """
    dir_skill = os.path.abspath(dir_skill)
    man_path = os.path.join(dir_skill, MANIFIESTO)
    sig_path = man_path + SIG_EXT
    if not os.path.isfile(man_path) or not os.path.isfile(sig_path):
        return ("ausente", "sin MANIFIESTO.json firmado", None)
    try:
        manifiesto = json.loads(open(man_path, encoding="utf-8").read())
        sig = base64.b64decode(open(sig_path, encoding="utf-8").read())
    except Exception as ex:
        return ("invalida", f"manifiesto o firma ilegibles: {ex}", None)
    # 1. Los hashes deben coincidir y el set de archivos ser exacto.
    esperados = set(manifiesto.get("archivos", {}))
    reales = set(_archivos_cubiertos(dir_skill))
    if esperados != reales:
        return ("invalida",
                f"set de archivos difiere: solo-manifiesto="
                f"{sorted(esperados - reales)}, solo-disco="
                f"{sorted(reales - esperados)}", None)
    for rel, sha in manifiesto["archivos"].items():
        if _sha256(os.path.join(dir_skill, rel)) != sha:
            return ("invalida", f"hash difiere (tampering): {rel}", None)
    # 2. La firma debe ser válida con alguna clave conocida.
    cuerpo = _json_canonico(manifiesto)
    _, pk_propia = asegurar_clave()
    if _ed25519.verificar(pk_propia, cuerpo, sig):
        return ("propia", "firma válida de Alejandro",
                NOMBRE_FIRMANTE_PROPIO)
    for autor, pk in _claves_autores().items():
        if _ed25519.verificar(pk, cuerpo, sig):
            return ("tercero", f"firma válida de {autor}", autor)
    return ("invalida", "firma no corresponde a ninguna clave conocida",
            None)


# --- escaneos estáticos (tiers 1 y 2) --------------------------------------

_PATRON_WEBHOOK = re.compile(r"webhook", re.I)
_PATRON_RECEPTOR = re.compile(
    r"do_POST|@app\.(post|route)|app\.post\(|Bun\.serve|createServer\(|"
    r"addEventListener\(\s*['\"]message['\"]|router\.post\(|\.post\(\s*['\"]/",
    re.I)
_PATRON_AUTH_ORIGEN = re.compile(
    r"hmac|verify_signature|validar_firma|check_signature|"
    r"X-?(Hub-)?Signature|secreto_compartido|shared_secret|"
    r"comparar_firmas|timingSafeEqual|Authorization",
    re.I)


def escanear_webhook(dir_skill):
    """Archivos que reciben webhooks sin validar origen → hallazgos.

    Heurística documentada: archivo 'webhook-ish' (nombre o contenido)
    con patrón receptor (POST) y sin evidencia de validación de origen.
    La skill propia (tier 0) no se escanea: su firma es la palabra de
    Alejandro."""
    hallazgos = []
    for base, _, ficheros in os.walk(dir_skill):
        for fn in ficheros:
            if fn in (MANIFIESTO, MANIFIESTO + SIG_EXT):
                continue
            full = os.path.join(base, fn)
            try:
                with open(full, encoding="utf-8", errors="ignore") as f:
                    contenido = f.read()
            except OSError:
                continue
            es_webhook = ("webhook" in fn.lower()
                          or (_PATRON_WEBHOOK.search(contenido)
                              and _PATRON_RECEPTOR.search(contenido)))
            if es_webhook and not _PATRON_AUTH_ORIGEN.search(contenido):
                rel = os.path.relpath(full, dir_skill)
                hallazgos.append(
                    f"{rel}: recibe webhook sin validación de origen "
                    f"aparente (sin HMAC/firma/secreto compartido)")
    return hallazgos


_PATRON_PROMPT = re.compile(r"prompt", re.I)
_PATRON_SECRETO_EN_PROMPT = re.compile(
    r"prompt[^;\n]{0,120}?"
    r"(REQUIRES\s+PIN|PIN\s*\(\s*\$\{|PIN\s*[:=]\s*['\"]?\w|"
    r"\$\{(SECURITY_PIN|PIN|SECRET|PASSWORD|API_KEY|TOKEN)\}|"
    r"\{(SECRET|PASSWORD|API_KEY|TOKEN|PIN)\})",
    re.I)


def escanear_secretos_en_prompts(dir_skill):
    """El pecado de vapi-2: el valor del secreto viaja en el prompt que
    ve el modelo. Estático y con evidencia (archivo:línea)."""
    hallazgos = []
    for base, _, ficheros in os.walk(dir_skill):
        for fn in ficheros:
            if fn in (MANIFIESTO, MANIFIESTO + SIG_EXT):
                continue
            full = os.path.join(base, fn)
            try:
                with open(full, encoding="utf-8", errors="ignore") as f:
                    lineas = f.read().splitlines()
            except OSError:
                continue
            for i, linea in enumerate(lineas, 1):
                if (_PATRON_PROMPT.search(linea)
                        and _PATRON_SECRETO_EN_PROMPT.search(linea)):
                    rel = os.path.relpath(full, dir_skill)
                    hallazgos.append(
                        f"{rel}:{i}: secreto interpolado en prompt: "
                        f"{linea.strip()[:100]}")
    return hallazgos


_PATRON_SECRETO_DURO = re.compile(
    r"(api[_-]?key|secret|token|password|passwd)\s*[:=]\s*"
    r"['\"]([A-Za-z0-9_\-./+]{12,})['\"]",
    re.I)
_PLACEHOLDERS = re.compile(
    r"xxx|example|tu_|your_|tu-|<|\btest\b|dummy|placeholder|changeme|"
    r"123456|abcdef", re.I)


def escanear_secretos_hardcodeados(dir_skill):
    """Literal secreto en código (defensa 13). Excluye placeholders."""
    hallazgos = []
    scripts = os.path.join(dir_skill, "scripts")
    if not os.path.isdir(scripts):
        return hallazgos
    for base, _, ficheros in os.walk(scripts):
        for fn in ficheros:
            full = os.path.join(base, fn)
            try:
                with open(full, encoding="utf-8", errors="ignore") as f:
                    lineas = f.read().splitlines()
            except OSError:
                continue
            for i, linea in enumerate(lineas, 1):
                m = _PATRON_SECRETO_DURO.search(linea)
                if m and not _PLACEHOLDERS.search(m.group(2)):
                    rel = os.path.relpath(full, dir_skill)
                    hallazgos.append(
                        f"{rel}:{i}: posible secreto hardcodeado "
                        f"({m.group(1)})")
    return hallazgos


def _tiene_scripts(dir_skill):
    scripts = os.path.join(dir_skill, "scripts")
    if not os.path.isdir(scripts):
        return False
    for _, _, ficheros in os.walk(scripts):
        if ficheros:
            return True
    return False


def puntuar(skill_fm, dir_skill):
    """Scoring regla 3: instruction-only → fast track; con scripts →
    checklist completa. Retorna dict (no decide)."""
    con_scripts = _tiene_scripts(dir_skill)
    checks = {
        "instruction_only": not con_scripts,
        "allowed_tools_declarado": bool(skill_fm.get("allowed-tools")
                                       or skill_fm.get("allowed_tools")),
        "webhook_limpio": not escanear_webhook(dir_skill),
        "sin_secretos_en_prompts":
            not escanear_secretos_en_prompts(dir_skill),
        "sin_secretos_hardcodeados":
            not escanear_secretos_hardcodeados(dir_skill),
    }
    return {
        "fast_track": not con_scripts,
        "checks": checks,
        "pasa_checklist": all(checks.values()),
    }


# --- evaluación y carga -----------------------------------------------------

def evaluar(path_skill_md, aprobacion_explicita=False):
    """Evalúa una skill y retorna el veredicto (dict). No carga nada.

    decision: plena | sandbox | restringida | bloqueada | rechazada.
    """
    path = os.path.abspath(path_skill_md)
    skill = cargar_skill(path)  # valida formato; raise si inválida
    dir_skill = os.path.dirname(path)
    fm, _ = parse_frontmatter(open(path, encoding="utf-8").read())
    con_scripts = _tiene_scripts(dir_skill)

    estado, motivo_firma, firmante = verificar_firma(dir_skill)

    if estado == "propia":
        return {
            "tier": TIER_PROPIA,
            "tier_nombre": NOMBRES_TIER[TIER_PROPIA],
            "decision": "plena",
            "motivos": [f"firma válida de {firmante}: su palabra"],
            "firmante": firmante,
            "score": puntuar(fm, dir_skill),
            "con_scripts": con_scripts,
        }

    # Tiers 1 y 2: escaneos fail closed.
    rechazos = []
    for h in escanear_webhook(dir_skill):
        rechazos.append(f"webhook sin auth: {h}")
    for h in escanear_secretos_en_prompts(dir_skill):
        rechazos.append(f"secreto en prompt: {h}")
    for h in escanear_secretos_hardcodeados(dir_skill):
        rechazos.append(f"secreto hardcodeado: {h}")
    if rechazos:
        tier = TIER_FIRMADA if estado == "tercero" else TIER_SIN_FIRMA
        return {
            "tier": tier,
            "tier_nombre": NOMBRES_TIER[tier],
            "decision": "rechazada",
            "motivos": [motivo_firma] + rechazos,
            "firmante": firmante,
            "score": puntuar(fm, dir_skill),
            "con_scripts": con_scripts,
        }

    if estado == "tercero":
        return {
            "tier": TIER_FIRMADA,
            "tier_nombre": NOMBRES_TIER[TIER_FIRMADA],
            "decision": "sandbox",
            "motivos": [motivo_firma,
                        "carga con sandbox según allowed-tools declarados"],
            "firmante": firmante,
            "score": puntuar(fm, dir_skill),
            "con_scripts": con_scripts,
        }

    # Tier 2: sin firma.
    motivos = [motivo_firma]
    if not con_scripts:
        motivos.append("instruction-only: fast track, sin código que correr")
        decision = "restringida"
    elif aprobacion_explicita:
        motivos.append("aprobación explícita caso por caso: carga "
                       "restringida con revisión")
        decision = "restringida"
    else:
        motivos.append("con scripts y sin firma: requiere aprobación "
                       "explícita")
        decision = "bloqueada"
    return {
        "tier": TIER_SIN_FIRMA,
        "tier_nombre": NOMBRES_TIER[TIER_SIN_FIRMA],
        "decision": decision,
        "motivos": motivos,
        "firmante": None,
        "score": puntuar(fm, dir_skill),
        "con_scripts": con_scripts,
    }


def cargar_segura(path_skill_md, aprobacion_explicita=False):
    """parse + evaluar + hacer cumplir. Retorna (Skill, veredicto).

    - bloqueada sin aprobación → SkillBloqueada
    - rechazada → SkillRechazada (ni la aprobación la carga)
    La Skill retornada lleva `nivel_confianza` (tier) y `veredicto`.
    `cargar_skill` original no se toca: sigue igual para lo interno.
    """
    veredicto = evaluar(path_skill_md, aprobacion_explicita)
    decision = veredicto["decision"]
    if decision == "rechazada":
        raise SkillRechazada(
            "skill rechazada (fail closed): "
            + "; ".join(veredicto["motivos"]))
    if decision == "bloqueada":
        raise SkillBloqueada(
            "skill bloqueada: tier 2 con scripts requiere aprobación "
            "explícita: " + "; ".join(veredicto["motivos"]))
    skill = cargar_skill(path_skill_md)
    skill.nivel_confianza = veredicto["tier"]
    skill.veredicto = veredicto
    return skill, veredicto


# --- registro de cargas y cache -------------------------------------------

_LOG_DIR_BASE = os.path.join(
    os.path.expanduser("~"), ".config", "alma", "logs")
_CACHE = {}


def ruta_log_cargas():
    """Ruta del log JSONL de cargas. Env ALMA_LOG_CARGAS."""
    return os.environ.get(
        "ALMA_LOG_CARGAS",
        os.path.join(_LOG_DIR_BASE, "cargas_skills.jsonl"))


def registrar_carga(path_skill_md, veredicto, punto=None):
    """Registra el veredicto de carga de una skill en el log JSONL.

    Una línea JSON por evento: hora, path, nombre de skill, tier,
    decisión, firmante, si tiene scripts, los motivos, y el punto de
    carga ("evaluar"/"cargar"/"registrar" según el que llame).
    Si el log no se puede escribir, no rompe la carga.
    """
    ev = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        "path": os.path.abspath(path_skill_md),
        "skill": os.path.basename(
            os.path.dirname(os.path.abspath(path_skill_md))),
        "tier": veredicto.get("tier"),
        "tier_nombre": veredicto.get("tier_nombre"),
        "decision": veredicto.get("decision"),
        "firmante": veredicto.get("firmante"),
        "con_scripts": bool(veredicto.get("con_scripts", False)),
        "motivos": veredicto.get("motivos", []),
        "punto": punto or "evaluar",
    }
    try:
        ruta = ruta_log_cargas()
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return ev


def historial_cargas(path_skill_md=None):
    """Lista de eventos del log (del más viejo al más nuevo)."""
    ruta = ruta_log_cargas()
    if not os.path.exists(ruta):
        return []
    eventos = []
    with open(ruta, encoding="utf-8", errors="ignore") as f:
        for linea in f:
            try:
                ev = json.loads(linea)
            except Exception:
                continue
            if path_skill_md is None or ev.get("path") == \
                    os.path.abspath(path_skill_md):
                eventos.append(ev)
    return eventos


def _huella(dir_skill):
    """Huella de la skill en disco para cachear el veredicto: nombre y
    tamaño/hora de todos los archivos relevantes de forma ordenada."""
    huellas = []
    for base, _, ficheros in os.walk(dir_skill):
        for fn in sorted(ficheros):
            full = os.path.join(base, fn)
            try:
                st = os.stat(full)
            except OSError:
                continue
            rel = os.path.relpath(full, dir_skill)
            huellas.append((rel, st.st_size, int(st.st_mtime)))
    return tuple(huellas)


def evaluar_cacheado(path_skill_md, aprobacion_explicita=False):
    """evaluar() con cache por huella de disco: misma skill con los
    mismos bytes → mismo veredicto, sin reescanear.

    Si la skill cambia en disco, la huella cambia y se reevalúa.
    La aprobación explícita no se cachea: es caso por caso, siempre
    se vuelve a evaluar."""
    if not aprobacion_explicita:
        clave = (os.path.abspath(path_skill_md),
                 _huella(os.path.dirname(os.path.abspath(path_skill_md))))
        if clave in _CACHE:
            return _CACHE[clave]
        veredicto = evaluar(path_skill_md, aprobacion_explicita)
        _CACHE[clave] = veredicto
        return veredicto
    return evaluar(path_skill_md, aprobacion_explicita)
