"""Encoder de video centralizado: decide libx264 (software) o h264_vaapi una sola vez por proceso.

Todos los `libx264` escritos a mano de editar.py y escena.py pasan por `vf()` + `cv_args()`.
Sin TUT_ENCODER: software, idéntico al Hito 1 (G3). `auto` prueba VAAPI codificando 1 cuadro
de verdad (R-1.4: nunca por si existe /dev/dri/renderD128) y cae a software con un aviso si
no anda. `vaapi` exige VAAPI y aborta si no hay (sin respaldo).

uso interno:
  vf("crop=...")           -> cadena de filtros lista (VAAPI le agrega el hwupload)
  cv_args(crf=20)           -> args de ffmpeg desde "-c:v" en adelante
"""
import functools
import os
import subprocess
import sys

MODOS = ("auto", "vaapi", "software")
DEVICE_DEFAULT = "/dev/dri/renderD128"


class EncoderError(RuntimeError):
    """TUT_ENCODER=vaapi sin VAAPI disponible: no hay respaldo posible."""


def _device() -> str:
    return os.environ.get("TUT_VAAPI_DEVICE", DEVICE_DEFAULT)


def _probar_vaapi(device: str) -> tuple[bool, str]:
    """Codifica 1 cuadro de prueba con VAAPI. (disponible, motivo-si-no-lo-está)."""
    res = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=128x128:r=1:d=1",
         "-vf", "format=nv12,hwupload", "-vaapi_device", device, "-c:v", "h264_vaapi",
         "-frames:v", "1", "-f", "null", "-"],
        capture_output=True, text=True)
    if res.returncode == 0:
        return True, ""
    lineas = [l for l in res.stderr.strip().splitlines() if l.strip()]
    return False, (lineas[-1] if lineas else "error desconocido al probar VAAPI")


@functools.lru_cache(maxsize=1)
def _elegido() -> tuple[str, str]:
    """(modo_real, device). 'vaapi' o 'software'. Se decide una sola vez por proceso."""
    modo = os.environ.get("TUT_ENCODER", "software").strip().lower() or "software"
    if modo not in MODOS:
        raise ValueError(f"TUT_ENCODER inválido: {modo!r} (opciones: {', '.join(MODOS)})")
    if modo == "software":
        return "software", ""
    if sys.platform.startswith("win"):
        if modo == "vaapi":
            raise EncoderError("TUT_ENCODER=vaapi no está soportado en Windows: usá software o auto")
        print("AVISO: VAAPI no está disponible en Windows: uso libx264", file=sys.stderr)
        return "software", ""
    device = _device()
    ok, motivo = _probar_vaapi(device)
    if ok:
        return "vaapi", device
    if modo == "vaapi":
        raise EncoderError(f"VAAPI no disponible en {device}: {motivo}")
    print(f"VAAPI no disponible ({motivo}): uso libx264", file=sys.stderr)
    return "software", ""


def reset() -> None:
    """Para tests (y para un proceso de larga vida que cambie TUT_ENCODER): olvida la decisión."""
    _elegido.cache_clear()


def preparar() -> None:
    """Decide el encoder ya, en vez de esperar al primer segmento.

    R-1.3: TUT_ENCODER=vaapi sin VAAPI tiene que abortar antes del primer tramo, no a
    mitad del render.
    """
    _elegido()


def vf(vf_actual: str) -> str:
    """Cadena de filtros lista para `-vf`. VAAPI necesita subir el cuadro a la GPU al final."""
    modo, _ = _elegido()
    if modo != "vaapi":
        return vf_actual
    return f"{vf_actual},format=nv12,hwupload" if vf_actual else "format=nv12,hwupload"


def cv_args(crf: int, preset: str = "veryfast", pix_fmt: bool = True) -> list[str]:
    """Args de ffmpeg desde "-c:v" en adelante (o "-vaapi_device" antes, si corresponde)."""
    modo, device = _elegido()
    if modo == "vaapi":
        return ["-vaapi_device", device, "-c:v", "h264_vaapi", "-qp", str(crf)]
    args = ["-c:v", "libx264", "-preset", preset, "-crf", str(crf)]
    if pix_fmt:
        args += ["-pix_fmt", "yuv420p"]
    return args
