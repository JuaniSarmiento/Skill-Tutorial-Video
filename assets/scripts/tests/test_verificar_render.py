"""H2 (HITO3.md): la puerta `check` dentro de `escena.py render` y los CLI.

Aparte de test_verificar_integracion.py porque render abre su propio Chrome (no puede
convivir con el Chrome de módulo de ese archivo: Playwright sync no se anida).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402
import verificar  # noqa: E402

pytestmark = pytest.mark.integracion

FIX = Path(__file__).parent / "fixtures" / "verificar"
SCRIPTS = Path(__file__).resolve().parents[1]


# --- la puerta en el render ------------------------------------------------------------

def test_render_no_renderiza_una_escena_que_no_pasa_y_nombra_el_problema(tmp_path):
    mp4 = tmp_path / "out.mp4"
    with pytest.raises(verificar.VerificacionError) as e:
        escena.render(FIX / "pisan.html", {}, mp4, fps=6, ancho=960)
    assert "precio" in str(e.value) and "--sin-verificar" in str(e.value)
    assert list(tmp_path.iterdir()) == []


def test_render_con_la_puerta_salteada_renderiza_igual(tmp_path):
    mp4 = tmp_path / "out.mp4"
    escena.render(FIX / "pisan.html", {}, mp4, fps=6, ancho=960, verificar=False)
    assert mp4.exists()


def test_el_cli_render_acepta_sin_verificar(tmp_path):
    spec = tmp_path / "s.json"
    spec.write_text("{}")
    mp4 = tmp_path / "o.mp4"
    corrida = [sys.executable, str(SCRIPTS / "escena.py"), "render", str(FIX / "pisan.html"), str(spec),
               "-o", str(mp4), "--fps", "6", "--ancho", "960"]
    falla = subprocess.run(corrida, capture_output=True, text=True)
    assert falla.returncode != 0 and "precio" in falla.stderr and not mp4.exists()
    pasa = subprocess.run(corrida + ["--sin-verificar"], capture_output=True, text=True)
    assert pasa.returncode == 0, pasa.stderr
    assert mp4.exists()


def test_el_cli_de_verificar_sale_con_1_y_lista_los_hallazgos(tmp_path):
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"tipo": "presentacion", "titulo": {"texto": "Hola"},
                                "puntos": [{"texto": "Uno", "cue": 0.5}], "duracion": 2}))
    ok = subprocess.run([sys.executable, str(SCRIPTS / "verificar.py"), str(spec)], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "sin hallazgos" in ok.stdout
    brand = tmp_path / "brand.json"
    brand.write_text(json.dumps({"colores": {"texto": "#2A2D33"}}))   # texto casi del color del fondo
    mal = subprocess.run([sys.executable, str(SCRIPTS / "verificar.py"), str(spec), "--brand", str(brand)],
                         capture_output=True, text=True)
    assert mal.returncode == 1
    assert "contraste" in mal.stdout and "s.json" in mal.stdout
