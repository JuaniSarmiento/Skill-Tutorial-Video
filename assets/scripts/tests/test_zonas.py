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

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala_x=1.0, escala_y=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    assert len(momentos) == 1
    m = momentos[0]
    assert m["t"] == 0.5
    assert (m["x"], m["y"], m["w"], m["h"]) == (2, 2, 4, 4)
    assert m["importancia"] > 0


def test_triangula_con_otra_caja_en_otra_posicion_y_otro_t():
    con_caja = _cuadro(FONDO, (6, 1, 9, 3))  # área 6 de 100 -> 6%
    cuadros = [(0.0, FONDO), (2.0, con_caja), (2.5, con_caja)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala_x=1.0, escala_y=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    assert len(momentos) == 1
    m = momentos[0]
    assert m["t"] == 2.0
    assert (m["x"], m["y"], m["w"], m["h"]) == (6, 1, 3, 2)


def test_un_cambio_que_vuelve_al_fondo_en_el_siguiente_cuadro_es_parpadeo_no_momento():
    # cursor/reloj: aparece en el cuadro 1 y en el cuadro 2 ya volvió a FONDO: ruido.
    parpadeo = _cuadro(FONDO, (4, 4, 6, 6))  # área 4 de 100 -> 4%, por encima de area_min_frac
    cuadros = [(0.0, FONDO), (0.5, parpadeo), (1.0, FONDO), (1.5, FONDO)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala_x=1.0, escala_y=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    assert momentos == []


def test_un_cambio_demasiado_chico_es_ruido_cursor_o_reloj():
    # una sola celda cambiada: por debajo de area_min_frac, aunque se sostenga.
    chico = _cuadro(FONDO, (5, 5, 6, 6))  # área 1 de 100 -> 1%
    cuadros = [(0.0, FONDO), (0.5, chico), (1.0, chico)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala_x=1.0, escala_y=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    assert momentos == []


def test_un_cambio_de_casi_toda_la_pantalla_es_scroll_no_momento():
    # el editor hace scroll: cambia el 81% de la pantalla, muy por encima de area_max_frac.
    scroll = _cuadro(FONDO, (0, 0, 9, 9))  # área 81 de 100
    cuadros = [(0.0, FONDO), (0.5, scroll), (1.0, scroll)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala_x=1.0, escala_y=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    assert momentos == []


def test_despues_del_scroll_el_siguiente_cambio_sostenido_sigue_siendo_momento():
    # el scroll actualiza el "estado estable" (si no, todo lo que venga después del
    # scroll se seguiría comparando contra la pantalla de ANTES del scroll).
    scroll = _cuadro(FONDO, (0, 0, 9, 9))
    con_caja = _cuadro(scroll, (0, 0, 4, 4), valor=10)  # nueva caja sobre el fondo YA scrolleado
    cuadros = [(0.0, FONDO), (0.5, scroll), (1.0, scroll), (1.5, con_caja), (2.0, con_caja)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala_x=1.0, escala_y=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    assert len(momentos) == 1
    assert momentos[0]["t"] == 1.5


def test_la_escala_convierte_la_caja_a_pixeles_del_crudo():
    con_caja = _cuadro(FONDO, (2, 2, 6, 6))
    cuadros = [(0.0, FONDO), (0.5, con_caja), (1.0, con_caja)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala_x=10.0, escala_y=10.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    m = momentos[0]
    assert (m["x"], m["y"], m["w"], m["h"]) == (20, 20, 40, 40)


def test_escala_distinta_por_eje_n1():
    # N1: una sola escala para los dos ejes corre la caja en resoluciones no 16:9
    # (hoy hasta 34px en y); x/y tienen que escalar cada uno con su propio factor.
    con_caja = _cuadro(FONDO, (2, 2, 6, 6))
    cuadros = [(0.0, FONDO), (0.5, con_caja), (1.0, con_caja)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala_x=2.0, escala_y=5.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    m = momentos[0]
    assert (m["x"], m["y"], m["w"], m["h"]) == (4, 10, 8, 20)


def test_el_tipeo_de_un_comando_tiene_mas_importancia_que_un_digito_de_barra_de_estado():
    # NOTE "Importancia": mide píxeles cambiados de verdad, no el área de la caja -así
    # una línea con varios caracteres tipeados (muchos píxeles cambiados) pesa más que
    # un solo dígito de una barra de estado (un único píxel cambiado).
    comando = _cuadro(FONDO, (1, 1, 8, 3))  # "línea" de varios caracteres, bien sostenida
    digito = _cuadro(FONDO, (1, 1, 2, 2))   # un solo píxel: un dígito angosto de la barra

    m_comando = zonas._momentos_en_cuadros(
        [(0.0, FONDO), (0.5, comando), (1.0, comando)], ANCHO, ALTO, escala_x=1.0, escala_y=1.0,
        umbral=30, area_min_frac=0.005, area_max_frac=0.5)[0]
    m_digito = zonas._momentos_en_cuadros(
        [(0.0, FONDO), (0.5, digito), (1.0, digito)], ANCHO, ALTO, escala_x=1.0, escala_y=1.0,
        umbral=30, area_min_frac=0.005, area_max_frac=0.5)[0]

    assert m_comando["importancia"] > m_digito["importancia"]


def test_una_caja_mas_grande_tiene_mas_importancia_que_una_chica():
    chica = _cuadro(FONDO, (2, 2, 4, 4))     # área 4
    grande = _cuadro(FONDO, (2, 2, 7, 7))    # área 25

    m_chica = zonas._momentos_en_cuadros(
        [(0.0, FONDO), (0.5, chica), (1.0, chica)], ANCHO, ALTO, escala_x=1.0, escala_y=1.0,
        umbral=30, area_min_frac=0.02, area_max_frac=0.5)[0]
    m_grande = zonas._momentos_en_cuadros(
        [(0.0, FONDO), (0.5, grande), (1.0, grande)], ANCHO, ALTO, escala_x=1.0, escala_y=1.0,
        umbral=30, area_min_frac=0.02, area_max_frac=0.5)[0]

    assert m_grande["importancia"] > m_chica["importancia"]


def test_sin_ningun_cuadro_cambiado_no_hay_momentos():
    cuadros = [(0.0, FONDO), (0.5, FONDO), (1.0, FONDO)]

    assert zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala_x=1.0, escala_y=1.0,
                                       umbral=30, area_min_frac=0.02, area_max_frac=0.5) == []


def test_un_parpadeo_que_vuelve_a_aparecer_justo_en_el_ultimo_cuadro_sigue_siendo_ruido():
    # el mismo parpadeo (cursor) que ya se confirmó como ruido una vez (aparece y vuelve
    # a FONDO) puede, por casualidad de muestreo, volver a aparecer justo en el ÚLTIMO
    # cuadro de la secuencia -donde no hay cuadro siguiente para confirmar que "vuelve"-.
    # no por eso se convierte en un momento de verdad.
    parpadeo = _cuadro(FONDO, (4, 4, 6, 6))  # misma caja que ya parpadeó antes
    cuadros = [(0.0, FONDO), (0.5, parpadeo), (1.0, FONDO), (1.5, parpadeo)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala_x=1.0, escala_y=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    assert momentos == []


def test_con_un_solo_cuadro_no_hay_nada_para_comparar():
    assert zonas._momentos_en_cuadros([(0.0, FONDO)], ANCHO, ALTO, escala_x=1.0, escala_y=1.0,
                                       umbral=30, area_min_frac=0.02, area_max_frac=0.5) == []


# --- componentes conexas (B3: dos cambios separados no se tienen que unir en una caja) --

def test_componentes_agrupa_pixeles_cercanos_y_separa_los_lejanos():
    # (1,1)-(1,2)-(2,1) quedan pegados (distancia 1); (8,8) está lejos de todos.
    cambiados = {(1, 1), (1, 2), (2, 1), (8, 8)}

    grupos = zonas._componentes(cambiados, dilatacion=1)

    tamanios = sorted(len(g) for g in grupos)
    assert tamanios == [1, 3]


def test_componentes_con_dilatacion_0_no_une_nada_salvo_contacto_directo():
    # con dilatacion=0 sólo se unen píxeles exactamente contiguos (distancia 1 en algún eje)
    cambiados = {(1, 1), (1, 2), (3, 3)}

    grupos = zonas._componentes(cambiados, dilatacion=0)

    tamanios = sorted(len(g) for g in grupos)
    assert tamanios == [1, 2]


# --- B3: dos cambios simultáneos y separados tienen que dar DOS momentos, no uno -------

ANCHO_G = 20
ALTO_G = 20
FONDO_G = bytes([50]) * (ANCHO_G * ALTO_G)


def _cuadro_g(caja: tuple[int, int, int, int] | None, valor: int = 220) -> bytes:
    datos = bytearray(FONDO_G)
    if caja:
        x0, y0, x1, y1 = caja
        for y in range(y0, y1):
            for x in range(x0, x1):
                datos[y * ANCHO_G + x] = valor
    return bytes(datos)


# --- B1: el scroll es un DESPLAZAMIENTO del contenido, no "cambia casi todo" --------

ANCHO_S = 20
ALTO_S = 20
COL_S = (2, 0, 6, 20)  # columna de "texto" que ocupa todo el alto, mitad del ancho


def _fila_valor(y: int) -> int:
    return 60 + (y % 5) * 40  # 60, 100, 140, 180, 220 (cíclico)


def _cuadro_texto(desplazamiento: int = 0) -> bytes:
    datos = bytearray([50]) * (ANCHO_S * ALTO_S)
    x0, y0, x1, y1 = COL_S
    for y in range(y0, y1):
        valor = _fila_valor(y + desplazamiento)
        for x in range(x0, x1):
            datos[y * ANCHO_S + x] = valor
    return bytes(datos)


def test_desplazamiento_detecta_el_scroll_de_una_columna_de_texto():
    base = _cuadro_texto(0)
    scrolleado = _cuadro_texto(1)  # cada fila "sube" una posición (contenido que entra)

    dy = zonas._desplazamiento(base, scrolleado, ANCHO_S, COL_S, umbral=30, dy_max=5,
                                residual_max_frac=0.1)

    assert dy == 1


def test_desplazamiento_triangula_con_otra_magnitud():
    base = _cuadro_texto(0)
    scrolleado = _cuadro_texto(2)

    dy = zonas._desplazamiento(base, scrolleado, ANCHO_S, COL_S, umbral=30, dy_max=5,
                                residual_max_frac=0.1)

    assert dy == 2


def test_desplazamiento_da_none_si_el_cambio_no_es_un_corrimiento():
    base = _cuadro_texto(0)
    # un cambio que no es un corrimiento de verdad: todas las filas al mismo valor fijo.
    x0, y0, x1, y1 = COL_S
    datos = bytearray(base)
    for y in range(y0, y1):
        for x in range(x0, x1):
            datos[y * ANCHO_S + x] = 10
    distinto = bytes(datos)

    dy = zonas._desplazamiento(base, distinto, ANCHO_S, COL_S, umbral=30, dy_max=5,
                                residual_max_frac=0.1)

    assert dy is None


def test_el_scroll_de_una_columna_de_texto_no_es_un_momento():
    # mismo patrón que el repro de QA (B1): una columna angosta de texto que scrollea
    # da una caja de ~0.2 del área total (por debajo de area_max_frac=0.35), así que
    # antes de detectar el desplazamiento el filtro de "área grande" no lo agarraba.
    cuadros = [(0.0, _cuadro_texto(0)), (0.5, _cuadro_texto(1)), (1.0, _cuadro_texto(2)),
               (1.5, _cuadro_texto(3))]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO_S, ALTO_S, escala_x=1.0, escala_y=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.35)

    assert momentos == []


def _filas(valores: dict[int, int]) -> bytes:
    """FONDO con la fila `y` pintada a `valor` (columnas 2-8) para cada (y, valor)."""
    datos = bytearray(FONDO)
    for y, valor in valores.items():
        for x in range(2, 8):
            datos[y * ANCHO + x] = valor
    return bytes(datos)


def test_una_componente_de_dos_filas_no_se_confunde_con_un_scroll_por_casualidad():
    # un componente de sólo 2 filas tiene tan poca información que un corrimiento de 1
    # fila puede "calzar" con una sola fila de superposición, por pura casualidad (la
    # fila 6 de albase, 150, es igual a la fila 5 del cuadro nuevo): eso no alcanza para
    # llamarlo scroll (un scroll real ocupa muchas filas, no 2).
    base = _filas({5: 90, 6: 150})
    nuevo = _filas({5: 150, 6: 200})
    cuadros = [(0.0, base), (0.5, nuevo), (1.0, nuevo)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO, ALTO, escala_x=1.0, escala_y=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    assert len(momentos) == 1, f"un cambio chico sostenido tiene que ser un momento: {momentos}"


def test_dos_cambios_separados_dan_dos_momentos_con_sus_propias_cajas():
    # un aviso arriba a la derecha + una salida abajo a la izquierda, a la vez: antes se
    # unían en una sola caja que ni de cerca pasaba el filtro de área; ahora cada uno es
    # su propio componente.
    datos = bytearray(FONDO_G)
    for y in range(1, 4):
        for x in range(1, 4):
            datos[y * ANCHO_G + x] = 220
    for y in range(15, 18):
        for x in range(15, 18):
            datos[y * ANCHO_G + x] = 220
    con_dos_cajas = bytes(datos)
    cuadros = [(0.0, FONDO_G), (0.5, con_dos_cajas), (1.0, con_dos_cajas)]

    momentos = zonas._momentos_en_cuadros(cuadros, ANCHO_G, ALTO_G, escala_x=1.0, escala_y=1.0,
                                           umbral=30, area_min_frac=0.02, area_max_frac=0.5)

    cajas = sorted((m["x"], m["y"], m["w"], m["h"]) for m in momentos)
    assert cajas == [(1, 1, 3, 3), (15, 15, 3, 3)]
