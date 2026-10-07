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


# ronda 2 (orquestador): una lista de hasta 4 puntos NO es cuerpo, va grande (abajo)
@pytest.mark.parametrize("tipo, spec, prefijo", [
    ("presentacion", MUCHOS, "punto"), ("datos", DATOS, "categoria"), ("imagen", IMAGEN, "rotulo")])
def test_el_cuerpo_mide_entre_28_y_42_px(chrome, tipo, spec, prefijo):
    cajas = [c for c in _al_final(chrome, tipo, spec, CAJAS) if c["n"].startswith(prefijo)]
    assert cajas
    assert all(28 <= c["px"] <= 42 for c in cajas), [(c["n"], c["px"]) for c in cajas]


# la etiqueta de flecha de diagrama salió de este rango en H9b/H10: lleva contenido y se lee
# en celular, su piso (32 px) lo fija test_plantillas.py
@pytest.mark.parametrize("tipo, spec, prefijo", [
    ("presentacion", PORTADA, "kicker"), ("datos", DATOS, "nota")])
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


def test_el_punto_en_foco_va_en_texto_y_los_anteriores_atenuados_pero_bien_legibles(chrome):
    import verificar
    brand = escena.cargar_brand(None)
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("presentacion"), {**LISTA, "duracion": 3.0},
                                 brand) as (page, d):
        escena._cuadro(page, d - 0.05)
        colores = page.evaluate("() => [...document.querySelectorAll('.txt')].map(e => getComputedStyle(e).color)")
        texto, fondo = page.evaluate(COLOR, brand["colores"]["texto"]), page.evaluate(COLOR, brand["colores"]["fondo"])
    anterior, foco = colores
    assert foco == texto and anterior != texto
    # ronda 2: en la hoja el tenue (5,9:1) se veía casi invisible; los anteriores van a >= 7:1 (AAA)
    razon = verificar.contraste(verificar.color(anterior), verificar.color(fondo))
    assert razon >= 7.0, f"{anterior} sobre el fondo da {razon:.2f}:1"


def test_el_titulo_de_cabecera_es_mas_pesado_que_el_cuerpo(chrome):
    pesos = _al_final(chrome, "presentacion", LISTA, """() => ['.titulo', '.txt'].map(
        s => +getComputedStyle(document.querySelector(s)).fontWeight)""")
    assert pesos[0] >= 800 and pesos[1] <= 600, pesos


# --- ronda 2 (orquestador, 06/10): igual o más grande que antes de H2 ----------------
# Las cifras de "antes" se midieron con las plantillas de 6070acc sobre el explicador v02
# (Inter): puntos de 62 px, lista de 315 px de alto con 3 puntos y 437 con 4, barras de
# hasta 480 px, valores de 54 px. Barlow es más angosta que Inter: a igual px se ve más chica.

ANA = {"kicker": "Mil dólares por año, al 7 %", "titulo": {"texto": "Ana contra Sofía"},
       "puntos": [{"texto": "Ana ahorra de los 25 a los 35, y para", "cue": 0.2},
                  {"texto": "Sofía ahorra de los 35 a los 65", "cue": 0.4},
                  {"texto": "¿Quién tiene más a los 65?", "cue": 0.6}]}
REGLA = {"kicker": "Un atajo para hacer la cuenta", "titulo": {"texto": "La regla del 72"},
         "puntos": [{"texto": "72 ÷ tasa", "cue": 0.2}, {"texto": "= años para duplicar tu plata", "cue": 0.4},
                    {"texto": "Al 10 %: unos 7 años", "cue": 0.6}, {"texto": "Al 7 %: unos 10 años", "cue": 0.8}]}
LISTA_JS = """() => {
  const t = [...document.querySelectorAll('.txt')], r = [...document.querySelectorAll('.punto')].map(e => e.getBoundingClientRect());
  const cab = document.querySelector('.cabecera').getBoundingClientRect();
  return {px: Math.min(...t.map(e => parseFloat(getComputedStyle(e).fontSize))),
          arriba: Math.min(...r.map(x => x.top)), abajo: Math.max(...r.map(x => x.bottom)), cab: cab.bottom};
}"""


@pytest.mark.parametrize("spec, alto_antes", [(ANA, 315), (REGLA, 437)], ids=["3-puntos", "4-puntos"])
def test_una_lista_de_hasta_4_puntos_va_grande_y_ocupa_el_area(chrome, spec, alto_antes):
    m = _al_final(chrome, "presentacion", spec, LISTA_JS)
    assert m["px"] >= 62, m
    assert m["abajo"] - m["arriba"] >= alto_antes, m
    # centrada entre la cabecera y la banda, no pegada arriba
    assert abs((m["arriba"] + m["abajo"]) / 2 - (m["cab"] + BANDA) / 2) <= 40, m


def test_una_lista_de_4_puntos_largos_no_baja_de_44_px(chrome):
    spec = {"titulo": {"texto": "Para llevarte"},
            "puntos": [{"texto": f"Una idea bastante larga número {i + 1} que conviene recordar", "cue": 0.1 * i}
                       for i in range(4)]}
    m = _al_final(chrome, "presentacion", spec, LISTA_JS)
    assert m["px"] >= 44, m


BARRAS_JS = """() => ({
  valor: Math.min(...[...document.querySelectorAll('.valor')].map(e => parseFloat(getComputedStyle(e).fontSize))),
  alto: Math.max(...[...document.querySelectorAll('.barra')].map(e => e.getBoundingClientRect().height))})"""


@pytest.mark.parametrize("spec, alto", [(DATOS, 400), ({**DATOS, "nota": None}, 440)], ids=["con-nota", "sin-nota"])
def test_datos_las_cifras_se_leen_en_un_celular_y_el_grafico_usa_el_area(chrome, spec, alto):
    # sin nota (como las 4 escenas datos del ejemplo) el gráfico vuelve a casi su alto de
    # antes (480); la nota se come un renglón más antes de la banda
    m = _al_final(chrome, "datos", {k: v for k, v in spec.items() if v is not None}, BARRAS_JS)
    assert m["valor"] >= 60, m
    assert m["alto"] >= alto, m


def test_diagrama_el_texto_y_el_detalle_de_cada_nodo_miden_al_menos_34_px(chrome):
    px = _al_final(chrome, "diagrama", DIAGRAMA, """() => [...document.querySelectorAll('.nodo .txt, .nodo .det')]
        .map(e => parseFloat(getComputedStyle(e).fontSize))""")
    assert px and min(px) >= 34, px


def test_el_kicker_va_al_tope_de_las_etiquetas(chrome):
    px = _al_final(chrome, "presentacion", LISTA, "() => parseFloat(getComputedStyle(document.querySelector('.kicker')).fontSize)")
    assert px == 24


def test_el_subtitulo_de_la_portada_compensa_que_barlow_es_mas_angosta(chrome):
    # antes de H2: 48 px en Inter; Barlow a 48 ocupa ~11 % menos de ancho
    spec = {**PORTADA, "subtitulo": {"texto": "Si arrancás antes", "cue": 0.5}}
    px = _al_final(chrome, "presentacion", spec, "() => parseFloat(getComputedStyle(document.querySelector('.sub')).fontSize)")
    assert px >= 54, px


# --- paletas (H10, HITO3.md): toda escena del ejemplo pasa contraste/solape/desborde
# en las 4 paletas, incluidas las de fondo claro --------------------------------------

import verificar  # noqa: E402


@pytest.mark.parametrize("tipo, spec", TODAS, ids=lambda x: x if isinstance(x, str) else "")
@pytest.mark.parametrize("paleta", escena.paletas_validas())
def test_toda_escena_del_ejemplo_pasa_verificar_en_cada_paleta(chrome, tipo, spec, paleta):
    brand = escena.cargar_brand(None, paleta=paleta)
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla(tipo), {"duracion": 3.0, **spec}, brand) as (page, d):
        hallazgos = verificar.verificar_pagina(page, d, {"duracion": 3.0, **spec}, f"{tipo}/{paleta}")
    assert hallazgos == [], (paleta, verificar.informe(hallazgos))
