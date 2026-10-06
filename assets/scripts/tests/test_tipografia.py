"""H2 (HITO3.md): dirección visual de las plantillas, contra Chrome.

Tipografía propia embebida (Barlow para títulos y números, IBM Plex Mono para
etiquetas), jerarquía para video (títulos 64–120 px, cuerpo 28–42, etiquetas 18–24 en
mono), número protagonista y banda libre para subtítulos (el contenido vive en el 83 %
superior del cuadro).
"""
import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402

pytestmark = pytest.mark.integracion

BANDA = 0.83 * 1080   # px: debajo de esto van los subtítulos


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def _al_final(chrome, tipo, spec, js, brand=None):
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), {"duracion": 3.0, **spec},
                                 brand or escena.cargar_brand(None)) as (page, d):
        escena._cuadro(page, d - 0.05)
        return page.evaluate(js)


# familia que pinta de verdad un elemento: la primera de su font-family que está CARGADA
# en document.fonts (Barlow y Plex Mono no están instaladas en el sistema: si no las
# trae @font-face, no están).
FAMILIA = """sel => {
  const e = document.querySelector(sel);
  const pedida = getComputedStyle(e).fontFamily.split(',')[0].trim().replace(/"/g, '');
  const cargada = [...document.fonts].some(f => f.family.replace(/"/g, '') === pedida && f.status === 'loaded');
  return cargada ? pedida : 'NO CARGADA: ' + pedida;
}"""

PORTADA = {"kicker": "Interés compuesto", "titulo": {"texto": "Ahorrar 10 años le gana a ahorrar 30"}}
LISTA = {"kicker": "Para llevarte", "titulo": {"texto": "Lo que importa"},
         "puntos": [{"texto": "Los intereses ganan intereses", "cue": 0.2},
                    {"texto": "El que multiplica es el tiempo", "cue": 0.4}]}


@pytest.mark.parametrize("sel, familia", [(".titulo", "Barlow"), (".kicker", "IBM Plex Mono")])
def test_titulo_en_barlow_y_kicker_en_mono_cargadas_desde_la_skill(chrome, sel, familia):
    assert _al_final(chrome, "presentacion", PORTADA, f"() => ({FAMILIA})('{sel}')") == familia


def test_la_numeracion_de_los_puntos_va_en_mono(chrome):
    assert _al_final(chrome, "presentacion", LISTA, f"() => ({FAMILIA})('.num')") == "IBM Plex Mono"


def test_si_la_fuente_mono_del_brand_no_existe_avisa_nombrandola(chrome, capsys):
    brand = {**escena.cargar_brand(None), "fuente_mono": "Mono Que No Existe"}
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("presentacion"), {**PORTADA, "duracion": 1.0}, brand):
        pass
    err = capsys.readouterr().err
    assert "AVISO" in err and "Mono Que No Existe" in err
