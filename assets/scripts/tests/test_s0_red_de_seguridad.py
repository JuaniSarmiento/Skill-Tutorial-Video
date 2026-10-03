"""S0: red de seguridad. Congela la salida de editar.py tal como queda al final del Hito 1,
antes de tocar nada del Hito 2 (docs/explicador/HITO2.md).

R-0.1 decide cómo se define G3. Medido a mano antes de escribir este test (dos renders
seguidos de `explicador-interes-compuesto.json` y de un guion mixto tipo v01, con voz y
palabras sintéticas): el framemd5 de video y el md5 de audio salen IDÉNTICOS entre las dos
corridas, para los dos guiones. Por eso G3 queda "framemd5 y md5 de audio idénticos" (no hace
falta pasar a PSNR >= 50 dB).

R-0.2 versiona esa base en tests/fixtures/s0/*.json (chica: dos hashes por guion, no videos) y
cada render futuro se compara contra ella: es un test de caracterización, pasa hoy por
construcción porque la base se grabó con este mismo render.
"""
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("playwright")
import editar  # noqa: E402
import palabras  # noqa: E402

pytestmark = pytest.mark.integracion

FIXTURES = Path(__file__).parent / "fixtures" / "s0"
GUION_EJEMPLO = Path(__file__).resolve().parents[2] / "guion-ejemplo" / "explicador-interes-compuesto.json"

GUION_ESCENAS = json.loads(GUION_EJEMPLO.read_text())

# "tipo v01": tarjeta de título + pantalla grabada + una escena + pantalla otra vez, como el
# mix de test_editar_e2e.py pero cubriendo también el segmento "titulo".
GUION_MIXTO = {"raw": "raw/v09.mp4", "segmentos": [
    {"tipo": "titulo", "titulo": "Capítulo uno", "subtitulo": "La base", "texto": "Bienvenidos."},
    {"inicio": 0, "fin": 2, "texto": "Esto es la pantalla."},
    {"escena": {"tipo": "presentacion", "titulo": {"texto": "Hola"},
                "puntos": [{"texto": "Sol", "cue": "el sol"}]}, "texto": "Mira el sol."},
    {"inicio": 2, "fin": 4, "texto": "Y esto es otra vez pantalla."},
]}

GUIONES = [("escenas", GUION_ESCENAS), ("mixto", GUION_MIXTO)]


def _palabras_de(texto: str, paso: float = 0.3) -> list[dict]:
    """Palabras falsas con tiempos crecientes, al estilo de test_palabras.py (_oido)."""
    return [{"palabra": w, "inicio": i * paso, "fin": i * paso + 0.25} for i, w in enumerate(texto.split())]


def _framemd5(mp4: Path) -> str:
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-map", "0:v", "-f", "framemd5", "-"],
                         capture_output=True, check=True).stdout
    return hashlib.sha256(out).hexdigest()


def _audio_md5(mp4: Path) -> str:
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-map", "0:a", "-f", "md5", "-"],
                         capture_output=True, check=True).stdout
    return out.decode().strip()


def _renderizar(dest: Path, guion: dict, monkeypatch, vid: str = "v09", voz_name: str = "juani") -> Path:
    """Arma final-<voz>.mp4 de `guion` en `dest`, con voz y palabras sintéticas (sin red, sin Whisper)."""
    monkeypatch.setattr(editar, "ROOT", dest)
    (dest / "guion").mkdir(parents=True)
    (dest / "guion" / f"{vid}.json").write_text(json.dumps(guion, ensure_ascii=False))
    if guion.get("raw"):
        (dest / "raw").mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=1920x1080:r=30:d=6",
                        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                        str(dest / guion["raw"])], check=True)
    textos = [s["texto"] for s in guion["segmentos"]]
    voces = dest / "videos" / vid / voz_name
    voces.mkdir(parents=True)
    for i in range(len(textos)):
        # Duraciones enteras: ffmpeg 6.1.1 cuelga con -af atempo=1.0000 para algunas
        # duraciones no enteras (p.ej. 1.3s, bug del filtro atempo/WSOLA, no es de esta skill).
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=f=300:d={2 + i}",
                        str(voces / f"{i:02d}.wav")], check=True)
    por_idx = {i: _palabras_de(t) for i, t in enumerate(textos)}
    monkeypatch.setattr(palabras, "transcribir", lambda wav, modelo=None: por_idx[int(Path(wav).stem)])

    editar.imagen(vid, voz_name)
    editar.voz(vid, voz_name)
    return dest / "videos" / vid / f"final-{voz_name}.mp4"


@pytest.mark.parametrize("nombre, guion", GUIONES)
def test_dos_renders_seguidos_dan_el_mismo_hash(tmp_path, monkeypatch, nombre, guion):
    """R-0.1: si esto deja de cumplirse, G3 pasa a ser PSNR >= 50 dB por cuadro + G1 + G2."""
    mp4_1 = _renderizar(tmp_path / "r1", guion, monkeypatch)
    mp4_2 = _renderizar(tmp_path / "r2", guion, monkeypatch)

    assert _framemd5(mp4_1) == _framemd5(mp4_2)
    assert _audio_md5(mp4_1) == _audio_md5(mp4_2)


@pytest.mark.parametrize("nombre, guion", GUIONES)
def test_el_render_coincide_con_la_base_congelada_del_hito_1(tmp_path, monkeypatch, nombre, guion):
    """R-0.2: test de caracterización, pasa hoy por construcción (la base es este mismo render)."""
    base = json.loads((FIXTURES / f"{nombre}.json").read_text())
    mp4 = _renderizar(tmp_path, guion, monkeypatch)

    assert _framemd5(mp4) == base["framemd5"]
    assert _audio_md5(mp4) == base["audio_md5"]
