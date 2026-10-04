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


# --- QA 04/10/2026 (NOTE, ronda 3): musica.py necesita leer stderr (ebur128/loudnorm lo --
# escriben ahí) para poder pasar TODOS sus subprocess por run() con vigía.

def test_run_con_devolver_stderr_da_una_tupla_stdout_stderr():
    out = editar.run(["python3", "-c", "import sys; print('hola'); print('chau', file=sys.stderr)"],
                      timeout=5, devolver_stderr=True)

    assert out == ("hola\n", "chau\n")


def test_run_sin_devolver_stderr_sigue_devolviendo_solo_stdout_como_antes():
    out = editar.run(["echo", "hola"], timeout=5)

    assert out == "hola\n"


# --- QA 04/10/2026 (NOTE, ronda 3): stderr que no es UTF-8 vállido no puede matar el hilo lector --

def test_run_con_stderr_no_utf8_no_tira_unicodedecodeerror(tmp_path):
    # un stream de stderr con bytes que no son UTF-8 válido mataba el hilo lector
    # (UnicodeDecodeError silencioso, sin traza): el error real quedaba sin causa.
    falso_cmd = tmp_path / "falso_cmd.py"
    falso_cmd.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.stderr.buffer.write(b'linea con byte invalido: \\xff\\xfe\\n')\n"
        "sys.stderr.buffer.flush()\n"
        "sys.exit(1)\n")
    falso_cmd.chmod(0o755)

    with pytest.raises(RuntimeError) as exc:
        editar.run(["python3", str(falso_cmd)], timeout=5)

    # tiene que llegar la CAUSA real (el texto decodificable de esa línea de stderr), no
    # perderla porque el hilo lector murió al toparse con el byte inválido.
    assert "linea con byte invalido" in str(exc.value), exc.value


def test_run_con_ffmpeg_real_callado_por_loglevel_error_pero_progresando_no_falla(tmp_path):
    # con -loglevel error, ffmpeg no escribe nada a stderr mientras todo va bien: sin el
    # -progress pipe:1 que run() le agrega, un render activo (CPU alto, sin colgarse) se
    # vería "sin avance" y el vigía lo mataría por error. Esto prueba que no pasa: un
    # encode con filtro pesado que tarda más que el timeout "sin avance" sin cortarse.
    #
    # QA 04/10/2026 (NOTE, ronda 3): con timeout=1.0 esto era flaky (1/11, medido por QA):
    # bajo carga del sistema, el intervalo entre actualizaciones de "-progress" (una por
    # cuadro, con boxblur+veryslow) a veces supera 1.0s, y el vigía lo corta por error -eso
    # NO es el comportamiento que el test quiere ejercitar, es ruido de timing. El timeout
    # del vigía sube a 5.0s (margen de sobra incluso bajo carga); lo que el test prueba
    # sigue intacto: el render total (medido, bastante más de 5s con este filtro) tiene
    # que terminar bien de todas formas.
    salida = tmp_path / "pesado.mp4"

    editar.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                "-i", "testsrc=s=640x480:r=30:d=3", "-vf", "boxblur=20:5",
                "-c:v", "libx264", "-preset", "veryslow", str(salida)], timeout=5.0)

    assert salida.exists()
