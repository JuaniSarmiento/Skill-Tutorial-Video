"""editar.py: los libx264 de build_segment (título y pantalla) pasan por encoder.py.

Antes del Hito 2 estaban escritos a mano en editar.py:257 (título), :281 (pantalla, 1ra
pasada) y :292 (pantalla, 2da pasada).
"""
import subprocess

import pytest

import editar
import encoder


@pytest.fixture(autouse=True)
def _sin_cache(monkeypatch):
    monkeypatch.delenv("TUT_ENCODER", raising=False)
    monkeypatch.delenv("TUT_VAAPI_DEVICE", raising=False)
    encoder.reset()
    yield
    encoder.reset()


def _spy_run(monkeypatch):
    """Deja pasar la llamada real (el archivo tiene que existir después) y la registra."""
    llamadas = []
    real = editar.run

    def _r(cmd):
        llamadas.append(cmd)
        return real(cmd)

    monkeypatch.setattr(editar, "run", _r)
    return llamadas


def _raw(tmp_path):
    raw = tmp_path / "raw.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=320x180:r=30:d=1",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(raw)], check=True)
    return raw


# --- título --------------------------------------------------------------------

def test_titulo_sin_tut_encoder_sigue_usando_libx264(tmp_path, monkeypatch):
    llamadas = _spy_run(monkeypatch)
    out = tmp_path / "t.mp4"

    editar.build_segment("v01", None, {"tipo": "titulo", "titulo": "Hola"}, 0.5, out)

    cmd = llamadas[-1]
    assert cmd[cmd.index("-c:v") + 1] == "libx264"


def test_titulo_con_vaapi_disponible_usa_h264_vaapi(tmp_path, monkeypatch):
    monkeypatch.setenv("TUT_ENCODER", "vaapi")
    monkeypatch.setattr(encoder, "_probar_vaapi", lambda device: (True, ""))
    llamadas = _spy_run(monkeypatch)
    out = tmp_path / "t.mp4"

    editar.build_segment("v01", None, {"tipo": "titulo", "titulo": "Hola"}, 0.5, out)

    cmd = llamadas[-1]
    assert cmd[cmd.index("-c:v") + 1] == "h264_vaapi"
    assert "format=nv12,hwupload" in cmd[cmd.index("-vf") + 1]


# --- pantalla (crudo) ------------------------------------------------------------

def test_pantalla_sin_tut_encoder_sigue_usando_libx264_en_las_dos_pasadas(tmp_path, monkeypatch):
    raw = _raw(tmp_path)
    llamadas = _spy_run(monkeypatch)
    out = tmp_path / "seg.mp4"

    editar.build_segment("v01", raw, {"inicio": 0, "fin": 1, "decimar": False}, 1.0, out)

    ffmpeg = [c for c in llamadas if c[0] == "ffmpeg"]
    assert len(ffmpeg) == 2
    for cmd in ffmpeg:
        assert cmd[cmd.index("-c:v") + 1] == "libx264"
    # 1ra pasada (tmp): sin -pix_fmt, igual que antes del Hito 2
    assert "-pix_fmt" not in ffmpeg[0]
    assert "-pix_fmt" in ffmpeg[1]


def test_pantalla_con_vaapi_disponible_usa_h264_vaapi_en_las_dos_pasadas(tmp_path, monkeypatch):
    raw = _raw(tmp_path)
    monkeypatch.setenv("TUT_ENCODER", "vaapi")
    monkeypatch.setattr(encoder, "_probar_vaapi", lambda device: (True, ""))
    llamadas = _spy_run(monkeypatch)
    out = tmp_path / "seg.mp4"

    editar.build_segment("v01", raw, {"inicio": 0, "fin": 1, "decimar": False}, 1.0, out)

    ffmpeg = [c for c in llamadas if c[0] == "ffmpeg"]
    assert len(ffmpeg) == 2
    for cmd in ffmpeg:
        assert cmd[cmd.index("-c:v") + 1] == "h264_vaapi"
        assert "format=nv12,hwupload" in cmd[cmd.index("-vf") + 1]


# --- R-1.3 de punta a punta: imagen() aborta ANTES del primer tramo -------------

# N4 (QA 03/10/2026): había acá un test
# "test_imagen_con_vaapi_forzado_sin_vaapi_aborta_antes_de_armar_el_primer_tramo" que sólo
# comprobaba que no existiera seg/00.mp4 — y esa aserción pasa igual de verde aunque se borre
# el encoder.preparar() de imagen() (comprobado a mano: build_segment del segmento "titulo"
# también llama a encoder.cv_args(), que revienta igual, sólo que más tarde). El test de abajo
# (test_imagen_aborta_antes_de_generar_ninguna_voz) sí lo detecta: mockea voice_wav para que
# falle si se llama, y sin encoder.preparar() se llega a invocarla antes de que el encoder
# aborte. Se borró el primero por redundante y más débil que el segundo, que cubre el mismo
# escenario (R-1.3) con una aserción que de verdad depende de la llamada temprana.

def test_imagen_aborta_antes_de_generar_ninguna_voz(tmp_path, monkeypatch):
    # "antes del primer tramo" significa antes de gastar en generar voces, no sólo
    # antes de escribir el primer .mp4: la voz puede ser una API paga (Fish, ElevenLabs).
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    monkeypatch.setenv("TUT_ENCODER", "vaapi")
    monkeypatch.setenv("TUT_VAAPI_DEVICE", "/no/existe")
    (tmp_path / "guion").mkdir()
    (tmp_path / "guion" / "v01.json").write_text(
        '{"segmentos": [{"tipo": "titulo", "titulo": "Hola", "texto": "x"}]}')

    def _no_debia_llamarse(*a, **kw):
        pytest.fail("no debía generar ninguna voz: el encoder tenía que fallar primero")

    monkeypatch.setattr(editar, "voice_wav", _no_debia_llamarse)

    with pytest.raises(encoder.EncoderError, match="/no/existe"):
        editar.imagen("v01", "juani")
