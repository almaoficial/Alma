#!/usr/bin/env python3
"""CLI del modo observador de ALMA.

Uso:
  python3 cliente_trazas.py registrar --tarea "..." --tipo investigacion \
      --estrategia "..." --herramientas deep_research,exec \
      --resultado ok --feedback 5 --nota "..."
  python3 cliente_trazas.py resumen
  python3 cliente_trazas.py listar [n]

tipos: investigacion | codigo | analisis | conversacion | otro
resultados: ok | fallo | parcial
feedback: 1-5 (opcional; la vara del mapa)
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trazas  # noqa: E402


def cmd_registrar(args):
    herramientas = [h.strip() for h in (args.herramientas or "").split(",")
                    if h.strip()]
    tid = trazas.registrar(
        tarea=args.tarea, tipo_tarea=args.tipo, estrategia=args.estrategia,
        herramientas=herramientas, resultado=args.resultado,
        feedback=args.feedback, nota=args.nota or "")
    print(f"Traza registrada: id {tid}.")


def cmd_resumen(_args):
    total = trazas.contar()
    print("=== Mapa de estrategias (modo observador) ===")
    print(f"{total} trazas registradas.\n")
    if total == 0:
        print("Sin datos todavía: el mapa arranca vacío.")
        return
    mapa = trazas.mapa()
    for tipo in sorted(mapa):
        n_tipo = sum(e["n"] for e in mapa[tipo])
        print(f"[{tipo}] ({n_tipo} trazas)")
        for i, e in enumerate(mapa[tipo], 1):
            fb = (f"{e['fb_medio']:.1f} (n={e['n_fb']})"
                  if e["fb_medio"] is not None else "sin feedback")
            print(f"  {i}. {e['estrategia']}")
            print(f"     n={e['n']}  feedback medio={fb}"
                  f"  tasa ok={e['tasa_ok']:.2f}")
        print()


def cmd_listar(args):
    rows = trazas.listar(args.n)
    if not rows:
        print("Sin trazas registradas.")
        return
    for r in rows:
        herr = ",".join(json.loads(r["herramientas"]))
        fb = r["feedback"] if r["feedback"] is not None else "-"
        print(f"#{r['id']} [{r['ts'][:16]}] {r['tipo_tarea']}/{r['resultado']}"
              f" fb={fb}")
        print(f"   tarea: {r['tarea']}")
        print(f"   estrategia: {r['estrategia']}")
        if herr:
            print(f"   herramientas: {herr}")
        if r["nota"]:
            print(f"   nota: {r['nota']}")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("registrar", help="registra una traza")
    r.add_argument("--tarea", required=True)
    r.add_argument("--tipo", required=True, choices=trazas.TIPOS)
    r.add_argument("--estrategia", required=True)
    r.add_argument("--herramientas", default="",
                   help="lista separada por comas")
    r.add_argument("--resultado", default="ok", choices=trazas.RESULTADOS)
    r.add_argument("--feedback", type=int, default=None,
                   help="1-5, opcional")
    r.add_argument("--nota", default="")
    r.set_defaults(fn=cmd_registrar)

    s = sub.add_parser("resumen", help="muestra el mapa aprendido")
    s.set_defaults(fn=cmd_resumen)

    li = sub.add_parser("listar", help="últimas trazas")
    li.add_argument("n", nargs="?", type=int, default=10)
    li.set_defaults(fn=cmd_listar)

    args = ap.parse_args(argv[1:])
    try:
        args.fn(args)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
