"""Render con canal alfa (H6, HITO3.md): el rótulo se compone como capa encima de
cualquier tramo (escena.render(..., alpha=True)). Sin alfa, el output sigue siendo
h264 yuv420p (G3: el render normal no cambia). Con alfa, qtrle (sin pix_fmt forzado:
RGBA entra tal cual) para que ffmpeg pueda overlay-earlo sobre el tramo base.
"""
import escena


def test_comando_alpha_usa_qtrle_en_vez_de_libx264():
    cmd = escena.comando_ffmpeg("out/rotulo.mov", fps=30, alpha=True)
    assert cmd[cmd.index("-c:v", cmd.index("-i")) + 1] == "qtrle"


def test_comando_alpha_no_fuerza_pix_fmt_yuv420p():
    cmd = escena.comando_ffmpeg("out/rotulo.mov", fps=30, alpha=True)
    assert "-pix_fmt" not in cmd


def test_sin_alpha_sigue_siendo_libx264_yuv420p():
    cmd = escena.comando_ffmpeg("out/x.mp4", fps=30)
    assert cmd[cmd.index("-c:v", cmd.index("-i")) + 1] == "libx264"
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
