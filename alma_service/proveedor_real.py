"""Proveedor de skills REAL — fase 1.

Implementa la costura `ProveedorSkills` del resolver sobre componentes
reales (no sobre el historial del mock):

- `ProveedorSkillsReal`: existe/brazo/soporte leídos de SkillIndex +
  MemoriaExperiencias. El "brazo de la skill" es el argmax de la media
  con decaimiento temporal por firma (análogo honesto del prior
  condicionado del mock); el soporte son wins pareados sobre probes
  limpios registrados en `probe_bloques` (umbral endurecido EXP49).
- `GeneradorSkills`: crea skills en formato SKILL.md desde experiencias
  (llamadas al modelo), y las refina cuando la evidencia nueva
  contradice la recomendación. Respeta el presupuesto duro de contexto
  (vía Curator ante PresupuestoExcedido) y el ciclo de vida de fase 0.
- `BackendConSkill`: la skill como procedimiento que guía la ejecución:
  inyecta el cuerpo del SKILL.md en el system prompt cuando se juega el
  brazo que la skill recomienda. Sin esto, la skill sería solo un prior;
  con esto, cambia el comportamiento del modelo (pregunta que solo los
  modelos reales pueden responder — regla mock-first, AGENTS.md 27/9).
- `ProveedorSkillsNulo`: control conceptual — nunca hay skills. En fase 1
  no se gasta en un brazo control con key (los mocks ya respondieron la
  aritmética del mecanismo, EXP45–52); existe para tests y para el modo
  adaptativo forzado.

Seguridad (diseño §1.2): las skills las genera el agente desde su propia
experiencia. Ninguna skill de terceros se auto-instala; este módulo no
tiene ningún camino de ingesta externa.
"""

import os
import re
import time

from alma_service.resolver import ProveedorSkills
from alma_service.scaffold import umbral_soporte
from alma_service.skills import (
    Skill, SkillIndex, cargar_skill, parse_frontmatter, SkillInvalida,
    PresupuestoExcedido,
)
from alma_service.llm import PresupuestoAgotado


CATEGORIA_FIRMAS = "firmas"


def slug_firma(sig):
    return re.sub(r"[^a-z0-9]+", "-", str(sig).lower()).strip("-") or "firma"


def umbral_endurecido(k):
    """Umbral endurecido con defaults validados (EXP56/57): 1 + floor(K/3)."""
    return umbral_soporte(k)


class ProveedorSkillsNulo(ProveedorSkills):
    """Nunca hay skills: modo adaptativo puro (Thompson + re-probe)."""

    def existe(self, b, sig):
        return False

    def brazo(self, b, sig):
        return None

    def soporte(self, b, sig, skill_arm):
        return (False, 0, 0, None)


class ProveedorSkillsReal(ProveedorSkills):
    """Lee skills y soporte de SkillIndex + MemoriaExperiencias."""

    def __init__(self, skill_index, memoria, brazos):
        self.index = skill_index
        self.memoria = memoria
        self.brazos = list(brazos)

    # -- localización de la skill --------------------------------------
    def _nombre(self, sig):
        return slug_firma(sig)

    def existe(self, b, sig):
        return self.index.tiene_skill(CATEGORIA_FIRMAS, self._nombre(sig))

    def cargar_skill(self, sig):
        """La Skill completa (cuerpo incluido) o None."""
        nombre = self._nombre(sig)
        filas = [f for f in self.index.listar(estado="active")
                 if f["categoria"] == CATEGORIA_FIRMAS
                 and f["name"] == nombre]
        if not filas:
            return None
        return self.index.cargar_completa(filas[0]["path"])

    def recomienda_brazo(self, sig):
        sk = self.cargar_skill(sig)
        if sk is None:
            return None
        fm, _ = parse_frontmatter(open(sk.path, encoding="utf-8").read())
        rb = fm.get("recomienda_brazo")
        return rb if rb in self.brazos else None

    # -- decisiones ------------------------------------------------------
    def brazo(self, b, sig):
        """Argmax de la media con decaimiento temporal por firma
        (análogo real del prior condicionado del mock)."""
        obs = self.memoria.recuperar_con_decaimiento(str(sig))
        if not obs:
            return None
        suma = {a: 0.0 for a in self.brazos}
        peso = {a: 0.0 for a in self.brazos}
        for arch_id, r, p in obs:
            if arch_id in suma:
                suma[arch_id] += r * p
                peso[arch_id] += p
        medias = {a: (suma[a] / peso[a] if peso[a] > 0 else 0.0)
                  for a in self.brazos}
        # Sin evidencia (todo peso 0) no hay recomendación honesta.
        if all(peso[a] == 0 for a in self.brazos):
            return None
        return max(self.brazos, key=lambda a: medias[a])

    def soporte(self, b, sig, skill_arm):
        """(fuerte, wins, K, umbral) sobre probes limpios reales."""
        if skill_arm is None:
            return (False, 0, 0, None)
        wins, k = self.memoria.soporte_firma(str(sig), int(b), skill_arm)
        umbral = umbral_endurecido(k)
        fuerte = k > 0 and wins >= umbral
        return (fuerte, wins, k, umbral)


class BackendConSkill:
    """Envuelve un backend inyectando la skill como guía.

    Cuando el resolver juega el brazo que la skill recomienda, el cuerpo
    del SKILL.md se agrega al system prompt. Los probes (Q1/Q2) siempre
    miden brazos raw: la medición stays limpia, la explotación usa la
    guía. Misma interfaz complete()/costo() que un backend.
    """

    def __init__(self, backend, skill):
        self.backend = backend
        self.skill = skill

    def complete(self, prompt, system=None, **kw):
        guia = (f"[Skill activa: {self.skill.nombre}]\n"
                f"{self.skill.cuerpo}\n\nSeguí este procedimiento.")
        system = f"{system}\n\n{guia}" if system else guia
        return self.backend.complete(prompt, system=system, **kw)

    def costo(self, uso):
        return self.backend.costo(uso)


# --- generación ----------------------------------------------------------

PROMPT_SISTEMA_GEN = (
    "Sos el generador de skills de ALMA. Respondés SOLO con un archivo "
    "SKILL.md válido: frontmatter YAML entre ---, luego el cuerpo. Sin "
    "texto antes ni después."
)

PLANTILLA_FRONTMATTER = """---
name: {nombre}
description: {descripcion}
firma: {firma}
recomienda_brazo: {brazo}
created_by: agent
version: {version}
---
"""


def _resumen_evidencia(experiencias):
    lineas = []
    for e in experiencias:
        ok = "✓" if e["reward"] and e["reward"] > 0.5 else "✗"
        lineas.append(
            f"- [{ok}] brazo={e['arch_id']} | {e['enunciado'][:90]}")
    return "\n".join(lineas)


class GeneradorSkills:
    """Crea y refina SKILL.md desde experiencias, con llamadas al modelo.

    Toda llamada sale por ClienteMedido (presupuesto duro). Ante
    PresupuestoExcedido en el índice: corre el Curator una vez y reintenta;
    si sigue sin entrar, la generación se omite y queda registrada
    (no se gasta en una skill que no entra al presupuesto).
    """

    def __init__(self, skill_index, memoria, skills_dir, curator=None,
                 min_experiencias=6, max_refinamientos=2,
                 presupuesto_indice_tokens=4000):
        self.index = skill_index
        self.memoria = memoria
        self.skills_dir = os.path.abspath(skills_dir)
        self.curator = curator
        self.min_experiencias = int(min_experiencias)
        self.max_refinamientos = int(max_refinamientos)
        self.presupuesto_tokens = int(presupuesto_indice_tokens)
        self.eventos = []  # bitácora para el reporte

    # -- lectura de evidencia -------------------------------------------
    def _evidencia(self, sig, n=12):
        return self.memoria.experiencias_detalle(str(sig), n=n)

    def _mejor_brazo(self, sig, brazos):
        obs = self.memoria.recuperar_con_decaimiento(str(sig))
        if not obs:
            return None, 0.0
        suma, peso = {}, {}
        for arch_id, r, p in obs:
            suma[arch_id] = suma.get(arch_id, 0.0) + r * p
            peso[arch_id] = peso.get(arch_id, 0.0) + p
        brazos = [a for a in brazos if peso.get(a, 0) > 0]
        if not brazos:
            return None, 0.0
        mejor = max(brazos, key=lambda a: suma[a] / peso[a])
        return mejor, suma[mejor] / peso[mejor]

    # -- entrada ---------------------------------------------------------
    def maybe_generar_o_refinar(self, sig, cliente_llm, brazos):
        """Decide y ejecuta: generar / refinar / omitir. Retorna
        (acción, detalle). Nunca gasta si no corresponde."""
        proveedor = ProveedorSkillsReal(self.index, self.memoria, brazos)
        ev = self._evidencia(sig)
        if len(ev) < self.min_experiencias:
            return ("omitida", {"razon": "poca evidencia",
                                "n": len(ev)})
        skill = proveedor.cargar_skill(sig)
        if skill is None:
            return self._generar(sig, ev, cliente_llm, brazos, proveedor)
        return self._refinar_si_corresponde(sig, skill, ev, cliente_llm,
                                            brazos, proveedor)

    # -- generación ------------------------------------------------------
    def _generar(self, sig, ev, cliente_llm, brazos, proveedor):
        mejor, tasa = self._mejor_brazo(sig, brazos)
        if mejor is None:
            return ("omitida", {"razon": "sin brazo ganador"})
        nombre = slug_firma(sig)
        prompt = (
            f"Firma de problema: {sig}\n\n"
            f"Evidencia (problema → brazo usado → éxito):\n"
            f"{_resumen_evidencia(ev)}\n\n"
            f"El brazo con mejor tasa de éxito es '{mejor}' "
            f"({tasa:.0%} de éxito ponderado).\n\n"
            f"Escribí el SKILL.md con EXACTAMENTE este frontmatter:\n"
            + PLANTILLA_FRONTMATTER.format(
                nombre=nombre,
                descripcion=(f"Procedimiento para problemas de tipo {sig}: "
                             f"usa {mejor}.")[:140],
                firma=sig, brazo=mejor, version=1)
            + "\nY un cuerpo de 120 palabras como máximo: procedimiento "
            f"concreto — qué hacer y qué evitar — para resolver problemas "
            f"de tipo '{sig}'. No nombres el brazo en el cuerpo: la "
            f"recomendación del brazo vive solo en el frontmatter. "
            f"Basate SOLO en la evidencia de arriba."
        )
        try:
            texto, _uso = cliente_llm.complete(
                prompt, etiqueta="skill-gen", system=PROMPT_SISTEMA_GEN)
        except PresupuestoAgotado as e:
            self.eventos.append({"accion": "generar", "firma": sig,
                                 "resultado": "presupuesto-agotado"})
            return ("omitida", {"razon": "presupuesto agotado"})
        skill = self._validar_y_guardar(texto, nombre, sig, mejor, brazos,
                                        version=1)
        if skill is None:
            return ("omitida", {"razon": "skill inválida del modelo"})
        self.eventos.append({"accion": "generar", "firma": sig,
                             "skill": skill.path, "brazo": mejor})
        return ("generada", {"path": skill.path, "brazo": mejor})

    # -- refinamiento ----------------------------------------------------
    def _refinar_si_corresponde(self, sig, skill, ev, cliente_llm, brazos,
                                proveedor):
        fm_txt = open(skill.path, encoding="utf-8").read()
        fm, cuerpo_actual = parse_frontmatter(fm_txt)
        version = int(fm.get("version", 1))
        if version - 1 >= self.max_refinamientos:
            return ("omitida", {"razon": "tope de refinamientos",
                                "version": version})
        recomendado = fm.get("recomienda_brazo")
        mejor, tasa = self._mejor_brazo(sig, brazos)
        if mejor is None or mejor == recomendado:
            return ("omitida", {"razon": "sin contradicción",
                                "recomienda": recomendado, "mejor": mejor})
        nombre = slug_firma(sig)
        prompt = (
            f"Firma de problema: {sig}\n\n"
            f"Procedimiento actual (v{version}):\n{cuerpo_actual}\n\n"
            f"Nueva evidencia:\n{_resumen_evidencia(ev)}\n\n"
            f"La evidencia nueva favorece '{mejor}' ({tasa:.0%}) por sobre "
            f"'{recomendado}' (recomendación actual).\n\n"
            f"Reescribí el SKILL.md con EXACTAMENTE este frontmatter:\n"
            + PLANTILLA_FRONTMATTER.format(
                nombre=nombre,
                descripcion=(f"Procedimiento para problemas de tipo {sig}: "
                             f"usa {mejor}.")[:140],
                firma=sig, brazo=mejor, version=version + 1)
            + "\nY el cuerpo actualizado (120 palabras máximo): mantené lo "
            "que sigue valiendo, corregí lo que la evidencia refutó. No "
            "nombres el brazo en el cuerpo."
        )
        try:
            texto, _uso = cliente_llm.complete(
                prompt, etiqueta="skill-refine", system=PROMPT_SISTEMA_GEN)
        except PresupuestoAgotado:
            self.eventos.append({"accion": "refinar", "firma": sig,
                                 "resultado": "presupuesto-agotado"})
            return ("omitida", {"razon": "presupuesto agotado"})
        nueva = self._validar_y_guardar(texto, nombre, sig, mejor, brazos,
                                        version=version + 1)
        if nueva is None:
            return ("omitida", {"razon": "skill inválida del modelo"})
        self.eventos.append({"accion": "refinar", "firma": sig,
                             "skill": nueva.path,
                             "version": version + 1,
                             "antes": recomendado, "ahora": mejor})
        return ("refinada", {"path": nueva.path, "version": version + 1})

    # -- validación y guardado --------------------------------------------
    def _validar_y_guardar(self, texto, nombre, sig, brazo, brazos,
                           version):
        texto = texto.strip()
        # El modelo a veces envuelve en ```markdown: tolerar y extraer.
        m = re.search(r"```(?:markdown)?\s*(---.*?)```", texto,
                      re.DOTALL | re.IGNORECASE)
        if m:
            texto = m.group(1).strip()
        try:
            fm, cuerpo = parse_frontmatter(texto)
        except SkillInvalida:
            return None
        for req in ("name", "description", "firma", "recomienda_brazo"):
            if not fm.get(req):
                return None
        if fm["recomienda_brazo"] not in brazos or not cuerpo:
            return None
        if fm["name"] != nombre or str(fm["firma"]) != str(sig):
            return None
        if int(fm.get("version", 0)) != version:
            return None
        d = os.path.join(self.skills_dir, CATEGORIA_FIRMAS, nombre)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "SKILL.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(texto + "\n")
        try:
            skill = cargar_skill(path)
        except SkillInvalida:
            return None
        try:
            self.index.registrar(skill, self.presupuesto_tokens)
        except PresupuestoExcedido:
            # Una oportunidad: el Curator libera y se reintenta. Si no
            # entra, no se gasta más en esta skill.
            if self.curator is not None:
                self.curator.barrer()
                try:
                    self.index.registrar(skill, self.presupuesto_tokens)
                except PresupuestoExcedido:
                    self.eventos.append(
                        {"accion": "registrar", "firma": sig,
                         "resultado": "presupuesto-indice-excedido"})
                    return None
            else:
                return None
        return skill
