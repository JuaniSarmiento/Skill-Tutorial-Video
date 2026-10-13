#!/usr/bin/env python3
"""Escena `codigo` (H4, HITO3.md): lo que se prepara en Python antes de abrir Chrome."""
import copy
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
    if ruta.suffix not in INTERPRETES:
        raise ValueError(f"no sé ejecutar {ruta.name!r}: la salida real se arma para "
                         f"{', '.join(sorted(INTERPRETES))}, no para {ruta.suffix!r}")
    modulos = _node_modules(ruta.parent) if INTERPRETES[ruta.suffix] != "python3" else None
    with tempfile.TemporaryDirectory(prefix="tut-codigo-") as tmp:
        dest = Path(tmp) / NEUTRA
        shutil.copytree(ruta.parent, dest, ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", ".venv", "venv", "node_modules"))
        if modulos is not None:
            # node_modules pesa cientos de MB: no se copia, se enlaza (node resuelve igual).
            (Path(tmp) / "node_modules").symlink_to(modulos, target_is_directory=True)
        orden, comando = _orden(ruta, modulos)
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        try:
            p = subprocess.run(orden, cwd=dest, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired as e:
            raise ValueError(f"{ruta.name} no terminó en {timeout} s: la salida de la escena tiene que ser "
                             "la de un programa que termina") from e
        texto = p.stdout
        for base in sorted({str(dest), str(dest.resolve()), tmp, str(Path(tmp).resolve())}, key=len, reverse=True):
            texto = texto.replace(base + os.sep, "").replace(base, NEUTRA)
        texto = texto.replace(str(Path.home()), "~")
    return {"comando": comando, "lineas": texto.rstrip("\n").splitlines()}


# Cada extensión corre con el intérprete que usaría el alumno, y la terminal muestra ESE
# comando (una salida de un .ts presentada como "$ python3 x.py" le miente).
INTERPRETES = {".py": "python3", ".js": "node", ".mjs": "node", ".cjs": "node",
               ".ts": "tsx", ".mts": "tsx"}


def _node_modules(desde: Path) -> Path | None:
    """El node_modules del proyecto: el de la carpeta del archivo o el de un ancestro,
    como lo resuelve node."""
    for d in [desde, *desde.parents]:
        if (d / "node_modules").is_dir():
            return (d / "node_modules").resolve()
    return None


def _orden(ruta: Path, modulos: Path | None) -> tuple[list[str], str]:
    """(argv a ejecutar, comando que se ve en la terminal)."""
    interprete = INTERPRETES[ruta.suffix]
    if interprete == "python3":
        return [shutil.which("python3") or sys.executable, ruta.name], f"$ python3 {ruta.name}"
    if interprete == "node":
        return ["node", ruta.name], f"$ node {ruta.name}"
    # TypeScript: el tsx DEL PROYECTO, nunca `npx` bajando de la red al armar un spec.
    tsx = modulos / ".bin" / "tsx" if modulos else None
    if tsx is None or not tsx.exists():
        raise ValueError(f"{ruta.name}: para ejecutar TypeScript hace falta tsx en el proyecto "
                         "(npm i -D tsx en la carpeta del código)")
    return [str(tsx), ruta.name], f"$ npx tsx {ruta.name}"


MODOS = ("tipeo", "resaltar", "diff", "salida")


def _ruta(nombre, base_dir) -> Path:
    p = Path(nombre)
    return p if p.is_absolute() else Path(base_dir) / p


def _rango(lineas) -> tuple[int, int]:
    partes = str(lineas).split("-")
    if not 1 <= len(partes) <= 2 or not all(p.strip().isdigit() for p in partes):
        raise ValueError(f"'lineas' de resaltar va como \"7\" o \"5-6\", vino {lineas!r}")
    return int(partes[0]), int(partes[-1])


def resolver(spec: dict, base_dir) -> dict:
    """Copia del spec de la escena `codigo` con todo lo que el navegador no tiene que hacer:

      _codigo        {"archivo": nombre, "filas": [{"tokens", "antes", "despues"}]}: las
                     filas son la unión del código de antes y después del diff (sin diff,
                     las mismas), con el número de línea real de cada lado (None si no está)
      pasos[diff]    "_archivo": el nombre del archivo nuevo
      pasos[resaltar] "_filas": [primera, última] fila, contando en lo que se ve en ese
                     momento (antes o después del diff, según el orden de los pasos)
      pasos[salida]  "_salida": la salida real de ejecutar el programa

    Las rutas relativas (archivo, diff.archivo, salida.ejecutar) son relativas a `base_dir`.
    """
    if "_codigo" in spec:
        raise ValueError("'_codigo' no es un campo del spec: lo genera resolver() desde el archivo")
    if ("archivo" in spec) == ("pseudocodigo" in spec):
        raise ValueError("la escena codigo lleva 'archivo' (código real, con 'desde'/'hasta' o 'lineas' "
                         "opcionales) o, sólo para pseudocódigo explícito, 'pseudocodigo'; uno de los dos")
    out = copy.deepcopy(spec)
    pasos = out.get("pasos", [])
    for p in pasos:
        if p.get("modo") not in MODOS:
            raise ValueError(f"paso con modo {p.get('modo')!r}: los modos son {', '.join(MODOS)}")
    modos = [p["modo"] for p in pasos]
    for m in ("tipeo", "diff", "salida"):
        if modos.count(m) > 1:
            raise ValueError(f"la escena codigo lleva un solo paso {m!r}")
    if "tipeo" in modos and "diff" in modos and modos.index("tipeo") > modos.index("diff"):
        raise ValueError("el tipeo va antes del diff: se tipea el código de partida")
    ts = [p["t"] for p in pasos if isinstance(p.get("t"), (int, float))]
    if ts != sorted(ts):
        raise ValueError("los pasos van en el orden en que suenan sus cues")

    if "archivo" in out:
        nombre = Path(out["archivo"]).name
        antes = codigo_de(_ruta(out["archivo"], base_dir), out)
    else:
        nombre, antes = None, list(enumerate(str(out["pseudocodigo"]).splitlines(), 1))
    despues = antes
    diff = next((p for p in pasos if p["modo"] == "diff"), None)
    if diff is not None:
        if "archivo" not in diff:
            raise ValueError("el paso diff nombra el 'archivo' con el código nuevo")
        despues = codigo_de(_ruta(diff["archivo"], base_dir), diff)
        diff["_archivo"] = Path(diff["archivo"]).name
    filas, renglones = [], []
    for _, i, j in diff_lineas([l for _, l in antes], [l for _, l in despues]):
        renglones.append(antes[i][1] if i is not None else despues[j][1])
        filas.append({"antes": antes[i][0] if i is not None else None,
                      "despues": despues[j][0] if j is not None else None})
    for f, tokens in zip(filas, tokenizar(renglones, nombre)):
        f["tokens"] = tokens

    lado = "antes"
    for p in pasos:
        if p["modo"] == "diff":
            lado = "despues"
        elif p["modo"] == "resaltar":
            desde, hasta = _rango(p.get("lineas"))
            numeros = [f[lado] for f in filas if f[lado] is not None]
            if desde > hasta or not set(range(desde, hasta + 1)) <= set(numeros):
                raise ValueError(f"resaltar {p['lineas']!r}: en ese momento se ven las líneas "
                                 f"{min(numeros)}-{max(numeros)}")
            idx = [k for k, f in enumerate(filas) if f[lado] is not None and desde <= f[lado] <= hasta]
            p["_filas"] = [idx[0], idx[-1]]
        elif p["modo"] == "salida":
            if "ejecutar" not in p:
                raise ValueError("el paso salida nombra el programa a 'ejecutar' (su salida real)")
            p["_salida"] = ejecutar(_ruta(p["ejecutar"], base_dir))
    out["_codigo"] = {"archivo": nombre or "pseudocódigo", "filas": filas}
    return out


def codigo_de(ruta: Path, d: dict) -> list[tuple[int, str]]:
    return fragmento(ruta, d.get("desde"), d.get("hasta"), d.get("lineas"))
