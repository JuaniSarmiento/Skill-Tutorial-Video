"""Segmentos de guion que son escenas en vez de cortes del crudo (editar.py).

Un segmento con "escena": {"tipo": ..., ...} se renderiza con el motor de
escenas y dura exactamente su slot, igual que un tramo de pantalla. Las cues
del spec se resuelven contra la voz de ESE segmento, que en el slot arranca
después de LEAD segundos de silencio.
"""
import json
import subprocess

import pytest

import editar
import escena
import palabras


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    monkeypatch.setattr(editar, "ROOT", tmp_path)
    (tmp_path / "guion").mkdir()
    return tmp_path


def _guion(raiz, vid, g):
    (raiz / "guion" / f"{vid}.json").write_text(json.dumps(g))


ESCENA = {"tipo": "presentacion", "titulo": {"texto": "Hola"},
          "puntos": [{"texto": "Sol", "cue": "el sol"}, {"texto": "Fin", "cue": 1.0}]}
VOZ = [{"palabra": "Mirá", "inicio": 0.0, "fin": 0.3},
       {"palabra": "el", "inicio": 0.3, "fin": 0.4},
       {"palabra": "sol.", "inicio": 0.4, "fin": 0.9}]


# --- crudos ------------------------------------------------------------------

def test_un_guion_solo_de_escenas_no_necesita_crudo(raiz):
    g = {"segmentos": [{"escena": ESCENA, "texto": "Mirá el sol."}]}
    assert editar.crudo_faltante(g) is None


def test_un_segmento_de_pantalla_sin_crudo_sigue_frenando(raiz):
    g = {"segmentos": [{"escena": ESCENA, "texto": "a"}, {"inicio": 0, "fin": 3, "texto": "b"}]}
    assert editar.crudo_faltante(g) == (1, None)


def test_un_crudo_que_no_existe_se_reporta_con_su_ruta(raiz):
    g = {"raw": "raw/v01.mp4", "segmentos": [{"inicio": 0, "fin": 3, "texto": "b"}]}
    assert editar.crudo_faltante(g) == (0, raiz / "raw/v01.mp4")


# --- spec de la escena -------------------------------------------------------

def test_la_escena_dura_el_slot_y_sus_cues_caen_donde_suena_la_palabra():
    spec = editar.spec_de_escena({"escena": ESCENA, "texto": "Mirá el sol."}, 4.2, VOZ)

    assert spec["duracion"] == 4.2
    assert spec["puntos"][0]["t"] == pytest.approx(0.3 + editar.LEAD)   # "el sol" suena a 0.3 del wav
    assert spec["puntos"][1]["t"] == 1.0                                 # en segundos: desde el inicio del slot


def test_una_escena_sin_tipo_falla_diciendo_cual_falta():
    with pytest.raises(ValueError, match="tipo"):
        editar.spec_de_escena({"escena": {"titulo": "x"}, "texto": "x"}, 3.0, VOZ)


# B8 (QA 04/10/2026): el mensaje listaba los tipos de escena sin "imagen".
def test_una_escena_sin_tipo_lista_imagen_entre_los_tipos_validos():
    with pytest.raises(ValueError, match="imagen"):
        editar.spec_de_escena({"escena": {"titulo": "x"}, "texto": "x"}, 3.0, VOZ)


def test_la_escena_del_guion_no_se_modifica():
    # literal propio: comparar contra ESCENA no sirve si otro test ya lo contaminó
    seg = {"escena": {"tipo": "presentacion", "puntos": [{"texto": "Sol", "cue": "el sol"}]}, "texto": "x"}
    editar.spec_de_escena(seg, 4.2, VOZ)
    assert seg["escena"] == {"tipo": "presentacion", "puntos": [{"texto": "Sol", "cue": "el sol"}]}


# --- N3 (QA 04/10/2026): "svg" relativo de un guion se resuelve contra ROOT, no contra el ----
# cwd (build_segment) ni contra el directorio del spec intermedio (escena.py contacto). El
# spec que deja editar.py escenas/build_segment lo escribe ABSOLUTO: así el paso de contacto
# documentado en SKILL.md (resolver contra el directorio DEL SPEC) también funciona.

def test_svg_relativo_de_una_escena_imagen_se_resuelve_contra_root(raiz):
    (raiz / "dibujos").mkdir()
    (raiz / "dibujos" / "a.svg").write_text("<svg></svg>")
    escena_imagen = {"tipo": "imagen", "titulo": {"texto": "x"},
                      "dibujos": [{"id": "a", "svg": "dibujos/a.svg", "cue": 0.1}]}

    spec = editar.spec_de_escena({"escena": escena_imagen, "texto": "x"}, 3.0, VOZ)

    assert spec["dibujos"][0]["svg"] == str((raiz / "dibujos" / "a.svg").resolve())


def test_svg_absoluto_de_una_escena_imagen_no_se_toca(raiz):
    p = raiz / "fuera" / "a.svg"
    p.parent.mkdir()
    p.write_text("<svg></svg>")
    escena_imagen = {"tipo": "imagen", "titulo": {"texto": "x"},
                      "dibujos": [{"id": "a", "svg": str(p), "cue": 0.1}]}

    spec = editar.spec_de_escena({"escena": escena_imagen, "texto": "x"}, 3.0, VOZ)

    assert spec["dibujos"][0]["svg"] == str(p)


def test_la_escena_imagen_del_guion_no_se_modifica_con_el_svg(raiz):
    (raiz / "dibujos").mkdir()
    (raiz / "dibujos" / "a.svg").write_text("<svg></svg>")
    seg = {"escena": {"tipo": "imagen", "dibujos": [{"id": "a", "svg": "dibujos/a.svg", "cue": 0.1}]},
           "texto": "x"}

    editar.spec_de_escena(seg, 3.0, VOZ)

    assert seg["escena"]["dibujos"][0]["svg"] == "dibujos/a.svg"


# --- palabras de la voz, cacheadas -------------------------------------------

def test_las_palabras_se_transcriben_una_vez_y_se_cachean_junto_al_wav(tmp_path, monkeypatch):
    wav = tmp_path / "03.wav"
    wav.write_bytes(b"x")
    llamadas = []
    monkeypatch.setattr(palabras, "transcribir", lambda a, modelo=None: llamadas.append(a) or VOZ)

    assert editar.palabras_de_voz(wav) == VOZ
    assert editar.palabras_de_voz(wav) == VOZ
    assert len(llamadas) == 1
    assert json.loads((tmp_path / "03.palabras.json").read_text()) == VOZ


def test_si_la_voz_cambio_despues_del_cache_se_vuelve_a_transcribir(tmp_path, monkeypatch):
    import os
    wav = tmp_path / "03.wav"
    wav.write_bytes(b"x")
    cache = tmp_path / "03.palabras.json"
    cache.write_text(json.dumps([{"palabra": "viejo", "inicio": 0, "fin": 1}]))
    os.utime(cache, (1_000_000, 1_000_000))            # el cache es más viejo que el wav
    monkeypatch.setattr(palabras, "transcribir", lambda a, modelo=None: VOZ)

    assert editar.palabras_de_voz(wav) == VOZ


def test_un_wav_con_otro_contenido_pero_fecha_vieja_se_vuelve_a_transcribir(tmp_path, monkeypatch):
    # cp -p o el unzip del export de Colab dejan la fecha vieja: la fecha no dice si la voz cambió
    import os
    wav = tmp_path / "03.wav"
    wav.write_bytes(b"voz vieja")
    monkeypatch.setattr(palabras, "transcribir",
                        lambda a, modelo=None: [{"palabra": a.read_bytes().decode(), "inicio": 0, "fin": 1}])
    editar.palabras_de_voz(wav)
    wav.write_bytes(b"voz nueva")
    os.utime(wav, (1_000_000, 1_000_000))

    assert editar.palabras_de_voz(wav)[0]["palabra"] == "voz nueva"


# --- build_segment -----------------------------------------------------------

def test_un_segmento_de_escena_se_renderiza_con_el_motor_y_no_corta_el_crudo(raiz, monkeypatch):
    llamadas = []
    monkeypatch.setattr(escena, "render", lambda plantilla, spec, salida, brand=None, **kw:
                        llamadas.append((plantilla, spec, salida, brand)) or spec["duracion"])
    monkeypatch.setattr(editar, "run", lambda cmd: pytest.fail(f"no debía llamar a ffmpeg: {cmd[:4]}"))
    out = raiz / "seg" / "02.mp4"

    editar.build_segment("v01", None, {"escena": ESCENA, "texto": "Mirá el sol."}, 4.2, out, VOZ)

    (plantilla, spec, salida, brand), = llamadas
    assert plantilla.name == "presentacion.html"
    assert spec["duracion"] == 4.2
    assert salida == out
    assert brand["colores"]["acento"] == escena.cargar_brand(None)["colores"]["acento"]


def test_el_brand_de_la_serie_vive_en_la_raiz_del_tutorial(raiz, monkeypatch):
    (raiz / "brand.json").write_text(json.dumps({"colores": {"acento": "#00AA88"}}))
    llamadas = []
    monkeypatch.setattr(escena, "render", lambda plantilla, spec, salida, brand=None, **kw: llamadas.append(brand))

    editar.build_segment("v01", None, {"escena": ESCENA, "texto": "x"}, 4.2, raiz / "o.mp4", VOZ)

    assert llamadas[0]["colores"]["acento"] == "#00AA88"


# --- editar.py escenas: preparar sin renderizar ------------------------------

def test_escenas_deja_cada_spec_resuelto_para_la_hoja_de_contacto(raiz, monkeypatch):
    wav = raiz / "voz.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=d=2", str(wav)], check=True)
    monkeypatch.setattr(editar, "voice_wav", lambda vid, voz, i, texto: wav)
    monkeypatch.setattr(palabras, "transcribir", lambda a, modelo=None: VOZ)
    # velocidad_voz 1.0: este test no prueba aceleración, y "argentina" (TTS) la trae
    # a 1.25 por default (ver test_editar_velocidad_voz.py), que movería la duración de abajo.
    _guion(raiz, "v09", {"velocidad_voz": 1.0,
                         "segmentos": [{"escena": ESCENA, "texto": "Mirá el sol."},
                                       {"escena": {**ESCENA, "tipo": "datos", "barras": []}, "texto": "x"}]})

    rutas = editar.escenas("v09", "argentina")

    assert [r.name for r in rutas] == ["00.json", "01.json"]
    spec = json.loads(rutas[0].read_text())
    assert spec["tipo"] == "presentacion"
    assert spec["duracion"] > 2.0 + editar.LEAD          # el slot se mide con la voz
    assert spec["puntos"][0]["t"] == pytest.approx(0.3 + editar.LEAD)


# --- editar.py escenas por línea de comandos ---------------------------------

def _correr_cli(raiz, monkeypatch, capsys, segmentos):
    import runpy
    import sys
    from pathlib import Path
    (raiz / "videos" / "v09" / "juani").mkdir(parents=True)
    for i in range(len(segmentos)):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=d=1",
                        str(raiz / "videos" / "v09" / "juani" / f"{i:02d}.wav")], check=True)
    _guion(raiz, "v09", {"segmentos": segmentos})
    monkeypatch.setattr(palabras, "transcribir", lambda a, modelo=None: VOZ)
    monkeypatch.setenv("TUT_ROOT", str(raiz))
    monkeypatch.setattr(sys, "argv", ["editar.py", "escenas", "v09", "juani"])
    runpy.run_path(str(Path(editar.__file__)), run_name="__main__")
    return capsys.readouterr().out


def test_escenas_imprime_un_comando_de_contacto_que_anda_desde_cualquier_carpeta(raiz, monkeypatch, capsys):
    from pathlib import Path
    out = _correr_cli(raiz, monkeypatch, capsys, [{"escena": ESCENA, "texto": "Mirá el sol."}])
    linea = next(ln for ln in out.splitlines() if " contacto " in ln)
    assert str(Path(editar.__file__).resolve().parent / "escena.py") in linea
    assert str(raiz / "videos" / "v09" / "escenas" / "00.json") in linea


def test_escenas_sin_escenas_en_el_guion_no_imprime_un_comando_sin_specs(raiz, monkeypatch, capsys):
    out = _correr_cli(raiz, monkeypatch, capsys, [{"tipo": "titulo", "titulo": "Hola", "texto": "Hola."}])
    assert " contacto " not in out
    assert "no tiene escenas" in out


# --- H4: la escena codigo nombra archivos reales, relativos a ROOT como los svg ---------

def test_los_archivos_de_una_escena_codigo_se_resuelven_contra_root(raiz):
    seg = {"escena": {"tipo": "codigo", "archivo": "codigo/a.py",
                      "pasos": [{"modo": "diff", "archivo": "codigo/b.py", "cue": 0.5},
                                {"modo": "salida", "ejecutar": "codigo/c.py", "cue": 1.0}]}, "texto": "x"}

    spec = editar.spec_de_escena(seg, 3.0, VOZ)

    d = (raiz / "codigo").resolve()
    assert spec["archivo"] == str(d / "a.py")
    assert [spec["pasos"][0]["archivo"], spec["pasos"][1]["ejecutar"]] == [str(d / "b.py"), str(d / "c.py")]
    assert seg["escena"]["archivo"] == "codigo/a.py" and seg["escena"]["pasos"][0]["archivo"] == "codigo/b.py"


def test_un_archivo_absoluto_de_una_escena_codigo_no_se_toca(raiz):
    seg = {"escena": {"tipo": "codigo", "archivo": "/otra/a.py"}, "texto": "x"}
    assert editar.spec_de_escena(seg, 3.0, VOZ)["archivo"] == "/otra/a.py"


# --- H5: pila/arbol resuelven "archivo" contra ROOT, igual que codigo ----------------

def test_el_archivo_de_una_escena_pila_se_resuelve_contra_root(raiz):
    seg = {"escena": {"tipo": "pila", "archivo": "codigo/factorial.py", "llamada": "factorial(4)",
                      "pasos": [{"cue": 0.1 * i} for i in range(10)]}, "texto": "x"}
    spec = editar.spec_de_escena(seg, 4.0, VOZ)
    assert spec["archivo"] == str((raiz / "codigo" / "factorial.py").resolve())
    assert seg["escena"]["archivo"] == "codigo/factorial.py"


def test_el_archivo_de_una_escena_arbol_se_resuelve_contra_root(raiz):
    seg = {"escena": {"tipo": "arbol", "archivo": "codigo/fibonacci.py", "llamada": "fibonacci(5)",
                      "pasos": [{"cue": 0.1 * i} for i in range(15)]}, "texto": "x"}
    spec = editar.spec_de_escena(seg, 4.0, VOZ)
    assert spec["archivo"] == str((raiz / "codigo" / "fibonacci.py").resolve())


def test_un_archivo_absoluto_de_una_escena_pila_no_se_toca(raiz):
    seg = {"escena": {"tipo": "pila", "archivo": "/otra/f.py", "llamada": "f(1)",
                      "pasos": [{"cue": 0.1}]}, "texto": "x"}
    assert editar.spec_de_escena(seg, 3.0, VOZ)["archivo"] == "/otra/f.py"


# --- H5: pila/curva también se renderizan con el motor desde un segmento ------------

def test_un_segmento_de_escena_pila_se_renderiza_con_el_motor(raiz, monkeypatch):
    (raiz / "codigo").mkdir()
    (raiz / "codigo" / "factorial.py").write_text(
        "def factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n - 1)\n")
    llamadas = []
    monkeypatch.setattr(escena, "render", lambda plantilla, spec, salida, brand=None, **kw:
                        llamadas.append((plantilla, spec, salida)) or spec["duracion"])
    seg = {"escena": {"tipo": "pila", "archivo": "codigo/factorial.py", "llamada": "factorial(2)",
                      "pasos": [{"cue": 0.2 * i} for i in range(6)]}, "texto": "x"}

    editar.build_segment("v01", None, seg, 4.0, raiz / "o.mp4", VOZ)

    (plantilla, spec, salida), = llamadas
    assert plantilla.name == "pila.html"
    assert spec["archivo"] == str((raiz / "codigo" / "factorial.py").resolve())
    assert salida == raiz / "o.mp4"


def test_un_segmento_de_escena_curva_se_renderiza_con_el_motor(raiz, monkeypatch):
    llamadas = []
    monkeypatch.setattr(escena, "render", lambda plantilla, spec, salida, brand=None, **kw:
                        llamadas.append((plantilla, spec, salida)) or spec["duracion"])
    seg = {"escena": {"tipo": "curva",
                      "puntos": [{"x": 0, "y": 1000, "cue": "el sol"}, {"x": 30, "y": 17449, "cue": 1.0}]},
          "texto": "Mirá el sol."}

    editar.build_segment("v01", None, seg, 4.2, raiz / "o.mp4", VOZ)

    (plantilla, spec, salida), = llamadas
    assert plantilla.name == "curva.html"
    assert spec["puntos"][0]["t"] == pytest.approx(0.3 + editar.LEAD)
