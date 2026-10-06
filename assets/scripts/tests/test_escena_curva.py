"""H5 (HITO3.md): la escena `curva` contra Chrome.

Una curva que se dibuja (DrawSVG) acompañada de un contador (contador.js, H4) y de
puntos marcados con su valor. El caso de referencia es el interés compuesto: US$ 1.000
que llegan a US$ 17.449 en 30 años (la comparativa con HyperFrames, HITO3.md).
"""
import hashlib

import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402

pytestmark = pytest.mark.integracion

INTERES = {
    "tipo": "curva", "titulo": {"texto": "US$ 1.000 a 30 años"},
    "puntos": [{"x": 0, "y": 1000, "etiqueta": "Año 0", "cue": 0.4},
               {"x": 10, "y": 2594, "etiqueta": "Año 10", "cue": 2.2},
               {"x": 30, "y": 17449, "etiqueta": "Año 30", "cue": 4.2}],
    "prefijo": "US$ ", "duracion": 6.0,
}


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def _abrir(chrome, spec=INTERES):
    return escena.pagina_de_escena(chrome, escena.ruta_plantilla("curva"), spec, escena.cargar_brand(None))


def _medir(page, t):
    escena._cuadro(page, t)
    return page.evaluate("""() => {
        const cifra = document.querySelector('[data-caja=cifra]');
        const trazo = document.querySelector('svg path');
        let o = 1; for (let x = cifra; x && x.nodeType === 1; x = x.parentElement) o *= +getComputedStyle(x).opacity;
        return {cifra: cifra.textContent, cifraOp: o, dashoffset: getComputedStyle(trazo).strokeDashoffset,
                puntos: [...document.querySelectorAll('.punto')].map(e => +getComputedStyle(e).opacity)};
    }""")


# --- el trazo se dibuja y el contador acompaña ---------------------------------------

def test_antes_de_la_primera_cue_no_hay_nada_visible(chrome):
    with _abrir(chrome) as (page, _):
        m = _medir(page, 0.1)
    assert m["cifraOp"] == 0
    assert all(op == 0 for op in m["puntos"])


def test_al_final_el_contador_termina_exacto_en_el_ultimo_punto(chrome):
    with _abrir(chrome) as (page, d):
        m = _medir(page, d - 0.05)
    assert m["cifra"] == "US$ 17.449"
    assert all(op > 0.9 for op in m["puntos"])


def test_el_trazo_avanza_entre_la_primera_y_la_ultima_cue(chrome):
    with _abrir(chrome) as (page, d):
        recien_arrancado = float(_medir(page, 0.5)["dashoffset"].replace("px", ""))
        a_mitad = float(_medir(page, 2.3)["dashoffset"].replace("px", ""))
        casi_al_final = float(_medir(page, 4.1)["dashoffset"].replace("px", ""))
    # stroke-dashoffset baja a medida que el trazo se dibuja (DrawSVG)
    assert recien_arrancado > a_mitad > casi_al_final >= 0


# --- triangulación: otros datos dan otro resultado -----------------------------------

def test_con_otros_puntos_el_contador_y_las_etiquetas_cambian(chrome):
    spec = {"tipo": "curva", "puntos": [{"x": 0, "y": 10, "etiqueta": "Antes", "cue": 0.2},
                                        {"x": 5, "y": 55, "etiqueta": "Después", "cue": 1.5}],
            "sufijo": " %", "duracion": 2.5}
    with _abrir(chrome, spec) as (page, d):
        m = _medir(page, d - 0.05)
    assert m["cifra"] == "55 %"


# --- determinismo, igual que el resto de las plantillas ------------------------------

def _hash(page, t):
    return hashlib.sha256(escena._cuadro(page, t)).hexdigest()


def test_el_mismo_t_da_el_mismo_cuadro_en_cualquier_orden(chrome):
    ts = [0.3, 1.8, 3.4, 5.5]
    with _abrir(chrome) as (page, _):
        en_orden = {t: _hash(page, t) for t in ts}
    with _abrir(chrome) as (page, _):
        al_reves = {t: _hash(page, t) for t in reversed(ts)}
    assert en_orden == al_reves
    assert len(set(en_orden.values())) == len(ts)


def test_una_curva_con_un_solo_punto_falla_claro(chrome):
    spec = {"tipo": "curva", "puntos": [{"x": 0, "y": 10, "cue": 0.2}], "duracion": 2.0}
    with pytest.raises(escena.ContratoError, match="al menos dos"):
        with _abrir(chrome, spec) as (page, d):
            escena._cuadro(page, d - 0.05)
