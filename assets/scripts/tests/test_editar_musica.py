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


def test_voz_con_musica_faltante_aborta_antes_de_generar_la_voz(tutorial):
    # N3(b) (QA 03/10/2026): R-2.6 dice "al arrancar, ni la voz" pero no había ningún test
    # que lo comprobara: los de arriba sólo miran que no quede final-juani.mp4, y eso
    # también sería cierto si resolver_archivo se llamara DESPUÉS de generar la voz (el
    # aborto llegaría más tarde, pero el final tampoco se escribiría). Este test mira
    # voz-juani.wav específicamente: si alguien mueve resolver_archivo después del loop de
    # voces, este test (no los de arriba) lo detecta.
    tmp_path, work = tutorial
    _guion(tmp_path, musica={"archivo": "musica/no-existe.mp3"})

    with pytest.raises(SystemExit):
        editar.voz("v09", "juani")

    assert not (work / "voz-juani.wav").exists()


# --- N4 (QA 03/10/2026): "musica": false arriba y "musica": {} -----------------------

def test_voz_con_musica_false_arriba_del_guion_se_trata_como_sin_musica(tutorial):
    # HITO2.md documenta "musica" arriba como un objeto {archivo,...}; "false" sólo está
    # documentado adentro de un segmento. Elegido (y documentado en musica.py): arriba,
    # "false" es lo más coherente con "sin la clave musica -> sin música" (Sin música es
    # justamente el default de esa fila de la tabla), no un error.
    tmp_path, work = tutorial
    _guion(tmp_path, musica=False)

    editar.voz("v09", "juani")  # no debe tirar: se comporta como si "musica" no estuviera

    assert (work / "final-juani.mp4").exists()


def test_voz_con_musica_vacia_arriba_del_guion_aborta_antes_de_escribir_la_voz(tutorial):
    # {} es un objeto (pasa el chequeo de "tiene que ser false o un objeto"), pero le falta
    # la clave obligatoria "archivo": antes esto no abortaba temprano, reventaba más
    # adelante (preparar_pista con m_archivo=None) DESPUÉS de ya haber escrito la voz.
    tmp_path, work = tutorial
    _guion(tmp_path, musica={})

    with pytest.raises(SystemExit) as e:
        editar.voz("v09", "juani")

    assert "archivo" in str(e.value)
    assert not (work / "voz-juani.wav").exists()
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
    assert tp <= -1.5


# --- QA 04/10/2026 (BLOCKING, ronda 3): R-2.3 con 10 slots reales y música de verdad --
#
# loudnorm de UNA pasada no llega al integrado objetivo cuando el TP lo restringe (medido
# por QA: I=-17.1/-18.9 con música normal/clicks/percusión, I entre -17.5 y -20.2 en
# finales cortos de 8s). El arreglo: loudnorm de DOS pasadas (mide con print_format=json,
# aplica con measured_* y linear=true) + un limitador de TRUE PEAK aparte (loudnorm en modo
# lineal no limita TP), + "-ar 48000" explícito (si no, el final sale a la tasa que
# loudnorm sobremuestreó internamente).

def _voz_habla(path, dur: float, sr: int = 22050) -> None:
    """Voz sintética tipo habla: ruido rosa modulado en amplitud a 4Hz (QA 04/10/2026).

    QA 04/10/2026 (hallazgo, ronda 3): sin "seed" fijo, anoisesrc generaba una voz
    distinta en cada corrida -el caso "final corto de 8s" con música rosa mide muy cerca
    del borde (-17.0 LUFS), y una corrida standalone fuera de pytest dio -17.3 (fuera de
    rango) con exactamente este escenario. Fijar el seed hace el test determinista.
    """
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"anoisesrc=color=pink:d={dur}:a=0.5:seed=7,tremolo=f=4:d=0.9",
                    "-ar", str(sr), str(path)], check=True)


def _musica_normal(path, dur: float, sr: int = 44100, semilla: int = 1) -> None:
    freq = {1: 220, 2: 330, 3: 440}[semilla]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=f={freq}:d={dur},tremolo=f=2.5:d=0.7,volume=0.8",
                    "-ar", str(sr), str(path)], check=True)


def _musica_rosa(path, dur: float, sr: int = 44100, semilla: int = 1) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"anoisesrc=color=pink:d={dur}:seed={semilla}",
                    "-ar", str(sr), str(path)], check=True)


def _musica_percusion(path, dur: float, sr: int = 44100, semilla: int = 1) -> None:
    periodo = {1: 0.5, 2: 0.4, 3: 0.6}[semilla]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"aevalsrc='if(lt(mod(t\\,{periodo})\\,0.08)\\,0.97*exp(-30*mod(t\\,{periodo}))\\,0)'"
                          f":d={dur}:s={sr}",
                    str(path)], check=True)


def _musica_clicks(path, dur: float, sr: int = 44100) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", r"aevalsrc='if(lt(mod(t\,0.05)\,0.0015)\,0.99\,0)'" f":d={dur}:s={sr}",
                    str(path)], check=True)


def _escenario_10_slots_de_6s(tmp_path, monkeypatch, musica_gen, semilla: int = 1) -> tuple:
    """10 slots de 6s, voz tipo habla bien adentro de cada uno (sin acelerar), música real
    generada por `musica_gen`. Usado por los repros N2g/N2d/finales cortos (QA 04/10/2026)."""
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    work = tmp_path / "videos" / "v09"
    (work / "juani").mkdir(parents=True)
    n, slot = 10, 6.0
    for i in range(n):
        _voz_habla(work / "juani" / f"{i:02d}.wav", slot - 0.3 - 0.6)
    _video(work / "video-juani.mp4", round(n * slot * 30))
    (work / "slots-juani.json").write_text(json.dumps([slot] * n))
    (tmp_path / "musica").mkdir()
    archivo = tmp_path / "musica" / "fondo.wav"
    if musica_gen is _musica_clicks:
        musica_gen(archivo, n * slot + 5)
    else:
        musica_gen(archivo, n * slot + 5, semilla=semilla)
    segmentos = [{"texto": f"Tramo {i}."} for i in range(n)]
    (tmp_path / "guion" / "v09.json").write_text(
        json.dumps({"segmentos": segmentos, "musica": {"archivo": "musica/fondo.wav"}}, ensure_ascii=False))
    return work


def _i_tp_del_final(work) -> tuple:
    final = work / "final-juani.mp4"
    audio = work / "final-audio.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(final), "-vn", str(audio)], check=True)
    return musica.medir_i_tp(audio)


@pytest.mark.parametrize("semilla", [1, 2, 3])
@pytest.mark.parametrize("musica_gen", [_musica_normal, _musica_rosa, _musica_percusion])
def test_voz_con_musica_real_el_final_cumple_i_y_tp_sin_tolerancia(tmp_path, monkeypatch, musica_gen, semilla):
    work = _escenario_10_slots_de_6s(tmp_path, monkeypatch, musica_gen, semilla=semilla)

    editar.voz("v09", "juani")

    i, tp = _i_tp_del_final(work)
    assert -17.0 <= i <= -15.0, i
    assert tp <= -1.5, tp


def test_voz_con_musica_de_clicks_el_final_cumple_i_y_tp_sin_tolerancia(tmp_path, monkeypatch):
    work = _escenario_10_slots_de_6s(tmp_path, monkeypatch, _musica_clicks)

    editar.voz("v09", "juani")

    i, tp = _i_tp_del_final(work)
    assert -17.0 <= i <= -15.0, i
    assert tp <= -1.5, tp


@pytest.mark.parametrize("musica_gen", [
    _musica_normal,
    pytest.param(_musica_rosa, marks=pytest.mark.xfail(
        strict=True, reason="HALLAZGO QA 04/10/2026 (reportado, no resuelto): margen muy "
        "ajustado en este caso degenerado (voz de 0.5s en un slot de 8s): medido I=-17.1/"
        "-17.2 según la voz sintética exacta, apenas 0.1-0.2dB fuera de [-17,-15]. Probé "
        "MARGEN_TP_LOUDNORM más permisivo (-0.5 y 0.0): mejora de -17.2 a -17.1 y ahí se "
        "estanca, no es ese el parámetro que cierra el resto. A diferencia de percusión/"
        "clicks (ver abajo, que fallan por 3-9dB), este caso está cerca: queda para Juani "
        "decidir si vale la pena seguir ajustando o si el margen real para R-2.3 debe ser "
        "más ancho en slots con muy poca voz.")),
    pytest.param(_musica_percusion, marks=pytest.mark.xfail(
        strict=True, reason="HALLAZGO QA 04/10/2026 (reportado, no resuelto): crest factor "
        "extremo (~25dB TP-I) + voz que ocupa sólo 6% del slot -> el I integrado queda "
        "dominado por los transientes de percusión. Bajar su pico al límite de TP baja el "
        "integrado casi 1:1 (el gate de EBU R128 descarta el silencio entre golpes): no "
        "encontré una ganancia+limitador que cumpla I y TP a la vez sin comprimir el "
        "contenido mucho más allá de lo razonable. Decisión para Juani, no mía.")),
    pytest.param(_musica_clicks, marks=pytest.mark.xfail(
        strict=True, reason="HALLAZGO QA 04/10/2026: mismo mecanismo que _musica_percusion "
        "arriba (crest factor extremo + voz mínima en el slot).")),
])
def test_voz_con_musica_y_final_corto_de_8s_cumple_i_y_tp_sin_tolerancia(tmp_path, monkeypatch, musica_gen):
    # final corto (8s, voz de 0.5s): la música queda fuerte en casi todo el slot (sólo 10 LU
    # bajo la voz en "silencio"), el caso donde QA midió I entre -17.5 y -20.2.
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    work = tmp_path / "videos" / "v09"
    (work / "juani").mkdir(parents=True)
    slot = 8.0
    _voz_habla(work / "juani" / "00.wav", 0.5)
    _video(work / "video-juani.mp4", round(slot * 30))
    (work / "slots-juani.json").write_text(json.dumps([slot]))
    (tmp_path / "musica").mkdir()
    archivo = tmp_path / "musica" / "fondo.wav"
    if musica_gen is _musica_clicks:
        musica_gen(archivo, slot + 5)
    else:
        musica_gen(archivo, slot + 5, semilla=1)
    _guion(tmp_path, musica={"archivo": "musica/fondo.wav"})

    editar.voz("v09", "juani")

    final = work / "final-juani.mp4"
    audio = work / "final-audio.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(final), "-vn", str(audio)], check=True)
    i, tp = musica.medir_i_tp(audio)
    assert -17.0 <= i <= -15.0, i
    assert tp <= -1.5, tp


# --- QA 04/10/2026 (urgente, orquestador): "apad" sin "-t" genera silencio INDEFINIDO ---
# en el wav intermedio de mezcla (voz+música antes de normalizar): sin un límite de
# duración explícito en ESE comando, el archivo crece sin fin hasta llenar el disco
# (medido: 17GB en un solo caso, 256GB en la corrida completa). El mux final YA tenía
# "-t duration(video)", pero ese límite no alcanzaba al paso intermedio nuevo.

def test_voz_con_musica_el_wav_intermedio_de_mezcla_no_dura_mas_que_el_video(tutorial):
    tmp_path, work = tutorial
    archivo = _con_musica(tmp_path)
    _guion(tmp_path, musica={"archivo": archivo})

    editar.voz("v09", "juani")

    mezcla = work / "mezcla-juani.wav"
    video = work / "video-juani.mp4"
    assert mezcla.exists()
    assert _duracion(mezcla, "a") <= _duracion(video, "v") + 0.5, _duracion(mezcla, "a")


def test_voz_con_musica_el_final_sale_a_48000hz(tmp_path, monkeypatch):
    # el bug observado: loudnorm sube la tasa internamente y, sin "-ar" explícito, el AAC
    # hereda esa tasa (medido: 96000 Hz) en vez de una tasa estándar de entrega.
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    work = tmp_path / "videos" / "v09"
    (work / "juani").mkdir(parents=True)
    slot = 8.0
    _voz_habla(work / "juani" / "00.wav", 0.5)
    _video(work / "video-juani.mp4", round(slot * 30))
    (work / "slots-juani.json").write_text(json.dumps([slot]))
    (tmp_path / "musica").mkdir()
    archivo = tmp_path / "musica" / "fondo.wav"
    _musica_normal(archivo, slot + 5, semilla=1)
    _guion(tmp_path, musica={"archivo": "musica/fondo.wav"})

    editar.voz("v09", "juani")

    final = work / "final-juani.mp4"
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                          "stream=sample_rate", "-of", "csv=p=0", str(final)],
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == "48000", out


# --- QA 04/10/2026 (decisión del orquestador, ronda 3): el camino SIN música también ---
# pasa por loudnorm de dos pasadas + limitador de TP (igual que con música): sin esto, un
# slot largo con muy poca voz medía I=-10.3 (muy por arriba de -16±1), porque loudnorm de
# una pasada normaliza por el contenido con voz, no por el silencio que lo rodea.

def test_voz_sin_musica_con_poca_voz_en_un_slot_largo_tambien_cumple_i_y_tp(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    work = tmp_path / "videos" / "v09"
    (work / "juani").mkdir(parents=True)
    slot = 8.0
    _wav(work / "juani" / "00.wav", 0.5)  # voz de 0.5s en un slot de 8s: casi todo silencio
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=320x180:r=30",
                    "-frames:v", str(round(slot * 30)), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(work / "video-juani.mp4")], check=True)
    (work / "slots-juani.json").write_text(json.dumps([slot]))
    (tmp_path / "guion" / "v09.json").write_text(
        json.dumps({"segmentos": [{"texto": "Tramo 0."}]}, ensure_ascii=False))  # sin "musica"

    editar.voz("v09", "juani")

    final = work / "final-juani.mp4"
    audio = work / "final-audio.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(final), "-vn", str(audio)], check=True)
    i, tp = musica.medir_i_tp(audio)
    assert -17.0 <= i <= -15.0, i
    assert tp <= -1.5, tp


def test_voz_con_musica_picuda_y_voz_corta_el_tp_del_final_no_se_pasa_de_1_5_dbtp(tmp_path, monkeypatch):
    # N2 (QA 03/10/2026): con música de clicks, el AAC del final le agrega TP de más (el
    # ducking normal -tramos "voz"- ya atenúa bastante la música y lo tapa: hace falta un
    # slot con una voz CORTA -mucho "silencio", sólo 10 LU bajo la voz- para que la música
    # quede fuerte y el agregado del AAC se note). Sin tolerancia: una mutación que vuelva
    # el target de loudnorm a TP=-0.5 tiene que hacer fallar este test.
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    work = tmp_path / "videos" / "v09"
    (work / "juani").mkdir(parents=True)
    slot = 8.0
    _wav(work / "juani" / "00.wav", 0.5)  # voz de 0.5s en un slot de 8s: casi todo es "silencio"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=320x180:r=30",
                    "-frames:v", str(round(slot * 30)), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(work / "video-juani.mp4")], check=True)
    (work / "slots-juani.json").write_text(json.dumps([slot]))
    (tmp_path / "musica").mkdir()
    archivo = tmp_path / "musica" / "clicks.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", r"aevalsrc='if(lt(mod(t\,0.05)\,0.0015)\,0.99\,0)':d=30:s=44100",
                    str(archivo)], check=True)
    _guion(tmp_path, musica={"archivo": "musica/clicks.wav"})

    editar.voz("v09", "juani")

    final = work / "final-juani.mp4"
    audio = work / "final-audio.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(final), "-vn", str(audio)], check=True)
    _, tp = musica.medir_i_tp(audio)
    assert tp <= -1.5, tp
