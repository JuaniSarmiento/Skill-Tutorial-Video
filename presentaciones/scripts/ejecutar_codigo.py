#!/usr/bin/env python3
"""Ejecuta los .py de una presentación y captura su salida REAL, lista para mostrar.

Por qué existe: una salida tipeada a mano en la diapositiva se desfasa del código en cuanto
alguien lo toca, y nadie lo nota hasta que un alumno lo ejecuta y ve otra cosa.

Cómo ejecuta cada archivo:
- copia la carpeta del archivo a una carpeta temporal NEUTRA (así los import y los archivos de
  datos vecinos siguen funcionando) y corre `python archivo.py` desde ahí;
- junta stdout y stderr en el orden en que salen (como `2>&1` en la terminal);
- reemplaza las rutas absolutas (la carpeta temporal, el home del usuario) para que un
  traceback no muestre `/home/<persona>/...` en una diapositiva pública;
- `entrada` (opcional) se manda por stdin, para programas que usan input().

Uso suelto:
    python ejecutar_codigo.py archivo.py [otro.py ...] [--entrada "3\\n4\\n"]
    python ejecutar_codigo.py especificacion.yaml        # corre todos los referenciados
"""
from __future__ import annotations

import argparse
import datetime
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NEUTRA = "codigo"   # nombre de la carpeta que se ve si algo imprime su ruta
ECO = """import builtins
_input = builtins.input
def _eco(prompt=""):
    valor = _input(prompt)
    print(valor)
    return valor
builtins.input = _eco
"""


def ejecutar(archivo: Path, entrada: str | None = None, timeout: int = 60,
             python: str | None = None) -> dict:
    archivo = Path(archivo).resolve()
    python = python or sys.executable
    with tempfile.TemporaryDirectory(prefix="tupad-") as tmp:
        dest = Path(tmp) / NEUTRA
        shutil.copytree(archivo.parent, dest,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", "venv"))
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        if entrada is not None:
            # Con stdin redirigido, input() no muestra lo que se "tipeó" y la salida queda
            # `a: b: suma: 7`. Un sitecustomize hace eco de cada valor leído, como en la
            # terminal real, sin agregar marcos al traceback del programa.
            eco = Path(tmp) / "_eco"
            eco.mkdir()
            (eco / "sitecustomize.py").write_text(ECO, encoding="utf-8")
            env["PYTHONPATH"] = str(eco)
        try:
            p = subprocess.run([python, archivo.name], cwd=dest, input=entrada or "",
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               timeout=timeout, env=env)
            texto, codigo = p.stdout, p.returncode
        except subprocess.TimeoutExpired as e:
            texto = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            texto += f"\n[cortado: superó {timeout} s]"
            codigo = None
        texto = limpiar_rutas(texto, Path(tmp), dest)
    return {"archivo": archivo.name, "salida": texto, "codigo": codigo,
            "comando": f"$ python3 {archivo.name}"}


def limpiar_rutas(texto: str, tmp: Path, dest: Path) -> str:
    """'File "/tmp/tupad-x/codigo/a.py"' -> 'File "a.py"'; el home queda como '~'."""
    for base in sorted({str(dest), str(dest.resolve()), str(tmp), str(tmp.resolve())},
                       key=len, reverse=True):
        texto = texto.replace(base + os.sep, "").replace(base, ".")
    texto = texto.replace(str(Path.home()), "~")
    # cualquier ruta de usuario que se haya colado igual (otro home, Windows)
    texto = re.sub(r"/home/[^/\s\"']+", "~", texto)
    texto = re.sub(r"[A-Za-z]:\\Users\\[^\\\s\"']+", "~", texto)
    return texto


def recortar(texto: str, primeras: int | None = None, ultimas: int | None = None,
             marca: str = "… ({n} líneas omitidas)") -> str:
    """Abrevia una salida larga dejando las primeras y últimas líneas reales."""
    lineas = texto.rstrip("\n").split("\n")
    p, u = primeras or 0, ultimas or 0
    if (p or u) and len(lineas) > p + u + 1:
        omit = len(lineas) - p - u
        return "\n".join(lineas[:p] + [marca.format(n=omit)] + (lineas[-u:] if u else []))
    return "\n".join(lineas)


def bitacora(resultados: list[dict]) -> str:
    """Texto para guardar junto a la presentación: qué se ejecutó, con qué Python y cuándo."""
    cab = (f"# Salidas reales, capturadas con Python {platform.python_version()} el "
           f"{datetime.datetime.now():%Y-%m-%d %H:%M}, desde una carpeta neutra.\n"
           "# stdout y stderr juntos (2>&1), en el orden en que aparecen en la terminal.\n")
    partes = [cab]
    for r in resultados:
        partes.append(f"\n{r['comando']}\n{r['salida'].rstrip()}\n[código de salida: {r['codigo']}]\n")
    return "".join(partes)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivos", nargs="+", type=Path)
    ap.add_argument("--entrada", help="texto para stdin (usar \\n para saltos)")
    ap.add_argument("--timeout", type=int, default=60)
    a = ap.parse_args()
    archivos = []
    for f in a.archivos:
        if f.suffix in (".yaml", ".yml", ".json"):
            sys.path.insert(0, str(Path(__file__).parent))
            from build import cargar_spec, programas_de
            spec = cargar_spec(f)
            archivos += [(ruta, ent) for ruta, ent in programas_de(spec, f.parent)]
        else:
            archivos.append((f, a.entrada.encode().decode("unicode_escape") if a.entrada else None))
    res = [ejecutar(f, e, a.timeout) for f, e in archivos]
    print(bitacora(res))


if __name__ == "__main__":
    main()
