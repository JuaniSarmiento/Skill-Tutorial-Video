"""Partes puras del motor de escenas (escena.py).

Una escena es un HTML con el contrato `window.DURATION` + `async window.seek(t)`:
cada pixel es función de t. El motor abre la página, la lleva a cada t y saca
un PNG por cuadro. Acá se prueba todo lo que no necesita un Chrome.
"""
import json

import pytest

import escena


# --- cuadros -----------------------------------------------------------------

def test_los_cuadros_cubren_la_duracion_exacta_a_ese_fps():
    t = escena.tiempos_de_cuadros(2.0, 30)
    assert len(t) == 60
    assert t[0] == 0.0
    assert t[-1] == pytest.approx(59 / 30)


def test_una_duracion_que_no_cae_en_cuadro_redondea_al_cuadro_mas_cercano():
    assert len(escena.tiempos_de_cuadros(1.01, 30)) == 30   # 30.3 cuadros
    assert len(escena.tiempos_de_cuadros(1.02, 30)) == 31   # 30.6 cuadros


@pytest.mark.parametrize("duracion", [0, -1, 0.001])
def test_una_duracion_sin_cuadros_es_un_error(duracion):
    with pytest.raises(ValueError, match="duraci"):
        escena.tiempos_de_cuadros(duracion, 30)


# --- ffmpeg ------------------------------------------------------------------

def test_el_comando_lee_pngs_de_stdin_al_fps_pedido_y_escribe_la_salida():
    cmd = escena.comando_ffmpeg("out/escena.mp4", fps=24)

    assert cmd[0] == "ffmpeg"
    assert cmd[cmd.index("-f") + 1] == "image2pipe"
    assert cmd[cmd.index("-framerate") + 1] == "24"
    assert cmd[cmd.index("-i") + 1] == "-"
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    assert cmd[-1] == "out/escena.mp4"


def test_el_comando_usa_el_mismo_codec_que_los_segmentos_de_editar():
    # si el codec o el pix_fmt difieren, el concat -c copy de editar.py se rompe
    cmd = escena.comando_ffmpeg("x.mp4", fps=30)
    assert cmd[cmd.index("-c:v", cmd.index("-i")) + 1] == "libx264"
    assert cmd[cmd.index("-r") + 1] == "30"


def test_a_ancho_completo_no_se_escala():
    assert "-vf" not in escena.comando_ffmpeg("x.mp4", fps=30)


def test_una_prueba_chica_la_achica_ffmpeg_y_no_chrome():
    # Chrome con device_scale_factor fraccionario NO rasteriza igual entre cargas
    # (medido: a 960 de ancho, 1 de 4 cargas daba otro PNG). Se captura siempre a
    # 1920x1080 y se escala en el encode.
    cmd = escena.comando_ffmpeg("x.mp4", fps=12, ancho=960)
    assert cmd[cmd.index("-vf") + 1] == "scale=960:-2:flags=lanczos"
    assert cmd.index("-vf") > cmd.index("-i")


# --- contrato ----------------------------------------------------------------

def test_un_contrato_completo_no_levanta():
    escena.verificar_contrato({"duracion": 4.5, "seek": "function"}, "ok.html")


def test_sin_duration_falla_nombrando_la_pagina_y_lo_que_falta():
    with pytest.raises(escena.ContratoError) as e:
        escena.verificar_contrato({"duracion": None, "seek": "function"}, "mala.html")
    assert "mala.html" in str(e.value)
    assert "window.DURATION" in str(e.value)
    assert "seek" not in str(e.value).split("falta:")[1]


def test_sin_seek_falla_nombrando_seek():
    with pytest.raises(escena.ContratoError, match=r"window\.seek"):
        escena.verificar_contrato({"duracion": 3, "seek": "undefined"}, "mala.html")


@pytest.mark.parametrize("duracion", [0, -2, "3", True])
def test_una_duration_que_no_es_un_numero_positivo_falla(duracion):
    with pytest.raises(escena.ContratoError, match="DURATION"):
        escena.verificar_contrato({"duracion": duracion, "seek": "function"}, "x.html")


# --- spec: cues a tiempos ----------------------------------------------------

VOZ = [
    {"palabra": "Primero", "inicio": 0.3, "fin": 0.7},
    {"palabra": "el", "inicio": 0.7, "fin": 0.8},
    {"palabra": "sol", "inicio": 0.8, "fin": 1.2},
    {"palabra": "llega", "inicio": 1.2, "fin": 1.5},
    {"palabra": "a", "inicio": 1.5, "fin": 1.6},
    {"palabra": "la", "inicio": 1.6, "fin": 1.7},
    {"palabra": "hoja.", "inicio": 1.7, "fin": 2.2},
]


def test_cada_cue_del_spec_gana_su_t_en_segundos():
    spec = {"tipo": "diagrama",
            "nodos": [{"id": "s", "texto": "Sol", "cue": "sol"},
                      {"id": "h", "texto": "Hoja", "cue": "la hoja"}],
            "flechas": [{"de": "s", "a": "h", "cue": "llega"}]}

    out = escena.resolver_spec(spec, VOZ)

    assert [n["t"] for n in out["nodos"]] == [0.8, 1.6]
    assert out["flechas"][0]["t"] == 1.2


def test_una_cue_numerica_no_necesita_voz():
    spec = {"puntos": [{"texto": "uno", "cue": 0.5}, {"texto": "dos", "cue": 2}]}
    out = escena.resolver_spec(spec, None)
    assert [p["t"] for p in out["puntos"]] == [0.5, 2.0]


def test_un_elemento_sin_cue_queda_sin_t():
    out = escena.resolver_spec({"titulo": {"texto": "Hola"}}, VOZ)
    assert "t" not in out["titulo"]


def test_una_cue_de_texto_sin_voz_falla_explicando_que_falta():
    with pytest.raises(ValueError, match="palabras"):
        escena.resolver_spec({"puntos": [{"cue": "sol"}]}, None)


def test_un_spec_ya_resuelto_no_necesita_voz_y_conserva_sus_tiempos():
    # es lo que deja `editar.py escenas` para la hoja de contacto: cue de texto + t ya calculado
    spec = {"puntos": [{"cue": "sol", "t": 1.1}, {"cue": "hoja", "t": 2.0}]}
    out = escena.resolver_spec(spec, None)
    assert [p["t"] for p in out["puntos"]] == [1.1, 2.0]


def test_con_voz_un_t_ya_resuelto_tampoco_se_recalcula():
    out = escena.resolver_spec({"puntos": [{"cue": "sol", "t": 9.9}, {"cue": "sol"}]}, VOZ)
    assert [p["t"] for p in out["puntos"]] == [9.9, 0.8]


def test_resolver_no_toca_el_spec_original():
    spec = {"puntos": [{"cue": "sol"}]}
    escena.resolver_spec(spec, VOZ)
    assert spec == {"puntos": [{"cue": "sol"}]}


# --- brand -------------------------------------------------------------------

def test_sin_brand_de_la_serie_se_usa_el_de_la_skill():
    b = escena.cargar_brand(None)
    assert b["fuente"]
    assert b["colores"]["acento"].startswith("#")


def test_el_brand_de_la_serie_pisa_solo_lo_que_declara(tmp_path):
    defecto = escena.cargar_brand(None)
    serie = tmp_path / "brand.json"
    serie.write_text(json.dumps({"colores": {"acento": "#00AA88"}}))

    b = escena.cargar_brand(serie)

    assert b["colores"]["acento"] == "#00AA88"
    assert b["colores"]["fondo"] == defecto["colores"]["fondo"]
    assert b["fuente"] == defecto["fuente"]


# --- hoja de contacto --------------------------------------------------------

def test_los_cuadros_de_contacto_caen_al_10_50_y_90_por_ciento():
    assert escena.tiempos_contacto(10.0) == [1.0, 5.0, 9.0]
    assert escena.tiempos_contacto(4.0, (0.25, 0.75)) == [1.0, 3.0]


def test_la_hoja_de_contacto_muestra_cada_cuadro_con_su_etiqueta():
    html = escena.html_contacto(
        [("/tmp/a.png", "00 diagrama · 1.0 s"), ("/tmp/b.png", "<script>x</script>")], columnas=3)

    assert html.count("<img") == 2
    assert "file:///tmp/a.png" in html
    assert "00 diagrama · 1.0 s" in html
    assert "<script>x</script>" not in html          # las etiquetas se escapan
    assert "repeat(3" in html


# --- plantillas --------------------------------------------------------------

@pytest.mark.parametrize("tipo", ["diagrama", "presentacion", "datos", "imagen"])
def test_cada_tipo_tiene_su_plantilla(tipo):
    p = escena.ruta_plantilla(tipo)
    assert p.name == f"{tipo}.html"
    assert "window.seek" in p.read_text() or "contrato(" in p.read_text()


def test_un_tipo_desconocido_falla_listando_los_que_hay():
    with pytest.raises(ValueError) as e:
        escena.ruta_plantilla("pizarron")
    for tipo in ("diagrama", "presentacion", "datos", "imagen"):
        assert tipo in str(e.value)


# --- CLI: lo que no sirve se rechaza antes de abrir Chrome --------------------

@pytest.fixture
def renders(monkeypatch):
    llamadas = []
    monkeypatch.setattr(escena, "render", lambda plantilla, spec, salida, *a, **k: llamadas.append(spec) or 1.0)
    monkeypatch.setattr(escena, "hoja_contacto", lambda escenas, salida, *a, **k: llamadas.append(escenas) or salida)
    return llamadas


def _spec(tmp_path, nombre="s.json", **spec):
    p = tmp_path / nombre
    p.write_text(json.dumps(spec))
    return str(p)


@pytest.mark.parametrize("args, dice", [
    (["--duracion", "0"], "--duracion"),
    (["--duracion", "-2"], "--duracion"),
    (["--ancho", "961"], "par"),
], ids=["duracion-cero", "duracion-negativa", "ancho-impar"])
def test_el_cli_rechaza_valores_que_no_sirven(tmp_path, renders, capsys, args, dice):
    with pytest.raises(SystemExit) as e:
        escena._cli(["render", "datos", _spec(tmp_path, duracion=2), "-o", str(tmp_path / "o.mp4"), *args])
    assert e.value.code == 2, "argparse: error de uso"
    assert dice in capsys.readouterr().err
    assert renders == []


def test_el_cli_con_una_duracion_valida_la_pasa_al_spec(tmp_path, renders):
    escena._cli(["render", "datos", _spec(tmp_path, duracion=2), "-o", str(tmp_path / "o.mp4"), "--duracion", "3.5"])
    assert renders[0]["duracion"] == 3.5


def test_contacto_con_un_spec_sin_tipo_falla_nombrando_el_archivo(tmp_path, renders, capsys):
    with pytest.raises(SystemExit) as e:
        escena._cli(["contacto", _spec(tmp_path, "sin-tipo.json", duracion=2), "-o", str(tmp_path / "h.png")])
    assert e.value.code == 2, "argparse: error de uso"
    err = capsys.readouterr().err
    assert "sin-tipo.json" in err and "tipo" in err
    assert renders == []
