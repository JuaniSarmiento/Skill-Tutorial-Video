"""Aceptación de HU-03: «clase con personaje» en la skill de shorts. Ver CONTRATO.md.

Correr desde la raíz de la skill (tarda: voz real con Fish y un render con Remotion):
    timeout 3600 uv run --with pytest --with pillow --with numpy pytest aceptacion/HU-03 -v

La biblioteca semilla (el profe y el aula) se copia del canal (HU-01/HU-02); si no está, falla.
C07 (Juani mira la demo) no se automatiza.
"""
import json
import re
import shlex
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

SKILL = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
CLASE = SKILL / "assets" / "scripts" / "clase.py"
SERIE = AQUI / "fixtures" / "serie"
FALSO = AQUI / "fixtures" / "generador_falso.py"
CANAL = Path.home() / "Proyectos" / "Skill-Tutorial-Video" / "canal-tiktok-youtube"
POSES_GUION = ["pensar", "senalar", "tipear", "festejar", "parado"]
OTRO_ARBOL = Path.home() / ".claude" / "skills" / "tutorial-video-agente"
OTRO_ARBOL_ESTADO = sorted([
    " M SKILL.md", " M assets/scripts/editar.py", " M references/escenas.md",
    " M references/guion-y-edicion.md", "?? assets/escenas/marcas.html",
    "?? assets/scripts/tests/test_editar_marcas.py", "?? assets/scripts/tests/test_editar_marcas_render.py",
    "?? assets/scripts/tests/test_escena_marcas_render.py",
])
W, H = 1080, 1920


# ---------- ayudas ----------

def sembrar(dest: Path) -> Path:
    """Biblioteca con el profe (vestuario base) y el aula, en el formato del contrato."""
    cat_canal = json.loads((CANAL / "video" / "src" / "personajes" / "catalogo.json").read_text())
    profe = [p for p in cat_canal["personajes"] if p["id"] == "profe"][0]
    pub = CANAL / "video" / "public"
    (dest / "personajes" / "profe" / "base").mkdir(parents=True)
    (dest / "fondos").mkdir()
    shutil.copy(pub / profe["referencia"], dest / "personajes" / "profe" / "referencia.png")
    poses = {}
    for nombre, p in profe["poses"].items():
        for cual in ("cerrada", "abierta"):
            shutil.copy(pub / p[cual], dest / "personajes" / "profe" / "base" / f"{nombre}-{cual}.png")
        poses[nombre] = {"cerrada": f"personajes/profe/base/{nombre}-cerrada.png",
                         "abierta": f"personajes/profe/base/{nombre}-abierta.png",
                         "boca": p["boca"], "prompt": p["prompt"]}
    shutil.copy(pub / "fondos" / "aula-pizarra.png", dest / "fondos" / "aula-pizarra.png")
    prompt_aula = json.loads((pub / "fondos" / "catalogo.json").read_text())["aula-pizarra.png"]
    cat = {"personajes": {"profe": {"referencia": "personajes/profe/referencia.png",
                                    "descripcion": "el profe del canal", "vestuarios": {"base": {"poses": poses}}}},
           "fondos": {"aula-pizarra": {"archivo": "fondos/aula-pizarra.png", "prompt": prompt_aula}}}
    (dest / "catalogo.json").write_text(json.dumps(cat, ensure_ascii=False, indent=2))
    return dest


def serie(dest: Path, **cambios) -> Path:
    shutil.copytree(SERIE, dest)
    g = json.loads((dest / "guion.json").read_text())
    g.update(cambios)
    (dest / "guion.json").write_text(json.dumps(g, ensure_ascii=False, indent=2))
    return dest


def correr(sub, root, reparto, log, *extra, falla=False, generador=None, timeout=1800):
    env = {**__import__("os").environ, "TUT_ROOT": str(root), "TUT_REPARTO": str(reparto),
           "GEN_LOG": str(log), "GEN_FALLA": "1" if falla else "0",
           "TUT_GENERADOR": generador or f"uv run -q --with pillow python {shlex.quote(str(FALSO))}"}
    assert CLASE.exists(), f"falta {CLASE}"
    return subprocess.run(["uv", "run", "-q", str(CLASE), sub, str(root / "guion.json"), *extra],
                          cwd=SKILL, env=env, capture_output=True, text=True, timeout=timeout)


def llamadas(log: Path):
    return [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []


def foto(d: Path):
    return {p.relative_to(d): p.read_bytes() for p in d.rglob("*") if p.is_file()}


def rgba(p: Path):
    return np.asarray(Image.open(p).convert("RGBA")).astype(int)


# ---------- C02: reparto ----------

@pytest.fixture
def bib(tmp_path):
    return sembrar(tmp_path / "reparto")


def test_c02_lo_existente_se_reusa_sin_generar(tmp_path, bib):
    r = correr("reparto", serie(tmp_path / "serie"), bib, tmp_path / "gen.log")
    assert r.returncode == 0, r.stdout + r.stderr
    assert llamadas(tmp_path / "gen.log") == [], "llamó al generador con todo ya en la biblioteca"
    for nombre in ("profe", "base", "aula-pizarra"):
        assert nombre in r.stdout, f"reparto no dice que resolvió {nombre}"


def test_c02_vestuario_nuevo_con_la_referencia(tmp_path, bib):
    log = tmp_path / "gen.log"
    raiz = serie(tmp_path / "serie", vestuario={"nombre": "invierno", "descripcion": "con bufanda roja y gorro de lana"})
    r = correr("reparto", raiz, bib, log)
    assert r.returncode == 0, r.stdout + r.stderr
    ll = llamadas(log)
    assert len(ll) == 2 * len(POSES_GUION), f"{len(ll)} imágenes generadas (esperadas {2 * len(POSES_GUION)}: cerrada y abierta por pose usada)"
    assert all(l["referencia"] for l in ll), "hay imágenes del personaje generadas sin referencia"
    assert any(x.endswith("personajes/profe/referencia.png") for x in ll[0]["referencia"]), \
        "la primera imagen no usa la referencia del profe"
    assert all("bufanda roja" in l["prompt"] for l in ll), "el prompt no lleva la descripción del vestuario"
    assert sum("boca abierta" in l["prompt"].lower() for l in ll) == len(POSES_GUION), "falta la versión con boca abierta"

    cat = json.loads((bib / "catalogo.json").read_text())
    vest = cat["personajes"]["profe"]["vestuarios"]
    assert set(vest["base"]["poses"]) >= set(POSES_GUION), "se perdió el vestuario base"
    poses = vest["invierno"]["poses"]
    assert set(poses) == set(POSES_GUION), f"poses del vestuario nuevo: {sorted(poses)}"
    for nombre, p in poses.items():
        assert "bufanda roja" in p["prompt"], f"{nombre}: el catálogo no guarda el prompt"
        c, a = rgba(bib / p["cerrada"]), rgba(bib / p["abierta"])
        assert c.shape == a.shape, f"{nombre}: cerrada y abierta de distinto tamaño"
        for img, cual in ((c, "cerrada"), (a, "abierta")):
            esquinas = [img[0, 0, 3], img[0, -1, 3], img[-1, 0, 3], img[-1, -1, 3]]
            assert max(esquinas) == 0, f"{nombre}-{cual}: el fondo no quedó transparente"
        x, y, w, h = p["boca"]
        assert w > 0 and h > 0 and x >= 0 and y >= 0 and x + w <= c.shape[1] and y + h <= c.shape[0], \
            f"{nombre}: boca {p['boca']} fuera de la imagen"
        dif = np.abs(c - a).sum(axis=2)
        adentro = dif[y:y + h, x:x + w].mean()
        dif[y:y + h, x:x + w] = 0
        assert adentro > 5, f"{nombre}: la caja de la boca no cubre lo que cambia"
        assert dif.mean() < 1, f"{nombre}: cerrada y abierta difieren fuera de la boca"

    correr("reparto", raiz, bib, log)
    assert len(llamadas(log)) == len(ll), "la segunda corrida volvió a generar"


def test_c02_fondo_nuevo(tmp_path, bib):
    log = tmp_path / "gen.log"
    raiz = serie(tmp_path / "serie", fondo={"nombre": "laboratorio",
                                            "descripcion": "un laboratorio de computación con una pizarra blanca"})
    r = correr("reparto", raiz, bib, log)
    assert r.returncode == 0, r.stdout + r.stderr
    ll = llamadas(log)
    assert len(ll) == 1 and "laboratorio de computación" in ll[0]["prompt"], f"llamadas: {ll}"
    f = json.loads((bib / "catalogo.json").read_text())["fondos"]["laboratorio"]
    assert (bib / f["archivo"]).is_file() and "laboratorio de computación" in f["prompt"]
    correr("reparto", raiz, bib, log)
    assert len(llamadas(log)) == 1, "la segunda corrida volvió a generar el fondo"


def test_c02_personaje_nuevo(tmp_path, bib):
    log = tmp_path / "gen.log"
    raiz = serie(tmp_path / "serie", personaje={"id": "profa",
                                                "descripcion": "una profesora de pelo corto violeta y anteojos"})
    r = correr("reparto", raiz, bib, log)
    assert r.returncode == 0, r.stdout + r.stderr
    ll = llamadas(log)
    assert len(ll) == 1 + 2 * len(POSES_GUION), f"{len(ll)} imágenes (esperadas referencia + 2 por pose)"
    assert "pelo corto violeta" in ll[0]["prompt"]
    for l in ll[1:]:
        assert any("referencia" in Path(x).name for x in l["referencia"]), "una pose no usa la referencia nueva"
    p = json.loads((bib / "catalogo.json").read_text())["personajes"]["profa"]
    assert (bib / p["referencia"]).is_file()
    assert set(p["vestuarios"]["base"]["poses"]) == set(POSES_GUION)


# ---------- N02 / N04 ----------

@pytest.mark.parametrize("modo", ["falla", "no-existe"])
def test_n02_generador_roto_no_toca_nada(tmp_path, bib, modo):
    antes = foto(bib)
    raiz = serie(tmp_path / "serie", vestuario={"nombre": "invierno", "descripcion": "con bufanda roja"})
    r = correr("reparto", raiz, bib, tmp_path / "gen.log", falla=(modo == "falla"),
               generador="/no/existe/generador" if modo == "no-existe" else None)
    assert r.returncode != 0, "con el generador roto, reparto salió con 0"
    assert "invierno" in r.stdout + r.stderr, "el error no dice qué falta"
    assert foto(bib) == antes, "tocó la biblioteca (catálogo o archivos a medias)"


def test_n04_pose_inexistente_falla_claro(tmp_path, bib):
    raiz = serie(tmp_path / "serie")
    g = json.loads((raiz / "guion.json").read_text())
    g["segmentos"][0]["pose"] = "bailar"
    (raiz / "guion.json").write_text(json.dumps(g, ensure_ascii=False))
    out = tmp_path / "x.mp4"
    r = correr("render", raiz, bib, tmp_path / "gen.log", "-o", str(out), falla=True)
    assert r.returncode != 0 and "bailar" in r.stdout + r.stderr, "no falló claro con la pose inexistente"
    assert not out.exists(), "renderizó igual"


# ---------- C01, C03-C06: render de punta a punta ----------

@pytest.fixture(scope="module")
def render(tmp_path_factory):
    t = tmp_path_factory.mktemp("e2e")
    bib = sembrar(t / "reparto")
    raiz = serie(t / "serie")
    log = t / "gen.log"
    r = correr("props", raiz, bib, log, "-o", str(t / "props.json"), falla=True)
    assert r.returncode == 0, f"props falló:\n{(r.stdout + r.stderr)[-2000:]}"
    out = t / "clase.mp4"
    r = correr("render", raiz, bib, log, "-o", str(out), falla=True, timeout=3000)
    assert r.returncode == 0, f"render falló:\n{(r.stdout + r.stderr)[-2000:]}"
    assert llamadas(log) == [], "el render llamó al generador con todo en la biblioteca"
    return {"video": out, "props": json.loads((t / "props.json").read_text()),
            "guion": json.loads((raiz / "guion.json").read_text()), "serie": raiz}


def info(video):
    r = subprocess.run(["ffprobe", "-v", "0", "-show_entries", "format=duration:stream=width,height,r_frame_rate",
                        "-of", "json", str(video)], capture_output=True, text=True)
    i = json.loads(r.stdout)
    v = [s for s in i["streams"] if "width" in s][0]
    return float(i["format"]["duration"]), v["width"], v["height"], v["r_frame_rate"]


def test_c01_vertical_30fps_duracion_de_la_voz(render):
    dur, w, h, fps = info(render["video"])
    assert (w, h) == (W, H), f"{w}×{h}"
    assert fps == "30/1", f"fps {fps}"
    assert abs(dur - render["props"]["duracion"]) <= 1, f"video {dur:.1f} s, voz {render['props']['duracion']:.1f} s"


def test_c03_codigo_y_salida_reales(render):
    f = render["serie"] / "codigo" / "edad.py"
    real = subprocess.run([sys.executable, str(f)], capture_output=True, text=True).stdout.splitlines()
    assert render["props"]["codigo"]["edad"] == f.read_text(), "el código mostrado no es el archivo"
    assert render["props"]["consola"]["edad"] == real, "la terminal no es la salida real"


def test_c04_poses_del_guion_y_boca_con_la_voz(render):
    p = render["props"]
    assert [s["pose"] for s in p["segmentos"]] == [s["pose"] for s in render["guion"]["segmentos"]]
    with wave.open(p["voz"]) as wv:
        sr, n = wv.getframerate(), wv.getnframes()
        a = np.frombuffer(wv.readframes(n), np.int16).reshape(-1, wv.getnchannels()).mean(axis=1)
    ven = int(sr * 0.02)
    rms = np.sqrt((a[: len(a) // ven * ven].reshape(-1, ven) ** 2).mean(axis=1))
    umbral = np.median(rms[rms > rms.max() * 0.05]) * 0.25
    boca = p["boca"]
    assert boca, "la boca nunca se abre"
    abierta = sum(f - i for i, f in boca)
    assert 0.15 * p["duracion"] <= abierta <= 0.9 * p["duracion"], f"boca abierta {abierta:.1f} s de {p['duracion']:.1f}"
    for i, f in boca:
        tramo = rms[int(i / 0.02): max(int(f / 0.02), int(i / 0.02) + 1)]
        assert tramo.mean() > umbral, f"la boca se abre en silencio ({i:.2f}-{f:.2f} s)"


def test_c05_ritmo(render):
    dur, *_ = info(render["video"])
    fps = 10
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(render["video"]), "-vf",
                        f"fps={fps},scale=270:480,format=gray", "-f", "rawvideo", "-"], capture_output=True, timeout=300)
    f = np.frombuffer(r.stdout, np.uint8).reshape(-1, 480, 270)[:, : int(1350 / H * 480), :].astype(int)
    cambia = (np.abs(np.diff(f, axis=0)) > 25).mean(axis=(1, 2)) > 0.005
    peor = actual = 0
    for c in cambia:
        actual = 0 if c else actual + 1
        peor = max(peor, actual)
    assert peor / fps <= 2.0, f"tramo de {peor / fps:.1f} s sin cambios"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(render["video"]), "-vf", "select='gt(scene,0.25)',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True, timeout=300)
    cortes = r.stderr.count("pts_time:")
    assert cortes >= dur / 8, f"{cortes} cortes en {dur:.0f} s"


def test_c06_audio(render):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(render["video"]), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=300)
    res = r.stderr[r.stderr.rfind("Summary:"):]
    mi, mtp = re.search(r"I:\s+(-?[\d.]+) LUFS", res), re.search(r"Peak:\s+(-?[\d.]+) dBFS", res)
    assert mi and mtp, "el video no tiene audio medible"
    i, tp = float(mi.group(1)), float(mtp.group(1))
    assert -17 <= i <= -15, f"loudness {i} LUFS"
    assert tp <= -1.5, f"pico {tp} dBFS"
    p = render["props"]
    assert Path(p["musica"]).is_file(), "no hay música"
    assert len(p["sfx"]) >= 3, f"{len(p['sfx'])} efectos"


# ---------- N01, N03, K01 ----------

def test_n01_suite_existente_en_verde():
    r = subprocess.run(["uv", "run", "-q", "--with", "pytest", "--with", "pillow", "--with", "numpy", "--with", "pygments",
                        "--with", "matplotlib", "pytest", "assets/scripts/tests", "-m", "not integracion", "-q"],
                       cwd=SKILL, capture_output=True, text=True, timeout=1800)
    assert r.returncode == 0, f"la suite existente falla:\n{r.stdout[-2000:]}"


def test_n03_no_toca_el_otro_arbol():
    r = subprocess.run(["git", "status", "--porcelain"], cwd=OTRO_ARBOL, capture_output=True, text=True)
    assert sorted(r.stdout.splitlines()) == OTRO_ARBOL_ESTADO, "cambió el estado de feat/marcas-sobre-pantalla"
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=OTRO_ARBOL, capture_output=True, text=True).stdout.strip()
    assert head == "f6c3b89543141d4adfb22aa8cbf03d479dc46ef1", "se commiteó en feat/marcas-sobre-pantalla"


def test_k01_documentado():
    guia = SKILL / "references" / "clase.md"
    assert guia.is_file(), "falta references/clase.md"
    texto = guia.read_text()
    for cosa in ("clase.py", "TUT_REPARTO", "TUT_GENERADOR", "vestuario", "fondo"):
        assert cosa in texto, f"la guía no explica {cosa}"
    assert "references/clase.md" in (SKILL / "SKILL.md").read_text(), "SKILL.md no rutea a la guía"
