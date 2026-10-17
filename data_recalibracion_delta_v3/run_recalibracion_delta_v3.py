"""Recalibración de δ — VERSIÓN 3 — EJECUCIÓN del pre-registro
preregistro-recalibracion-delta-v3-2026-10-16.md (autorizado por
Alejandro, «Corre», 16/10/2026, reafirmado). Mock US$0, local: NO
toca el servicio, NO toca gate.py, NO evalúa candidatos, NO corre
el meta-loop. Sigue el documento (§7) al pie de la letra:

- Paso 0: auditoría de determinismo (10 evaluaciones frescas del
  scaffold base sobre [0,1,2]+[3,4]); cualquier diferencia detiene
  TODO. Se asienta la duración medida.
- Paso 1: pool fresco [4000..4029]. La virginidad se verificó ANTES
  de esta corrida con el barrido amplio de §5.6 (árbol completo,
  375 archivos JSON/JSONL; únicos hits: índices GSM8K declarados en
  §5.6, maquinaria ajena; pool sin hits) — detalle en
  barrido_virginidad.json de esta carpeta. σ̂_pool = sd entre
  réplicas (ddof=1), estimado UNA SOLA VEZ; σ_usado =
  max(σ̂_pool, 9,04) SOLO para el piso de adopción (§2.2).
  CLÁUSULA DE RÉGIMEN: σ̂_pool > 11,30 (= 1,25 × 9,04) → se detiene
  la corrida; no se adopta ningún número (§7 Paso 1, §8).
- Paso 2: control A — método original EXP-piso-ruido, panel 3/2,
  B = 5000, z = 2,0, semilla 12345 (misma mecánica y mismo orden de
  llamadas al RNG que las corridas v1/v2). Debe reproducir
  0,5331 ± 0,02 (escala δ); si no, se detiene TODO.
- Paso 3: validación H4, especificación de la v3 (§2.2) —
  (a) piso empírico A/A por sorteo de paneles disjuntos a panel 3/2
  desde el pool del Paso 1, mecánica de la v1 (default_rng(12345);
  choice(30, 10, replace=False); partición idx[0:5]/idx[5:10],
  train 0:3 y ho 3:5 contra train 5:8 y ho 8:10);
  (b) δ_P(3/2) paramétrico con σ̂_pool (SIN regla max).
  Deben coincidir dentro de ±0,10 (escala δ). Si la validación
  cae → rareza (§8): se detiene, no se adopta nada.
  Referencia INFORMATIVA (NO es puerta, §2.2): δ_P(3/2) con
  σ_usado, reportado contra el 0,5623 de la v1.
- Paso 4: δ_P(18/12) paramétrico con σ_usado. Solo si cae en
  (0,25 ; 0,30]: δ_P(24/16) con el mismo σ_usado y la misma
  mecánica (§7 Paso 4, §8).

Diseño P (§5.4): sorteos Δ_in ~ N(0, 2σ²/n_in), Δ_ho ~ N(0, 2σ²/n_ho)
independientes (σ en TOTALES), s = max(Δ_in, Δ_ho), δ = 2,0·sd(s)
(ddof=1), B = 5000, semilla 12345. Mecánica de sorteo (la de la
v2): por cada panel, un default_rng(12345) fresco; primero Δ_in
completo (rng.normal(0, sd_in, 5000)), después Δ_ho
(rng.normal(0, sd_ho, 5000)). Los pisos nacen en totales;
conversión a escala δ: ÷ 24, escrita junto a cada resultado.
La tabla de decisión (§8) se aplica en el documento de resultados;
acá se computan los pisos y los flags.
"""
import sys, os, json, time
import numpy as np

BASE = "/home/hatch/workspace/alma-prototype"
sys.path.insert(0, BASE)
sys.path.insert(0, BASE + "/exp56_rso")
import run_experiment47 as e47
import run_experiment56 as e56
from alma_service.scaffold import DEFAULT_SCAFFOLD

OUT = BASE + "/data_recalibracion_delta_v3"
os.makedirs(OUT, exist_ok=True)
RES = {"fecha": "2026-10-16",
       "preregistro": BASE + "/preregistro-recalibracion-delta-v3-2026-10-16.md",
       "preregistro_md5": "5d4d51875850c160fde4cf30d15f1239",
       "B": 5000, "z": 2.0, "seed": 12345,
       "escala_delta": "media por bloque (totales / 24)"}

TRAIN_REPS = [0, 1, 2]
HELDOUT_REPS = [3, 4]
POOL_IDS = list(range(4000, 4030))
PANEL_PRIMARIO = {"train": list(range(400, 418)),
                  "heldout": list(range(600, 612)), "e3": [500, 501]}
PANEL_ESCALON = {"train": list(range(400, 424)),
                 "heldout": list(range(600, 616)), "e3": [500, 501]}
DELTA_VIGENTE = 0.5331
TOL_A = 0.02
SIGMA_V1 = 9.04
UMBRAL_REGIMEN = 11.30
TOL_H4 = 0.10
PISO_V1_3_2 = 0.5623

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
    with open(OUT + "/resultados.json", "w", encoding="utf-8") as f:
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

t_eval = float(np.mean(tiempos_eval))
# Estimación del protocolo completo (§7 Paso 0): Paso 0 (hecho) + 30
# réplicas del pool + bootstrap de bloques (control A) + sorteo
# empírico + sorteos paramétricos (aritmética numpy).
t_pool_est = 30 * (t_eval / 5.0)
dur_est = t_paso0 + t_pool_est + 10.0  # 10 s holgados de bootstrap
RES["paso0"] = {
    "identicas_10_de_10": identicas,
    "max_diferencia_absoluta": max_dif,
    "reg_pol_base": {str(r): ref_regs[r] for r in TRAIN_REPS + HELDOUT_REPS},
    "duracion_evaluacion_completa_s": round(t_eval, 4),
    "duracion_paso0_s": round(t_paso0, 3),
    "duracion_protocolo_estimada_s": round(dur_est, 2),
    "umbral_1h_superado": bool(dur_est > 3600),
}
print(f"[paso 0] identicas={identicas} max_dif={max_dif} "
      f"eval_completa={t_eval:.3f}s dur_est_protocolo={dur_est:.1f}s",
      flush=True)
if not identicas:
    print("[paso 0] HALLAZGO: no-determinismo. SE DETIENE TODO (§9).",
          flush=True)
    guardar("DETENIDO_PASO_0")
    sys.exit(2)

# ================= Paso 1 — Pool fresco y σ̂ =================
print("[paso 1] evaluando pool fresco [4000..4029] ...", flush=True)
t0 = time.time()
pool_regs_d, pool_bloques_d = evaluar_fresco(BASE_SC, POOL_IDS)
t_pool = time.time() - t0
pool_regs = np.array([pool_regs_d[r] for r in POOL_IDS], dtype=float)
sigma_hat = float(np.std(pool_regs, ddof=1))
var_entre = float(np.var(pool_regs, ddof=1))
sigma_usado = max(sigma_hat, SIGMA_V1)
regimen = bool(sigma_hat > UMBRAL_REGIMEN)

mat_pool = np.array([pool_bloques_d[r] for r in POOL_IDS], dtype=float)
var_bloques_pool = [float(np.var(mat_pool[i], ddof=1)) for i in range(30)]
regs5 = np.array([ref_regs[r] for r in TRAIN_REPS + HELDOUT_REPS],
                 dtype=float)
RES["pool"] = {"ids": POOL_IDS,
               "reg_pol": {str(r): pool_regs_d[r] for r in POOL_IDS},
               "duracion_s": round(t_pool, 3),
               "virginidad": "barrido amplio de §5.6 repetido antes "
                             "de correr (375 archivos JSON/JSONL del "
                             "árbol completo, 373 parseados; los 2 no "
                             "parseables inspeccionados en texto): "
                             "pool 0 hits; panel solo hits GSM8K "
                             "declarados en §5.6 (maquinaria ajena). "
                             "Detalle: barrido_virginidad.json"}
RES["paso1"] = {
    "varianza_entre_bloques_dentro_de_replica_pool": {
        "media": float(np.mean(var_bloques_pool)),
        "sd_bloques_tipica": float(np.sqrt(np.mean(var_bloques_pool))),
    },
    "varianza_entre_replicas_del_reg_pol": {
        "pool_fresco_30": {"varianza": var_entre, "sd": sigma_hat,
                           "media": float(np.mean(pool_regs))},
        "panel_historico_5_referencia": {
            "varianza": float(np.var(regs5, ddof=1)),
            "sd": float(np.std(regs5, ddof=1)),
            "media": float(np.mean(regs5))},
    },
    "varianza_medicion_repetida": 0.0,
    "varianza_medicion_repetida_nota": "Paso 0: 10/10 idénticas, "
                                       "max_dif = 0 (H2 verificada)",
    "varianza_juez_en_el_camino_del_delta": 0.0,
    "varianza_juez_nota": "0 por construcción: no hay LLM en el camino "
                          "del Δ (§11.1); se declara, no se estima",
    "sigma_hat": round(sigma_hat, 4),
    "sigma_usado": round(sigma_usado, 4),
    "regla_sigma": "σ_usado = max(σ̂_pool, 9,04) SOLO para el piso de "
                   "adopción; la validación (Paso 3) usa σ̂_pool sin "
                   "max (§2.2)",
    "clausula_regimen": {
        "umbral": UMBRAL_REGIMEN,
        "sigma_hat_supera_umbral": regimen,
    },
}
print(f"[paso 1] sigma_hat={sigma_hat:.4f} sigma_usado={sigma_usado:.4f} "
      f"regimen={regimen}", flush=True)
if regimen:
    print("[paso 1] σ̂ EN RÉGIMEN (> 11,30): se detiene la corrida; "
          "no se adopta ningún número (§7 Paso 1, §8).", flush=True)
    guardar("DETENIDO_REGIMEN_PASO_1")
    sys.exit(4)

# ================= Paso 2 — Control A (método original, B=5000) =================
# Réplica exacta del bootstrap de data_exppisorruido/mock_piso_ruido.py
# con la mecánica ejecutada en la v1/v2 (mismo orden de llamadas al
# RNG), B=5000 (§7 Paso 2).
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
print(f"[paso 2] delta_A={delta_A:.4f} (vigente 0.5331, "
      f"desvio {abs(delta_A - DELTA_VIGENTE):.4f})", flush=True)
if abs(delta_A - DELTA_VIGENTE) > TOL_A:
    print("[paso 2] A NO REPRODUCE: se detiene todo antes de mirar "
          "cualquier otro piso (§7 Paso 2, §9).", flush=True)
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


# ================= Paso 3 — Validación H4 (especificación §2.2) =================
# (a) Empírico A/A a panel 3/2 desde el pool de 30, mecánica de la v1.
print("[paso 3a] empirico A/A panel 3/2 desde el pool, B=5000 ...",
      flush=True)
t0 = time.time()
rng = np.random.default_rng(12345)
s_e, din_e, dho_e = [], [], []
for _ in range(5000):
    idx = rng.choice(30, size=10, replace=False)
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
    "mecanica_sorteo": "rng.choice(30, size=10, replace=False); "
                       "P=idx[0:5] (train 0:3, ho 3:5), Q=idx[5:10] "
                       "(train 5:8, ho 8:10); default_rng(12345) — "
                       "mecánica de la v1, pool de 30 (§7 Paso 3)",
}
print(f"[paso 3a] delta_empirico_3_2={delta_emp:.4f} (escala δ) "
      f"= {delta_emp_tot:.4f} totales", flush=True)

# (b) Paramétrico a panel 3/2 con σ̂_pool (SIN regla max, §2.2 punto 1).
print("[paso 3b] parametrico P(3/2) con sigma_hat del pool ...", flush=True)
p32_hat = piso_parametrico(3, 2, sigma_hat)
delta_P32_hat = p32_hat["delta_escala_delta"]
RES["paso3b_parametrico_3_2_sigma_hat"] = p32_hat

# Referencia INFORMATIVA (no puerta, §2.2): paramétrico con σ_usado.
print("[paso 3c] parametrico P(3/2) con sigma_usado (informativo) ...",
      flush=True)
p32_usado = piso_parametrico(3, 2, sigma_usado)
delta_P32_usado = p32_usado["delta_escala_delta"]
RES["paso3c_parametrico_3_2_sigma_usado_informativo"] = p32_usado

dif_h4 = abs(delta_emp - delta_P32_hat)
h4_ok = bool(dif_h4 <= TOL_H4)
RES["paso3_validacion_H4"] = {
    "empirico_escala_delta": round(delta_emp, 4),
    "parametrico_sigma_hat_escala_delta": round(delta_P32_hat, 4),
    "diferencia_absoluta": round(dif_h4, 4),
    "tolerancia": TOL_H4,
    "valida": h4_ok,
    "especificacion": "§2.2 de la v3: paramétrico con σ̂_pool vs "
                      "empírico del MISMO pool (mismo pool, mismo σ)",
    "referencia_informativa_no_puerta": {
        "parametrico_sigma_usado_escala_delta": round(delta_P32_usado, 4),
        "piso_v1_3_2": PISO_V1_3_2,
        "desvio_vs_v1": round(abs(delta_P32_usado - PISO_V1_3_2), 4),
        "empirico_vs_v1": round(abs(delta_emp - PISO_V1_3_2), 4),
    },
}
print(f"[paso 3] H4 (v3): empirico={delta_emp:.4f} "
      f"parametrico(σ̂)={delta_P32_hat:.4f} dif={dif_h4:.4f} "
      f"(tol ±0,10) valida={h4_ok} | informativo: "
      f"parametrico(σ_usado)={delta_P32_usado:.4f} vs v1 0.5623 "
      f"(desvío {abs(delta_P32_usado - PISO_V1_3_2):.4f})", flush=True)
if not h4_ok:
    print("[paso 3] VALIDACIÓN H4 CAÍDA (especificación §2.2) → "
          "rareza (§8): no se adopta nada por la vía paramétrica. "
          "Se detiene la corrida.", flush=True)
    guardar("RARO_H4_NO_VALIDA")
    sys.exit(5)

# ================= Paso 4 — δ_P(18/12) con σ_usado =================
print("[paso 4] parametrico P(18/12) con sigma_usado ...", flush=True)
p1812 = piso_parametrico(18, 12, sigma_usado)
delta_P1812 = p1812["delta_escala_delta"]
RES["paso4_parametrico_18_12"] = p1812
print(f"[paso 4] delta_P(18/12)={delta_P1812:.4f} (escala δ) "
      f"= {p1812['delta_totales']:.4f} totales", flush=True)

delta_P2416 = None
p2416 = None
if 0.25 < delta_P1812 <= 0.30:
    print("[paso 4] zona inconclusa (0,25; 0,30]: se evalúa el "
          "escalón 24/16 pre-declarado (§5.5, §8) ...", flush=True)
    p2416 = piso_parametrico(24, 16, sigma_usado)
    delta_P2416 = p2416["delta_escala_delta"]
    RES["paso4_parametrico_24_16"] = p2416
    print(f"[paso 4] delta_P(24/16)={delta_P2416:.4f} (escala δ) "
          f"= {p2416['delta_totales']:.4f} totales", flush=True)

# ================= Hipótesis y flags de decisión (§6, §8) =================
pisos = [delta_A, delta_emp, delta_P32_hat, delta_P32_usado,
         delta_P1812]
if delta_P2416 is not None:
    pisos.append(delta_P2416)
RES["hipotesis"] = {
    "H1_prima_piso_18_12_menor_o_igual_0.25": bool(delta_P1812 <= 0.25),
    "H2_varianza_medicion_cero": True,
    "H3_sd_ho_mayor_sd_in": {
        "control_A": bool(RES["paso2_control_A"]["sd_d_ho"]
                          > RES["paso2_control_A"]["sd_d_in"]),
        "empirico_3_2": bool(RES["paso3a_empirico_3_2"]["sd_d_ho_totales"]
                             > RES["paso3a_empirico_3_2"]["sd_d_in_totales"]),
        "parametrico_18_12": bool(p1812["sd_d_ho_totales"]
                                  > p1812["sd_d_in_totales"]),
    },
    "H4_validacion_estimador_v3": h4_ok,
}
RES["flags_decision"] = {
    "delta_P_18_12": round(delta_P1812, 4),
    "delta_P_24_16": (round(delta_P2416, 4)
                      if delta_P2416 is not None else None),
    "rama_18_12": ("adoptar_primario" if delta_P1812 <= 0.25 else
                   ("zona_inconclusa" if delta_P1812 <= 0.30
                    else "archivar_estructural")),
    "adoptado_segun_tabla": None,  # se resuelve abajo
    "rareza_piso_a_adoptar_mayor_o_igual_delta_A": False,
    "rareza_algun_piso_menor_0.05": bool(min(pisos) < 0.05),
    "sigma_hat_en_regimen": regimen,
    "H4_valida": h4_ok,
}
# Resolución de la tabla (§8) con cláusulas de rareza.
candidato_delta, candidato_panel, candidato_ids = None, None, None
if delta_P1812 <= 0.25:
    candidato_delta, candidato_panel, candidato_ids = \
        delta_P1812, "18/12", PANEL_PRIMARIO
elif delta_P1812 <= 0.30 and delta_P2416 is not None and delta_P2416 <= 0.25:
    candidato_delta, candidato_panel, candidato_ids = \
        delta_P2416, "24/16", PANEL_ESCALON
if candidato_delta is not None:
    if candidato_delta >= delta_A:
        RES["flags_decision"]["rareza_piso_a_adoptar_mayor_o_igual_delta_A"] = True
        candidato_delta, candidato_panel, candidato_ids = None, None, None
    elif RES["flags_decision"]["rareza_algun_piso_menor_0.05"]:
        candidato_delta, candidato_panel, candidato_ids = None, None, None
if candidato_delta is not None:
    RES["flags_decision"]["adoptado_segun_tabla"] = {
        "delta_nuevo_escala_delta": round(candidato_delta, 4),
        "delta_nuevo_totales": round(candidato_delta * 24.0, 4),
        "panel": candidato_panel,
        "ids_train": candidato_ids["train"],
        "ids_heldout": candidato_ids["heldout"],
        "ids_e3_sin_cambio": candidato_ids["e3"],
    }
guardar("PISOS_COMPUTADOS")
print(f"[fin] A={delta_A:.4f} emp={delta_emp:.4f} "
      f"P(3/2,σ̂)={delta_P32_hat:.4f} P(18/12)={delta_P1812:.4f}"
      + (f" P(24/16)={delta_P2416:.4f}" if delta_P2416 is not None else "")
      + f" en {time.time() - t_inicio:.1f}s", flush=True)
