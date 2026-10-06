#!/usr/bin/env python3
"""Escena `codigo` (H4, HITO3.md): lo que se prepara en Python antes de abrir Chrome."""
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
