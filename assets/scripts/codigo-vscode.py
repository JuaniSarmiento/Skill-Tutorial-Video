#!/usr/bin/env python3
"""Escribe código en VS Code con verificación de punta a punta.

Existe porque escribir a ciegas falló CUATRO veces seguidas, siempre igual y
siempre en silencio: el texto terminaba en el archivo equivocado o en la terminal,
sin un solo error, y sólo se descubría al correr el código.

Las tres cosas que verifica, en orden:
  1. que el archivo EXISTA antes de abrirlo (ctrl+P no crea archivos)
  2. que la ventana muestre ESE archivo antes de tipear una letra
  3. que el contenido en DISCO sea el esperado después de guardar

Si algo no cuadra, aborta y lo dice. Nunca sigue "a ver si sale".

uso: codigo-vscode.py <archivo> <<'EOF'
     ...las lineas a escribir...
     EOF
opciones: --append (va al final)  --linea N (inserta despues de la linea N)  --velocidad MS
"""
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from plataforma import SISTEMA, enfocar, tecla, tipear, titulo_activo  # noqa: E402

DISP = os.environ.get("DISPLAY", ":2")
WIN = os.environ.get("VSCODE_WIN", "")
PROY = Path(os.environ.get("PROYECTO", Path.home() / "Proyectos/Video-Tutoriales/biblioteca-vivo"))
E = {**os.environ, "DISPLAY": DISP}


def k(*teclas, pausa=0.25):
    tecla(*teclas, pausa=pausa)


def titulo() -> str:
    return titulo_activo()


def crear_en_camara(archivo: str) -> None:
    """Crea el archivo con `touch` en la terminal integrada.

    De las tres formas de crear un archivo en VS Code, es la única que funciona
    para automatizar Y la única que además es didáctica: el alumno ve cómo se
    crea un archivo desde la terminal, que es lo que va a hacer siempre.
      - "File: New File" del Command Palette escribe "New File" dentro del código
      - `code archivo.py` abre un editor pero no crea nada hasta que guardás
      - `touch archivo.py` crea el archivo de verdad, y se puede verificar en disco

    En Windows la terminal integrada es PowerShell y `touch` no existe: ahi va
    `ni`, que es el alias de New-Item y hace lo mismo. Si no se distingue, el
    comando falla con "no se reconoce" y el archivo nunca se crea, que es
    exactamente el fallo silencioso que esta funcion existe para evitar.
    """
    crear = f"ni {archivo}" if SISTEMA == "windows" else f"touch {archivo}"
    # Enfocar ANTES de abrir la paleta. Sin esto la funcion asume que VS Code ya
    # tiene el foco, que era cierto de casualidad porque lo dejaba el comando
    # anterior: si el foco esta en otra ventana, el comando entero se tipea ahi.
    if WIN:
        enfocar(WIN)
    k("ctrl+shift+p", pausa=1.2)
    tipear("Terminal: Focus on Terminal View", delay_ms=40)
    time.sleep(1.3); k("Return", pausa=2.5)
    tipear(crear, delay_ms=35)
    time.sleep(1.0); k("Return", pausa=2.5)
    destino = PROY / archivo
    if not destino.exists():
        sys.exit(f"  ABORTADO: `{crear}` no creó {destino}.")
    print(f"  archivo creado en camara: {archivo}")


def abrir(archivo: str) -> None:
    destino = PROY / archivo if not archivo.startswith("/") else Path(archivo)
    # 1) el archivo tiene que existir: ctrl+P NO crea archivos nuevos
    if not destino.exists():
        sys.exit(f"  ABORTADO: {destino} no existe. Usá --crear o creálo antes.")
    if WIN:
        enfocar(WIN)
    k("ctrl+p", pausa=1.2)
    tipear(destino.name, delay_ms=45)
    time.sleep(1.5)
    k("Return", pausa=2.0)
    # 2) la ventana tiene que mostrar ese archivo (esto atrapa el foco en la terminal)
    t = titulo()
    if destino.name not in t:
        sys.exit(f"  ABORTADO: la ventana dice '{t[:70]}', esperaba '{destino.name}'.")

    # 3) sincronizar con el disco. Si el archivo se tocó por fuera (un script, git),
    # VS Code se queda con su copia en memoria y al guardar dice "the content of the
    # file is newer" y NO guarda: el código se ve en pantalla pero nunca llega al
    # disco. Revert descarta la copia en memoria y relee el archivo.
    k("ctrl+shift+p", pausa=1.2)
    tipear("File: Revert File", delay_ms=40)
    time.sleep(1.3)
    k("Return", pausa=1.8)


def escribir(lineas: list[str], ms: int) -> None:
    for i, linea in enumerate(lineas):
        if i:
            k("Return", pausa=0.13)
        k("shift+Home", pausa=0.07)
        if linea.strip():
            tipear(linea, delay_ms=ms)
        else:
            k("Delete", pausa=0.05)
        time.sleep(0.28)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    archivo = args[0]
    ms = 28
    linea_ins = None
    for i, a in enumerate(sys.argv):
        if a == "--velocidad": ms = int(sys.argv[i + 1])
        if a == "--linea": linea_ins = int(sys.argv[i + 1])

    lineas = sys.stdin.read().rstrip("\n").split("\n")

    # xdotool escribe bien ASCII y los latinos (tildes, ñ), pero se cuelga con
    # los de dibujo de cajas y similares: el tipeo muere a mitad y el resto del
    # bloque no llega. Mejor rechazarlo acá que descubrirlo en el video.
    PERMITIDOS = set("áéíóúüñÁÉÍÓÚÜÑ¿¡°")
    raros = {c for l in lineas for c in l if ord(c) > 127 and c not in PERMITIDOS}
    if raros:
        sys.exit("  ABORTADO: caracteres que xdotool no escribe: "
                 + " ".join(f"{c!r}(U+{ord(c):04X})" for c in sorted(raros))
                 + "\n  Usá ASCII para el codigo (las tildes y la ñ sí van).")

    destino = PROY / archivo
    if not destino.exists() and "--crear" not in sys.argv:
        sys.exit(f"  ABORTADO: {destino} no existe. Usá --crear para crearlo en cámara.")
    antes = destino.read_text() if destino.exists() else ""

    if "--crear" in sys.argv:
        crear_en_camara(archivo)
    abrir(archivo)

    if linea_ins:
        k("ctrl+g", pausa=1.2)
        tipear(str(linea_ins), delay_ms=60)
        time.sleep(1.0); k("Return", pausa=1.2); k("End", pausa=1.0); k("Return", pausa=0.2)
    else:
        k("ctrl+End", pausa=1.2)
        if antes.strip():
            k("Return", pausa=0.2)

    escribir(lineas, ms)
    time.sleep(0.8)
    k("ctrl+s", pausa=2.0)

    # 3) lo que importa: qué quedó en el disco
    despues = destino.read_text()
    faltan = [l.strip() for l in lineas if l.strip() and l.strip() not in despues]
    if faltan:
        sys.exit(f"  ABORTADO: no llegaron al archivo {len(faltan)} línea(s). "
                 f"Primera: {faltan[0][:60]}")
    print(f"  ✅ {len(lineas)} líneas en {archivo} · verificado en disco")


if __name__ == "__main__":
    main()
