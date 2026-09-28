"""El struct INPUT de SendInput necesita mi/hi en la unión, no sólo ki.

Sin mi (MOUSEINPUT) y hi (HARDWAREINPUT) en la unión, ctypes.sizeof(INPUT)
da un tamaño más chico que el que espera user32.SendInput, y la llamada
falla con ERROR_INVALID_PARAMETER (87) sin tirar una excepción de Python:
el bug silencioso que describe el informe.

Las definiciones de los structs son ctypes puro (wintypes no necesita
Windows para importarse), así que esto se puede probar en Linux sin
ctypes.windll. Lo que NO se prueba acá es que SendInput funcione de verdad
—eso requiere Windows real— sino que el layout de memoria es el correcto.
"""
import ctypes

import plataforma


def test_input_con_mi_y_hi_mide_40_bytes_en_64_bits():
    # En Windows x64, el INPUT real (type DWORD + unión de 32 bytes con
    # padding) mide 40 bytes. Sin mi/hi, la unión sólo tiene ki (24 bytes)
    # y el struct entero da 32 — el tamaño que reportaba el bug.
    assert ctypes.sizeof(plataforma._IN) == 40


def test_la_union_puede_llevar_un_evento_de_mouse():
    ev = plataforma._IN(type=0)
    ev.mi.dx = 12345
    ev.mi.dy = 6789
    assert (ev.mi.dx, ev.mi.dy) == (12345, 6789)


def test_la_union_puede_llevar_un_evento_de_hardware():
    ev = plataforma._IN(type=0)
    ev.hi.uMsg = 42
    assert ev.hi.uMsg == 42
