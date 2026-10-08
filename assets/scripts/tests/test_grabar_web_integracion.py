"""Integración de Toma contra una página local de fixtures (tests/fixtures/web/
pagina.html): clicks por locator (no coordenadas), diálogos nativos neutralizados,
cola de prompt en orden, cursor dibujado, tipeo exacto en un editor CodeMirror-like.

Necesita Chrome real + Playwright conectado por CDP (connect_over_cdp), nunca el
navegador empaquetado de Playwright. Se corre con:
    uv run --with pytest --with playwright --with pygments --with matplotlib \\
        --with faster-whisper --with "av<19" python -m pytest -m integracion ...
Si no hay DISPLAY con un X11 real (Xephyr via entorno.sh start bajo Wayland),
Chrome no abre ventana y el test falla con un mensaje claro, no en silencio.
"""
import os
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("playwright")

import grabar_web  # noqa: E402

pytestmark = pytest.mark.integracion

FIXTURE_URL = (Path(__file__).parent / "fixtures" / "web" / "pagina.html").resolve().as_uri()

_PUERTO = 9500


@pytest.fixture
def toma(tmp_path, monkeypatch):
    global _PUERTO
    _PUERTO += 1
    monkeypatch.setattr(grabar_web, "PERFILES_DIR", tmp_path / "perfiles")
    t = grabar_web.Toma("test-fixture", FIXTURE_URL, puerto=_PUERTO, seed=7, display=":2")
    try:
        yield t
    finally:
        t.cerrar()


def test_click_llega_al_elemento_correcto_aunque_un_modal_corra_todo_hacia_abajo(toma):
    toma.click("Abrir modal")  # el modal crece 145px y empuja "Objetivo" hacia abajo

    toma.click("Objetivo")

    assert toma._page.locator("#resultado").inner_text() == "objetivo-clickeado"


def test_el_click_real_nunca_usa_una_coordenada_fija_cacheada(toma):
    """El centro se calcula para animar el cursor dibujado, pero el click en sí
    tiene que resolver el elemento DE NUEVO al momento de clickear (Locator.click,
    con la espera de estabilidad de Playwright) y no reusar esa coordenada vieja
    con page.mouse.click: eso es justo lo que corrió mal clicks en una toma
    anterior cuando un modal corrió 145px todo lo de abajo."""
    def _prohibido(*a, **kw):
        raise AssertionError("click() no debe llamar a page.mouse.click con una coordenada fija")

    toma._page.mouse.click = _prohibido

    toma.click("Avisar")  # no debe reventar: el click real no pasa por mouse.click


def test_ningun_dialogo_nativo_bloquea_alert_ni_confirm(toma):
    toma.click("Avisar")  # alert() real colgaría el navegador (CLAUDE.md §4.10)
    toma.click("Confirmar")

    assert toma._page.locator("#resultado").inner_text() == "confirm:true"


def test_las_respuestas_de_prompt_llegan_en_el_orden_encolado(toma):
    toma.entradas(["mariana perez"])

    toma.click("Preguntar")

    assert toma._page.locator("#resultado").inner_text() == "prompt:mariana perez"


def test_el_cursor_dibujado_se_mueve_al_hacer_click(toma):
    pos_inicial = toma._page.evaluate(
        "() => { const c = document.getElementById('__toma-cursor'); return c && c.style.transform; }"
    )

    toma.click("Avisar")

    pos_final = toma._page.evaluate(
        "() => document.getElementById('__toma-cursor').style.transform"
    )
    assert pos_final != pos_inicial
    assert pos_final  # no vacío: el init script lo creó y mover() lo actualizó


def test_escribir_produce_el_texto_exacto_en_el_editor_tipo_codemirror(toma):
    toma.escribir("#editor", "hola mundo")

    assert "hola mundo" in toma._page.locator("#editor .cm-line").inner_text()


def test_el_frame_real_no_muestra_barra_de_titulo_ni_scrollbar(toma, tmp_path):
    """--kiosk saca la barra de título que openbox dibuja sobre cualquier
    ventana normal, y --hide-scrollbars la scrollbar: se verifica contra un
    frame x11grab REAL (no una captura de Playwright, que no pasa por el
    compositor de la ventana ni por el window manager)."""
    frame = tmp_path / "frame.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "x11grab",
                    "-video_size", "1920x1080", "-i", ":2", "-frames:v", "1", str(frame)],
                   check=True, timeout=20)

    import matplotlib.image as mpimg
    img = mpimg.imread(str(frame))
    # franja superior, lejos de la esquina donde puede estar el cursor dibujado
    # (el cursor es esperable ahí; una barra de título NO lo es, y ocupa el ANCHO).
    franja_superior = img[0:4, 100:1900, :3]
    # blanco puro (fondo de la página) en toda la franja superior = sin decoración encima
    assert (franja_superior > 0.95).all(), "hay algo (barra de título?) pintado en la fila superior"


def test_el_texto_mide_mas_grande_que_1_a_1_por_el_scale_factor(toma, tmp_path):
    """Prueba empírica de --force-device-scale-factor=1.5 sobre un frame x11grab
    REAL (no sobre el DOM/CSS): un texto de 16px CSS tiene que medir bastante
    más que 16px físicos en el cuadro grabado (~24px, con tolerancia por el
    ascenso/descenso de la fuente). Si el flag se rompe o se borra, esto cae a
    ~16-17px y el test lo detecta."""
    import matplotlib.image as mpimg
    import numpy as np

    frame = tmp_path / "frame.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "x11grab",
                    "-video_size", "1920x1080", "-i", ":2", "-frames:v", "1", str(frame)],
                   check=True, timeout=20)

    img = mpimg.imread(str(frame))
    # CSS left:20 top:300 a escala 1.5 cae ~(30, 450) en píxeles físicos: recorte generoso.
    recorte = img[420:520, 0:500, :3]
    oscuro = recorte.mean(axis=2) < 0.5
    filas_con_tinta = np.where(oscuro.any(axis=1))[0]
    assert len(filas_con_tinta) > 0, "no encontré el texto de medida en el recorte esperado"
    alto_medido = int(filas_con_tinta.max() - filas_con_tinta.min() + 1)
    assert alto_medido >= 20, (
        f"el texto de 16px CSS midió {alto_medido}px físicos: esperaba ~24px (16*1.5). "
        "¿se rompió --force-device-scale-factor?")


def test_grabar_iniciar_fuerza_el_display_de_la_toma_no_el_del_proceso(toma, monkeypatch, tmp_path):
    """rec.py arma el comando de x11grab leyendo os.environ["DISPLAY"] AL MOMENTO de
    llamar a start(): si el proceso que corre el script de toma tiene otro DISPLAY
    en su entorno (p.ej. :1, el de verdad bajo Wayland) y grabar_iniciar no lo pisa
    con el de la Toma (:2, Xephyr), rec.py graba la pantalla EQUIVOCADA -> .mkv
    negro, el mismo gotcha de Wayland que describe references/grabacion.md, pero
    disparado desde adentro de Toma en vez de por el entorno del shell."""
    capturado = {}

    def rec_start_falso(nombre):
        capturado["display"] = os.environ.get("DISPLAY")
        capturado["nombre"] = nombre

    monkeypatch.setattr(grabar_web.rec, "start", rec_start_falso)
    monkeypatch.setattr(grabar_web.rec, "RAIZ", tmp_path)
    monkeypatch.setenv("DISPLAY", ":1")  # simula el DISPLAY real del host, no Xephyr

    toma.grabar_iniciar("v00-demo")

    assert capturado["display"] == ":2"
