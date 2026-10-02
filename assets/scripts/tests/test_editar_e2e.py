"""De punta a punta: un guion que mezcla pantalla grabada y una escena.

imagen() corta el crudo y renderiza la escena con Chrome; voz() monta la voz. Voz
sintética (tonos) y palabras falsas: lo que se prueba es el armado, no Whisper.
"""
import json
import subprocess

import pytest

pytest.importorskip("playwright")
import editar  # noqa: E402
import palabras  # noqa: E402

pytestmark = pytest.mark.integracion

VOZ = [{"palabra": "Mirá", "inicio": 0.0, "fin": 0.3},
       {"palabra": "el", "inicio": 0.3, "fin": 0.4},
       {"palabra": "sol.", "inicio": 0.4, "fin": 0.9}]


def _probe(mp4, stream, campos):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-count_packets",
                          "-show_entries", f"stream={campos}", "-of", "csv=p=0", str(mp4)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return out.split(",")


def test_imagen_y_voz_arman_un_video_mixto_de_pantalla_y_escena(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "raw").mkdir()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=1920x1080:r=30:d=3",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    str(tmp_path / "raw" / "v09.mp4")], check=True)
    (tmp_path / "guion").mkdir()
    (tmp_path / "guion" / "v09.json").write_text(json.dumps({"raw": "raw/v09.mp4", "segmentos": [
        {"inicio": 0, "fin": 2, "texto": "Esto es la pantalla."},
        {"escena": {"tipo": "presentacion", "titulo": {"texto": "Hola"},
                    "puntos": [{"texto": "Sol", "cue": "el sol"}]}, "texto": "Mirá el sol."}]}))
    voces = tmp_path / "videos" / "v09" / "juani"
    voces.mkdir(parents=True)
    for i in range(2):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=300:d=1",
                        str(voces / f"{i:02d}.wav")], check=True)
    monkeypatch.setattr(palabras, "transcribir", lambda a, modelo=None: VOZ)

    editar.imagen("v09", "juani")
    editar.voz("v09", "juani")

    work = tmp_path / "videos" / "v09"
    slots = json.loads((work / "slots-juani.json").read_text())
    pantalla, escena_ = (_probe(work / "seg" / f"{i:02d}.mp4", "v", "codec_name,width,height,pix_fmt,r_frame_rate,nb_read_packets")
                         for i in range(2))
    assert pantalla[:5] == escena_[:5] == ["h264", "1920", "1080", "yuv420p", "30/1"], "si difieren, el concat -c copy se rompe"
    assert int(escena_[5]) == round(slots[1] * 30), "la escena dura su slot"
    cuadros, = _probe(work / "final-juani.mp4", "v", "nb_read_packets")
    assert int(cuadros) == int(pantalla[5]) + int(escena_[5])
    duracion_audio, = _probe(work / "final-juani.mp4", "a", "duration")
    assert float(duracion_audio) == pytest.approx(int(cuadros) / 30, abs=0.05)
