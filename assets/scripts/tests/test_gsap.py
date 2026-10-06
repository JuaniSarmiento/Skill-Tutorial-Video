"""H0 (HITO3.md): puente GSAP -> contrato del motor (window.DURATION + window.seek(t)).

Una plantilla arma una timeline de GSAP y E.lineaDeTiempo la entrega al motor: la
duración es la de la timeline y seek(t) la deja en t. Nada puede avanzar con el reloj
real (GSAP trae su propio ticker con requestAnimationFrame): eso se mide acá, no se
asume. GSAP se carga desde assets/escenas/vendor/ como archivo local; la red sigue
bloqueada.
"""
import hashlib
from pathlib import Path

import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402

pytestmark = pytest.mark.integracion

VENDOR = (escena.ESCENAS / "vendor" / "gsap").as_uri()
BASE = (escena.ESCENAS / "base.js").as_uri()


def _plantilla(tmp_path, construir, con_gsap=True):
    """Una caja #b y la timeline que arma `construir` (cuerpo JS que devuelve la timeline)."""
    gsap = f'<script src="{VENDOR}/gsap.min.js"></script>' if con_gsap else ""
    html = tmp_path / "gsap.html"
    html.write_text(f"""<!doctype html><body style="margin:0;background:#111">
<div id=b style="position:absolute;top:400px;width:200px;height:200px;background:#f2b544"></div>
<div id=suelta style="position:absolute;top:700px;width:100px;height:100px;background:#4a9"></div>
{gsap}<script src="{BASE}"></script>
<script>E.lineaDeTiempo(() => {{ {construir} }});</script>""")
    return html


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def _x(page, sel="#b"):
    return page.evaluate(f"() => gsap.getProperty('{sel}', 'x')")


@pytest.mark.parametrize("segundos", [2.4, 1.7])
def test_la_duracion_de_la_escena_es_la_de_la_timeline(chrome, tmp_path, segundos):
    html = _plantilla(tmp_path, f"return gsap.timeline().to('#b', {{x: 1000, duration: {segundos}}});")
    with escena.pagina_de_escena(chrome, html, {}, escena.cargar_brand(None)) as (_, duracion):
        assert duracion == pytest.approx(segundos)


def test_el_spec_puede_pisar_la_duracion_como_en_las_otras_plantillas(chrome, tmp_path):
    # editar.py le pasa a cada escena la duración de su slot de voz (spec.duracion)
    html = _plantilla(tmp_path, "return gsap.timeline().to('#b', {x: 1000, duration: 2});")
    with escena.pagina_de_escena(chrome, html, {"duracion": 3.5}, escena.cargar_brand(None)) as (_, duracion):
        assert duracion == 3.5


def test_seek_deja_la_timeline_en_t_aunque_los_cuadros_vengan_desordenados(chrome, tmp_path):
    html = _plantilla(tmp_path, "return gsap.timeline().to('#b', {x: 1000, duration: 2, ease: 'none'});")
    with escena.pagina_de_escena(chrome, html, {}, escena.cargar_brand(None)) as (page, _):
        vistos = {}
        for t in [1.5, 0.5, 2.0, 0.0, 1.0]:
            escena._cuadro(page, t)
            vistos[t] = round(_x(page), 3)
    assert vistos == {1.5: 750, 0.5: 250, 2.0: 1000, 0.0: 0, 1.0: 500}


def test_nada_avanza_con_el_reloj_real_ni_un_tween_suelto_fuera_de_la_timeline(chrome, tmp_path):
    # un tween suelto (gsap.to fuera de la timeline) lo mueve el ticker de GSAP con
    # requestAnimationFrame: si el reloj real corre, se ve en el cuadro.
    html = _plantilla(tmp_path, """gsap.to('#suelta', {x: 1500, duration: 1, ease: 'none'});
        return gsap.timeline().to('#b', {x: 1000, duration: 2, ease: 'none'});""")
    with escena.pagina_de_escena(chrome, html, {}, escena.cargar_brand(None)) as (page, _):
        antes = escena._cuadro(page, 1.0)
        page.wait_for_timeout(600)
        despues = page.screenshot(type="png")
        x_b, x_suelta = _x(page), _x(page, "#suelta")
    assert (x_b, x_suelta) == (500, 0)
    assert despues == antes, "el cuadro cambió sin que nadie llamara a seek"


def test_sin_gsap_cargado_la_escena_falla_diciendo_de_donde_cargarlo(chrome, tmp_path):
    html = _plantilla(tmp_path, "return null;", con_gsap=False)
    with pytest.raises(escena.ContratoError, match="vendor/gsap/gsap.min.js"):
        with escena.pagina_de_escena(chrome, html, {}, escena.cargar_brand(None)):
            pass


# --- la plantilla de prueba: timeline + DrawSVG + SplitText + MorphSVG ----------------

PRUEBA = Path(__file__).parent / "fixtures" / "gsap" / "prueba-gsap.html"
SPEC_PRUEBA = {"titulo": {"texto": "Todo es función de t"}}


def _hash(page, t):
    return hashlib.sha256(escena._cuadro(page, t)).hexdigest()


def _estado(page, t):
    escena._cuadro(page, t)
    return page.evaluate("""() => {
        const trazo = document.querySelector('#trazo');
        const palabras = [...document.querySelectorAll('#titulo .palabra')];
        return {
            dibujado: parseFloat(getComputedStyle(trazo).strokeDasharray) / trazo.getTotalLength(),
            palabras: palabras.map(p => +getComputedStyle(p).opacity),
            forma: document.querySelector('#forma').getAttribute('d'),
        };
    }""")


def test_la_prueba_usa_drawsvg_splittext_y_morphsvg_sobre_la_timeline(chrome):
    with escena.pagina_de_escena(chrome, PRUEBA, SPEC_PRUEBA, escena.cargar_brand(None)) as (page, d):
        inicio, medio, final = _estado(page, 0.0), _estado(page, 1.2), _estado(page, d)
    # SplitText: el título entra palabra por palabra
    assert len(inicio["palabras"]) == 5
    assert inicio["palabras"] == [0] * 5 and final["palabras"] == [1] * 5
    assert medio["palabras"][0] == 1
    # DrawSVG: el trazo se dibuja de nada a completo
    assert inicio["dibujado"] < 0.01 < medio["dibujado"] < 0.99 < final["dibujado"]
    # MorphSVG: la forma termina siendo otra
    assert inicio["forma"] != final["forma"]


def test_la_prueba_da_el_mismo_cuadro_para_el_mismo_t(chrome):
    with escena.pagina_de_escena(chrome, PRUEBA, SPEC_PRUEBA, escena.cargar_brand(None)) as (page, _):
        assert _hash(page, 1.3) == _hash(page, 1.3)


def test_el_orden_de_los_cuadros_no_cambia_ningun_cuadro_de_la_prueba(chrome):
    ts = [0.3, 1.2, 2.1, 2.8]
    brand = escena.cargar_brand(None)
    with escena.pagina_de_escena(chrome, PRUEBA, SPEC_PRUEBA, brand) as (page, _):
        en_orden = {t: _hash(page, t) for t in ts}
    with escena.pagina_de_escena(chrome, PRUEBA, SPEC_PRUEBA, brand) as (page, _):
        al_reves = {t: _hash(page, t) for t in reversed(ts)}
    assert en_orden == al_reves
    assert len(set(en_orden.values())) == len(ts), "cuatro momentos distintos tienen que verse distintos"


def test_la_prueba_no_se_mueve_sin_seek(chrome):
    with escena.pagina_de_escena(chrome, PRUEBA, SPEC_PRUEBA, escena.cargar_brand(None)) as (page, _):
        antes = escena._cuadro(page, 1.2)
        page.wait_for_timeout(600)
        assert page.screenshot(type="png") == antes
