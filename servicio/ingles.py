"""Dominio inglés del servicio ALMA.

ALMA elige el método de estudio de inglés con Thompson sampling sobre el
historial del usuario. Sin LLM, sin costo de API: pura selección con
evidencia — es el loop medir→aprender→elegir aplicado a su rutina.

- Brazos = métodos de práctica (METODOS).
- Recompensa = auto-reporte nocturno 1..5 → (p-1)/4 en [0,1].
- Prior warm con olvido 0.5^días (misma maquinaria validada en EXP9):
  lo reciente pesa más; si un método deja de rendir, se olvida.
- Persistencia: la misma SQLite del servicio, clase="ingles". El motor
  principal la ignora al reconstruir priors (esos brazos no están en su
  repertorio), así que no hay interferencia.

Flujo nocturno:
  1. /ingles/recomendar → método para mañana (Thompson), guarda la
     experiencia con reward=None y anota el pendiente en
     ingles_pendiente.json.
  2. /ingles/puntuar {metodo_id, puntaje 1-5, nota} → si el método
     coincide con el pendiente de hoy, el feedback cierra esa
     experiencia; si hizo otro método, se registra directo con el
     reward conocido. En ambos casos el historial aprende.
"""

import json
import os
import random
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from alma.selector import SelectorArquitecturas  # noqa: E402
from store_sqlite import SQLiteStore  # noqa: E402

CLASE = "ingles"
BASE_OLVIDO = 0.5
PENDIENTE_FN = "ingles_pendiente.json"

METODOS = (
    {
        "id": "conversacion",
        "nombre": "Conversación (5 min)",
        "detalle": "Charlamos en inglés sobre tu día. Te corrijo al final, en español cuando haga falta.",
    },
    {
        "id": "podcast_3pasos",
        "nombre": "Podcast en 3 pasos",
        "detalle": "Escuchás el episodio, leés la transcripción y lo re-escuchás. Con subtítulos sí o sí.",
    },
    {
        "id": "shadowing",
        "nombre": "Shadowing (5 min)",
        "detalle": "Repetís en voz alta pegado al audio, sin pausar. Oído y pronunciación juntos.",
    },
    {
        "id": "frases_utiles",
        "nombre": "10 frases útiles",
        "detalle": "Frases de todos los días: las repetís y las usás en mini-diálogos.",
    },
    {
        "id": "dictado",
        "nombre": "Dictado corto",
        "detalle": "Escuchás 5 frases y las escribís. Después corregimos juntos.",
    },
    {
        "id": "otro",
        "nombre": "Otro (libre)",
        "detalle": "Lo que se te ocurra: serie, música, leer en voz alta. Contame qué fue.",
    },
)

IDS = [m["id"] for m in METODOS]
POR_ID = {m["id"]: m for m in METODOS}


def puntaje_a_reward(puntaje):
    """1..5 → [0,1]. 1 = no rindió nada, 5 = rindió al máximo."""
    p = int(puntaje)
    if p < 1 or p > 5:
        raise ValueError("puntaje: 1 a 5")
    return (p - 1) / 4.0


class Ingles:
    def __init__(self, db_path, seed=7):
        self.store = SQLiteStore(db_path)
        self._rng = random.Random(seed)
        self._lock = threading.Lock()
        self._dir = os.path.dirname(os.path.abspath(__file__))

    # -- estado pendiente -------------------------------------------------
    def _pendiente_path(self):
        return os.path.join(self._dir, PENDIENTE_FN)

    def _leer_pendiente(self):
        try:
            with open(self._pendiente_path(), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _guardar_pendiente(self, experiencia_id, metodo_id):
        with open(self._pendiente_path(), "w", encoding="utf-8") as f:
            json.dump(
                {"experiencia_id": experiencia_id,
                 "metodo_id": metodo_id,
                 "fecha": time.strftime("%Y-%m-%d")},
                f,
            )

    def _limpiar_pendiente(self):
        try:
            os.remove(self._pendiente_path())
        except OSError:
            pass

    # -- bandit ------------------------------------------------------------
    def _bandit(self):
        """Reconstruye el bandit desde la DB en cada llamada: sin estado
        en memoria, a prueba de reinicios."""
        sel = SelectorArquitecturas(arch_ids=IDS)
        bandit = sel._bandit(CLASE)
        ahora = time.time()
        for arch_id, reward, ts in self.store.recompensas_por_clase(CLASE):
            if arch_id not in bandit.alpha:
                continue
            dias = max(0.0, (ahora - ts) / 86400.0)
            peso = BASE_OLVIDO ** dias
            bandit.alpha[arch_id] += reward * peso
            bandit.beta[arch_id] += (1.0 - reward) * peso
            bandit.pulls[arch_id] += 1
        return sel, bandit

    def _resumen(self, bandit):
        total = sum(bandit.pulls.values())
        mejor = max(IDS, key=lambda a: bandit.mean(a))
        return {
            "medias": bandit.means(),
            "pulls": dict(bandit.pulls),
            "practicas_registradas": total,
            "mejor_hasta_ahora": POR_ID[mejor]["nombre"],
            "mejor_media_5": round(bandit.mean(mejor) * 4 + 1, 1),
        }

    # -- API ---------------------------------------------------------------
    def recomendar(self):
        """Método para mañana. Thompson sampling sobre el historial."""
        with self._lock:
            sel, bandit = self._bandit()
            metodo_id = sel.select(CLASE, self._rng)
            fila = self.store.append_experiencia({
                "problema_id": f"ingles-{time.strftime('%Y%m%d')}",
                "clase": CLASE,
                "arch_id": metodo_id,
                "config": {"metodo": metodo_id},
                "features": {},
                "respuesta": "",
                "traza": "recomendacion thompson",
                "metricas": {"reward": None},  # aprende con el puntaje
                "costo_usd": 0.0,
                "fase": "ingles:recomendar",
                "origen": "servicio-ingles",
            })
            self._guardar_pendiente(fila["id"], metodo_id)
            out = {"metodo": POR_ID[metodo_id],
                   "experiencia_id": fila["id"]}
            out.update(self._resumen(bandit))
            return out

    def puntuar(self, metodo_id, puntaje, nota=""):
        """Registra la práctica de hoy con su puntaje 1-5."""
        if metodo_id not in POR_ID:
            raise ValueError(
                f"método desconocido: {metodo_id} "
                f"(usá uno de: {', '.join(IDS)})")
        reward = puntaje_a_reward(puntaje)
        hoy = time.strftime("%Y-%m-%d")
        with self._lock:
            pendiente = self._leer_pendiente()
            if (pendiente and pendiente.get("metodo_id") == metodo_id
                    and pendiente.get("fecha") == hoy):
                # Hizo lo recomendado: el feedback cierra esa experiencia.
                fid = self.store.append_feedback(
                    pendiente["experiencia_id"], reward, nota)
                self._limpiar_pendiente()
                return {"via": "feedback",
                        "experiencia_id": pendiente["experiencia_id"],
                        "feedback_id": fid, "reward": reward,
                        "metodo": POR_ID[metodo_id]["nombre"]}
            # Hizo otro método (o el pendiente venció): registro directo.
            if pendiente:
                self._limpiar_pendiente()
            fila = self.store.append_experiencia({
                "problema_id": f"ingles-{time.strftime('%Y%m%d')}",
                "clase": CLASE,
                "arch_id": metodo_id,
                "config": {"metodo": metodo_id},
                "features": {},
                "respuesta": nota[:500],
                "traza": "registro directo",
                "metricas": {"reward": reward},
                "costo_usd": 0.0,
                "fase": "ingles:registrar",
                "origen": "servicio-ingles",
            })
            return {"via": "registro_directo",
                    "experiencia_id": fila["id"], "reward": reward,
                    "metodo": POR_ID[metodo_id]["nombre"]}

    def estado(self):
        with self._lock:
            _sel, bandit = self._bandit()
            out = self._resumen(bandit)
            out["pendiente"] = self._leer_pendiente()
            return out
