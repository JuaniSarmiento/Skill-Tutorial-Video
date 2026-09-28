"""Escapado de rutas de fuente para el filtro drawtext de ffmpeg.

En el filtro drawtext, ':' separa opciones (fontfile=RUTA:text=...). Una
ruta de Windows tipo C:/Windows/Fonts/arialbd.ttf choca con eso. El fix es
envolver la ruta entre comillas simples con el ':' escapado:
'C\\:/Windows/Fonts/arialbd.ttf'. En Linux la ruta no tiene ':' y no hace
falta tocarla.
"""
import editar


def test_en_linux_la_ruta_no_se_toca():
    ruta = editar._ruta_fuente(
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", es_windows=False,
    )
    assert ruta == "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"


def test_en_windows_se_escapa_el_dos_puntos_y_se_envuelve_en_comillas():
    ruta = editar._ruta_fuente("C:/Windows/Fonts/arialbd.ttf", es_windows=True)
    assert ruta == r"'C\:/Windows/Fonts/arialbd.ttf'"
