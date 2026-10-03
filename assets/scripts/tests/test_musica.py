"""musica.py: música de fondo con ducking bajo la voz (S2, docs/explicador/HITO2.md).

R-2.6: archivo faltante o ilegible aborta antes de tocar nada, con la ruta absoluta
en el mensaje.
"""
import re
import subprocess
import wave
from pathlib import Path

import pytest

import musica


def _tono(tmp_path, nombre: str, dur: float, sr: int = 22050) -> Path:
    out = Path(tmp_path) / nombre
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=f=300:d={dur}", "-ar", str(sr), "-ac", "1", str(out)], check=True)
    return out


def _rms_en(wav: Path, t: float, ventana: float = 0.02, sr: int = 22050) -> float:
    """RMS normalizado (0..1) de una ventanita de `wav` centrada en el segundo `t`."""
    import math

    with wave.open(str(wav)) as w:
        w.setpos(max(int((t - ventana / 2) * sr), 0))
        n = int(ventana * sr)
        frames = w.readframes(n)
    import array
    muestras = array.array("h")
    muestras.frombytes(frames)
    if not muestras:
        return 0.0
    return math.sqrt(sum(s * s for s in muestras) / len(muestras)) / 32768


def test_resolver_archivo_con_ruta_inexistente_aborta_con_la_ruta_absoluta(tmp_path):
    root = tmp_path
    archivo = "musica/no-existe.mp3"

    with pytest.raises(SystemExit) as e:
        musica.resolver_archivo(root, archivo)

    assert str((root / archivo).resolve()) in str(e.value)


def test_resolver_archivo_con_un_mp3_corrupto_aborta_con_la_ruta_absoluta(tmp_path):
    root = tmp_path
    (root / "musica").mkdir()
    archivo = root / "musica" / "rota.mp3"
    archivo.write_bytes(b"esto no es un mp3 valido, es texto cualquiera")

    with pytest.raises(SystemExit) as e:
        musica.resolver_archivo(root, "musica/rota.mp3")

    assert str(archivo.resolve()) in str(e.value)


def test_resolver_archivo_con_un_archivo_valido_devuelve_la_ruta_absoluta(tmp_path):
    import subprocess

    root = tmp_path
    (root / "musica").mkdir()
    archivo = root / "musica" / "ok.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "sine=f=220:d=1", str(archivo)], check=True)

    assert musica.resolver_archivo(root, "musica/ok.wav") == archivo.resolve()


# --- ventanas(): silencio/voz/mute a partir de los slots y la voz de cada segmento ----

def test_ventanas_de_un_segmento_con_lead_y_tail_da_silencio_voz_silencio():
    # slot de 3s, la voz (LEAD incluido) va de 0.3 a 2.0: antes y después es silencio.
    out = musica.ventanas(slots=[3.0], voces=[(0.3, 2.0)])

    assert out == [(0.0, 0.3, "silencio"), (0.3, 2.0, "voz"), (2.0, 3.0, "silencio")]


def test_ventanas_de_dos_segmentos_uno_mute_encadena_los_tiempos():
    # 2do segmento (musica: false) -> todo el slot queda "mute", sin tocar lo del 1ro.
    out = musica.ventanas(slots=[2.0, 1.5], voces=[(0.3, 1.8), None])

    assert out == [(0.0, 0.3, "silencio"), (0.3, 1.8, "voz"), (1.8, 2.0, "silencio"),
                   (2.0, 3.5, "mute")]


def test_ventanas_con_la_voz_ocupando_todo_el_slot_no_agrega_silencio_de_mas():
    # la voz arranca en t=0 (sin LEAD) y llena el slot entero: ni antes ni después hay silencio.
    out = musica.ventanas(slots=[1.2], voces=[(0.0, 1.2)])

    assert out == [(0.0, 1.2, "voz")]


# --- aplicar_ducking(): la ganancia por ventana, en rampa (no en escalón) -------------

def test_aplicar_ducking_deja_cada_meseta_en_la_ganancia_que_le_toca(tmp_path):
    tono = _tono(tmp_path, "tono.wav", 3.0)
    base = _rms_en(tono, 0.5)  # el sine de lavfi no sale a escala completa: medirlo, no asumirlo
    vts = [(0.0, 1.0, "silencio"), (1.0, 2.0, "voz"), (2.0, 3.0, "silencio")]
    out = tmp_path / "out.wav"

    musica.aplicar_ducking(tono, vts, {"silencio": 0.0, "voz": -20.0}, out, ramp=0.2)

    # meseta "silencio" (lejos de cualquier rampa): ganancia ~1.0 (0 dB) respecto de la fuente
    assert _rms_en(out, 0.5) == pytest.approx(base, rel=0.1)
    # meseta "voz": ganancia ~0.1 (-20 dB)
    assert _rms_en(out, 1.5) == pytest.approx(base * 0.1, rel=0.15)
    # vuelve a "silencio"
    assert _rms_en(out, 2.5) == pytest.approx(base, rel=0.1)


def test_aplicar_ducking_la_transicion_es_rampa_no_escalon(tmp_path):
    tono = _tono(tmp_path, "tono.wav", 3.0)
    base = _rms_en(tono, 0.5)
    vts = [(0.0, 1.0, "silencio"), (1.0, 2.0, "voz"), (2.0, 3.0, "silencio")]
    out = tmp_path / "out.wav"

    musica.aplicar_ducking(tono, vts, {"silencio": 0.0, "voz": -20.0}, out, ramp=0.2)

    # justo en el cambio (t=1.0, mitad de la rampa de 0.2s): ni la meseta de antes ni la de
    # después, algo entre medio (si fuera escalón, caería en una de las dos puntas).
    en_el_cambio = _rms_en(out, 1.0, ventana=0.01)
    assert base * 0.15 < en_el_cambio < base * 0.85


def test_aplicar_ducking_la_rampa_progresa_de_a_poco_y_no_salta_de_golpe(tmp_path):
    # N3(a) (QA 03/10/2026): el test anterior medía con una ventana de RMS (0.01s) tan
    # ancha como la mitad de la rampa (ramp=0.2 -> r/2=0.1): esa ventana promedia un
    # escalón seco (sin rampa) con la meseta de ANTES y la de DESPUÉS y da el mismo
    # resultado "entre medio" que una rampa real, así que un escalón también la pasaba.
    # Acá se muestrean varios puntos chicos (ventana 0.005s) atravesando la rampa y se
    # pide que progresen de forma monótona SIN llegar de entrada a ninguna de las dos
    # mesetas: un escalón pondría los puntos de antes exactamente en la meseta de antes
    # y los de después exactamente en la de después, violando la monotonía estricta
    # entre ellos (todos saltan juntos en el mismo instante).
    tono = _tono(tmp_path, "tono.wav", 3.0)
    base = _rms_en(tono, 0.5)
    vts = [(0.0, 1.0, "silencio"), (1.0, 2.0, "voz"), (2.0, 3.0, "silencio")]
    out = tmp_path / "out.wav"

    musica.aplicar_ducking(tono, vts, {"silencio": 0.0, "voz": -20.0}, out, ramp=0.2)

    puntos = [_rms_en(out, 1.0 + d, ventana=0.005) for d in (-0.08, -0.04, 0.0, 0.04, 0.08)]
    # estrictamente decreciente (silencio -> voz, -20dB): cada punto más cerca de la meseta
    # de voz que el anterior, y ninguno YA en una meseta (ni en el primero ni en el último).
    for a, b in zip(puntos, puntos[1:]):
        assert a > b * 1.02, puntos  # progreso real, no una meseta repetida
    assert puntos[0] < base * 0.98, puntos      # no arrancó ya en la meseta "silencio"
    assert puntos[-1] > base * 0.1 * 1.3, puntos  # no llegó ya a la meseta "voz"


# --- B1 (QA 03/10/2026): con muchos segmentos, el evaluador de ffmpeg no puede con -------
# una expresión de if() anidados (2 niveles por transición, límite de 100 del evaluador).

def test_aplicar_ducking_con_muchos_segmentos_no_rompe_el_evaluador_de_ffmpeg(tmp_path):
    # repro de QA: con 33 segmentos de 6s (igual patrón silencio/voz/silencio que acá, con
    # slots más chicos para que el test sea rápido) la expresión anidada pasaba los 100
    # niveles que el evaluador de ffmpeg admite y fallaba con "Missing ')' or too many args".
    # Con 32 andaba: no es un límite de tamaño de archivo, es de PROFUNDIDAD de la expresión.
    n = 40
    tono = _tono(tmp_path, "tono.wav", n * 0.3)
    vts = musica.ventanas([0.3] * n, [(0.05, 0.25)] * n)
    out = tmp_path / "out.wav"

    musica.aplicar_ducking(tono, vts, {"voz": -18, "silencio": -10}, out)

    assert musica.duracion(out) == pytest.approx(n * 0.3, abs=0.2)


def test_aplicar_ducking_con_300_segmentos_tambien_funciona(tmp_path):
    # triangula B1 con un n bien por encima del límite (no alcanza con "subir el límite
    # un poco": la solución tiene que ser independiente de la cantidad de segmentos).
    import time

    n = 300
    tono = _tono(tmp_path, "tono.wav", n * 0.3)
    vts = musica.ventanas([0.3] * n, [(0.05, 0.25)] * n)
    out = tmp_path / "out.wav"

    inicio = time.monotonic()
    musica.aplicar_ducking(tono, vts, {"voz": -18, "silencio": -10}, out)
    tardo = time.monotonic() - inicio

    assert musica.duracion(out) == pytest.approx(n * 0.3, abs=0.2)
    assert tardo < 60, f"tardó {tardo:.1f}s con 300 segmentos"


# --- preparar_pista(): dura exactamente `total`, en bucle o recortada con fundido -----

def test_preparar_pista_mas_corta_que_el_total_hace_bucle(tmp_path):
    corta = _tono(tmp_path, "corta.wav", 1.0)
    out = tmp_path / "pista.wav"

    musica.preparar_pista(corta, total=3.2, fundido=2.0, out=out)

    assert musica.duracion(out) == pytest.approx(3.2, abs=0.05)


def test_preparar_pista_mas_larga_que_el_total_recorta_con_fundido(tmp_path):
    larga = _tono(tmp_path, "larga.wav", 5.0)
    out = tmp_path / "pista.wav"

    musica.preparar_pista(larga, total=2.0, fundido=1.0, out=out)

    assert musica.duracion(out) == pytest.approx(2.0, abs=0.05)
    # el fundido de salida tiene que bajar el volumen antes del final, no cortarlo seco
    base = _rms_en(larga, 0.5)
    assert _rms_en(out, 1.9, ventana=0.02) < base * 0.5


# --- loudness_integrada(): I (LUFS), vía ebur128 ---------------------------------------

def test_loudness_integrada_de_un_tono_mas_fuerte_es_mayor(tmp_path):
    bajo = _tono(tmp_path, "bajo.wav", 2.0)
    alto = tmp_path / "alto.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(bajo), "-af", "volume=10dB", str(alto)],
                   check=True)

    assert musica.loudness_integrada(alto) > musica.loudness_integrada(bajo) + 5


def test_loudness_integrada_con_10db_mas_de_ganancia_mide_casi_10_lu_mas(tmp_path):
    base = _tono(tmp_path, "base.wav", 2.0)
    mas_fuerte = tmp_path / "mas.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(base), "-af", "volume=10dB", str(mas_fuerte)],
                   check=True)

    diff = musica.loudness_integrada(mas_fuerte) - musica.loudness_integrada(base)
    assert diff == pytest.approx(10.0, abs=1.0)


# --- medir_i_tp(): (I, TP) de un archivo, para R-2.3 y para medir el ejemplo final ----

def test_medir_i_tp_de_un_tono_a_0db_da_el_pico_cerca_de_0_dbtp(tmp_path):
    tono = _tono(tmp_path, "tono.wav", 1.0)

    i, tp = musica.medir_i_tp(tono)

    assert i == pytest.approx(musica.loudness_integrada(tono), abs=0.1)
    assert -25.0 < tp <= 0.2  # el sine de lavfi no sale a escala completa (medido: ~-18 dBFS)


def test_medir_i_tp_con_menos_ganancia_da_un_pico_mas_bajo(tmp_path):
    tono = _tono(tmp_path, "tono.wav", 1.0)
    bajito = tmp_path / "bajito.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tono), "-af", "volume=-20dB",
                    str(bajito)], check=True)

    _, tp_bajito = musica.medir_i_tp(bajito)
    _, tp_tono = musica.medir_i_tp(tono)

    assert tp_bajito < tp_tono - 15


# --- construir_pista(): la pista final, atenuada relativa a la voz medida (R-2.2) ------

def _loudness_en(wav: Path, inicio: float, fin: float) -> float:
    """Loudness integrado de sólo el tramo [inicio, fin) de `wav`."""
    recorte = wav.with_name(f"{wav.stem}.recorte.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ss", str(inicio),
                    "-to", str(fin), str(recorte)], check=True)
    return musica.loudness_integrada(recorte)


def test_construir_pista_en_tramos_con_voz_queda_al_menos_15_lu_por_debajo(tmp_path):
    voz = _tono(tmp_path, "voz.wav", 3.0)  # sirve de "voz" sintética para medir contra ella
    cruda = _tono(tmp_path, "musica-cruda.wav", 3.0, sr=44100)
    vts = [(0.0, 0.3, "silencio"), (0.3, 2.7, "voz"), (2.7, 3.0, "silencio")]
    out = tmp_path / "musica-juani.wav"

    musica.construir_pista(voz, cruda, vts, debajo_de_la_voz_lu=18, out=out)

    v_loudness = musica.loudness_integrada(voz)
    m_loudness_voz = _loudness_en(out, 0.5, 2.5)  # bien adentro de la meseta "voz"

    assert m_loudness_voz <= v_loudness - 15
    assert m_loudness_voz == pytest.approx(v_loudness - 18, abs=1.5)


def test_construir_pista_separa_al_menos_15_lu_en_cada_tramo_aunque_la_voz_cambie_de_volumen(tmp_path):
    # N1 (QA 03/10/2026): construir_pista medía el loudness de TODA la voz de una sola vez;
    # con 15 LU de diferencia entre dos mitades, la mitad floja quedaba a sólo ~3 LU de la
    # música (bien por debajo del piso de R-2.2) porque la ganancia salía del promedio, no
    # del loudness de CADA tramo.
    def _ruido(nombre, dur, ganancia_db):
        out = tmp_path / nombre
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", f"anoisesrc=color=pink:a=0.3:d={dur}", "-af", f"volume={ganancia_db}dB",
                        "-ar", "44100", str(out)], check=True)
        return out

    floja = _ruido("vozA.wav", 6.0, -12)
    fuerte = _ruido("vozB.wav", 6.0, 3)
    voz = tmp_path / "voz.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(floja), "-i", str(fuerte),
                    "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1", str(voz)], check=True)
    cruda = tmp_path / "musica-cruda.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "anoisesrc=color=pink:d=12", "-ar", "44100", str(cruda)], check=True)
    vts = [(0.0, 6.0, "voz"), (6.0, 12.0, "voz")]
    out = tmp_path / "musica-juani.wav"

    musica.construir_pista(voz, cruda, vts, debajo_de_la_voz_lu=18, out=out)

    voz_floja_lu = _loudness_en(voz, 0.0, 6.0)
    voz_fuerte_lu = _loudness_en(voz, 6.0, 12.0)
    m_floja_lu = _loudness_en(out, 0.0, 6.0)
    m_fuerte_lu = _loudness_en(out, 6.0, 12.0)

    assert voz_floja_lu - m_floja_lu >= 15, (voz_floja_lu, m_floja_lu)
    assert voz_fuerte_lu - m_fuerte_lu >= 15, (voz_fuerte_lu, m_fuerte_lu)


def test_construir_pista_en_silencios_queda_mas_arriba_que_en_tramos_con_voz(tmp_path):
    voz = _tono(tmp_path, "voz.wav", 4.0)
    cruda = _tono(tmp_path, "musica-cruda.wav", 4.0, sr=44100)
    # ventanas largas (ebur128 necesita >= ~0.4s de meseta real para no caer en el piso
    # de compuerta de -70 LUFS por falta de bloques válidos).
    vts = [(0.0, 1.5, "silencio"), (1.5, 4.0, "voz")]
    out = tmp_path / "musica-juani.wav"

    musica.construir_pista(voz, cruda, vts, debajo_de_la_voz_lu=18, out=out)

    m_loudness_silencio = _loudness_en(out, 0.3, 1.2)
    m_loudness_voz = _loudness_en(out, 1.8, 3.7)
    assert m_loudness_silencio > m_loudness_voz


def _dbfs_pico_en(wav: Path, inicio: float, fin: float) -> float:
    recorte = wav.with_name(f"{wav.stem}.recorte2.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ss", str(inicio),
                    "-to", str(fin), str(recorte)], check=True)
    out = subprocess.run(["ffmpeg", "-i", str(recorte), "-af", "astats=metadata=0:reset=1",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"Peak level dB:\s*(-inf|-?\d+\.?\d*)", out)
    return float("-inf") if m.group(1) == "-inf" else float(m.group(1))


def test_construir_pista_en_un_segmento_con_musica_false_queda_por_debajo_de_60dbfs(tmp_path):
    voz = _tono(tmp_path, "voz.wav", 3.0)
    cruda = _tono(tmp_path, "musica-cruda.wav", 3.0, sr=44100)
    vts = [(0.0, 0.3, "silencio"), (0.3, 2.0, "voz"), (2.0, 3.0, "mute")]
    out = tmp_path / "musica-juani.wav"

    musica.construir_pista(voz, cruda, vts, debajo_de_la_voz_lu=18, out=out)

    assert _dbfs_pico_en(out, 2.2, 2.8) < -60
