"""Construcción del comando de Chrome grabable: perfil persistente, --app (sin
pestañas/barra/favoritos), ventana 1920x1080 en 0,0, --force-device-scale-factor
(default 1.5, para que el texto mida >=24px en el cuadro, CLAUDE.md §4.2/§4.6) y
--remote-debugging-port para que Playwright se conecte con connect_over_cdp.

Capa pura: devuelve el argv, no ejecuta nada (ver _lanzar_chrome / Toma para el
lanzamiento real, cubierto por integración).
"""
import grabar_web


def test_usa_perfil_persistente_del_perfil_pedido():
    argv = grabar_web._cmd_chrome("docente-n4", "https://tutor.example/x", puerto=9333)

    esperado = str(grabar_web.PERFILES_DIR / "docente-n4")
    assert any(a == f"--user-data-dir={esperado}" for a in argv)


def test_abre_en_modo_app_sin_pestanas_ni_barra():
    argv = grabar_web._cmd_chrome("p", "https://tutor.example/x", puerto=9333)

    assert "--app=https://tutor.example/x" in argv


def test_ventana_1920x1080_en_el_origen():
    argv = grabar_web._cmd_chrome("p", "https://tutor.example/x", puerto=9333)

    assert "--window-position=0,0" in argv
    assert "--window-size=1920,1080" in argv


def test_escala_default_es_1_5():
    argv = grabar_web._cmd_chrome("p", "https://tutor.example/x", puerto=9333)

    assert "--force-device-scale-factor=1.5" in argv


def test_escala_configurable():
    argv = grabar_web._cmd_chrome("p", "https://tutor.example/x", puerto=9333, escala=2)

    assert "--force-device-scale-factor=2" in argv


def test_puerto_de_remote_debugging_configurable():
    argv = grabar_web._cmd_chrome("p", "https://tutor.example/x", puerto=9444)

    assert "--remote-debugging-port=9444" in argv


def test_arranca_en_kiosk_para_que_no_se_vea_la_barra_de_titulo_del_wm():
    """openbox (entorno.sh) dibuja una barra de título sobre cualquier ventana
    normal. --kiosk saca esa decoración (verificado a mano contra una
    grabación real, ver references/grabacion.md): --start-fullscreen también
    la saca, pero de paso muestra 3-4s el cartel "Para salir de pantalla
    completa, mantén Esc" ENCIMA de la página — kiosk no lo muestra."""
    argv = grabar_web._cmd_chrome("p", "https://tutor.example/x", puerto=9333)

    assert "--kiosk" in argv


def test_esconde_la_scrollbar():
    argv = grabar_web._cmd_chrome("p", "https://tutor.example/x", puerto=9333)

    assert "--hide-scrollbars" in argv
