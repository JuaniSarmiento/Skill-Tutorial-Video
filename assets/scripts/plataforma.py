#!/usr/bin/env python3
"""Los tres verbos que atan la skill al sistema operativo: capturar, tipear, enfocar.

Todo lo demas de la skill es ffmpeg y Python puro, y ya corre igual en los dos
lados. Aca esta lo unico que cambia.

    Linux    x11grab   ·  xdotool   ·  wmctrl
    Windows  gdigrab   ·  SendInput ·  SetForegroundWindow

En Windows NO hace falta nada instalado aparte de ffmpeg: la entrada va por
ctypes contra user32, que es la libreria estandar de Python. Y no hace falta
Xephyr, porque gdigrab captura el escritorio real sin el problema de Wayland.

Se tipea con KEYEVENTF_UNICODE, que manda el caracter Unicode directo en vez de
un codigo de tecla. Eso lo hace independiente del layout del teclado: las tildes
y la enie salen bien sin tocar la configuracion, que en Linux hay que forzar a
mano con setxkbmap.

uso:
    from plataforma import tipear, tecla, enfocar, titulo_activo, cmd_captura
    enfocar(ventana); tipear("hola, ¿que tal?"); tecla("ctrl", "s")

    plataforma.py info            que detecto y con que herramientas cuenta
    plataforma.py ventanas        lista las ventanas visibles, con su id
    plataforma.py activa          el titulo de la ventana enfocada
    plataforma.py captura f.png   una captura de pantalla (reemplaza a shot.sh)
"""
import os
import shutil
import subprocess
import sys
import time

SISTEMA = "windows" if sys.platform.startswith("win") else "linux"


def _falta(que: str, como: str) -> None:
    """Muere fuerte y explicando. Un fallo silencioso acá arruina una grabación
    entera, y eso no se descubre hasta que alguien mira el video."""
    sys.exit(f"  FALTA {que}.\n  {como}")


# ────────────────────────────── capturar ──────────────────────────────

def cmd_captura(salida: str, fps: int = 30, tamano: str = "1920x1080",
                pantalla: str | None = None, frames: int | None = None) -> list[str]:
    """Devuelve el comando ffmpeg de captura para este sistema.

    Devuelve el comando en vez de correrlo porque quien graba necesita el
    proceso vivo para poder cortarlo despues (ver rec.py).
    """
    if not shutil.which("ffmpeg"):
        _falta("ffmpeg", "Linux: sudo apt install ffmpeg | Windows: winget install Gyan.FFmpeg")
    base = ["ffmpeg", "-y", "-loglevel", "error"]
    if SISTEMA == "windows":
        # gdigrab captura el escritorio real. No hay problema de Wayland ni
        # hace falta un X anidado: en Windows esto simplemente anda.
        entrada = ["-f", "gdigrab", "-framerate", str(fps), "-draw_mouse", "0",
                   "-i", pantalla or "desktop"]
    else:
        entrada = ["-f", "x11grab", "-framerate", str(fps), "-video_size", tamano,
                   "-draw_mouse", "0", "-i", pantalla or os.environ.get("DISPLAY", ":0")]
    salidas = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p"]
    if frames:
        salidas = ["-frames:v", str(frames)]
    return base + entrada + salidas + [salida]


def captura_frame(salida: str, pantalla: str | None = None) -> str:
    subprocess.run(cmd_captura(salida, pantalla=pantalla, frames=1),
                   capture_output=True, check=True)
    return salida


# ────────────────────────────── tipear ──────────────────────────────

if SISTEMA == "windows":
    import ctypes
    from ctypes import wintypes

    _u32 = ctypes.WinDLL("user32", use_last_error=True)
    _KEYEVENTF_UNICODE, _KEYEVENTF_KEYUP, _INPUT_KEYBOARD = 0x0004, 0x0002, 1

    # Nombres de tecla como los de xdotool, para que los scripts no cambien.
    _VK = {
        "return": 0x0D, "enter": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B,
        "space": 0x20, "backspace": 0x08, "delete": 0x2E, "home": 0x24, "end": 0x23,
        "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
        "ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "super": 0x5B,
        "prior": 0x21, "next": 0x22,
        **{c: ord(c.upper()) for c in "abcdefghijklmnopqrstuvwxyz0123456789"},
        **{f"f{n}": 0x6F + n for n in range(1, 13)},
    }

    class _KBD(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

    class _IN(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("ki", _KBD)]
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    def _enviar(**kw) -> None:
        ev = _IN(type=_INPUT_KEYBOARD, ki=_KBD(**kw))
        if _u32.SendInput(1, ctypes.byref(ev), ctypes.sizeof(ev)) != 1:
            raise OSError(f"SendInput fallo: {ctypes.get_last_error()}")

    def _unicode(ch: str) -> None:
        for flags in (_KEYEVENTF_UNICODE, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP):
            _enviar(wVk=0, wScan=ord(ch), dwFlags=flags)

    def tipear(texto: str, delay_ms: int = 22) -> None:
        """Escribe el texto tal cual, caracter por caracter.

        KEYEVENTF_UNICODE manda el codepoint, no una tecla, asi que no depende
        del layout: con teclado en ingles o en latinoamericano sale igual.
        """
        for ch in texto:
            if ch == "\n":
                tecla("Return")
                continue
            _unicode(ch)
            time.sleep(delay_ms / 1000)

    def tecla(*combo: str, pausa: float = 0.25) -> None:
        """tecla("ctrl", "s")  ·  tecla("Return")  ·  tecla("ctrl+shift+p")"""
        partes = [p for c in combo for p in c.split("+")]
        codigos = []
        for p in partes:
            vk = _VK.get(p.lower())
            if vk is None:
                _falta(f"la tecla {p!r}", "agregala al diccionario _VK de plataforma.py")
            codigos.append(vk)
        for vk in codigos:
            _enviar(wVk=vk, wScan=0, dwFlags=0)
        for vk in reversed(codigos):
            _enviar(wVk=vk, wScan=0, dwFlags=_KEYEVENTF_KEYUP)
        time.sleep(pausa)

    # ───────────────────────── enfocar (Windows) ─────────────────────────

    def listar_ventanas() -> list[tuple[str, str]]:
        salida = []
        largo = _u32.GetWindowTextLengthW

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cb(hwnd, _):
            if _u32.IsWindowVisible(hwnd):
                n = largo(hwnd)
                if n:
                    buf = ctypes.create_unicode_buffer(n + 1)
                    _u32.GetWindowTextW(hwnd, buf, n + 1)
                    salida.append((hex(hwnd), buf.value))
            return True

        _u32.EnumWindows(cb, 0)
        return salida

    def enfocar(ventana: str) -> None:
        """Acepta un handle (0x...) o un pedazo del titulo."""
        hwnd = None
        if ventana.startswith("0x"):
            hwnd = int(ventana, 16)
        else:
            for h, t in listar_ventanas():
                if ventana.lower() in t.lower():
                    hwnd = int(h, 16)
                    break
        if hwnd is None:
            _falta(f"una ventana que diga {ventana!r}",
                   "corre: plataforma.py ventanas   para ver las que hay")
        _u32.ShowWindow(hwnd, 9)          # SW_RESTORE, por si esta minimizada
        _u32.SetForegroundWindow(hwnd)
        time.sleep(0.8)

    def titulo_activo() -> str:
        hwnd = _u32.GetForegroundWindow()
        n = _u32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        _u32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value

else:
    # ───────────────────────────── Linux ─────────────────────────────
    def _x(*args: str) -> subprocess.CompletedProcess:
        if not shutil.which(args[0]):
            _falta(args[0], "sudo apt install xdotool wmctrl")
        return subprocess.run(list(args), capture_output=True, text=True)

    def tipear(texto: str, delay_ms: int = 22) -> None:
        """Los no-ASCII van de a uno y lentos: xdotool los pierde en rafaga."""
        buf = ""

        def flush():
            nonlocal buf
            if buf:
                _x("xdotool", "type", "--delay", str(delay_ms), buf)
                buf = ""

        for ch in texto:
            if ord(ch) < 128:
                buf += ch
            else:
                flush()
                time.sleep(0.12)
                _x("xdotool", "type", "--delay", str(max(delay_ms, 60)), ch)
                time.sleep(0.12)
        flush()

    def tecla(*combo: str, pausa: float = 0.25) -> None:
        _x("xdotool", "key", "--clearmodifiers", *("+".join(combo).split(" ")))
        time.sleep(pausa)

    def listar_ventanas() -> list[tuple[str, str]]:
        out = _x("wmctrl", "-l").stdout
        vs = []
        for linea in out.splitlines():
            p = linea.split(None, 3)
            if len(p) == 4:
                vs.append((p[0], p[3]))
        return vs

    def enfocar(ventana: str) -> None:
        if ventana.startswith("0x"):
            _x("wmctrl", "-i", "-a", ventana)
        else:
            _x("wmctrl", "-a", ventana)
        time.sleep(0.8)

    def titulo_activo() -> str:
        return _x("xdotool", "getactivewindow", "getwindowname").stdout.strip()


# ────────────────────────────── diagnostico ──────────────────────────────

def info() -> None:
    print(f"\n  sistema        {SISTEMA}")
    if SISTEMA == "linux":
        print(f"  sesion grafica {os.environ.get('XDG_SESSION_TYPE', '?')}")
        print(f"  DISPLAY        {os.environ.get('DISPLAY', '(sin definir)')}")
    print("\n  herramientas")
    faltan = []
    req = ["ffmpeg", "ffprobe"] + ([] if SISTEMA == "windows" else ["xdotool", "wmctrl"])
    for h in req + ["tesseract"]:
        ok = shutil.which(h)
        print(f"    {h:<12} {'ok' if ok else 'FALTA'}")
        if not ok and h != "tesseract":
            faltan.append(h)
    if SISTEMA == "linux" and os.environ.get("XDG_SESSION_TYPE") == "wayland":
        print("\n  AVISO: estas en Wayland. x11grab captura NEGRO sin reportar error.")
        print("         Levanta el entorno anidado:  entorno.sh start")
    if SISTEMA == "windows":
        print("\n  En Windows no hace falta Xephyr: gdigrab captura el escritorio real.")
    print(f"\n  captura: {' '.join(cmd_captura('salida.mkv')[:9])} ...")
    print(f"  ventanas visibles: {len(listar_ventanas())}\n")
    if faltan:
        sys.exit(f"  Faltan herramientas: {', '.join(faltan)}")


if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) > 1 else "info"
    if accion == "info":
        info()
    elif accion == "ventanas":
        for h, t in listar_ventanas():
            print(f"  {h:<12} {t}")
    elif accion == "activa":
        print(titulo_activo())
    elif accion == "captura":
        destino = sys.argv[2] if len(sys.argv) > 2 else "captura.png"
        print(" ", captura_frame(destino))
    else:
        sys.exit(__doc__)
