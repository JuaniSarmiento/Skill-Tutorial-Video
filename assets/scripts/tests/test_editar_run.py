"""editar.run: wrapper de subprocess con timeout, para no colgarse para siempre.

QA (03/10/2026): ffmpeg 6.1.1 se cuelga (deadlock) con ciertas combinaciones de
entrada y `-af atempo=1.0000` (ver test_editar_voz.py, el caso real). run() no
tenía timeout: un ffmpeg colgado colgaba el proceso entero sin ningún mensaje.
"""
import time

import pytest

import editar


def test_run_con_timeout_falla_nombrando_el_comando_en_vez_de_colgarse():
    inicio = time.monotonic()

    with pytest.raises(RuntimeError, match="sleep"):
        editar.run(["sleep", "5"], timeout=0.5)

    assert time.monotonic() - inicio < 3


def test_run_sin_pasar_el_timeout_igual_devuelve_la_salida_si_termina_antes():
    out = editar.run(["echo", "hola"], timeout=5)

    assert out.strip() == "hola"


# --- N6 (QA 03/10/2026): ffmpeg falla a mitad de un tramo VAAPI ------------------

def test_run_que_falla_con_h264_vaapi_sugiere_software_sin_mezclar_encoders():
    with pytest.raises(RuntimeError, match="TUT_ENCODER=software"):
        editar.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "color=c=black:s=16x16:r=1:d=1", "-vf", "format=nv12,hwupload",
                    "-vaapi_device", "/no/existe", "-c:v", "h264_vaapi",
                    "-frames:v", "1", "-f", "null", "-"])


def test_run_que_falla_con_libx264_no_sugiere_cambiar_de_encoder():
    with pytest.raises(RuntimeError) as exc:
        editar.run(["ffmpeg", "-y", "-loglevel", "error", "-c:v", "libx264", "-i", "/no/existe.mp4",
                    "-f", "null", "-"])

    assert "TUT_ENCODER" not in str(exc.value)
