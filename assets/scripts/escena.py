#!/usr/bin/env python3
"""Motor de escenas: un HTML + un spec JSON + un brand -> un .mp4 de duración exacta.

Una escena es una página con un contrato de dos piezas (el mismo de HyperFrames,
github.com/heygen-com/hyperframes, así migrar después es barato):

  window.DURATION      segundos que dura la escena
  async window.seek(t) deja la página EXACTAMENTE como se ve en el segundo t

Cada pixel es función pura de t: nada de Date.now, requestAnimationFrame, timers,
transiciones CSS ni Math.random sin semilla. Por eso el render no es en tiempo
real: se lleva la página a cada t, se saca un PNG y se le pasa a ffmpeg. El mismo
t da siempre el mismo cuadro, en cualquier orden.

La página recibe, antes de cargar, window.SPEC (el spec con cada cue ya resuelta
a un `t` en segundos) y window.BRAND (paleta, tipografía, movimiento).

uso:
  escena.py render   <tipo|plantilla.html> <spec.json> -o out.mp4 [--palabras p.json]
                     [--brand brand.json] [--duracion S] [--fps 30] [--ancho 1920]
  escena.py contacto <spec.json>... -o hoja.png [--brand brand.json] [--palabras p.json]

`tipo` es el nombre de una plantilla de assets/escenas/ (diagrama, presentacion, datos).
Corre con: uv run --with playwright python escena.py ...   (usa el Chrome instalado)
"""
import copy
import html
import json
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import palabras as _palabras

ESCENAS = Path(__file__).resolve().parent.parent / "escenas"
ANCHO_BASE, ALTO_BASE = 1920, 1080  # las plantillas se diseñan a este tamaño


class ContratoError(RuntimeError):
    """La página no cumple el contrato window.DURATION + window.seek(t)."""


# --- puro ----------------------------------------------------------------------

def tiempos_de_cuadros(duracion: float, fps: int) -> list[float]:
    n = round(duracion * fps)
    if n < 1:
        raise ValueError(f"duración {duracion} s no alcanza para un cuadro a {fps} fps")
    return [i / fps for i in range(n)]


def comando_ffmpeg(salida, fps: int, ancho: int = ANCHO_BASE) -> list[str]:
    """PNGs por stdin -> h264 yuv420p, el mismo formato que los segmentos de editar.py."""
    return ["ffmpeg", "-y", "-loglevel", "error",
            "-f", "image2pipe", "-framerate", str(fps), "-c:v", "png", "-i", "-",
            *(["-vf", f"scale={ancho}:-2:flags=lanczos"] if ancho != ANCHO_BASE else []),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-r", str(fps), "-an", str(salida)]


def verificar_contrato(info: dict, pagina) -> None:
    """info = {"duracion": window.DURATION, "seek": typeof window.seek}."""
    falta = []
    d = info.get("duracion")
    if isinstance(d, bool) or not isinstance(d, (int, float)) or d <= 0:
        falta.append(f"window.DURATION como número positivo de segundos (vino {d!r})")
    if info.get("seek") != "function":
        falta.append("window.seek(t) como función (async)")
    if falta:
        raise ContratoError(f"{pagina} no cumple el contrato de escena; falta: " + "; ".join(falta))


def _con_cue(nodo, encontrados):
    if isinstance(nodo, dict):
        if "cue" in nodo:
            encontrados.append(nodo)
        for v in nodo.values():
            _con_cue(v, encontrados)
    elif isinstance(nodo, list):
        for v in nodo:
            _con_cue(v, encontrados)
    return encontrados


def resolver_spec(spec: dict, palabras) -> dict:
    """Copia del spec donde cada elemento con "cue" gana "t" (segundos).

    Un elemento que ya trae "t" (el spec que deja `editar.py escenas`) se respeta.
    """
    out = copy.deepcopy(spec)
    elementos = [e for e in _con_cue(out, []) if "t" not in e]
    cues = [e["cue"] for e in elementos]
    if palabras is None and any(isinstance(c, str) for c in cues):
        raise ValueError("el spec tiene cues de texto y no hay palabras (tiempos de la voz) "
                         "para resolverlas: pasá --palabras o usá cues en segundos")
    for e, t in zip(elementos, _palabras.resolver_cues(palabras or [], cues)):
        e["t"] = t
    return out


def cargar_brand(ruta) -> dict:
    """Brand de la skill, con lo que declare el de la serie encima (un nivel de profundidad)."""
    brand = json.loads((ESCENAS / "brand.json").read_text())
    if ruta:
        for k, v in json.loads(Path(ruta).read_text()).items():
            brand[k] = {**brand[k], **v} if isinstance(v, dict) and isinstance(brand.get(k), dict) else v
    return brand


def ruta_plantilla(tipo: str) -> Path:
    if tipo.endswith(".html"):
        return Path(tipo).resolve()
    p = ESCENAS / f"{tipo}.html"
    if not p.exists():
        hay = sorted(x.stem for x in ESCENAS.glob("*.html"))
        raise ValueError(f"no hay plantilla de escena {tipo!r}; hay: {', '.join(hay)}")
    return p


def tiempos_contacto(duracion: float, fracciones=(0.1, 0.5, 0.9)) -> list[float]:
    return [round(duracion * f, 3) for f in fracciones]


def html_contacto(celdas, columnas: int = 3) -> str:
    """Página con una grilla de cuadros [(png, etiqueta)] para revisar escenas de un vistazo."""
    items = "".join(
        f'<figure><img src="{Path(png).resolve().as_uri()}"><figcaption>{html.escape(etq)}</figcaption></figure>'
        for png, etq in celdas)
    return ("<!doctype html><meta charset=utf-8><style>"
            "body{margin:0;padding:24px;background:#0b0c0f;font:500 18px Inter,sans-serif;color:#c9ccd3}"
            f"main{{display:grid;grid-template-columns:repeat({columnas},640px);gap:20px 16px}}"
            "figure{margin:0}img{width:640px;height:360px;display:block;border-radius:6px}"
            "figcaption{padding-top:8px}</style>"
            f"<main>{items}</main>")


# --- Chrome ----------------------------------------------------------------------

@contextmanager
def navegador():
    """Un solo Chrome headless (el instalado, no se baja nada), cerrado siempre."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True,
                              args=["--disable-gpu", "--hide-scrollbars", "--font-render-hinting=none"])
        try:
            yield b
        finally:
            b.close()


@contextmanager
def pagina_de_escena(browser, plantilla, spec: dict, brand: dict):
    """Abre la escena, verifica el contrato y devuelve (page, duracion).

    Siempre a 1920x1080 y escala 1. Con un device_scale_factor fraccionario Chrome
    NO rasteriza igual entre cargas (medido: a 960 de ancho una de cada cuatro
    cargas daba otro PNG para el mismo t), y eso rompe "mismo t, mismo cuadro".
    Para previsualizar más chico escala ffmpeg, no Chrome.
    """
    page = browser.new_page(viewport={"width": ANCHO_BASE, "height": ALTO_BASE}, device_scale_factor=1)
    errores = []
    page.on("pageerror", lambda e: errores.append(str(e)))
    try:
        page.add_init_script(f"window.SPEC = {json.dumps(spec)}; window.BRAND = {json.dumps(brand)};")
        page.goto(Path(plantilla).resolve().as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready.then(() => true)")
        if errores:
            raise ContratoError(f"{plantilla} tiró un error de JavaScript al cargar: {errores[0]}")
        info = page.evaluate("({duracion: window.DURATION === undefined ? null : window.DURATION,"
                             " seek: typeof window.seek})")
        verificar_contrato(info, plantilla)
        yield page, float(info["duracion"])
        if errores:
            raise ContratoError(f"{plantilla} tiró un error de JavaScript: {errores[0]}")
    finally:
        page.close()


# Después de seek, el body sale y vuelve a entrar al layout: Chrome lo repinta ENTERO.
# Sin esto repinta sólo lo que cambió, y una esquina redondeada que no se movió
# conserva los pixeles del primer cuadro en que se dibujó: el mismo t salía distinto
# según el orden (medido: la portada, 14 de 27 cuadros; datos, 11 de 27).
SEEK = """async t => {
  await window.seek(t);
  const b = document.body;
  b.style.display = 'none'; void b.offsetHeight; b.style.display = '';
}"""


def _cuadro(page, t: float) -> bytes:
    page.evaluate(SEEK, t)
    return page.screenshot(type="png")


def render(plantilla, spec: dict, salida, brand: dict | None = None, palabras=None,
           fps: int = 30, ancho: int = ANCHO_BASE) -> float:
    """Renderiza la escena a `salida` y devuelve su duración (cuadros / fps)."""
    spec = resolver_spec(spec, palabras)
    brand = brand or cargar_brand(None)
    Path(salida).parent.mkdir(parents=True, exist_ok=True)
    with navegador() as b, pagina_de_escena(b, plantilla, spec, brand) as (page, duracion):
        tiempos = tiempos_de_cuadros(duracion, fps)
        ff = subprocess.Popen(comando_ffmpeg(salida, fps, ancho), stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for t in tiempos:
                ff.stdin.write(_cuadro(page, t))
        finally:
            ff.stdin.close()
            err = ff.stderr.read().decode()
            ff.wait()
        if ff.returncode != 0:
            raise RuntimeError(f"ffmpeg falló armando {salida}: {err[-1500:]}")
    return len(tiempos) / fps


def hoja_contacto(escenas, salida, brand: dict | None = None, columnas: int = 3) -> Path:
    """escenas = [(nombre, plantilla, spec_resuelto)] -> PNG con 10/50/90 % de cada una."""
    brand = brand or cargar_brand(None)
    with tempfile.TemporaryDirectory() as tmp, navegador() as b:
        celdas = []
        for i, (nombre, plantilla, spec) in enumerate(escenas):
            with pagina_de_escena(b, plantilla, spec, brand) as (page, duracion):
                for t in tiempos_contacto(duracion):
                    png = Path(tmp) / f"{i:02d}-{t:.3f}.png"
                    png.write_bytes(_cuadro(page, t))
                    celdas.append((png, f"{nombre} · {t:.1f} s de {duracion:.1f}"))
        hoja = Path(tmp) / "hoja.html"
        hoja.write_text(html_contacto(celdas, columnas))
        page = b.new_page(viewport={"width": 24 * 2 + columnas * 640 + (columnas - 1) * 16, "height": 400})
        page.goto(hoja.as_uri(), wait_until="load")
        Path(salida).parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(salida), full_page=True)
        page.close()
    return Path(salida)


# --- CLI -------------------------------------------------------------------------

def _cli(argv) -> None:
    import argparse
    ap = argparse.ArgumentParser(description="motor de escenas HTML -> mp4", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="accion", required=True)
    r = sub.add_parser("render")
    r.add_argument("plantilla", help="tipo (diagrama, presentacion, datos) o ruta a un .html")
    r.add_argument("spec")
    r.add_argument("--duracion", type=float, help="pisa la duración del spec (ej: el slot de la voz)")
    r.add_argument("--fps", type=int, default=30)
    r.add_argument("--ancho", type=int, default=ANCHO_BASE, help="960 para pruebas rápidas")
    c = sub.add_parser("contacto")
    c.add_argument("specs", nargs="+", help="specs JSON con 'tipo' (los que deja editar.py escenas)")
    c.add_argument("--columnas", type=int, default=3)
    for p in (r, c):
        p.add_argument("-o", "--salida", required=True)
        p.add_argument("--brand")
        p.add_argument("--palabras", help="palabras.json de la voz, para cues de texto")
    a = ap.parse_args(argv)
    brand = cargar_brand(a.brand)
    voz = json.loads(Path(a.palabras).read_text()) if a.palabras else None
    if a.accion == "render":
        spec = json.loads(Path(a.spec).read_text())
        if a.duracion:
            spec["duracion"] = a.duracion
        d = render(ruta_plantilla(a.plantilla), spec, a.salida, brand, voz, a.fps, a.ancho)
        print(f"{a.salida}: {d:.2f} s")
    else:
        escenas = []
        for s in a.specs:
            spec = json.loads(Path(s).read_text())
            escenas.append((Path(s).stem + " " + spec["tipo"], ruta_plantilla(spec["tipo"]),
                            resolver_spec(spec, voz)))
        print(hoja_contacto(escenas, a.salida, brand, a.columnas))


if __name__ == "__main__":
    _cli(sys.argv[1:])
