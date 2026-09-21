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
        extra["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008  # DETACHED
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


def stop(nombre: str) -> None:
    pid_f = RAIZ / f"{nombre}.pid"
    if not pid_f.exists():
        sys.exit(f"  no hay grabacion llamada {nombre}")
    pid = int(pid_f.read_text())
    if SISTEMA == "windows":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        import signal
        try:
            os.kill(pid, signal.SIGINT)
        except ProcessLookupError:
            pass
    for _ in range(20):
        if not _vive(pid):
            break
        time.sleep(0.4)
    destino = RAIZ / f"{nombre}.mkv"
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(destino)], capture_output=True, text=True).stdout.strip()
    if not dur:
        sys.exit(f"  ATENCION: {destino} no tiene duracion legible. La grabacion fallo.")
    print(f"  {nombre}: {float(dur):.1f}s  ->  {destino}")


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
