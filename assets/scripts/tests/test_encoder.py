"""encoder.py: elige libx264 (software) o h264_vaapi una sola vez por proceso.

TUT_ENCODER (auto|vaapi|software; default software) decide el modo. TUT_VAAPI_DEVICE
(default /dev/dri/renderD128) el dispositivo. La disponibilidad se prueba codificando
1 cuadro de verdad (R-1.4): nunca por si el archivo del dispositivo existe.
"""
import subprocess
import sys
from pathlib import Path

import pytest

import encoder


@pytest.fixture(autouse=True)
def _sin_cache(monkeypatch):
    """Cada test decide su propio TUT_ENCODER: la decisión no puede quedar cacheada de otro test."""
    monkeypatch.delenv("TUT_ENCODER", raising=False)
    monkeypatch.delenv("TUT_VAAPI_DEVICE", raising=False)
    encoder.reset()
    yield
    encoder.reset()


# --- R-1.5: sin TUT_ENCODER, software, idéntico al Hito 1 --------------------

def test_sin_tut_encoder_usa_libx264():
    assert encoder.cv_args(crf=20, preset="veryfast") == [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]


def test_sin_tut_encoder_el_vf_no_se_toca():
    assert encoder.vf("crop=10:10:0:0") == "crop=10:10:0:0"
    assert encoder.vf("") == ""


def test_software_explicito_es_igual_que_sin_la_variable(monkeypatch):
    monkeypatch.setenv("TUT_ENCODER", "software")
    assert encoder.cv_args(crf=18, preset="ultrafast", pix_fmt=False) == [
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18"]


# --- N2 (QA 03/10/2026): TUT_ENCODER="" se comporta como no-definida ---------

def test_tut_encoder_vacia_se_comporta_como_no_definida(monkeypatch):
    monkeypatch.setenv("TUT_ENCODER", "")
    assert encoder.cv_args(crf=20, preset="veryfast") == [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]


def test_tut_encoder_con_mayusculas_y_espacios_se_normaliza(monkeypatch):
    monkeypatch.setenv("TUT_ENCODER", " AUTO ")
    monkeypatch.setenv("TUT_VAAPI_DEVICE", "/no/existe")

    args = encoder.cv_args(crf=20)

    assert args[1] == "libx264"


# --- TUT_ENCODER inválido -----------------------------------------------------

def test_un_encoder_desconocido_falla_nombrando_las_opciones(monkeypatch):
    monkeypatch.setenv("TUT_ENCODER", "nvenc")
    with pytest.raises(ValueError, match="auto.*vaapi.*software|nvenc"):
        encoder.cv_args(crf=20)


# --- R-1.2: auto sin VAAPI cae a software, una sola línea en stderr ----------

def test_auto_sin_vaapi_cae_a_software_con_un_aviso(monkeypatch, capsys):
    monkeypatch.setenv("TUT_ENCODER", "auto")
    monkeypatch.setenv("TUT_VAAPI_DEVICE", "/no/existe")

    args = encoder.cv_args(crf=20, preset="veryfast")

    assert args == ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    err = capsys.readouterr().err
    lineas = [l for l in err.splitlines() if l.strip()]
    assert len(lineas) == 1
    assert lineas[0].startswith("VAAPI no disponible (")
    assert lineas[0].endswith("): uso libx264")


def test_el_aviso_de_auto_sale_una_sola_vez_aunque_se_pida_varias_veces(monkeypatch, capsys):
    monkeypatch.setenv("TUT_ENCODER", "auto")
    monkeypatch.setenv("TUT_VAAPI_DEVICE", "/no/existe")

    encoder.cv_args(crf=20)
    encoder.cv_args(crf=18)
    encoder.vf("algo")

    err = capsys.readouterr().err
    assert err.count("VAAPI no disponible") == 1


# --- R-1.3: TUT_ENCODER=vaapi sin VAAPI: salida != 0, el mensaje nombra el dispositivo --

def test_vaapi_forzado_sin_vaapi_revienta_nombrando_el_dispositivo(monkeypatch):
    monkeypatch.setenv("TUT_ENCODER", "vaapi")
    monkeypatch.setenv("TUT_VAAPI_DEVICE", "/no/existe")

    with pytest.raises(encoder.EncoderError, match="/no/existe"):
        encoder.cv_args(crf=20)


def test_preparar_decide_ya_en_vez_de_esperar_al_primer_segmento(monkeypatch):
    # R-1.3: imagen() llama a esto ANTES de armar ningún tramo, para abortar temprano.
    monkeypatch.setenv("TUT_ENCODER", "vaapi")
    monkeypatch.setenv("TUT_VAAPI_DEVICE", "/no/existe")

    with pytest.raises(encoder.EncoderError, match="/no/existe"):
        encoder.preparar()


# --- R-1.4: se decide codificando, no por la existencia del archivo ----------

def test_un_dispositivo_que_existe_pero_no_es_vaapi_tambien_cae_a_software(monkeypatch, capsys, tmp_path):
    # el path EXISTE (es un archivo cualquiera): si decidiéramos por existencia, esto
    # pasaría por disponible y rompería; tiene que caer a software igual que R-1.2.
    falso = tmp_path / "no-es-un-gpu.txt"
    falso.write_text("esto no es un dispositivo vaapi")
    monkeypatch.setenv("TUT_ENCODER", "auto")
    monkeypatch.setenv("TUT_VAAPI_DEVICE", str(falso))

    args = encoder.cv_args(crf=20)

    assert args[1] == "libx264"
    assert "VAAPI no disponible" in capsys.readouterr().err


# --- Windows con auto: software + aviso, nunca VAAPI -------------------------

def test_windows_con_auto_usa_software_y_avisa(monkeypatch, capsys):
    monkeypatch.setenv("TUT_ENCODER", "auto")
    monkeypatch.setattr(encoder.sys, "platform", "win32")

    args = encoder.cv_args(crf=20)

    assert args[1] == "libx264"
    assert "Windows" in capsys.readouterr().err


def test_windows_con_vaapi_forzado_tambien_falla(monkeypatch):
    monkeypatch.setenv("TUT_ENCODER", "vaapi")
    monkeypatch.setattr(encoder.sys, "platform", "win32")

    with pytest.raises(encoder.EncoderError, match="Windows"):
        encoder.cv_args(crf=20)


# --- R-1.1: VAAPI real disponible --------------------------------------------

def _vaapi_en_esta_maquina() -> bool:
    res = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=128x128:r=1:d=1",
         "-vf", "format=nv12,hwupload", "-vaapi_device", "/dev/dri/renderD128",
         "-c:v", "h264_vaapi", "-frames:v", "1", "-f", "null", "-"],
        capture_output=True)
    return res.returncode == 0


@pytest.mark.skipif(not _vaapi_en_esta_maquina(), reason="esta máquina no tiene VAAPI h264 (sin /dev/dri o sin permisos)")
def test_auto_con_vaapi_disponible_usa_h264_vaapi():
    import os
    os.environ["TUT_ENCODER"] = "auto"
    try:
        encoder.reset()
        vf = encoder.vf("crop=10:10:0:0")
        args = encoder.cv_args(crf=20)
    finally:
        del os.environ["TUT_ENCODER"]
        encoder.reset()

    assert vf == "crop=10:10:0:0,format=nv12,hwupload"
    assert args[:4] == ["-vaapi_device", "/dev/dri/renderD128", "-c:v", "h264_vaapi"]


@pytest.mark.skipif(not _vaapi_en_esta_maquina(), reason="esta máquina no tiene VAAPI h264 (sin /dev/dri o sin permisos)")
def test_el_cuadro_codificado_con_vaapi_se_lee_h264_yuv420p(tmp_path, monkeypatch):
    monkeypatch.setenv("TUT_ENCODER", "auto")
    salida = tmp_path / "prueba.mp4"
    vf = encoder.vf("")
    args = encoder.cv_args(crf=20)

    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=red:s=128x128:r=30:d=0.2",
                    *(["-vf", vf] if vf else []), *args, str(salida)], check=True)

    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v",
                          "-show_entries", "stream=codec_name,pix_fmt:stream_tags=encoder",
                          "-of", "csv=p=0", str(salida)], capture_output=True, text=True, check=True).stdout
    assert "h264" in out
    assert "yuv420p" in out
    assert "h264_vaapi" in out
