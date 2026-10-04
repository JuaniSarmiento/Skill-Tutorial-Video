"""zonas.py: detección de momentos clave a partir de diffs entre cuadros del crudo
(S7a del Hito 2, docs/explicador/HITO2.md, decisión Q5 de Juani del 03/10/2026).

Capa pura (sin ffmpeg, sin numpy): se le dan cuadros en escala de grises ya armados a
mano, para poder triangular rápido los casos de ruido (cursor parpadeando, reloj),
scroll (cambia casi toda la pantalla) y cambio sostenido (momento clave de verdad).
Los tests que arman un crudo de verdad con ffmpeg están en test_editar_zonas.py.
"""
import zonas

ANCHO = 10
ALTO = 10
FONDO = bytes([50]) * (ANCHO * ALTO)


def _cuadro(fondo: bytes, caja: tuple[int, int, int, int] | None, valor: int = 220) -> bytes:
    """`fondo` con una caja (x0, y0, x1, y1) pintada a `valor`, o `fondo` tal cual si no hay caja."""
    datos = bytearray(fondo)
    if caja:
        x0, y0, x1, y1 = caja
        for y in range(y0, y1):
            for x in range(x0, x1):
                datos[y * ANCHO + x] = valor
    return bytes(datos)


def test_diff_bbox_sin_ninguna_diferencia_da_none():
    assert zonas._diff_bbox(FONDO, FONDO, ANCHO, umbral=30) is None


def test_diff_bbox_encuentra_la_caja_exacta_del_cambio():
    cuadro = _cuadro(FONDO, (3, 4, 6, 7))

    assert zonas._diff_bbox(FONDO, cuadro, ANCHO, umbral=30) == (3, 4, 6, 7)


def test_un_cambio_sostenido_es_un_momento_con_su_caja_e_importancia():
    # aparece una caja en el cuadro 1 y se queda ahí (no vuelve a FONDO): momento de verdad.
    con_caja = _cuadro(FONDO, (2, 2, 6, 6))  # área 16 de 100 -> 16%
    cuadros = [(0.0, FONDO), (0.5, con_caja), (1.0, con_caja)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    assert len(momentos) == 1
    m = momentos[0]
    assert m["t"] == 0.5
    assert (m["x"], m["y"], m["w"], m["h"]) == (2, 2, 4, 4)
    assert m["importancia"] > 0


def test_triangula_con_otra_caja_en_otra_posicion_y_otro_t():
    con_caja = _cuadro(FONDO, (6, 1, 9, 3))  # área 6 de 100 -> 6%
    cuadros = [(0.0, FONDO), (2.0, con_caja), (2.5, con_caja)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    assert len(momentos) == 1
    m = momentos[0]
    assert m["t"] == 2.0
    assert (m["x"], m["y"], m["w"], m["h"]) == (6, 1, 3, 2)


def test_un_cambio_que_vuelve_al_fondo_en_el_siguiente_cuadro_es_parpadeo_no_momento():
    # cursor/reloj: aparece en el cuadro 1 y en el cuadro 2 ya volvió a FONDO: ruido.
    parpadeo = _cuadro(FONDO, (4, 4, 6, 6))  # área 4 de 100 -> 4%, por encima de area_min_frac
    cuadros = [(0.0, FONDO), (0.5, parpadeo), (1.0, FONDO), (1.5, FONDO)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    assert momentos == []


def test_un_cambio_demasiado_chico_es_ruido_cursor_o_reloj():
    # una sola celda cambiada: por debajo de area_min_frac, aunque se sostenga.
    chico = _cuadro(FONDO, (5, 5, 6, 6))  # área 1 de 100 -> 1%
    cuadros = [(0.0, FONDO), (0.5, chico), (1.0, chico)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    assert momentos == []


def test_un_cambio_de_casi_toda_la_pantalla_es_scroll_no_momento():
    # el editor hace scroll: cambia el 81% de la pantalla, muy por encima de area_max_frac.
    scroll = _cuadro(FONDO, (0, 0, 9, 9))  # área 81 de 100
    cuadros = [(0.0, FONDO), (0.5, scroll), (1.0, scroll)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    assert momentos == []


def test_despues_del_scroll_el_siguiente_cambio_sostenido_sigue_siendo_momento():
    # el scroll actualiza el "estado estable" (si no, todo lo que venga después del
    # scroll se seguiría comparando contra la pantalla de ANTES del scroll).
    scroll = _cuadro(FONDO, (0, 0, 9, 9))
    con_caja = _cuadro(scroll, (0, 0, 4, 4), valor=10)  # nueva caja sobre el fondo YA scrolleado
    cuadros = [(0.0, FONDO), (0.5, scroll), (1.0, scroll), (1.5, con_caja), (2.0, con_caja)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    assert len(momentos) == 1
    assert momentos[0]["t"] == 1.5


def test_la_escala_convierte_la_caja_a_pixeles_del_crudo():
    con_caja = _cuadro(FONDO, (2, 2, 6, 6))
    cuadros = [(0.0, FONDO), (0.5, con_caja), (1.0, con_caja)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala=10.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    m = momentos[0]
    assert (m["x"], m["y"], m["w"], m["h"]) == (20, 20, 40, 40)


def test_una_caja_mas_grande_tiene_mas_importancia_que_una_chica():
    chica = _cuadro(FONDO, (2, 2, 4, 4))     # área 4
    grande = _cuadro(FONDO, (2, 2, 7, 7))    # área 25

    m_chica = zonas._momentos_en_cuadros(
        [(0.0, FONDO), (0.5, chica), (1.0, chica)], ANCHO, ALTO, escala=1.0,
        umbral=30, area_min_frac=0.02, area_max_frac=0.5)[0]
    m_grande = zonas._momentos_en_cuadros(
        [(0.0, FONDO), (0.5, grande), (1.0, grande)], ANCHO, ALTO, escala=1.0,
        umbral=30, area_min_frac=0.02, area_max_frac=0.5)[0]

    assert m_grande["importancia"] > m_chica["importancia"]


def test_sin_ningun_cuadro_cambiado_no_hay_momentos():
    cuadros = [(0.0, FONDO), (0.5, FONDO), (1.0, FONDO)]

    assert zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala=1.0,
                                       umbral=30, area_min_frac=0.02, area_max_frac=0.5) == []


def test_con_un_solo_cuadro_no_hay_nada_para_comparar():
    assert zonas._momentos_en_cuadros([(0.0, FONDO)], ANCHO, ALTO, escala=1.0,
                                       umbral=30, area_min_frac=0.02, area_max_frac=0.5) == []
