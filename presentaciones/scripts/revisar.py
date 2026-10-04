#!/usr/bin/env python3
"""Rasteriza el PDF de una presentación y arma una hoja de contactos para revisarla por imagen.

Por qué por imagen: python-pptx no sabe cuánto ocupa un texto, así que no puede avisar si se
desborda. El único juez fiable es el render. Esta hoja muestra todas las diapositivas juntas,
numeradas, para mirarlas con Read una por una.

Uso:
    python revisar.py presentacion.pdf                 # -> presentacion_hoja.png
    python revisar.py presentacion.pdf --columnas 3 --dpi 50
    python revisar.py presentacion.pdf --diapo 4       # una sola, en grande (para el detalle)
    python revisar.py nuevo.pdf --comparar original.pdf   # lado a lado, diapositiva por diapositiva
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def rasterizar(pdf: Path, carpeta: Path, dpi: int, pagina: int | None = None) -> list[Path]:
    if not shutil.which("pdftoppm"):
        sys.exit("Falta pdftoppm (paquete poppler-utils). Corré scripts/preflight.py.")
    cmd = ["pdftoppm", "-r", str(dpi), "-png"]
    if pagina:
        cmd += ["-f", str(pagina), "-l", str(pagina)]
    subprocess.run(cmd + [str(pdf), str(carpeta / "p")], check=True)
    return sorted(carpeta.glob("p-*.png"), key=lambda p: int(p.stem.split("-")[-1]))


def _fuente(t):
    for nombre in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(nombre, t)
        except OSError:
            pass
    return ImageFont.load_default()


def hoja(imagenes: list[list[Image.Image]], columnas: int, rotulos=None) -> Image.Image:
    """imagenes: una lista por celda (1 imagen, o 2 para comparar lado a lado)."""
    w, h = imagenes[0][0].size
    por_celda = max(len(c) for c in imagenes)
    cw, ch, pad, cab = w * por_celda + 6 * (por_celda - 1), h, 14, 26
    filas = (len(imagenes) + columnas - 1) // columnas
    lienzo = Image.new("RGB", (columnas * (cw + pad) + pad, filas * (ch + cab + pad) + pad),
                       (150, 150, 150))
    dib = ImageDraw.Draw(lienzo)
    f = _fuente(16)
    for k, celda in enumerate(imagenes):
        x = pad + (k % columnas) * (cw + pad)
        y = pad + (k // columnas) * (ch + cab + pad)
        rot = rotulos[k] if rotulos else f"{k + 1}"
        dib.text((x, y + 3), rot, fill=(0, 0, 0), font=f)
        for j, im in enumerate(celda):
            lienzo.paste(im.resize((w, h)), (x + j * (w + 6), y + cab))
    return lienzo


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("-o", "--salida", type=Path)
    ap.add_argument("--dpi", type=int, default=60)
    ap.add_argument("--columnas", type=int, default=2)
    ap.add_argument("--diapo", type=int, help="renderiza solo esa diapositiva, a 110 dpi")
    ap.add_argument("--comparar", type=Path, help="otro PDF para poner al lado (izq: este)")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if a.diapo:
            (tmp / "a").mkdir()
            ims = rasterizar(a.pdf, tmp / "a", 110, a.diapo)
            out = a.salida or a.pdf.with_name(f"{a.pdf.stem}_diapo{a.diapo}.png")
            shutil.copy(ims[0], out)
            print(out)
            return
        (tmp / "a").mkdir()
        nuevos = [Image.open(p).convert("RGB") for p in rasterizar(a.pdf, tmp / "a", a.dpi)]
        if a.comparar:
            (tmp / "b").mkdir()
            otros = [Image.open(p).convert("RGB") for p in rasterizar(a.comparar, tmp / "b", a.dpi)]
            n = max(len(nuevos), len(otros))
            vacio = Image.new("RGB", nuevos[0].size, (220, 220, 220))
            celdas = [[nuevos[i] if i < len(nuevos) else vacio, otros[i] if i < len(otros) else vacio]
                      for i in range(n)]
            rot = [f"{i + 1}   izq: {a.pdf.name}   der: {a.comparar.name}" for i in range(n)]
            img = hoja(celdas, 1, rot)
            out = a.salida or a.pdf.with_name(f"{a.pdf.stem}_comparacion.png")
        else:
            img = hoja([[i] for i in nuevos], a.columnas)
            out = a.salida or a.pdf.with_name(f"{a.pdf.stem}_hoja.png")
        img.save(out)
        print(f"{out}  ({len(nuevos)} diapositivas)")


if __name__ == "__main__":
    main()
