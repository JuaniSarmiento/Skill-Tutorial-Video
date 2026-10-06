"""editar.py: `velocidad_voz` acelera las voces TTS a 1.25x (Juani la escucha mejor así,
aceleración sin cambio de tono) y deja la voz grabada `juani` a 1.0x.

La aceleración es con `atempo` (no con el `speed` de Fish, que cambia la entonación: ver
references/voces.md), DESPUÉS de generar la voz como siempre y ANTES de medir el slot, así
el video se ajusta a la voz acelerada y `palabras.py` transcribe sobre esa voz (los tiempos
por palabra ya salen en la línea de tiempo acelerada, sin escalar nada).
"""
import array
import json
import math
import subprocess
import wave

import pytest

import editar


def _wav(path, dur: float, freq: float = 300, sr: int = 22050) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=f={freq}:d={dur}", "-ar", str(sr), str(path)], check=True)


def _muestras(path, inicio: float, fin: float, sr: int = 22050) -> array.array:
    pcm = path.with_name(path.stem + f".{inicio:.3f}-{fin:.3f}.pcm.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-ss", str(inicio),
                    "-to", str(fin), "-ac", "1", "-ar", str(sr), "-sample_fmt", "s16", str(pcm)], check=True)
    with wave.open(str(pcm)) as w:
        frames = w.readframes(w.getnframes())
    m = array.array("h")
    m.frombytes(frames)
    pcm.unlink()
    return m


def _rms(muestras: array.array) -> float:
    if not muestras:
        return 0.0
    return math.sqrt(sum(s * s for s in muestras) / len(muestras)) / 32768


def _frecuencia(path, inicio: float, fin: float, sr: int = 22050) -> float:
    """Frecuencia fundamental de un tono puro: cruces por cero (de - a +) por segundo."""
    m = _muestras(path, inicio, fin, sr)
    cruces = sum(1 for a, b in zip(m, m[1:]) if a < 0 <= b)
    return cruces / (fin - inicio)


# --- velocidad_voz: validación -----------------------------------------------------

@pytest.mark.parametrize("v", [0, -1, -0.5])
def test_una_velocidad_cero_o_negativa_falla_con_mensaje_claro(v):
    with pytest.raises(ValueError, match="velocidad_voz"):
        editar.validar_velocidad_voz(v)


@pytest.mark.parametrize("v", ["rapido", None, [1.25], {}])
def test_una_velocidad_no_numerica_falla_con_mensaje_claro(v):
    with pytest.raises(ValueError, match="velocidad_voz"):
        editar.validar_velocidad_voz(v)


def test_una_velocidad_valida_se_devuelve_como_float():
    assert editar.validar_velocidad_voz(1.25) == 1.25
    assert editar.validar_velocidad_voz("1.5") == 1.5


# --- default por voz: 1.25 las TTS, 1.0 la grabada ("juani") -----------------------

@pytest.mark.parametrize("voz", ["argentina", "joven", "profe", "fish", "daniela", "elevenlabs"])
def test_el_default_es_1_25_para_las_voces_tts(voz):
    assert editar.velocidad_default(voz) == 1.25


def test_el_default_es_1_0_para_la_voz_grabada_juani():
    assert editar.velocidad_default("juani") == 1.0


def test_velocidad_de_sin_la_clave_en_el_guion_usa_el_default_de_la_voz():
    assert editar.velocidad_de({}, "argentina") == 1.25
    assert editar.velocidad_de({}, "juani") == 1.0


def test_velocidad_de_con_la_clave_en_el_guion_la_pisa():
    assert editar.velocidad_de({"velocidad_voz": 1.5}, "argentina") == 1.5
    assert editar.velocidad_de({"velocidad_voz": 1.5}, "juani") == 1.5


def test_velocidad_de_valida_antes_de_devolver_nada():
    with pytest.raises(ValueError, match="velocidad_voz"):
        editar.velocidad_de({"velocidad_voz": -1}, "argentina")


# --- acelerar_voz: dura menos, el tono no cambia ------------------------------------

def test_acelerar_a_1_25_deja_la_duracion_en_el_80_por_ciento(tmp_path):
    wav = tmp_path / "voz.wav"
    _wav(wav, dur=4.0, freq=300)
    out = tmp_path / "voz-x1.25.wav"

    editar.acelerar_voz(wav, out, 1.25)

    assert editar.duration(out) == pytest.approx(4.0 / 1.25, rel=0.02)


def test_acelerar_a_2_0_deja_la_duracion_en_la_mitad(tmp_path):
    # segundo caso con datos distintos: triangula que no es una constante hardcodeada
    wav = tmp_path / "voz.wav"
    _wav(wav, dur=3.0, freq=440)
    out = tmp_path / "voz-x2.wav"

    editar.acelerar_voz(wav, out, 2.0)

    assert editar.duration(out) == pytest.approx(3.0 / 2.0, rel=0.02)


def test_acelerar_no_cambia_el_tono(tmp_path):
    wav = tmp_path / "voz.wav"
    _wav(wav, dur=4.0, freq=300)
    out = tmp_path / "voz-x1.25.wav"
    editar.acelerar_voz(wav, out, 1.25)

    dur = editar.duration(out)
    antes = _frecuencia(wav, 0.5, 3.5)
    despues = _frecuencia(out, 0.5, dur - 0.5)

    assert antes == pytest.approx(300, rel=0.03)
    assert despues == pytest.approx(300, rel=0.03)


def test_acelerar_a_otra_velocidad_tampoco_cambia_el_tono(tmp_path):
    # segundo caso: otra frecuencia y otra velocidad, para que no sea casualidad del 300 Hz/1.25x
    wav = tmp_path / "voz.wav"
    _wav(wav, dur=4.0, freq=440)
    out = tmp_path / "voz-x1.5.wav"
    editar.acelerar_voz(wav, out, 1.5)

    dur = editar.duration(out)
    despues = _frecuencia(out, 0.3, dur - 0.3)

    assert despues == pytest.approx(440, rel=0.03)


def test_con_velocidad_1_el_archivo_no_se_toca(tmp_path):
    wav = tmp_path / "voz.wav"
    _wav(wav, dur=2.0)
    out = tmp_path / "voz-x1.wav"

    editar.acelerar_voz(wav, out, 1.0)

    assert out.read_bytes() == wav.read_bytes()


# --- una marca cae en el tiempo escalado por la velocidad (cues tras acelerar) -----

def test_una_marca_cae_a_tiempo_escalado_despues_de_acelerar(tmp_path):
    # silencio, un tono de 0.3 s a los 2.0 s ("la palabra"), silencio: a 1.25x la marca
    # tiene que caer en 2.0 / 1.25 = 1.6 s, no en 2.0 s.
    partes = tmp_path / "partes.txt"
    silencio_a = tmp_path / "s1.wav"
    tono = tmp_path / "t.wav"
    silencio_b = tmp_path / "s2.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
                    "-t", "2.0", str(silencio_a)], check=True)
    _wav(tono, dur=0.3, freq=500)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
                    "-t", "1.7", str(silencio_b)], check=True)
    partes.write_text("".join(f"file '{p}'\n" for p in (silencio_a, tono, silencio_b)))
    wav = tmp_path / "voz.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(partes), "-ar", "22050", str(wav)], check=True)
    out = tmp_path / "voz-x1.25.wav"

    editar.acelerar_voz(wav, out, 1.25)

    esperado = 2.0 / 1.25
    antes = _rms(_muestras(out, max(0, esperado - 0.5), esperado - 0.05))
    marca = _rms(_muestras(out, esperado + 0.02, esperado + 0.2))
    assert antes < 0.01, "no tiene que haber nada antes de la marca"
    assert marca > antes * 5, "la marca tiene que estar donde la escala la pone"


# --- acelerar_voz_cacheada: el caché depende de la velocidad -----------------------

def test_acelerar_voz_cacheada_con_velocidad_1_devuelve_el_mismo_wav_sin_crear_nada(tmp_path):
    wav = tmp_path / "00.wav"
    _wav(wav, dur=1.0)

    out = editar.acelerar_voz_cacheada(wav, 1.0)

    assert out == wav
    assert list(tmp_path.iterdir()) == [wav]


def test_acelerar_voz_cacheada_reusa_si_no_cambio_nada(tmp_path):
    wav = tmp_path / "00.wav"
    _wav(wav, dur=2.0)

    primera = editar.acelerar_voz_cacheada(wav, 1.25)
    mtime_1 = primera.stat().st_mtime_ns
    segunda = editar.acelerar_voz_cacheada(wav, 1.25)

    assert segunda == primera
    assert segunda.stat().st_mtime_ns == mtime_1, "no se tiene que haber regenerado"


def test_un_cambio_de_velocidad_no_reusa_la_voz_vieja(tmp_path):
    wav = tmp_path / "00.wav"
    _wav(wav, dur=4.0)

    a_1_25 = editar.acelerar_voz_cacheada(wav, 1.25)
    a_1_5 = editar.acelerar_voz_cacheada(wav, 1.5)

    assert a_1_25 != a_1_5
    assert editar.duration(a_1_25) == pytest.approx(4.0 / 1.25, rel=0.02)
    assert editar.duration(a_1_5) == pytest.approx(4.0 / 1.5, rel=0.02)


def test_si_la_voz_de_origen_cambio_se_vuelve_a_acelerar(tmp_path):
    wav = tmp_path / "00.wav"
    _wav(wav, dur=2.0)
    primera = editar.acelerar_voz_cacheada(wav, 1.25)
    dur_1 = editar.duration(primera)

    _wav(wav, dur=4.0)  # el texto cambió, voice_wav regeneró el wav con el mismo nombre
    segunda = editar.acelerar_voz_cacheada(wav, 1.25)

    assert editar.duration(segunda) != pytest.approx(dur_1, rel=0.02)
    assert editar.duration(segunda) == pytest.approx(4.0 / 1.25, rel=0.02)


# --- preparar(): el slot se mide sobre la voz YA acelerada --------------------------

def test_preparar_mide_el_slot_sobre_la_voz_acelerada(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    (tmp_path / "guion" / "v09.json").write_text(json.dumps({"segmentos": [{"texto": "Hola."}]}))
    wav = tmp_path / "00.wav"
    _wav(wav, dur=4.0)
    monkeypatch.setattr(editar, "voice_wav", lambda vid, voz, i, texto: wav)

    tramos = editar.preparar("v09", "argentina")

    _, slot, _ = tramos[0]
    # sin velocidad_voz en el guion, "argentina" (TTS) usa el default 1.25: la voz de 4.0s
    # pasa a ~3.2s antes de sumar LEAD y la cola, no a los 4.0s originales
    voz_acelerada = 4.0 / 1.25
    assert slot == pytest.approx(voz_acelerada + editar.LEAD + editar._cola("argentina"), abs=0.05)


def test_preparar_respeta_velocidad_voz_1_0_para_juani_por_default(tmp_path, monkeypatch):
    # G3: la base de S0 usa "juani" sin tocar nada; esto prueba que el default no la mueve.
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    (tmp_path / "guion" / "v09.json").write_text(json.dumps({"segmentos": [{"texto": "Hola."}]}))
    voces = tmp_path / "videos" / "v09" / "juani"
    voces.mkdir(parents=True)
    _wav(voces / "00.wav", dur=4.0)

    tramos = editar.preparar("v09", "juani")

    _, slot, _ = tramos[0]
    assert slot == pytest.approx(4.0 + editar.LEAD + editar._cola("juani"), abs=0.05)
