"""H6 (HITO3.md): texto cinético en el título de `presentacion` con
"entrada": "palabras" (SplitText, GSAP): las palabras suben de a una con
resorte, además de la entrada actual (sin la clave, sin cambios)."""
import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402

pytestmark = pytest.mark.integracion


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def _abrir(chrome, spec):
    return escena.pagina_de_escena(chrome, escena.ruta_plantilla("presentacion"), spec, escena.cargar_brand(None))


def _palabras(page, t):
    escena._cuadro(page, t)
    return page.evaluate("""() => [...document.querySelectorAll('.titulo .word')]
        .map(w => { let o = 1; for (let x = w; x && x.nodeType === 1; x = x.parentElement) o *= +getComputedStyle(x).opacity; return o; })""")


SPEC = {"tipo": "presentacion", "titulo": {"texto": "Programación dinámica real", "cue": 0, "entrada": "palabras"},
        "subtitulo": {"texto": "Memoización", "cue": 1.0}, "duracion": 3.0}


def test_antes_de_la_cue_ninguna_palabra_se_ve(chrome):
    with _abrir(chrome, SPEC) as (page, _):
        ops = _palabras(page, 0.0)
    assert ops and all(o == 0 for o in ops)


def test_poco_despues_de_la_cue_la_primera_palabra_ya_se_ve_y_la_ultima_todavia_no(chrome):
    with _abrir(chrome, SPEC) as (page, _):
        ops = _palabras(page, 0.1)
    assert ops[0] > 0.3
    assert ops[-1] == 0


def test_bien_despues_todas_las_palabras_se_ven(chrome):
    with _abrir(chrome, SPEC) as (page, _):
        ops = _palabras(page, 1.5)
    assert all(o > 0.9 for o in ops)


# --- triangulación: sin "entrada": "palabras", no hay .word (sigue el camino actual) --

def test_sin_entrada_palabras_no_usa_split_text(chrome):
    spec = {"tipo": "presentacion", "titulo": {"texto": "Programación dinámica", "cue": 0}, "duracion": 2.0}
    with _abrir(chrome, spec) as (page, _):
        escena._cuadro(page, 1.0)
        hay = page.evaluate("document.querySelectorAll('.titulo .word').length")
    assert hay == 0


def test_con_mas_palabras_hay_mas_elementos_word(chrome):
    spec = {**SPEC, "titulo": {"texto": "Uno dos tres cuatro cinco", "cue": 0, "entrada": "palabras"}}
    with _abrir(chrome, spec) as (page, _):
        escena._cuadro(page, 1.5)
        n = page.evaluate("document.querySelectorAll('.titulo .word').length")
    assert n == 5
