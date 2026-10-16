"""Generador determinista de problemas para la validación de fase 1.

Dos firmas con ground truth entero y exact-match estricto:
- "aritmetica": cálculo directo (single debería rendir bien).
- "razonamiento": problemas de 2-3 pasos en palabras (cot/reflexión
  deberían rendir mejor).

El generador es determinista por seed: el stream queda comprometido en
el pre-registro y es reproducible. No usa la key.
"""

import random

FIRMAS = ("aritmetica", "razonamiento")


def _aritmetica(rng):
    op = rng.choice(["+", "-", "×"])
    if op == "+":
        a, b = rng.randint(101, 999), rng.randint(101, 999)
        esp = a + b
    elif op == "-":
        a, b = rng.randint(200, 999), rng.randint(101, 199)
        esp = a - b
    else:
        a, b = rng.randint(12, 99), rng.randint(12, 29)
        esp = a * b
    return f"¿Cuánto es {a} {op} {b}?", str(esp)


def _razonamiento(rng):
    t = rng.choice([1, 2, 3, 4])
    if t == 1:
        a, b, c, d = (rng.randint(20, 80), rng.randint(2, 5),
                      rng.randint(6, 15), rng.randint(5, 30))
        esp = a + b * c - d
        en = (f"Lucía tiene {a} figuritas. Compra {b} paquetes de {c} "
              f"y regala {d}. ¿Cuántas le quedan?")
    elif t == 2:
        a, b, c, d = (rng.randint(40, 90), rng.randint(1, 3),
                      rng.randint(50, 100), rng.randint(1, 2))
        esp = a * b + c * d
        en = (f"Un tren viaja a {a} km/h durante {b} horas y después a "
              f"{c} km/h durante {d} horas. "
              f"¿Cuántos km recorrió en total?")
    elif t == 3:
        a, b = rng.randint(15, 40), rng.randint(2, 6)
        c = rng.randint(10, a * b - 10)
        esp = a * b - c
        en = (f"En un corral hay {a} gallinas. Cada una pone {b} huevos "
              f"por día. Si se venden {c} huevos, "
              f"¿cuántos quedan al cabo de un día?")
    else:
        c = rng.randint(2, 6)
        b = rng.randint(20, 120)
        resto = c * rng.randint(15, 60)
        a = b + resto
        esp = resto // c
        en = (f"Martín ahorró {a} pesos. Gasta {b} en un libro y el resto "
              f"lo reparte en partes iguales entre sus {c} hermanos. "
              f"¿Cuánto recibe cada uno?")
    assert esp > 0
    return en, str(esp)


def generar_problemas(seed, n_bloques=8, por_bloque=6):
    """Stream de validación: bloques que alternan la firma mayoritaria
    (5 de la firma del bloque + 1 de ruido de la otra), como los
    regímenes del mock. Retorna lista de dicts
    {id, enunciado, firma, esperado}."""
    rng = random.Random(seed)
    problemas = []
    for b in range(n_bloques):
        firma_may = FIRMAS[b % 2]
        firma_min = FIRMAS[(b + 1) % 2]
        for q in range(por_bloque):
            firma = firma_may if q < por_bloque - 1 else firma_min
            if firma == "aritmetica":
                en, esp = _aritmetica(rng)
            else:
                en, esp = _razonamiento(rng)
            problemas.append({
                "id": f"f1-s{seed}-b{b}-q{q}",
                "enunciado": en,
                "firma": firma,
                "esperado": esp,
            })
    return problemas


if __name__ == "__main__":
    ps = generar_problemas(11)
    print(len(ps), "problemas")
    for p in ps[:7]:
        print(p["firma"], "|", p["enunciado"], "=>", p["esperado"])
