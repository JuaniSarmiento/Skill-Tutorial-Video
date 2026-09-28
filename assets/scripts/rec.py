#!/usr/bin/env python3
"""Graba la pantalla y anota marcas de tiempo. Linux y Windows.

Reemplazo multiplataforma de rec.sh, que es bash y x11grab. Este usa la capa de
plataforma, asi que en Windows graba con gdigrab sin cambiar nada del flujo.

Sale en .mkv a proposito: el Matroska sobrevive a que lo corten de golpe. Un .mp4
cortado sin cerrar queda ilegible, porque el indice se escribe al final.

Y el pid que guarda es el de ffmpeg DE VERDAD. rec.sh guardaba el de `setsid`,
que es otro proceso: al cortar mataba al equivocado y dejaba un ffmpeg huerfano
grabando nueve minutos de mas. Popen devuelve el pid real y no hace falta buscarlo.

uso:
    rec.py start <nombre>
    rec.py mark  <nombre> "lo que esta pasando"
    rec.py stop  <nombre>
"""
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from plataforma import SISTEMA, cmd_captura  # noqa: E402

RAIZ = Path(os.environ.get("TUT_ROOT", os.getcwd())) / "raw"


def _vive(pid: int) -> bool:
    if SISTEMA == "windows":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, text=True).stdout
        return str(pid) in out
    return Path(f"/proc/{pid}").exists()


def start(nombre: str) -> None:
    RAIZ.mkdir(parents=True, exist_ok=True)
    destino = RAIZ / f"{nombre}.mkv"
    log = open(RAIZ / f"{nombre}.log", "wb")
    extra = {}
    if SISTEMA == "windows":
        # CREATE_NEW_CONSOLE (no DETACHED_PROCESS): GenerateConsoleCtrlEvent
        # -que es lo que manda CTRL_BREAK_EVENT en stop()- necesita que el
        # proceso tenga una consola asociada, aunque quede oculta. Va junto
        # con CREATE_NEW_PROCESS_GROUP: sin ese flag, el PID del hijo no es
        # el id de ningun grupo de consola propio, y CTRL_BREAK_EVENT no le
        # llega a nadie (lo manda GenerateConsoleCtrlEvent contra un id de
        # GRUPO de procesos, no contra un PID cualquiera).
        extra["creationflags"] = subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        extra["startupinfo"] = si
    else:
        extra["start_new_session"] = True
    proc = subprocess.Popen(cmd_captura(str(destino)), stdin=subprocess.DEVNULL,
                            stdout=log, stderr=log, **extra)
    time.sleep(1.2)
    if proc.poll() is not None:
        sys.exit(f"  ffmpeg murio al arrancar. Mira {RAIZ / (nombre + '.log')}")
    (RAIZ / f"{nombre}.t0").write_text(f"{time.time()}")
    (RAIZ / f"{nombre}.pid").write_text(str(proc.pid))
    (RAIZ / f"{nombre}.marks").write_text("")
    print(f"  grabando {nombre}  (pid {proc.pid})")


def mark(nombre: str, texto: str) -> None:
    t0 = float((RAIZ / f"{nombre}.t0").read_text())
    linea = f"{time.time() - t0:.1f}\t{texto}\n"
    with open(RAIZ / f"{nombre}.marks", "a", encoding="utf-8") as f:
        f.write(linea)
    print("  " + linea.strip())


def _corte_prolijo(pid: int, matar, vivo, intentos: int = 20, espera: float = 0.4) -> bool:
    """Pide el corte prolijo UNA vez y espera a que el proceso termine solo.

    `matar` y `vivo` se inyectan para poder probar la espera/reintento sin
    Windows real ni procesos de verdad (ver tests/test_rec_corte.py).
    Devuelve True si terminó solo dentro de los intentos, False si no.
    """
    matar(pid)
    for _ in range(intentos):
        if not vivo(pid):
            return True
        time.sleep(espera)
    return False


def _matar_prolijo(pid: int) -> None:
    if SISTEMA == "windows":
        import signal
        # GenerateConsoleCtrlEvent (lo que hace os.kill con CTRL_BREAK_EVENT
        # en Windows) necesita que el proceso comparta consola o grupo de
        # consola con quien lo manda: por eso start() lo lanza con
        # CREATE_NEW_CONSOLE + CREATE_NEW_PROCESS_GROUP. taskkill /F equivale
        # a un SIGKILL y corrompe el .mkv a mitad de escribir un cluster
        # ("invalid as first byte of an EBML number", visto en la práctica).
        os.kill(pid, signal.CTRL_BREAK_EVENT)
    else:
        import signal
        try:
            os.kill(pid, signal.SIGINT)
        except ProcessLookupError:
            pass


def _verificar_grabacion(destino: Path, ffprobe_duracion, ffprobe_frames) -> tuple[bool, str]:
    """Confirma que la grabación quedó completa.

    El corte con CTRL_BREAK_EVENT puede dejar el .mkv sin trailer (sin
    duración en los metadatos) aunque los frames estén todos ahí: Matroska
    escribe el índice de duración al final, y un corte -aunque prolijo- no
    siempre le da tiempo a ffmpeg de cerrarlo antes de que el proceso baje.
    Eso NO es lo mismo que una grabación rota. Antes de abortar, se verifica
    con `ffprobe -count_frames` que los frames estén completos.
    """
    dur = ffprobe_duracion(destino)
    if dur:
        return True, f"{float(dur):.1f}s  ->  {destino}"
    frames = ffprobe_frames(destino)
    if frames:
        return True, f"sin duracion en metadata, {frames} frames verificados  ->  {destino}"
    return False, f"ATENCION: {destino} no tiene duracion legible ni frames verificables. La grabacion fallo."


def _ffprobe_duracion(destino: Path) -> str:
    return subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                           "-of", "csv=p=0", str(destino)], capture_output=True, text=True).stdout.strip()


def _ffprobe_frames(destino: Path) -> str:
    return subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_entries",
                           "stream=nb_read_frames", "-of", "csv=p=0", str(destino)],
                          capture_output=True, text=True).stdout.strip()


def stop(nombre: str) -> None:
    pid_f = RAIZ / f"{nombre}.pid"
    if not pid_f.exists():
        sys.exit(f"  no hay grabacion llamada {nombre}")
    pid = int(pid_f.read_text())
    if not _corte_prolijo(pid, _matar_prolijo, _vive):
        # Ultimo recurso: el proceso no respondio al corte prolijo. Recien
        # aca se usa taskkill /F, que puede corromper el .mkv pero al menos
        # libera el proceso colgado.
        if SISTEMA == "windows":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    destino = RAIZ / f"{nombre}.mkv"
    ok, mensaje = _verificar_grabacion(destino, _ffprobe_duracion, _ffprobe_frames)
    if not ok:
        sys.exit(f"  {mensaje}")
    print(f"  {nombre}: {mensaje}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    accion, nombre = sys.argv[1], sys.argv[2]
    if accion == "start":
        start(nombre)
    elif accion == "mark":
        mark(nombre, " ".join(sys.argv[3:]))
    elif accion == "stop":
        stop(nombre)
    else:
        sys.exit(__doc__)
