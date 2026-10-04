#!/usr/bin/env python3
"""Diagramas de recursión (pila de llamadas y árbol) dibujados a partir de una traza REAL.

No se dibuja lo que uno cree que pasa: se ejecuta la función, un decorador registra cada
llamada y cada retorno (y lo que se imprimió entre medio), y el dibujo sale de ese registro.
Si el código cambia, el diagrama cambia con él.

Uso desde Python:
    from diagramas import trazar, dibujar_pila, dibujar_arbol
    eventos = trazar("cuenta_regresiva.py", "cuenta_regresiva(3)")
    dibujar_pila(eventos, "pila.png")
    dibujar_arbol(trazar("fibonacci.py", "fibonacci(5)"), "arbol.png", formato="F({n})")

Uso suelto:
    python diagramas.py pila  cuenta_regresiva.py "cuenta_regresiva(3)" -o pila.png
    python diagramas.py arbol fibonacci.py "fibonacci(5)" -o arbol.png --formato "F({n})"
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import inspect
import io
import os
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

NAVY, ACC, TXT, GRIS = "#1b365d", "#2f6fa7", "#1f2328", "#5b6470"
CARD, BORDE, NARANJA, NARANJA_FONDO = "#e8eef6", "#c9d3df", "#b54708", "#fdf1e8"
MONO = "DejaVu Sans Mono"
SANS = "Inter" if any("Inter" in f.name for f in font_manager.fontManager.ttflist) else "DejaVu Sans"
MAX_NODOS = 60


# ---------------------------------------------------------------- traza
class _Escritor(io.TextIOBase):
    def __init__(self, eventos):
        self.eventos = eventos

    def write(self, s):
        if self.eventos:
            self.eventos[-1]["impreso"] += s
        return len(s)


def trazar(archivo, llamada, funcion=None):
    """Ejecuta `archivo` (sin mostrar lo que imprime) y después evalúa `llamada` registrando
    cada llamada y retorno de `funcion` (por defecto, el nombre antes del paréntesis)."""
    archivo = Path(archivo)
    funcion = funcion or re.match(r"\s*(\w+)", llamada).group(1)
    ns = {"__name__": "__traza__", "__file__": str(archivo)}
    cwd = os.getcwd()
    os.chdir(archivo.parent)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(archivo.read_text(encoding="utf-8"), archivo.name, "exec"), ns)
        original = ns[funcion]
        firma = inspect.signature(original)
        eventos, pila = [], []

        @functools.wraps(original)
        def envoltura(*a, **k):
            args = dict(firma.bind(*a, **k).arguments)
            nodo = {"id": len([e for e in eventos if e["tipo"] == "llamada"]), "args": args,
                    "padre": pila[-1] if pila else None}
            pila.append(nodo["id"])
            eventos.append({"tipo": "llamada", "pila": list(pila), "impreso": "", **nodo})
            r = original(*a, **k)
            eventos.append({"tipo": "retorno", "pila": list(pila), "impreso": "", "valor": r,
                            "args": args, "id": nodo["id"]})
            pila.pop()
            return r

        ns[funcion] = envoltura   # la recursión busca el nombre en el módulo: pasa por acá
        with contextlib.redirect_stdout(_Escritor(eventos)):
            eval(llamada, ns)
    finally:
        os.chdir(cwd)
    args_de = {e["id"]: e["args"] for e in eventos if e["tipo"] == "llamada"}
    for e in eventos:
        e["pila_args"] = [args_de[i] for i in e["pila"]]
    return eventos


def _fmt(args, formato=None):
    if formato:
        return formato.format(**args)
    return ", ".join(f"{k} = {v!r}" for k, v in args.items())


def etiqueta_defecto(e):
    impreso = e["impreso"].strip()
    if impreso:
        return "imprime\n" + impreso.replace("\n", " ")[:18]
    if e["tipo"] == "llamada":
        return "llama"
    return "termina" if e["valor"] is None else f"devuelve {e['valor']!r}"[:18]


# ---------------------------------------------------------------- pila
def dibujar_pila(eventos, salida, formato=None, etiquetas=None, dpi=200):
    """Una columna por evento: la pila después de cada llamada (arriba, en azul lleno) y en
    cada retorno (arriba, en naranja: esa llamada está terminando)."""
    n = len(eventos)
    if n > 16:
        raise ValueError(f"{n} eventos: demasiados para una diapositiva (máx. 16). "
                         "Usá una llamada más chica.")
    prof = max(len(e["pila"]) for e in eventos)
    cw, bh, bw = 1.5, 0.41, 1.23
    fig_w, fig_h = n * cw, prof * bh + 1.15
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    base = 1.05
    for i, e in enumerate(eventos):
        cx = i * cw + cw / 2
        for k, args in enumerate(e["pila_args"]):
            tope = k == len(e["pila_args"]) - 1
            if tope and e["tipo"] == "llamada":
                fc, ec, tc = ACC, NAVY, "white"
            elif tope:
                fc, ec, tc = NARANJA_FONDO, NARANJA, NARANJA
            else:
                fc, ec, tc = CARD, BORDE, NAVY
            y = base + k * bh
            ax.add_patch(FancyBboxPatch((cx - bw / 2, y + 0.03), bw, bh - 0.08,
                                        boxstyle="round,pad=0,rounding_size=0.05",
                                        fc=fc, ec=ec, lw=1.6))
            ax.text(cx, y + bh / 2 - 0.01, _fmt(args, formato), ha="center", va="center",
                    family=MONO, size=13, color=tc)
        et = etiquetas[i] if etiquetas else etiqueta_defecto(e)
        col = ACC if e["tipo"] == "llamada" else NARANJA
        ax.text(cx, 0.62, et, ha="center", va="center", family=SANS, size=10.5,
                weight="bold", color=col, linespacing=1.3)
        ax.text(cx, 0.14, str(i + 1), ha="center", va="center", family=SANS, size=9,
                color=GRIS)
    fig.savefig(salida, dpi=dpi, facecolor="white")
    plt.close(fig)
    return Path(salida)


# ---------------------------------------------------------------- árbol
def dibujar_arbol(eventos, salida, formato=None, marcar_repetidos=True, dpi=200):
    """Árbol de llamadas. Con marcar_repetidos, la primera vez que se calcula un valor va en
    azul y cada repetición en naranja: se ve cuánto trabajo se recalcula."""
    nodos = {e["id"]: {"args": e["args"], "padre": e["padre"], "hijos": []}
             for e in eventos if e["tipo"] == "llamada"}
    if len(nodos) > MAX_NODOS:
        raise ValueError(f"{len(nodos)} llamadas: el árbol no entra en una diapositiva "
                         f"(máx. {MAX_NODOS}). Usá una llamada más chica.")
    raiz = None
    for i, nd in nodos.items():
        if nd["padre"] is None:
            raiz = raiz if raiz is not None else i
        else:
            nodos[nd["padre"]]["hijos"].append(i)
    vistos, hoja = set(), [0]

    def ubicar(i, d):
        nd = nodos[i]
        clave = tuple(sorted(nd["args"].items(), key=str))
        nd["rep"] = clave in vistos
        vistos.add(clave)
        nd["d"] = d
        for h in nd["hijos"]:
            ubicar(h, d + 1)
        if nd["hijos"]:
            nd["x"] = sum(nodos[h]["x"] for h in nd["hijos"]) / len(nd["hijos"])
        else:
            nd["x"] = hoja[0]
            hoja[0] += 1

    ubicar(raiz, 0)
    hojas, prof = hoja[0], max(nd["d"] for nd in nodos.values()) + 1
    sx, sy, bw, bh = 0.85, 0.56, 0.72, 0.28
    fig_w, fig_h = max(hojas * sx + 0.3, 3), prof * sy + 0.2
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")

    def pos(nd):
        return 0.15 + nd["x"] * sx + sx / 2, fig_h - 0.1 - nd["d"] * sy - sy / 2

    for nd in nodos.values():
        x, y = pos(nd)
        for h in nd["hijos"]:
            hx, hy = pos(nodos[h])
            ax.plot([x, hx], [y - bh / 2, hy + bh / 2], color=BORDE, lw=1.6, zorder=1)
    for nd in nodos.values():
        x, y = pos(nd)
        rep = marcar_repetidos and nd["rep"]
        ax.add_patch(FancyBboxPatch((x - bw / 2, y - bh / 2), bw, bh,
                                    boxstyle="round,pad=0,rounding_size=0.04",
                                    fc=NARANJA_FONDO if rep else CARD, ec=NARANJA if rep else ACC,
                                    lw=1.4, zorder=2))
        ax.text(x, y, _fmt(nd["args"], formato), ha="center", va="center", family=MONO,
                size=10, color=NARANJA if rep else NAVY, zorder=3)
    fig.savefig(salida, dpi=dpi, facecolor="white")
    plt.close(fig)
    return Path(salida)


def generar(spec: dict, base: Path, salida: Path) -> Path:
    """Para build.py: spec = {diagrama: pila|arbol, archivo, llamada, funcion?, formato?, etiquetas?}."""
    ev = trazar(base / spec["archivo"], spec["llamada"], spec.get("funcion"))
    if (spec.get("diagrama") or spec.get("tipo", "pila")) == "arbol":
        return dibujar_arbol(ev, salida, spec.get("formato"), spec.get("marcar_repetidos", True))
    return dibujar_pila(ev, salida, spec.get("formato"), spec.get("etiquetas"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tipo", choices=["pila", "arbol"])
    ap.add_argument("archivo", type=Path)
    ap.add_argument("llamada")
    ap.add_argument("-o", "--salida", type=Path, required=True)
    ap.add_argument("--funcion")
    ap.add_argument("--formato", help='p. ej. "n = {n}" o "F({n})"')
    a = ap.parse_args()
    p = generar({"diagrama": a.tipo, "archivo": a.archivo.name, "llamada": a.llamada,
                 "funcion": a.funcion, "formato": a.formato}, a.archivo.resolve().parent, a.salida)
    print(p)


if __name__ == "__main__":
    main()
