"""H6 (HITO3.md): la escena `rotulo` (lower-third) contra Chrome.

No es un segmento propio: va en seg["rotulo"] y se compone encima de cualquier
tramo (ver test_editar_rotulo.py). Entra con la barra de acento dibujándose y
el título con resorte; sale limpio antes de que termine "dura".
"""
import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402

pytestmark = pytest.mark.integracion

MEMOIZACION = {"titulo": "Memoización", "subtitulo": "Unidad 10 · Programación I",
               "cue": 1.0, "dura": 2.0, "duracion": 5.0}


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def _abrir(chrome, spec=MEMOIZACION):
    return escena.pagina_de_escena(chrome, escena.ruta_plantilla("rotulo"), spec, escena.cargar_brand(None))


def _medir(page, t):
    escena._cuadro(page, t)
    return page.evaluate("""() => {
        const titulo = document.querySelector('[data-caja=rotulo-titulo]');
        const sub = document.querySelector('[data-caja=rotulo-subtitulo]');
        const barra = document.querySelector('.barra');
        const op = e => { let o = 1; for (let x = e; x && x.nodeType === 1; x = x.parentElement) o *= +getComputedStyle(x).opacity; return o; };
        return {tituloTexto: titulo.textContent, tituloOp: op(titulo),
                subOp: sub ? op(sub) : null, scaleX: +getComputedStyle(barra).transform.split(',')[0].replace('matrix(', '')};
    }""")


def test_antes_de_la_cue_no_se_ve_nada(chrome):
    with _abrir(chrome) as (page, _):
        m = _medir(page, 0.5)
    assert m["tituloOp"] == 0


def test_durante_dura_el_titulo_y_la_barra_se_ven(chrome):
    with _abrir(chrome) as (page, _):
        m = _medir(page, 1.8)
    assert m["tituloTexto"] == "Memoización"
    assert m["tituloOp"] > 0.9
    assert m["subOp"] > 0.9
    assert m["scaleX"] > 0.9


def test_despues_de_cue_mas_dura_sale_limpio(chrome):
    with _abrir(chrome) as (page, _):
        m = _medir(page, 3.4)
    assert m["tituloOp"] == 0


# --- triangulación: otro spec, sin subtítulo, cambia lo que se ve -------------------

def test_sin_subtitulo_no_hay_elemento_de_subtitulo(chrome):
    spec = {"titulo": "Recursión", "cue": 0.2, "dura": 1.5, "duracion": 3.0}
    with _abrir(chrome, spec) as (page, _):
        tiene_sub = page.evaluate("!!document.querySelector('[data-caja=rotulo-subtitulo]')")
    assert tiene_sub is False


def test_con_otro_titulo_el_texto_cambia(chrome):
    spec = {"titulo": "Recursión", "cue": 0.2, "dura": 1.5, "duracion": 3.0}
    with _abrir(chrome, spec) as (page, _):
        m = _medir(page, 1.0)
    assert m["tituloTexto"] == "Recursión"
