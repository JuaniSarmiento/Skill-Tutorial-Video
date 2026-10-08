"""Formato del archivo de marcas que escribe Toma.marca() (raw/<nombre>.marcas.json):
una línea JSON por marca, {t, nombre}, t en segundos desde el inicio de la
grabación. Capa pura: sin Playwright, sin Chrome real.
"""
import json

import grabar_web


def test_formatear_marca_redondea_el_tiempo_y_conserva_el_nombre():
    marca = grabar_web._formatear_marca(12.34567, "abrio comisiones")

    assert marca == {"t": 12.346, "nombre": "abrio comisiones"}


def test_escribir_marca_agrega_una_linea_json_por_marca(tmp_path):
    destino = tmp_path / "v01.marcas.json"

    grabar_web._escribir_marca(destino, grabar_web._formatear_marca(1.0, "primera"))
    grabar_web._escribir_marca(destino, grabar_web._formatear_marca(2.5, "segunda"))

    lineas = destino.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 2
    assert json.loads(lineas[0]) == {"t": 1.0, "nombre": "primera"}
    assert json.loads(lineas[1]) == {"t": 2.5, "nombre": "segunda"}
