"""Efectos de sonido (sfx.py, S3 del Hito 2, docs/explicador/HITO2.md).

Decisión Q1: sin licencia. Los sfx se generan con ffmpeg (lavfi): un set chico y
reproducible ("pop", "whoosh", "click", "ding"). El guion también puede referir un
archivo propio por ruta relativa a TUT_ROOT; si falta, aborta igual que la música
(ruta absoluta en el mensaje, antes de generar nada).
"""
import array
import subprocess
import wave

import pytest

import sfx

UMBRAL_BORDE = 500  # sobre 32767: silencio de sobra para decir "sin click" (ver _bordes)


def _muestras(path) -> array.array:
    with wave.open(str(path)) as w:
        datos = w.readframes(w.getnframes())
    m = array.array("h")
    m.frombytes(datos)
    return m


def _bordes(path, n: int = 50) -> tuple[int, int]:
    """Máximo |muestra| en los primeros y los últimos `n` samples."""
    m = _muestras(path)
    return max(abs(x) for x in m[:n]), max(abs(x) for x in m[-n:])


# --- un sonido conocido se genera con ffmpeg, cacheado, con fundidos ------------------

def test_resolver_un_sonido_conocido_genera_un_wav_con_fundidos_sin_click_de_borde(tmp_path):
    cache = tmp_path / "sfx"

    ruta = sfx.resolver_archivo(tmp_path, "pop", cache)

    assert ruta.exists()
    inicio, fin = _bordes(ruta)
    assert inicio < UMBRAL_BORDE, inicio
    assert fin < UMBRAL_BORDE, fin


def test_resolver_un_sonido_conocido_lo_cachea_y_no_lo_regenera(tmp_path, monkeypatch):
    cache = tmp_path / "sfx"
    ruta = sfx.resolver_archivo(tmp_path, "pop", cache)
    llamado = []
    monkeypatch.setattr(sfx, "_generar", lambda nombre, out: llamado.append(nombre))

    ruta2 = sfx.resolver_archivo(tmp_path, "pop", cache)

    assert ruta2 == ruta
    assert llamado == []


# --- triangulación: otro sonido conocido, con otra duración y otro timbre -------------

def test_resolver_otro_sonido_conocido_da_un_archivo_distinto_y_tambien_sin_click(tmp_path):
    cache = tmp_path / "sfx"

    pop = sfx.resolver_archivo(tmp_path, "pop", cache)
    ding = sfx.resolver_archivo(tmp_path, "ding", cache)

    assert pop != ding
    inicio, fin = _bordes(ding)
    assert inicio < UMBRAL_BORDE, inicio
    assert fin < UMBRAL_BORDE, fin


# --- una ruta propia se resuelve relativa a TUT_ROOT, sin generar nada ----------------

def test_resolver_un_archivo_propio_existente_no_lo_genera_y_devuelve_su_ruta_absoluta(tmp_path):
    cache = tmp_path / "sfx"
    propio = tmp_path / "mis-sfx" / "campana.wav"
    propio.parent.mkdir()
    propio.write_bytes(b"RIFF....WAVEfmt ")  # el contenido no importa: no se abre

    ruta = sfx.resolver_archivo(tmp_path, "mis-sfx/campana.wav", cache)

    assert ruta == propio.resolve()
    assert not cache.exists()


# --- archivo propio faltante: aborta igual que la música, con la ruta absoluta --------

def test_resolver_un_archivo_propio_faltante_aborta_con_su_ruta_absoluta(tmp_path):
    cache = tmp_path / "sfx"

    with pytest.raises(SystemExit) as e:
        sfx.resolver_archivo(tmp_path, "mis-sfx/no-existe.wav", cache)

    assert str((tmp_path / "mis-sfx/no-existe.wav").resolve()) in str(e.value)


# --- construir_pista: una pista mono de la duración pedida, con cada efecto en su t --

def _duracion(path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout)


def _pico_en(path, inicio: float, fin: float, sr: int = 44100) -> int:
    """Máximo |muestra| de `path` entre `inicio` y `fin` segundos."""
    m = _muestras(path)
    a, b = int(inicio * sr), int(fin * sr)
    tramo = m[a:b]
    return max((abs(x) for x in tramo), default=0)


def test_construir_pista_sin_efectos_da_silencio_de_la_duracion_pedida(tmp_path):
    out = tmp_path / "pista.wav"

    sfx.construir_pista(1.5, [], out)

    assert _duracion(out) == pytest.approx(1.5, abs=0.05)
    assert _pico_en(out, 0, 1.5) == 0


def test_construir_pista_pone_el_efecto_en_el_t_pedido_y_no_antes(tmp_path):
    cache = tmp_path / "sfx"
    pop = sfx.resolver_archivo(tmp_path, "pop", cache)
    out = tmp_path / "pista.wav"

    sfx.construir_pista(2.0, [(1.0, pop, 0.0)], out)

    assert _pico_en(out, 0.0, 0.9) == 0
    assert _pico_en(out, 1.0, 1.12) > 1000


def test_construir_pista_con_dos_efectos_en_momentos_distintos_no_se_pisan(tmp_path):
    cache = tmp_path / "sfx"
    pop = sfx.resolver_archivo(tmp_path, "pop", cache)
    ding = sfx.resolver_archivo(tmp_path, "ding", cache)
    out = tmp_path / "pista.wav"

    sfx.construir_pista(3.0, [(0.2, pop, 0.0), (2.0, ding, 0.0)], out)

    assert _pico_en(out, 0.2, 0.3) > 1000
    assert _pico_en(out, 0.5, 1.9) == 0  # entre los dos: silencio
    assert _pico_en(out, 2.0, 2.4) > 1000


def test_construir_pista_la_ganancia_db_sube_o_baja_el_efecto(tmp_path):
    cache = tmp_path / "sfx"
    pop = sfx.resolver_archivo(tmp_path, "pop", cache)
    bajo = tmp_path / "bajo.wav"
    alto = tmp_path / "alto.wav"

    sfx.construir_pista(1.0, [(0.0, pop, -20.0)], bajo)
    sfx.construir_pista(1.0, [(0.0, pop, 10.0)], alto)

    assert _pico_en(alto, 0.0, 0.12) > _pico_en(bajo, 0.0, 0.12)
