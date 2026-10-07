"""H5 (HITO3.md): la escena `linea-de-vida` contra Chrome.

Un eje de años/edades con tramos que se dibujan uno por fila (ejemplo de HITO3.md: Ana
25→35, Sofía 35→65).
"""
import hashlib

import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402

pytestmark = pytest.mark.integracion

ANA_SOFIA = {
    "tipo": "linea-de-vida", "titulo": {"texto": "Diez años de diferencia"},
    "tramos": [{"nombre": "Ana", "desde": 25, "hasta": 35, "cue": 0.4},
               {"nombre": "Sofía", "desde": 35, "hasta": 65, "cue": 2.4}],
    "duracion": 5.0,
}


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def _abrir(chrome, spec=ANA_SOFIA):
    return escena.pagina_de_escena(chrome, escena.ruta_plantilla("linea-de-vida"), spec, escena.cargar_brand(None))


def _tramos(page, t):
    escena._cuadro(page, t)
    # DrawSVGPlugin codifica el avance en stroke-dasharray (el largo visible), no en
    # stroke-dashoffset (que se queda cerca de 0 en el modo de dibujo "desde el inicio").
    return page.evaluate("""() => [...document.querySelectorAll('svg line[stroke="var(--acento)"]')].map(l => ({
        visible: parseFloat(l.style.strokeDasharray.split(',')[0]), largo: l.getTotalLength(),
        op: +l.style.opacity}))""")


def _nombres_visibles(page, t):
    escena._cuadro(page, t)
    return page.evaluate("""() => [...document.querySelectorAll('.nombre')]
        .filter(e => +getComputedStyle(e).opacity > 0.5).map(e => e.textContent)""")


# --- cada tramo se dibuja en su cue ---------------------------------------------------

def test_antes_de_cualquier_cue_no_se_ve_ningun_nombre(chrome):
    with _abrir(chrome) as (page, _):
        assert _nombres_visibles(page, 0.1) == []


def test_ana_aparece_antes_que_sofia(chrome):
    with _abrir(chrome) as (page, _):
        a_los_1s = _nombres_visibles(page, 1.0)
        a_los_3s = _nombres_visibles(page, 3.0)
    assert a_los_1s == ["Ana"]
    assert set(a_los_3s) == {"Ana", "Sofía"}


def test_el_trazo_de_cada_tramo_crece_de_0_a_100_por_ciento(chrome):
    with _abrir(chrome) as (page, d):
        recien = _tramos(page, 0.5)[0]
        avanzado = _tramos(page, 1.2)[0]
    assert 0 < recien["visible"] < recien["largo"]
    assert recien["visible"] < avanzado["visible"] <= avanzado["largo"] + 0.5


# --- triangulación: otro eje, otra cantidad de tramos --------------------------------

def test_con_un_solo_tramo_y_otro_rango_el_eje_cambia(chrome):
    spec = {"tipo": "linea-de-vida", "tramos": [{"nombre": "Proyecto", "desde": 0, "hasta": 6, "cue": 0.2}],
            "eje": {"desde": 0, "hasta": 12, "unidad": "meses"}, "duracion": 2.0}
    with _abrir(chrome, spec) as (page, d):
        escena._cuadro(page, d - 0.05)
        marcas = page.evaluate("() => [...document.querySelectorAll('.marca')].map(e => e.textContent)")
    assert "0 meses" in marcas and "6 meses" in marcas


# --- llena el área: barras gruesas y etiquetas grandes (H5 ronda 2, HITO3.md) -------

def _anchos_trazo(page, t):
    escena._cuadro(page, t)
    return page.evaluate("""() => [...document.querySelectorAll('svg line[stroke="var(--acento)"]')]
        .map(l => parseFloat(getComputedStyle(l).strokeWidth))""")


def test_las_barras_son_gruesas_legibles_en_celular(chrome):
    with _abrir(chrome) as (page, d):
        anchos = _anchos_trazo(page, d - 0.05)
    assert anchos and all(w >= 24 for w in anchos), anchos


def test_con_un_solo_tramo_la_barra_es_mas_gruesa_que_con_dos(chrome):
    uno = {"tipo": "linea-de-vida", "tramos": [{"nombre": "Sola", "desde": 0, "hasta": 10, "cue": 0.2}],
           "duracion": 1.5}
    with _abrir(chrome, uno) as (page, d):
        ancho_uno = _anchos_trazo(page, d - 0.05)[0]
    with _abrir(chrome) as (page, d):   # ANA_SOFIA, dos tramos
        ancho_dos = _anchos_trazo(page, d - 0.05)[0]
    assert ancho_uno > ancho_dos, (ancho_uno, ancho_dos)


def test_las_marcas_del_eje_miden_al_menos_24px(chrome):
    with _abrir(chrome) as (page, d):
        escena._cuadro(page, d - 0.05)
        pxs = page.evaluate(
            "() => [...document.querySelectorAll('.marca')].map(e => parseFloat(getComputedStyle(e).fontSize))")
    assert pxs and all(p >= 24 for p in pxs), pxs


# --- etiqueta de rango legible y sin pisar el fin de la barra (H9b, HITO3.md) ---------

def _rangos(page, t):
    escena._cuadro(page, t)
    return page.evaluate("""() => [...document.querySelectorAll('.rango')].map(e => {
        const r = e.getBoundingClientRect();
        return {px: parseFloat(getComputedStyle(e).fontSize), izq: r.left};
    })""")


def _fin_de_barra(page, t):
    """x2 + la mitad del grosor de cada trazo: el punto más a la derecha donde el
    stroke-linecap:round todavía pinta algo (H9b)."""
    escena._cuadro(page, t)
    return page.evaluate("""() => [...document.querySelectorAll('svg line[stroke="var(--acento)"]')].map(l =>
        parseFloat(l.getAttribute('x2')) + parseFloat(getComputedStyle(l).strokeWidth) / 2)""")


def test_la_etiqueta_de_rango_mide_al_menos_32px(chrome):
    # piso subido de 28 a 32px (H10, HITO3.md): a 28 se veía chico al lado del
    # resto de las etiquetas secundarias en mono de la misma familia de escenas.
    with _abrir(chrome) as (page, d):
        rangos = _rangos(page, d - 0.05)
    assert rangos and all(r["px"] >= 32 for r in rangos), rangos


def test_la_etiqueta_de_rango_no_pisa_la_punta_redondeada_de_la_barra(chrome):
    with _abrir(chrome) as (page, d):
        rangos = _rangos(page, d - 0.05)
        fines = _fin_de_barra(page, d - 0.05)
    assert len(rangos) == len(fines)
    for r, fin in zip(rangos, fines):
        assert r["izq"] >= fin, (r, fin)


def test_con_un_solo_tramo_grueso_la_etiqueta_de_rango_tampoco_pisa_la_barra(chrome):
    # un solo tramo: la barra es más gruesa (ver test_con_un_solo_tramo_la_barra_es_mas_gruesa_que_con_dos),
    # así que el gorro redondeado avanza más: el caso que más fuerza el solape.
    spec = {"tipo": "linea-de-vida", "tramos": [{"nombre": "Sola", "desde": 0, "hasta": 10, "cue": 0.2}],
            "duracion": 1.5}
    with _abrir(chrome, spec) as (page, d):
        rangos = _rangos(page, d - 0.05)
        fines = _fin_de_barra(page, d - 0.05)
    assert rangos[0]["izq"] >= fines[0], (rangos, fines)


# --- determinismo ---------------------------------------------------------------------

def _hash(page, t):
    return hashlib.sha256(escena._cuadro(page, t)).hexdigest()


def test_el_mismo_t_da_el_mismo_cuadro_en_cualquier_orden(chrome):
    ts = [0.2, 1.3, 2.9, 4.5]
    with _abrir(chrome) as (page, _):
        en_orden = {t: _hash(page, t) for t in ts}
    with _abrir(chrome) as (page, _):
        al_reves = {t: _hash(page, t) for t in reversed(ts)}
    assert en_orden == al_reves
    assert len(set(en_orden.values())) == len(ts)


def test_un_eje_con_hasta_menor_o_igual_a_desde_falla_claro(chrome):
    spec = {"tipo": "linea-de-vida", "tramos": [{"nombre": "X", "desde": 10, "hasta": 10, "cue": 0.2}],
            "duracion": 2.0}
    with pytest.raises(escena.ContratoError, match="hasta > desde"):
        with _abrir(chrome, spec) as (page, d):
            escena._cuadro(page, d - 0.05)
