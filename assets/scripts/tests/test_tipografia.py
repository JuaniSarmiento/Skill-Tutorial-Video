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


# --- jerarquía para video y banda de subtítulos ----------------------------------

DIAGRAMA = {"kicker": "Cómo crece", "titulo": {"texto": "Con la plata pasa lo mismo"},
            "nodos": [{"id": "c", "texto": "Tu capital", "detalle": "US$ 1.000", "cue": 0.2},
                      {"id": "i", "texto": "Intereses", "detalle": "+ 10 %", "cue": 0.4},
                      {"id": "n", "texto": "Capital nuevo", "cue": 0.6}],
            "flechas": [{"de": "c", "a": "i", "texto": "genera", "cue": 0.3},
                        {"de": "i", "a": "n", "texto": "se suman", "cue": 0.5}]}
DATOS = {"kicker": "Mil dólares al 10 %", "titulo": {"texto": "El tiempo hace el trabajo"},
         "prefijo": "US$ ",
         "barras": [{"etiqueta": "Hoy", "valor": 1000, "cue": 0.2},
                    {"etiqueta": "10 años", "valor": 2594, "cue": 0.3},
                    {"etiqueta": "30 años", "valor": 17449, "cue": 0.4, "destacar": True}],
         "nota": "Interés compuesto anual, sin aportes extra"}
IMAGEN = escena.resolver_dibujos({
    "titulo": {"texto": "Una bola de nieve"},
    "dibujos": [{"id": "copo", "svg": str(escena.ESCENAS / "dibujos" / "copo.svg"), "cue": 0.2},
                {"id": "bola", "svg": str(escena.ESCENAS / "dibujos" / "bola-grande.svg"), "cue": 0.4}],
    "rotulos": [{"texto": "Tus ahorros", "de": "copo", "cue": 0.2},
                {"texto": "El resultado", "de": "bola", "cue": 0.4}]})
MUCHOS = {"titulo": {"texto": "Para llevarte"},
          "puntos": [{"texto": f"Una idea número {i + 1} para recordar", "cue": 0.1 * i} for i in range(6)]}
TODAS = [("presentacion", PORTADA), ("presentacion", LISTA), ("presentacion", MUCHOS),
         ("diagrama", DIAGRAMA), ("datos", DATOS), ("imagen", IMAGEN)]

CAJAS = """() => [...document.querySelectorAll('[data-caja]')].map(e => {
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return {n: e.dataset.caja, abajo: r.bottom, px: parseFloat(s.fontSize),
          familia: s.fontFamily.split(',')[0].replace(/"/g, '').trim()};
})"""


@pytest.mark.parametrize("tipo, spec", TODAS, ids=lambda x: x if isinstance(x, str) else "")
def test_el_contenido_deja_libre_la_banda_de_subtitulos(chrome, tipo, spec):
    cajas = _al_final(chrome, tipo, spec, CAJAS)
    assert cajas
    abajo = [(c["n"], round(c["abajo"])) for c in cajas if c["abajo"] > BANDA]
    assert abajo == [], f"invaden la banda de subtítulos (y > {BANDA:.0f}): {abajo}"


@pytest.mark.parametrize("tipo, spec", TODAS, ids=lambda x: x if isinstance(x, str) else "")
def test_sin_degrade_a_pantalla_completa(chrome, tipo, spec):
    # sobre fondo oscuro un degradé grande hace bandas en H.264
    assert _al_final(chrome, tipo, spec, "() => getComputedStyle(document.body).backgroundImage") == "none"


@pytest.mark.parametrize("spec", [PORTADA, LISTA, MUCHOS], ids=["portada", "lista", "muchos"])
def test_el_titulo_mide_entre_64_y_120_px(chrome, spec):
    px = _al_final(chrome, "presentacion", spec, "() => parseFloat(getComputedStyle(document.querySelector('.titulo')).fontSize)")
    assert 64 <= px <= 120, px


@pytest.mark.parametrize("tipo, spec, prefijo", [
    ("presentacion", LISTA, "punto"), ("presentacion", MUCHOS, "punto"),
    ("datos", DATOS, "categoria"), ("imagen", IMAGEN, "rotulo")])
def test_el_cuerpo_mide_entre_28_y_42_px(chrome, tipo, spec, prefijo):
    cajas = [c for c in _al_final(chrome, tipo, spec, CAJAS) if c["n"].startswith(prefijo)]
    assert cajas
    assert all(28 <= c["px"] <= 42 for c in cajas), [(c["n"], c["px"]) for c in cajas]


@pytest.mark.parametrize("tipo, spec, prefijo", [
    ("presentacion", PORTADA, "kicker"), ("datos", DATOS, "nota"), ("diagrama", DIAGRAMA, "flecha")])
def test_las_etiquetas_van_en_mono_entre_18_y_24_px(chrome, tipo, spec, prefijo):
    cajas = [c for c in _al_final(chrome, tipo, spec, CAJAS) if c["n"].startswith(prefijo)]
    assert cajas
    assert all(18 <= c["px"] <= 24 and c["familia"] == "IBM Plex Mono" for c in cajas), cajas


# --- número protagonista -----------------------------------------------------------

NUMERO = {"kicker": "Interés compuesto",
          "numero": {"texto": "10", "unidad": "años", "cue": 0.6},
          "contra": {"texto": "30", "unidad": "años", "cue": 1.2},
          "subtitulo": {"texto": "Si arrancás antes", "cue": 1.8}}

CIFRAS = """() => [...document.querySelectorAll('.cifra')].map(e => {
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return {px: parseFloat(s.fontSize), color: s.color, x0: r.left, x1: r.right, y0: r.top, y1: r.bottom};
})"""
COLOR = "v => { const d = document.createElement('div'); d.style.color = v; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return c; }"


def test_el_numero_protagonista_es_gigante_en_acento_y_el_de_contraste_en_tenue(chrome):
    brand = escena.cargar_brand(None)
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("presentacion"), {**NUMERO, "duracion": 3.0},
                                 brand) as (page, d):
        escena._cuadro(page, d - 0.05)
        cifras = page.evaluate(CIFRAS)
        acento, tenue = page.evaluate(COLOR, brand["colores"]["acento"]), page.evaluate(COLOR, brand["colores"]["tenue"])
    assert len(cifras) == 2
    numero, contra = cifras
    assert numero["px"] >= 300 and contra["px"] >= 300, cifras
    assert (numero["color"], contra["color"]) == (acento, tenue)
    assert numero["x1"] < contra["x0"], "el número y su contraste no pueden pisarse"
    assert all(c["x0"] >= 0 and c["x1"] <= 1920 and c["y0"] >= 0 and c["y1"] <= BANDA for c in cifras), cifras


def test_el_numero_protagonista_entra_en_su_cue(chrome):
    js = "() => [...document.querySelectorAll('.cifra')].map(e => +getComputedStyle(e.parentElement).opacity)"
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("presentacion"), {**NUMERO, "duracion": 3.0},
                                 escena.cargar_brand(None)) as (page, _):
        escena._cuadro(page, 0.55)
        antes = page.evaluate(js)
        escena._cuadro(page, 1.0)
        medio = page.evaluate(js)
    assert antes == [0, 0]
    assert medio[0] > 0.9 and medio[1] == 0


def test_un_numero_largo_que_no_entra_a_300_px_falla_nombrandolo(chrome):
    spec = {"numero": {"texto": "1.234.567.890", "unidad": "pesos", "cue": 0.2},
            "contra": {"texto": "9.876.543.210", "cue": 0.4}, "duracion": 1.0}
    with pytest.raises(escena.ContratoError, match="1.234.567.890"):
        with escena.pagina_de_escena(chrome, escena.ruta_plantilla("presentacion"), spec,
                                     escena.cargar_brand(None)) as (page, _):
            escena._cuadro(page, 0.5)   # la escena se arma en el primer seek


def test_numero_y_puntos_juntos_es_un_error(chrome):
    spec = {**LISTA, "numero": {"texto": "10", "cue": 0.2}, "duracion": 1.0}
    with pytest.raises(escena.ContratoError, match="numero"):
        with escena.pagina_de_escena(chrome, escena.ruta_plantilla("presentacion"), spec, escena.cargar_brand(None)):
            pass


@pytest.mark.parametrize("tipo, spec", [
    ("diagrama", {"nodos": [{"id": "a", "texto": "Abajo", "x": 0.3, "y": 0.97, "cue": 0.1},
                            {"id": "b", "texto": "Arriba", "x": 0.7, "y": 0.5, "cue": 0.2}]}),
    ("imagen", escena.resolver_dibujos({
        "dibujos": [{"id": "copo", "svg": str(escena.ESCENAS / "dibujos" / "copo.svg"), "x": 0.3, "y": 0.97, "cue": 0.1},
                    {"id": "bola", "svg": str(escena.ESCENAS / "dibujos" / "bola-grande.svg"), "x": 0.7, "y": 0.5, "cue": 0.2}],
        "rotulos": [{"texto": "Abajo de todo", "de": "copo", "cue": 0.1}]})),
], ids=["diagrama-xy", "imagen-xy"])
def test_una_posicion_x_y_bien_abajo_tampoco_invade_la_banda(chrome, tipo, spec):
    cajas = _al_final(chrome, tipo, spec, CAJAS)
    abajo = [(c["n"], round(c["abajo"])) for c in cajas if c["abajo"] > BANDA]
    assert abajo == [], abajo


def test_el_punto_en_foco_va_en_texto_y_los_anteriores_en_tenue(chrome):
    brand = escena.cargar_brand(None)
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("presentacion"), {**LISTA, "duracion": 3.0},
                                 brand) as (page, d):
        escena._cuadro(page, d - 0.05)
        colores = page.evaluate("() => [...document.querySelectorAll('.txt')].map(e => getComputedStyle(e).color)")
        texto, tenue = page.evaluate(COLOR, brand["colores"]["texto"]), page.evaluate(COLOR, brand["colores"]["tenue"])
    assert colores == [tenue, texto]


def test_el_titulo_de_cabecera_es_mas_pesado_que_el_cuerpo(chrome):
    pesos = _al_final(chrome, "presentacion", LISTA, """() => ['.titulo', '.txt'].map(
        s => +getComputedStyle(document.querySelector(s)).fontWeight)""")
    assert pesos[0] >= 800 and pesos[1] <= 600, pesos
