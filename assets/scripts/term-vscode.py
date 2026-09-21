#!/usr/bin/env python3
"""Corre un comando en la terminal integrada de VS Code, a la vista.

Existe por un fallo concreto: `ctrl+grave` NO abre la terminal con teclado
latinoamericano, asi que el comando terminaba tipeado DENTRO del archivo de
codigo, sin un solo error. El Command Palette no depende del layout.

uso: term-vscode.py 'python probar.py'
     term-vscode.py --editor            (devuelve el foco al editor)
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
from plataforma import enfocar, tecla, tipear, titulo_activo  # noqa: E402

DISP = os.environ.get("DISPLAY", ":2")
WIN = os.environ.get("VSCODE_WIN", "")
E = {**os.environ, "DISPLAY": DISP}


def k(*teclas, pausa=0.25):
    tecla(*teclas, pausa=pausa)


def paleta(comando: str, pausa=2.0):
    k("ctrl+shift+p", pausa=1.2)
    tipear(comando, delay_ms=40)
    time.sleep(1.3)
    k("Return", pausa=pausa)


def main() -> None:
    if WIN:
        enfocar(WIN)

    if "--editor" in sys.argv:
        paleta("View: Focus Active Editor Group")
        print("  foco devuelto al editor")
        return

    comando = sys.argv[1]
    espera = 4.0
    for i, a in enumerate(sys.argv):
        if a == "--espera":
            espera = float(sys.argv[i + 1])

    paleta("Terminal: Focus on Terminal View", pausa=2.5)
    tipear(comando, delay_ms=45)
    time.sleep(1.2)
    k("Return", pausa=espera)
    print(f"  corrido en terminal: {comando}")


if __name__ == "__main__":
    main()
