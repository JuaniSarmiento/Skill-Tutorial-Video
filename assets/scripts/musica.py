"""Música de fondo con ducking bajo la voz (S2 del Hito 2).

La música la pone Juani en TUT_ROOT/musica/ (la skill no la incluye, ver
docs/explicador/HITO2.md, Q1). Se atenúa para quedar por debajo de la voz:
el default es 18 LU en los tramos con voz y 10 LU en los silencios (Q3). La
transición entre niveles es una rampa, no un escalón, para no "bombear".
"""
import re
import subprocess
from pathlib import Path

SILENCIO_LU = 10   # Q3: 10 LU bajo la voz en los silencios (fijo, no configurable en el guion)
MUTE_DB = -90      # "musica": false en un segmento: de sobra por debajo de -60 dBFS (R-2.5)

_RE_INTEGRADA = re.compile(r"Integrated loudness:\s*\n\s*I:\s*(-?\d+\.?\d*) LUFS")


def loudness_integrada(path: Path) -> float:
    """Loudness integrado (LUFS), medido con el filtro ebur128 de ffmpeg."""
    res = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-filter_complex", "ebur128",
                          "-f", "null", "-"], capture_output=True, text=True)
    m = _RE_INTEGRADA.search(res.stderr)
    if not m:
        raise RuntimeError(f"no se pudo medir el loudness de {path}:\n{res.stderr[-1000:]}")
    return float(m.group(1))


_RE_TP = re.compile(r"True peak:\s*\n\s*Peak:\s*(-?\d+\.?\d*) dBFS")


def medir_i_tp(path: Path) -> tuple[float, float]:
    """(I en LUFS, TP en dBTP) de `path`, medidos con ebur128=peak=true."""
    res = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-filter_complex", "ebur128=peak=true",
                          "-f", "null", "-"], capture_output=True, text=True)
    i = _RE_INTEGRADA.search(res.stderr)
    tp = _RE_TP.search(res.stderr)
    if not i or not tp:
        raise RuntimeError(f"no se pudo medir I/TP de {path}:\n{res.stderr[-1000:]}")
    return float(i.group(1)), float(tp.group(1))


def duracion(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError(f"ffprobe no pudo leer {path}: {out.stderr[-500:]}")
    return float(out.stdout)


def ventanas(slots: list[float], voces: list[tuple[float, float] | None]) -> list[tuple[float, float, str]]:
    """[(inicio, fin, nivel)] cubriendo [0, total) sin huecos. nivel: "voz"|"silencio"|"mute".

    `voces[i]` es (inicio_rel, fin_rel) de la voz dentro del slot i (LEAD incluido), o None si
    el segmento tiene `"musica": false`: ahí el slot entero queda "mute".
    """
    out = []
    t = 0.0
    for slot, v in zip(slots, voces):
        if v is None:
            out.append((t, t + slot, "mute"))
        else:
            vi, vf = v
            if vi > 0:
                out.append((t, t + vi, "silencio"))
            out.append((t + vi, t + vf, "voz"))
            if vf < slot:
                out.append((t + vf, t + slot, "silencio"))
        t += slot
    return out


def _expresion_envolvente(vts: list[tuple[float, float, str]], ganancia_db: dict[str, float],
                           ramp: float = 0.15) -> str:
    """Expresión para `-af volume=eval=frame:volume='EXPR'` (multiplicador LINEAL).

    Interpola en rampa (no en escalón) entre niveles: `ramp` segundos centrados en cada
    cambio, recortados si alguna de las dos ventanas vecinas es más chica que eso.
    """
    niveles = [10 ** (ganancia_db[nivel] / 20) for _, _, nivel in vts]
    expr = f"{niveles[0]:.6f}"
    for i in range(len(vts) - 1):
        b = vts[i][1]
        antes, despues = niveles[i], niveles[i + 1]
        ancho_izq = vts[i][1] - vts[i][0]
        ancho_der = vts[i + 1][1] - vts[i + 1][0]
        r = max(min(ramp, ancho_izq, ancho_der), 0.0)
        if r <= 0:
            expr = f"if(lt(t,{b:.6f}),{expr},{despues:.6f})"
            continue
        lo, hi = b - r / 2, b + r / 2
        rampa = f"({antes:.6f}+({despues:.6f}-{antes:.6f})*(t-{lo:.6f})/{r:.6f})"
        expr = f"if(lt(t,{lo:.6f}),{expr},if(lt(t,{hi:.6f}),{rampa},{despues:.6f}))"
    return expr


def aplicar_ducking(pista: Path, vts: list[tuple[float, float, str]], ganancia_db: dict[str, float],
                     out: Path, ramp: float = 0.15) -> None:
    """Aplica la envolvente de ganancia (por ventana, en rampa) a `pista` y la deja en `out`."""
    expr = _expresion_envolvente(vts, ganancia_db, ramp)
    # asetnsamples achica el frame: volume=eval=frame sólo reevalúa la expresión una vez por
    # frame, y el tamaño que trae por default (varios miles de muestras) deja la rampa como
    # uno o dos escalones grandes en vez de una rampa.
    res = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(pista),
                          "-af", f"asetnsamples=n=64,volume=eval=frame:volume='{expr}'", str(out)],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"falló aplicando el ducking: {res.stderr[-1000:]}")


def preparar_pista(archivo: Path, total: float, fundido: float, out: Path) -> None:
    """Deja la música durando exactamente `total` (R-2.4): bucle si es corta, recorte con
    fundido de `fundido` segundos al final si es larga."""
    d = duracion(archivo)
    if d >= total:
        f = min(fundido, total)
        res = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(archivo), "-t", f"{total:.3f}",
             "-af", f"afade=t=out:st={max(total - f, 0):.3f}:d={f:.3f}", str(out)],
            capture_output=True, text=True)
    else:
        vueltas = int(total // d) + 1
        res = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", str(vueltas), "-i", str(archivo),
             "-t", f"{total:.3f}", str(out)],
            capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"falló preparando la pista de música: {res.stderr[-1000:]}")


def construir_pista(voz_wav: Path, pista: Path, vts: list[tuple[float, float, str]],
                     debajo_de_la_voz_lu: float, out: Path) -> None:
    """La pista de música ya atenuada (R-2.2): mide la voz y la música, y calcula cuánta
    ganancia hace falta para que la música quede `debajo_de_la_voz_lu` LU bajo la voz en los
    tramos con voz, y SILENCIO_LU en los silencios. "mute" (musica: false) va a MUTE_DB fijo.
    """
    voz_lu = loudness_integrada(voz_wav)
    musica_lu = loudness_integrada(pista)
    ganancia_db = {
        "voz": (voz_lu - debajo_de_la_voz_lu) - musica_lu,
        "silencio": (voz_lu - SILENCIO_LU) - musica_lu,
        "mute": MUTE_DB,
    }
    aplicar_ducking(pista, vts, ganancia_db, out)


def resolver_archivo(root: Path, archivo: str) -> Path:
    """Ruta absoluta del archivo de música, o aborta (R-2.6) si no existe o no se puede leer."""
    ruta = (root / archivo).resolve()
    if not ruta.exists():
        raise SystemExit(f"ABORTADO: no existe el archivo de música: {ruta}")
    try:
        duracion(ruta)
    except RuntimeError as e:
        raise SystemExit(f"ABORTADO: no se pudo leer el archivo de música {ruta}: {e}")
    return ruta
