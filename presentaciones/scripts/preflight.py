#!/usr/bin/env python3
"""Verifica lo que necesita la skill presentaciones-tupad y dice qué instalar si falta algo.

Uso: python preflight.py
Código de salida: 0 = todo lo obligatorio está; 1 = falta algo obligatorio.

Por qué importan las fuentes: si Inter o DejaVu Sans Mono no están instaladas, LibreOffice
las reemplaza por otras con métricas distintas, el texto ocupa más (o menos) y la
diagramación que se revisó deja de ser la que se ve. La hoja de contactos mentiría.
"""
import importlib.util
import platform
import shutil
import subprocess
import sys

faltan, avisos = [], []


def ok(cond, nombre, instalar, obligatorio=True):
    print(f"  [{'ok' if cond else 'FALTA' if obligatorio else 'aviso'}] {nombre}")
    if not cond:
        (faltan if obligatorio else avisos).append((nombre, instalar))


def fuente(nombre):
    if not shutil.which("fc-list"):
        return None
    out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True).stdout
    return any(nombre.lower() == f.strip().lower() for l in out.splitlines() for f in l.split(","))


def main():
    so = platform.system()
    print(f"Python {platform.python_version()} en {so}")
    ok(sys.version_info >= (3, 9), "Python 3.9 o superior", "instalar Python 3.9+")
    print("Módulos de Python (instalar en un venv: pip install -r requirements.txt):")
    for mod, pip in (("pptx", "python-pptx"), ("matplotlib", "matplotlib"), ("PIL", "Pillow")):
        ok(importlib.util.find_spec(mod) is not None, pip, f"pip install {pip}")
    ok(importlib.util.find_spec("yaml") is not None, "PyYAML (sin él, la spec va en JSON)",
       "pip install PyYAML", obligatorio=False)
    print("Programas del sistema:")
    ok(bool(shutil.which("soffice") or shutil.which("libreoffice")),
       "LibreOffice (exportar a PDF)",
       {"Linux": "sudo apt install libreoffice-impress", "Darwin": "brew install --cask libreoffice"}
       .get(so, "instalar LibreOffice desde libreoffice.org y agregar soffice al PATH"))
    ok(bool(shutil.which("pdftoppm")), "pdftoppm (rasterizar para revisar)",
       {"Linux": "sudo apt install poppler-utils", "Darwin": "brew install poppler"}
       .get(so, "instalar poppler y agregar pdftoppm al PATH"))
    print("Fuentes:")
    for f, inst in (("Inter", {"Linux": "sudo apt install fonts-inter",
                               "Darwin": "brew install --cask font-inter"}),
                    ("DejaVu Sans Mono", {"Linux": "sudo apt install fonts-dejavu-core",
                                          "Darwin": "brew install --cask font-dejavu"})):
        hay = fuente(f)
        if hay is None:
            ok(False, f"{f} (no hay fc-list: verificalo a mano)", inst.get(so, f"instalar {f}"),
               obligatorio=False)
        else:
            ok(hay, f, inst.get(so, f"instalar la fuente {f}"))
    if faltan:
        print("\nFalta lo obligatorio. Instalá:")
        for n, i in faltan:
            print(f"  - {n}: {i}")
    if avisos:
        print("\nRecomendado:")
        for n, i in avisos:
            print(f"  - {n}: {i}")
    if not faltan:
        print("\nTodo lo obligatorio está.")
    sys.exit(1 if faltan else 0)


if __name__ == "__main__":
    main()
