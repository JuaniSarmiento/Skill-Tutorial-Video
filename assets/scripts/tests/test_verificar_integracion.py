"""H2 (HITO3.md): la puerta `check` contra Chrome.

Escenas fabricadas con un problema cada una (tests/fixtures/verificar/) tienen que
fallar nombrando escena, tiempo y elemento; las cuatro plantillas con specs como los
del ejemplo tienen que pasar; y `escena.py render` no renderiza una escena que no pasa,
salvo que se lo pidan explícitamente.
"""
from pathlib import Path

import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402
import verificar  # noqa: E402

pytestmark = pytest.mark.integracion

FIX = Path(__file__).parent / "fixtures" / "verificar"


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def _verificar(chrome, plantilla, spec=None):
    spec = spec or {}
    with escena.pagina_de_escena(chrome, plantilla, spec, escena.cargar_brand(None)) as (page, d):
        return verificar.verificar_pagina(page, d, spec, Path(plantilla).name)


@pytest.mark.parametrize("archivo, tipo, nombres", [
    ("pisan.html", "solape", ["precio", "descuento"]),
    ("contraste.html", "contraste", ["nota gris"]),
    ("temprano.html", "cue", ["punto tardío", "2.00"]),
])
def test_una_escena_con_un_problema_lo_nombra_con_escena_tiempo_y_elemento(chrome, archivo, tipo, nombres):
    hallazgos = _verificar(chrome, FIX / archivo)
    assert {h.tipo for h in hallazgos} == {tipo}
    for h in hallazgos:
        assert archivo in h.texto and "t=" in h.texto
        assert all(n in h.texto for n in nombres), h.texto


def test_el_contraste_medido_es_el_de_la_escena(chrome):
    (h, *_) = _verificar(chrome, FIX / "contraste.html")
    assert "2.06:1" in h.texto, h.texto   # #555 sobre #252525, a mano


def test_una_escena_limpia_no_tiene_hallazgos(chrome):
    assert _verificar(chrome, FIX / "limpia.html") == []


# --- las plantillas de la skill pasan con specs como los del ejemplo -------------------

from test_tipografia import TODAS, NUMERO  # noqa: E402


@pytest.mark.parametrize("tipo, spec", TODAS + [("presentacion", NUMERO)],
                         ids=lambda x: x if isinstance(x, str) else "")
def test_las_plantillas_pasan_la_puerta(chrome, tipo, spec):
    assert _verificar(chrome, escena.ruta_plantilla(tipo), {"duracion": 3.0, **spec}) == []


SIN_CUE = {"titulo", "kicker", "nota"}   # entran con el título, no con una cue propia


@pytest.mark.parametrize("tipo, spec", TODAS + [("presentacion", NUMERO)],
                         ids=lambda x: x if isinstance(x, str) else "")
def test_cada_elemento_con_cue_declara_su_t_para_que_la_puerta_lo_mida(chrome, tipo, spec):
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), {"duracion": 3.0, **spec},
                                 escena.cargar_brand(None)) as (page, d):
        escena._cuadro(page, d - 0.05)
        cajas = page.evaluate("() => [...document.querySelectorAll('[data-caja]')].map(e => [e.dataset.caja, e.dataset.t])")
    sin_t = [n for n, t in cajas if t is None and n.split()[0] not in SIN_CUE]
    assert sin_t == []
