"""editar.py voz: música de fondo con ducking (S2, docs/explicador/HITO2.md).

Formato del guion: "musica" arriba es {archivo, debajo_de_la_voz_lu?, fundido?}; en un
segmento, "musica": false la apaga para ese tramo. Sin la clave "musica" arriba, el
comportamiento es el del Hito 1 (G3, cubierto por test_s0_red_de_seguridad.py).
"""
import array
import json
import math
import re
import subprocess
import wave

import pytest

import editar
import musica

SLOTS = [2.8, 3.4]


def _wav(path, dur: float, freq: float = 300, sr: int = 22050) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=f={freq}:d={dur}", "-ar", str(sr), str(path)], check=True)


def _rms_en(wav_path, inicio: float, fin: float) -> float:
    """RMS normalizado (0..1) del canal 0 de `wav_path` entre `inicio` y `fin` segundos."""
    pcm = wav_path.with_name(f"{wav_path.stem}.rms.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), "-ss", str(inicio),
                    "-to", str(fin), "-ac", "1", "-ar", "22050", "-sample_fmt", "s16", str(pcm)], check=True)
    with wave.open(str(pcm)) as w:
        frames = w.readframes(w.getnframes())
    muestras = array.array("h")
    muestras.frombytes(frames)
    if not muestras:
        return 0.0
    return math.sqrt(sum(s * s for s in muestras) / len(muestras)) / 32768


def _dbfs(rms: float) -> float:
    return 20 * math.log10(rms) if rms > 0 else float("-inf")


def _duracion(path, stream="a") -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries",
                          "stream=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def _video(path, cuadros: int) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=320x180:r=30",
                    "-frames:v", str(cuadros), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)


@pytest.fixture
def tutorial(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    work = tmp_path / "videos" / "v09"
    (work / "juani").mkdir(parents=True)
    for i, d in enumerate(SLOTS):
        # voz bien adentro del slot (LEAD=0.3, TAIL=0.5): no activa el camino "acelerar"
        _wav(work / "juani" / f"{i:02d}.wav", d - 0.3 - 0.6)
    cuadros = sum(round(s * 30) for s in SLOTS)
    _video(work / "video-juani.mp4", cuadros)
    (work / "slots-juani.json").write_text(json.dumps(SLOTS))
    return tmp_path, work


def _guion(tmp_path, musica=None, musica_segmentos=(None, None)):
    segmentos = [{"texto": f"Tramo {i}."} for i in range(len(SLOTS))]
    for seg, m in zip(segmentos, musica_segmentos):
        if m is not None:
            seg["musica"] = m
    g = {"segmentos": segmentos}
    if musica is not None:
        g["musica"] = musica
    (tmp_path / "guion" / "v09.json").write_text(json.dumps(g, ensure_ascii=False))


# --- R-2.6: archivo de música faltante o ilegible -------------------------------------

def test_voz_con_musica_faltante_aborta_con_la_ruta_absoluta_y_no_escribe_el_final(tutorial):
    tmp_path, work = tutorial
    _guion(tmp_path, musica={"archivo": "musica/no-existe.mp3"})

    with pytest.raises(SystemExit) as e:
        editar.voz("v09", "juani")

    assert str((tmp_path / "musica/no-existe.mp3").resolve()) in str(e.value)
    assert not (work / "final-juani.mp4").exists()


def test_voz_con_musica_ilegible_aborta_y_no_escribe_el_final(tutorial):
    tmp_path, work = tutorial
    (tmp_path / "musica").mkdir()
    (tmp_path / "musica" / "rota.mp3").write_bytes(b"no es un mp3 valido")
    _guion(tmp_path, musica={"archivo": "musica/rota.mp3"})

    with pytest.raises(SystemExit):
        editar.voz("v09", "juani")

    assert not (work / "final-juani.mp4").exists()


def _con_musica(tmp_path, dur=10.0, freq=220):
    (tmp_path / "musica").mkdir()
    archivo = tmp_path / "musica" / "fondo.wav"
    _wav(archivo, dur, freq=freq, sr=44100)
    return "musica/fondo.wav"


# --- R-2.1: con música, el final no es silencio digital ------------------------------

def test_voz_con_musica_los_primeros_0_3s_no_son_silencio_digital(tutorial):
    tmp_path, work = tutorial
    archivo = _con_musica(tmp_path)
    _guion(tmp_path, musica={"archivo": archivo})

    editar.voz("v09", "juani")

    final = work / "final-juani.mp4"
    assert _dbfs(_rms_en(final, 0.0, 0.3)) > -60


# --- R-2.4: la música dura lo mismo que el video (bucle si es corta) -----------------

def test_voz_con_musica_mas_corta_que_el_total_hace_bucle_y_dura_lo_mismo_que_el_video(tutorial):
    tmp_path, work = tutorial
    archivo = _con_musica(tmp_path, dur=1.5)  # el total de los slots es 6.2s
    _guion(tmp_path, musica={"archivo": archivo})

    editar.voz("v09", "juani")

    # la pista de música en bucle, NO el final (que además tiene su propio apad de
    # seguridad): si el bucle no alcanza, esto lo detecta y el apad del final lo tapa.
    cruda = work / "musica-cruda-juani.wav"
    assert _duracion(cruda, "a") == pytest.approx(sum(SLOTS), abs=0.05)

    final = work / "final-juani.mp4"
    assert _duracion(final, "a") == pytest.approx(_duracion(final, "v"), abs=0.05)


# --- R-2.5: "musica": false en un segmento ---------------------------------------------

def test_voz_con_musica_false_en_un_segmento_queda_por_debajo_de_60dbfs_en_ese_slot(tutorial):
    tmp_path, work = tutorial
    archivo = _con_musica(tmp_path)
    _guion(tmp_path, musica={"archivo": archivo}, musica_segmentos=(None, False))

    editar.voz("v09", "juani")

    # R-2.5 habla de la música, no del final mezclado con la voz (que sigue sonando igual
    # en ese segmento): se mide la pista musica-<voz>.wav, bien adentro del slot "mute"
    # (segmento 1: arranca en SLOTS[0]=2.8s, dura SLOTS[1]=3.4s).
    musica_wav = work / "musica-juani.wav"
    assert _dbfs(_rms_en(musica_wav, 3.2, 5.8)) < -60


# --- R-2.7 (G2): el .srt y el arranque de la voz no se mueven con música -------------

def test_voz_con_musica_no_cambia_el_srt_ni_el_arranque_de_la_voz(tutorial):
    tmp_path, work = tutorial
    archivo = _con_musica(tmp_path)
    _guion(tmp_path, musica={"archivo": archivo})
    srt_sin_musica = work / "final-juani.sin-musica.srt"

    _guion(tmp_path)  # primero, sin música: srt de referencia
    editar.voz("v09", "juani")
    srt_sin_musica.write_text((work / "final-juani.srt").read_text())

    _guion(tmp_path, musica={"archivo": archivo})  # ahora, con música
    editar.voz("v09", "juani")

    assert (work / "final-juani.srt").read_text() == srt_sin_musica.read_text()


# --- R-2.3: con música, el final sigue dando -16±1 LUFS / TP<=-1.5 dBTP --------------

def test_voz_con_musica_el_final_sigue_cumpliendo_el_loudness_objetivo(tutorial):
    tmp_path, work = tutorial
    archivo = _con_musica(tmp_path)
    _guion(tmp_path, musica={"archivo": archivo})

    editar.voz("v09", "juani")

    final = work / "final-juani.mp4"
    audio = work / "final-audio.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(final), "-vn", str(audio)], check=True)
    i, tp = musica.medir_i_tp(audio)
    assert i == pytest.approx(-16.0, abs=1.0)
    assert tp <= -1.5 + 0.3  # loudnorm no es exacto al dBTP: margen chico de medición
