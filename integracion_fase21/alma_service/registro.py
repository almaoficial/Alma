#!/usr/bin/env python3
"""Registry de proveedores del router ALMA (fase 2.x).

El único lugar donde el router mira para decidir qué proveedor usar.
Cada proveedor se describe con metadata MEDIDA (reward y costo por celda
slice/brazo); las keys viven en el vault y nunca pasan por acá.

Reglas de seguridad:
  - Este módulo jamás lee, escribe, imprime ni recibe secretos. Solo IDs de
    proveedor/conector y estadísticas.
  - El health check usa un ping GRATUITO (GET /models) con el surrogate del
    vault (patrón de los skills): la credencial la reemplaza authd al salir.
  - Fail-closed: si ningún proveedor está disponible, `elegir` lanza
    SinProveedorDisponible en vez de inventar uno.

Uso:
    reg = RegistroProveedores("proveedores.yaml")
    print(reg.disponibles())      # chequea conectores, failover ante 401/403/404
    print(reg.elegir("gsm8k"))     # -> ("deepseek", "single")
"""

import datetime
import sys
import urllib.error
import urllib.request

import yaml

# ---------------------------------------------------------------- excepciones

class RegistryInvalido(ValueError):
    """El YAML no cumple el schema. Falla ruidoso al cargar."""


class SinProveedorDisponible(RuntimeError):
    """Fail-closed: ningún proveedor disponible para elegir."""


# ---------------------------------------------------------------- constantes

HTTP_AUTH_FALLOS = (401, 403, 404)  # voltean al proveedor a no_disponible
HEADER_GENERADO = (
    "# Registry de proveedores del router ALMA (fase 2.x) — reescrito por registro.py\n"
    "# Las keys viven en el vault; acá solo hay IDs y estadísticas medidas.\n"
    "# Procedencia de cada campaña en su campo `fuente`. Ver NOTA.md.\n"
)


def _hoy():
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------- ping real

def _ping_surrogate(proveedor):
    """GET gratuito al ping_url con auth por surrogate del vault.

    Lanza urllib.error.HTTPError / urllib.error.URLError /
    DynamicCredentialError según lo que falle. Nunca gasta tokens.
    """
    sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
    from dynamic_credentials import add_surrogate_to_request  # noqa: E402
    req = urllib.request.Request(proveedor["ping_url"], method="GET")
    add_surrogate_to_request(
        req,
        proveedor["connector"],
        entry_name=proveedor.get("credencial_entry", "access_token"),
        allowed_hosts=proveedor["hosts_permitidos"],
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read(1)  # basta con que responda 2xx


# ---------------------------------------------------------------- validación

def _exige(cond, mensaje):
    if not cond:
        raise RegistryInvalido(mensaje)


def _validar_celda(clave, celda, pid):
    _exige(isinstance(clave, str) and "/" in clave,
           f"[{pid}] clave de celda inválida: {clave!r} (formato 'slice/brazo')")
    sl, brazo = clave.split("/", 1)
    _exige(sl.strip() and brazo.strip(),
           f"[{pid}] celda {clave!r}: slice o brazo vacío")
    _exige(isinstance(celda, dict), f"[{pid}] celda {clave!r}: debe ser un mapeo")
    for campo in ("n", "reward_medio", "costo_medio_usd"):
        _exige(campo in celda, f"[{pid}] celda {clave!r}: falta {campo!r}")
    _exige(isinstance(celda["n"], int) and celda["n"] > 0,
           f"[{pid}] celda {clave!r}: n debe ser entero > 0")
    _exige(isinstance(celda["reward_medio"], (int, float))
           and 0.0 <= celda["reward_medio"] <= 1.0,
           f"[{pid}] celda {clave!r}: reward_medio debe estar en [0,1]")
    _exige(isinstance(celda["costo_medio_usd"], (int, float))
           and celda["costo_medio_usd"] > 0,
           f"[{pid}] celda {clave!r}: costo_medio_usd debe ser > 0")


def _validar_proveedor(p):
    _exige(isinstance(p, dict), "cada proveedor debe ser un mapeo")
    pid = p.get("id", "?")
    for campo in ("id", "connector", "modelos", "hosts_permitidos", "ping_url",
                  "habilitado", "estado", "ultima_medicion", "mediciones"):
        _exige(campo in p, f"[{pid}] falta el campo {campo!r}")
    _exige(isinstance(p["id"], str) and p["id"].strip(), "[?] id inválido")
    _exige(isinstance(p["connector"], str) and p["connector"].strip(),
           f"[{pid}] connector inválido")
    _exige(isinstance(p["modelos"], list) and p["modelos"]
           and all(isinstance(m, str) for m in p["modelos"]),
           f"[{pid}] modelos debe ser lista no vacía de strings")
    _exige(isinstance(p["hosts_permitidos"], list) and p["hosts_permitidos"],
           f"[{pid}] hosts_permitidos debe ser lista no vacía")
    _exige(isinstance(p["ping_url"], str)
           and p["ping_url"].startswith("https://"),
           f"[{pid}] ping_url debe ser https://")
    _exige(isinstance(p["habilitado"], bool), f"[{pid}] habilitado debe ser bool")
    est = p["estado"]
    _exige(isinstance(est, dict), f"[{pid}] estado debe ser un mapeo")
    _exige(est.get("disponibilidad") in ("disponible", "no_disponible"),
           f"[{pid}] estado.disponibilidad inválido")
    _exige("motivo" in est and "fecha" in est,
           f"[{pid}] estado necesita 'motivo' y 'fecha'")
    _exige(isinstance(p["mediciones"], list) and p["mediciones"],
           f"[{pid}] mediciones debe ser lista no vacía")
    for camp in p["mediciones"]:
        _exige(isinstance(camp, dict), f"[{pid}] cada medición debe ser un mapeo")
        for campo in ("campana", "fecha", "fuente", "celdas"):
            _exige(campo in camp, f"[{pid}] medición sin {campo!r}")
        _exige(isinstance(camp["celdas"], dict) and camp["celdas"],
               f"[{pid}] medición {camp.get('campana')}: celdas vacías")
        for clave, celda in camp["celdas"].items():
            _validar_celda(clave, celda, pid)


def validar_documento(doc):
    _exige(isinstance(doc, dict) and isinstance(doc.get("proveedores"), list)
           and doc["proveedores"], "el documento necesita 'proveedores' no vacío")
    vistos = set()
    for p in doc["proveedores"]:
        _validar_proveedor(p)
        _exige(p["id"] not in vistos, f"id duplicado: {p['id']!r}")
        vistos.add(p["id"])
    return doc


# ---------------------------------------------------------------- registro

class RegistroProveedores:
    """Registry de proveedores con failover y elección por reward/USD.

    `ping_fn(proveedor)` es inyectable: por defecto hace el ping real con
    surrogate del vault; los tests pasan un doble que no toca la red.
    """

    def __init__(self, ruta_yaml, ping_fn=None):
        self.ruta = ruta_yaml
        self._ping = ping_fn or _ping_surrogate
        with open(ruta_yaml, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        self._doc = validar_documento(doc)
        self._proveedores = self._doc["proveedores"]
        self._transitorio = {}  # id -> motivo de fallo no-auth de la última ronda

    # -- persistencia ------------------------------------------------

    def guardar(self):
        """Reescribe el YAML (estado + mediciones). Los comentarios del
        archivo original se reemplazan por un encabezado generado; la
        procedencia vive en los campos `fuente` y se preserva."""
        with open(self.ruta, "w", encoding="utf-8") as f:
            f.write(HEADER_GENERADO)
            yaml.safe_dump(self._doc, f, allow_unicode=True, sort_keys=False)

    # -- disponibilidad / failover -----------------------------------

    def _marcar(self, p, disponibilidad, motivo):
        p["estado"] = {"disponibilidad": disponibilidad,
                       "motivo": motivo, "fecha": _hoy()}

    def disponibles(self, persistir=True):
        """Chequea cada conector habilitado con un ping gratuito.

        - 2xx → disponible.
        - 401/403/404 → no_disponible con motivo y fecha (persiste; no voltea
          a los demás).
        - Otro error (red, timeout, credencial) → se excluye de ESTA ronda
          sin voltear el estado persistido (fail-closed para el ruteo, sin
          castigar un hipo transitorio).
        Devuelve la lista de ids disponibles.
        """
        ok = []
        for p in self._proveedores:
            if not p["habilitado"]:
                continue
            try:
                self._ping(p)
            except urllib.error.HTTPError as e:
                if e.code in HTTP_AUTH_FALLOS:
                    self._marcar(p, "no_disponible",
                                 f"HTTP {e.code} en ping {p['ping_url']}")
                    if persistir:
                        self.guardar()
                else:
                    self._transitorio[p["id"]] = f"HTTP {e.code} (transitorio)"
                continue
            except Exception as e:  # noqa: BLE001 - red, timeout, credencial
                self._transitorio[p["id"]] = f"{type(e).__name__}: {e}"
                continue
            self._transitorio.pop(p["id"], None)
            self._marcar(p, "disponible", None)
            ok.append(p["id"])
        if persistir and ok:
            # Persiste también las vueltas a disponible.
            self.guardar()
        return ok

    def estado(self, proveedor_id):
        """Estado actual (persistido) de un proveedor."""
        p = self._por_id(proveedor_id)
        return dict(p["estado"])

    # -- elección (regla EXP69) ---------------------------------------

    def _por_id(self, pid):
        for p in self._proveedores:
            if p["id"] == pid:
                return p
        raise KeyError(f"proveedor desconocido: {pid!r}")

    @staticmethod
    def _mejor_campana(p):
        """La campaña con más evidencia (mayor n total); desempate por fecha."""
        def clave(c):
            n_total = sum(celda["n"] for celda in c["celdas"].values())
            return (n_total, c.get("fecha", ""))
        return max(p["mediciones"], key=clave)

    def elegir(self, slice, persistir=True):
        """Devuelve (proveedor_id, brazo) con mayor reward/USD esperado para
        el slice, entre los proveedores disponibles. Desempate por menor
        costo. Fail-closed: si no hay ninguno, lanza SinProveedorDisponible.
        """
        disp = self.disponibles(persistir=persistir)
        if not disp:
            raise SinProveedorDisponible(
                "ningún proveedor disponible (todos deshabilitados, "
                "no_disponible o con ping fallido)")
        mejor = None  # (score, costo, pid, brazo)
        for pid in sorted(disp):
            p = self._por_id(pid)
            camp = self._mejor_campana(p)
            for clave in sorted(camp["celdas"]):
                sl, brazo = clave.split("/", 1)
                if sl != slice:
                    continue
                celda = camp["celdas"][clave]
                costo = celda["costo_medio_usd"]
                score = celda["reward_medio"] / costo if costo > 0 else 0.0
                if (mejor is None or score > mejor[0]
                        or (score == mejor[0] and costo < mejor[1])):
                    mejor = (score, costo, pid, brazo)
        if mejor is None:
            raise ValueError(f"slice {slice!r}: sin mediciones en el registry")
        return (mejor[2], mejor[3])

    # -- actualización de mediciones -----------------------------------

    def actualizar_medicion(self, proveedor_id, brazo, slice, reward, costo,
                            n=1, fuente="manual"):
        """Acumula una medición en la campaña 'acumulada-operativa' (media
        corrida por celda). Las keys nunca pasan por acá: solo números.
        La campaña con más evidencia es la que usa `elegir`, así que una
        medición chica no tapa un oráculo grande.
        """
        _exige(isinstance(reward, (int, float)) and 0.0 <= reward <= 1.0,
               "reward debe estar en [0,1]")
        _exige(isinstance(costo, (int, float)) and costo > 0,
               "costo debe ser > 0")
        _exige(isinstance(n, int) and n > 0, "n debe ser entero > 0")
        p = self._por_id(proveedor_id)
        camp = None
        for c in p["mediciones"]:
            if c.get("campana") == "acumulada-operativa":
                camp = c
                break
        if camp is None:
            camp = {"campana": "acumulada-operativa", "fecha": _hoy(),
                    "fuente": fuente, "celdas": {}}
            p["mediciones"].append(camp)
        clave = f"{slice}/{brazo}"
        celda = camp["celdas"].get(clave)
        if celda is None:
            camp["celdas"][clave] = {"n": n, "reward_medio": float(reward),
                                     "costo_medio_usd": float(costo)}
        else:
            n0 = celda["n"]
            n1 = n0 + n
            celda["reward_medio"] = (celda["reward_medio"] * n0 + reward * n) / n1
            celda["costo_medio_usd"] = (celda["costo_medio_usd"] * n0
                                       + costo * n) / n1
            celda["n"] = n1
        camp["fecha"] = _hoy()
        p["ultima_medicion"] = _hoy()
        self.guardar()
        return dict(camp["celdas"][clave])
