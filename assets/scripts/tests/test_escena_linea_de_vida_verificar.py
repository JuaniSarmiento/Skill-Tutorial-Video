"""H5: la escena `linea-de-vida` en la puerta `check` de verificar.py.

Aparte de test_escena_linea_de_vida.py porque verificar_escena abre su propio Chrome
(Playwright sync no se anida con el Chrome de módulo de ese archivo; ver
test_escena_codigo_render.py).
"""
import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402
import verificar  # noqa: E402

pytestmark = pytest.mark.integracion

ANA_SOFIA = {
    "tipo": "linea-de-vida", "titulo": {"texto": "Diez años de diferencia"},
    "tramos": [{"nombre": "Ana", "desde": 25, "hasta": 35, "cue": 0.4},
               {"nombre": "Sofía", "desde": 35, "hasta": 65, "cue": 2.4}],
    "duracion": 5.0,
}


def test_ana_y_sofia_pasa_la_puerta_de_verificar():
    hallazgos = verificar.verificar_escena(escena.ruta_plantilla("linea-de-vida"), ANA_SOFIA, nombre="linea-de-vida")
    assert hallazgos == [], verificar.informe(hallazgos)
