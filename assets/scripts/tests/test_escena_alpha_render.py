"""render(..., alpha=True) contra Chrome: el fondo transparente de la página sale
con canal alfa 0 y lo opaco con alfa 255 (H6, HITO3.md: el rótulo se compone con
`overlay` de ffmpeg encima de un tramo ya armado)."""
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402

pytestmark = pytest.mark.integracion

FIX = Path(__file__).parent / "fixtures" / "alfa" / "transparente.html"


def _alfa(mp4, x, y):
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-frames:v", "1",
                          "-vf", f"format=rgba,crop=2:2:{x}:{y}",
                          "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                         capture_output=True, check=True).stdout
    assert len(out) >= 4, f"ffmpeg no devolvió ningún cuadro para {mp4}"
    return out[3]   # canal alfa del primer pixel


def test_el_fondo_transparente_sale_con_alfa_cero(tmp_path):
    salida = tmp_path / "rotulo.mov"
    escena.render(FIX, {}, salida, alpha=True, verificar=False)
    assert _alfa(salida, 10, 10) == 0


def test_lo_opaco_sale_con_alfa_completo(tmp_path):
    salida = tmp_path / "rotulo.mov"
    escena.render(FIX, {}, salida, alpha=True, verificar=False)
    assert _alfa(salida, 150, 150) == 255


def test_sin_alpha_el_fondo_transparente_se_compone_sobre_blanco(tmp_path):
    # triangulación: la MISMA página, sin alpha=True, no tiene canal alfa real
    # (yuv420p no lo tiene): el fondo transparente se compuso contra blanco al
    # sacar el PNG (comportamiento de Playwright sin omit_background).
    salida = tmp_path / "normal.mp4"
    escena.render(FIX, {}, salida, alpha=False, verificar=False)
    rgb = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(salida), "-frames:v", "1",
                          "-vf", "crop=2:2:10:10", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    assert rgb[:3] == b"\xff\xff\xff"
