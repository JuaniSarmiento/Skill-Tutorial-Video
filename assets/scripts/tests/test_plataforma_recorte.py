"""Cálculo puro del recorte al monitor primario para gdigrab (Windows).

El monitor primario siempre está en (0,0) en las coordenadas de Windows,
pero el escritorio virtual (todos los monitores juntos) puede arrancar en
un origen negativo si hay un monitor secundario a la izquierda o arriba
(SM_XVIRTUALSCREEN/SM_YVIRTUALSCREEN). Esta función no llama a la API de
Windows: recibe las métricas ya leídas y devuelve el offset y tamaño para
pasarle a gdigrab. Así se puede probar en Linux sin ctypes.windll.
"""
import plataforma


def test_un_solo_monitor_offset_es_cero():
    offset_x, offset_y, tamano = plataforma._recorte_monitor_primario(
        ancho_primario=1920, alto_primario=1080, virt_x=0, virt_y=0,
    )
    assert (offset_x, offset_y, tamano) == (0, 0, "1920x1080")


def test_monitor_secundario_a_la_izquierda_desplaza_el_offset():
    # El escritorio virtual arranca en x=-1920 porque hay un segundo monitor
    # de 1920px a la izquierda del primario. El primario sigue en x=0 real,
    # o sea 1920px adentro del lienzo que gdigrab captura.
    offset_x, offset_y, tamano = plataforma._recorte_monitor_primario(
        ancho_primario=1920, alto_primario=1080, virt_x=-1920, virt_y=0,
    )
    assert (offset_x, offset_y, tamano) == (1920, 0, "1920x1080")
