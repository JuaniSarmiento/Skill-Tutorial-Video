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


# --- N4 (QA 03/10/2026): más caminos de error que tienen que abortar al arrancar --------

def test_resolver_archivo_con_un_wav_de_0_segundos_aborta_con_la_ruta_absoluta(tmp_path):
    # duracion() no tira RuntimeError acá: ffprobe da "N/A" para format=duration de un wav
    # de 0s, y float("N/A") tira ValueError, que resolver_archivo no atrapaba (sólo
    # RuntimeError): el error se escapaba sin ruta y sin SystemExit.
    root = tmp_path
    (root / "musica").mkdir()
    archivo = root / "musica" / "vacio.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc", "-t", "0",
                    str(archivo)], check=True)

    with pytest.raises(SystemExit) as e:
        musica.resolver_archivo(root, "musica/vacio.wav")

    assert str(archivo.resolve()) in str(e.value)


def test_resolver_archivo_con_un_mp4_sin_audio_aborta_con_la_ruta_absoluta(tmp_path):
    # un mp4 sin stream de audio tiene duración de CONTENEDOR válida (ffprobe la lee bien),
    # así que duracion() no fallaba: resolver_archivo lo daba por bueno y recién reventaba
    # más adelante, al intentar procesarlo como audio (después de escribir la voz).
    root = tmp_path
    archivo = root / "video_sin_audio.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=160x90:r=10:d=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(archivo)], check=True)

    with pytest.raises(SystemExit) as e:
        musica.resolver_archivo(root, "video_sin_audio.mp4")

    assert str(archivo.resolve()) in str(e.value)


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
    # N3(a) (QA 03/10/2026): la versión original de este test medía con una ventana de RMS
    # (0.01s) tan ancha como la mitad de la rampa (ramp=0.2 -> r/2=0.1): esa ventana promedia
    # un escalón seco (sin rampa) con la meseta de ANTES y la de DESPUÉS y da el mismo
    # resultado "entre medio" que una rampa real, así que un escalón TAMBIÉN la pasaba (no
    # ejercitaba nada). Acá se muestrean varios puntos chicos (ventana 0.005s) atravesando
    # la rampa y se pide que progresen de forma monótona SIN llegar de entrada a ninguna de
    # las dos mesetas: un escalón pondría los puntos de antes exactamente en la meseta de
    # antes y los de después exactamente en la de después (todos saltan juntos), violando
    # la monotonía estricta entre ellos. Verificado a mano: con ramp=0 (escalón puro) este
    # test falla en el primer assert.
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
    # QA 04/10/2026: la rampa interpola en dB (NOTE, ronda 3), no en amplitud lineal: al
    # 80% del camino en tiempo (d=0.08 de una rampa de ancho 0.1 a cada lado) corresponde
    # al 80% del camino EN dB (-16 de los -20 totales), bastante más cerca en amplitud
    # lineal que con una interpolación lineal -eso es justo el comportamiento esperado-,
    # pero todavía no es la meseta: tiene que quedar al menos 1dB por arriba de los -20.
    db_final = _dbfs_de_rms(puntos[-1] / base)
    assert db_final > -20.0 + 1.0, (puntos, db_final)  # no llegó ya a la meseta "voz"


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


def _salto_maximo_cerca_de(wav: Path, t: float, ventana: float, sr: int = 44100) -> int:
    """Máxima diferencia absoluta entre muestras consecutivas de `wav`, en una ventana de
    `ventana` segundos centrada en el segundo `t` (para medir un click puntual)."""
    import array

    with wave.open(str(wav)) as w:
        w.setpos(max(int((t - ventana / 2) * sr), 0))
        n = int(ventana * sr)
        frames = w.readframes(n)
    m = array.array("h")
    m.frombytes(frames)
    if len(m) < 2:
        return 0
    return max(abs(m[i + 1] - m[i]) for i in range(len(m) - 1))


# --- QA 04/10/2026 (NOTE, ronda 3): el bucle con crossfade no escala -------------------
# (repro: música de 1s x total de 1200s -> 1200 acrossfade encadenados, 294s; música de
# 0.15s x total de 600s -> OSError: Argument list too long). Arreglo: una UNIDAD de bucle
# sin costura (el crossfade aplicado UNA vez, no por vuelta) + "-stream_loop" sin filtros
# por vuelta: el costo no crece con la cantidad de vueltas.

def test_preparar_pista_con_musica_de_1s_y_total_de_1800s_termina_en_tiempo_acotado(tmp_path):
    import time

    corta = _tono(tmp_path, "corta.wav", 1.0)
    out = tmp_path / "pista.wav"

    inicio = time.monotonic()
    musica.preparar_pista(corta, total=1800.0, fundido=2.0, out=out)
    tardo = time.monotonic() - inicio

    assert musica.duracion(out) == pytest.approx(1800.0, abs=0.5)
    assert tardo < 30, f"tardó {tardo:.1f}s con música de 1s x total de 1800s"


def test_preparar_pista_con_musica_muy_corta_y_total_largo_no_falla_por_argument_list_too_long(tmp_path):
    corta = _tono(tmp_path, "corta.wav", 0.5)  # >= 2*CROSSFADE_BUCLE (0.1*2=0.2), no rechazada
    out = tmp_path / "pista.wav"

    musica.preparar_pista(corta, total=600.0, fundido=2.0, out=out)

    assert musica.duracion(out) == pytest.approx(600.0, abs=0.5)


def test_preparar_pista_con_musica_mas_corta_que_2x_el_crossfade_aborta_con_mensaje_claro(tmp_path):
    muy_corta = _tono(tmp_path, "muy_corta.wav", 0.05)  # < 2*CROSSFADE_BUCLE (0.2)
    out = tmp_path / "pista.wav"

    with pytest.raises(SystemExit) as e:
        musica.preparar_pista(muy_corta, total=10.0, fundido=2.0, out=out)

    assert "corta" in str(e.value).lower()
    assert not out.exists()


def test_preparar_pista_en_bucle_no_deja_un_click_en_la_costura(tmp_path):
    # N6 (QA 03/10/2026): -stream_loop repite el clip tal cual, sin pisar los extremos: si
    # el clip no cierra en un cruce por cero (437.3 Hz en 1.0s no completa un número entero
    # de ciclos), cada vuelta del bucle salta de golpe del último valor al primero. Medido
    # sin fix: salto en la costura ~3966 contra ~256 en el resto de la señal (~15x).
    archivo = tmp_path / "clip.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "sine=f=437.3:d=1.0", "-ar", "44100", str(archivo)], check=True)
    out = tmp_path / "pista.wav"

    musica.preparar_pista(archivo, total=4.0, fundido=2.0, out=out)

    salto_costura = max(_salto_maximo_cerca_de(out, 1.0, ventana=0.01),
                         _salto_maximo_cerca_de(out, 2.0, ventana=0.01))
    salto_resto = _salto_maximo_cerca_de(out, 1.5, ventana=0.5)
    assert salto_costura <= salto_resto * 3, (salto_costura, salto_resto)


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


# --- QA 04/10/2026 (NOTE, ronda 3, M24): "en silencio, usar la voz anterior; si no hay, --
# la siguiente" no tenía ningún test directo (sólo quedaba implícito en tests de
# end-to-end que no distinguían los dos casos).

def test_voz_lu_mas_cercana_prioriza_la_anterior_si_hay():
    # índice 3 ("silencio"/"mute"): hay voz medida ANTES (índice 1) y DESPUÉS (índice 5):
    # tiene que usar la de ANTES, no la de después.
    voz_lu_por_indice = {1: -20.0, 5: -10.0}

    resultado = musica._voz_lu_mas_cercana(voz_lu_por_indice, 3, default=-99.0)

    assert resultado == -20.0


def test_voz_lu_mas_cercana_usa_la_siguiente_si_no_hay_anterior():
    # triangula: sin ninguna voz medida ANTES del índice 1, tiene que caer a la siguiente
    # (índice 5), no al default.
    voz_lu_por_indice = {5: -10.0}

    resultado = musica._voz_lu_mas_cercana(voz_lu_por_indice, 1, default=-99.0)

    assert resultado == -10.0


# --- QA 04/10/2026 (NOTE, ronda 3, M1): la rampa tiene que probarse por el camino REAL --
# (voz()/construir_pista): los tests de "no es un escalón" de más arriba llaman a
# aplicar_ducking() DIRECTO con un `ramp` explícito, así que una mutación que deje
# construir_pista pasando ramp=0 (escalón) a aplicar_ducking no la detecta ninguno.

def test_construir_pista_la_transicion_a_silencio_es_rampa_no_escalon(tmp_path):
    voz = _tono(tmp_path, "voz.wav", 4.0)
    cruda = _tono(tmp_path, "musica-cruda.wav", 4.0, sr=44100)
    vts = [(0.0, 2.0, "voz"), (2.0, 4.0, "silencio")]
    out = tmp_path / "musica-juani.wav"

    musica.construir_pista(voz, cruda, vts, debajo_de_la_voz_lu=18, out=out)

    # RELEASE_S=0.6s (liberación, subiendo: voz->silencio): muestrea bien adentro de esa
    # rampa, lejos de las dos mesetas. Con un escalón (ramp=0), estos puntos saltarían
    # directo a la meseta de destino -eso es justo lo que este test tiene que detectar.
    # "voz" (debajo_de_la_voz_lu=18) queda MÁS atenuada que "silencio" (SILENCIO_LU=10):
    # la transición sube (es la liberación, RELEASE_S=0.6s).
    meseta_voz = _rms_en(out, 0.5, ventana=0.01, sr=44100)
    meseta_silencio = _rms_en(out, 3.5, ventana=0.01, sr=44100)
    puntos = [_rms_en(out, 2.0 + d, ventana=0.005, sr=44100) for d in (-0.2, -0.1, 0.0, 0.1, 0.2)]
    for a, b in zip(puntos, puntos[1:]):
        assert b > a * 1.02, puntos  # progreso real, creciente (no un salto ya hecho)
    assert puntos[0] > meseta_voz * 1.02, (puntos, meseta_voz)          # ya se despegó de "voz"
    assert puntos[-1] < meseta_silencio * 0.98, (puntos, meseta_silencio)  # no llegó ya a "silencio"


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


# --- QA 04/10/2026 (NOTE, ronda 3): construir_pista no puede costar 2 ffmpeg por ventana -
# de voz (medido: 57s con 300 segmentos). El loudness de todas las ventanas se mide en UNA
# sola pasada sobre voz_wav (no un ffmpeg nuevo por ventana).

def test_construir_pista_con_300_segmentos_no_tarda_mas_de_15s(tmp_path):
    import time

    n = 300
    voz = _tono(tmp_path, "voz.wav", n * 0.3)
    cruda = _tono(tmp_path, "musica-cruda.wav", n * 0.3, sr=44100)
    vts = musica.ventanas([0.3] * n, [(0.05, 0.25)] * n)
    out = tmp_path / "musica-juani.wav"

    inicio = time.monotonic()
    musica.construir_pista(voz, cruda, vts, debajo_de_la_voz_lu=18, out=out)
    tardo = time.monotonic() - inicio

    assert tardo < 15, f"tardó {tardo:.1f}s con 300 segmentos (no puede escalar con 2 ffmpeg/ventana)"


def test_construir_pista_en_un_segmento_con_musica_false_queda_por_debajo_de_60dbfs(tmp_path):
    voz = _tono(tmp_path, "voz.wav", 3.0)
    cruda = _tono(tmp_path, "musica-cruda.wav", 3.0, sr=44100)
    vts = [(0.0, 0.3, "silencio"), (0.3, 2.0, "voz"), (2.0, 3.0, "mute")]
    out = tmp_path / "musica-juani.wav"

    musica.construir_pista(voz, cruda, vts, debajo_de_la_voz_lu=18, out=out)

    assert _dbfs_pico_en(out, 2.2, 2.8) < -60


# --- QA 04/10/2026 (NOTE, ronda 3, M19): MUTE_DB=-50 sobrevivía ------------------------
# porque el test de arriba usa un sine de lavfi (~-18dBFS, "flojo"): -18-50=-68dBFS, que
# TAMBIÉN es < -60 (no distingue -50 de -90). Con una música FUERTE (cerca de 0dBFS):
# -50dBFS NO es < -60 (la mutación falla este test), -90dBFS SÍ lo es.

def test_construir_pista_en_mute_con_musica_fuerte_queda_por_debajo_de_60dbfs(tmp_path):
    voz = _tono(tmp_path, "voz.wav", 3.0)
    fuerte = tmp_path / "musica-fuerte.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=300:d=3.0",
                    "-af", "volume=20dB", "-ar", "44100", str(fuerte)], check=True)
    assert _dbfs_pico_en(fuerte, 0.0, 3.0) > -5, "la música de este test tiene que estar cerca de 0dBFS"
    vts = [(0.0, 0.3, "silencio"), (0.3, 2.0, "voz"), (2.0, 3.0, "mute")]
    out = tmp_path / "musica-juani.wav"

    musica.construir_pista(voz, fuerte, vts, debajo_de_la_voz_lu=18, out=out)

    assert _dbfs_pico_en(out, 2.2, 2.8) < -60


# --- N5 (QA 03/10/2026): R-2.5, la rampa hacia/desde "mute" no puede cruzar el borde ----

def test_aplicar_ducking_al_entrar_en_mute_la_musica_ya_esta_callada_justo_en_el_borde(tmp_path):
    # la rampa estaba centrada en el borde (mitad adentro del slot mudo): con ramp=0.15 la
    # música entraba ~75ms "de más" en un slot "musica: false" (R-2.5). La bajada tiene que
    # terminar ANTES de que el slot mudo arranque, no a mitad de camino en su borde.
    tono = _tono(tmp_path, "tono.wav", 3.0)
    vts = [(0.0, 1.5, "voz"), (1.5, 3.0, "mute")]
    out = tmp_path / "out.wav"

    musica.aplicar_ducking(tono, vts, {"voz": 0.0, "mute": -90.0}, out, ramp=0.15)

    # 10ms DESPUÉS del borde (1.5s): con la rampa vieja (centrada, mitad-vida 0.075s dentro
    # del slot mudo) todavía estaría a mitad de camino, muy por arriba de -60dBFS.
    assert _dbfs_pico_en(out, 1.50, 1.52) < -60


def test_aplicar_ducking_al_salir_de_mute_la_rampa_de_subida_arranca_despues_del_borde(tmp_path):
    # simétrico: la subida (saliendo de "mute") tiene que EMPEZAR en el borde, no antes
    # (si empezara antes, la música se oiría de a poco DURANTE el slot mudo, el mismo bug
    # de R-2.5 pero en el otro sentido).
    tono = _tono(tmp_path, "tono.wav", 3.0)
    vts = [(0.0, 1.5, "mute"), (1.5, 3.0, "voz")]
    out = tmp_path / "out.wav"

    musica.aplicar_ducking(tono, vts, {"mute": -90.0, "voz": 0.0}, out, ramp=0.15)

    # 10ms ANTES del borde (1.5s): todavía tiene que estar callada.
    assert _dbfs_pico_en(out, 1.48, 1.50) < -60


# --- QA 04/10/2026 (NOTE, ronda 3): la rampa interpolaba en AMPLITUD LINEAL, no en dB ---
# (repro n1.py): con 26dB de diferencia entre mesetas, eso da saltos de 4.5-5.8dB en 10ms
# cerca del extremo bajo de la rampa (ahí la amplitud lineal cambia poco por muestra, pero
# en dB ese mismo cambio es enorme). La rampa tiene que sonar pareja: ningún salto > ~1dB
# en una ventana de 10ms, en ningún punto de la rampa.

def _dbfs_de_rms(rms: float) -> float:
    import math

    return 20 * math.log10(rms) if rms > 0 else float("-inf")


def test_aplicar_ducking_la_rampa_no_da_saltos_grandes_de_db_con_26db_de_diferencia(tmp_path):
    tono = _tono(tmp_path, "tono.wav", 3.0)
    vts = [(0.0, 1.0, "silencio"), (1.0, 2.0, "voz"), (2.0, 3.0, "silencio")]
    out = tmp_path / "out.wav"

    musica.aplicar_ducking(tono, vts, {"silencio": 0.0, "voz": -26.0}, out, ramp=0.2)

    # muestrea toda la rampa (1.0 ± 0.1, bien cubierta por ramp=0.2) en pasos de 10ms.
    pasos = [1.0 - 0.1 + i * 0.01 for i in range(21)]
    dbs = [_dbfs_de_rms(_rms_en(out, t, ventana=0.005)) for t in pasos]
    saltos = [abs(b - a) for a, b in zip(dbs, dbs[1:]) if a != float("-inf") and b != float("-inf")]

    assert max(saltos) < 1.5, (saltos, dbs)


# --- J1 (QA 03/10/2026): ataque rápido, liberación lenta (sin bombeo) -------------------

def _tiempo_y_db(puntos: list[tuple[float, float]], i: int) -> tuple[float, float]:
    # QA 04/10/2026: _puntos_envolvente ahora devuelve (t, nivel_EN_dB) directamente (antes
    # era lineal y había que convertir acá).
    return puntos[i]


def test_puntos_envolvente_la_liberacion_es_mas_lenta_que_el_ataque_y_no_pasa_20db_por_s():
    # bajando (voz entra, "ataque"): rápido, como antes. vts = [voz, silencio]: el único
    # cambio (índice 0) es una SUBIDA (silencio queda más arriba que voz), o sea que acá se
    # ejercita la liberación.
    vts = [(0.0, 2.0, "voz"), (2.0, 4.0, "silencio")]
    ganancias_db = [-18.0, -10.0]  # 8dB, la misma distancia que el default real (18 vs 10 LU)

    puntos = musica._puntos_envolvente(vts, ganancias_db, ramp=musica.ATTACK_S,
                                        ramp_release=musica.RELEASE_S)

    # puntos: [(0, voz), (lo, voz), (hi, silencio), (4, silencio)] -> la rampa es [1]->[2]
    t_lo, db_lo = _tiempo_y_db(puntos, 1)
    t_hi, db_hi = _tiempo_y_db(puntos, 2)
    duracion_rampa = t_hi - t_lo
    pendiente = (db_hi - db_lo) / duracion_rampa

    assert duracion_rampa == pytest.approx(musica.RELEASE_S, abs=1e-6)
    assert pendiente <= 20.0, pendiente


def test_puntos_envolvente_el_ataque_sigue_siendo_rapido_entre_100_y_200ms():
    # triangula con el caso contrario: BAJANDO (voz entra, silencio -> voz) tiene que
    # seguir siendo rápido (ATTACK_S), no la liberación lenta.
    vts = [(0.0, 2.0, "silencio"), (2.0, 4.0, "voz")]
    ganancias_db = [-10.0, -18.0]  # bajando: silencio (más arriba) -> voz (más abajo)

    puntos = musica._puntos_envolvente(vts, ganancias_db, ramp=musica.ATTACK_S,
                                        ramp_release=musica.RELEASE_S)

    t_lo, _ = _tiempo_y_db(puntos, 1)
    t_hi, _ = _tiempo_y_db(puntos, 2)
    assert 0.1 <= t_hi - t_lo <= 0.2


def test_sin_huecos_cortos_un_hueco_de_0_4s_entre_frases_no_dispara_la_subida():
    # un hueco de 0.4s (< UMBRAL_HUECO_S=0.8) entre dos tramos de voz no tiene que dejar
    # que la música suba a nivel de silencio: se queda en el nivel más atenuado del vecino.
    vts = [(0.0, 2.0, "voz"), (2.0, 2.4, "silencio"), (2.4, 4.0, "voz")]
    ganancias_db = [-18.0, -10.0, -18.0]

    sin_huecos = musica._sin_huecos_cortos(vts, ganancias_db, musica.UMBRAL_HUECO_S)

    assert sin_huecos[1] == -18.0, sin_huecos


def test_sin_huecos_cortos_un_hueco_real_que_cruza_el_borde_de_dos_slots_si_sube():
    # QA 04/10/2026 (NOTE, ronda 3): un hueco real de 0.9s (> UMBRAL_HUECO_S=0.8) que cruza
    # el borde entre dos slots queda partido en DOS ventanas "silencio" (una por slot, 0.6s
    # y 0.3s), cada una por debajo del umbral por separado: la música no sube aunque el
    # hueco junto sí sea "de verdad". Hay que evaluar la duración CONTIGUA, no por ventana.
    vts = musica.ventanas([3.0, 3.0], [(0.3, 2.4), (0.3, 2.7)])
    ganancias_db = [-12, -20, -12, -12, -20, -12]

    sin_huecos = musica._sin_huecos_cortos(vts, ganancias_db, 0.8)

    # las dos ventanas "silencio" contiguas (índices 2 y 3) forman un hueco de 0.9s: no
    # tienen que quedar en el mínimo de sus vecinas (-20), tienen que poder subir.
    assert sin_huecos[2] != -20, sin_huecos
    assert sin_huecos[3] != -20, sin_huecos


def test_sin_huecos_cortos_un_hueco_largo_si_deja_subir():
    # triangula: un hueco de 1.0s (>= UMBRAL_HUECO_S) es un silencio de verdad, sí sube.
    vts = [(0.0, 2.0, "voz"), (2.0, 3.0, "silencio"), (3.0, 5.0, "voz")]
    ganancias_db = [-18.0, -10.0, -18.0]

    sin_huecos = musica._sin_huecos_cortos(vts, ganancias_db, musica.UMBRAL_HUECO_S)

    assert sin_huecos[1] == -10.0, sin_huecos


# --- QA 04/10/2026 (BLOCKING, ronda 3): normalizar_dos_pasadas, R-2.3 sin tolerancia ----
#
# loudnorm de UNA pasada no llega al integrado objetivo cuando el TP lo restringe (el
# target de TP limita la ganancia antes de que el integrado llegue a destino). El estándar
# profesional es loudnorm de DOS pasadas (1ra mide con print_format=json, 2da aplica con
# measured_* y linear=true) + un limitador de TRUE PEAK aparte (loudnorm en modo lineal no
# limita TP realmente).

def _rosa(path, dur: float, sr: int = 44100, amplitud: float = 0.5) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"anoisesrc=color=pink:d={dur}:a={amplitud}", "-ar", str(sr), str(path)],
                   check=True)


def test_normalizar_dos_pasadas_con_musica_picuda_el_integrado_llega_al_objetivo(tmp_path):
    # el TP de loudnorm de UNA pasada restringe la ganancia antes de llegar al objetivo:
    # ruido rosa fuerte (cerca de 0dBFS, crest factor real de música, no un pulso aislado).
    rosa = tmp_path / "rosa.wav"
    _rosa(rosa, 6.0, amplitud=0.9)
    out = tmp_path / "normalizada.wav"

    musica.normalizar_dos_pasadas(rosa, out, objetivo_i=-16.0, margen_tp=-1.0,
                                   limite_tp_final=-2.0, sr=48000)

    i = musica.loudness_integrada(out)
    assert i == pytest.approx(-16.0, abs=1.0)


def test_normalizar_dos_pasadas_respeta_el_limite_de_true_peak(tmp_path):
    rosa = tmp_path / "rosa.wav"
    _rosa(rosa, 6.0, amplitud=0.9)
    out = tmp_path / "normalizada.wav"

    musica.normalizar_dos_pasadas(rosa, out, objetivo_i=-16.0, margen_tp=-1.0,
                                   limite_tp_final=-2.0, sr=48000)

    _, tp = musica.medir_i_tp(out)
    assert tp <= -2.0 + 0.3, tp  # tolerancia chica: el oversampling de la medición no es exacto


def test_musica_no_llama_subprocess_run_directo_todo_pasa_por_el_vigia_de_editar(tmp_path, monkeypatch):
    # QA 04/10/2026 (NOTE, ronda 3): todo subprocess de musica.py tiene que pasar por el
    # vigía anti-cuelgue de editar.run() (antes llamaba subprocess.run directo en varios
    # puntos: duracion(), loudness_integrada(), aplicar_ducking(), preparar_pista(), etc.
    # editar.run() usa subprocess.Popen internamente (no subprocess.run), así que
    # bloquear subprocess.run acá detecta cualquier llamada que NO haya pasado por ahí.
    def _explota(*a, **k):
        raise AssertionError(f"musica.py llamó subprocess.run directo (no pasó por editar.run()): {a}")

    # arma el escenario ANTES de bloquear subprocess.run (esta preparación del test usa
    # subprocess.run directo a propósito: no es lo que se está verificando).
    voz = _tono(tmp_path, "voz.wav", 2.0)
    cruda = _tono(tmp_path, "cruda.wav", 2.0, sr=44100)
    vts = [(0.0, 2.0, "voz")]
    out = tmp_path / "out.wav"

    monkeypatch.setattr(musica.subprocess, "run", _explota)

    musica.construir_pista(voz, cruda, vts, debajo_de_la_voz_lu=18, out=out)
    musica.preparar_pista(voz, total=1.5, fundido=0.5, out=tmp_path / "pista.wav")


def test_normalizar_dos_pasadas_deja_la_salida_a_la_tasa_pedida(tmp_path):
    tono = _tono(tmp_path, "tono.wav", 2.0, sr=44100)
    out = tmp_path / "normalizada.wav"

    musica.normalizar_dos_pasadas(tono, out, objetivo_i=-16.0, margen_tp=-1.0,
                                   limite_tp_final=-2.0, sr=48000)

    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate",
                          "-of", "csv=p=0", str(out)], capture_output=True, text=True, check=True)
    assert res.stdout.strip() == "48000"
