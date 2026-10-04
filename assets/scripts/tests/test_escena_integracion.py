"""El motor de escenas contra un Chrome de verdad.

Renders cortos (1 s, 12 fps, 960 de ancho) para no pasar de ~1 GB de RAM. Lo que
se verifica es lo que un test puro no puede: que la página cumpla el contrato,
que el mp4 dure lo que tiene que durar y que los cuadros cambien con t.
"""
import json
import re
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


@pytest.mark.parametrize("tipo", ["webgl", "webgl2", "experimental-webgl"])
def test_una_plantilla_que_llama_a_webgl_falla_con_contrato_error(tmp_path, tipo):
    # R-4.5 (HITO2.md S4): Canvas 2D / SVG, nunca WebGL (PLAN.md, GPU integrada de Juani)
    html = tmp_path / "webgl.html"
    html.write_text(f"""<script>
      window.DURATION = 1;
      window.seek = async t => {{ document.createElement('canvas').getContext({tipo!r}); }};
    </script>""")

    with pytest.raises(escena.ContratoError, match="webgl"):
        escena.render(html, {}, tmp_path / "out.mp4", fps=12, ancho=960)


@pytest.mark.parametrize("tipo", ["webgl", "webgl2", "experimental-webgl"])
def test_una_plantilla_que_llama_a_webgl_por_offscreencanvas_tambien_falla(tmp_path, tipo):
    # B6 (QA 03/10/2026): la guardia sólo cubría HTMLCanvasElement; OffscreenCanvas
    # la saltea y sigue pudiendo pedir WebGL.
    html = tmp_path / "webgl-offscreen.html"
    html.write_text(f"""<script>
      window.DURATION = 1;
      window.seek = async t => {{ new OffscreenCanvas(100, 100).getContext({tipo!r}); }};
    </script>""")

    with pytest.raises(escena.ContratoError, match="webgl"):
        escena.render(html, {}, tmp_path / "out.mp4", fps=12, ancho=960)


def test_una_plantilla_que_usa_canvas_2d_no_se_ve_afectada_por_la_guardia_de_webgl(tmp_path):
    html = tmp_path / "canvas2d.html"
    html.write_text("""<script>
      window.DURATION = 1;
      window.seek = async t => { document.createElement('canvas').getContext('2d'); };
    </script>""")

    d = escena.render(html, {}, tmp_path / "out.mp4", fps=12, ancho=960)

    assert d == pytest.approx(1.0)


RED = """<!doctype html><script>
window.DURATION = 1;
window.seek = async t => {
  try { await fetch('http://127.0.0.1:1/nope'); } catch (e) { /* una plantilla rota podría
    tragarse el error de red: la defensa tiene que saltar igual, no depender de esto */ }
};
</script>"""


def test_un_intento_de_red_durante_el_seek_falla_con_contrato_error(tmp_path):
    # B1, defensa en profundidad: aunque el JS se trague el error de fetch, el motor
    # tiene que fallar (page.route bloquea todo lo que no sea file://).
    html = tmp_path / "red.html"
    html.write_text(RED)

    with pytest.raises(escena.ContratoError, match="red"):
        escena.render(html, {"duracion": 1.0}, tmp_path / "out.mp4", fps=12, ancho=960)


RED_AL_CARGAR = """<!doctype html><script>
fetch('http://127.0.0.1:1/nope').catch(() => {});
window.DURATION = 1;
window.seek = async t => {};
</script>"""


def test_un_intento_de_red_al_cargar_la_pagina_tambien_falla(tmp_path):
    html = tmp_path / "red2.html"
    html.write_text(RED_AL_CARGAR)

    with pytest.raises(escena.ContratoError, match="red"):
        escena.render(html, {"duracion": 1.0}, tmp_path / "out.mp4", fps=12, ancho=960)


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


def test_un_error_de_js_a_mitad_del_render_falla_claro_y_no_deja_un_mp4_truncado(tmp_path):
    # antes quedaba un out.mp4 de 0,53 s que se reproducía bien: parecía un render válido
    html = tmp_path / "rota-a-mitad.html"
    html.write_text(VALIDA.replace("window.seek = async t => {",
                                   "window.seek = async t => { if (t > 0.5) throw new Error('se rompió a mitad');"))
    mp4 = tmp_path / "out.mp4"

    with pytest.raises(escena.ContratoError) as e:
        escena.render(html, {"duracion": 1.0}, mp4, fps=12, ancho=960)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["rota-a-mitad.html"]
    assert re.search(r"seek\(0\.5\d*\).*se rompió a mitad", str(e.value)), str(e.value)


SIMPLE = {"titulo": {"texto": "Interés compuesto"}, "duracion": 1.0}


def test_si_la_fuente_del_brand_no_esta_instalada_avisa_nombrandola(capsys):
    # sin esto Chrome usa otra fuente en silencio y nadie se entera hasta ver el video
    brand = {**escena.cargar_brand(None), "fuente": "Fuente Que No Existe"}
    with escena.navegador() as b, escena.pagina_de_escena(b, escena.ruta_plantilla("presentacion"), SIMPLE, brand):
        pass
    err = capsys.readouterr().err
    assert "AVISO" in err and "Fuente Que No Existe" in err


def test_con_la_fuente_instalada_no_avisa(capsys):
    with escena.navegador() as b, escena.pagina_de_escena(b, escena.ruta_plantilla("presentacion"), SIMPLE,
                                                          escena.cargar_brand(None)):
        pass
    assert "AVISO" not in capsys.readouterr().err


# --- CLI de punta a punta ------------------------------------------------------

def test_el_cli_render_arma_el_mp4_con_el_fps_el_ancho_y_la_duracion_pedidos(tmp_path, capsys):
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"tipo": "datos", "barras": [{"etiqueta": "A", "valor": 1, "cue": 0.1}], "duracion": 3}))
    mp4 = tmp_path / "o.mp4"

    escena._cli(["render", "datos", str(spec), "-o", str(mp4), "--fps", "12", "--ancho", "960", "--duracion", "1"])

    assert f"{mp4}: 1.00 s" in capsys.readouterr().out
    ancho, cuadros = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-count_packets",
                                     "-show_entries", "stream=width,nb_read_packets", "-of", "csv=p=0", str(mp4)],
                                    capture_output=True, text=True, check=True).stdout.strip().split(",")
    assert (ancho, cuadros) == ("960", "12")


def test_el_cli_render_imagen_da_un_mp4_con_la_duracion_del_spec(tmp_path, capsys):
    # R-4.1 (HITO2.md S4). Falla hoy: ValueError: no hay plantilla de escena 'imagen'.
    svg = tmp_path / "dibujo.svg"
    svg.write_text('<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" stroke="currentColor" fill="none"/></svg>')
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"tipo": "imagen",
                                "dibujos": [{"id": "a", "svg": str(svg), "cue": 0.1}],
                                "duracion": 1}))
    mp4 = tmp_path / "o.mp4"

    escena._cli(["render", "imagen", str(spec), "-o", str(mp4), "--fps", "12", "--ancho", "960"])

    assert f"{mp4}: 1.00 s" in capsys.readouterr().out
    cuadros = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-count_packets",
                              "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(mp4)],
                             capture_output=True, text=True, check=True).stdout.strip()
    assert cuadros == "12"


def test_el_cli_contacto_arma_la_hoja_con_los_specs_que_deja_editar(tmp_path):
    specs = []
    for i, tipo in enumerate(["presentacion", "datos"]):
        p = tmp_path / f"{i:02d}.json"
        p.write_text(json.dumps({"tipo": tipo, "titulo": {"texto": "Hola"}, "duracion": 1.0}))
        specs.append(str(p))
    hoja = tmp_path / "hoja.png"

    escena._cli(["contacto", *specs, "-o", str(hoja), "--columnas", "3"])

    alto = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=height", "-of", "csv=p=0", str(hoja)],
                          capture_output=True, text=True, check=True).stdout
    assert int(alto) > 2 * 360, "dos escenas = dos filas"


def test_el_cli_contacto_acepta_specs_imagen(tmp_path):
    # R-4.8 (HITO2.md S4)
    svg = tmp_path / "dibujo.svg"
    svg.write_text('<svg viewBox="0 0 10 10"><path d="M1 1L9 9" stroke="currentColor" fill="none"/></svg>')
    spec = tmp_path / "00.json"
    spec.write_text(json.dumps({"tipo": "imagen",
                                "dibujos": [{"id": "a", "svg": str(svg), "cue": 0.1}],
                                "duracion": 1.0}))
    hoja = tmp_path / "hoja.png"

    escena._cli(["contacto", str(spec), "-o", str(hoja), "--columnas", "3"])

    alto = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=height", "-of", "csv=p=0", str(hoja)],
                          capture_output=True, text=True, check=True).stdout.strip()
    assert int(alto) > 0


def test_el_cli_render_imagen_con_svg_relativo_funciona_desde_otro_cwd(tmp_path, monkeypatch):
    # B3 (QA 03/10/2026): el "svg" se resuelve contra el directorio del spec.json, no
    # contra el cwd de quien corre escena.py.
    serie = tmp_path / "serie"
    serie.mkdir()
    (serie / "dibujo.svg").write_text(
        '<svg viewBox="0 0 10 10"><path d="M1 1L9 9" stroke="currentColor" fill="none"/></svg>')
    spec = serie / "s.json"
    spec.write_text(json.dumps({"tipo": "imagen", "dibujos": [{"id": "a", "svg": "dibujo.svg", "cue": 0.1}],
                                "duracion": 1}))
    mp4 = tmp_path / "o.mp4"
    otro_cwd = tmp_path / "otro"
    otro_cwd.mkdir()
    monkeypatch.chdir(otro_cwd)

    escena._cli(["render", "imagen", str(spec), "-o", str(mp4), "--fps", "12", "--ancho", "960"])

    assert mp4.exists()


def test_el_cli_contacto_con_svg_relativo_funciona_desde_otro_cwd(tmp_path, monkeypatch):
    serie = tmp_path / "serie"
    serie.mkdir()
    (serie / "dibujo.svg").write_text(
        '<svg viewBox="0 0 10 10"><path d="M1 1L9 9" stroke="currentColor" fill="none"/></svg>')
    spec = serie / "00.json"
    spec.write_text(json.dumps({"tipo": "imagen", "dibujos": [{"id": "a", "svg": "dibujo.svg", "cue": 0.1}],
                                "duracion": 1.0}))
    hoja = tmp_path / "hoja.png"
    otro_cwd = tmp_path / "otro"
    otro_cwd.mkdir()
    monkeypatch.chdir(otro_cwd)

    escena._cli(["contacto", str(spec), "-o", str(hoja), "--columnas", "3"])

    assert hoja.exists()


def test_el_cli_contacto_con_svg_faltante_falla_antes_de_abrir_chrome(tmp_path):
    # R-4.6 por el camino de contacto, no sólo por render
    spec = tmp_path / "00.json"
    spec.write_text(json.dumps({"tipo": "imagen",
                                "dibujos": [{"id": "a", "svg": str(tmp_path / "no-existe.svg"), "cue": 0.1}],
                                "duracion": 1.0}))

    with pytest.raises(ValueError, match="no-existe.svg"):
        escena._cli(["contacto", str(spec), "-o", str(tmp_path / "hoja.png")])
