"""editar.run: wrapper de subprocess con timeout, para no colgarse para siempre.

QA (03/10/2026): ffmpeg 6.1.1 se cuelga (deadlock) con ciertas combinaciones de
entrada y `-af atempo=1.0000` (ver test_editar_voz.py, el caso real). run() no
tenía timeout: un ffmpeg colgado colgaba el proceso entero sin ningún mensaje.

B2 (QA 03/10/2026): ese timeout era un límite TOTAL (120s por defecto), y un tramo
largo que va progresando bien (un screen recording de 20 minutos, en la 2da pasada
de build_segment) caía en el timeout sin haberse colgado. Ahora `timeout` (y
TUT_FFMPEG_TIMEOUT) son segundos SIN AVANCE: sólo falla si el proceso deja de
progresar, nunca por tardar en total.
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


# --- B2 (QA 03/10/2026): timeout = sin avance, no total ------------------------------

def test_run_con_progreso_continuo_mas_alla_del_timeout_total_no_falla():
    # "avanza" (imprime algo) cada 0.1s durante 1.2s con un timeout de 0.3s SIN avance:
    # nunca pasa 0.3s sin progresar, así que tiene que terminar bien aunque en total
    # tarde 4x el timeout. Un timeout TOTAL (el de antes de B2) cortaría esto por error.
    script = "import time, sys\nfor _ in range(12):\n time.sleep(0.1)\n print('x'); sys.stdout.flush()\n"

    inicio = time.monotonic()
    out = editar.run(["python3", "-c", script], timeout=0.3)

    assert time.monotonic() - inicio > 1.0
    assert out.count("x") == 12


def test_run_sin_ningun_avance_falla_nombrando_la_variable_del_timeout():
    inicio = time.monotonic()

    with pytest.raises(RuntimeError, match="TUT_FFMPEG_TIMEOUT"):
        editar.run(["sleep", "5"], timeout=0.3)

    assert time.monotonic() - inicio < 3


def test_run_que_se_cuelga_borra_el_mp4_parcial_si_el_comando_es_ffmpeg(tmp_path):
    # simula un "ffmpeg" que escribe un archivo parcial y después se cuelga sin progresar
    # más: run() tiene que borrar ese parcial al cortar (si no, queda un .mp4/.wav corrupto
    # que un render repetido podría encontrar y dar por bueno).
    falso_ffmpeg = tmp_path / "ffmpeg"
    falso_ffmpeg.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, time\n"
        "open(sys.argv[-1], 'wb').write(b'datos a medio escribir')\n"
        "time.sleep(5)\n")
    falso_ffmpeg.chmod(0o755)
    salida = tmp_path / "seg.tmp.mp4"

    with pytest.raises(RuntimeError):
        editar.run([str(falso_ffmpeg), str(salida)], timeout=0.3)

    assert not salida.exists()


def test_run_con_ffmpeg_real_callado_por_loglevel_error_pero_progresando_no_falla(tmp_path):
    # con -loglevel error, ffmpeg no escribe nada a stderr mientras todo va bien: sin el
    # -progress pipe:1 que run() le agrega, un render activo (CPU alto, sin colgarse) se
    # vería "sin avance" y el vigía lo mataría por error. Esto prueba que no pasa: un
    # encode con filtro pesado que tarda más de 1s sin cortarse por el timeout de 1s.
    salida = tmp_path / "pesado.mp4"

    editar.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                "-i", "testsrc=s=640x480:r=30:d=3", "-vf", "boxblur=20:5",
                "-c:v", "libx264", "-preset", "veryslow", str(salida)], timeout=1.0)

    assert salida.exists()
