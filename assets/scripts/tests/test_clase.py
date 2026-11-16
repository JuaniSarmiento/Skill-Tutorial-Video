"""Formato «clase» (references/clase.md): validación, reparto, cámara, boca y el envoltorio del
generador. Sin red, sin Codex y sin Remotion: el generador es un script falso de este archivo.
Lo que procesa imágenes necesita scipy (dependencia de clase.py): correr con --with scipy."""
import json
import subprocess
import sys
import textwrap
import wave
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

import clase
import generar_imagen
import reparto

FALSO = textwrap.dedent('''
    import argparse, json, os, sys
    from PIL import Image, ImageDraw
    p = argparse.ArgumentParser()
    p.add_argument("--prompt"); p.add_argument("--salida"); p.add_argument("--referencia", action="append", default=[])
    a = p.parse_args()
    with open(os.environ["LOG_FALSO"], "a") as f:
        f.write(json.dumps({"prompt": a.prompt, "referencia": a.referencia}) + "\\n")
    if os.environ.get("FALLA_FALSO") == "1" and "festejando" in a.prompt:
        sys.exit(1)
    im = Image.new("RGB", (600, 900), "white")
    d = ImageDraw.Draw(im)
    d.ellipse((200, 100, 400, 300), fill=(250, 210, 180), outline="black", width=6)
    d.rectangle((180, 300, 420, 760), fill=(150, 190, 230), outline="black", width=6)
    d.rectangle((210, 760, 290, 880), fill=(90, 90, 120), outline="black", width=6)
    d.rectangle((310, 760, 390, 880), fill=(90, 90, 120), outline="black", width=6)
    if "boca abierta" in a.prompt.lower():
        d.ellipse((260, 220, 340, 270), fill=(120, 30, 40), outline="black", width=4)
    else:
        d.line((270, 245, 330, 245), fill="black", width=6)
    im.save(a.salida)
''')


def guion(**cambios):
    g = {"formato": "clase", "personaje": "profe", "vestuario": "base", "fondo": "aula", "voz_id": "x",
         "segmentos": [{"texto": "Hola a todos, esto es una prueba.", "pose": "parado", "camara": "profe",
                        "escena": {"tipo": "pizarra", "texto": "Hola"}}]}
    g.update(cambios)
    return g


@pytest.fixture
def bib(tmp_path, monkeypatch):
    """Biblioteca con un personaje «profe» (vestuario base, pose parado) y un fondo «aula»."""
    b = tmp_path / "bib"
    (b / "personajes/profe/base").mkdir(parents=True)
    (b / "fondos").mkdir()
    for n in ("referencia.png", "base/parado-cerrada.png", "base/parado-abierta.png"):
        Image.new("RGBA", (960, 1440)).save(b / "personajes/profe" / n)
    fondo = Image.new("RGB", (1080, 1620), (250, 240, 220))
    ImageDraw.Draw(fondo).rectangle((60, 120, 1020, 860), fill="white")
    fondo.save(b / "fondos/aula.png")
    cat = {"personajes": {"profe": {"referencia": "personajes/profe/referencia.png", "vestuarios": {"base": {"poses": {
        "parado": {"cerrada": "personajes/profe/base/parado-cerrada.png", "abierta": "personajes/profe/base/parado-abierta.png",
                   "boca": [400, 400, 100, 80], "prompt": "p"}}}}}},
           "fondos": {"aula": {"archivo": "fondos/aula.png", "prompt": "f"}}}
    (b / "catalogo.json").write_text(json.dumps(cat))
    falso = tmp_path / "falso.py"
    falso.write_text(FALSO)
    monkeypatch.setenv("TUT_REPARTO", str(b))
    monkeypatch.setenv("TUT_GENERADOR", f"{sys.executable} {falso}")
    monkeypatch.setenv("LOG_FALSO", str(tmp_path / "log"))
    return b


def foto(d: Path):
    return {p.relative_to(d): p.read_bytes() for p in d.rglob("*") if p.is_file()}


# ---------- validación ----------

@pytest.mark.parametrize("cambio, texto", [
    ({"formato": "otro"}, "formato"),
    ({"voz_id": ""}, "voz_id"),
    ({"velocidad": 0}, "velocidad"),
    ({"segmentos": []}, "segmentos"),
])
def test_validar_rechaza_lo_basico(cambio, texto):
    with pytest.raises(SystemExit, match=texto):
        clase.validar(guion(**cambio))


def test_validar_rechaza_camara_y_escena_desconocidas():
    g = guion()
    g["segmentos"][0]["camara"] = "dron"
    with pytest.raises(SystemExit, match="dron"):
        clase.validar(g)
    g = guion()
    g["segmentos"][0]["escena"] = {"tipo": "codigo", "archivo": "nada"}
    with pytest.raises(SystemExit, match="nada"):
        clase.validar(g)


# ---------- reparto ----------

def test_planear_pose_desconocida_sin_descripcion_la_nombra(bib):
    g = guion()
    g["segmentos"][0]["pose"] = "bailar"
    with pytest.raises(SystemExit, match="bailar"):
        reparto.planear(g, reparto.leer_catalogo(bib))


def test_planear_pose_desconocida_con_descripcion_se_genera(bib):
    g = guion(poses={"bailar": "baila con los brazos arriba"})
    g["segmentos"][0]["pose"] = "bailar"
    pedido = reparto.planear(g, reparto.leer_catalogo(bib))
    assert pedido.poses_nuevas == ["bailar"]


def test_planear_lo_que_hay_no_pide_nada(bib):
    assert reparto.planear(guion(), reparto.leer_catalogo(bib)).vacio()


def test_planear_fondo_nuevo_sin_descripcion_falla(bib):
    with pytest.raises(SystemExit, match="playa"):
        reparto.planear(guion(fondo="playa"), reparto.leer_catalogo(bib))


def test_vestuario_nuevo_genera_cerrada_y_abierta_con_parche_de_boca(bib, tmp_path):
    pytest.importorskip("scipy")
    g = guion(vestuario={"nombre": "verano", "descripcion": "con remera amarilla"})
    g["segmentos"].append({**g["segmentos"][0], "pose": "senalar"})
    res = reparto.resolver(g, log=lambda *_: None)
    assert res["vestuario"] == "verano"
    llamadas = [json.loads(x) for x in (tmp_path / "log").read_text().splitlines()]
    assert len(llamadas) == 4
    assert all("remera amarilla" in x["prompt"] and x["referencia"] for x in llamadas)
    cat = json.loads((bib / "catalogo.json").read_text())
    for p in ("parado", "senalar"):
        f = cat["personajes"]["profe"]["vestuarios"]["verano"]["poses"][p]
        c = np.asarray(Image.open(bib / f["cerrada"])).astype(int)
        a = np.asarray(Image.open(bib / f["abierta"])).astype(int)
        x, y, w, h = f["boca"]
        dif = np.abs(c - a).sum(axis=2)
        assert dif[y:y + h, x:x + w].mean() > 5
        dif[y:y + h, x:x + w] = 0
        assert dif.max() == 0, "la abierta difiere de la cerrada fuera de la boca"
        assert c[0, 0, 3] == 0 and c.shape == (1440, 960, 4)


def test_generador_que_falla_a_mitad_no_toca_la_biblioteca(bib, monkeypatch):
    pytest.importorskip("scipy")
    monkeypatch.setenv("FALLA_FALSO", "1")
    antes = foto(bib)
    g = guion(vestuario={"nombre": "verano", "descripcion": "con remera"})
    g["segmentos"].append({**g["segmentos"][0], "pose": "festejar"})
    with pytest.raises(SystemExit, match="verano"):
        reparto.resolver(g, log=lambda *_: None)
    assert foto(bib) == antes


def test_detectar_pizarra_encuentra_el_rectangulo_blanco(bib):
    pytest.importorskip("scipy")
    x, y, w, h = reparto.detectar_pizarra(bib / "fondos/aula.png")
    assert abs(x - 60) <= 2 and abs(y - 120) <= 2 and abs(w - 961) <= 3 and abs(h - 741) <= 3


def test_detectar_pizarra_sin_pizarra_usa_la_de_defecto(tmp_path):
    pytest.importorskip("scipy")
    f = tmp_path / "f.png"
    Image.new("RGB", (1080, 1620), (200, 120, 120)).save(f)
    assert reparto.detectar_pizarra(f) == reparto.PIZARRA_DEFECTO


# ---------- tiempos, cámara y boca ----------

def test_alinear_usa_las_palabras_del_guion():
    oidas = [{"w": "Hola", "t0": 0.0, "t1": 0.3}, {"w": "mundo", "t0": 0.4, "t1": 0.8}]
    assert [p["w"] for p in clase.alinear("Hola, mundo", oidas, 1.0)] == ["Hola,", "mundo"]
    out = clase.alinear("Hola querido mundo", oidas, 1.0)
    assert [p["w"] for p in out] == ["Hola", "querido", "mundo"]
    assert all(a["t0"] <= b["t0"] for a, b in zip(out, out[1:]))


def test_buscar_cue_y_cue_inexistente():
    pal = [{"w": "Si", "t0": 1.0, "t1": 1.2}, {"w": "cambias", "t0": 1.3, "t1": 1.6}, {"w": "la", "t0": 1.7, "t1": 1.8},
           {"w": "edad,", "t0": 1.9, "t1": 2.2}]
    assert clase.buscar_cue(pal, "la edad", 0) == 1.7
    with pytest.raises(SystemExit, match="nombre"):
        clase.buscar_cue(pal, "nombre", 0)


def _info(inicio, fin, n=8):
    voz = inicio + 0.12
    pal = [{"w": f"p{k}", "t0": voz + k * (fin - voz - 0.3) / n, "t1": voz + (k + 0.8) * (fin - voz - 0.3) / n} for k in range(n)]
    return {"inicio": inicio, "fin": fin, "voz": voz, "dur": fin - voz - 0.22, "palabras": pal}


def test_planos_primer_plano_vuelve_al_general():
    seg = {"camara": "profe", "escena": {"tipo": "pizarra"}}
    planos = clase.planos_de(seg, _info(0, 3.5), 0)
    assert [p["camara"] for p in planos] == ["profe", "normal"]


def test_planos_lo_que_se_lee_no_se_tapa_con_un_primer_plano():
    for cam in ("normal", "pizarra"):
        planos = clase.planos_de({"camara": cam, "escena": {"tipo": "codigo"}}, _info(0, 6), 0)
        assert "profe" not in [p["camara"] for p in planos[1:]]


def test_planos_del_guion_mandan():
    info = _info(0, 6)
    seg = {"camara": "normal", "escena": {"tipo": "pizarra"}, "planos": [{"cue": "p3", "camara": "profe"}]}
    assert clase.planos_de(seg, info, 0) == [{"t": 0, "camara": "normal"}, {"t": info["palabras"][3]["t0"], "camara": "profe"}]


def test_boca_solo_con_voz(tmp_path):
    sr = 22050
    t = np.arange(sr * 2) / sr
    a = np.where((t > 0.5) & (t < 1.2), 0.5 * np.sin(2 * np.pi * 220 * t), 0.0)
    f = tmp_path / "v.wav"
    clase.escribir_wav(f, a, sr)
    tramos = clase.boca_de(f)
    assert tramos and all(0.45 <= i and f_ <= 1.25 for i, f_ in tramos)


def test_texto_para_voz_aplica_la_pronunciacion_del_guion():
    g = {"pronunciacion": {"while": "guáil"}}
    assert clase.texto_para_voz(g, "Con while y whilex.") == "Con guáil y whilex."


def test_efectos_sintetizados_no_saturan():
    pista = clase.pista_sfx(3.0, [{"tipo": x, "t": 0.2 * k} for k, x in enumerate(clase.SFX_TIPOS)])
    assert 0.05 < np.abs(pista).max() <= 0.9


# ---------- envoltorio de Codex (sin correrlo) ----------

def test_encargo_y_comando_de_codex(tmp_path):
    texto = generar_imagen.encargo("un profe", ["referencia-1.png"], "imagen.png")
    assert texto.startswith("Tarea única") and "referencia-1.png" in texto and "imagen.png" in texto
    cmd = generar_imagen.comando(tmp_path, [tmp_path / "referencia-1.png"])
    assert cmd[:2] == ["codex", "exec"] and cmd[-1] == "-" and "--sandbox" in cmd and "workspace-write" in cmd
    assert f"--image={tmp_path / 'referencia-1.png'}" in cmd


def test_sin_codex_falla_claro(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(generar_imagen.shutil, "which", lambda _: None)
    assert generar_imagen.main(["--prompt", "x", "--salida", str(tmp_path / "s.png")]) != 0
    assert "codex" in capsys.readouterr().err
    assert not (tmp_path / "s.png").exists()


def test_validar_cue_que_no_se_dice_falla_antes_de_la_voz():
    g = guion()
    g["segmentos"][0]["luego"] = [{"pose": "pensar", "cue": "chau"}]
    with pytest.raises(SystemExit, match="chau"):
        clase.validar(g)
    g["segmentos"][0]["luego"] = [{"pose": "pensar", "cue": "una prueba"}]
    clase.validar(g)
