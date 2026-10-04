"""editar.py voz: efectos de sonido sobre palabras (S3, docs/explicador/HITO2.md).

Formato del guion: en un segmento, "sfx": [{"archivo", "cue", "ganancia_db"?}]. `archivo`
es el nombre de un sonido generado (ver sfx.SONIDOS) o una ruta propia relativa a
TUT_ROOT. `cue` es texto (se resuelve igual que en las escenas, por palabras.py) o un
número de segundos CONTADO DESDE EL INICIO DEL SLOT (no desde el arranque de la voz).
Sin la clave "sfx" en ningún lado del guion, el comportamiento es el de antes del Hito 2
(no se toca ni se genera ningún archivo de sfx).
"""
import array
import json
import subprocess
import wave

import pytest

import editar
import musica
import palabras
import sfx

SLOT = 6.0  # grande: deja silencio de sobra después de una voz corta, para medir onset


def _wav_voz(path, dur: float, freq: float = 300, sr: int = 22050) -> None:
    # tono corto, no silencio digital: loudnorm necesita algo medible (measured_I=-inf
    # con silencio puro hace que ffmpeg rechace la 2da pasada, igual que en test_editar_musica.py)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=f={freq}:d={dur}", "-ar", str(sr), str(path)], check=True)


def _video(path, cuadros: int) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=320x180:r=30",
                    "-frames:v", str(cuadros), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)


def _muestras(path) -> array.array:
    pcm = path.with_name(f"{path.stem}.pcm.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1",
                    "-ar", "22050", "-sample_fmt", "s16", str(pcm)], check=True)
    with wave.open(str(pcm)) as w:
        datos = w.readframes(w.getnframes())
    m = array.array("h")
    m.frombytes(datos)
    return m


def _pico_en(path, inicio: float, fin: float, sr: int = 22050) -> int:
    m = _muestras(path)
    a, b = max(int(inicio * sr), 0), int(fin * sr)
    tramo = m[a:b]
    return max((abs(x) for x in tramo), default=0)


@pytest.fixture
def tutorial(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    work = tmp_path / "videos" / "v09"
    (work / "juani").mkdir(parents=True)
    # voz bien cortita (0.3s): deja casi todo el slot en silencio, fácil de medir
    _wav_voz(work / "juani" / "00.wav", 0.3)
    _video(work / "video-juani.mp4", round(SLOT * 30))
    (work / "slots-juani.json").write_text(json.dumps([SLOT]))
    return tmp_path, work


def _guion(tmp_path, sfx_seg=None, texto="Tramo cero."):
    seg = {"texto": texto}
    if sfx_seg is not None:
        seg["sfx"] = sfx_seg
    (tmp_path / "guion" / "v09.json").write_text(
        json.dumps({"segmentos": [seg]}, ensure_ascii=False))


# --- R-3.1: el efecto arranca en el t pedido (cue numérica, ±1 cuadro = 1/30s) --------

def test_sfx_con_cue_numerica_arranca_en_el_segundo_pedido(tutorial):
    tmp_path, work = tutorial
    _guion(tmp_path, sfx_seg=[{"archivo": "pop", "cue": 3.0}])

    editar.voz("v09", "juani")

    final = work / "final-juani.mp4"
    # 1 cuadro @30fps = 0.033s de margen
    assert _pico_en(final, 2.0, 2.95) < 1500   # antes: silencio
    assert _pico_en(final, 3.0, 3.1) > 1500    # en el cue: el pop


# --- triangulación: otro cue numérico, bien lejos del primero ------------------------

def test_sfx_con_otra_cue_numerica_arranca_en_ese_otro_segundo(tutorial):
    tmp_path, work = tutorial
    _guion(tmp_path, sfx_seg=[{"archivo": "ding", "cue": 1.0}])

    editar.voz("v09", "juani")

    final = work / "final-juani.mp4"
    # la voz (0.3s) ocupa [LEAD, LEAD+0.3] = [0.3, 0.6]: la ventana "antes" arranca
    # después de eso, para medir sólo el sfx y no la cola de la voz.
    assert _pico_en(final, 0.65, 0.95) < 1500
    assert _pico_en(final, 1.0, 1.1) > 1500


# --- R-3.2: funciona igual en tramos de pantalla, con cue de TEXTO -------------------

def test_sfx_con_cue_de_texto_en_un_tramo_de_pantalla_arranca_en_la_palabra(tutorial, monkeypatch):
    tmp_path, work = tutorial
    _guion(tmp_path, sfx_seg=[{"archivo": "pop", "cue": "base de datos"}])
    palabras_falsas = [
        {"palabra": "la", "inicio": 0.0, "fin": 0.1},
        {"palabra": "base", "inicio": 2.0, "fin": 2.3},
        {"palabra": "de", "inicio": 2.3, "fin": 2.4},
        {"palabra": "datos", "inicio": 2.4, "fin": 2.8},
    ]
    monkeypatch.setattr(palabras, "transcribir", lambda wav, modelo=None: palabras_falsas)

    editar.voz("v09", "juani")

    final = work / "final-juani.mp4"
    # LEAD=0.3 corre el audio real: la palabra "base" cae en LEAD + 2.0 = 2.3
    assert _pico_en(final, 1.0, 2.25) < 1500
    assert _pico_en(final, 2.3, 2.4) > 1500


# --- R-3.3: cue que no se dice frena nombrando segmento, sfx, cue y lo que se oyó -----

def test_sfx_con_cue_de_texto_que_no_se_dice_aborta_nombrando_el_segmento_y_lo_oido(tutorial, monkeypatch):
    tmp_path, work = tutorial
    _guion(tmp_path, sfx_seg=[{"archivo": "pop", "cue": "hipoteca"}])
    palabras_falsas = [{"palabra": "hola", "inicio": 0.0, "fin": 0.3}]
    monkeypatch.setattr(palabras, "transcribir", lambda wav, modelo=None: palabras_falsas)

    with pytest.raises(SystemExit) as e:
        editar.voz("v09", "juani")

    msg = str(e.value)
    assert "00" in msg
    assert "sfx" in msg
    assert "hipoteca" in msg
    assert "Se oyó" in msg  # reusa tal cual el mensaje de palabras.resolver_cue
    assert not (work / "final-juani.mp4").exists()


# --- R-3.4: cue numérica fuera del slot falla nombrando el segmento ------------------

def test_sfx_con_cue_numerica_fuera_del_slot_aborta_nombrando_el_segmento(tutorial):
    tmp_path, work = tutorial
    _guion(tmp_path, sfx_seg=[{"archivo": "pop", "cue": SLOT + 1.0}])

    with pytest.raises(SystemExit) as e:
        editar.voz("v09", "juani")

    assert "00" in str(e.value)
    assert not (work / "final-juani.mp4").exists()


# --- archivo de sfx faltante: igual que la música (ruta absoluta, nada escrito) -----

def test_sfx_con_archivo_propio_faltante_aborta_con_la_ruta_absoluta_y_no_escribe_nada(tutorial):
    tmp_path, work = tutorial
    _guion(tmp_path, sfx_seg=[{"archivo": "mis-sfx/no-existe.wav", "cue": 1.0}])

    with pytest.raises(SystemExit) as e:
        editar.voz("v09", "juani")

    assert str((tmp_path / "mis-sfx/no-existe.wav").resolve()) in str(e.value)
    assert not (work / "voz-juani.wav").exists()
    assert not (work / "final-juani.mp4").exists()


# --- R-3.5: con efectos se sigue cumpliendo R-2.3 (I=-16±1 LUFS, TP<=-1.5 dBTP) ------

def test_sfx_con_musica_el_final_sigue_cumpliendo_el_loudness_objetivo(tutorial):
    tmp_path, work = tutorial
    (tmp_path / "musica").mkdir()
    archivo = tmp_path / "musica" / "fondo.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=f=220:d={SLOT + 2}", "-ar", "44100", str(archivo)], check=True)
    (tmp_path / "guion" / "v09.json").write_text(json.dumps(
        {"segmentos": [{"texto": "Tramo cero.", "sfx": [{"archivo": "ding", "cue": 4.0}]}],
         "musica": {"archivo": "musica/fondo.wav"}}, ensure_ascii=False))

    editar.voz("v09", "juani")

    final = work / "final-juani.mp4"
    audio = work / "final-audio.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(final), "-vn", str(audio)], check=True)
    i, tp = musica.medir_i_tp(audio)
    assert i == pytest.approx(-16.0, abs=1.0)
    assert tp <= -1.5


# --- G: sin "sfx" en ningún lado del guion, no se toca ni se genera nada de sfx ------

def test_sin_sfx_en_el_guion_no_se_genera_ninguna_pista_de_efectos(tutorial):
    tmp_path, work = tutorial
    _guion(tmp_path, sfx_seg=None)

    editar.voz("v09", "juani")

    assert not (work / "sfx").exists()
    assert not list(work.glob("sfx-*.wav"))
