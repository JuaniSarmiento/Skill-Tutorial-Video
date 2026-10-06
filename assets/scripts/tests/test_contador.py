"""H4 (HITO3.md): un número que cuenta hasta su valor en su cue.

`contador.js` lo usan la escena `contador` (el número protagonista suelto) y la escena
`codigo` (los números de una salida que cuentan). Ideas de los bloques `count-up` y
`number-pop-in` de HyperFrames (Apache 2.0); el código es propio.
"""
import hashlib

import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402

pytestmark = pytest.mark.integracion

SPEC = {"titulo": {"texto": "Fibonacci de 30, sin memoria"}, "valor": 2692537, "unidad": "llamadas",
        "cue": 1.0, "duracion": 4.0}


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def _abrir(chrome, spec=SPEC):
    return escena.pagina_de_escena(chrome, escena.ruta_plantilla("contador"), spec, escena.cargar_brand(None))


def _numero(page, t):
    escena._cuadro(page, t)
    return page.evaluate("""() => { const e = document.querySelector('[data-caja=numero]');
        let o = 1; for (let x = e; x && x.nodeType === 1; x = x.parentElement) o *= +getComputedStyle(x).opacity;
        return {texto: e.textContent, opacidad: o, px: parseFloat(getComputedStyle(e).fontSize)}; }""")


# --- formato ---------------------------------------------------------------------------

@pytest.mark.parametrize("valor, opciones, sale", [
    (2692537, {}, "2.692.537"),
    (1000, {}, "1.000"),
    (1500, {"prefijo": "US$ "}, "US$ 1.500"),
    (3.5, {"dec": 1, "sufijo": " %"}, "3,5 %"),
    (-500, {"prefijo": "$"}, "-$500"),
    (999, {}, "999"),
])
def test_el_formato_es_el_argentino_con_punto_de_miles_y_coma_decimal(chrome, valor, opciones, sale):
    with _abrir(chrome) as (page, _):
        assert page.evaluate("([v, o]) => Contador.formato(v, o)", [valor, opciones]) == sale


# --- la escena -------------------------------------------------------------------------

def test_antes_de_su_cue_el_numero_no_se_ve(chrome):
    with _abrir(chrome) as (page, _):
        assert _numero(page, 0.95)["opacidad"] == 0


def test_cuenta_hacia_arriba_y_termina_exacto_en_su_valor(chrome):
    with _abrir(chrome) as (page, d):
        medio = _numero(page, 1.3)["texto"]
        final = _numero(page, d - 0.05)["texto"]
    assert final == "2.692.537"
    assert 0 < int(medio.replace(".", "")) < 2692537


def test_el_numero_es_protagonista_de_300_px_o_mas(chrome):
    with _abrir(chrome) as (page, d):
        assert _numero(page, d - 0.05)["px"] >= 300


def test_prefijo_y_sufijo_acompanan_al_numero(chrome):
    spec = {"valor": 1500, "prefijo": "US$ ", "sufijo": "", "cue": 0.2, "duracion": 3.0}
    with _abrir(chrome, spec) as (page, d):
        assert _numero(page, d - 0.05)["texto"] == "US$ 1.500"


def test_un_numero_que_no_entra_a_300_px_falla_nombrandolo(chrome):
    spec = {"valor": 123456789012345, "cue": 0.2, "duracion": 3.0}
    with pytest.raises(escena.ContratoError, match="123"):
        with _abrir(chrome, spec) as (page, _):
            escena._cuadro(page, 1.0)


def _hash(page, t):
    return hashlib.sha256(escena._cuadro(page, t)).hexdigest()


def test_el_mismo_t_da_el_mismo_cuadro_en_cualquier_orden(chrome):
    ts = [0.5, 1.2, 1.9, 3.5]
    with _abrir(chrome) as (page, _):
        en_orden = {t: _hash(page, t) for t in ts}
    with _abrir(chrome) as (page, _):
        al_reves = {t: _hash(page, t) for t in reversed(ts)}
    assert en_orden == al_reves
    assert len(set(en_orden.values())) == len(ts)


def test_el_numero_terminado_arranca_alineado_con_su_unidad(chrome):
    # la caja se medía con canvas, que ignora el letter-spacing negativo: quedaba más ancha
    # que el número y el número (alineado a la derecha) arrancaba ~200 px más adentro
    with _abrir(chrome) as (page, d):
        escena._cuadro(page, d - 0.05)
        izq = page.evaluate("""() => ['numero', 'unidad'].map(n => {
            const r = document.createRange(); r.selectNodeContents(document.querySelector(`[data-caja=${n}]`));
            return r.getBoundingClientRect().left; })""")
    assert abs(izq[0] - izq[1]) <= 24, izq
