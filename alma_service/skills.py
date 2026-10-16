"""Skills en formato AgentSkills — fase 0.

Diseño §1.1.1: las skills viven como `skills/<categoria>/<nombre>/SKILL.md`
con frontmatter YAML (name, description; opcionales: created_by, version,
estado). Progressive disclosure: al inicio solo se precargan
nombre+descripción (~30-50 tokens por skill); el cuerpo se carga bajo
demanda desde el archivo (fuente de verdad en disco).

El índice SQLite guarda metadatos + telemetría (use_count, last_used_at,
estado) para el Curator y el umbral endurecido. Presupuesto DURO de
contexto: la suma de tokens del índice (nombre+descripción) no puede
superar el tope; registrar por encima corta con PresupuestoExcedido
(anti-bloat: el estudio midió 75 skills = 38.8% del prompt).
"""

import os
import sqlite3
import time

SCHEMA_VERSION = "skill-index-v2"
# v2 agrega columnas license, compatibility, metadata_json (capa fina del
# formato abierto Agent Skills). La migración es automática y aditiva:
# ALTER TABLE solo si la columna falta; filas viejas quedan legibles.


class SkillInvalida(ValueError):
    pass


class PresupuestoExcedido(Exception):
    def __init__(self, tope, en_uso, intento):
        super().__init__(
            f"presupuesto de índice excedido: tope {tope} tokens, "
            f"en uso {en_uso}, intento +{intento}"
        )
        self.tope = tope
        self.en_uso = en_uso
        self.intento = intento


def parse_frontmatter(texto):
    """Parser mínimo de frontmatter `---\\nclave: valor\\n---`.

    Solo soporta pares simples clave: valor (suficiente para el formato
    AgentSkills que usamos). Retorna (dict, cuerpo)."""
    if not texto.startswith("---"):
        raise SkillInvalida("falta frontmatter '---' inicial")
    partes = texto.split("---", 2)
    if len(partes) < 3 or not partes[1].strip():
        raise SkillInvalida("frontmatter vacío o sin cierre '---'")
    fm = {}
    for i, linea in enumerate(partes[1].splitlines(), 1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if ":" not in linea:
            raise SkillInvalida(f"línea {i} del frontmatter sin ':': {linea!r}")
        k, v = linea.split(":", 1)
        k = k.strip()
        if not k:
            raise SkillInvalida(f"línea {i} del frontmatter sin clave")
        v = v.strip()
        if (len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"')):
            v = v[1:-1]
        fm[k] = v
    return fm, partes[2].strip()


def estimar_tokens_skill(nombre, descripcion):
    """Tokens del índice por skill: solo nombre+descripción (el cuerpo se
    carga bajo demanda). Heurística chars/4."""
    return max(1, (len(nombre) + len(descripcion)) // 4)


class Skill:
    """Una skill cargada: metadatos + cuerpo bajo demanda."""

    def __init__(self, path, categoria, nombre, descripcion, cuerpo,
                 created_by="agent", version=1, estado="active",
                 referencias=(), archivos_referencia=(),
                 license=None, compatibility=None, metadata=None,
                 allowed_tools=None, scripts=(), assets=(),
                 ecc_secciones=None):
        self.path = path
        self.categoria = categoria
        self.nombre = nombre
        self.descripcion = descripcion
        self.cuerpo = cuerpo
        self.created_by = created_by
        self.version = int(version)
        self.estado = estado
        self.referencias = list(referencias)
        # Capa fina Agent Skills (opcionales, default None/vacío: lo viejo
        # sigue funcionando igual).
        self.archivos_referencia = list(archivos_referencia)
        self.license = license
        self.compatibility = compatibility
        self.metadata = dict(metadata) if metadata else {}
        self.allowed_tools = allowed_tools
        self.scripts = list(scripts)
        self.assets = list(assets)
        # Secciones de formato ECC (Patrón 1 del estudio ECC, 2026-10-02):
        # vista parseada del cuerpo (When to Use, When NOT to Use,
        # Workflow, Anti-Patterns, Related Skills). `cuerpo` SIEMPRE
        # conserva el texto completo (proveedor_real lo inyecta al
        # prompt); esto es una vista paralela, no un reemplazo.
        self.ecc_secciones = dict(ecc_secciones) if ecc_secciones else {}

    @property
    def tokens_indice(self):
        return estimar_tokens_skill(self.nombre, self.descripcion)

    def __repr__(self):
        return (f"Skill({self.categoria}/{self.nombre} v{self.version} "
                f"[{self.estado}] by={self.created_by})")


def cargar_skill(path_skill_md):
    """Lee y valida un SKILL.md. Retorna Skill."""
    path = os.path.abspath(path_skill_md)
    if os.path.basename(path) != "SKILL.md":
        raise SkillInvalida(f"no es un SKILL.md: {path}")
    nombre_dir = os.path.basename(os.path.dirname(path))
    categoria = os.path.basename(
        os.path.dirname(os.path.dirname(path)))
    with open(path, "r", encoding="utf-8") as f:
        texto = f.read()
    fm, cuerpo = parse_frontmatter(texto)
    for req in ("name", "description"):
        if req not in fm or not fm[req]:
            raise SkillInvalida(f"frontmatter sin '{req}' requerido: {path}")
    if not cuerpo:
        raise SkillInvalida(f"cuerpo vacío: {path}")
    refs = [l.strip() for l in fm.get("referencias", "").split(",")
            if l.strip()] if "referencias" in fm else []
    return Skill(
        path=path, categoria=categoria, nombre=fm["name"],
        descripcion=fm["description"], cuerpo=cuerpo,
        created_by=fm.get("created_by", "agent"),
        version=fm.get("version", 1), estado=fm.get("estado", "active"),
        referencias=refs,
    )


class SkillIndex:
    """Índice SQLite de skills: metadatos + telemetría de uso.

    El cuerpo vive en disco (fuente de verdad); acá solo lo indexado.
    `listar()` retorna filas livianas (nombre+descripción): progressive
    disclosure enforced por construcción.
    """

    def __init__(self, path):
        self.path = path
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS skills (
                   path TEXT PRIMARY KEY,
                   name TEXT NOT NULL,
                   description TEXT NOT NULL,
                   categoria TEXT NOT NULL,
                   created_by TEXT NOT NULL DEFAULT 'agent',
                   estado TEXT NOT NULL DEFAULT 'active',
                   version INTEGER NOT NULL DEFAULT 1,
                   use_count INTEGER NOT NULL DEFAULT 0,
                   last_used_at REAL,
                   created_at REAL NOT NULL,
                   tokens_idx INTEGER NOT NULL,
                   schema TEXT NOT NULL
               )"""
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_skills_estado"
            " ON skills(estado)"
        )
        self._migrar_v2()
        self._db.commit()

    def _migrar_v2(self):
        """Migración aditiva v1 -> v2 (capa fina Agent Skills).

        Agrega license, compatibility, metadata_json solo si faltan.
        Idempotente y segura sobre DBs existentes: no toca filas ni
        otras columnas.
        """
        cols = {r[1] for r in
                self._db.execute("PRAGMA table_info(skills)").fetchall()}
        if "license" not in cols:
            self._db.execute("ALTER TABLE skills ADD COLUMN"
                             " license TEXT")
        if "compatibility" not in cols:
            self._db.execute("ALTER TABLE skills ADD COLUMN"
                             " compatibility TEXT")
        if "metadata_json" not in cols:
            self._db.execute("ALTER TABLE skills ADD COLUMN"
                             " metadata_json TEXT NOT NULL DEFAULT '{}'")

    def registrar(self, skill, presupuesto_tokens, aprobacion_explicita=False):
        """Registra una skill si entra en el presupuesto duro. Si no entra,
        corta con PresupuestoExcedido (el llamante corre el Curator).

        Si el filtro de confianza está activo, la skill pasa antes por
        el manifiesto (tiers 0/1/2): tier 2 con scripts sin firma no
        entra sin aprobación explícita; la `decision` queda registrada
        en el log de cargas (punto="registrar").
        """
        if self._filtro_confianza_activo():
            from . import manifiesto as M
            aprob = aprobacion_explicita or os.environ.get(
                "ALMA_APROBACION_CARGA") == "1"
            veredicto = M.evaluar_cacheado(skill.path, aprob)
            M.registrar_carga(skill.path, veredicto, punto="registrar")
            if veredicto["decision"] == "rechazada":
                raise M.SkillRechazada(
                    "skill rechazada (fail closed): "
                    + "; ".join(veredicto["motivos"]))
            if veredicto["decision"] == "bloqueada":
                raise M.SkillBloqueada(
                    "skill bloqueada: tier 2 con scripts requiere aprobación "
                    "explícita: " + "; ".join(veredicto["motivos"]))
            skill.nivel_confianza = veredicto["tier"]
            skill.veredicto = veredicto
        en_uso = self.tokens_indice()
        if en_uso + skill.tokens_indice > presupuesto_tokens:
            raise PresupuestoExcedido(presupuesto_tokens, en_uso,
                                      skill.tokens_indice)
        ahora = time.time()
        import json as _json
        self._db.execute(
            """INSERT INTO skills
                   (path, name, description, categoria, created_by, estado,
                    version, use_count, last_used_at, created_at,
                    tokens_idx, schema, license, compatibility,
                    metadata_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(path) DO UPDATE SET
                   name=excluded.name, description=excluded.description,
                   categoria=excluded.categoria, estado=excluded.estado,
                   version=excluded.version, tokens_idx=excluded.tokens_idx,
                   license=excluded.license,
                   compatibility=excluded.compatibility,
                   metadata_json=excluded.metadata_json""",
            (skill.path, skill.nombre, skill.descripcion, skill.categoria,
             skill.created_by, skill.estado, skill.version, 0, None, ahora,
             skill.tokens_indice, SCHEMA_VERSION,
             getattr(skill, "license", None),
             getattr(skill, "compatibility", None),
             _json.dumps(getattr(skill, "metadata", None) or {},
                         ensure_ascii=False, sort_keys=True)),
        )
        self._db.commit()

    def tokens_indice(self, solo_estado="active"):
        cur = self._db.execute(
            "SELECT COALESCE(SUM(tokens_idx),0) t FROM skills WHERE estado=?",
            (solo_estado,),
        )
        return cur.fetchone()["t"]

    def listar(self, estado="active"):
        """Filas livianas: nombre+descripción (+telemetría). Sin cuerpo."""
        import json as _json
        cur = self._db.execute(
            "SELECT path, name, description, categoria, created_by, estado,"
            " version, use_count, last_used_at, tokens_idx, license,"
            " compatibility, metadata_json FROM skills"
            " WHERE estado=? ORDER BY use_count DESC, last_used_at DESC",
            (estado,),
        )
        filas = []
        for f in cur.fetchall():
            d = dict(f)
            try:
                d["metadata"] = _json.loads(d.pop("metadata_json") or "{}")
            except Exception:
                d["metadata"] = {}
            filas.append(d)
        return filas

    def _filtro_confianza_activo(self):
        return os.environ.get("ALMA_FILTRO_SKILLS", "1") != "0"

    def cargar_completa(self, path):
        """Carga el cuerpo desde disco bajo demanda (progressive disclosure).

        Si el filtro de confianza está activo, la skill pasa por el
        manifiesto firmado (tiers 0/1/2) antes de entregar el cuerpo, y
        el veredicto queda registrado. Tier 2 con scripts bloquea acá
        con SkillBloqueada salvo que la carga venga con aprobación
        explícita (atributo `_aprobacion_explicita` por crear el
        índice en el mismo proceso, o env ALMA_APROBACION_CARGA=1).
        """
        fila = self._db.execute(
            "SELECT path FROM skills WHERE path=?", (path,)
        ).fetchone()
        if not fila:
            raise KeyError(f"skill no indexada: {path}")
        full = fila["path"]
        if not self._filtro_confianza_activo():
            return cargar_skill(full)
        from . import manifiesto as M
        aprob = getattr(self, "_aprobacion_explicita", False) or \
            os.environ.get("ALMA_APROBACION_CARGA") == "1"
        veredicto = M.evaluar_cacheado(full, aprob)
        M.registrar_carga(full, veredicto, punto="cargar")
        if veredicto["decision"] == "rechazada":
            raise M.SkillRechazada(
                "skill rechazada (fail closed): "
                + "; ".join(veredicto["motivos"]))
        if veredicto["decision"] == "bloqueada":
            raise M.SkillBloqueada(
                "skill bloqueada: tier 2 con scripts requiere aprobación "
                "explícita: " + "; ".join(veredicto["motivos"]))
        skill = cargar_skill(full)
        skill.nivel_confianza = veredicto["tier"]
        skill.veredicto = veredicto
        return skill

    def marcar_uso(self, path, ahora=None):
        ahora = ahora if ahora is not None else time.time()
        self._db.execute(
            "UPDATE skills SET use_count = use_count + 1,"
            " last_used_at = ? WHERE path = ?",
            (ahora, path),
        )
        self._db.commit()

    def transicionar(self, path, nuevo_estado):
        if nuevo_estado not in ("active", "stale", "archived"):
            raise ValueError(f"estado inválido: {nuevo_estado}")
        self._db.execute(
            "UPDATE skills SET estado=? WHERE path=?", (nuevo_estado, path)
        )
        self._db.commit()

    def tiene_skill(self, categoria, nombre):
        fila = self._db.execute(
            "SELECT 1 FROM skills WHERE categoria=? AND name=?"
            " AND estado='active' LIMIT 1",
            (categoria, nombre),
        ).fetchone()
        return fila is not None

    def antiguedad_uso(self, path, ahora=None):
        """Días desde el último uso (o desde la creación si nunca se usó).
        None si la skill no existe."""
        ahora = ahora if ahora is not None else time.time()
        fila = self._db.execute(
            "SELECT last_used_at, created_at FROM skills WHERE path=?",
            (path,),
        ).fetchone()
        if not fila:
            return None
        ref = fila["last_used_at"] or fila["created_at"]
        return max(0.0, (ahora - ref) / 86400.0)

    def close(self):
        self._db.close()
