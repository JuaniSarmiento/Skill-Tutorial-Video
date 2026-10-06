#!/usr/bin/env python3
"""Puerta `check` antes del render (H2, HITO3.md): lo que se ve, medido en N tiempos.

Con Playwright sobre la misma página de la escena (el contrato DURATION + seek de
escena.py), lleva la escena a N tiempos parejos más justo antes y después de cada cue,
y en cada uno mide:

  solape    dos cajas de texto visibles ([data-caja] con texto) se pisan
  desborde  un texto se sale del cuadro útil (la banda de subtítulos, el 17 % de abajo,
            queda libre) o de su propia caja
  contraste texto/fondo < 4,5:1 (WCAG AA); 3:1 para texto >= 32 px, o >= 24 px en negrita
  cue       un elemento (con data-t) se ve antes de su cue

Idea tomada del `check` de HyperFrames (docs/packages/cli.mdx: layout, contrast); el
código es propio. El fondo de un texto es el primer background-color opaco de sus
ancestros (o el del body): un texto encima de una forma que NO es su ancestro (una
barra, un dibujo) se mide contra el fondo de la página.

`escena.py render` la corre antes de renderizar (se saltea con --sin-verificar) y
`editar.py revisar` suma sus hallazgos como D5 (contraste) y D6 (solape y desborde).

uso:
  verificar.py <spec.json>... [--brand brand.json] [--palabras p.json] [-n 12]
Corre con: uv run --with playwright --with pygments python verificar.py ...
"""
import json
import re
import sys
from collections import namedtuple
from pathlib import Path

ANCHO, ALTO = 1920, 1080
BANDA = int(ALTO * 0.83)   # px: debajo van los subtítulos (E.BANDA de base.js)
VISIBLE = 0.05             # opacidad desde la que un texto "se ve" y puede pisar a otro
ASENTADO = 0.99            # opacidad desde la que se mide el contraste (no a mitad de fundido)
TOLERANCIA = 1.0           # px de redondeo del layout

Hallazgo = namedtuple("Hallazgo", "tipo texto")


class VerificacionError(RuntimeError):
    """La escena no pasa la puerta: el mensaje lista cada hallazgo."""


# --- puro ----------------------------------------------------------------------------

def _lineal(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminancia(rgb) -> float:
    r, g, b = (_lineal(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a, b) -> float:
    """Razón de contraste WCAG 2.x entre dos colores RGB (1 a 21)."""
    la, lb = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def umbral(px: float, peso: int) -> float:
    """4,5:1 (AA); 3:1 para texto grande: >= 32 px, o >= 24 px en negrita (>= 700)."""
    return 3.0 if px >= 32 or (px >= 24 and peso >= 700) else 4.5


def color(css: str):
    """'rgb(r, g, b)' / 'rgba(r, g, b, a)' / 'color(srgb r g b [/ a])' (lo que da un
    color-mix) de getComputedStyle -> (r, g, b, a), con r, g, b de 0 a 255."""
    m = re.fullmatch(r"color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*/\s*([\d.]+))?\s*\)", css.strip())
    if m:
        r, g, b = (round(float(x) * 255) for x in m.groups()[:3])
        return (r, g, b, float(m.group(4)) if m.group(4) is not None else 1.0)
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+))?\s*\)", css.strip())
    if not m:
        raise ValueError(f"color que no se sabe leer: {css!r}")
    r, g, b = (int(float(x)) for x in m.groups()[:3])
    return (r, g, b, float(m.group(4)) if m.group(4) is not None else 1.0)


def _sobre(fg, bg):
    """fg (r, g, b, a) mezclado sobre bg (r, g, b)."""
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3))


def tiempos_de_muestra(duracion: float, cues, n: int = 12) -> list[float]:
    """n tiempos parejos en [0, duracion) más, por cada cue, uno justo antes (-0,05 s)
    y otro con el elemento ya entrado (+0,6 s). Ordenados, sin repetir, dentro de la escena."""
    ultimo = duracion - 1 / 30
    ts = {round(duracion * i / n, 3) for i in range(n)}
    for c in cues:
        ts |= {round(c - 0.05, 3), round(c + 0.6, 3)}
    return sorted(t for t in ts if 0 <= t <= ultimo)


def _pisan(a: dict, b: dict) -> bool:
    return (min(a["x1"], b["x1"]) - max(a["x0"], b["x0"]) > TOLERANCIA
            and min(a["y1"], b["y1"]) - max(a["y0"], b["y0"]) > TOLERANCIA)


def hallazgos_del_cuadro(escena: str, t: float, cajas: list[dict], textos: list[dict]) -> list[Hallazgo]:
    """Hallazgos de un cuadro ya medido.

    cajas:  [{n, x0, y0, x1, y1, op, texto, desborda, t}] de cada [data-caja]
    textos: [{n, color, fondo, px, peso, op}] de cada elemento con texto propio
    """
    donde = f"{escena}, t={t:.2f} s"
    out = []
    visibles = [c for c in cajas if c["op"] > VISIBLE]
    con_texto = [c for c in visibles if c["texto"]]
    for i, a in enumerate(con_texto):
        for b in con_texto[i + 1:]:
            if _pisan(a, b):
                out.append(Hallazgo("solape", f"{donde}: {a['n']!r} y {b['n']!r} se pisan"))
    for c in con_texto:
        if (c["x0"] < -TOLERANCIA or c["y0"] < -TOLERANCIA or c["x1"] > ANCHO + TOLERANCIA
                or c["y1"] > BANDA + TOLERANCIA):
            out.append(Hallazgo("desborde", f"{donde}: {c['n']!r} se sale del cuadro útil "
                                            f"(x {c['x0']:.0f}-{c['x1']:.0f}, y {c['y0']:.0f}-{c['y1']:.0f}; "
                                            f"la banda de subtítulos empieza en y={BANDA})"))
        elif c["desborda"]:
            out.append(Hallazgo("desborde", f"{donde}: el texto de {c['n']!r} se sale de su caja"))
    for c in visibles:
        if c.get("t") is not None and t < c["t"] - 1e-3:
            out.append(Hallazgo("cue", f"{donde}: {c['n']!r} ya se ve (opacidad {c['op']:.2f}) "
                                       f"antes de su cue en {c['t']:.2f} s"))
    for x in textos:
        if x["op"] < ASENTADO:
            continue
        fondo = color(x["fondo"])
        razon = contraste(_sobre(color(x["color"]), fondo), fondo)
        minimo = umbral(x["px"], x["peso"])
        if razon < minimo:
            out.append(Hallazgo("contraste", f"{donde}: {x['n']!r} tiene contraste {razon:.2f}:1 "
                                             f"(mínimo {minimo}:1 a {x['px']:.0f} px)"))
    return out


# --- Chrome ----------------------------------------------------------------------------

# Lo que se ve en el cuadro actual: cada [data-caja] (geometría, opacidad efectiva, si
# tiene texto, si el texto se sale de su caja, su cue) y cada elemento con texto propio
# (color, fondo efectivo, tamaño y peso), para el contraste.
MEDIR = r"""() => {
  const opacidad = e => { let o = 1; for (let x = e; x && x.nodeType === 1; x = x.parentElement) o *= parseFloat(getComputedStyle(x).opacity); return o; };
  const transparente = c => c === 'transparent' || /rgba\([^)]*,\s*0\)$/.test(c);
  const fondo = e => {
    for (let x = e; x; x = x.parentElement) { const c = getComputedStyle(x).backgroundColor; if (!transparente(c)) return c; }
    return 'rgb(255, 255, 255)';
  };
  // una caja que todavía se mueve (transform no identidad en ella o adentro) desborda su
  // scroll por la animación, no por el texto: se mide cuando quedó quieta
  const identidad = x => { const t = getComputedStyle(x).transform; return t === 'none' || t === 'matrix(1, 0, 0, 1, 0, 0)'; };
  const quieta = e => [e, ...e.querySelectorAll('*')].every(identidad);
  const nombre = e => { const c = e.closest('[data-caja]'); return c ? c.dataset.caja : e.tagName.toLowerCase() + (e.className ? '.' + e.className : ''); };
  const cajas = [...document.querySelectorAll('[data-caja]')].map(e => {
    const r = e.getBoundingClientRect();
    return {n: e.dataset.caja, x0: r.left, y0: r.top, x1: r.right, y1: r.bottom, op: opacidad(e),
            texto: e.textContent.trim() !== '',
            // sólo a lo ancho: a lo alto un line-height < 1 (las cifras gigantes) ya "desborda" sin que se corte nada
            desborda: e.clientWidth > 0 && quieta(e) && e.scrollWidth > e.clientWidth + 1,
            t: e.dataset.t != null ? parseFloat(e.dataset.t) : null};
  });
  const textos = [...document.body.querySelectorAll('*')]
    .filter(e => !['SCRIPT', 'STYLE'].includes(e.tagName)
                 && [...e.childNodes].some(x => x.nodeType === 3 && x.textContent.trim() !== ''))
    .map(e => { const s = getComputedStyle(e);
      return {n: nombre(e), color: s.color, fondo: fondo(e), px: parseFloat(s.fontSize),
              peso: parseInt(s.fontWeight, 10), op: opacidad(e)}; });
  return {cajas, textos};
}"""


def _clave(h: Hallazgo) -> tuple:
    """El mismo problema visto en varios tiempos se informa una vez (el primero)."""
    return h.tipo, h.texto.split(": ", 1)[1].split(" (", 1)[0]


def verificar_pagina(page, duracion: float, spec: dict, nombre: str, n: int = 12) -> list[Hallazgo]:
    """Hallazgos de la escena ya abierta en `page` (pagina_de_escena), muestreando n
    tiempos más los de cada cue (del spec resuelto y de los data-t de la página)."""
    import escena
    cues = {e["t"] for e in escena._con_cue(spec, []) if isinstance(e.get("t"), (int, float))}
    vistos, out = set(), []
    for i, t in enumerate(tiempos_de_muestra(duracion, sorted(cues), n)):
        error = page.evaluate(escena.SEEK, t)
        if error:
            raise escena.ContratoError(f"window.seek({t:.3f}) tiró un error de JavaScript: {error}")
        medido = page.evaluate(MEDIR)
        if i == 0:   # los data-t recién existen después del primer seek (la escena se arma ahí)
            extra = {c["t"] for c in medido["cajas"] if c["t"] is not None} - cues
            if extra:
                return verificar_pagina(page, duracion, {"_cues": [{"cue": t, "t": t} for t in cues | extra]},
                                        nombre, n)
        for h in hallazgos_del_cuadro(nombre, t, medido["cajas"], medido["textos"]):
            if _clave(h) not in vistos:
                vistos.add(_clave(h))
                out.append(h)
    return out


def informe(hallazgos: list[Hallazgo]) -> str:
    return "\n".join(f"  - {h.tipo}: {h.texto}" for h in hallazgos)


def verificar_escena(plantilla, spec: dict, brand: dict | None = None, nombre: str | None = None,
                     n: int = 12) -> list[Hallazgo]:
    """Abre su propio Chrome y verifica una escena (spec ya resuelto, con dibujos embebidos)."""
    import escena
    brand = brand or escena.cargar_brand(None)
    with escena.navegador() as b, escena.pagina_de_escena(b, plantilla, spec, brand) as (page, d):
        return verificar_pagina(page, d, spec, nombre or Path(plantilla).name, n)


def _cli(argv) -> int:
    import argparse
    import escena
    ap = argparse.ArgumentParser(description="puerta check de escenas", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("specs", nargs="+", help="specs JSON con 'tipo' (los que deja editar.py escenas)")
    ap.add_argument("--brand")
    ap.add_argument("--palabras", help="palabras.json de la voz, para cues de texto")
    ap.add_argument("-n", type=int, default=12, help="tiempos parejos a muestrear (además de las cues)")
    a = ap.parse_args(argv)
    brand = escena.cargar_brand(a.brand)
    voz = json.loads(Path(a.palabras).read_text()) if a.palabras else None
    hay = False
    for s in a.specs:
        spec = json.loads(Path(s).read_text())
        if not spec.get("tipo"):
            ap.error(f"{s} no dice su 'tipo' (diagrama, presentacion, datos, imagen)")
        base = Path(s).resolve().parent
        plantilla = escena.ruta_plantilla(spec["tipo"])
        spec = escena.resolver_codigo(escena.resolver_dibujos(escena.resolver_spec(spec, voz), base), plantilla, base)
        hallazgos = verificar_escena(plantilla, spec, brand, Path(s).name, a.n)
        print(f"{s}: " + ("sin hallazgos" if not hallazgos else f"{len(hallazgos)} hallazgo(s)\n" + informe(hallazgos)))
        hay = hay or bool(hallazgos)
    return 1 if hay else 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
