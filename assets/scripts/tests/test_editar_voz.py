"""editar.py voz: el audio se monta sobre el video sin comerse cuadros.

QA (02/10/2026): un video armado de 685 cuadros (22,83 s) terminaba con 681 en
final-<voz>.mp4. `-shortest` corta por el stream más corto, y la voz suma los
slots (22,8 s) mientras cada tramo de video puede durar hasta un cuadro más.
"""
import json
import subprocess

import pytest

import editar

SLOTS = [3.82, 5.89, 8.79, 4.3]


def _cuadros(mp4):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-count_packets",
                          "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(mp4)],
                         capture_output=True, text=True, check=True).stdout
    return int(out)


def _duracion(mp4, stream):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries",
                          "stream=duration", "-of", "csv=p=0", str(mp4)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


@pytest.fixture
def tutorial(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    (tmp_path / "guion" / "v09.json").write_text(json.dumps(
        {"segmentos": [{"texto": f"Tramo {i}."} for i in range(len(SLOTS))]}))
    work = tmp_path / "videos" / "v09"
    (work / "juani").mkdir(parents=True)
    for i in range(len(SLOTS)):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=300:d=2",
                        str(work / "juani" / f"{i:02d}.wav")], check=True)
    # cada tramo dura su slot redondeado al cuadro, como lo deja imagen(): 685 cuadros
    cuadros = sum(round(s * 30) for s in SLOTS)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=320x180:r=30",
                    "-frames:v", str(cuadros), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(work / "video-juani.mp4")], check=True)
    (work / "slots-juani.json").write_text(json.dumps(SLOTS))
    return work


def test_voz_no_le_corta_cuadros_al_video_y_el_audio_dura_lo_mismo(tutorial):
    editar.voz("v09", "juani")

    final = tutorial / "final-juani.mp4"
    assert _cuadros(final) == _cuadros(tutorial / "video-juani.mp4") == 685
    assert _duracion(final, "a") == pytest.approx(_duracion(final, "v"), abs=0.05)
