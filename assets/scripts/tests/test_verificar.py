"""H2 (HITO3.md): la puerta `check` antes del render, en sus partes puras.

`verificar.py` lleva la escena a N tiempos y mide lo que se ve. Acá se prueba lo que
no necesita Chrome: el contraste WCAG, qué tiempos se muestrean y qué cuenta como
hallazgo en un cuadro ya medido.
"""
import pytest

import verificar


# --- contraste (WCAG 2.x) ------------------------------------------------------------

def test_blanco_sobre_negro_es_21_a_1():
    assert verificar.contraste((255, 255, 255), (0, 0, 0)) == pytest.approx(21.0)


def test_el_contraste_no_depende_del_orden():
    a, b = (0x8B, 0x91, 0x9C), (0x11, 0x13, 0x18)
    assert verificar.contraste(a, b) == pytest.approx(verificar.contraste(b, a))
    assert verificar.contraste(a, b) == pytest.approx(5.86, abs=0.02)   # tenue sobre fondo, a mano: 0.3313 / 0.0565


def test_mismo_color_es_1_a_1():
    assert verificar.contraste((40, 40, 40), (40, 40, 40)) == pytest.approx(1.0)


@pytest.mark.parametrize("px, peso, umbral", [
    (16, 400, 4.5), (23.9, 700, 4.5), (24, 700, 3.0), (24, 600, 4.5), (31.9, 500, 4.5), (32, 400, 3.0)])
def test_el_umbral_baja_a_3_para_texto_grande(px, peso, umbral):
    assert verificar.umbral(px, peso) == umbral


@pytest.mark.parametrize("css, rgba", [
    ("rgb(17, 19, 24)", (17, 19, 24, 1.0)),
    ("rgba(242, 181, 68, 0.5)", (242, 181, 68, 0.5)),
    ("rgba(0, 0, 0, 0)", (0, 0, 0, 0.0)),
    # lo que devuelve Chrome para un color-mix(in srgb, ...)
    ("color(srgb 0.665098 0.680392 0.705882)", (170, 173, 180, 1.0)),
    ("color(srgb 1 0 0 / 0.5)", (255, 0, 0, 0.5)),
])
def test_lee_los_colores_que_devuelve_getcomputedstyle(css, rgba):
    assert verificar.color(css) == rgba


# --- tiempos de muestra -----------------------------------------------------------------

def test_muestrea_n_tiempos_parejos_y_justo_antes_y_despues_de_cada_cue():
    ts = verificar.tiempos_de_muestra(6.0, [2.0], n=4)
    assert [0.0, 1.5, 3.0, 4.5] == [t for t in ts if t in (0.0, 1.5, 3.0, 4.5)]
    assert 1.95 in ts and 2.6 in ts
    assert ts == sorted(set(ts))


def test_los_tiempos_de_muestra_quedan_dentro_de_la_escena():
    ts = verificar.tiempos_de_muestra(3.0, [0.0, 2.9], n=3)
    assert min(ts) >= 0 and max(ts) < 3.0


# --- hallazgos de un cuadro ---------------------------------------------------------------

def _caja(n, x0, y0, x1, y1, **extra):
    return {"n": n, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "op": 1.0, "texto": True,
            "desborda": False, "t": None, **extra}


def _tipos(hallazgos):
    return sorted(h.tipo for h in hallazgos)


def test_un_cuadro_limpio_no_tiene_hallazgos():
    cajas = [_caja("titulo", 140, 100, 900, 190), _caja("punto 1", 140, 400, 900, 450)]
    assert verificar.hallazgos_del_cuadro("00.json", 2.0, cajas, []) == []


def test_dos_textos_visibles_que_se_pisan_se_nombran_con_escena_y_tiempo():
    cajas = [_caja("nodo a", 100, 100, 500, 200), _caja("flecha rinde", 450, 150, 700, 190)]
    h = verificar.hallazgos_del_cuadro("04.json", 3.25, cajas, [])
    assert _tipos(h) == ["solape"]
    assert "04.json" in h[0].texto and "3.25" in h[0].texto
    assert "nodo a" in h[0].texto and "flecha rinde" in h[0].texto


def test_un_texto_invisible_no_pisa_a_nadie():
    cajas = [_caja("nodo a", 100, 100, 500, 200), _caja("flecha rinde", 450, 150, 700, 190, op=0.0)]
    assert verificar.hallazgos_del_cuadro("04.json", 1.0, cajas, []) == []


def test_un_dibujo_sin_texto_no_cuenta_como_solape():
    cajas = [_caja("dibujo copo", 100, 100, 500, 500, texto=False), _caja("rotulo", 120, 450, 480, 520)]
    assert verificar.hallazgos_del_cuadro("03.json", 1.0, cajas, []) == []


@pytest.mark.parametrize("caja", [
    _caja("punto 9", 140, 860, 900, 930),        # invade la banda de subtítulos
    _caja("valor", 1800, 400, 1990, 460),        # se sale por la derecha
    _caja("categoria", 140, 700, 300, 740, desborda=True),   # se sale de su propia caja
])
def test_un_texto_que_se_sale_del_cuadro_util_o_de_su_caja_es_desborde(caja):
    h = verificar.hallazgos_del_cuadro("02.json", 4.0, [caja], [])
    assert _tipos(h) == ["desborde"]
    assert caja["n"] in h[0].texto


def test_un_elemento_visible_antes_de_su_cue_se_nombra_con_su_cue():
    cajas = [_caja("punto 2", 140, 400, 900, 450, t=3.0, op=0.4)]
    h = verificar.hallazgos_del_cuadro("01.json", 2.95, cajas, [])
    assert _tipos(h) == ["cue"]
    assert "punto 2" in h[0].texto and "3.00" in h[0].texto


def test_un_elemento_invisible_antes_de_su_cue_esta_bien():
    cajas = [_caja("punto 2", 140, 400, 900, 450, t=3.0, op=0.0)]
    assert verificar.hallazgos_del_cuadro("01.json", 2.95, cajas, []) == []


def _texto(n, color, fondo, px=36, peso=500, op=1.0):
    return {"n": n, "color": color, "fondo": fondo, "px": px, "peso": peso, "op": op}


def test_un_texto_con_contraste_2_a_1_es_hallazgo_con_la_razon_medida():
    textos = [_texto("punto 1", "rgb(119, 119, 119)", "rgb(37, 37, 37)", px=28)]
    h = verificar.hallazgos_del_cuadro("01.json", 2.0, [], textos)
    assert _tipos(h) == ["contraste"]
    assert "punto 1" in h[0].texto and "4.5" in h[0].texto


def test_texto_grande_con_3_5_a_1_pasa_y_chico_no():
    gris, fondo = "rgb(130, 130, 130)", "rgb(30, 30, 30)"   # ~4,1:1
    assert verificar.hallazgos_del_cuadro("x", 1.0, [], [_texto("grande", gris, fondo, px=40)]) == []
    # px=30 (no 20): acá se prueba sólo el umbral de CONTRASTE, no "texto chico" (más abajo)
    assert _tipos(verificar.hallazgos_del_cuadro("x", 1.0, [], [_texto("chico", gris, fondo, px=30)])) == ["contraste"]


def test_el_color_semitransparente_se_mezcla_con_el_fondo_antes_de_medir():
    # blanco al 20 % sobre negro es un gris oscuro: no llega a 4,5 (px=26: sólo contraste)
    textos = [_texto("nota", "rgba(255, 255, 255, 0.2)", "rgb(0, 0, 0)", px=26)]
    assert _tipos(verificar.hallazgos_del_cuadro("x", 1.0, [], textos)) == ["contraste"]


def test_un_texto_entrando_a_mitad_de_fundido_no_se_mide():
    textos = [_texto("punto 1", "rgb(119, 119, 119)", "rgb(37, 37, 37)", op=0.5)]
    assert verificar.hallazgos_del_cuadro("x", 1.0, [], textos) == []


# --- texto chico (H5 ronda 2, HITO3.md): legible en un celular --------------------------

def test_un_texto_de_16px_es_texto_chico():
    # blanco sobre negro: contraste de sobra, así que el único hallazgo es el tamaño
    textos = [_texto("etiqueta", "rgb(255, 255, 255)", "rgb(0, 0, 0)", px=16)]
    h = verificar.hallazgos_del_cuadro("x", 1.0, [], textos)
    assert _tipos(h) == ["texto_chico"]
    assert "etiqueta" in h[0].texto and "16" in h[0].texto


def test_una_etiqueta_mono_de_24px_pasa():
    textos = [_texto("kicker", "rgb(255, 255, 255)", "rgb(0, 0, 0)", px=24)]
    assert verificar.hallazgos_del_cuadro("x", 1.0, [], textos) == []


def test_el_umbral_de_texto_chico_es_configurable():
    textos = [_texto("etiqueta", "rgb(255, 255, 255)", "rgb(0, 0, 0)", px=16)]
    assert verificar.hallazgos_del_cuadro("x", 1.0, [], textos, umbral_texto_chico=12) == []
