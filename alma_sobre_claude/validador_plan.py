# -*- coding: utf-8 -*-
"""Validador congelado v1 de la batería de pantalla del plan matutino.

Programa «ALMA sobre Muse» — pre-registro
preregistro-alma-sobre-claude-2026-10-17.md §7.2. Determinista, sin juez
LLM, solo stdlib. CONGELADO: este archivo no se toca a mitad de ciclo;
cambiarlo es un ciclo nuevo con su papel.

Puntúa un plan (texto) contra el registro del día en corpus_planes.jsonl
con 7 chequeos binarios. Puntaje = pasados / aplicables.
"""
import re
import unicodedata

VERSION = "v1"


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _segmentos(texto):
    """Devuelve (marcadores, [seg1, seg2, seg3]) cortando en '1)' '2)' '3)'."""
    marcas = [(m.start(), int(m.group(1)), m.end())
              for m in re.finditer(r"([123])\)\s", texto)]
    segs = []
    for i, (_, _, fin) in enumerate(marcas):
        hasta = marcas[i + 1][0] if i + 1 < len(marcas) else len(texto)
        segs.append(texto[fin:hasta])
    return [d for _, d, _ in marcas], segs


def _montos(texto):
    """Montos US$ como floats normalizados (miles con '.', decimal con ',')."""
    out = set()
    for m in re.finditer(r"US\$\s*([0-9][0-9.,]*)", texto):
        tok = m.group(1).rstrip(".,")
        if "," in tok and "." in tok:
            tok = tok.replace(".", "").replace(",", ".")
        elif "," in tok:
            tok = tok.replace(",", ".")
        elif re.fullmatch(r"[0-9]+\.[0-9]{3}", tok):
            tok = tok.replace(".", "")
        out.add(round(float(tok), 2))
    return out


_GUARDA = re.compile(
    r"(reserva|disponible|sin gasto|no esencial|no gastar|vence|"
    r"vencimiento|paga|pagar)")


def puntuar(texto, dia):
    """Devuelve dict C1..C7 con True/False/None (None = no aplicable)."""
    t = norm(texto)
    marcas, segs = _segmentos(texto)
    top = dia["compromiso_top"]
    kws = [norm(k) for k in top["keywords"]]
    r = {}

    # C1 formato: exactamente 1) 2) 3) en orden, sin preguntas.
    r["C1"] = (marcas == [1, 2, 3]) and ("?" not in texto) and ("¿" not in texto)
    # C2 cobertura del compromiso que ata el día.
    r["C2"] = any(k in t for k in kws)
    # C3 horario del compromiso, si lo tuvo.
    if top.get("horario_tokens"):
        r["C3"] = any(norm(tok) in t or tok in texto
                      for tok in top["horario_tokens"])
    else:
        r["C3"] = None
    # C4 ancla factible (y ninguna infactible), si el día tenía ancla aplicable.
    if dia.get("c4_aplicable"):
        ok = any(norm(k) in t for k in dia["ancla_factible"])
        mal = any(norm(k) in t for k in dia["ancla_infactible"])
        r["C4"] = bool(ok and not mal)
    else:
        r["C4"] = None
    # C5 sin invenciones de plata: todo monto del plan está en el paquete.
    r["C5"] = _montos(texto) <= _montos(dia["paquete"])
    # C6 guarda de plata, si la plata era crítica ese día.
    if dia.get("plata_critica"):
        r["C6"] = bool(_GUARDA.search(t))
    else:
        r["C6"] = None
    # C7 liderazgo: el punto 1 es el compromiso que ata el día.
    r["C7"] = bool(segs) and any(k in norm(segs[0]) for k in kws)

    aplicables = [v for v in r.values() if v is not None]
    r["puntaje"] = (sum(1 for v in aplicables if v) / len(aplicables)
                    if aplicables else 0.0)
    return r
