#!/usr/bin/env python3
"""Runner de ALMA-EXP18: 4 seeds con API real, secuenciales, con freno de costo.

Lee las seeds de resultados/exp18-20260926/preregistro.json (pre-registradas
ANTES de correr). Tras cada seed verifica el gasto acumulado: si supera
US$0,80 no inicia la siguiente (freno duro total US$1,00).
Al final aplica la regla de confiabilidad pre-registrada (rango > 1,0 ->
NO CONFIABLE) y escribe reporte-exp18.json + veredictos-exp18.md.
"""
import json
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
EXP_DIR = os.path.join(BASE, "resultados", "exp18-20260926")
FRENO_TOTAL = 1.00
FRENO_PREVENTIVO = 0.80
TIMEOUT_SEED_S = 4200  # 70 min por seed (EXP12: ~37 min)


def cargar_prereg():
    with open(os.path.join(EXP_DIR, "preregistro.json"), encoding="utf-8") as f:
        return json.load(f)


def gasto_acumulado(seeds_hechas):
    total = 0.0
    for s in seeds_hechas:
        rp = os.path.join(EXP_DIR, f"seed{s}", "report.json")
        if os.path.exists(rp):
            with open(rp, encoding="utf-8") as f:
                total += json.load(f).get("costo_total_usd", 0.0)
    return total


def correr_seed(seed):
    out = os.path.join(EXP_DIR, f"seed{seed}")
    log = os.path.join(EXP_DIR, f"seed{seed}.log")
    cmd = [sys.executable, os.path.join(BASE, "run_experiment12.py"),
           "--api", "--seed", str(seed), "--out", out]
    print(f"\n===== seed {seed}: lanzando ({' '.join(cmd)}) =====", flush=True)
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as lf:
        proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                              timeout=TIMEOUT_SEED_S, cwd=BASE)
    dur = time.time() - t0
    rp = os.path.join(out, "report.json")
    if not os.path.exists(rp):
        raise RuntimeError(f"seed {seed}: no se generó report.json "
                           f"(rc={proc.returncode}, ver {log})")
    with open(rp, encoding="utf-8") as f:
        rep = json.load(f)
    print(f"===== seed {seed}: fin rc={proc.returncode} "
          f"costo=${rep.get('costo_total_usd', 0):.4f} "
          f"detenido={rep.get('detenido_por_costo')} "
          f"pasa={rep['veredicto']['pasa']} ({dur:.0f}s) =====", flush=True)
    return rep


def main():
    prereg = cargar_prereg()
    seeds = prereg["diseno"]["seeds_pre_registradas"]
    assert seeds == [1821, 1822, 1823, 1824], "seeds no coinciden con preregistro"
    print(f"EXP18: seeds pre-registradas {seeds}", flush=True)

    resultados = {}
    detenida = None
    for seed in seeds:
        gastado = gasto_acumulado(list(resultados.keys()))
        print(f"gasto acumulado antes de seed {seed}: ${gastado:.4f}", flush=True)
        if gastado > FRENO_PREVENTIVO:
            detenida = (f"FRENO de costo: acumulado ${gastado:.4f} > "
                        f"${FRENO_PREVENTIVO:.2f} preventivo "
                        f"(duro ${FRENO_TOTAL:.2f}). No se inicia seed {seed}.")
            print(detenida, flush=True)
            break
        rep = correr_seed(seed)
        if rep.get("detenido_por_costo"):
            detenida = (f"seed {seed} detenida por su freno interno de costo.")
            print(detenida, flush=True)
            resultados[str(seed)] = {"detenida": True, "report": rep}
            break
        rt = rep["regret_total"]
        mejor_fija = min(a for a in ("single", "cot", "reflexion"))
        reg_fijas = {a: rt[f"fija_{a}"] for a in ("single", "cot", "reflexion")}
        mejor = min(reg_fijas, key=lambda a: reg_fijas[a])
        resultados[str(seed)] = {
            "regret_alma": rt["alma"],
            "regret_fijas": reg_fijas,
            "mejor_fija": mejor,
            "pasa": bool(rep["veredicto"]["pasa"]),
            "costo_usd": rep.get("costo_total_usd"),
            "duracion_s": rep.get("duracion_s"),
        }

    regs = [r["regret_alma"] for r in resultados.values()
            if "regret_alma" in r]
    reporte = {
        "experimento": "ALMA-EXP18",
        "preregistro": "resultados/exp18-20260926/preregistro.json",
        "seeds": resultados,
        "gasto_total_usd": round(gasto_acumulado(
            [int(s) for s in resultados]), 4),
        "detenida_por_costo": detenida,
    }
    if regs and len(regs) == len(seeds):
        rango = max(regs) - min(regs)
        pasan = [s for s, r in resultados.items() if r["pasa"]]
        if rango > 1.0:
            veredicto = "NO CONFIABLE"
        elif len(pasan) == len(seeds):
            veredicto = "PASS"
        else:
            veredicto = "FAIL"
        reporte["rango_regret_alma"] = round(rango, 4)
        reporte["veredicto_global"] = veredicto
        reporte["motivo"] = (
            f"regrets alma por seed: "
            f"{', '.join(f'{s}={resultados[s]['regret_alma']:.4f}' for s in sorted(resultados))}; "
            f"rango={rango:.4f} (umbral 1,0); "
            f"pasan {len(pasan)}/{len(seeds)} seeds.")
    else:
        reporte["veredicto_global"] = "INCOMPLETO"
        reporte["motivo"] = detenida or "no se completaron las 4 seeds"

    with open(os.path.join(EXP_DIR, "reporte-exp18.json"), "w",
              encoding="utf-8") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    with open(os.path.join(EXP_DIR, "veredictos-exp18.md"), "w",
              encoding="utf-8") as f:
        f.write("# ALMA-EXP18 — veredictos\n\n")
        f.write(f"Fecha: {time.strftime('%Y-%m-%dT%H:%M:%S')}\n\n")
        f.write("Pregunta: ¿ALMA le gana a la mejor brazo fijo? "
                "(4 seeds, API real, oráculo re-medido por seed)\n\n")
        for s in sorted(resultados, key=int):
            r = resultados[s]
            if "regret_alma" in r:
                f.write(f"- seed {s}: regret alma={r['regret_alma']:.4f} vs "
                        f"mejor fija ({r['mejor_fija']})={r['regret_fijas'][r['mejor_fija']]:.4f} "
                        f"→ {'PASS' if r['pasa'] else 'FAIL'} "
                        f"(costo ${r['costo_usd']:.4f})\n")
            else:
                f.write(f"- seed {s}: DETENIDA\n")
        f.write(f"\nVeredicto global: **{reporte['veredicto_global']}**\n\n")
        f.write(reporte["motivo"] + "\n")
        if "rango_regret_alma" in reporte:
            f.write(f"\nRegla de confiabilidad pre-registrada: rango "
                    f"{reporte['rango_regret_alma']:.4f} vs umbral 1,0.\n")

    print("\n================ EXP18 TERMINADO ================", flush=True)
    print(f"veredicto global: {reporte['veredicto_global']}", flush=True)
    print(reporte["motivo"], flush=True)
    print(f"gasto total: ${reporte['gasto_total_usd']:.4f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
