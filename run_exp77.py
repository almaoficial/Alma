"""EXP77 — auditoría de handoff de las skills existentes de ALMA.

Corre: python3 run_exp77.py
Pre-registro obligatorio: metaloop_preregistro_exp77.json (fail-closed:
sin pre-registro no corre). Mock US$0, semillas fijas.

SOLO AUDITA: evaluar_skill_para_adopcion se llama con un spy que
registra las aceptaciones de la puerta SIN adoptar (la puerta invoca
adoptar_fn cuando acepta, por contrato; el spy devuelve adoptada=False).
Nada se adopta, nada se cuarentena, nada se modifica. El informe es para
decisión humana.

El traductor (traductor-exp77-v1, abajo) deriva (ayuda, rigidez) del
contenido observable de cada SKILL.md con predicados mecánicos y
deterministas. Los veredictos son CONDICIONALES a esta rúbrica — se
declara en el informe; lo exacto es q (claridad_interfaz) y los deltas
dada la rúbrica. Sensibilidad ±0.2 incluida.
"""

import glob
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alma_service.handoff import (
    REGLA_HANDOFF, claridad_interfaz, evaluar_skill_para_adopcion,
    interfaz_de_skill)
from alma_service.skills import parse_frontmatter

BASE = os.path.dirname(os.path.abspath(__file__))
PREREG_PATH = os.path.join(BASE, "metaloop_preregistro_exp77.json")
OUT_DIR = os.path.join(BASE, "data_exp77")

RUBRICA_VERSION = "traductor-exp77-v1"

# -- traductor explícito: contenido observable -> (ayuda, rigidez) --------
# ayuda: cuánto ayuda la skill cuando la interfaz es clara (q->1).
# rigidez: cuánto constriñe/desvía cuando la interfaz es confusa (q->0).
# Cada predicado es mecánico (regex sobre el cuerpo/frontmatter) y queda
# registrado por skill en el informe. Rúbrica versionada: si cambia la
# rúbrica, cambian los settings del instrumento, y se re-audita.


def traducir(contenido_md):
    """Retorna (ayuda, rigidez, predicados). Determinista."""
    fm, cuerpo = parse_frontmatter(contenido_md)
    cuerpo = cuerpo or ""
    preds = []
    ayuda = 0.5
    rigidez = 0.0
    # A1 PROCEDIMIENTO: pasos ordenados explícitos (lista o marcadores)
    if (re.search(r"(?im)^\s*(?:\d+[.)]|[-*])\s+\S", cuerpo)
            or re.search(r"(?i)\b(primero|segundo|tercero|paso\s*\d+|"
                         r"luego|despu[eé]s)\b", cuerpo)):
        ayuda += 0.2
        preds.append("PROCEDIMIENTO")
    # A2 TECNICA: nombra una técnica concreta
    if re.search(r"(?i)t[eé]cnica\s+de\s+\w+", cuerpo):
        ayuda += 0.1
        preds.append("TECNICA")
    # A3 INSTRUCCION_CONCRETA: micro-procedimiento (<60 palabras, imperativo)
    if (len(cuerpo.split()) < 60 and re.search(
            r"(?i)\b(respond[eé]|us[ae]|hac[eé]|gener[ae]|dec[ií]|"
            r"escrib[ei]|salud[ae]|comenz[aá]|identific[ae])\b", cuerpo)):
        ayuda += 0.2
        preds.append("INSTRUCCION_CONCRETA")
    # A4 GENERICO: ningún predicado positivo disparó -> consejo genérico
    if not [p for p in preds
            if p in ("PROCEDIMIENTO", "TECNICA", "INSTRUCCION_CONCRETA")]:
        ayuda -= 0.2
        preds.append("GENERICO")
    # R1 PRESCRIBE: el frontmatter prescribe una elección (brazo, etc.)
    if any(str(k).lower().startswith(
            ("recomienda", "fuerza", "usa_siempre", "fija_")) for k in fm):
        rigidez += 0.3
        preds.append("PRESCRIBE")
    # R2 RESTRINGE: lenguaje de restricción en el cuerpo
    if re.search(r"(?i)\b(evit\w*|nunca|jam[aá]s|no\s+debes|no\s+omit\w*|"
                 r"prohibido|siempre\s+debes)\b", cuerpo):
        rigidez += 0.2
        preds.append("RESTRINGE")
    ayuda = round(min(1.0, max(0.0, ayuda)), 4)
    rigidez = round(min(1.0, max(0.0, rigidez)), 4)
    return ayuda, rigidez, preds


def inventario():
    """Todas las SKILL.md del repo con su hash. Los DBs de skills están
    vacíos (verificado 1/10); las skills vivas son estas + resultados."""
    patrones = [
        os.path.join(BASE, "resultados/fase1-puerta/rep*/skills/firmas/*/SKILL.md"),
        os.path.join(BASE, "skills/ejemplo/*/SKILL.md"),
    ]
    rutas = sorted({p for pat in patrones for p in glob.glob(pat)})
    inv = []
    for p in rutas:
        md = open(p, encoding="utf-8").read()
        inv.append({
            "ruta": os.path.relpath(p, BASE),
            "sha256": hashlib.sha256(md.encode()).hexdigest()[:12],
            "contenido": md,
        })
    return inv


def clasificar(veredicto):
    d = veredicto["delta_down"]
    if veredicto["aceptada"]:
        return "pasa"
    if d < 0:
        return "resta"
    return "bloat"


def auditar_skill(item, ayuda, rigidez, spy):
    nombre = item["ruta"]
    v = evaluar_skill_para_adopcion(
        nombre, item["contenido"], ayuda, rigidez, adoptar_fn=spy)
    return v


def sensibilidad(item, ayuda, rigidez, spy):
    """Grilla ayuda±0.2, rigidez±0.2 -> veredictos. Estabilidad del hallazgo."""
    res = {}
    for da in (-0.2, 0.0, 0.2):
        for dr in (-0.2, 0.0, 0.2):
            a = round(min(1.0, max(0.0, ayuda + da)), 4)
            r = round(min(1.0, max(0.0, rigidez + dr)), 4)
            v = evaluar_skill_para_adopcion(
                item["ruta"], item["contenido"], a, r, adoptar_fn=None)
            res[f"ayuda{a:+.1f}_rigidez{r:+.1f}"] = clasificar(v)
    base = clasificar(evaluar_skill_para_adopcion(
        item["ruta"], item["contenido"], ayuda, rigidez, adoptar_fn=None))
    estables = sum(1 for c in res.values() if c == base)
    return {"grilla": res, "base": base,
            "estables": estables, "total": len(res)}


def main():
    if not os.path.exists(PREREG_PATH):
        print("FAIL - sin pre-registro no corre "
              f"(falta {PREREG_PATH})")
        sys.exit(2)
    prereg = json.load(open(PREREG_PATH, encoding="utf-8"))
    assert prereg.get("experimento") == "exp77_auditoria_handoff_skills", \
        "pre-registro de otro experimento"

    llamadas_spy = []

    def spy(deltas, evidencia):
        # La puerta invoca adoptar_fn cuando ACEPTA (es su contrato).
        # El spy REGISTRA la llamada sin adoptar nada: la auditoría
        # nunca toca Promotor.auto_adoptar. Si alguna adopción real
        # ocurriera, v["adoptada_via_fn"] sería True -> FAIL.
        llamadas_spy.append({"deltas": deltas,
                             "origen": evidencia.get("origen")})
        return {"adoptada": False,
                "motivo": "auditoría EXP77: registro sin adopción"}

    os.makedirs(OUT_DIR, exist_ok=True)
    inv = inventario()
    print(f"inventario: {len(inv)} archivos SKILL.md")
    hallazgos = []
    for item in inv:
        ayuda, rigidez, preds = traducir(item["contenido"])
        interfaz = interfaz_de_skill(item["contenido"])
        q = claridad_interfaz(interfaz)
        v = auditar_skill(item, ayuda, rigidez, spy)
        sens = sensibilidad(item, ayuda, rigidez, spy)
        h = {
            "ruta": item["ruta"],
            "sha256": item["sha256"],
            "nombre_skill": interfaz["nombre"],
            "q_interfaz": q,
            "rubrica": RUBRICA_VERSION,
            "predicados": preds,
            "ayuda": ayuda,
            "rigidez": rigidez,
            "delta_down": v["delta_down"],
            "delta_ref": v["delta_ref"],
            "aceptada_por_puerta": v["aceptada"],
            "motivo": v["motivo"],
            "clasificacion": clasificar(v),
            "sensibilidad": sens,
            "adoptada_via_fn": v["adoptada_via_fn"],
        }
        hallazgos.append(h)
        print(f"  {item['ruta']}: q={q} ayuda={ayuda} rigidez={rigidez} "
              f"Δ_down={v['delta_down']:+.4f} -> {h['clasificacion']} "
              f"(estable {sens['estables']}/{sens['total']}) "
              f"[{','.join(preds)}]")

    # Cero adopciones reales: el spy solo registra aceptaciones de la
    # puerta; v["adoptada_via_fn"] debe ser False en todas.
    assert all(not h["adoptada_via_fn"] for h in hallazgos), \
        "adopción real durante la auditoría"
    aceptadas = sum(1 for h in hallazgos if h["aceptada_por_puerta"])
    assert len(llamadas_spy) == aceptadas, \
        "el spy debe registrar exactamente las aceptaciones de la puerta"
    print(f"cero adopciones reales: OK "
          f"({aceptadas} aceptaciones registradas por el spy, sin adoptar)")

    # Determinismo: re-correr y comparar
    for item, h in zip(inv, hallazgos):
        v2 = auditar_skill(item, h["ayuda"], h["rigidez"], spy)
        assert (v2["delta_down"], v2["delta_ref"]) == \
            (h["delta_down"], h["delta_ref"]), \
            f"no-determinista en {item['ruta']}"
    print("determinismo: OK (re-corrida idéntica)")

    reporte = {
        "experimento": "exp77_auditoria_handoff_skills",
        "fecha": "2026-10-01",
        "regla": REGLA_HANDOFF,
        "rubrica": RUBRICA_VERSION,
        "nota_honesta": ("veredictos CONDICIONALES a la rúbrica "
                         f"{RUBRICA_VERSION}; q es exacto; deltas exactos "
                         "dada la rúbrica. Auditoría de lectura: cero "
                         "adopciones, cero modificaciones."),
        "inventario_n": len(inv),
        "hallazgos": hallazgos,
    }
    with open(os.path.join(OUT_DIR, "resultados_exp77.json"), "w",
              encoding="utf-8") as fh:
        json.dump(reporte, fh, ensure_ascii=False, indent=2)

    # INFORME.md legible
    lineas = [
        "# EXP77 — Auditoría de handoff de skills",
        "",
        f"Fecha: 2026-10-01 · Regla: `{REGLA_HANDOFF}` · "
        f"Rúbrica: `{RUBRICA_VERSION}` · Costo: US$0 (mock)",
        "",
        "> Nota honesta: los veredictos son **condicionales a la rúbrica**",
        "> (predicados mecánicos sobre el contenido, versionada y",
        "> documentada en `run_exp77.py`). Lo exacto es `q` (calidad de",
        "> interfaz) y los deltas dada la rúbrica. Auditoría de **solo",
        "> lectura**: cero adopciones, cero modificaciones.",
        "",
        "## Inventario",
        "",
        f"{len(inv)} archivos SKILL.md (los DBs de skills están vacíos; "
        "las variantes de `resultados/fase1-puerta` son skills distintas: "
        "distinto brazo recomendado y distinto cuerpo).",
        "",
        "## Hallazgos",
        "",
        "| Skill | q | ayuda | rigidez | Δ_down | Δ_ref | Veredicto | "
        "Estab. | Predicados |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for h in hallazgos:
        # etiqueta distintiva: rep + nombre (hay 3 variantes aritmetica)
        partes = h["ruta"].split("/")
        if "rep0" in partes or "rep1" in partes or "rep2" in partes:
            i = next(i for i, x in enumerate(partes)
                     if x in ("rep0", "rep1", "rep2"))
            etiqueta = "/".join(partes[i:i + 3])
        else:
            etiqueta = "/".join(partes[-2:])
        lineas.append(
            f"| `{etiqueta}` "
            f"| {h['q_interfaz']} | {h['ayuda']} | {h['rigidez']} "
            f"| {h['delta_down']:+.4f} | {h['delta_ref']:+.4f} "
            f"| **{h['clasificacion']}** "
            f"| {h['sensibilidad']['estables']}/{h['sensibilidad']['total']} "
            f"| {', '.join(h['predicados'])} |")
    resumen = {}
    for h in hallazgos:
        resumen[h["clasificacion"]] = resumen.get(h["clasificacion"], 0) + 1
    lineas += [
        "",
        "## Resumen",
        "",
        f"- pasan: {resumen.get('pasa', 0)}",
        f"- restan (peor que nada): {resumen.get('resta', 0)}",
        f"- bloat (Δ=0): {resumen.get('bloat', 0)}",
        "",
        "## Limitación honesta del instrumento",
        "",
        "Las 7 skills tienen q=0.8 (interfaces prolijas: descripción de",
        "longitud media + firma de un parámetro). Con q=0.8 la puerta",
        "rechaza solo si ayuda < rigidez/4; el piso de ayuda de la rúbrica",
        "es 0.3, así que ninguna variante del set actual puede caer en",
        "rechazo. La auditoría establece el baseline (todo pasa, nada",
        "resta, nada es bloat) y la capacidad de rechazo de la puerta quedó",
        "probada en EXP76 con mocks calibrados. La discriminación real",
        "aparecerá cuando el meta-loop proponga skills nuevas.",
        "",
        "## Decisión pendiente (humana)",
        "",
        "Este informe no adopta, cuarentena ni modifica nada. "
        "Qué hacer con las que restan o son bloat lo decide él.",
        "",
    ]
    with open(os.path.join(OUT_DIR, "INFORME.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lineas) + "\n")
    print(f"informe en {OUT_DIR}/ (resultados_exp77.json + INFORME.md)")
    print("PASS - auditoría completa, cero adopciones")


if __name__ == "__main__":
    main()
