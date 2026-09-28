"""Normalización de coordenadas para click(x, y) en Windows.

SendInput con MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK espera las
coordenadas normalizadas de 0 a 65535 sobre el escritorio virtual completo
(todos los monitores), no sobre un solo monitor. Esta función es la cuenta
pura: recibe el punto en píxeles y el rectángulo del escritorio virtual
(que puede arrancar en un origen negativo) y devuelve el par normalizado.
"""
import plataforma


def test_esquina_superior_izquierda_de_un_solo_monitor():
    nx, ny = plataforma._normalizar_click_virtual(
        x=0, y=0, virt_x=0, virt_y=0, virt_w=1920, virt_h=1080,
    )
    assert (nx, ny) == (0, 0)


def test_esquina_inferior_derecha_de_un_solo_monitor():
    nx, ny = plataforma._normalizar_click_virtual(
        x=1919, y=1079, virt_x=0, virt_y=0, virt_w=1920, virt_h=1080,
    )
    assert (nx, ny) == (65535, 65535)


def test_click_en_monitor_primario_con_secundario_a_la_izquierda():
    # Escritorio virtual de 3840x1080: un monitor de 1920 a la izquierda
    # (arranca en x=-1920) y el primario a la derecha (arranca en x=0).
    # Clickear (0,0) —el origen del primario— NO es (0,0) en el escritorio
    # virtual completo.
    nx, ny = plataforma._normalizar_click_virtual(
        x=0, y=0, virt_x=-1920, virt_y=0, virt_w=3840, virt_h=1080,
    )
    assert (nx, ny) == (32776, 0)
