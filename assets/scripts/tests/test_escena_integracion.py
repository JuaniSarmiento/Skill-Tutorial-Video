"""El motor de escenas contra un Chrome de verdad.

Renders cortos (1 s, 12 fps, 960 de ancho) para no pasar de ~1 GB de RAM. Lo que
se verifica es lo que un test puro no puede: que la página cumpla el contrato,
que el mp4 dure lo que tiene que durar y que los cuadros cambien con t.
"""
import json
import subprocess

import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402

pytestmark = pytest.mark.integracion

# Una caja que cruza la pantalla: x es función pura de t.
VALIDA = """<!doctype html><body style="margin:0;background:#111">
<div id=c style="position:absolute;top:400px;width:200px;height:200px;background:#f2b544"></div>
<script>
window.DURATION = window.SPEC.duracion;
window.seek = async t => { c.style.left = (t / DURATION * 1600) + 'px'; };
</script>"""


def _ffprobe_duracion(mp4):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(mp4)], capture_output=True, text=True, check=True)
    return float(out.stdout)


def _hashes_de_cuadros(mp4):
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-f", "framemd5", "-"],
                         capture_output=True, text=True, check=True).stdout
    return [ln.split(",")[-1].strip() for ln in out.splitlines() if ln and not ln.startswith("#")]


def test_una_escena_valida_dura_exacto_y_sus_cuadros_cambian(tmp_path):
    html = tmp_path / "valida.html"
    html.write_text(VALIDA)
    mp4 = tmp_path / "out.mp4"

    d = escena.render(html, {"duracion": 1.0}, mp4, fps=12, ancho=960)

    assert d == pytest.approx(1.0)
    assert _ffprobe_duracion(mp4) == pytest.approx(1.0, abs=1 / 12)
    hashes = _hashes_de_cuadros(mp4)
    assert len(hashes) == 12
    assert len(set(hashes)) > 6, "la caja se mueve: casi todos los cuadros tienen que ser distintos"


def test_la_duracion_la_manda_el_spec(tmp_path):
    html = tmp_path / "valida.html"
    html.write_text(VALIDA)
    mp4 = tmp_path / "out.mp4"

    escena.render(html, {"duracion": 2.0}, mp4, fps=12, ancho=960)

    assert len(_hashes_de_cuadros(mp4)) == 24


def test_una_pagina_sin_seek_falla_claro_y_no_deja_video(tmp_path):
    html = tmp_path / "sin-seek.html"
    html.write_text("<script>window.DURATION = 2;</script>")
    mp4 = tmp_path / "out.mp4"

    with pytest.raises(escena.ContratoError, match="window.seek"):
        escena.render(html, {}, mp4, fps=12, ancho=960)
    assert not mp4.exists()


def test_una_pagina_que_tira_un_error_de_js_falla_con_ese_error(tmp_path):
    html = tmp_path / "rota.html"
    html.write_text("<script>window.DURATION = 1; window.seek = async t => {}; noExiste();</script>")

    with pytest.raises(escena.ContratoError, match="noExiste"):
        escena.render(html, {}, tmp_path / "out.mp4", fps=12, ancho=960)


def test_la_hoja_de_contacto_es_un_png_con_tres_cuadros_por_escena(tmp_path):
    html = tmp_path / "valida.html"
    html.write_text(VALIDA)
    hoja = tmp_path / "hoja.png"

    escena.hoja_contacto([("a", html, {"duracion": 1.0}), ("b", html, {"duracion": 2.0})], hoja, columnas=3)

    ancho, alto = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                                  "stream=width,height", "-of", "csv=p=0", str(hoja)],
                                 capture_output=True, text=True, check=True).stdout.strip().split(",")
    assert int(ancho) == 24 * 2 + 3 * 640 + 2 * 16
    assert int(alto) > 2 * 360, "dos escenas = dos filas de tres cuadros"


def test_si_el_script_revienta_antes_del_contrato_se_ve_el_error_de_js_y_no_falta_duration(tmp_path):
    # Sin esto el mensaje sería "falta window.DURATION", que manda a buscar en el lugar equivocado
    html = tmp_path / "rota.html"
    html.write_text("<script>SPEC.nodos.map(n => n);  window.DURATION = 1; window.seek = async t => {};</script>")

    with pytest.raises(escena.ContratoError, match="error de JavaScript al cargar.*map"):
        escena.render(html, {}, tmp_path / "out.mp4", fps=12, ancho=960)
