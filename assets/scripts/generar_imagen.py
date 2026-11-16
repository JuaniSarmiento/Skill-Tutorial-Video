#!/usr/bin/env python3
"""Generador de imágenes por defecto del formato «clase» (`TUT_GENERADOR`): un envoltorio de
`codex exec` con su herramienta de generación de imágenes (usa la cuenta con la que esté logueado
Codex; no hace falta una API paga).

uso: generar_imagen.py --prompt <texto> --salida <png> [--referencia <png>]...

Arma un encargo de una sola tarea, copia las referencias a un directorio temporal (el único lugar
donde Codex puede escribir), corre `codex exec -C <dir> --sandbox workspace-write -` con el encargo
por stdin (si stdin no se cierra, codex se queda esperando entrada) y copia el PNG a `--salida`.
Sale con 0 sólo si el PNG existe y es una imagen PNG.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PNG = b"\x89PNG\r\n\x1a\n"


def encargo(prompt: str, referencias: list[str], destino: str) -> str:
    """El texto que recibe Codex. Una sola tarea, sin código ni otros archivos."""
    partes = ["Tarea única: generar 1 imagen con tu herramienta de generación de imágenes. "
              "No escribas código, no instales nada y no toques otros archivos."]
    if referencias:
        nombres = ", ".join(referencias)
        partes.append(f"Adjuntá como referencia la{'s' if len(referencias) > 1 else ''} imagen{'es' if len(referencias) > 1 else ''} "
                      f"{nombres} (están en este directorio y también adjuntas al encargo).")
    partes.append(f"La imagen: {prompt}")
    partes.append(f"Guardala como PNG en {destino} (en este directorio). Cuando el archivo exista, terminaste.")
    return "\n\n".join(partes)


def comando(directorio: Path, referencias: list[Path]) -> list[str]:
    cmd = ["codex", "exec", "-C", str(directorio), "--sandbox", "workspace-write", "--skip-git-repo-check",
           "--enable", "image_generation"]
    for r in referencias:
        cmd.append(f"--image={r}")
    cmd.append("-")  # el encargo va por stdin
    return cmd


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--referencia", action="append", default=[])
    a = ap.parse_args(argv)
    if shutil.which("codex") is None:
        print("generar_imagen: no está el comando `codex` (instalalo y logueate, o apuntá TUT_GENERADOR a otro "
              "generador)", file=sys.stderr)
        return 2
    salida = Path(a.salida)
    with tempfile.TemporaryDirectory(prefix="generar-imagen-") as tmp_:
        tmp = Path(tmp_)
        refs = []
        for k, r in enumerate(a.referencia, 1):
            origen = Path(r)
            if not origen.is_file():
                print(f"generar_imagen: no existe la referencia {origen}", file=sys.stderr)
                return 2
            copia = tmp / f"referencia-{k}{origen.suffix or '.png'}"
            shutil.copy(origen, copia)
            refs.append(copia)
        destino = "imagen.png"
        texto = encargo(a.prompt, [r.name for r in refs], destino)
        try:
            r = subprocess.run(comando(tmp, refs), input=texto, capture_output=True, text=True,
                               timeout=int(os.environ.get("TUT_GENERADOR_TIMEOUT", "900")))
        except subprocess.TimeoutExpired:
            print("generar_imagen: codex no terminó a tiempo", file=sys.stderr)
            return 3
        hecho = tmp / destino
        if r.returncode != 0 or not hecho.is_file() or hecho.read_bytes()[:8] != PNG:
            print(f"generar_imagen: codex no dejó un PNG en {destino} (código {r.returncode}).\n"
                  f"{(r.stderr or r.stdout)[-800:]}", file=sys.stderr)
            return 1
        salida.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(hecho, salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
