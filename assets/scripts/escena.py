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

`tipo` es el nombre de una plantilla de assets/escenas/ (diagrama, presentacion, datos, imagen).
Corre con: uv run --with playwright python escena.py ...   (usa el Chrome instalado)
"""
import copy
import html
import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path

import encoder
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
    vf = encoder.vf(f"scale={ancho}:-2:flags=lanczos" if ancho != ANCHO_BASE else "")
    return ["ffmpeg", "-y", "-loglevel", "error",
            "-f", "image2pipe", "-framerate", str(fps), "-c:v", "png", "-i", "-",
            *(["-vf", vf] if vf else []),
            *encoder.cv_args(crf=20, preset="veryfast"),
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


# R-4.6 / B1 (QA 03/10/2026): sólo SVG local (Q8, decidido por Juani), sin JS ni red. El SVG
# entra por innerHTML, así que un regex sobre el texto crudo no alcanza (mayúsculas, sin
# comillas, entidades, @import/@font-face, foreignObject, image con data:, file://...): se
# parsea como XML y se pasa por una lista blanca de elementos/atributos. Lo que no está en la
# lista blanca falla ANTES de abrir Chrome, nombrando archivo/elemento/atributo.
NS_SVG = "http://www.w3.org/2000/svg"
NS_XLINK = "http://www.w3.org/1999/xlink"
ET.register_namespace("", NS_SVG)
ET.register_namespace("xlink", NS_XLINK)

# Sólo dibujo: nada de <script>, <style>, <foreignObject>, <image> (ni con data:, Q8 prohíbe
# fotos) ni SMIL (<animate>/<set>, rompe el determinismo de t).
ELEMENTOS_PERMITIDOS = {
    "svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon",
    "defs", "use", "title", "desc", "text",
}
ATRIBUTOS_PERMITIDOS = {
    "viewbox", "width", "height", "x", "y", "cx", "cy", "r", "rx", "ry",
    "x1", "y1", "x2", "y2", "points", "d", "transform",
    "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
    "stroke-dasharray", "stroke-dashoffset", "fill-opacity", "stroke-opacity",
    "opacity", "fill-rule", "clip-rule", "class", "id",
    "href", "xmlns", "xmlns:xlink", "version",
    "font-size", "font-weight", "font-family", "text-anchor",
}
# atributos cuyo valor puede referenciar una url(): sólo url(#id) interno, nunca de red
ATRIBUTOS_CON_POSIBLE_URL = {"fill", "stroke"}
# B4(b) (QA 03/10/2026): fill/stroke con un color fijo no se recolorea al brand; la
# convención (ver imagen.html) es "none" o "currentColor". Un color fijo falla claro en vez
# de quedar pegado para siempre al color con el que se dibujó el SVG original.
COLORES_PERMITIDOS = {"none", "currentColor"}
DOCTYPE_O_ENTIDAD = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)


def _local(tag: str) -> str:
    """"{namespace}tag" o "ns:tag" -> "tag", en minúscula."""
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1].lower()


def sanear_svg(contenido: str, ruta) -> str:
    """Lista blanca de elementos/atributos; levanta ValueError nombrando archivo/elemento/
    atributo ante cualquier cosa fuera de ella. Devuelve el SVG re-serializado.
    """
    m = DOCTYPE_O_ENTIDAD.search(contenido)
    if m:
        raise ValueError(f"SVG {ruta!r}: {m.group(1).upper()} no permitido (protección XXE/billion-laughs)")
    try:
        raiz = ET.fromstring(contenido)
    except ET.ParseError as e:
        raise ValueError(f"SVG {ruta!r}: no es XML válido ({e})") from e

    for el in raiz.iter():
        nombre = _local(el.tag)
        if nombre not in ELEMENTOS_PERMITIDOS:
            raise ValueError(f"SVG {ruta!r}: elemento {nombre!r} no permitido (sólo dibujo vectorial, Q8)")
        for attr, valor in el.attrib.items():
            nombre_attr = _local(attr)
            if nombre_attr.startswith("on"):
                raise ValueError(f"SVG {ruta!r}: elemento {nombre!r} con atributo de evento {attr!r} no permitido")
            if nombre_attr not in ATRIBUTOS_PERMITIDOS:
                raise ValueError(f"SVG {ruta!r}: elemento {nombre!r} con atributo {attr!r} no permitido")
            if nombre_attr == "href":
                if nombre != "use" or not valor.startswith("#"):
                    raise ValueError(
                        f"SVG {ruta!r}: elemento {nombre!r} con href {valor!r}; "
                        "sólo <use href=\"#id\"> interno (sin red, Q8)")
            if nombre_attr in ATRIBUTOS_CON_POSIBLE_URL and "url(" in valor and "url(#" not in valor:
                raise ValueError(f"SVG {ruta!r}: elemento {nombre!r} con {attr}={valor!r}; "
                                 "url() sólo puede referenciar un #id interno")
            if (nombre_attr in ATRIBUTOS_CON_POSIBLE_URL and "url(" not in valor
                    and valor not in COLORES_PERMITIDOS):
                raise ValueError(
                    f"SVG {ruta!r}: elemento {nombre!r} con {attr}={valor!r}; "
                    'usá "currentColor" (se recolorea al brand) o "none", nunca un color fijo')
    return ET.tostring(raiz, encoding="unicode")


def resolver_dibujos(spec: dict, base_dir=None) -> dict:
    """Copia del spec con el contenido de cada dibujos[].svg embebido en "markup".

    Escena "imagen" (HITO2.md S4). Se valida ANTES de abrir Chrome: un SVG
    faltante, mal formado o fuera de la lista blanca corta aquí, sin .mp4 ni
    .parcial.mp4 (R-4.6, B1).

    B3 (QA 03/10/2026): un "svg" relativo se resuelve contra `base_dir` (el
    directorio del spec.json), no contra el cwd de quien corre escena.py; así
    el ejemplo renderiza igual desde la raíz del repo o desde cualquier otro
    directorio. Sin base_dir, el default documentado es el cwd (compatible con
    specs que ya traían una ruta absoluta). Un "svg" absoluto no se ve afectado.
    """
    base_dir = Path(base_dir) if base_dir is not None else Path.cwd()
    out = copy.deepcopy(spec)
    for d in out.get("dibujos", []):
        ruta = d.get("svg")
        if not ruta:
            continue
        p = Path(ruta)
        if not p.is_absolute():
            p = base_dir / p
        if not p.exists():
            raise ValueError(f"dibujo {d.get('id', '?')!r}: no existe el SVG {ruta!r}")
        d["markup"] = sanear_svg(p.read_text(), ruta)
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


# Una fuente que no está hace que Chrome use otra EN SILENCIO (medido por QA: Noto
# Sans en vez de Inter). Si la fuente existe, el texto mide distinto que con la
# genérica de respaldo; si mide igual contra dos genéricas, no está.
FUENTE_FALTA = """f => {
  const c = document.createElement('canvas').getContext('2d');
  const ancho = fam => { c.font = `700 72px ${fam}`; return c.measureText('Interés compuesto 0123').width; };
  return ['monospace', 'serif'].every(g => ancho(`"${f}", ${g}`) === ancho(g));
}"""


def avisar_si_falta_la_fuente(page, fuente) -> bool:
    if fuente and page.evaluate(FUENTE_FALTA, fuente):
        print(f"AVISO: la fuente {fuente!r} del brand no está instalada: Chrome va a usar otra. "
              "Instalala (Inter es libre, OFL) o cambiá 'fuente' en brand.json.", file=sys.stderr)
        return True
    return False


# R-4.5 (PLAN.md): Canvas 2D / SVG, nunca WebGL (la GPU integrada de Juani la arrastra).
# Se patchea ANTES de que cargue la plantilla: si una la llama, página falla con el mismo
# camino que un error de JS (page.on("pageerror")) y sale como ContratoError.
# B6 (QA 03/10/2026): HTMLCanvasElement no es el único con getContext; OffscreenCanvas (que
# puede pedir 'webgl' igual, sin estar en el DOM) la saltea si no se cubre también.
GUARDIA_WEBGL = """(function () {
  function bloquear(proto) {
    const orig = proto.getContext;
    proto.getContext = function (tipo, ...resto) {
      if (['webgl', 'webgl2', 'experimental-webgl'].includes(tipo))
        throw new Error(`getContext(${JSON.stringify(tipo)}): esta skill es Canvas 2D / SVG, nunca WebGL`);
      return orig.call(this, tipo, ...resto);
    };
  }
  bloquear(HTMLCanvasElement.prototype);
  if (typeof OffscreenCanvas !== 'undefined') bloquear(OffscreenCanvas.prototype);
})();"""


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

    def _bloquear_red(route):
        """B1, defensa en profundidad: el saneado de resolver_dibujos es la primera barrera;
        esta es la segunda, para todas las plantillas. Nada sale al mundo (XHR/fetch/img/CSS):
        sólo file:// de la propia escena. Un intento de red falla el render con ContratoError
        en vez de pasar en silencio (antes un `catch` de la plantilla se lo tragaba).
        """
        url = route.request.url
        if url.startswith("file://"):
            route.continue_()
        else:
            errores.append(f"intento de red bloqueado ({route.request.method} {url})")
            route.abort()

    page.route("**/*", _bloquear_red)
    try:
        page.add_init_script(GUARDIA_WEBGL)
        page.add_init_script(f"window.SPEC = {json.dumps(spec)}; window.BRAND = {json.dumps(brand)};")
        page.goto(Path(plantilla).resolve().as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready.then(() => true)")
        if errores:
            raise ContratoError(f"{plantilla} tiró un error de JavaScript al cargar: {errores[0]}")
        info = page.evaluate("({duracion: window.DURATION === undefined ? null : window.DURATION,"
                             " seek: typeof window.seek})")
        verificar_contrato(info, plantilla)
        avisar_si_falta_la_fuente(page, brand.get("fuente"))
        yield page, float(info["duracion"])
        if errores:
            raise ContratoError(f"{plantilla} tiró un error de JavaScript: {errores[0]}")
    finally:
        page.close()


# Forzar relayout del body después de cada seek hace determinista el render (medido:
# sin él 14/27 y 11/27 cuadros dependen del orden; con él 0). La causa exacta en
# Chrome no está identificada: en la portada la diferencia cae en el borde de un
# elemento redondeado, en `datos` en una fila horizontal de ~242 px.
SEEK = """async t => {
  try { await window.seek(t); } catch (e) { return String((e && e.message) || e); }
  const b = document.body;
  b.style.display = 'none'; void b.offsetHeight; b.style.display = '';
  return null;
}"""


def _cuadro(page, t: float) -> bytes:
    error = page.evaluate(SEEK, t)
    if error:
        raise ContratoError(f"window.seek({t:.3f}) tiró un error de JavaScript: {error}")
    return page.screenshot(type="png")


def render(plantilla, spec: dict, salida, brand: dict | None = None, palabras=None,
           fps: int = 30, ancho: int = ANCHO_BASE, base_dir=None) -> float:
    """Renderiza la escena a `salida` y devuelve su duración (cuadros / fps).

    Se escribe a un .parcial.mp4 y se renombra al final: si algo falla a mitad, no
    queda un mp4 corto que se reproduce bien y parece un render válido.

    `base_dir` (B3): directorio contra el que se resuelven los "svg" relativos de
    dibujos[] (el directorio del spec.json); sin él, el cwd de quien llama.
    """
    spec = resolver_dibujos(resolver_spec(spec, palabras), base_dir)
    brand = brand or cargar_brand(None)
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    parcial = salida.with_name(salida.stem + ".parcial" + salida.suffix)
    try:
        with navegador() as b, pagina_de_escena(b, plantilla, spec, brand) as (page, duracion):
            tiempos = tiempos_de_cuadros(duracion, fps)
            ff = subprocess.Popen(comando_ffmpeg(parcial, fps, ancho), stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                for t in tiempos:
                    ff.stdin.write(_cuadro(page, t))
            finally:
                ff.stdin.close()
                err = ff.stderr.read().decode()
                ff.wait()
            if ff.returncode != 0:
                raise RuntimeError(f"ffmpeg falló armando {salida}: {err[-1500:]}")
        parcial.replace(salida)
    finally:
        parcial.unlink(missing_ok=True)
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
    r.add_argument("plantilla", help="tipo (diagrama, presentacion, datos, imagen) o ruta a un .html")
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
    if a.accion == "render":
        if a.duracion is not None and a.duracion <= 0:
            ap.error(f"--duracion tiene que ser mayor que 0 (vino {a.duracion})")
        if a.ancho <= 0 or a.ancho % 2:
            ap.error(f"--ancho tiene que ser un número par (vino {a.ancho}): h264 yuv420p no acepta impares")
    brand = cargar_brand(a.brand)
    voz = json.loads(Path(a.palabras).read_text()) if a.palabras else None
    if a.accion == "render":
        spec = json.loads(Path(a.spec).read_text())
        if a.duracion is not None:
            spec["duracion"] = a.duracion
        d = render(ruta_plantilla(a.plantilla), spec, a.salida, brand, voz, a.fps, a.ancho,
                   base_dir=Path(a.spec).resolve().parent)
        print(f"{a.salida}: {d:.2f} s")
    else:
        escenas = []
        for s in a.specs:
            spec = json.loads(Path(s).read_text())
            if not spec.get("tipo"):
                ap.error(f"{s} no dice su 'tipo' (diagrama, presentacion, datos, imagen)")
            escenas.append((Path(s).stem + " " + spec["tipo"], ruta_plantilla(spec["tipo"]),
                            resolver_dibujos(resolver_spec(spec, voz), Path(s).resolve().parent)))
        print(hoja_contacto(escenas, a.salida, brand, a.columnas))


if __name__ == "__main__":
    _cli(sys.argv[1:])
