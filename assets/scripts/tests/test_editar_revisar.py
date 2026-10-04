"""`editar.py revisar`: el director mide lo que pide S5 (HITO2.md).

Todo de sólo lectura: `revisar()` nunca genera ni modifica guion ni videos. Si un
chequeo necesita un artefacto que no está, lo dice (R-5.6) en vez de omitirlo.
"""
import json
import subprocess

import pytest

import editar


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    (tmp_path / "videos" / "v09").mkdir(parents=True)
    return tmp_path


def _guion(raiz, g):
    (raiz / "guion" / "v09.json").write_text(json.dumps(g))


def _clip(path, fuente):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", fuente, "-y", str(path)], check=True)


def _concat_video(path, clips):
    entradas = []
    for c in clips:
        entradas += ["-i", str(c)]
    filtro = "".join(f"[{i}:v]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=0[v]"
    subprocess.run(["ffmpeg", "-loglevel", "error", *entradas, "-filter_complex", filtro,
                    "-map", "[v]", "-y", str(path)], check=True)


def _concat_wav(path, clips):
    entradas = []
    for c in clips:
        entradas += ["-i", str(c)]
    filtro = "".join(f"[{i}:a]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=0:a=1[a]"
    subprocess.run(["ffmpeg", "-loglevel", "error", *entradas, "-filter_complex", filtro,
                    "-map", "[a]", "-y", str(path)], check=True)


# --- R-5.1 / R-5.6: sin artefactos, informa qué no corrió y por qué -----------------

def test_revisar_sin_ningun_artefacto_dice_que_no_corrio_en_vez_de_omitirlo(raiz):
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    hallazgos, no_corrio = editar.revisar("v09", "argentina")

    assert hallazgos == ["el guion no declara roles"]
    assert any("video-argentina.mp4" in m for m in no_corrio)
    assert any("voz-argentina.wav" in m for m in no_corrio)


# --- R-5.2: tiempo muerto (freezedetect) sobre video-<voz>.mp4 ----------------------

def test_tiempo_muerto_de_mas_de_n_segundos_se_reporta(raiz, tmp_path):
    clip = tmp_path / "clip.mp4"
    quieto = tmp_path / "quieto.mp4"
    _clip(clip, "testsrc=s=320x240:r=30:d=1,format=yuv420p")
    _clip(quieto, "color=c=black:s=320x240:r=30:d=8")
    _concat_video(raiz / "videos" / "v09" / "video-argentina.mp4", [clip, quieto, clip])
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    hallazgos, no_corrio = editar.revisar("v09", "argentina")

    assert any("tiempo muerto" in h for h in hallazgos)
    assert not any("video-argentina.mp4" in m for m in no_corrio)


def test_sin_tiempo_muerto_largo_no_hay_hallazgo_de_eso(raiz, tmp_path):
    clip = tmp_path / "clip.mp4"
    _clip(clip, "testsrc=s=320x240:r=30:d=3,format=yuv420p")
    _concat_video(raiz / "videos" / "v09" / "video-argentina.mp4", [clip])
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert not any("tiempo muerto" in h for h in hallazgos)


# --- R-5.3: huecos entre entradas de elementos, desde los specs resueltos ----------

def test_un_hueco_de_mas_de_n_segundos_en_una_escena_se_reporta(raiz):
    escenas_dir = raiz / "videos" / "v09" / "escenas"
    escenas_dir.mkdir(parents=True)
    spec = {"tipo": "presentacion", "duracion": 10.0,
            "puntos": [{"texto": "a", "cue": "a", "t": 1.0}]}
    (escenas_dir / "00.json").write_text(json.dumps(spec))
    _guion(raiz, {"segmentos": [{"escena": {"tipo": "presentacion"}, "texto": "a"}]})

    hallazgos, no_corrio = editar.revisar("v09", "argentina")

    assert any("00.json" in h and "sin elemento nuevo" in h for h in hallazgos)
    assert not any("specs resueltos" in m for m in no_corrio)


def test_elementos_repartidos_sin_huecos_largos_no_da_hallazgo(raiz):
    escenas_dir = raiz / "videos" / "v09" / "escenas"
    escenas_dir.mkdir(parents=True)
    spec = {"tipo": "presentacion", "duracion": 6.0,
            "puntos": [{"texto": "a", "cue": "a", "t": 1.0}, {"texto": "b", "cue": "b", "t": 5.0}]}
    (escenas_dir / "00.json").write_text(json.dumps(spec))
    _guion(raiz, {"segmentos": [{"escena": {"tipo": "presentacion"}, "texto": "a b"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert not any("sin elemento nuevo" in h for h in hallazgos)


def test_sin_specs_resueltos_y_con_escena_en_el_guion_dice_que_no_corrio(raiz):
    _guion(raiz, {"segmentos": [{"escena": {"tipo": "presentacion"}, "texto": "a"}]})

    _, no_corrio = editar.revisar("v09", "argentina")

    assert any("specs resueltos" in m for m in no_corrio)


# --- R-5.4: silencios > 0.9s en voz-<voz>.wav (no en el final) ---------------------

def test_un_silencio_de_mas_de_0_9s_en_la_voz_se_reporta(raiz, tmp_path):
    habla = tmp_path / "habla.wav"
    silencio = tmp_path / "silencio.wav"
    _clip(habla, "sine=f=300:d=1")
    _clip(silencio, "anullsrc=r=22050:cl=mono:d=1.2")
    _concat_wav(raiz / "videos" / "v09" / "voz-argentina.wav", [habla, silencio, habla])
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    hallazgos, no_corrio = editar.revisar("v09", "argentina")

    assert any("silencio" in h for h in hallazgos)
    assert not any("voz-argentina.wav" in m for m in no_corrio)


def test_sin_silencios_largos_no_hay_hallazgo_de_eso(raiz, tmp_path):
    habla = tmp_path / "habla.wav"
    _clip(habla, "sine=f=300:d=2")
    _concat_wav(raiz / "videos" / "v09" / "voz-argentina.wav", [habla])
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert not any("silencio" in h for h in hallazgos)


# --- R-5.5: estructura de clase por `rol` ------------------------------------------

def test_sin_ningun_rol_avisa_una_sola_linea(raiz):
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"},
                                {"inicio": 1, "fin": 2, "texto": "b"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert hallazgos == ["el guion no declara roles"]


def test_con_roles_completos_y_bien_ubicados_no_hay_hallazgo_de_rol(raiz):
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a", "rol": "gancho"},
        {"inicio": 1, "fin": 2, "texto": "b", "rol": "analogia"},
        {"inicio": 2, "fin": 3, "texto": "c", "rol": "ejemplo"},
        {"inicio": 3, "fin": 4, "texto": "d", "rol": "repaso"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert hallazgos == []


def test_sin_repaso_al_final_se_reporta(raiz):
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a", "rol": "gancho"},
        {"inicio": 1, "fin": 2, "texto": "b", "rol": "analogia"},
        {"inicio": 2, "fin": 3, "texto": "c", "rol": "ejemplo"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("repaso" in h for h in hallazgos)


def test_sin_gancho_al_inicio_se_reporta(raiz):
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a", "rol": "analogia"},
        {"inicio": 1, "fin": 2, "texto": "b", "rol": "ejemplo"},
        {"inicio": 2, "fin": 3, "texto": "c", "rol": "repaso"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("gancho" in h for h in hallazgos)


def test_sin_ninguna_analogia_se_reporta(raiz):
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a", "rol": "gancho"},
        {"inicio": 1, "fin": 2, "texto": "b", "rol": "ejemplo"},
        {"inicio": 2, "fin": 3, "texto": "c", "rol": "repaso"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("analogia" in h for h in hallazgos)


# --- R-5.1 / R-5.7: por línea de comandos, informe y código de salida --------------

def _correr_cli(raiz, monkeypatch, capsys, argv_extra):
    import runpy
    import sys
    from pathlib import Path
    monkeypatch.setenv("TUT_ROOT", str(raiz))
    monkeypatch.setattr(sys, "argv", ["editar.py", "revisar", "v09", *argv_extra])
    code = None
    try:
        runpy.run_path(str(Path(editar.__file__)), run_name="__main__")
    except SystemExit as e:
        code = e.code
    salida = capsys.readouterr().out
    return salida, (0 if code is None else code)


def test_revisar_imprime_un_informe_y_sale_con_0_por_defecto(raiz, monkeypatch, capsys):
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    salida, code = _correr_cli(raiz, monkeypatch, capsys, [])

    assert "el guion no declara roles" in salida
    assert code == 0


def test_con_hallazgos_y_sin_estricto_sigue_saliendo_con_0(raiz, monkeypatch, capsys):
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    _, code = _correr_cli(raiz, monkeypatch, capsys, [])

    assert code == 0


def test_con_hallazgos_y_estricto_sale_con_1(raiz, monkeypatch, capsys):
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    _, code = _correr_cli(raiz, monkeypatch, capsys, ["--estricto"])

    assert code == 1


def test_sin_hallazgos_y_estricto_sale_con_0(raiz, monkeypatch, capsys):
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a", "rol": "gancho"},
        {"inicio": 1, "fin": 2, "texto": "b", "rol": "analogia"},
        {"inicio": 2, "fin": 3, "texto": "c", "rol": "ejemplo"},
        {"inicio": 3, "fin": 4, "texto": "d", "rol": "repaso"}]})

    _, code = _correr_cli(raiz, monkeypatch, capsys, ["--estricto"])

    assert code == 0
