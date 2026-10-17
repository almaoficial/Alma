"""Recalibración de δ — CICLO L1 — EJECUCIÓN del pre-registro
preregistro-L1-panel-grande-2026-10-16.md (commit fa7cb8f;
autorizado por Alejandro, «Corre», 16/10/2026 — adelanta la
ventana declarada: su orden manda). Mock US$0, local: NO toca
gate.py, NO toca el panel cableado, NO evalúa candidatos, NO
corre el meta-loop, NO desbloquea el freno.

Metodología v3 heredada tal cual (pre-registro L1 §5), cambiando
solo el panel y el pool:

- Paso 0: auditoría de determinismo (10 evaluaciones frescas del
  scaffold base sobre [0,1,2]+[3,4]); identidad exacta y ancla
  reg_pol = 71/83/90/84/81; cualquier diferencia detiene TODO.
- Paso 1: pool fresco [23000..23059] (60 réplicas; virginidad
  re-verificada HOY con el barrido amplio de §4 del pre-registro:
  0 hits en posición de réplica en los cuatro rangos; único hit
  declarado: 23039 como /prompt_tokens, maquinaria ajena).
  σ̂_pool = sd entre réplicas (ddof=1), estimado UNA SOLA VEZ;
  σ_usado = max(σ̂_pool, 9,04) SOLO para el piso de adopción.
  CLÁUSULA DE RÉGIMEN: σ̂_pool > 11,30 → se detiene; no se adopta
  ningún número.
- Paso 2: control A — método original EXP-piso-ruido, panel 3/2,
  B = 5000, z = 2,0, semilla 12345 (misma mecánica y mismo orden
  de llamadas al RNG que v1/v2/v3). Debe reproducir
  0,5331 ± 0,02 (escala δ); si no, se detiene TODO.
- Paso 3: validación (§5 del pre-registro L1; especificación
  §2.2 de la v3) — (a) piso empírico A/A por sorteo de paneles
  disjuntos a panel 3/2 desde el pool del Paso 1 (mecánica de la
  v1 adaptada al pool de 60: default_rng(12345);
  choice(60, 10, replace=False); partición idx[0:5]/idx[5:10],
  train 0:3 y ho 3:5 contra train 5:8 y ho 8:10);
  (b) δ_P(3/2) paramétrico con σ̂_pool (SIN regla max).
  Deben coincidir dentro de ±0,10 (escala δ). Si la validación
  cae → rareza (§6.2): se detiene, no se adopta nada.
  Referencia INFORMATIVA (NO es puerta): δ_P(3/2) con σ_usado,
  reportado contra el 0,5623 de la v1.
- Paso 4: δ_P(72/48) paramétrico con σ_usado. SIN escalón (§6.1):
  no hay panel mayor esperando bajo este papel.

Diseño P: sorteos Δ_in ~ N(0, 2σ²/n_in), Δ_ho ~ N(0, 2σ²/n_ho)
independientes (σ en TOTALES), s = max(Δ_in, Δ_ho),
δ = 2,0·sd(s) (ddof=1), B = 5000, semilla 12345. Mecánica: por
cada panel, un default_rng(12345) fresco; primero Δ_in completo,
después Δ_ho. Conversión a escala δ: totales / 24, escrita junto
a cada resultado.

Decisión (§6.1 del pre-registro L1): δ_L1 se adopta si y solo si
(1) la validación pasa en su especificación, (2) ninguna rareza
de §6.2 se dispara, y (3) δ_P(72/48) < 0,2283.
"""
import sys, os, json, time
import numpy as np

BASE = "/home/hatch/workspace/alma-prototype"
sys.path.insert(0, BASE)
sys.path.insert(0, BASE + "/exp56_rso")
import run_experiment47 as e47
import run_experiment56 as e56
from alma_service.scaffold import DEFAULT_SCAFFOLD

OUT = BASE + "/data_L1_2026-10-16"
os.makedirs(OUT, exist_ok=True)
RES = {"fecha": "2026-10-16",
       "preregistro": BASE + "/preregistro-L1-panel-grande-2026-10-16.md",
       "preregistro_commit": "fa7cb8f",
       "ciclo": "L1",
       "B": 5000, "z": 2.0, "seed": 12345,
       "escala_delta": "media por bloque (totales / 24)"}

TRAIN_REPS = [0, 1, 2]
HELDOUT_REPS = [3, 4]
POOL_IDS = list(range(23000, 23060))          # 60 réplicas
PANEL_NUEVO = {"train": list(range(20000, 20072)),
               "heldout": list(range(21000, 21048)),
               "e3": list(range(22000, 22024))}
DELTA_VIGENTE = 0.5331          # referencia del control A
DELTA_ADOPTADO_V3 = 0.2283      # δ vigente a superar (§6.1(3))
TOL_A = 0.02
SIGMA_V1 = 9.04
UMBRAL_REGIMEN = 11.30
TOL_H4 = 0.10
PISO_V1_3_2 = 0.5623
REGS_ANCLA = [71.0, 83.0, 90.0, 84.0, 81.0]

t_inicio = time.time()
items = e47.construir_stream()
tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
BASE_SC = dict(DEFAULT_SCAFFOLD)


def evaluar_fresco(scaffold, replicas):
    """Sin caché: una llamada real por réplica."""
    regs, bloques = {}, {}
    for r in replicas:
        rr = e56.correr_replica_param(r, items, tasas, dict(scaffold))
        regs[r] = rr["reg_pol"]
        bloques[r] = list(rr["reg_pol_bloques"])
    return regs, bloques


def guardar(estado):
    RES["estado"] = estado
    RES["duracion_total_s"] = round(time.time() - t_inicio, 3)
    with open(OUT + "/recalibracion_resultados.json", "w",
              encoding="utf-8") as f:
        json.dump(RES, f, indent=2, ensure_ascii=False)


# ================= Paso 0 — Auditoría de determinismo =================
print("[paso 0] 10 evaluaciones frescas del scaffold base ...", flush=True)
t0 = time.time()
corridas = []
tiempos_eval = []
for k in range(10):
    te = time.time()
    regs, bloques = evaluar_fresco(BASE_SC, TRAIN_REPS + HELDOUT_REPS)
    tiempos_eval.append(time.time() - te)
    corridas.append((regs, bloques))
t_paso0 = time.time() - t0

ref_regs, ref_bloques = corridas[0]
max_dif = 0.0
identicas = True
for regs, bloques in corridas[1:]:
    for r in TRAIN_REPS + HELDOUT_REPS:
        if regs[r] != ref_regs[r]:
            identicas = False
            max_dif = max(max_dif, abs(regs[r] - ref_regs[r]))
        for a, b in zip(bloques[r], ref_bloques[r]):
            if a != b:
                identicas = False
                max_dif = max(max_dif, abs(a - b))
ancla_ok = [ref_regs[r] for r in TRAIN_REPS + HELDOUT_REPS] == REGS_ANCLA

t_eval = float(np.mean(tiempos_eval))
t_pool_est = 60 * (t_eval / 5.0)
dur_est = t_paso0 + t_pool_est + 10.0
RES["paso0"] = {
    "identicas_10_de_10": identicas,
    "ancla_reg_pol_esperada": REGS_ANCLA,
    "ancla_reproduce": ancla_ok,
    "max_diferencia_absoluta": max_dif,
    "reg_pol_base": {str(r): ref_regs[r] for r in TRAIN_REPS + HELDOUT_REPS},
    "duracion_evaluacion_completa_s": round(t_eval, 4),
    "duracion_paso0_s": round(t_paso0, 3),
    "duracion_protocolo_estimada_s": round(dur_est, 2),
    "umbral_1h_superado": bool(dur_est > 3600),
}
print(f"[paso 0] identicas={identicas} ancla={ancla_ok} max_dif={max_dif} "
      f"eval_completa={t_eval:.3f}s dur_est_protocolo={dur_est:.1f}s",
      flush=True)
if not identicas or not ancla_ok:
    print("[paso 0] HALLAZGO: no-determinismo o ancla caída. "
          "SE DETIENE TODO (§5 del pre-registro).", flush=True)
    guardar("DETENIDO_PASO_0")
    sys.exit(2)

# ================= Paso 1 — Pool fresco y σ̂ =================
print("[paso 1] evaluando pool fresco [23000..23059] (60) ...", flush=True)
t0 = time.time()
pool_regs_d, pool_bloques_d = evaluar_fresco(BASE_SC, POOL_IDS)
t_pool = time.time() - t0
pool_regs = np.array([pool_regs_d[r] for r in POOL_IDS], dtype=float)
sigma_hat = float(np.std(pool_regs, ddof=1))
var_entre = float(np.var(pool_regs, ddof=1))
sigma_usado = max(sigma_hat, SIGMA_V1)
regimen = bool(sigma_hat > UMBRAL_REGIMEN)

mat_pool = np.array([pool_bloques_d[r] for r in POOL_IDS], dtype=float)
var_bloques_pool = [float(np.var(mat_pool[i], ddof=1)) for i in range(60)]
regs5 = np.array([ref_regs[r] for r in TRAIN_REPS + HELDOUT_REPS],
                 dtype=float)
RES["pool"] = {"ids": POOL_IDS,
               "reg_pol": {str(r): pool_regs_d[r] for r in POOL_IDS},
               "duracion_s": round(t_pool, 3),
               "virginidad": "barrido amplio de §4 del pre-registro "
                             "REPETIDO hoy antes de ejecutar (402 "
                             "archivos JSON/JSONL, 400 parseados, los "
                             "2 no parseables inspeccionados por "
                             "texto): los cuatro rangos L1 con 0 hits "
                             "en posición de réplica; controles "
                             "EXP64b y pool v3 detectados; único hit "
                             "declarado: 23039 como /prompt_tokens "
                             "(maquinaria ajena). Detalle: "
                             "barrido_virginidad_ejecucion.json"}
RES["paso1"] = {
    "varianza_entre_bloques_dentro_de_replica_pool": {
        "media": float(np.mean(var_bloques_pool)),
        "sd_bloques_tipica": float(np.sqrt(np.mean(var_bloques_pool))),
    },
    "varianza_entre_replicas_del_reg_pol": {
        "pool_fresco_60": {"varianza": var_entre, "sd": sigma_hat,
                           "media": float(np.mean(pool_regs))},
        "panel_historico_5_referencia": {
            "varianza": float(np.var(regs5, ddof=1)),
            "sd": float(np.std(regs5, ddof=1)),
            "media": float(np.mean(regs5))},
    },
    "varianza_medicion_repetida": 0.0,
    "varianza_medicion_repetida_nota": "Paso 0: 10/10 idénticas, "
                                       "max_dif = 0",
    "varianza_juez_en_el_camino_del_delta": 0.0,
    "varianza_juez_nota": "0 por construcción: no hay LLM en el camino "
                          "del Δ; se declara, no se estima",
    "sigma_hat": round(sigma_hat, 4),
    "sigma_usado": round(sigma_usado, 4),
    "regla_sigma": "σ_usado = max(σ̂_pool, 9,04) SOLO para el piso de "
                   "adopción; la validación (Paso 3) usa σ̂_pool sin "
                   "max (especificación §2.2 de la v3, heredada)",
    "clausula_regimen": {
        "umbral": UMBRAL_REGIMEN,
        "sigma_hat_supera_umbral": regimen,
    },
}
print(f"[paso 1] sigma_hat={sigma_hat:.4f} sigma_usado={sigma_usado:.4f} "
      f"regimen={regimen}", flush=True)
if regimen:
    print("[paso 1] σ̂ EN RÉGIMEN (> 11,30): se detiene la corrida; "
          "no se adopta ningún número (§5, §6.2).", flush=True)
    guardar("DETENIDO_REGIMEN_PASO_1")
    sys.exit(4)

# ================= Paso 2 — Control A (método original, B=5000) =================
print("[paso 2] control A: bootstrap metodo original B=5000 ...", flush=True)
t0 = time.time()
arr = {r: np.array(ref_bloques[r], dtype=float)
       for r in TRAIN_REPS + HELDOUT_REPS}
rng = np.random.default_rng(12345)
s_null, din_null, dho_null = [], [], []
nblo = 24
for _ in range(5000):
    din_r, dho_r = [], []
    for r in TRAIN_REPS + HELDOUT_REPS:
        a = arr[r]
        m1 = a[rng.integers(0, nblo, nblo)].mean()
        m2 = a[rng.integers(0, nblo, nblo)].mean()
        d = m1 - m2
        (din_r if r in TRAIN_REPS else dho_r).append(d)
    din = float(np.mean(din_r)); dho = float(np.mean(dho_r))
    din_null.append(din); dho_null.append(dho)
    s_null.append(max(din, dho))
s_null = np.array(s_null)
delta_A = 2.0 * float(s_null.std(ddof=1))
RES["paso2_control_A"] = {
    "delta_A_escala_delta": round(delta_A, 4),
    "sd_s": round(float(s_null.std(ddof=1)), 4),
    "sd_d_in": round(float(np.std(din_null, ddof=1)), 4),
    "sd_d_ho": round(float(np.std(dho_null, ddof=1)), 4),
    "duracion_s": round(time.time() - t0, 3),
    "reproduce_0.5331": bool(abs(delta_A - DELTA_VIGENTE) <= TOL_A),
    "desvio_vs_0.5331": round(abs(delta_A - DELTA_VIGENTE), 4),
}
print(f"[paso 2] delta_A={delta_A:.4f} (referencia 0.5331, "
      f"desvio {abs(delta_A - DELTA_VIGENTE):.4f})", flush=True)
if abs(delta_A - DELTA_VIGENTE) > TOL_A:
    print("[paso 2] A NO REPRODUCE: se detiene todo antes de mirar "
          "cualquier otro piso (§5).", flush=True)
    guardar("INVALIDADA_A_NO_REPRODUCE")
    sys.exit(3)


# ================= Diseño P (paramétrico) =================
def piso_parametrico(n_in, n_ho, sigma):
    """δ_P(n_in/n_ho) con σ en totales. Retorna dict con ambas escalas."""
    sd_in = sigma * np.sqrt(2.0 / n_in)
    sd_ho = sigma * np.sqrt(2.0 / n_ho)
    r = np.random.default_rng(12345)
    din = r.normal(0.0, sd_in, 5000)
    dho = r.normal(0.0, sd_ho, 5000)
    s = np.maximum(din, dho)
    sd_s = float(s.std(ddof=1))
    delta_tot = 2.0 * sd_s
    return {
        "sd_d_in_totales": round(float(din.std(ddof=1)), 4),
        "sd_d_ho_totales": round(float(dho.std(ddof=1)), 4),
        "sd_in_teorico_totales": round(float(sd_in), 4),
        "sd_ho_teorico_totales": round(float(sd_ho), 4),
        "sd_s_totales": round(sd_s, 4),
        "delta_totales": round(delta_tot, 4),
        "delta_escala_delta": round(delta_tot / 24.0, 4),
        "mecanica": "default_rng(12345) fresco; Δ_in = normal(0, "
                    "σ√(2/n_in), 5000), luego Δ_ho = normal(0, "
                    "σ√(2/n_ho), 5000); s = max; δ = 2·sd(s) ddof=1; "
                    "escala δ = totales / 24",
    }


# ================= Paso 3 — Validación (especificación §2.2 de la v3) =================
# (a) Empírico A/A a panel 3/2 desde el pool de 60, mecánica de la v1.
print("[paso 3a] empirico A/A panel 3/2 desde el pool de 60, B=5000 ...",
      flush=True)
t0 = time.time()
rng = np.random.default_rng(12345)
s_e, din_e, dho_e = [], [], []
for _ in range(5000):
    idx = rng.choice(60, size=10, replace=False)
    d_in = float(np.mean(pool_regs[idx[0:3]]) - np.mean(pool_regs[idx[5:8]]))
    d_ho = float(np.mean(pool_regs[idx[3:5]]) - np.mean(pool_regs[idx[8:10]]))
    din_e.append(d_in); dho_e.append(d_ho)
    s_e.append(max(d_in, d_ho))
s_e = np.array(s_e)
delta_emp_tot = 2.0 * float(s_e.std(ddof=1))
delta_emp = delta_emp_tot / 24.0
RES["paso3a_empirico_3_2"] = {
    "delta_totales": round(delta_emp_tot, 4),
    "delta_escala_delta": round(delta_emp, 4),
    "sd_s_totales": round(float(s_e.std(ddof=1)), 4),
    "sd_d_in_totales": round(float(np.std(din_e, ddof=1)), 4),
    "sd_d_ho_totales": round(float(np.std(dho_e, ddof=1)), 4),
    "duracion_s": round(time.time() - t0, 3),
    "mecanica_sorteo": "rng.choice(60, size=10, replace=False); "
                       "P=idx[0:5] (train 0:3, ho 3:5), Q=idx[5:10] "
                       "(train 5:8, ho 8:10); default_rng(12345) — "
                       "mecánica de la v1 adaptada al pool de 60 "
                       "del ciclo L1",
}
print(f"[paso 3a] delta_empirico_3_2={delta_emp:.4f} (escala δ) "
      f"= {delta_emp_tot:.4f} totales", flush=True)

# (b) Paramétrico a panel 3/2 con σ̂_pool (SIN regla max).
print("[paso 3b] parametrico P(3/2) con sigma_hat del pool ...", flush=True)
p32_hat = piso_parametrico(3, 2, sigma_hat)
delta_P32_hat = p32_hat["delta_escala_delta"]
RES["paso3b_parametrico_3_2_sigma_hat"] = p32_hat

# Referencia INFORMATIVA (no puerta): paramétrico con σ_usado.
print("[paso 3c] parametrico P(3/2) con sigma_usado (informativo) ...",
      flush=True)
p32_usado = piso_parametrico(3, 2, sigma_usado)
delta_P32_usado = p32_usado["delta_escala_delta"]
RES["paso3c_parametrico_3_2_sigma_usado_informativo"] = p32_usado

dif_h4 = abs(delta_emp - delta_P32_hat)
h4_ok = bool(dif_h4 <= TOL_H4)
RES["paso3_validacion"] = {
    "empirico_escala_delta": round(delta_emp, 4),
    "parametrico_sigma_hat_escala_delta": round(delta_P32_hat, 4),
    "diferencia_absoluta": round(dif_h4, 4),
    "tolerancia": TOL_H4,
    "valida": h4_ok,
    "especificacion": "§5 del pre-registro L1 (especificación §2.2 "
                      "de la v3): paramétrico con σ̂_pool vs "
                      "empírico del MISMO pool (mismo pool, mismo σ)",
    "referencia_informativa_no_puerta": {
        "parametrico_sigma_usado_escala_delta": round(delta_P32_usado, 4),
        "piso_v1_3_2": PISO_V1_3_2,
        "desvio_vs_v1": round(abs(delta_P32_usado - PISO_V1_3_2), 4),
        "empirico_vs_v1": round(abs(delta_emp - PISO_V1_3_2), 4),
    },
}
print(f"[paso 3] validacion: empirico={delta_emp:.4f} "
      f"parametrico(σ̂)={delta_P32_hat:.4f} dif={dif_h4:.4f} "
      f"(tol ±0,10) valida={h4_ok} | informativo: "
      f"parametrico(σ_usado)={delta_P32_usado:.4f} vs v1 0.5623 "
      f"(desvío {abs(delta_P32_usado - PISO_V1_3_2):.4f})", flush=True)
if not h4_ok:
    print("[paso 3] VALIDACIÓN CAÍDA en su especificación → "
          "rareza (§6.2): no se adopta nada. Se detiene la corrida.",
          flush=True)
    guardar("RARO_VALIDACION_NO_PASA")
    sys.exit(5)

# ================= Paso 4 — δ_P(72/48) con σ_usado =================
print("[paso 4] parametrico P(72/48) con sigma_usado ...", flush=True)
p7248 = piso_parametrico(72, 48, sigma_usado)
delta_P7248 = p7248["delta_escala_delta"]
RES["paso4_parametrico_72_48"] = p7248
print(f"[paso 4] delta_P(72/48)={delta_P7248:.4f} (escala δ) "
      f"= {p7248['delta_totales']:.4f} totales", flush=True)

# ================= Hipótesis y decisión (§6 del pre-registro L1) =================
pisos = [delta_A, delta_emp, delta_P32_hat, delta_P32_usado,
         delta_P7248]
rareza_menor_005 = bool(min(pisos) < 0.05)
rareza_vs_A = bool(delta_P7248 >= delta_A)
cond3 = bool(delta_P7248 < DELTA_ADOPTADO_V3)
adopta = bool(h4_ok and not rareza_menor_005 and not rareza_vs_A
              and not regimen and cond3)
RES["hipotesis"] = {
    "H-L1-1_resolucion_delta_menor_0.2283": cond3,
    "H-L1-3_sd_ho_mayor_sd_in": {
        "empirico_3_2": bool(RES["paso3a_empirico_3_2"]["sd_d_ho_totales"]
                             > RES["paso3a_empirico_3_2"]["sd_d_in_totales"]),
        "parametrico_72_48": bool(p7248["sd_d_ho_totales"]
                                  > p7248["sd_d_in_totales"]),
    },
    "validacion_estimador": h4_ok,
}
RES["decision_seccion6"] = {
    "condicion_1_validacion_pasa": h4_ok,
    "condicion_2_sin_rarezas": bool(not rareza_menor_005
                                    and not rareza_vs_A
                                    and not regimen),
    "condicion_3_delta_P_72_48_menor_0.2283": cond3,
    "rareza_piso_a_adoptar_mayor_o_igual_delta_A": rareza_vs_A,
    "rareza_algun_piso_menor_0.05": rareza_menor_005,
    "sigma_hat_en_regimen": regimen,
    "delta_P_72_48_escala_delta": round(delta_P7248, 4),
    "delta_P_72_48_totales": p7248["delta_totales"],
    "adopta": adopta,
    "congelamiento_si_adopta": ({
        "delta_nuevo_escala_delta": round(delta_P7248, 4),
        "delta_nuevo_totales": p7248["delta_totales"],
        "panel": "72/48, E3 24",
        "ids_train": PANEL_NUEVO["train"],
        "ids_heldout": PANEL_NUEVO["heldout"],
        "ids_e3": PANEL_NUEVO["e3"],
    } if adopta else None),
}
guardar("ADOPTA" if adopta else "NO_ADOPTA")
print(f"[fin] A={delta_A:.4f} emp={delta_emp:.4f} "
      f"P(3/2,σ̂)={delta_P32_hat:.4f} P(72/48)={delta_P7248:.4f} "
      f"adopta={adopta} en {time.time() - t_inicio:.1f}s", flush=True)
