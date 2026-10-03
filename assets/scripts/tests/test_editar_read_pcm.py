"""editar.read_pcm: normaliza la voz al wav final, acelerándola si no entra en el slot.

QA (03/10/2026): ffmpeg 6.1.1 se cuelga (deadlock) con `-af atempo=1.0000` para
ciertas entradas, reproducible con `sine=f=300:d=1.3` a 44100 Hz. Ese es
justamente el factor que read_pcm aplica en el camino normal: la voz entra en
el slot (factor <= 1.0 -> tempo = 1.0). No hace falta acelerar nada cuando el
factor es 1.0, así que no hay que pasar por ese filtro.
"""
import subprocess

import pytest

import editar


def _wav(tmp_path, nombre: str, dur: float, sr: int = 44100) -> "editar.Path":
    from pathlib import Path

    out = Path(tmp_path) / nombre
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=f=300:d={dur}", "-ar", str(sr), str(out)], check=True)
    return out


def test_read_pcm_con_factor_1_no_se_cuelga_y_devuelve_pcm(tmp_path, monkeypatch):
    # la voz entra de sobra en el slot: factor 1.0, el caso que colgaba a ffmpeg.
    monkeypatch.setenv("TUT_FFMPEG_TIMEOUT", "5")
    wav = _wav(tmp_path, "voz.wav", 1.3)

    data = editar.read_pcm(wav, max_len=5.0)

    assert len(data) > 0


def test_read_pcm_con_factor_mayor_a_1_sigue_acelerando(tmp_path, monkeypatch):
    # la voz NO entra en el slot: factor > 1.0, tiene que seguir acelerando con atempo.
    monkeypatch.setenv("TUT_FFMPEG_TIMEOUT", "5")
    wav = _wav(tmp_path, "voz.wav", 2.0)

    data = editar.read_pcm(wav, max_len=1.0)

    # a doble velocidad, la cantidad de muestras (a 22050 Hz mono s16) es ~ la mitad
    muestras = len(data) // 2
    assert 22050 * 0.9 <= muestras <= 22050 * 1.1
