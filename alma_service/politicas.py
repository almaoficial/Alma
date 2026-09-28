"""Puerta determinística de políticas sobre llamadas a herramientas — de Dawn Song.

Doctrina (informe §3.2/§4.1): ninguna defensa a nivel modelo aguanta
atacantes adaptativos ("The Attacker Moves Second": 12/12 defensas
caídas a >90% ASR). Lo que sí aguanta es enforcement determinístico
fuera de banda, estilo Progent: política simbólica de least privilege
sobre tool calls, evaluada por CÓDIGO, nunca por un LLM.

El detector LLM-based NO existe en ningún camino de enforcement de este
sistema (la revisión con LLM de revision.py está apagada por default y,
cuando se habilite, es telemetría — nunca decide permisos). Este módulo
no importa ningún módulo LLM; hay un test que lo verifica.

Superficie cubierta (lo que el servicio realmente hace — sin shell):
- Carga/escritura de skills: `cargar_skill` / `escribir_skill` con
  `path` confinado a la raíz de skills (verificar_ruta: deniega escapes
  `..` y rutas absolutas fuera de la raíz).
- Superficie declarada de skills: una skill puede declarar
  `herramientas:` en su frontmatter; la admisión (admision.py) y
  `verificar_carga_skill` exigen que cada herramienta declarada esté en
  la allowlist. Default-deny: lo no listado está prohibido.

Monotonic confinement (Progent): la política solo se achica sin
aprobación.
- `estrechar`: quita permisos → aplica de inmediato, queda en el ledger.
- `solicitar_ampliacion` → queda PENDIENTE; `aprobar_ampliacion`
  (gate humano explícito) la aplica. Sin aprobación no hay expansión.

LO QUE NO CUBRE (documentado, no prometido — ver SIN_CUBRIR):
"""

import hashlib
import json
import os
import re
import time

REGLA_RUTA_EN_RAIZ = "ruta_en_raiz"
REGLA_LITERAL = "literal"
REGLA_REGEX = "regex"

# Fix A3b (red-team): la aprobación de ampliaciones exige un aprobador
# en esta allowlist. "humano" es el único valor válido por default: un
# label arbitrario ("admin", "sistema", ...) NO aprueba. Alcance honesto:
# dentro del proceso no hay autenticación real (código confiable); la
# allowlist frena contenido malicioso que intente auto-aprobarse, no un
# atacante con acceso al proceso. Además, aprobar_ampliacion NO está
# expuesta como endpoint del servidor (verificado: solo se alcanza desde
# código Python del proceso).
APROBADORES_PERMITIDOS = ("humano",)

SIN_CUBRIR = (
    "1. Sin sandbox de ejecución: el servicio no ejecuta código de skills "
    "(las skills son prosa que se inyecta en prompts). Si algún día se "
    "ejecutara código, esta puerta no alcanza: haría falta sandbox + la "
    "puerta.\n"
    "2. Inyección indirecta vía contenido de memoria (AgentPoison): mitigada "
    "por procedencia+cuarentena (procedencia.py), no eliminada.\n"
    "3. La política NO se auto-genera con LLM (el eslabón probabilístico de "
    "Progent se evita no implementándolo): toda ampliación es humana y "
    "requiere aprobación explícita.\n"
    "4. Sin control de egress de red: el servicio no hace llamadas de red "
    "salvo backends vía Vault (fuera de esta superficie).\n"
    "5. El detector LLM-based no existe en ningún camino de enforcement: "
    "la revisión con LLM (revision.py) está apagada por default y, cuando "
    "se habilite, es telemetría — nunca decide permisos."
)


def politica_default():
    """Least privilege inicial: solo lo que el servicio necesita.

    Formato: herramienta -> {arg: (regla, parametro)}.
    Lo no listado está prohibido (default-deny). "comando_shell"
    deliberadamente ausente: el servicio no ejecuta shell.
    """
    return {
        "cargar_skill": {"path": (REGLA_RUTA_EN_RAIZ, "skills")},
        "escribir_skill": {"path": (REGLA_RUTA_EN_RAIZ, "skills")},
        "leer_memoria": {},
        "escribir_memoria": {},
        "ejecutar_benchmark": {},
        "proponer_scaffold": {},
    }


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


class PuertaPoliticas:
    """Policy gate determinístico. Sin LLM en ningún camino."""

    def __init__(self, raices, politica=None, ledger_path=None,
                 aprobadores_permitidos=None):
        # raices: {"skills": <dir>, "workspace": <dir>}
        # Fix A4b: realpath (resuelve symlinks), no abspath.
        self.raices = {k: os.path.realpath(v) for k, v in raices.items()}
        self._politica = (dict(politica) if politica is not None
                          else politica_default())
        self._pendientes = {}
        self._prox_id = 1
        # Fix A3b: allowlist de aprobadores.
        self._aprobadores = (
            tuple(aprobadores_permitidos)
            if aprobadores_permitidos is not None
            else APROBADORES_PERMITIDOS)
        self.ledger_path = (ledger_path or os.path.join(
            self.raices.get("workspace", os.getcwd()),
            "politica_ledger.jsonl"))
        d = os.path.dirname(os.path.abspath(self.ledger_path))
        os.makedirs(d, exist_ok=True)
        if not os.path.exists(self.ledger_path):
            with open(self.ledger_path, "w", encoding="utf-8") as f:
                f.write("")

    # -- evaluación (pura, determinista) ---------------------------------
    def verificar_ruta(self, path, raiz_nombre):
        """True ssi path queda dentro de la raíz nombrada (sin escapes).

        Fix A4b (red-team): usa realpath — resuelve symlinks antes de
        comparar. Un enlace dentro de la raíz apuntando afuera se deniega.
        """
        raiz = self.raices.get(raiz_nombre)
        if raiz is None:
            return False
        abs_path = os.path.realpath(path)
        try:
            dentro = os.path.commonpath([abs_path, raiz]) == raiz
        except ValueError:
            return False
        return dentro

    def _chequear_arg(self, regla, param, valor):
        if regla == REGLA_RUTA_EN_RAIZ:
            return self.verificar_ruta(str(valor), param)
        if regla == REGLA_LITERAL:
            return str(valor) == str(param)
        if regla == REGLA_REGEX:
            return re.fullmatch(str(param), str(valor)) is not None
        return False

    def herramienta_permitida(self, herramienta):
        """¿La herramienta está listada? (sin mirar argumentos)."""
        return herramienta in self._politica

    def evaluar(self, herramienta, args):
        """Veredicto determinístico sobre una llamada.

        Retorna dict {permitido, motivo, herramienta} — convención de
        feedback explícito (ACI regla 3): siempre hay motivo, incluso
        cuando se permite.
        """
        args = dict(args or {})
        reglas = self._politica.get(herramienta)
        if reglas is None:
            return {"permitido": False, "herramienta": herramienta,
                    "motivo": "herramienta no listada (default-deny)"}
        for arg, valor in args.items():
            if arg not in reglas:
                return {"permitido": False, "herramienta": herramienta,
                        "motivo": f"argumento no permitido: {arg!r}"}
            regla, param = reglas[arg]
            if not self._chequear_arg(regla, param, valor):
                return {"permitido": False, "herramienta": herramienta,
                        "motivo": f"argumento {arg!r} viola la regla"
                                  f" {regla} ({param})"}
        faltantes = [a for a in reglas if a not in args]
        if faltantes:
            return {"permitido": False, "herramienta": herramienta,
                    "motivo": f"faltan argumentos requeridos: {faltantes}"}
        return {"permitido": True, "herramienta": herramienta,
                "motivo": "dentro de la política least-privilege"}

    # -- monotonic confinement ---------------------------------------------
    def estrechar(self, herramienta, args_quitar=None):
        """Narrowing: quita permisos. Aplica de inmediato (sin aprobación)."""
        reglas = self._politica.get(herramienta, {})
        if args_quitar:
            for a in args_quitar:
                reglas.pop(a, None)
            if not reglas:
                self._politica.pop(herramienta, None)
        else:
            self._politica.pop(herramienta, None)
        self._asentar({"tipo": "narrowing",
                       "herramienta": herramienta,
                       "quitado": list(args_quitar or []) or "herramienta"})
        return {"ok": True, "tipo": "narrowing"}

    def solicitar_ampliacion(self, herramienta, nuevas_reglas):
        """Expansion: queda PENDIENTE hasta aprobación humana explícita."""
        pid = self._prox_id
        self._prox_id += 1
        self._pendientes[pid] = {
            "herramienta": herramienta,
            "nuevas_reglas": {k: list(v)
                              for k, v in nuevas_reglas.items()},
            "estado": "pendiente", "ts": time.time(),
        }
        self._asentar({"tipo": "expansion_solicitada", "id": pid,
                       "herramienta": herramienta})
        return {"ok": True, "id": pid, "estado": "pendiente"}

    def aprobar_ampliacion(self, pid, aprobador="humano"):
        """Gate humano explícito. Fix A3b (red-team): el aprobador debe
        estar en la allowlist; un label arbitrario no aprueba."""
        if aprobador not in self._aprobadores:
            return {"ok": False,
                    "motivo": f"aprobador no autorizado: {aprobador!r}"}
        p = self._pendientes.get(pid)
        if not p or p["estado"] != "pendiente":
            return {"ok": False, "motivo": "solicitud no pendiente"}
        reglas = self._politica.setdefault(p["herramienta"], {})
        for arg, (regla, param) in p["nuevas_reglas"].items():
            reglas[arg] = (regla, param)
        p["estado"] = "aprobada"
        self._asentar({"tipo": "expansion_aprobada", "id": pid,
                       "herramienta": p["herramienta"],
                       "aprobador": aprobador})
        return {"ok": True, "id": pid}

    def rechazar_ampliacion(self, pid):
        p = self._pendientes.get(pid)
        if not p or p["estado"] != "pendiente":
            return {"ok": False, "motivo": "solicitud no pendiente"}
        p["estado"] = "rechazada"
        self._asentar({"tipo": "expansion_rechazada", "id": pid})
        return {"ok": True, "id": pid}

    def politica_actual(self):
        return {h: dict(r) for h, r in self._politica.items()}

    def pendientes(self):
        return {pid: dict(p) for pid, p in self._pendientes.items()
                if p["estado"] == "pendiente"}

    # -- ledger ---------------------------------------------------------------
    def _asentar(self, evento):
        prev = "GENESIS"
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    prev = json.loads(linea)["hash"]
        cuerpo = dict(evento)
        cuerpo["timestamp"] = time.time()
        h = hashlib.sha256(
            (prev + _canonical(cuerpo)).encode("utf-8")).hexdigest()
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(_canonical({"prev": prev, "hash": h,
                                "evento": cuerpo}) + "\n")
        return h


def herramientas_declaradas(skill):
    """Lee `herramientas:` del frontmatter de una skill (lista separada
    por comas). Vacío si no declara ninguna."""
    raw = ""
    try:
        # Skill tiene .referencias; el frontmatter crudo no se guarda, así
        # que re-leemos el archivo para las claves declarativas.
        with open(skill.path, "r", encoding="utf-8") as f:
            texto = f.read()
    except OSError:
        return []
    en_fm = False
    for linea in texto.splitlines():
        s = linea.strip()
        if s == "---":
            if not en_fm:
                en_fm = True
                continue
            break
        if en_fm and s.lower().startswith("herramientas:"):
            raw = s.split(":", 1)[1]
    return [t.strip() for t in raw.split(",") if t.strip()]


def verificar_carga_skill(skill, puerta):
    """Gate determinístico de carga: cada herramienta declarada por la
    skill debe estar en la allowlist. Retorna (ok, motivo)."""
    for h in herramientas_declaradas(skill):
        if not puerta.herramienta_permitida(h):
            return (False, f"herramienta declarada fuera de la allowlist:"
                           f" {h!r} (default-deny)")
    return (True, "superficie declarada dentro de la política")
