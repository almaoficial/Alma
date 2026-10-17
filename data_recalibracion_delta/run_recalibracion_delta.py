"""Recalibración de δ (piso de ruido) — EJECUCIÓN del pre-registro
preregistro-recalibracion-delta-2026-10-16.md (aprobado por Alejandro,
«Corre», 16/10/2026). Mock US$0, local, sobre copias: NO toca el
servicio, NO toca gate.py, NO evalúa candidatos, NO corre el meta-loop.

Sigue el documento al pie de la letra:
- Paso 0: auditoría de determinismo (10 evaluaciones idénticas del
  scaffold base; cualquier diferencia detiene TODO).
- Paso 1: descomposición de fuentes de varianza.
- Paso 2: tres pisos con s = max(Δ_in, Δ_ho), δ = z·sd(s*), z = 2,0,
  B = 5000, semilla 12345.
  A = método original (debe reproducir 0,5331 ± 0,02; si no, se
      detiene todo ANTES de mirar B o C).
  B = nulo A/A pareado entre paneles disjuntos, pool [1000..1019],
      panel actual 3/2.
  C = nulo A/A pareado, panel ampliado 6/4, mismo pool.
- §5: reglas de decisión y rareza (se aplican en el documento de
  resultados; acá se computan los pisos y los flags).
"""
import sys, os, json, time
import numpy as np

BASE = "/home/hatch/workspace/alma-prototype"
sys.path.insert(0, BASE)
sys.path.insert(0, BASE + "/exp56_rso")
import run_experiment47 as e47
import run_experiment56 as e56
from alma_service.scaffold import DEFAULT_SCAFFOLD

OUT = BASE + "/data_recalibracion_delta"
os.makedirs(OUT, exist_ok=True)
RES = {"fecha": "2026-10-16",
       "preregistro": BASE + "/preregistro-recalibracion-delta-2026-10-16.md",
       "B": 5000, "z": 2.0, "seed": 12345}

TRAIN_REPS = [0, 1, 2]
HELDOUT_REPS = [3, 4]
POOL_IDS = list(range(1000, 1020))
DELTA_VIGENTE = 0.5331
TOL_A = 0.02

t_inicio = time.time()
items = e47.construir_stream()
tasas = json.load(open(e47.TASAS_PATH, encoding="utf-8"))
BASE_SC = dict(DEFAULT_SCAFFOLD)


def evaluar_fresco(scaffold, replicas):
    """Sin caché: una llamada real por réplica (para el Paso 0)."""
    regs, bloques = {}, {}
    for r in replicas:
        rr = e56.correr_replica_param(r, items, tasas, dict(scaffold))
        regs[r] = rr["reg_pol"]
        bloques[r] = list(rr["reg_pol_bloques"])
    return regs, bloques


_cache = {}
def evaluar(scaffold, replicas):
    key = (tuple(sorted(scaffold.items())), tuple(replicas))
    if key not in _cache:
        _cache[key] = evaluar_fresco(scaffold, replicas)
    return _cache[key]


def guardar(estado):
    RES["estado"] = estado
    RES["duracion_total_s"] = round(time.time() - t_inicio, 3)
    with open(OUT + "/resultados.json", "w", encoding="utf-8") as f:
        json.dump(RES, f, indent=2, ensure_ascii=False)


# ================= Paso 0 — Auditoría de determinismo =================
print("[paso 0] 10 evaluaciones identicas del scaffold base ...", flush=True)
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
# Estimación del protocolo completo (§7): Paso 0 (hecho) + 20 réplicas
# del pool + bootstraps (aritmética numpy sobre arreglos ya calculados).
t_pool_est = 20 * (t_eval / 5.0)
dur_est = t_paso0 + t_pool_est + 5.0  # 5 s holgados de bootstrap
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
    print("[paso 0] HALLAZGO: no-determinismo. SE DETIENE TODO.", flush=True)
    guardar("DETENIDO_PASO_0")
    sys.exit(2)

# ================= Pool fresco [1000..1019] =================
t0 = time.time()
pool_regs, pool_bloques = evaluar(BASE_SC, POOL_IDS)
t_pool = time.time() - t0
RES["pool"] = {"ids": POOL_IDS,
               "reg_pol": {str(r): pool_regs[r] for r in POOL_IDS},
               "duracion_s": round(t_pool, 3)}
print(f"[pool] 20 replicas evaluadas en {t_pool:.2f}s", flush=True)

# ================= Paso 1 — Descomposición de fuentes =================
mat = np.array([ref_bloques[r] for r in TRAIN_REPS + HELDOUT_REPS],
               dtype=float)  # 5 x 24
var_bloques_intra = [float(np.var(mat[i], ddof=1)) for i in range(5)]
regs5 = np.array([ref_regs[r] for r in TRAIN_REPS + HELDOUT_REPS],
                 dtype=float)
regs_pool = np.array([pool_regs[r] for r in POOL_IDS], dtype=float)
RES["paso1"] = {
    "varianza_entre_bloques_dentro_de_replica": {
        "por_replica": {str(r): var_bloques_intra[i]
                        for i, r in enumerate(TRAIN_REPS + HELDOUT_REPS)},
        "media": float(np.mean(var_bloques_intra)),
        "sd_bloques_tipica": float(np.sqrt(np.mean(var_bloques_intra))),
    },
    "varianza_entre_replicas_del_reg_pol": {
        "panel_historico_5": {"varianza": float(np.var(regs5, ddof=1)),
                              "sd": float(np.std(regs5, ddof=1)),
                              "media": float(np.mean(regs5))},
        "pool_20": {"varianza": float(np.var(regs_pool, ddof=1)),
                    "sd": float(np.std(regs_pool, ddof=1)),
                    "media": float(np.mean(regs_pool))},
    },
    "varianza_medicion_repetida": 0.0,
    "varianza_medicion_repetida_nota": "Paso 0: 10/10 idénticas, "
                                       "max_dif = 0 (H2 verificada)",
    "varianza_juez_en_el_camino_del_delta": 0.0,
    "varianza_juez_nota": "0 por construcción: no hay LLM en el camino "
                          "del Δ (pre-registro §2); se declara, no se estima",
}
print("[paso 1] descomposicion asentada", flush=True)

# ================= Paso 2A — Control (método original, B=5000) =================
# Réplica exacta del bootstrap de data_exppisorruido/mock_piso_ruido.py
# (mismo orden de llamadas al RNG), con B=5000 en vez de 2000 (§4).
print("[paso 2A] bootstrap metodo original B=5000 ...", flush=True)
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
RES["paso2A"] = {
    "delta_A": round(delta_A, 4),
    "sd_s": round(float(s_null.std(ddof=1)), 4),
    "sd_d_in": round(float(np.std(din_null, ddof=1)), 4),
    "sd_d_ho": round(float(np.std(dho_null, ddof=1)), 4),
    "duracion_s": round(time.time() - t0, 3),
    "reproduce_0.5331": bool(abs(delta_A - DELTA_VIGENTE) <= TOL_A),
    "desvio_vs_0.5331": round(abs(delta_A - DELTA_VIGENTE), 4),
}
print(f"[paso 2A] delta_A={delta_A:.4f} (vigente 0.5331, "
      f"desvio {abs(delta_A - DELTA_VIGENTE):.4f})", flush=True)
if abs(delta_A - DELTA_VIGENTE) > TOL_A:
    print("[paso 2A] A NO REPRODUCE: se detiene todo antes de B/C.",
          flush=True)
    guardar("INVALIDADA_A_NO_REPRODUCE")
    sys.exit(3)

# ================= Paso 2B — Nulo pareado A/A, panel 3/2 =================
# Mecánica de sorteo (declarada): por draw, rng.choice(20, size=10,
# replace=False); panel P = idx[0:5] (train idx[0:3], held-out idx[3:5]),
# panel Q = idx[5:10] (train idx[5:8], held-out idx[8:10]). Disjuntos.
print("[paso 2B] nulo pareado A/A panel 3/2, B=5000 ...", flush=True)
t0 = time.time()
P = regs_pool  # reg_pol del scaffold base, ordenado por POOL_IDS
rng = np.random.default_rng(12345)
s_b, din_b, dho_b = [], [], []
for _ in range(5000):
    idx = rng.choice(20, size=10, replace=False)
    d_in = float(np.mean(P[idx[0:3]]) - np.mean(P[idx[5:8]]))
    d_ho = float(np.mean(P[idx[3:5]]) - np.mean(P[idx[8:10]]))
    din_b.append(d_in); dho_b.append(d_ho)
    s_b.append(max(d_in, d_ho))
s_b = np.array(s_b)
delta_B = 2.0 * float(s_b.std(ddof=1))
RES["paso2B"] = {
    "delta_B": round(delta_B, 4),
    "sd_s": round(float(s_b.std(ddof=1)), 4),
    "sd_d_in": round(float(np.std(din_b, ddof=1)), 4),
    "sd_d_ho": round(float(np.std(dho_b, ddof=1)), 4),
    "duracion_s": round(time.time() - t0, 3),
    "mecanica_sorteo": "rng.choice(20, size=10, replace=False); "
                       "P=idx[0:5] (train 0:3, ho 3:5), Q=idx[5:10] "
                       "(train 5:8, ho 8:10); default_rng(12345)",
}
print(f"[paso 2B] delta_B={delta_B:.4f}", flush=True)

# ================= Paso 2C — Nulo pareado A/A, panel 6/4 =================
# Mecánica de sorteo (declarada): por draw, permutación completa del
# pool, rng.choice(20, size=20, replace=False); panel P = idx[0:10]
# (train idx[0:6], held-out idx[6:10]), panel Q = idx[10:20]
# (train idx[10:16], held-out idx[16:20]). Nunca se comparte una
# réplica entre los dos lados de un mismo draw.
print("[paso 2C] nulo pareado A/A panel 6/4, B=5000 ...", flush=True)
t0 = time.time()
rng = np.random.default_rng(12345)
s_c, din_c, dho_c = [], [], []
for _ in range(5000):
    idx = rng.choice(20, size=20, replace=False)
    d_in = float(np.mean(P[idx[0:6]]) - np.mean(P[idx[10:16]]))
    d_ho = float(np.mean(P[idx[6:10]]) - np.mean(P[idx[16:20]]))
    din_c.append(d_in); dho_c.append(d_ho)
    s_c.append(max(d_in, d_ho))
s_c = np.array(s_c)
delta_C = 2.0 * float(s_c.std(ddof=1))
RES["paso2C"] = {
    "delta_C": round(delta_C, 4),
    "sd_s": round(float(s_c.std(ddof=1)), 4),
    "sd_d_in": round(float(np.std(din_c, ddof=1)), 4),
    "sd_d_ho": round(float(np.std(dho_c, ddof=1)), 4),
    "duracion_s": round(time.time() - t0, 3),
    "mecanica_sorteo": "rng.choice(20, size=20, replace=False) "
                       "(permutacion); P=idx[0:10] (train 0:6, ho 6:10), "
                       "Q=idx[10:20] (train 10:16, ho 16:20); "
                       "default_rng(12345)",
}
print(f"[paso 2C] delta_C={delta_C:.4f}", flush=True)

# ================= Hipótesis y flags de decisión (§3 y §5) =================
RES["hipotesis"] = {
    "H1_piso_reducido_al_menos_50pct": bool(
        delta_B <= 0.2666 or delta_C <= 0.2666),
    "H2_varianza_medicion_cero": True,
    "H3_sd_ho_mayor_sd_in": {
        "A": bool(RES["paso2A"]["sd_d_ho"] > RES["paso2A"]["sd_d_in"]),
        "B": bool(RES["paso2B"]["sd_d_ho"] > RES["paso2B"]["sd_d_in"]),
        "C": bool(RES["paso2C"]["sd_d_ho"] > RES["paso2C"]["sd_d_in"]),
        "brecha_B": round(RES["paso2B"]["sd_d_ho"]
                          - RES["paso2B"]["sd_d_in"], 4),
        "brecha_C": round(RES["paso2C"]["sd_d_ho"]
                          - RES["paso2C"]["sd_d_in"], 4),
        "brecha_se_achica_C_vs_B": bool(
            (RES["paso2C"]["sd_d_ho"] - RES["paso2C"]["sd_d_in"])
            < (RES["paso2B"]["sd_d_ho"] - RES["paso2B"]["sd_d_in"])),
    },
}
RES["flags_decision"] = {
    "delta_B_mayor_o_igual_delta_A": bool(delta_B >= delta_A),
    "algun_piso_menor_0.05": bool(min(delta_A, delta_B, delta_C) < 0.05),
    "delta_C_menor_o_igual_0.20": bool(delta_C <= 0.20),
    "delta_B_menor_o_igual_0.20": bool(delta_B <= 0.20),
    "menor_piso_BC": round(min(delta_B, delta_C), 4),
    "todos_BC_mayor_0.30": bool(delta_B > 0.30 and delta_C > 0.30),
}
guardar("PISOS_COMPUTADOS")
print(f"[fin] A={delta_A:.4f} B={delta_B:.4f} C={delta_C:.4f} "
      f"en {time.time() - t_inicio:.1f}s", flush=True)
