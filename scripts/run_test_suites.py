#!/usr/bin/env python3
"""Run root-level ALMA test scripts, classifying each suite by its exit code.

Usage:
    python scripts/run_test_suites.py
    python scripts/run_test_suites.py --tests-dir .

No third-party dependencies. Each suite runs in its own subprocess.
Exit code: 0 only when every discovered suite passes.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

def classify(returncode: int, output: str) -> tuple[str, str]:
    # BLOCKED: la suite ni siquiera pudo ejecutar (import/archivo ausente).
    lines = output.splitlines()
    for line in lines:
        if "ModuleNotFoundError" in line or re.search(r"\bImportError\b", line):
            return "BLOCKED", "Falta un módulo/import requerido."
    # PASS/FAIL se decide SOLO por el código de salida, no por el texto
    # impreso: una suite puede imprimir líneas «FAIL» a propósito como parte
    # de su propia demostración (p. ej. test_exp77_auditoria ejercita el
    # camino fail-closed del auditor y muestra los rechazos que produce).
    # Escanear el texto marcaba esa suite como FAIL aunque terminara con
    # código 0 y todos sus checks en verde.
    if returncode != 0:
        return "FAIL", f"El proceso terminó con código {returncode}."
    return "PASS", "Código de salida 0."


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tests-dir",
        default=".",
        help="Directorio con scripts test_*.py (default: raíz actual).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Timeout por suite, en segundos (default: 180).",
    )
    parser.add_argument(
        "--json",
        default="test-results.json",
        help="Ruta del resumen JSON (default: test-results.json).",
    )
    args = parser.parse_args()

    tests_dir = Path(args.tests_dir).resolve()
    scripts = sorted(p for p in tests_dir.glob("test_*.py") if p.is_file())
    if not scripts:
        print(f"ERROR: no se encontraron test_*.py en {tests_dir}", file=sys.stderr)
        return 2

    results = []
    print(f"ALMA test runner — {len(scripts)} suites — {tests_dir}")
    print("=" * 78)

    for script in scripts:
        started = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(tests_dir),
                capture_output=True,
                text=True,
                timeout=args.timeout,
                check=False,
            )
            output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            status, reason = classify(proc.returncode, output)
            returncode = proc.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            output = stdout + "\n" + stderr
            status, reason, returncode = "FAIL", f"Timeout tras {args.timeout}s.", None

        duration = round(time.monotonic() - started, 3)
        result = {
            "suite": script.name,
            "status": status,
            "reason": reason,
            "duration_seconds": duration,
            "returncode": returncode,
            "output_tail": output[-4000:],
        }
        results.append(result)
        print(f"[{status:7}] {script.name} ({duration}s) — {reason}")

    counts = {
        status: sum(1 for result in results if result["status"] == status)
        for status in ("PASS", "FAIL", "BLOCKED")
    }
    summary = {
        "tests_dir": str(tests_dir),
        "python": sys.version,
        "total": len(results),
        "counts": counts,
        "results": results,
    }
    output_path = Path(args.json).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=" * 78)
    print(f"Total: {len(results)} | PASS: {counts['PASS']} | FAIL: {counts['FAIL']} | BLOCKED: {counts['BLOCKED']}")
    print(f"JSON: {output_path}")
    return 0 if counts["FAIL"] == 0 and counts["BLOCKED"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
