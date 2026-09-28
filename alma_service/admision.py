"""Pipeline de admisión de skills por etapas — de OpenSpace (HKUDS).

OpenSpace: Trigger → Evidence → Decision → Admission → staging →
validation → commit, con firma humana obligatoria en la decisión y
cuarentena: lo admitido nace provisional (upload trust-gated).

Etapas acá (terminales marcadas con *):
    propuesta → evidencia → decision → staging → validacion_ok
                                             ↘ rechazada* / validacion_fallida*
    validacion_ok → committed*

- `proponer`: crea el caso (no valida nada todavía).
- `adjuntar_evidencia`: Trigger→Evidencia. La evidencia cita
  observaciones concretas (qué ejecución/lectura motiva la skill).
- `decidir`: gate HUMANO (mismo patrón que revision.py: nada se aplica
  solo). aprobar=True → staging; False → rechazada*.
- `validar`: checks DETERMINISTAS (US$0): el SKILL.md parsea
  (cargar_skill), nombre+descripción válidos, nombre único, tokens bajo
  tope opcional. No hay LLM en ningún punto.
- `commit`: escribe SKILL.md, registra en el índice, nace en confianza
  PROVISIONAL y abre versión CAPTURED en el DAG. Cada transición puede
  asentarse en el ledger del Curator (callable opcional).

El trust nunca se hereda: hasta una skill aprobada por humano nace
provisional y se gana `trusted` con uso (confianza.py).
"""

import json
import os
import re
import sqlite3
import tempfile
import time

from .skills import cargar_skill
from alma_service.politicas import verificar_carga_skill  # Song (g)
from alma_service.aci import (  # Yao (c): reglas ACI como checklist
    resumir, editar_con_guardrails)

ETAPA_PROPUESTA = "propuesta"
ETAPA_EVIDENCIA = "evidencia"
ETAPA_STAGING = "staging"
ETAPA_VALIDACION_OK = "validacion_ok"
ETAPA_VALIDACION_FALLIDA = "validacion_fallida"
ETAPA_RECHAZADA = "rechazada"
ETAPA_COMMITTED = "committed"
TERMINALES = (ETAPA_RECHAZADA, ETAPA_VALIDACION_FALLIDA, ETAPA_COMMITTED)


def _estimar_tokens(texto):
    """Heurística chars/4, igual que skills.py."""
    return max(1, len(texto) // 4)


# Fix A1 (red-team): tripwire determinista sobre el cuerpo en prosa de la
# skill — lo que se inyecta en prompts. Lista de patrones (regex, sin
# LLM), deliberadamente ruidosa y barata: un hit FRENA la admisión
# (fail-closed) y el gate humano decide en última instancia.
#
# Falsos positivos conocidos y aceptados:
# - una skill legítima de "cómo reportar un incidente de seguridad"
#   puede mencionar exfiltración; una skill de red puede traer URLs.
#   Esos casos los destraba el humano en `decidir`, no el check.
PATRONES_HOSTILES = [
    # Exfiltración / envío de datos afuera
    (r"https?://", "url_externa"),
    (r"\bwebhook\b", "webhook"),
    (r"exfiltr", "exfiltracion"),
    (r"\bcurl\b", "curl"),
    (r"env[ií]a(r)?\s+(los\s+)?datos", "envio_de_datos"),
    # Auto-promoción a trusted / manipulación de la confianza
    (r"\btrusted\b", "auto_promocion_trusted"),
    (r"marcar_uso", "manipulacion_confianza"),
    (r"\bgraduar\b", "manipulacion_confianza"),
    # Intentos de deshabilitar el gate de seguridad
    (r"deshabilit", "deshabilitar_gate"),
    (r"\bbypass\b", "bypass"),
    (r"ignorar\s+(la\s+)?(puerta|pol[ií]tica|gate|validaci[oó]n)",
     "ignorar_gate"),
    (r"sin\s+restriccion", "sin_restriccion"),
]

_PATRONES_COMPILADOS = [(re.compile(p, re.IGNORECASE), nombre)
                        for p, nombre in PATRONES_HOSTILES]


def escanear_contenido(texto):
    """Scan determinista del cuerpo de la skill.

    Retorna [(patron_nombre, fragmento)] con los hits. Vacío = limpio.
    Solo mira el cuerpo (tras el frontmatter ---): el frontmatter es
    metadatos, el cuerpo es lo que se inyecta en prompts.
    """
    cuerpo = texto or ""
    # Cortar el frontmatter si existe (--- ... ---).
    lineas = cuerpo.splitlines()
    if lineas and lineas[0].strip() == "---":
        for i, ln in enumerate(lineas[1:], start=1):
            if ln.strip() == "---":
                cuerpo = "\n".join(lineas[i + 1:])
                break
    hits = []
    for rx, nombre in _PATRONES_COMPILADOS:
        m = rx.search(cuerpo)
        if m:
            frag = m.group(0)
            hits.append((nombre, frag[:80]))
    return hits


class PipelineAdmision:
    def __init__(self, db_path, skills_dir, skill_index=None,
                 confianza=None, versionador=None,
                 registrar_ledger=None, tope_tokens=None,
                 presupuesto_tokens=None, puerta=None, procedencia=None):
        self.db_path = db_path
        self.skills_dir = skills_dir
        self.index = skill_index
        self.confianza = confianza
        self.versionador = versionador
        self._ledger = registrar_ledger
        self.tope_tokens = tope_tokens
        self.presupuesto_tokens = presupuesto_tokens
        # Song (g): puerta determinística de políticas (opcional; si no
        # se pasa, el check de allowlist se saltea pero queda documentado).
        self.puerta = puerta
        # Song (h): registro de procedencia de skills admitidas.
        self.procedencia = procedencia
        self._init_db()

    def _con(self):
        con = sqlite3.connect(self.db_path, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init_db(self):
        with self._con() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS admision_casos (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       skill_nombre TEXT NOT NULL,
                       etapa TEXT NOT NULL,
                       propuesta_json TEXT NOT NULL,
                       evidencia_json TEXT NOT NULL DEFAULT '{}',
                       decision_json TEXT NOT NULL DEFAULT '{}',
                       ts_creado REAL NOT NULL,
                       ts_actualizado REAL NOT NULL
                   )""")

    def _asentar_ledger(self, evento):
        if self._ledger:
            try:
                self._ledger(evento)
            except Exception:
                pass  # el ledger es auditoría, no debe frenar el pipeline

    def _caso(self, caso_id):
        with self._con() as con:
            f = con.execute(
                "SELECT id, skill_nombre, etapa, propuesta_json,"
                " evidencia_json, decision_json, ts_creado, ts_actualizado"
                " FROM admision_casos WHERE id=?", (caso_id,)).fetchone()
        if not f:
            raise KeyError(f"caso inexistente: {caso_id}")
        return {"id": f[0], "skill_nombre": f[1], "etapa": f[2],
                "propuesta": json.loads(f[3]),
                "evidencia": json.loads(f[4]),
                "decision": json.loads(f[5]),
                "ts_creado": f[6], "ts_actualizado": f[7]}

    def _mover(self, caso_id, etapa):
        with self._con() as con:
            con.execute(
                "UPDATE admision_casos SET etapa=?, ts_actualizado=?"
                " WHERE id=?", (etapa, time.time(), caso_id))

    def _exigir_etapa(self, caso, esperada):
        if caso["etapa"] != esperada:
            raise ValueError(
                f"caso {caso['id']}: etapa {caso['etapa']!r}, se esperaba"
                f" {esperada!r}")

    # -- etapas -------------------------------------------------------------
    def proponer(self, nombre, descripcion, contenido, propuesto_por="agent"):
        """Crea el caso en etapa `propuesta`. No valida nada todavía."""
        propuesta = {"nombre": nombre, "descripcion": descripcion,
                     "contenido": contenido, "propuesto_por": propuesto_por}
        ahora = time.time()
        with self._con() as con:
            cur = con.execute(
                """INSERT INTO admision_casos
                   (skill_nombre, etapa, propuesta_json, ts_creado,
                    ts_actualizado)
                   VALUES (?, 'propuesta', ?, ?, ?)""",
                (nombre, json.dumps(propuesta, ensure_ascii=False),
                 ahora, ahora))
            caso_id = cur.lastrowid
        self._asentar_ledger({"tipo": "admision_propuesta",
                              "caso_id": caso_id, "skill": nombre})
        return {"id": caso_id, "etapa": ETAPA_PROPUESTA}

    def adjuntar_evidencia(self, caso_id, evidencia):
        """Evidencia: observaciones concretas que motivan la skill.

        ACI regla 1 (Yao c): la evidencia se resume con tope antes de
        guardarse — el contexto del harness se mantiene conciso."""
        caso = self._caso(caso_id)
        self._exigir_etapa(caso, ETAPA_PROPUESTA)
        evidencia = evidencia or {}
        evidencia = {k: resumir(v) if isinstance(v, str) else v
                     for k, v in evidencia.items()}
        with self._con() as con:
            con.execute(
                "UPDATE admision_casos SET evidencia_json=?, etapa=?,"
                " ts_actualizado=? WHERE id=?",
                (json.dumps(evidencia or {}, ensure_ascii=False),
                 ETAPA_EVIDENCIA, time.time(), caso_id))
        self._asentar_ledger({"tipo": "admision_evidencia",
                              "caso_id": caso_id})
        return {"id": caso_id, "etapa": ETAPA_EVIDENCIA}

    def decidir(self, caso_id, aprobar, motivo="", decidido_por="humano"):
        """Gate humano: aprobar=True → staging; False → rechazada*."""
        caso = self._caso(caso_id)
        self._exigir_etapa(caso, ETAPA_EVIDENCIA)
        etapa = ETAPA_STAGING if aprobar else ETAPA_RECHAZADA
        with self._con() as con:
            con.execute(
                "UPDATE admision_casos SET decision_json=?, etapa=?,"
                " ts_actualizado=? WHERE id=?",
                (json.dumps({"aprobar": bool(aprobar), "motivo": motivo,
                             "decidido_por": decidido_por},
                            ensure_ascii=False),
                 etapa, time.time(), caso_id))
        self._asentar_ledger({"tipo": "admision_decision", "caso_id": caso_id,
                              "aprobar": bool(aprobar)})
        return {"id": caso_id, "etapa": etapa}

    def _checks_validacion(self, caso):
        """Checks deterministas (US$0, sin LLM)."""
        checks = []
        contenido = caso["propuesta"]["contenido"]
        nombre = caso["propuesta"]["nombre"]
        # 1. El SKILL.md parsea (cargar_skill exige nombre+descripcion).
        # Se escribe en un tmpdir como SKILL.md porque cargar_skill exige
        # ese nombre de archivo. El tmp se mantiene vivo hasta el final
        # de los checks para el gate de políticas (check 5).
        tmpdir = tempfile.mkdtemp(prefix="alma_admision_val_")
        tmp = os.path.join(tmpdir, "SKILL.md")
        try:
            try:
                with open(tmp, "w", encoding="utf-8") as fh:
                    fh.write(contenido)
                meta = cargar_skill(tmp)
                checks.append({"check": "skllmd_parsea", "ok": True,
                               "detalle": f"nombre={meta.nombre}"})
            except Exception as e:  # noqa: BLE001 - el check reporta
                checks.append({"check": "skllmd_parsea", "ok": False,
                               "detalle": str(e)[:200]})
                return checks
            # 2. El nombre declarado coincide con el caso.
            checks.append({"check": "nombre_coincide",
                           "ok": meta.nombre == nombre,
                           "detalle": f"{meta.nombre!r} vs {nombre!r}"})
            # 3. Nombre único en el índice.
            if self.index is not None:
                existe = any(s.get("name") == meta.nombre
                             for s in self.index.listar())
                checks.append({"check": "nombre_unico", "ok": not existe,
                               "detalle": "ya existe" if existe
                                          else "libre"})
            # 4. Presupuesto de contexto (opcional).
            if self.tope_tokens:
                toks = _estimar_tokens(contenido)
                checks.append({"check": "presupuesto_contexto",
                               "ok": toks <= self.tope_tokens,
                               "detalle": f"{toks} <= {self.tope_tokens}"})
            # 5. Puerta de políticas (Song g): cada herramienta declarada
            # en el frontmatter (`herramientas:`) debe estar en la
            # allowlist. Default-deny.
            if self.puerta is not None:
                ok_pol, motivo_pol = verificar_carga_skill(meta,
                                                          self.puerta)
                checks.append({"check": "politica_allowlist",
                               "ok": ok_pol, "detalle": motivo_pol})
            # 6. Scan determinista del cuerpo en prosa (Fix A1, red-team):
            #    tripwire contra prompt injection / exfiltración /
            #    auto-promoción a trusted. Fail-closed: un hit frena la
            #    admisión y el gate humano decide en última instancia.
            hits = escanear_contenido(contenido)
            checks.append({"check": "contenido_limpio",
                           "ok": not hits,
                           "detalle": ("limpio" if not hits else
                                       f"patrones hostiles: {hits}")})
        finally:
            try:
                os.unlink(tmp)
                os.rmdir(tmpdir)
            except OSError:
                pass
        return checks

    def validar(self, caso_id):
        """Corre los checks; validacion_ok o validacion_fallida*."""
        caso = self._caso(caso_id)
        self._exigir_etapa(caso, ETAPA_STAGING)
        checks = self._checks_validacion(caso)
        ok = all(c["ok"] for c in checks)
        etapa = ETAPA_VALIDACION_OK if ok else ETAPA_VALIDACION_FALLIDA
        with self._con() as con:
            con.execute(
                "UPDATE admision_casos SET etapa=?, ts_actualizado=?"
                " WHERE id=?", (etapa, time.time(), caso_id))
        self._asentar_ledger({"tipo": "admision_validacion",
                              "caso_id": caso_id, "ok": ok,
                              "checks": checks})
        return {"id": caso_id, "etapa": etapa, "ok": ok, "checks": checks}

    def commit(self, caso_id):
        """Admite la skill: escribe SKILL.md, registra, nace provisional,
        abre versión CAPTURED. Etapa final committed*."""
        caso = self._caso(caso_id)
        self._exigir_etapa(caso, ETAPA_VALIDACION_OK)
        if self.index is None:
            raise ValueError("commit requiere skill_index")
        nombre = caso["propuesta"]["nombre"]
        contenido = caso["propuesta"]["contenido"]
        destino_dir = os.path.join(self.skills_dir, nombre)
        os.makedirs(destino_dir, exist_ok=True)
        destino = os.path.join(destino_dir, "SKILL.md")
        if os.path.exists(destino):
            raise ValueError(f"ya existe SKILL.md en {destino}")

        def _valida_parsea(tmp_path):
            try:
                cargar_skill(tmp_path)
                return True, "SKILL.md parsea"
            except Exception as e:  # noqa: BLE001 - el guardrail reporta
                return False, f"no parsea: {e}"[:200]

        # ACI regla 2 (Yao c): guardrails en edición. El contenido se
        # valida (parsea) ANTES de existir en el destino; si no pasa, el
        # destino nunca se toca. Escritura atómica (tmp + rename). El tmp
        # se llama SKILL.md porque cargar_skill exige ese nombre.
        res_edicion = editar_con_guardrails(destino, contenido,
                                            _valida_parsea,
                                            nombre_tmp="SKILL.md")
        if not res_edicion["ok"]:
            raise ValueError(f"commit abortado: {res_edicion['motivo']}")
        skill = cargar_skill(destino)
        if self.presupuesto_tokens is None:
            # Sin presupuesto configurado, la admisión no lo impone: el
            # control de bloat lo hace el Curator (ciclo active/stale).
            presupuesto = skill.tokens_indice + self.index.tokens_indice()
        else:
            presupuesto = self.presupuesto_tokens
        self.index.registrar(skill, presupuesto)
        if self.procedencia is not None:
            # Song (h): la procedencia se registra al admitir. Lo del
            # sistema/usuario nace propio; lo demás nace tercero → en
            # cuarentena hasta graduación explícita.
            origen = ("propio" if skill.created_by
                       in ("agent", "user", "background_review")
                       else "tercero")
            self.procedencia.registrar(skill.path, origen)
        if self.confianza is not None:
            # Toda skill admitida nace PROVISIONAL: el trust se gana con
            # uso (confianza.py), nunca se hereda ni se otorga.
            self.confianza.registrar(skill.path)
        if self.versionador is not None:
            self.versionador.captured(
                skill.path,
                caso["propuesta"]["descripcion"],
                {"caso_id": caso_id, "evidencia": caso["evidencia"]})
        self._mover(caso_id, ETAPA_COMMITTED)
        self._asentar_ledger({"tipo": "admision_commit", "caso_id": caso_id,
                              "path": skill.path})
        return {"id": caso_id, "etapa": ETAPA_COMMITTED,
                "path": skill.path}

    # -- lectura --------------------------------------------------------------
    def caso(self, caso_id):
        return self._caso(caso_id)

    def pendientes(self):
        """Casos en etapas no terminales."""
        with self._con() as con:
            filas = con.execute(
                "SELECT id, skill_nombre, etapa, ts_actualizado"
                " FROM admision_casos WHERE etapa NOT IN (?,?,?)"
                " ORDER BY id",
                (ETAPA_RECHAZADA, ETAPA_VALIDACION_FALLIDA,
                 ETAPA_COMMITTED)).fetchall()
        return [{"id": f[0], "skill_nombre": f[1], "etapa": f[2],
                 "ts_actualizado": f[3]} for f in filas]
