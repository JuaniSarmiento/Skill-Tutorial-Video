#!/usr/bin/env python3
"""Escena `codigo` (H4, HITO3.md): lo que se prepara en Python antes de abrir Chrome."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def fragmento(ruta, desde=None, hasta=None, lineas=None) -> list[tuple[int, str]]:
    """[(número de línea real, texto)] del archivo, entero o de `desde` a `hasta` (inclusive).

    `lineas` ("4-11") es un atajo de desde/hasta. El texto es el del archivo tal cual: la
    escena muestra el código real, nunca uno tipeado a mano en el spec.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ValueError(f"no existe el archivo de código {str(ruta)!r}")
    todas = ruta.read_text(encoding="utf-8").splitlines()
    if lineas is not None:
        partes = str(lineas).split("-")
        if len(partes) != 2 or not all(p.strip().isdigit() for p in partes):
            raise ValueError(f"{ruta.name}: 'lineas' va como \"desde-hasta\" (ej. \"4-11\"), vino {lineas!r}")
        desde, hasta = (int(p) for p in partes)
    desde = 1 if desde is None else desde
    hasta = len(todas) if hasta is None else hasta
    if not 1 <= desde <= hasta <= len(todas):
        raise ValueError(f"{ruta.name}: el rango {desde}-{hasta} no está dentro de sus {len(todas)} líneas")
    return [(n, todas[n - 1]) for n in range(desde, hasta + 1)]


# Clase de color de cada token (la paleta sale del brand, en codigo.html). El orden importa:
# Operator.Word ("in", "and", "not") se lee como palabra clave, no como operador.
CLASES = (("Keyword", "kw"), ("Operator.Word", "kw"), ("Name.Function", "fn"), ("Name.Class", "fn"),
          ("Name.Decorator", "fn"), ("Name.Builtin", "bi"), ("Literal.String", "str"),
          ("Literal.Number", "num"), ("Comment", "com"), ("Operator", "op"), ("Punctuation", "op"))


def _clase(tipo) -> str:
    nombre = str(tipo).removeprefix("Token.")
    return next((c for prefijo, c in CLASES if nombre == prefijo or nombre.startswith(prefijo + ".")), "")


def tokenizar(renglones: list[str], nombre: str | None) -> list[list[list[str]]]:
    """Por renglón, [[clase, texto], ...] con los tokens vecinos de la misma clase juntos.

    Se tokeniza en Python con Pygments (el lenguaje sale de la extensión de `nombre`), nunca
    en el navegador. `nombre` None es pseudocódigo: un solo token sin clase por renglón.
    """
    if nombre is None:
        return [[["", r]] if r else [] for r in renglones]
    try:
        from pygments.lexers import get_lexer_for_filename
        from pygments.util import ClassNotFound
    except ImportError as e:
        raise RuntimeError("la escena codigo necesita Pygments: corré con uv run --with pygments ...") from e
    try:
        lexer = get_lexer_for_filename(nombre, stripnl=False, stripall=False)
    except ClassNotFound:
        return tokenizar(renglones, None)
    filas, fila = [], []
    for tipo, texto in lexer.get_tokens("\n".join(renglones)):
        for i, pedazo in enumerate(texto.split("\n")):
            if i:
                filas.append(fila)
                fila = []
            if not pedazo:
                continue
            clase = _clase(tipo)
            if fila and fila[-1][0] == clase:
                fila[-1][1] += pedazo
            else:
                fila.append([clase, pedazo])
    filas.append(fila)
    return filas[:len(renglones)]


def diff_lineas(antes: list[str], despues: list[str]) -> list[tuple]:
    """Diff por líneas con la subsecuencia común más larga (LCS).

    [("=", i, j) | ("-", i, None) | ("+", None, j)] en orden de lectura; en un renglón
    cambiado, el viejo se va antes de que entre el nuevo. Idea del bloque `code-diff` de
    HyperFrames (Apache 2.0); el código es propio.
    """
    n, m = len(antes), len(despues)
    # largo[i][j] = LCS de antes[i:] y despues[j:]
    largo = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            largo[i][j] = (largo[i + 1][j + 1] + 1 if antes[i] == despues[j]
                           else max(largo[i + 1][j], largo[i][j + 1]))
    out, i, j = [], 0, 0
    while i < n or j < m:
        if i < n and j < m and antes[i] == despues[j]:
            out.append(("=", i, j))
            i, j = i + 1, j + 1
        elif i < n and (j == m or largo[i + 1][j] >= largo[i][j + 1]):
            out.append(("-", i, None))
            i += 1
        else:
            out.append(("+", None, j))
            j += 1
    return out


NEUTRA = "codigo"   # la carpeta que se ve si el programa imprime su ruta


def ejecutar(ruta, timeout: int = 60) -> dict:
    """{"comando": "$ python3 x.py", "lineas": [...]}: la salida REAL del programa.

    Como presentaciones/scripts/ejecutar_codigo.py: copia la carpeta del archivo a una
    carpeta temporal neutra (los import y archivos vecinos siguen andando), corre python3
    desde ahí, junta stdout y stderr (un traceback también es salida real) y saca las
    rutas de la carpeta temporal y del home. Un programa que no termina falla.
    """
    ruta = Path(ruta).resolve()
    if not ruta.is_file():
        raise ValueError(f"no existe el programa a ejecutar {str(ruta)!r}")
    python = shutil.which("python3") or sys.executable
    with tempfile.TemporaryDirectory(prefix="tut-codigo-") as tmp:
        dest = Path(tmp) / NEUTRA
        shutil.copytree(ruta.parent, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", "venv"))
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        try:
            p = subprocess.run([python, ruta.name], cwd=dest, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired as e:
            raise ValueError(f"{ruta.name} no terminó en {timeout} s: la salida de la escena tiene que ser "
                             "la de un programa que termina") from e
        texto = p.stdout
        for base in sorted({str(dest), str(dest.resolve()), tmp, str(Path(tmp).resolve())}, key=len, reverse=True):
            texto = texto.replace(base + os.sep, "").replace(base, NEUTRA)
        texto = texto.replace(str(Path.home()), "~")
    return {"comando": f"$ python3 {ruta.name}", "lineas": texto.rstrip("\n").splitlines()}
