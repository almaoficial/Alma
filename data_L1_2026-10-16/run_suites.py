"""Corre la batería completa de suites (archivos test_*.py de la
raíz + alma_service/) de a un proceso por archivo, en el formato
de los suites.log previos: PASS/FAIL por archivo + resumen.
Uso: python3 run_suites.py <salida.log>
"""
import glob
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    salida = sys.argv[1]
    archivos = sorted(glob.glob(os.path.join(RAIZ, "test_*.py")) +
                      glob.glob(os.path.join(RAIZ, "alma_service",
                                             "test_*.py")))
    lineas = []
    npass = nfail = 0
    fallas = []
    t0 = time.time()
    for a in archivos:
        rel = os.path.relpath(a, RAIZ)
        try:
            p = subprocess.run([sys.executable, a], cwd=RAIZ,
                               capture_output=True, text=True,
                               timeout=600)
            ok = p.returncode == 0
        except subprocess.TimeoutExpired:
            ok = False
        lineas.append(("PASS " if ok else "FAIL ") + rel)
        if ok:
            npass += 1
        else:
            nfail += 1
            fallas.append(rel)
        print(lineas[-1], flush=True)
    lineas.append(f"RESUMEN: {npass} PASS / {nfail} FAIL / "
                  f"{len(archivos)} archivos / "
                  f"{time.time() - t0:.1f} s")
    if fallas:
        lineas.append("FALLAS: " + ", ".join(fallas))
    with open(salida, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    print(lineas[-2] if fallas else lineas[-1], flush=True)


if __name__ == "__main__":
    main()
