"""Las plantillas de assets/escenas/ contra Chrome: función pura de t y cues respetadas.

Una plantilla que lee el reloj, usa transiciones CSS o acumula estado entre
cuadros se delata acá: el mismo t tiene que dar el mismo PNG, venga en el orden
que venga. Y un elemento no puede asomar antes de la palabra que lo nombra.
"""
import hashlib

import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402

pytestmark = pytest.mark.integracion

SPECS = {
    "presentacion": {
        "titulo": {"texto": "El interés compuesto"},
        "puntos": [{"texto": "Ganás intereses", "cue": 2.0},
                   {"texto": "sobre intereses ya ganados", "cue": 3.2}],
        "duracion": 4.5,
    },
    "diagrama": {
        "titulo": {"texto": "Cómo crece la plata"},
        "nodos": [{"id": "c", "texto": "Capital", "cue": 0.4},
                  {"id": "i", "texto": "Interés", "cue": 2.0},
                  {"id": "n", "texto": "Capital nuevo", "cue": 3.0}],
        "flechas": [{"de": "c", "a": "i", "texto": "rinde", "cue": 2.4},
                    {"de": "i", "a": "n", "cue": 3.4}],
        "duracion": 4.5,
    },
    "datos": {
        "titulo": {"texto": "1.000 pesos al 10 % anual"},
        "barras": [{"etiqueta": "Año 0", "valor": 1000, "cue": 0.4},
                   {"etiqueta": "Año 10", "valor": 2594, "cue": 2.0},
                   {"etiqueta": "Año 30", "valor": 17449, "cue": 3.0, "destacar": True}],
        "duracion": 4.5,
    },
}
# t en el que entra un elemento con cue, para cada plantilla
CUE = {"presentacion": 2.0, "diagrama": 2.0, "datos": 2.0}


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def _hash(page, t):
    return hashlib.sha256(escena._cuadro(page, t)).hexdigest()


@pytest.mark.parametrize("tipo", SPECS)
def test_el_mismo_t_da_el_mismo_cuadro(chrome, tipo):
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), SPECS[tipo],
                                 escena.cargar_brand(None)) as (page, _):
        assert _hash(page, 2.3) == _hash(page, 2.3)


@pytest.mark.parametrize("tipo", SPECS)
def test_el_orden_de_los_cuadros_no_cambia_ningun_cuadro(chrome, tipo):
    ts = [0.3, 2.2, 3.6, 1.1]
    brand = escena.cargar_brand(None)
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), SPECS[tipo], brand) as (page, _):
        en_orden = {t: _hash(page, t) for t in ts}
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), SPECS[tipo], brand) as (page, _):
        al_reves = {t: _hash(page, t) for t in reversed(ts)}
    assert en_orden == al_reves
    assert len(set(en_orden.values())) == len(ts), "cuatro momentos distintos tienen que verse distintos"


@pytest.mark.parametrize("tipo", SPECS)
def test_nada_entra_antes_de_su_cue_y_entra_en_su_cue(chrome, tipo):
    cue = CUE[tipo]
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), SPECS[tipo],
                                 escena.cargar_brand(None)) as (page, _):
        justo_antes, un_poco_antes = _hash(page, cue - 0.02), _hash(page, cue - 0.4)
        despues = _hash(page, cue + 0.3)
    assert un_poco_antes == justo_antes, "algo se movió antes de la cue"
    assert despues != justo_antes, "el elemento no entró en su cue"


@pytest.mark.parametrize("tipo", SPECS)
def test_al_final_ningun_elemento_se_superpone_con_otro(chrome, tipo):
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), SPECS[tipo],
                                 escena.cargar_brand(None)) as (page, d):
        page.evaluate("t => window.seek(t)", d - 0.05)
        cajas = page.evaluate("""() => [...document.querySelectorAll('[data-caja]')].map(e => {
            const r = e.getBoundingClientRect();
            return {n: e.dataset.caja, x: r.left, y: r.top, w: r.width, h: r.height};
        })""")
    assert len(cajas) >= 3
    for i, a in enumerate(cajas):
        assert a["x"] >= 0 and a["y"] >= 0 and a["x"] + a["w"] <= 1920 and a["y"] + a["h"] <= 1080, a
        for b in cajas[i + 1:]:
            solapan = (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                       and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"])
            assert not solapan, f"{a['n']} se pisa con {b['n']}"
