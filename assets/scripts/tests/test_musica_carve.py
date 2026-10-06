"""musica.aplicar_carve_voz: "voiceover carve" (H1, docs/explicador/HITO3.md). Baja la
música SÓLO en las bandas de la voz (BANDAS_VOZ_HZ) mientras hay voz, con la misma máquina
de ataque/liberación que el ducking de banda ancha; en los silencios vuelve a sonar entera,
sin tocar los graves. Idea robada de HyperFrames (heygen-com/hyperframes, Apache 2.0,
packages/core/src/audioCarve.ts) -bandas FIJAS, no el análisis FFT por voz, ver el
comentario en musica.py junto a BANDAS_VOZ_HZ.
"""
import array
import re
import subprocess
import wave
from pathlib import Path

import pytest

import musica


def _ruido_rosa(tmp_path, nombre: str, dur: float, sr: int = 44100, semilla: int = 3) -> Path:
    out = Path(tmp_path) / nombre
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"anoisesrc=color=pink:d={dur}:seed={semilla}", "-ar", str(sr), str(out)],
                   check=True)
    return out


def _nivel_de_banda_db(wav: Path, inicio: float, fin: float, freq: float, ancho_oct: float = 0.3) -> float:
    """Nivel RMS (dBFS) de `wav` en [inicio,fin) filtrado a una banda angosta alrededor de
    `freq` (bandpass + astats): mide si el EQ tocó esa banda en ese tramo."""
    recorte = wav.with_name(f"{wav.stem}.banda-{freq:.0f}-{inicio:.2f}.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ss", str(inicio), "-to", str(fin),
                    "-af", f"bandpass=f={freq}:width_type=o:w={ancho_oct}", str(recorte)], check=True)
    out = subprocess.run(["ffmpeg", "-i", str(recorte), "-af", "astats=metadata=0:reset=1",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"RMS level dB:\s*(-inf|-?\d+\.?\d*)", out)
    return float("-inf") if m.group(1) == "-inf" else float(m.group(1))


# --- analiseCarveBands de HyperFrames: bandas fijas documentadas en SKILL.md ------------

def test_bandas_voz_hz_son_las_seis_de_hyperframes_a_fuerza_0_8():
    # SKILL.md (hyperframes-audio, ~línea 408): "250Hz -7.4dB ... 1600Hz -14.8dB ... 2500Hz
    # -7.4dB". Acá redondeado a -7/-15 (HITO3.md): triangula que son 6 bandas y que 1.6kHz
    # es la única que corta más fuerte que el resto.
    frecuencias = [f for f, _ in musica.BANDAS_VOZ_HZ]
    assert frecuencias == [250, 400, 630, 1000, 1600, 2500]
    ganancias = dict(musica.BANDAS_VOZ_HZ)
    assert ganancias[1600] < ganancias[1000]
    assert ganancias[1000] == ganancias[250] == ganancias[400] == ganancias[630] == ganancias[2500]


# --- _puntos_presencia(): entra rápido (ramp_in), sale lento (ramp_out) -----------------

def test_puntos_presencia_entra_mas_rapido_que_sale():
    vts = [(0.0, 2.0, "silencio"), (2.0, 4.0, "voz"), (4.0, 6.0, "silencio")]

    puntos = musica._puntos_presencia(vts, ramp_in=0.1, ramp_out=0.6)

    # puntos: [(0,MUTE), (lo1,MUTE), (hi1,0), (lo2,0), (hi2,MUTE), (6,MUTE)]
    t_lo1, _ = puntos[1]
    t_hi1, _ = puntos[2]
    t_lo2, _ = puntos[3]
    t_hi2, _ = puntos[4]
    assert t_hi1 - t_lo1 == pytest.approx(0.1, abs=1e-6)  # entrando a la voz: ramp_in
    assert t_hi2 - t_lo2 == pytest.approx(0.6, abs=1e-6)  # saliendo de la voz: ramp_out


def test_puntos_presencia_triangula_con_las_rampas_invertidas():
    # mismo escenario, pero pidiendo lo contrario: entra lento, sale rápido.
    vts = [(0.0, 2.0, "silencio"), (2.0, 4.0, "voz"), (4.0, 6.0, "silencio")]

    puntos = musica._puntos_presencia(vts, ramp_in=0.6, ramp_out=0.1)

    t_lo1, t_hi1 = puntos[1][0], puntos[2][0]
    t_lo2, t_hi2 = puntos[3][0], puntos[4][0]
    assert t_hi1 - t_lo1 == pytest.approx(0.6, abs=1e-6)
    assert t_hi2 - t_lo2 == pytest.approx(0.1, abs=1e-6)


# --- aplicar_carve_voz(): el EQ está activo en voz y se va en los silencios ------------

def test_aplicar_carve_voz_baja_una_banda_de_la_voz_durante_la_voz(tmp_path):
    rosa = _ruido_rosa(tmp_path, "rosa.wav", 4.0)
    vts = [(0.0, 1.5, "silencio"), (1.5, 2.5, "voz"), (2.5, 4.0, "silencio")]
    out = tmp_path / "out.wav"

    musica.aplicar_carve_voz(rosa, vts, out)

    silencio_1000 = _nivel_de_banda_db(out, 0.2, 1.3, 1000)
    voz_1000 = _nivel_de_banda_db(out, 1.75, 2.25, 1000)
    assert voz_1000 < silencio_1000 - 3.0, (silencio_1000, voz_1000)


def test_aplicar_carve_voz_vuelve_a_sonar_entera_en_el_silencio_de_despues(tmp_path):
    # triangula con una banda DISTINTA (1600Hz, la del corte más profundo): sin esto, un
    # carve que quedara siempre "húmedo" (p.ej. olvidando el complemento en los silencios)
    # pasaría el test de arriba si por casualidad sólo mide la banda equivocada.
    rosa = _ruido_rosa(tmp_path, "rosa.wav", 4.0)
    vts = [(0.0, 1.5, "silencio"), (1.5, 2.5, "voz"), (2.5, 4.0, "silencio")]
    out = tmp_path / "out.wav"

    musica.aplicar_carve_voz(rosa, vts, out)

    voz_1600 = _nivel_de_banda_db(out, 1.75, 2.25, 1600)
    silencio_despues_1600 = _nivel_de_banda_db(out, 2.75, 3.75, 1600)
    assert silencio_despues_1600 > voz_1600 + 3.0, (voz_1600, silencio_despues_1600)


def test_aplicar_carve_voz_no_toca_los_graves_fuera_de_las_bandas(tmp_path):
    # R-2.x nuevo (HITO3.md): "los graves (< 150 Hz) de la música bajan mucho menos que
    # antes" -el EQ sólo pisa 250-2500 Hz, 80Hz queda lejos de la banda más baja (250Hz).
    rosa = _ruido_rosa(tmp_path, "rosa.wav", 4.0)
    vts = [(0.0, 1.5, "silencio"), (1.5, 2.5, "voz"), (2.5, 4.0, "silencio")]
    out = tmp_path / "out.wav"

    musica.aplicar_carve_voz(rosa, vts, out)

    silencio_graves = _nivel_de_banda_db(out, 0.2, 1.3, 80)
    voz_graves = _nivel_de_banda_db(out, 1.75, 2.25, 80)
    assert abs(voz_graves - silencio_graves) < 1.5, (silencio_graves, voz_graves)


def _salto_maximo_cerca_de(wav: Path, t: float, ventana: float, sr: int = 44100) -> int:
    with wave.open(str(wav)) as w:
        w.setpos(max(int((t - ventana / 2) * sr), 0))
        n = int(ventana * sr)
        frames = w.readframes(n)
    m = array.array("h")
    m.frombytes(frames)
    if len(m) < 2:
        return 0
    return max(abs(m[i + 1] - m[i]) for i in range(len(m) - 1))


def test_aplicar_carve_voz_no_deja_un_click_en_el_borde_de_la_rampa(tmp_path):
    rosa = _ruido_rosa(tmp_path, "rosa.wav", 4.0)
    vts = [(0.0, 2.0, "silencio"), (2.0, 4.0, "voz")]
    out = tmp_path / "out.wav"

    musica.aplicar_carve_voz(rosa, vts, out, ramp=0.2, ramp_release=0.2)

    salto_borde = _salto_maximo_cerca_de(out, 2.0, ventana=0.01)
    salto_resto = _salto_maximo_cerca_de(out, 1.0, ventana=0.5)
    assert salto_borde <= salto_resto * 3, (salto_borde, salto_resto)


# --- carve + ducking de banda ancha combinados: separación en la banda de la voz -------

def test_carve_mas_ducking_separa_al_menos_15db_en_la_banda_de_la_voz(tmp_path):
    voz = tmp_path / "voz.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=1000:d=3.0",
                    "-ar", "44100", str(voz)], check=True)
    cruda = _ruido_rosa(tmp_path, "cruda.wav", 3.0)
    vts = [(0.0, 0.3, "silencio"), (0.3, 2.7, "voz"), (2.7, 3.0, "silencio")]
    carveada = tmp_path / "carveada.wav"
    out = tmp_path / "musica-final.wav"

    musica.aplicar_carve_voz(cruda, vts, carveada)
    musica.construir_pista(voz, carveada, vts, debajo_de_la_voz_lu=10, out=out)

    voz_1000 = _nivel_de_banda_db(voz, 0.5, 2.5, 1000)
    musica_1000 = _nivel_de_banda_db(out, 0.5, 2.5, 1000)
    assert voz_1000 - musica_1000 >= 15, (voz_1000, musica_1000)


# --- tp_interno(): margen del AAC aplicado al perfil elegido ---------------------------

def test_tp_interno_de_youtube_es_el_mismo_margen_de_antes():
    # antes: TP_OBJETIVO_CON_MUSICA = -2.0 (= -1.5 - 0.5, el perfil "youtube"). G3 depende
    # de que este número no se mueva para el perfil default.
    assert musica.tp_interno("youtube") == pytest.approx(-2.0)


def test_tp_interno_de_redes_usa_el_mismo_margen_con_su_propio_tp():
    # triangula con el otro perfil: mismo margen (0.5), tp real distinto (-1.0).
    assert musica.tp_interno("redes") == pytest.approx(-1.5)
