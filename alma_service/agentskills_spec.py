"""Capa fina del formato abierto Agent Skills (agentskills.io).

Fase 0 de ALMA ya hablaba este formato; acá se implementa la validación
de la spec + import/export, sin tocar el handoff gate ni la gobernanza.

Spec (documentada en agentskills.io/specification):
- Una skill = directorio con SKILL.md obligatorio (frontmatter YAML +
  cuerpo Markdown).
- `name` requerido: <=64 chars, kebab-case ^[a-z0-9]+(-[a-z0-9]+)*$,
  debe coincidir con el nombre del directorio.
- `description` requerida: <=1024 chars (qué hace + cuándo usarla).
- Opcionales: `license`, `compatibility` (<=500), `metadata` (mapa
  string->string), `allowed-tools` (experimental, soporte variable).
- Directorios opcionales: `scripts/`, `references/`, `assets/`.
- Progressive disclosure en 3 niveles (ya implementado en skills.py).

Ambigüedades de la spec resueltas así (documentado, no adivinado):
- Los límites de longitud se miden en caracteres (len), no en bytes.
- `name == dirname` es comparación exacta (el kebab-case ya es
  minúsculas, así que no hay caso borde).
- Campos top-level desconocidos se IGNORAN (la spec no los prohíbe y
  el formato evoluciona sobre main sin versionado formal).
- `metadata` debe ser un dict; valores escalares se convierten con
  str() (ej: `version: 2` -> "2"). No-dict corta con error.
- `allowed-tools` se acepta tal cual (string o lista); no se ejecuta
  ni se valida contra nada: es experimental en la spec misma.
- `scripts/` y `assets/` son passthrough: se listan, JAMÁS se
  ejecutan (doctrina ClawHavoc: contenido de terceros no se corre).

Formato ECC (Patrón 1 del estudio ECC, 2026-10-02, ADOPTAR):
- El cuerpo puede traer secciones fijas con encabezado `## `:
  When to Use, When NOT to Use, Workflow, Anti-Patterns,
  Related Skills. Se parsean a `Skill.ecc_secciones` (vista paralela;
  `cuerpo` conserva el texto completo) y el exportador las emite en
  orden canónico. `metadata.origin` se acepta como primer campo de
  provenance (autodeclarado: útil como etiqueta, NO como prueba —
  ver ClawHavoc).
- Presupuesto de contexto: la description vive en el índice siempre;
  >30 palabras = WARNING (ECC context-budget), nunca fallo.
- `When NOT to Use` ausente = WARNING (vacuna anti-bloat sugerida,
  no exigida).

Ambigüedades del formato ECC resueltas así (documentado):
- Solo se reconocen encabezados `## ` (exactamente dos #, con
  espacio). `#` y `###` son contenido común.
- El nombre de sección se normaliza (minúsculas, guiones/espacios
  colapsados): "when NOT to use", "When-Not-To-Use", etc. valen.
- La "zona de secciones" arranca en el primer encabezado ECC
  reconocido; lo anterior es la intro. Encabezados `## ` NO
  reconocidos dentro de la zona se conservan verbatim como contenido
  de la sección en curso: nunca se pierde texto.
- Secciones duplicadas se concatenan con línea en blanco.
- En la exportación, las secciones explícitas de
  `skill.ecc_secciones` tienen prioridad sobre las detectadas en el
  cuerpo; la emisión es siempre en orden canónico (punto fijo:
  exportar->cargar->exportar es estable).
- Palabras = len(texto.split()). El WARNING de 30 palabras no
  invalida: la spec permite 1024 caracteres y la spec manda.
- `check_skill_format` acepta path a SKILL.md o el texto directo
  (si es archivo existente, lo lee); entrada inválida corta con
  SkillInvalida (fail-closed, como el resto del módulo).
"""

import json
import os
import re

import yaml

from .skills import Skill, SkillInvalida, SCHEMA_VERSION

RE_NOMBRE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NOMBRE = 64
MAX_DESCRIPCION = 1024
MAX_COMPATIBILITY = 500

# Nombres de directorio aceptados para referencias (ALMA usaba el
# español; la spec usa el inglés). Se aceptan ambos, sin romper nada.
DIRS_REFERENCIA = ("references", "referencias")
DIR_SCRIPTS = "scripts"
DIR_ASSETS = "assets"

# --- Formato ECC (Patrón 1, ADOPTAR) ---------------------------------
# Secciones fijas del cuerpo, en orden canónico de emisión:
# (clave_normalizada, encabezado_canónico).
SECCIONES_ECC = (
    ("when_to_use", "When to Use"),
    ("when_not_to_use", "When NOT to Use"),
    ("workflow", "Workflow"),
    ("anti_patterns", "Anti-Patterns"),
    ("related_skills", "Related Skills"),
)
# La description vive en el índice (contexto siempre): más de esto en
# palabras = WARNING de bloat (ECC context-budget), nunca fallo.
MAX_PALABRAS_DESCRIPCION = 30

RE_ENCABEZADO_ECC = re.compile(r"^##\s+(.+?)\s*$")


def _normalizar_titulo_seccion(titulo):
    t = re.sub(r"[-_]+", " ", titulo.strip().lower())
    return re.sub(r"\s+", " ", t)


_MAPA_SECCIONES_ECC = {
    _normalizar_titulo_seccion(titulo): clave
    for clave, titulo in SECCIONES_ECC
}


def dividir_secciones_ecc(cuerpo):
    """Divide el cuerpo en (intro, secciones).

    intro: texto antes del primer encabezado `## ` reconocido como
    sección ECC (puede ser "").
    secciones: dict {clave: texto} con las 5 secciones ECC
    encontradas, en orden canónico de SECCIONES_ECC.
    Reglas (documentadas en el docstring del módulo): solo `## `,
    nombres normalizados, encabezados desconocidos dentro de la zona
    se conservan verbatim, duplicadas se concatenan.
    """
    intro_lineas = []
    secciones = {}
    actual = None  # clave de la sección en curso (None = zona intro)
    for linea in cuerpo.splitlines():
        m = RE_ENCABEZADO_ECC.match(linea)
        if m:
            clave = _MAPA_SECCIONES_ECC.get(
                _normalizar_titulo_seccion(m.group(1)))
            if clave is not None:
                actual = clave
                secciones.setdefault(clave, [])
                continue
            # Encabezado `## ` no reconocido: se conserva verbatim.
            # Dentro de la zona de secciones pertenece a la sección
            # en curso; antes de la primera sección ECC es intro.
        if actual is None:
            intro_lineas.append(linea)
        else:
            secciones[actual].append(linea)
    # Orden canónico + concatenar duplicadas con línea en blanco.
    ordenadas = {}
    for clave, _titulo in SECCIONES_ECC:
        if clave in secciones:
            texto = "\n".join(secciones[clave]).strip()
            if texto:
                ordenadas[clave] = texto
    return "\n".join(intro_lineas).strip(), ordenadas


def _emitir_cuerpo_con_secciones(intro, secciones):
    """Cuerpo canónico: intro + secciones ECC en orden fijo.

    Solo emite secciones no vacías. Si no hay secciones, el llamante
    usa el cuerpo verbatim (comportamiento anterior intacto).
    """
    partes = []
    if intro and intro.strip():
        partes.append(intro.strip())
    for clave, titulo in SECCIONES_ECC:
        contenido = (secciones or {}).get(clave)
        if contenido and contenido.strip():
            partes.append(f"## {titulo}\n\n{contenido.strip()}")
    return "\n\n".join(partes)


def _palabras(texto):
    return len(texto.split())


def check_skill_format(entrada):
    """Chequea el formato ECC de un SKILL.md sin conectarlo a nada.

    entrada: path a un SKILL.md o el texto del SKILL.md directo.
    Retorna lista de findings: dicts {seccion, severidad, mensaje}.
    Hoy solo emite "warning" (la spec manda: nada de esto invalida);
    la estructura admite severidades futuras. Pensada para que el
    gate la use después; NO está conectada al gate ni al loader.
    Fail-closed: frontmatter inválido o sin description ->
    SkillInvalida (igual que el resto del módulo).
    """
    if isinstance(entrada, str) and os.path.isfile(entrada):
        with open(entrada, "r", encoding="utf-8") as f:
            texto = f.read()
    elif isinstance(entrada, str):
        texto = entrada
    else:
        raise SkillInvalida(
            "check_skill_format espera path o texto, no "
            f"{type(entrada).__name__}"
        )
    fm, cuerpo = parse_frontmatter_yaml(texto)
    descripcion = fm.get("description")
    if not descripcion or not isinstance(descripcion, str):
        raise SkillInvalida("frontmatter sin 'description' requerida")
    descripcion = descripcion.strip()
    findings = []
    n_palabras = _palabras(descripcion)
    if n_palabras > MAX_PALABRAS_DESCRIPCION:
        findings.append({
            "seccion": "description",
            "severidad": "warning",
            "mensaje": (
                f"description con {n_palabras} palabras "
                f"(>{MAX_PALABRAS_DESCRIPCION}): vive en el índice en "
                "contexto siempre; cada palabra extra es impuesto por "
                "turno (ECC context-budget). No invalida: la spec "
                "permite 1024 caracteres."
            ),
        })
    _intro, secciones = dividir_secciones_ecc(cuerpo)
    if "when_not_to_use" not in secciones:
        findings.append({
            "seccion": "when_not_to_use",
            "severidad": "warning",
            "mensaje": (
                "falta la sección 'When NOT to Use': es la vacuna "
                "anti-bloat del formato ECC (declara cuándo NO usar "
                "la skill). Se sugiere, no se exige."
            ),
        })
    return findings


def parse_frontmatter_yaml(texto):
    """Parser YAML real del frontmatter. Retorna (dict, cuerpo).

    Fail-closed: sin '---' inicial, sin cierre, bloque vacío, YAML
    inválido o resultado no-dict -> SkillInvalida con motivo claro.
    A diferencia de parse_frontmatter (plano, schema-agnóstico), este
    preserva mapas anidados como `metadata:`.
    """
    if not texto.startswith("---"):
        raise SkillInvalida("falta frontmatter '---' inicial")
    partes = texto.split("---", 2)
    if len(partes) < 3 or not partes[1].strip():
        raise SkillInvalida("frontmatter vacío o sin cierre '---'")
    try:
        fm = yaml.safe_load(partes[1])
    except yaml.YAMLError as e:
        raise SkillInvalida(f"frontmatter YAML inválido: {e}")
    if fm is None:
        raise SkillInvalida("frontmatter vacío")
    if not isinstance(fm, dict):
        raise SkillInvalida(
            "frontmatter debe ser un mapa clave: valor, no "
            f"{type(fm).__name__}"
        )
    return fm, partes[2].strip()


def _validar_metadata(valor):
    if valor is None:
        return {}
    if not isinstance(valor, dict):
        raise SkillInvalida(
            "metadata debe ser un mapa string->string, no "
            f"{type(valor).__name__}"
        )
    out = {}
    for k, v in valor.items():
        out[str(k)] = v if isinstance(v, str) else str(v)
    return out


def validar_spec(fm, nombre_dir):
    """Valida un frontmatter ya parseado contra la spec Agent Skills.

    Retorna dict normalizado con: name, description, license,
    compatibility, metadata (dict), allowed_tools. Campos desconocidos
    se ignoran. Fail-closed: cualquier violación -> SkillInvalida con
    el motivo exacto.
    """
    if not isinstance(fm, dict):
        raise SkillInvalida("frontmatter debe ser un mapa")
    nombre = fm.get("name")
    if not nombre or not isinstance(nombre, str):
        raise SkillInvalida("frontmatter sin 'name' requerido")
    nombre = nombre.strip()
    if len(nombre) > MAX_NOMBRE:
        raise SkillInvalida(
            f"name excede {MAX_NOMBRE} caracteres ({len(nombre)})"
        )
    if not RE_NOMBRE.match(nombre):
        raise SkillInvalida(
            f"name no es kebab-case válido: {nombre!r} "
            "(solo minúsculas, dígitos y guiones simples)"
        )
    if nombre != nombre_dir:
        raise SkillInvalida(
            f"name {nombre!r} no coincide con el directorio "
            f"{nombre_dir!r} (la spec exige igualdad)"
        )
    descripcion = fm.get("description")
    if not descripcion or not isinstance(descripcion, str):
        raise SkillInvalida("frontmatter sin 'description' requerida")
    descripcion = descripcion.strip()
    if len(descripcion) > MAX_DESCRIPCION:
        raise SkillInvalida(
            f"description excede {MAX_DESCRIPCION} caracteres "
            f"({len(descripcion)})"
        )
    compat = fm.get("compatibility")
    if compat is not None:
        compat = str(compat)
        if len(compat) > MAX_COMPATIBILITY:
            raise SkillInvalida(
                f"compatibility excede {MAX_COMPATIBILITY} caracteres "
                f"({len(compat)})"
            )
    lic = fm.get("license")
    if lic is not None:
        lic = str(lic)
    allowed = fm.get("allowed-tools")
    if allowed is not None and not isinstance(allowed, (str, list)):
        raise SkillInvalida("allowed-tools debe ser string o lista")
    return {
        "name": nombre,
        "description": descripcion,
        "license": lic,
        "compatibility": compat,
        "metadata": _validar_metadata(fm.get("metadata")),
        "allowed_tools": allowed,
    }


def _listar_dir(base_dir, *nombres):
    """Lista archivos (relativos) dentro de los directorios dados que
    existan bajo base_dir. Passthrough: solo lista, nunca ejecuta."""
    encontrados = []
    for n in nombres:
        d = os.path.join(base_dir, n)
        if not os.path.isdir(d):
            continue
        for raiz, _dirs, archivos in os.walk(d):
            for a in sorted(archivos):
                encontrados.append(
                    os.path.relpath(os.path.join(raiz, a), base_dir)
                )
    return sorted(set(encontrados))


def cargar_skill_spec(path_skill_md):
    """Carga un SKILL.md validándolo contra la spec Agent Skills.

    Usa el parser YAML real (soporta `metadata:` anidado), valida
    name/description/límites/igualdad con el directorio, acepta
    `references/` además del `referencias/` histórico, y lista
    `scripts/` y `assets/` como passthrough (sin ejecutar).
    Retorna Skill con los atributos extendidos (license, compatibility,
    metadata, allowed_tools, scripts, assets, archivos_referencia).
    """
    path = os.path.abspath(path_skill_md)
    if os.path.basename(path) != "SKILL.md":
        raise SkillInvalida(f"no es un SKILL.md: {path}")
    base_dir = os.path.dirname(path)
    nombre_dir = os.path.basename(base_dir)
    categoria = os.path.basename(os.path.dirname(base_dir))
    with open(path, "r", encoding="utf-8") as f:
        texto = f.read()
    fm, cuerpo = parse_frontmatter_yaml(texto)
    spec = validar_spec(fm, nombre_dir)
    if not cuerpo:
        raise SkillInvalida(f"cuerpo vacío: {path}")
    refs_fm = [l.strip() for l in str(fm.get("referencias", "")).split(",")
               if l.strip()] if "referencias" in fm else []
    # Formato ECC: las secciones del cuerpo se parsean a la vista
    # `ecc_secciones`; `cuerpo` conserva el texto completo (los
    # consumidores como proveedor_real lo esperan íntegro).
    _intro, secciones_ecc = dividir_secciones_ecc(cuerpo)
    return Skill(
        path=path, categoria=categoria, nombre=spec["name"],
        descripcion=spec["description"], cuerpo=cuerpo,
        created_by=str(fm.get("created_by", "agent")),
        version=fm.get("version", 1), estado=str(fm.get("estado", "active")),
        referencias=refs_fm,
        archivos_referencia=_listar_dir(base_dir, *DIRS_REFERENCIA),
        license=spec["license"], compatibility=spec["compatibility"],
        metadata=spec["metadata"], allowed_tools=spec["allowed_tools"],
        scripts=_listar_dir(base_dir, DIR_SCRIPTS),
        assets=_listar_dir(base_dir, DIR_ASSETS),
        ecc_secciones=secciones_ecc,
    )


def _linaje_a_metadata(versionador, skill_path):
    """Lineage de versiones.py -> metadata de exportación.

    Retorna {} si no hay versionador o no hay lineage asentado.
    """
    if versionador is None:
        return {}
    try:
        cadena = versionador.linaje(skill_path)
    except Exception:
        return {}
    if not cadena:
        return {}
    ultimo = cadena[-1]
    return {
        "alma_split": str(ultimo.get("split_nombre") or ""),
        "alma_delta": str(ultimo.get("delta_down")),
        "alma_fecha": str(ultimo.get("ts")),
    }


def _yaml_esc_unilinea(v):
    """Escalar YAML seguro en una línea: entrecomilla si el valor tiene
    caracteres que romperían el frontmatter (ej: 'clave: valor' con ': ')."""
    s = str(v)
    especiales = (": ", " #", "\"", "'", "[", "]", "{", "}", ",",
                  "&", "*", "?", "|", "<", ">", "=", "!", "%", "@", "`")
    if "\n" in s or s != s.strip() or s[:1] in ("-", "?", ":"):
        necesita = True
    else:
        necesita = any(c in s for c in especiales)
    if necesita:
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s}"'
    return s


def exportar_skill(skill, dir_destino, versionador=None):
    """Exporta una skill de ALMA a SKILL.md válido según la spec.

    Mapeo:
    - name, description: directo (se validan antes de escribir).
    - version/created_by -> metadata: {version, author}.
    - lineage (versiones.py) -> metadata: {alma_split, alma_delta,
      alma_fecha} (solo si hay lineage asentado).
    - estado NO se exporta (lifecycle interno de ALMA).
    - referencias/ -> references/ (nombre de la spec).
    - scripts/ y assets/ se copian como passthrough (no se ejecutan).
    - Formato ECC: las secciones del cuerpo (When to Use, When NOT
      to Use, Workflow, Anti-Patterns, Related Skills) se emiten en
      orden canónico; punto fijo exportar->cargar->exportar.

    Escribe dir_destino/<name>/SKILL.md (+ subdirs) y retorna
    (dir_skill, texto_skill_md). Fail-closed: si name/description no
    validan, no escribe nada.
    """
    # Validar ANTES de escribir (fail-closed)
    fm_check = {"name": skill.nombre, "description": skill.descripcion}
    validar_spec(fm_check, skill.nombre)
    meta = {
        "version": str(getattr(skill, "version", 1)),
        "author": str(getattr(skill, "created_by", "agent")),
    }
    meta.update(_linaje_a_metadata(versionador, skill.path))
    meta.update(getattr(skill, "metadata", None) or {})
    lineas = ["---", f"name: {skill.nombre}"]
    # description puede ser multilínea: usar bloque literal si hace falta
    desc = skill.descripcion
    if "\n" in desc:
        lineas.append("description: |")
        lineas.extend("  " + l for l in desc.splitlines())
    else:
        lineas.append(f"description: {_yaml_esc_unilinea(desc)}")
    if getattr(skill, "license", None):
        lineas.append(f"license: {skill.license}")
    if getattr(skill, "compatibility", None):
        lineas.append(f"compatibility: {skill.compatibility}")
    if getattr(skill, "allowed_tools", None) is not None:
        at = skill.allowed_tools
        if isinstance(at, list):
            lineas.append("allowed-tools: ["
                          + ", ".join(str(x) for x in at) + "]")
        else:
            lineas.append(f"allowed-tools: {at}")
    lineas.append("metadata:")
    for k in sorted(meta):
        lineas.append(f"  {k}: {_yaml_esc_unilinea(meta[k])}")
    lineas.append("---")
    lineas.append("")
    # Formato ECC: si hay secciones (detectadas en el cuerpo o
    # explícitas en skill.ecc_secciones, que tienen prioridad), el
    # cuerpo se emite canónico: intro + secciones en orden fijo.
    # Sin secciones, el cuerpo sale verbatim (cero cambio).
    _intro_det, detectadas = dividir_secciones_ecc(skill.cuerpo)
    secciones = dict(detectadas)
    secciones.update(getattr(skill, "ecc_secciones", None) or {})
    if secciones:
        cuerpo_md = _emitir_cuerpo_con_secciones(_intro_det, secciones)
    else:
        cuerpo_md = skill.cuerpo
    texto = "\n".join(lineas) + cuerpo_md.rstrip() + "\n"
    # Re-validar lo generado (la exportación debe pasar su propia puerta)
    fm_gen, _cuerpo_gen = parse_frontmatter_yaml(texto)
    validar_spec(fm_gen, skill.nombre)

    dir_skill = os.path.join(os.path.abspath(dir_destino), skill.nombre)
    os.makedirs(dir_skill, exist_ok=True)
    with open(os.path.join(dir_skill, "SKILL.md"), "w",
              encoding="utf-8") as f:
        f.write(texto)
    # referencias/ -> references/ (copia passthrough)
    import shutil
    src_base = os.path.dirname(os.path.abspath(skill.path))
    for nombre_src in ("referencias", "references"):
        src = os.path.join(src_base, nombre_src)
        if os.path.isdir(src):
            dst = os.path.join(dir_skill, "references")
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            break
    for nombre_src in (DIR_SCRIPTS, DIR_ASSETS):
        src = os.path.join(src_base, nombre_src)
        if os.path.isdir(src):
            dst = os.path.join(dir_skill, nombre_src)
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
    return dir_skill, texto


def skill_a_metadata_json(skill):
    """metadata de una skill -> JSON para la columna metadata_json."""
    return json.dumps(getattr(skill, "metadata", None) or {},
                      ensure_ascii=False, sort_keys=True)
