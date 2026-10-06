"""H5: la escena `curva` en la puerta `check` de verificar.py.

Aparte de test_escena_curva.py porque verificar_escena abre su propio Chrome (Playwright
sync no se anida con el Chrome de módulo de ese archivo; ver test_escena_codigo_render.py).
"""
import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402
import verificar  # noqa: E402

pytestmark = pytest.mark.integracion

INTERES = {
    "tipo": "curva", "titulo": {"texto": "US$ 1.000 a 30 años"},
    "puntos": [{"x": 0, "y": 1000, "etiqueta": "Año 0", "cue": 0.4},
               {"x": 10, "y": 2594, "etiqueta": "Año 10", "cue": 2.2},
               {"x": 30, "y": 17449, "etiqueta": "Año 30", "cue": 4.2}],
    "prefijo": "US$ ", "duracion": 6.0,
}


def test_la_curva_del_interes_compuesto_pasa_la_puerta_de_verificar():
    hallazgos = verificar.verificar_escena(escena.ruta_plantilla("curva"), INTERES, nombre="curva")
    assert hallazgos == [], verificar.informe(hallazgos)
