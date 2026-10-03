"""escena.py: comando_ffmpeg pasa por encoder.py (HITO2.md S1).

Antes del Hito 2, comando_ffmpeg tenía "-c:v", "libx264" escrito a mano (escena.py:59).
"""
import pytest

import encoder
import escena


@pytest.fixture(autouse=True)
def _sin_cache(monkeypatch):
    monkeypatch.delenv("TUT_ENCODER", raising=False)
    monkeypatch.delenv("TUT_VAAPI_DEVICE", raising=False)
    encoder.reset()
    yield
    encoder.reset()


def test_sin_tut_encoder_sigue_siendo_libx264_igual_que_antes():
    # R-1.5 / G3: ningún byte cambia sin la variable.
    cmd = escena.comando_ffmpeg("x.mp4", fps=30)
    assert cmd[cmd.index("-c:v", cmd.index("-i")) + 1] == "libx264"
    assert "-vf" not in cmd


def test_a_ancho_completo_sigue_sin_vf_sin_tut_encoder():
    assert "-vf" not in escena.comando_ffmpeg("x.mp4", fps=30, ancho=1920)


def test_con_auto_sin_vaapi_tambien_cae_a_libx264(monkeypatch, capsys):
    monkeypatch.setenv("TUT_ENCODER", "auto")
    monkeypatch.setenv("TUT_VAAPI_DEVICE", "/no/existe")

    cmd = escena.comando_ffmpeg("x.mp4", fps=30)

    assert cmd[cmd.index("-c:v", cmd.index("-i")) + 1] == "libx264"
    assert "VAAPI no disponible" in capsys.readouterr().err


def test_con_vaapi_disponible_usa_h264_vaapi_y_agrega_el_hwupload_al_final(monkeypatch):
    monkeypatch.setenv("TUT_ENCODER", "vaapi")
    monkeypatch.setattr(encoder, "_probar_vaapi", lambda device: (True, ""))

    cmd = escena.comando_ffmpeg("x.mp4", fps=30, ancho=960)

    assert "-vaapi_device" in cmd
    assert cmd[cmd.index("-c:v", cmd.index("-i")) + 1] == "h264_vaapi"
    assert cmd[cmd.index("-vf") + 1] == "scale=960:-2:flags=lanczos,format=nv12,hwupload"


def test_con_vaapi_disponible_y_ancho_completo_el_vf_es_solo_el_hwupload(monkeypatch):
    monkeypatch.setenv("TUT_ENCODER", "vaapi")
    monkeypatch.setattr(encoder, "_probar_vaapi", lambda device: (True, ""))

    cmd = escena.comando_ffmpeg("x.mp4", fps=30)

    assert cmd[cmd.index("-vf") + 1] == "format=nv12,hwupload"
