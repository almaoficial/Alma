# -*- coding: utf-8 -*-
"""CORPUS SINTÉTICO DE EJEMPLO — no contiene datos reales.

En el repositorio local, este módulo contiene el corpus privado de 15 días
reconstruido desde los registros reales del dueño del sistema (planes,
veredictos y bits diarios). Ese corpus NO se publica: son datos de su vida.

Esta versión pública trae 3 días completamente inventados (personas,
proveedores, montos y situaciones ficticios) con el MISMO esquema, para que
la batería — construir_corpus.py, puntuar.py, puntuar_ciclo1.py y el
validador congelado validador_plan.py — corra de punta a punta y reproduzca
el MÉTODO. Los números citados en los papeles del programa (línea de base
v0 = 0,9828 · ancla de planes reales = 0,8511 · ciclo 1 Δ = +0,0144) se
midieron sobre el corpus privado de 15 días y están archivados en
resultados_v0.json y resultados_ciclo1.json, cuyas filas son solo puntajes
(sin textos). Ver SANEADO.md en este directorio.
"""

DIAS = [
 dict(
  fecha="2026-01-05", dia_semana="lunes",
  paquete=("Cierre del 4/1: día planificado, bit 1. Hoy vence NetSur: "
           "US$61,20. Quedó abierto el frente de ordenar el archivo de "
           "planillas del depósito. La pileta está cerrada por refacción "
           "toda la semana. Turno de trabajo 14–20."),
  paquete_fuente="SINTÉTICO — ejemplo inventado",
  compromiso_top=dict(texto="Pagar NetSur, que vence hoy",
                      keywords=["netsur"], horario_tokens=None),
  plata_critica=True,
  ancla_factible=["caminata", "meditación", "meditacion", "lectura"],
  ancla_infactible=["natación", "natacion", "pileta"],
  c4_aplicable=True,
  bit_real=1, veredicto_real="planificado",
  verdad_fuente="SINTÉTICO — ejemplo inventado"),
 dict(
  fecha="2026-01-06", dia_semana="martes",
  paquete=("Cierre del 5/1: día improvisado, bit 0. Hoy a las 18:30 hay "
           "que entregar la planilla de inventario al depósito. Lluvia "
           "todo el día: la caminata queda descartada, la bicicleta del "
           "galpón está disponible. Sin vencimientos de plata hoy."),
  paquete_fuente="SINTÉTICO — ejemplo inventado",
  compromiso_top=dict(texto="Entregar la planilla de inventario a las 18:30",
                      keywords=["inventario"], horario_tokens=["18:30"]),
  plata_critica=False,
  ancla_factible=["bicicleta"],
  ancla_infactible=["caminata"],
  c4_aplicable=True,
  bit_real=0, veredicto_real="improvisado",
  verdad_fuente="SINTÉTICO — ejemplo inventado"),
 dict(
  fecha="2026-01-07", dia_semana="miércoles",
  paquete=("Cierre del 6/1: día planificado, bit 1. LuzAndina vence el "
           "9/1: US$88,40 — conviene dejar el pago reservado hoy. Día de "
           "viaje: no hay ancla de rutina aplicable. Turno de trabajo "
           "14–20."),
  paquete_fuente="SINTÉTICO — ejemplo inventado",
  compromiso_top=dict(texto="Reservar el pago de LuzAndina",
                      keywords=["luzandina"], horario_tokens=None),
  plata_critica=True,
  ancla_factible=[],
  ancla_infactible=[],
  c4_aplicable=False,
  bit_real=1, veredicto_real="planificado",
  verdad_fuente="SINTÉTICO — ejemplo inventado"),
]

# Planes «reales» del ejemplo: textos deliberadamente imperfectos, como los
# planes vividos que la batería usa de ancla (en el corpus privado son los
# planes que el asistente produjo de verdad esos días).
REALES = {
 "2026-01-05": (
   "1) Pagar NetSur hoy (dato · paquete del día). "
   "2) A la tarde, natación en la pileta del club. "
   "3) Nada más."),
 "2026-01-06": (
   "1) Entregar la planilla de inventario al depósito. "
   "2) Caminata larga para despejar. "
   "3) Revisar el correo del depósito."),
 "2026-01-07": (
   "1) Reservar el pago de LuzAndina (dato · paquete del día). "
   "2) Frente abierto: ordenar el archivo de planillas. "
   "3) Dejar US$50,00 separados para gastos de la semana."),
}
