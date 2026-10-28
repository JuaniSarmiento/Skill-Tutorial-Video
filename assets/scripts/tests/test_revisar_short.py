"""Director de Shorts verticales (canal "Fuera de Rango"): revisa un episodio YA
grabado (guion/eNN.json + video/public/eNN/tiempos.json + el .mp4 publicado) sin
renderizar nada. Mismo espíritu que `editar.py revisar` (sólo lee), ver
`references/shorts.md`.
"""
import json
import subprocess
from pathlib import Path

import pytest

import revisar_short


def _clip(path, fuente, duracion=1.0, ancho=1080, alto=1920, silencio=True, tono_db=None):
    """Clip sintético chico vía ffmpeg lavfi, al estilo de test_editar_revisar.py."""
    separador = ":" if "=" in fuente else "="
    video = f"{fuente}{separador}s={ancho}x{alto}:r=10:d={duracion}"
    if silencio:
        audio = f"anullsrc=r=48000:cl=stereo:d={duracion}"
    else:
        # sine por defecto sale a ~-18 dBFS de pico (parámetro fijo del filtro, sin
        # amplitud configurable): 20dB de volumen por defecto lo sube cerca de 0dBFS
        # (más alto que el umbral), y tono_db permite pedir uno más bajo (pasa).
        tono_db = 20 if tono_db is None else tono_db
        audio = f"sine=frequency=1000:sample_rate=48000:d={duracion},volume={tono_db}dB"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", video,
         "-f", "lavfi", "-i", audio, "-shortest", "-y", str(path)],
        check=True)


@pytest.fixture
def raiz(tmp_path):
    (tmp_path / "guion").mkdir()
    (tmp_path / "video" / "public" / "e34").mkdir(parents=True)
    return tmp_path


def _guion(raiz, segmentos):
    ruta = raiz / "guion" / "e34.json"
    ruta.write_text(json.dumps({"segmentos": segmentos}))
    return ruta


def _tiempos(raiz, datos):
    ruta = raiz / "video" / "public" / "e34" / "tiempos.json"
    ruta.write_text(json.dumps(datos))
    return ruta


# --- D2 vertical: huecos de más de n segundos sin una entrada nueva ---------------
# Entradas = inicio de cada segmento + tiempo de cada cue (NO renderiza nada: lee
# directo de tiempos.json).

def test_tramo_de_mas_de_n_segundos_sin_entrada_se_reporta():
    tiempos = {"total": 9.0, "segmentos": [
        {"inicio": 0.0, "fin": 9.0, "cues": {}},
    ]}

    huecos = revisar_short._huecos_tiempos(tiempos, 6.0)

    assert any(a == 0.0 and b == 9.0 for a, b in huecos)


def test_una_cue_a_mitad_del_tramo_corta_el_hueco():
    tiempos = {"total": 9.0, "segmentos": [
        {"inicio": 0.0, "fin": 9.0, "cues": {"algo": 4.5}},
    ]}

    huecos = revisar_short._huecos_tiempos(tiempos, 6.0)

    assert huecos == []


def test_hueco_de_exactamente_n_no_es_hallazgo():
    """Mismo criterio de borde que D1/D2 16:9: estrictamente MÁS de n, no 'n o más'."""
    tiempos = {"total": 6.0, "segmentos": [{"inicio": 0.0, "fin": 6.0, "cues": {}}]}

    assert revisar_short._huecos_tiempos(tiempos, 6.0) == []


# --- D8 vertical: ritmo por `escena.forma`, no por `tipo` -------------------------
# Distintos `tipo` ("z34_boca_433", "z34_boca_paredes"...) pueden ser la MISMA forma
# visual ("cancha"): D8 16:9 (editar._hallazgos_ritmo) agrupa por `tipo` y no tiene
# parámetro para cambiar esa clave, así que con ese campo D8 pasaría en falso sobre
# el e34. Por eso esto no reusa `editar._hallazgos_ritmo`: se reescribe agrupando por
# `escena.forma`, con el aviso nuevo que esa función no tiene.

def _seg(forma=None, **kw):
    escena = {"tipo": "z", **({"forma": forma} if forma is not None else {})}
    return {"inicio": 0, "fin": 1, "texto": "x", "escena": escena, **kw}


def test_tres_segmentos_de_la_misma_forma_seguidos_se_reporta():
    segmentos = [_seg("cancha"), _seg("cancha"), _seg("cancha")]

    hallazgos, no_corrio = revisar_short._hallazgos_ritmo_forma(segmentos)

    assert any("ritmo" in h and "cancha" in h for h in hallazgos), hallazgos
    assert no_corrio == []


def test_dos_segmentos_de_la_misma_forma_no_se_reporta():
    segmentos = [_seg("cancha"), _seg("cancha")]

    hallazgos, _ = revisar_short._hallazgos_ritmo_forma(segmentos)

    assert hallazgos == []


def test_sin_ningun_segmento_que_declare_forma_avisa_que_d8_no_corrio():
    segmentos = [_seg(forma=None), _seg(forma=None), _seg(forma=None)]

    hallazgos, no_corrio = revisar_short._hallazgos_ritmo_forma(segmentos)

    assert hallazgos == []
    assert any("D8 no corrió" in m and "escena.forma" in m for m in no_corrio), no_corrio


# --- revisar_short(): orquesta D1 (reusado de editar), D2, D8 y lo vertical --------

def test_video_inexistente_es_no_corrio_nunca_un_pase(raiz):
    guion = _guion(raiz, [{"inicio": 0, "fin": 1, "texto": "a"}])
    tiempos = _tiempos(raiz, {"total": 1.0, "segmentos": [{"inicio": 0.0, "fin": 1.0, "cues": {}}]})
    video = raiz / "video" / "public" / "e34" / "e34.mp4"  # no existe

    hallazgos, no_corrio = revisar_short.revisar_short(guion, tiempos, video)

    assert hallazgos == []
    assert any("falta" in m and video.name in m for m in no_corrio), no_corrio


def test_tiempo_muerto_del_video_se_reporta_reusando_freezes(raiz, tmp_path):
    """D1: reusa editar._freezes (no lo copia)."""
    guion = _guion(raiz, [{"inicio": 0, "fin": 9, "texto": "a"}])
    tiempos = _tiempos(raiz, {"total": 9.0, "segmentos": [{"inicio": 0.0, "fin": 9.0, "cues": {}}]})
    video = raiz / "video" / "public" / "e34" / "e34.mp4"
    _clip(video, "color=c=black", duracion=8, ancho=1080, alto=1920)

    hallazgos, _ = revisar_short.revisar_short(guion, tiempos, video)

    assert any("tiempo muerto" in h for h in hallazgos), hallazgos


def test_video_con_dimensiones_horizontales_se_reporta(raiz, tmp_path):
    guion = _guion(raiz, [{"inicio": 0, "fin": 1, "texto": "a"}])
    tiempos = _tiempos(raiz, {"total": 1.0, "segmentos": [{"inicio": 0.0, "fin": 1.0, "cues": {}}]})
    video = raiz / "video" / "public" / "e34" / "e34.mp4"
    _clip(video, "testsrc2", duracion=1, ancho=1920, alto=1080)

    hallazgos, _ = revisar_short.revisar_short(guion, tiempos, video)

    assert any("vertical" in h and "1920" in h and "1080" in h for h in hallazgos), hallazgos


def test_video_vertical_1080x1920_no_reporta_dimensiones(raiz, tmp_path):
    guion = _guion(raiz, [{"inicio": 0, "fin": 1, "texto": "a"}])
    tiempos = _tiempos(raiz, {"total": 1.0, "segmentos": [{"inicio": 0.0, "fin": 1.0, "cues": {}}]})
    video = raiz / "video" / "public" / "e34" / "e34.mp4"
    _clip(video, "testsrc2", duracion=1, ancho=1080, alto=1920)

    hallazgos, _ = revisar_short.revisar_short(guion, tiempos, video)

    assert not any("mide" in h for h in hallazgos), hallazgos


def test_video_de_mas_de_180s_avisa_que_ya_no_es_short(raiz, tmp_path):
    guion = _guion(raiz, [{"inicio": 0, "fin": 1, "texto": "a"}])
    tiempos = _tiempos(raiz, {"total": 181.0, "segmentos": [{"inicio": 0.0, "fin": 181.0, "cues": {}}]})
    video = raiz / "video" / "public" / "e34" / "e34.mp4"
    _clip(video, "color=c=black", duracion=181, ancho=160, alto=90)

    hallazgos, _ = revisar_short.revisar_short(guion, tiempos, video)

    assert any("aviso" in h and "180" in h and "Short" in h for h in hallazgos), hallazgos


def test_true_peak_por_encima_de_umbral_avisa(raiz, tmp_path):
    guion = _guion(raiz, [{"inicio": 0, "fin": 1, "texto": "a"}])
    tiempos = _tiempos(raiz, {"total": 1.0, "segmentos": [{"inicio": 0.0, "fin": 1.0, "cues": {}}]})
    video = raiz / "video" / "public" / "e34" / "e34.mp4"
    _clip(video, "color=c=black", duracion=1, ancho=1080, alto=1920, silencio=False)  # sine a 0dBFS

    hallazgos, _ = revisar_short.revisar_short(guion, tiempos, video)

    assert any("aviso" in h and "true peak" in h for h in hallazgos), hallazgos


def test_true_peak_bajo_no_avisa(raiz, tmp_path):
    guion = _guion(raiz, [{"inicio": 0, "fin": 1, "texto": "a"}])
    tiempos = _tiempos(raiz, {"total": 1.0, "segmentos": [{"inicio": 0.0, "fin": 1.0, "cues": {}}]})
    video = raiz / "video" / "public" / "e34" / "e34.mp4"
    _clip(video, "color=c=black", duracion=1, ancho=1080, alto=1920, silencio=False, tono_db=-30)

    hallazgos, _ = revisar_short.revisar_short(guion, tiempos, video)

    assert not any("true peak" in h for h in hallazgos), hallazgos


# --- CLI: revisar_short.py <guion.json> <tiempos.json> <video.mp4> [--estricto] ---

def test_cli_sin_estricto_sale_con_0_aunque_haya_hallazgos(raiz, monkeypatch, capsys):
    guion = _guion(raiz, [{"inicio": 0, "fin": 1, "texto": "a"}])
    tiempos = _tiempos(raiz, {"total": 1.0, "segmentos": [{"inicio": 0.0, "fin": 1.0, "cues": {}}]})
    video = raiz / "video" / "public" / "e34" / "e34.mp4"  # inexistente -> no_corrio

    codigo = revisar_short._dispatch([str(guion), str(tiempos), str(video)])

    assert codigo == 0
    assert "no corrió" in capsys.readouterr().out


def test_cli_con_estricto_sale_con_1_si_algo_no_corrio(raiz, monkeypatch, capsys):
    guion = _guion(raiz, [{"inicio": 0, "fin": 1, "texto": "a"}])
    tiempos = _tiempos(raiz, {"total": 1.0, "segmentos": [{"inicio": 0.0, "fin": 1.0, "cues": {}}]})
    video = raiz / "video" / "public" / "e34" / "e34.mp4"  # inexistente -> no_corrio

    codigo = revisar_short._dispatch([str(guion), str(tiempos), str(video), "--estricto"])

    assert codigo == 1
