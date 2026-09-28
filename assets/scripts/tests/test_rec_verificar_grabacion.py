"""Fallback de duración: si el .mkv quedó sin trailer, se verifica con
ffprobe -count_frames que los frames estén completos ANTES de abortar la
grabación, en vez de tirarla directamente por no tener duración legible.
"""
from pathlib import Path

import rec


def test_con_duracion_legible_se_acepta_sin_mirar_frames():
    llamado_frames = []
    ok, msg = rec._verificar_grabacion(
        Path("toma1.mkv"),
        ffprobe_duracion=lambda d: "12.5",
        ffprobe_frames=lambda d: llamado_frames.append(d) or "999",
    )
    assert ok is True
    assert "12.5s" in msg
    assert llamado_frames == []  # ni hace falta pedir los frames


def test_sin_duracion_pero_con_frames_completos_se_acepta():
    ok, msg = rec._verificar_grabacion(
        Path("toma1.mkv"),
        ffprobe_duracion=lambda d: "",
        ffprobe_frames=lambda d: "1800",
    )
    assert ok is True
    assert "1800 frames" in msg


def test_sin_duracion_y_sin_frames_se_rechaza():
    ok, msg = rec._verificar_grabacion(
        Path("toma1.mkv"),
        ffprobe_duracion=lambda d: "",
        ffprobe_frames=lambda d: "",
    )
    assert ok is False
    assert "ATENCION" in msg
