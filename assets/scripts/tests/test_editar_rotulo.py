"""H6 (HITO3.md): "rotulo" en un segmento se superpone (ffmpeg overlay, canal
alfa) a CUALQUIER tramo ya armado — pantalla grabada, diapositiva o escena.
G1: no cambia la cantidad de cuadros del tramo. G4: el tramo final sigue
compartiendo códec/pix_fmt con el resto (encoder.cv_args). Sin "rotulo" en el
segmento, build_segment no toca nada (G3: no hay llamada a ffmpeg de más).
"""
import subprocess

import pytest

pytest.importorskip("playwright")
import editar  # noqa: E402

pytestmark = pytest.mark.integracion


def _raw(tmp_path, color="red", dur=5):
    r = tmp_path / "raw.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"color=c={color}:s=1920x1080:r=30:d={dur}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(r)], check=True)
    return r


def _probe(mp4, campos="codec_name,pix_fmt,nb_read_packets"):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-count_packets",
                          "-show_entries", f"stream={campos}", "-of", "csv=p=0", str(mp4)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return out.split(",")


def _pixel(mp4, t, x=150, y=645):
    # (150, 645): esquina interna del chip del rótulo (x140+40 padding, y635+28
    # padding), lejos de cualquier glyph de texto -- medido una vez contra Chrome
    # con el spec de referencia (ver test_escena_rotulo.py).
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-ss", str(t), "-frames:v", "1",
                          "-vf", f"crop=2:2:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    assert len(out) >= 3
    return tuple(out[:3])


def _cerca(rgb, esperado, tol=6):
    return all(abs(a - b) <= tol for a, b in zip(rgb, esperado))


ROTULO = {"titulo": "Memoización", "subtitulo": "Unidad 10 · Programación I", "cue": 1.0, "dura": 2.0}


def test_sin_rotulo_el_tramo_no_cambia(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    raw = _raw(tmp_path)
    out = tmp_path / "out.mp4"
    editar.build_segment("v01", raw, {"inicio": 0, "fin": 5}, 5.0, out)
    assert _cerca(_pixel(out, 1.8), (255, 0, 0))   # rojo puro: nada se superpuso


def test_con_rotulo_durante_la_ventana_se_ve_el_chip_oscuro(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    raw = _raw(tmp_path)
    out = tmp_path / "out.mp4"
    editar.build_segment("v01", raw, {"inicio": 0, "fin": 5, "rotulo": ROTULO}, 5.0, out)
    assert _cerca(_pixel(out, 1.8), (27, 30, 37))   # var(--superficie) del brand default


def test_con_rotulo_y_paleta_elegida_usa_el_color_de_esa_paleta(tmp_path, monkeypatch):
    """H10 (HITO3.md): el rótulo también respeta la paleta elegida por el guion."""
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    raw = _raw(tmp_path)
    out = tmp_path / "out.mp4"
    editar.build_segment("v01", raw, {"inicio": 0, "fin": 5, "rotulo": ROTULO}, 5.0, out, paleta="utn")
    assert _cerca(_pixel(out, 1.8), (232, 238, 246))   # var(--superficie) de la paleta "utn"


def test_con_rotulo_antes_y_despues_de_la_ventana_sigue_rojo(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    raw = _raw(tmp_path)
    out = tmp_path / "out.mp4"
    editar.build_segment("v01", raw, {"inicio": 0, "fin": 5, "rotulo": ROTULO}, 5.0, out)
    assert _cerca(_pixel(out, 0.3), (255, 0, 0))
    assert _cerca(_pixel(out, 4.5), (255, 0, 0))


def test_con_rotulo_no_cambia_la_cantidad_de_cuadros_ni_el_codec(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    raw = _raw(tmp_path)
    sin = tmp_path / "sin.mp4"
    con = tmp_path / "con.mp4"
    editar.build_segment("v01", raw, {"inicio": 0, "fin": 5}, 5.0, sin)
    editar.build_segment("v01", raw, {"inicio": 0, "fin": 5, "rotulo": ROTULO}, 5.0, con)
    codec_s, pf_s, n_s = _probe(sin)
    codec_c, pf_c, n_c = _probe(con)
    assert (codec_c, pf_c) == (codec_s, pf_s) == ("h264", "yuv420p")
    assert n_c == n_s   # G1: mismos cuadros con o sin rótulo
