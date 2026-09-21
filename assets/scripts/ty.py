#!/usr/bin/env python3
"""Tipea texto en la ventana que se este manejando. Linux y Windows.

Va por la capa de plataforma, asi que en Windows escribe con SendInput y en
Linux con xdotool, sin que el resto del flujo cambie.

La ventana se elige con la variable OC_WIN: un id (0x...) o un pedazo del
titulo. Si no esta definida, escribe en la que ya tiene el foco.

uso: ty.py 'texto con tildes' [--enter] [--delay MS]
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from plataforma import enfocar, tecla, tipear  # noqa: E402


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    delay = 22
    for i, a in enumerate(sys.argv):
        if a == "--delay":
            delay = int(sys.argv[i + 1])

    ventana = os.environ.get("OC_WIN")
    if ventana:
        enfocar(ventana)

    tipear(args[0], delay_ms=delay)
    if "--enter" in sys.argv:
        time.sleep(0.8)
        tecla("Return")


main()
