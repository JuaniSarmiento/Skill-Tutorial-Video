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


def _spec_vigente(raiz, voz, indice, seg, **campos):
    """Escribe un spec de escena YA vigente (B5/NOTE 2/3a): con las mismas
    etiquetas que `escenas()` deja de verdad (`_voz`, `_segmento_hash`), atado al
    segmento `seg` del guion y a la voz `voz`. Así los tests de D2 no dependen de
    cómo se decide "vigente" por dentro."""
    spec = {**campos, "_voz": voz, "_segmento_hash": editar._hash_segmento(seg)}
    escenas_dir = raiz / "videos" / "v09" / "escenas"
    escenas_dir.mkdir(parents=True, exist_ok=True)
    (escenas_dir / f"{indice:02d}.json").write_text(json.dumps(spec))
    return spec


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


# --- NOTE 5: guion JSON roto o sin "segmentos": error claro, no traceback ---------

def test_guion_con_json_invalido_es_error_claro(raiz):
    (raiz / "guion" / "v09.json").write_text("{ esto no es json")

    with pytest.raises(editar.RevisarError) as exc:
        editar.revisar("v09", "argentina")

    assert "v09" in str(exc.value)
    assert "inválido" in str(exc.value)


def test_guion_sin_segmentos_es_error_claro(raiz):
    _guion(raiz, {})  # sin la clave "segmentos"

    with pytest.raises(editar.RevisarError) as exc:
        editar.revisar("v09", "argentina")

    assert "v09" in str(exc.value)
    assert "segmentos" in str(exc.value)


# --- B3a: voz sin NINGÚN artefacto, habiendo artefactos de otra voz: error claro ----

def test_voz_sin_ningun_artefacto_pero_con_otra_voz_presente_es_error(raiz, tmp_path):
    clip = tmp_path / "clip.mp4"
    _clip(clip, "testsrc=s=320x240:r=30:d=1,format=yuv420p")
    _concat_video(raiz / "videos" / "v09" / "video-argentina.mp4", [clip])
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    with pytest.raises(editar.RevisarError) as exc:
        editar.revisar("v09", "argentin")  # typo

    assert "argentin" in str(exc.value)
    assert "argentina" in str(exc.value)


# --- NOTE 3b: _voces_con_artefactos también mira la carpeta <voz>/ (ej. "juani") --

def test_voces_con_artefactos_reconoce_la_carpeta_de_la_voz(tmp_path):
    (tmp_path / "juani").mkdir()
    (tmp_path / "juani" / "00.wav").write_bytes(b"")

    assert "juani" in editar._voces_con_artefactos(tmp_path)


def test_voces_con_artefactos_no_confunde_escenas_ni_seg_con_una_voz(tmp_path):
    (tmp_path / "escenas").mkdir()
    (tmp_path / "seg").mkdir()

    assert editar._voces_con_artefactos(tmp_path) == set()


def test_voces_con_artefactos_reconoce_solo_slots(tmp_path):
    """N17: si se borra el glob de slots-*.json, una voz para la que sólo corrió
    `imagen` (y no `voz`/`escenas`) deja de reconocerse."""
    (tmp_path / "slots-mendoza.json").write_text("[]")

    assert "mendoza" in editar._voces_con_artefactos(tmp_path)


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


# --- NOTE 1: ffmpeg que falla (video vacío/corrupto) no es "sin hallazgos" --------

def test_video_vacio_o_corrupto_dice_que_no_corrio_con_la_causa(raiz):
    (raiz / "videos" / "v09" / "video-argentina.mp4").touch()  # 0 bytes: ffmpeg falla
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    hallazgos, no_corrio = editar.revisar("v09", "argentina")

    assert not any("tiempo muerto" in h for h in hallazgos)  # NUNCA "sin hallazgos" por error
    assert any("video-argentina.mp4" in m and "no corrió" in m for m in no_corrio)


# --- B1: congelado hasta el final (freeze_start sin freeze_end) ---------------------

def test_congelado_hasta_el_final_del_video_se_reporta(raiz, tmp_path):
    clip = tmp_path / "clip.mp4"
    quieto = tmp_path / "quieto.mp4"
    _clip(clip, "testsrc=s=320x240:r=30:d=1,format=yuv420p")
    _clip(quieto, "color=c=black:s=320x240:r=30:d=8")
    _concat_video(raiz / "videos" / "v09" / "video-argentina.mp4", [clip, quieto])
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("tiempo muerto" in h for h in hallazgos)


# --- B9: D1 usa el mismo criterio de borde que D2 (> N, no >= N) -------------------

def test_tiempo_muerto_de_mas_de_n_pero_menos_del_mutante_se_reporta(raiz, tmp_path):
    """Entre N=6 (correcto) y 7.9 (mutante de N): un tramo de 7s tiene que reportarse."""
    clip = tmp_path / "clip.mp4"
    quieto = tmp_path / "quieto.mp4"
    _clip(clip, "testsrc=s=320x240:r=30:d=1,format=yuv420p")
    _clip(quieto, "color=c=black:s=320x240:r=30:d=7")
    _concat_video(raiz / "videos" / "v09" / "video-argentina.mp4", [clip, quieto, clip])
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("tiempo muerto" in h for h in hallazgos)


def test_video_con_textura_sutil_que_cambia_no_es_tiempo_muerto(raiz, tmp_path):
    """B9/M8: freezedetect usa un umbral de sensibilidad estricto (-60dB). Un video con
    cambios sutiles pero reales entre cuadros (ruido de amplitud 20) no es tiempo muerto;
    con un umbral más laxo (-15dB, mutante) se confundiría con congelado."""
    sutil = tmp_path / "sutil.mp4"
    _clip(sutil, "color=c=gray:s=320x240:r=30:d=8,noise=alls=20:allf=t+u,format=yuv420p")
    (raiz / "videos" / "v09" / "video-argentina.mp4").write_bytes(sutil.read_bytes())
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert not any("tiempo muerto" in h for h in hallazgos)


# --- R-5.3: huecos entre entradas de elementos, desde los specs resueltos ----------

def test_un_hueco_de_mas_de_n_segundos_en_una_escena_se_reporta(raiz):
    seg = {"escena": {"tipo": "presentacion"}, "texto": "a"}
    _guion(raiz, {"segmentos": [seg]})
    _spec_vigente(raiz, "argentina", 0, seg, tipo="presentacion", duracion=10.0,
                  puntos=[{"texto": "a", "cue": "a", "t": 1.0}])

    hallazgos, no_corrio = editar.revisar("v09", "argentina")

    assert any("00.json" in h and "sin elemento nuevo" in h for h in hallazgos)
    assert not any("specs resueltos" in m for m in no_corrio)


def test_elementos_repartidos_sin_huecos_largos_no_da_hallazgo(raiz):
    seg = {"escena": {"tipo": "presentacion"}, "texto": "a b"}
    _guion(raiz, {"segmentos": [seg]})
    _spec_vigente(raiz, "argentina", 0, seg, tipo="presentacion", duracion=6.0,
                  puntos=[{"texto": "a", "cue": "a", "t": 1.0}, {"texto": "b", "cue": "b", "t": 5.0}])

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert not any("sin elemento nuevo" in h for h in hallazgos)


def test_hueco_de_mas_de_n_pero_menos_del_mutante_se_reporta(raiz):
    """M9/M11: entre N=6 (correcto) y 7.9/8.5 (mutantes), un hueco de 7s tiene que
    reportarse."""
    seg = {"escena": {"tipo": "presentacion"}, "texto": "a b"}
    _guion(raiz, {"segmentos": [seg]})
    _spec_vigente(raiz, "argentina", 0, seg, tipo="presentacion", duracion=10.0,
                  puntos=[{"texto": "a", "cue": "a", "t": 1.0}, {"texto": "b", "cue": "b", "t": 8.0}])

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("00.json" in h and "sin elemento nuevo" in h for h in hallazgos)


# --- M4: D2 con el mismo criterio de borde exacto (6.0s), sin pasar por ffmpeg ------

def test_hueco_de_exactamente_n_no_es_hallazgo():
    """M4: en el límite EXACTO, D2 tiene que usar '>', nunca '>=' (igual que D1).
    Llama directo a la función pura: no depende de redondeo de video/audio real."""
    assert editar._huecos_escena({"duracion": 6.0, "puntos": []}, 6.0) == []


def test_hueco_de_apenas_mas_de_n_es_hallazgo():
    assert editar._huecos_escena({"duracion": 6.001, "puntos": []}, 6.0) == [(0.0, 6.001)]


# --- B6: el hueco también se mide desde 0, y una escena sin ninguna cue es hueco ---

def test_escena_sin_ninguna_cue_mas_larga_que_n_es_hallazgo(raiz):
    seg = {"escena": {"tipo": "presentacion"}, "texto": "a"}
    _guion(raiz, {"segmentos": [seg]})
    _spec_vigente(raiz, "argentina", 0, seg, tipo="presentacion", duracion=10.0, puntos=[])

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("00.json" in h and "sin elemento nuevo" in h for h in hallazgos)


def test_hueco_desde_el_0_hasta_la_primera_entrada_se_mide(raiz):
    seg = {"escena": {"tipo": "presentacion"}, "texto": "a"}
    _guion(raiz, {"segmentos": [seg]})
    _spec_vigente(raiz, "argentina", 0, seg, tipo="presentacion", duracion=10.0,
                  puntos=[{"texto": "a", "cue": "a", "t": 7.0}])

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("00.json" in h and "sin elemento nuevo" in h for h in hallazgos)


def test_sin_specs_resueltos_y_con_escena_en_el_guion_dice_que_no_corrio(raiz):
    _guion(raiz, {"segmentos": [{"escena": {"tipo": "presentacion"}, "texto": "a"}]})

    _, no_corrio = editar.revisar("v09", "argentina")

    assert any("specs resueltos" in m for m in no_corrio)


# --- B4: spec con cue sin "t" o sin "duracion": hallazgo/no_corrio claro, sin traceback ---

def test_spec_con_cue_sin_t_dice_que_no_corrio_nombrando_el_archivo(raiz):
    seg = {"escena": {"tipo": "presentacion"}, "texto": "a"}
    _guion(raiz, {"segmentos": [seg]})
    _spec_vigente(raiz, "argentina", 0, seg, tipo="presentacion", duracion=10.0,
                  puntos=[{"texto": "a", "cue": "a"}])  # sin "t": no se resolvió

    hallazgos, no_corrio = editar.revisar("v09", "argentina")

    assert any("00.json" in m for m in no_corrio)
    assert not any("00.json" in h for h in hallazgos)


def test_spec_sin_duracion_dice_que_no_corrio_nombrando_el_archivo(raiz):
    seg = {"escena": {"tipo": "presentacion"}, "texto": "a"}
    _guion(raiz, {"segmentos": [seg]})
    _spec_vigente(raiz, "argentina", 0, seg, tipo="presentacion",
                  puntos=[{"texto": "a", "cue": "a", "t": 1.0}])  # sin "duracion"

    hallazgos, no_corrio = editar.revisar("v09", "argentina")

    assert any("00.json" in m for m in no_corrio)
    assert not any("00.json" in h for h in hallazgos)


# --- NOTE 5: spec JSON roto o con "duracion" no numérica: no_corrio, no traceback --

def test_spec_con_json_invalido_dice_que_no_corrio_nombrando_el_archivo(raiz):
    seg = {"escena": {"tipo": "presentacion"}, "texto": "a"}
    _guion(raiz, {"segmentos": [seg]})
    escenas_dir = raiz / "videos" / "v09" / "escenas"
    escenas_dir.mkdir(parents=True)
    (escenas_dir / "00.json").write_text("{ esto no es json")

    hallazgos, no_corrio = editar.revisar("v09", "argentina")

    assert any("00.json" in m and "JSON inválido" in m for m in no_corrio)
    assert not any("00.json" in h for h in hallazgos)


def test_spec_con_duracion_no_numerica_dice_que_no_corrio_nombrando_el_archivo(raiz):
    seg = {"escena": {"tipo": "presentacion"}, "texto": "a"}
    _guion(raiz, {"segmentos": [seg]})
    _spec_vigente(raiz, "argentina", 0, seg, tipo="presentacion", duracion="10",
                  puntos=[{"texto": "a", "cue": "a", "t": 1.0}])

    hallazgos, no_corrio = editar.revisar("v09", "argentina")

    assert any("00.json" in m for m in no_corrio)
    assert not any("00.json" in h for h in hallazgos)


# --- B5/B5-bis: sólo se miden los specs que corresponden al guion y la voz de hoy -

def test_spec_de_un_segmento_que_ya_no_es_escena_se_ignora(raiz):
    """También fija N19: con dos segmentos donde sólo el de índice 1 es escena,
    un spec viejo en 00.json (índice que HOY no es escena) no puede filtrarse: si
    `_specs_escena_vigentes` mirara todos los índices (mutante `range(100)`) en vez
    de sólo los que son escena, este "00.json" aparecería en algún lado."""
    seg_normal = {"inicio": 0, "fin": 1, "texto": "a"}
    seg_escena = {"escena": {"tipo": "presentacion"}, "texto": "b"}
    _guion(raiz, {"segmentos": [seg_normal, seg_escena]})
    escenas_dir = raiz / "videos" / "v09" / "escenas"
    escenas_dir.mkdir(parents=True)
    # spec viejo en el índice que HOY no es escena: nunca debería mirarse
    (escenas_dir / "00.json").write_text(json.dumps({"duracion": 10.0, "puntos": []}))
    _spec_vigente(raiz, "argentina", 1, seg_escena, tipo="presentacion", duracion=1.0, puntos=[])

    hallazgos, no_corrio = editar.revisar("v09", "argentina")

    assert not any("00.json" in h for h in hallazgos)
    assert not any("00.json" in m for m in no_corrio)


def test_escena_sin_spec_dice_que_no_corrio_sin_saltearla_en_silencio(raiz):
    """BLOCKING B5-bis (R-5.6): una escena del guion de HOY sin ningún spec en
    escenas/ no puede saltearse en silencio; tiene que decir "no corrió" para ESE
    índice, nombrándolo."""
    seg0 = {"escena": {"tipo": "presentacion"}, "texto": "a", "rol": "gancho"}
    seg1 = {"texto": "b", "rol": "analogia"}
    seg2 = {"escena": {"tipo": "presentacion"}, "texto": "c", "rol": "ejemplo"}
    seg3 = {"texto": "d", "rol": "repaso"}
    _guion(raiz, {"segmentos": [seg0, seg1, seg2, seg3]})
    # sólo hay spec para la escena 00; la escena 02 no tiene ningún spec
    _spec_vigente(raiz, "argentina", 0, seg0, tipo="presentacion", duracion=4.0,
                  puntos=[{"cue": "x", "t": 2.0}])

    hallazgos, no_corrio = editar.revisar("v09", "argentina")

    assert any("02.json" in m and "falta el spec" in m for m in no_corrio)
    assert not any("sin hallazgos" in h for h in hallazgos)  # no es "informe vacío"


def test_spec_desactualizado_por_el_guion_dice_que_no_corrio(raiz):
    """NOTE 2: un spec viejo cuyos slots (en el diseño anterior) también eran
    viejos coincidía igual. Ahora el spec queda atado al CONTENIDO del segmento
    (hash), no a un número de duración: si el guion cambió, no coincide más,
    aunque nadie haya tocado `slots-<voz>.json`."""
    seg_viejo = {"escena": {"tipo": "presentacion"}, "texto": "texto viejo"}
    seg_nuevo = {"escena": {"tipo": "presentacion"}, "texto": "texto nuevo, el guion cambió"}
    _spec_vigente(raiz, "argentina", 0, seg_viejo, tipo="presentacion", duracion=10.0, puntos=[])
    _guion(raiz, {"segmentos": [seg_nuevo]})  # el guion de HOY ya no es seg_viejo

    hallazgos, no_corrio = editar.revisar("v09", "argentina")

    assert not any("00.json" in h for h in hallazgos)
    assert any("00.json" in m and "desactualizado" in m for m in no_corrio)


def test_spec_de_otra_voz_sin_imagen_previa_no_se_mide(raiz):
    """NOTE 3a/4: un spec generado por `escenas()` para OTRA voz, sin que
    `imagen` haya corrido nunca para la voz pedida (o sea, sin
    `slots-<voz>.json`), no se mide igual. El remedio correcto es correr
    `escenas` (que es quien etiqueta el spec), no `imagen` (NOTE 4)."""
    seg = {"escena": {"tipo": "presentacion"}, "texto": "a"}
    _guion(raiz, {"segmentos": [seg]})
    _spec_vigente(raiz, "profe", 0, seg, tipo="presentacion", duracion=10.0, puntos=[])  # para "profe"

    hallazgos, no_corrio = editar.revisar("v09", "argentina")  # pedido para "argentina"

    assert not any("00.json" in h for h in hallazgos)
    problema = next(m for m in no_corrio if "00.json" in m)
    assert "no corresponde a la voz" in problema
    assert "editar.py escenas" in problema  # NOTE 4: el remedio correcto, no 'imagen'


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


def test_silencio_de_mas_de_0_9s_pero_menos_del_mutante_se_reporta(raiz, tmp_path):
    """M6: entre 0.9s (correcto) y 1.15s (mutante), un silencio de 1.0s tiene que
    reportarse."""
    habla = tmp_path / "habla.wav"
    silencio = tmp_path / "silencio.wav"
    _clip(habla, "sine=f=300:d=1")
    _clip(silencio, "anullsrc=r=22050:cl=mono:d=1.0")
    _concat_wav(raiz / "videos" / "v09" / "voz-argentina.wav", [habla, silencio, habla])
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("silencio" in h for h in hallazgos)


def test_voz_baja_pero_con_contenido_no_se_confunde_con_silencio(raiz, tmp_path):
    """M7: silencedetect usa un umbral de sensibilidad estricto (-40dB). Un tramo con
    voz de verdad pero floja (RMS ~ -31dB) no es silencio; con un umbral más laxo
    (-20dB, mutante) se confundiría con silencio."""
    habla = tmp_path / "habla.wav"
    floja = tmp_path / "floja.wav"
    _clip(habla, "sine=f=300:d=1")
    _clip(floja, "sine=frequency=300:duration=1.5,volume=-10dB")
    _concat_wav(raiz / "videos" / "v09" / "voz-argentina.wav", [habla, floja, habla])
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert not any("silencio" in h for h in hallazgos)


# --- NOTE 1: ffmpeg que falla (wav vacío/corrupto) no es "sin hallazgos" ----------

def test_wav_vacio_o_corrupto_dice_que_no_corrio_con_la_causa(raiz):
    (raiz / "videos" / "v09" / "voz-argentina.wav").touch()  # 0 bytes: ffmpeg falla
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    hallazgos, no_corrio = editar.revisar("v09", "argentina")

    assert not any("silencio" in h for h in hallazgos)  # NUNCA "sin hallazgos" por error
    assert any("voz-argentina.wav" in m and "no corrió" in m for m in no_corrio)


# --- Decisión pendiente de Juani (#2, HITO2.md): D3 con voces FISH_LENTAS --------
#
# El pipeline real (preparar(), editar.py) deja LEAD (0.3s, línea ~64: silencio
# antes de que arranque la voz en cada slot) + cola (1.0s para las voces de
# FISH_LENTAS, fijado en la línea ~430 de preparar()) = 1.3s de silencio "de
# diseño" en CADA borde entre segmentos. Como 1.3s > 0.9s (el umbral de D3),
# `revisar` marca TODOS esos bordes como silencio. Este test documenta el
# comportamiento ACTUAL sin resolver la decisión: si Juani decide que D3 no
# tiene que contar ese silencio de diseño para las voces FISH_LENTAS, el cambio
# es sólo en CHEQUEOS["D3"]/_silencios (o en cómo revisar() los llama), y este
# test es el que hay que actualizar primero.

def test_fish_lentas_deja_1_3s_de_silencio_entre_segmentos_y_d3_lo_marca(raiz, tmp_path):
    assert "profe" in editar.FISH_LENTAS  # profe es una voz de FISH_LENTAS
    gap = editar.LEAD + editar._cola("profe")  # NOTE 11: misma fuente que preparar()
    habla = tmp_path / "habla.wav"
    silencio = tmp_path / "silencio.wav"
    _clip(habla, "sine=f=300:d=1")
    _clip(silencio, f"anullsrc=r=22050:cl=mono:d={gap:.2f}")
    _concat_wav(raiz / "videos" / "v09" / "voz-profe.wav", [habla, silencio, habla, silencio, habla])
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a"},
        {"inicio": 1, "fin": 2, "texto": "b"},
        {"inicio": 2, "fin": 3, "texto": "c"}]})

    hallazgos, _ = editar.revisar("v09", "profe")

    silencios = [h for h in hallazgos if "silencio" in h]
    assert len(silencios) == 2  # los DOS bordes entre los 3 segmentos, todos marcados


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


def test_sin_ningun_ejemplo_se_reporta(raiz):
    """M5: si se borra este chequeo, falta ejemplo deja de reportarse."""
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a", "rol": "gancho"},
        {"inicio": 1, "fin": 2, "texto": "b", "rol": "analogia"},
        {"inicio": 2, "fin": 3, "texto": "c", "rol": "repaso"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("ejemplo" in h for h in hallazgos)


def test_gancho_que_no_esta_primero_se_reporta_aunque_este_en_otra_posicion(raiz):
    """M13: 'gancho' tiene que ser el PRIMER segmento, no estar en cualquier posición."""
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a", "rol": "analogia"},
        {"inicio": 1, "fin": 2, "texto": "b", "rol": "gancho"},
        {"inicio": 2, "fin": 3, "texto": "c", "rol": "ejemplo"},
        {"inicio": 3, "fin": 4, "texto": "d", "rol": "repaso"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("primer segmento no es 'gancho'" in h for h in hallazgos)


# --- B7: rol desconocido avisa, y se normalizan mayúsculas/tildes ------------------

def test_rol_desconocido_avisa_con_los_roles_validos(raiz):
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a", "rol": "gancho"},
        {"inicio": 1, "fin": 2, "texto": "b", "rol": "profesor"},
        {"inicio": 2, "fin": 3, "texto": "c", "rol": "ejemplo"},
        {"inicio": 3, "fin": 4, "texto": "d", "rol": "repaso"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("rol desconocido 'profesor'" in h and "gancho, analogia, ejemplo, repaso" in h
               for h in hallazgos)


def test_rol_con_mayusculas_y_tildes_se_normaliza_con_aviso(raiz):
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a", "rol": "gancho"},
        {"inicio": 1, "fin": 2, "texto": "b", "rol": "Analogía"},
        {"inicio": 2, "fin": 3, "texto": "c", "rol": "ejemplo"},
        {"inicio": 3, "fin": 4, "texto": "d", "rol": "repaso"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("'Analogía'" in h and "'analogia'" in h for h in hallazgos)
    assert not any("no hay ningún segmento con rol 'analogia'" in h for h in hallazgos)


def test_rol_con_espacios_se_normaliza_sin_romper(raiz):
    """N4: si se borra el .strip() de _normalizar_rol, 'analogia ' (con espacio)
    queda como rol desconocido en vez de normalizarse a 'analogia'."""
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a", "rol": "gancho"},
        {"inicio": 1, "fin": 2, "texto": "b", "rol": "analogia "},
        {"inicio": 2, "fin": 3, "texto": "c", "rol": "ejemplo"},
        {"inicio": 3, "fin": 4, "texto": "d", "rol": "repaso"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert not any("rol desconocido" in h for h in hallazgos)
    assert not any("no hay ningún segmento con rol 'analogia'" in h for h in hallazgos)


def test_rol_no_textual_se_informa_sin_romper(raiz):
    """NOTE 5: un rol que no es texto (p.ej. 1, por un guion mal armado) no puede
    tirar un AttributeError al intentar normalizarlo."""
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a", "rol": "gancho"},
        {"inicio": 1, "fin": 2, "texto": "b", "rol": 1},
        {"inicio": 2, "fin": 3, "texto": "c", "rol": "ejemplo"},
        {"inicio": 3, "fin": 4, "texto": "d", "rol": "repaso"}]})

    hallazgos, _ = editar.revisar("v09", "argentina")

    assert any("rol inválido" in h and "1" in h for h in hallazgos)


# --- NOTE 10: un aviso de normalización no cuenta como hallazgo para --estricto ---

def test_estricto_no_falla_solo_por_un_rol_con_tildes_bien_escrito(raiz, monkeypatch, capsys):
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a", "rol": "gancho"},
        {"inicio": 1, "fin": 2, "texto": "b", "rol": "Analogía"},
        {"inicio": 2, "fin": 3, "texto": "c", "rol": "ejemplo"},
        {"inicio": 3, "fin": 4, "texto": "d", "rol": "repaso"}]})

    _, code = _correr_cli(raiz, monkeypatch, capsys, ["--estricto"])

    assert code == 0


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


# --- B8: vNN inexistente, sin argumentos, --estricto antes del vid ----------------

def _correr_cli_argv(raiz, monkeypatch, capsys, argv_despues_de_revisar):
    import runpy
    import sys
    from pathlib import Path
    monkeypatch.setenv("TUT_ROOT", str(raiz))
    monkeypatch.setattr(sys, "argv", ["editar.py", "revisar", *argv_despues_de_revisar])
    code = None
    try:
        runpy.run_path(str(Path(editar.__file__)), run_name="__main__")
    except SystemExit as e:
        code = e.code
    captura = capsys.readouterr()
    return captura.out, captura.err, (0 if code is None else code)


def test_revisar_sin_argumentos_da_mensaje_claro_y_uso(raiz, monkeypatch, capsys):
    _, err, code = _correr_cli_argv(raiz, monkeypatch, capsys, [])

    assert code != 0
    assert "uso" in err.lower()


def test_revisar_con_vnn_inexistente_da_mensaje_claro(raiz, monkeypatch, capsys):
    _, err, code = _correr_cli_argv(raiz, monkeypatch, capsys, ["v99"])

    assert code != 0
    assert "v99" in err


def test_revisar_con_flag_desconocido_es_error_no_se_ignora(raiz, monkeypatch, capsys):
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    _, err, code = _correr_cli_argv(raiz, monkeypatch, capsys, ["v09", "--estrict"])

    assert code != 0
    assert "--estrict" in err


def test_estricto_antes_del_vid_tambien_hace_fallar_con_hallazgos(raiz, monkeypatch, capsys):
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    _, _, code = _correr_cli_argv(raiz, monkeypatch, capsys, ["--estricto", "v09"])

    assert code == 1


def test_revisar_con_guion_corto_no_se_cuela_como_voz(raiz, monkeypatch, capsys):
    """NOTE 6: 'revisar v09 -e' no puede tomar '-e' como si fuera la voz."""
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    _, err, code = _correr_cli_argv(raiz, monkeypatch, capsys, ["v09", "-e"])

    assert code != 0
    assert "-e" in err


def test_revisar_con_demasiados_argumentos_es_error(raiz, monkeypatch, capsys):
    """NOTE 6: 'revisar v09 argentina extra' no puede ignorar 'extra' en silencio."""
    _guion(raiz, {"segmentos": [{"inicio": 0, "fin": 1, "texto": "a"}]})

    _, err, code = _correr_cli_argv(raiz, monkeypatch, capsys, ["v09", "argentina", "extra"])

    assert code != 0
    assert "extra" in err


# --- B3c (decisión pendiente): hoy --estricto NO falla si algo no corrió ----------

def test_estricto_no_falla_solo_porque_un_chequeo_no_corrio(raiz, monkeypatch, capsys):
    """Política actual (B3c, pendiente de decisión de Juani): `_estricto_falla` sólo
    mira `hallazgos`, nunca `no_corrio`. Guion con roles completos (sin hallazgo de
    D4) y SIN ningún artefacto (D1/D2/D3 "no corrieron"): --estricto sale con 0."""
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a", "rol": "gancho"},
        {"inicio": 1, "fin": 2, "texto": "b", "rol": "analogia"},
        {"inicio": 2, "fin": 3, "texto": "c", "rol": "ejemplo"},
        {"inicio": 3, "fin": 4, "texto": "d", "rol": "repaso"}]})

    _, code = _correr_cli(raiz, monkeypatch, capsys, ["--estricto"])

    assert code == 0


# --- M12: --estricto tiene que fallar también por hallazgos de D1-D3, no sólo D4 --

def test_estricto_falla_por_un_hallazgo_de_tiempo_muerto_sin_que_haya_problema_de_roles(
        raiz, monkeypatch, capsys, tmp_path):
    clip = tmp_path / "clip.mp4"
    quieto = tmp_path / "quieto.mp4"
    _clip(clip, "testsrc=s=320x240:r=30:d=1,format=yuv420p")
    _clip(quieto, "color=c=black:s=320x240:r=30:d=8")
    _concat_video(raiz / "videos" / "v09" / "video-argentina.mp4", [clip, quieto, clip])
    _guion(raiz, {"segmentos": [
        {"inicio": 0, "fin": 1, "texto": "a", "rol": "gancho"},
        {"inicio": 1, "fin": 2, "texto": "b", "rol": "analogia"},
        {"inicio": 2, "fin": 3, "texto": "c", "rol": "ejemplo"},
        {"inicio": 3, "fin": 4, "texto": "d", "rol": "repaso"}]})

    _, code = _correr_cli(raiz, monkeypatch, capsys, ["--estricto"])

    assert code == 1
