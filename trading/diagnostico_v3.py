"""Diagnóstico de robustez v3 (pre-registrado en el addendum de ARENA_PREREGISTRO.md).

Re-corre la v3 en cada ventana (parámetros ya fijados: grilla vacía) y reporta:
1. Estabilidad del mapa clima→brazo entre ventanas (acuerdo por clima).
2. Cambios de brazo por ventana (anti-churn).
3. Disparos del freno de emergencia por ventana.

Papel, US$0. No toca la arena ni sus resultados.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datos import cargar_universo, recortar_por_fecha
from alma_v3 import correr_alma_v3, CLIMAS
from arena import VENTANAS
from banco_papel import verificar_solo_papel

verificar_solo_papel()
fechas, precios = cargar_universo()

mapas = {}
print("=== v3 por ventana: mapa final, cambios, emergencias ===\n")
for ini, fin in VENTANAS:
    f_w, p_w = recortar_por_fecha(fechas, precios, ini, fin)
    banco, decisiones = correr_alma_v3(p_w, f_w)
    final = decisiones[-1]
    assert final.get("tipo") == "mapa_final", "falta el mapa final en decisiones"
    etiqueta = f"{ini[:4]}–{fin[:4]}"
    mapas[etiqueta] = final
    print(f"ventana {etiqueta}: cambios_brazo={final['cambios_brazo']} "
          f"emergencias={final['emergencias']} "
          f"regimen_final={final['regimen_final']}")
    for c in CLIMAS:
        m = final["mapa"][c]
        print(f"    {c:14s} -> {m['brazo']:9s} "
              f"(sharpe_decayed={m['sharpe_decayed']}, peso={m['peso']})")
    print()

print("=== Estabilidad del mapa entre ventanas (acuerdo por clima) ===")
for c in CLIMAS:
    brazos = [mapas[v]["mapa"][c]["brazo"] for v in mapas]
    modal = max(set(brazos), key=brazos.count)
    acuerdo = brazos.count(modal)
    veredicto = ("ESTABLE" if acuerdo >= 4 else
                 "dudoso" if acuerdo == 3 else "INESTABLE")
    print(f"  {c:14s}: {brazos} -> modal={modal} ({acuerdo}/5) [{veredicto}]")

tot_cambios = sum(mapas[v]["cambios_brazo"] for v in mapas)
tot_emerg = sum(mapas[v]["emergencias"] for v in mapas)
print(f"\nTotal cambios de brazo v3 (5 ventanas): {tot_cambios} "
      f"(v1/v2: ~28 por ventana en 2021–2026)")
print(f"Total emergencias v3 (5 ventanas): {tot_emerg}")
