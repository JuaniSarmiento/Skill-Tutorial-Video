"""Detección de momentos clave para el zoom automático, a partir de diferencias entre
cuadros del crudo (S7a del Hito 2, docs/explicador/HITO2.md: decisión Q5 de Juani del
03/10/2026 — los momentos salen de analizar los cuadros grabados, no de coordenadas que
`rec.py` nunca guardó, y así funciona también con lo que ya está grabado hoy).

Analiza el crudo ANTES de mpdecimate (igual que el recorte del zoom fijo en `editar.py`),
muestreando a pocos fps y en escala de grises a baja resolución: así el diff se hace en
Python puro, sin numpy (no está instalado en el entorno fijo de los tests de este repo,
`uv run --with pytest --with playwright ...`).

Formato de salida (`videos/<vNN>/zonas/NN.json`, uno por segmento de pantalla):
  [{"t": segundos en el eje del CRUDO (el mismo que seg["inicio"]/seg["fin"]),
    "x", "y", "w", "h": caja en píxeles del crudo (sin escalar, misma convención que el
    "zoom": {x,y,w,h} fijo de editar.py), "importancia": número, mayor = cambio más
    grande}, ...]
No decide CUÁLES usar ni limita la frecuencia entre acercamientos: eso es trabajo de S7b
(R-7.2 como mucho un acercamiento cada 3 s, R-7.4 sin momentos clave).
"""
import array
import tempfile
from pathlib import Path

import editar

FPS_MUESTREO = 2.0       # muestras por segundo analizadas
ANCHO_MUESTRA = 160      # ancho (px) del cuadro reducido para el diff en Python puro
UMBRAL_GRIS = 30         # diferencia de gris (0-255) para contar un píxel como "cambiado"
AREA_MIN_FRAC = 0.0015   # por debajo: ruido (cursor parpadeando, reloj) -> no es momento
AREA_MAX_FRAC = 0.35     # por encima: cambia casi toda la pantalla (scroll) -> no es momento


def _diff_bbox(a: bytes, b: bytes, ancho: int, umbral: int) -> tuple[int, int, int, int] | None:
    """(x0, y0, x1, y1) -caja semiabierta- de los píxeles donde `b` difiere de `a` en más
    de `umbral` (escala de grises, 0-255). None si no hay ninguno."""
    av = array.array("B", a)
    bv = array.array("B", b)
    x0 = y0 = None
    x1 = y1 = -1
    for i in range(len(av)):
        if abs(av[i] - bv[i]) > umbral:
            x, y = i % ancho, i // ancho
            if x0 is None or x < x0:
                x0 = x
            if y0 is None or y < y0:
                y0 = y
            if x > x1:
                x1 = x
            if y > y1:
                y1 = y
    if x0 is None:
        return None
    return x0, y0, x1 + 1, y1 + 1


def _momentos_en_cuadros(cuadros_con_t: list[tuple[float, bytes]], ancho: int, alto: int,
                          escala: float, *, umbral: int, area_min_frac: float,
                          area_max_frac: float) -> list[dict]:
    """[{t,x,y,w,h,importancia}] a partir de una secuencia de (t, cuadro en escala de
    grises) ya muestreada.

    Compara cada cuadro contra un "estado estable" (`base`), que arranca en el primer
    cuadro y sólo se actualiza cuando el cambio no es ruido (ver abajo). Así:
      - un cambio demasiado chico (cursor parpadeando, reloj) se ignora y NO mueve la
        base: lo que vino antes del parpadeo sigue siendo la referencia.
      - un cambio demasiado grande (scroll: cambia casi toda la pantalla) no es un
        momento, pero SÍ actualiza la base (si no, todo lo que pase después del scroll
        se seguiría comparando contra la pantalla de antes, y "cambiaría" siempre).
      - un cambio que se sostiene en el cuadro siguiente (no vuelve a la base) es un
        momento de verdad: se guarda y la base pasa a ser este nuevo estado.
      - un cambio que YA volvió a la base en el cuadro siguiente es un parpadeo
        (cursor, reloj): no se guarda y la base no se mueve.
    """
    if len(cuadros_con_t) < 2:
        return []
    area_total = ancho * alto
    momentos: list[dict] = []
    base = cuadros_con_t[0][1]
    i = 1
    while i < len(cuadros_con_t):
        t_k, f_k = cuadros_con_t[i]
        bbox = _diff_bbox(base, f_k, ancho, umbral)
        if bbox is None:
            i += 1
            continue
        x0, y0, x1, y1 = bbox
        frac = (x1 - x0) * (y1 - y0) / area_total
        if frac < area_min_frac:
            i += 1
            continue
        if frac > area_max_frac:
            base = f_k
            i += 1
            continue
        if i + 1 < len(cuadros_con_t):
            f_sig = cuadros_con_t[i + 1][1]
            volvio_a_la_base = _diff_bbox(base, f_sig, ancho, umbral) is None
        else:
            volvio_a_la_base = False
        if volvio_a_la_base:
            i += 1
            continue
        momentos.append({
            "t": t_k,
            "x": round(x0 * escala), "y": round(y0 * escala),
            "w": round((x1 - x0) * escala), "h": round((y1 - y0) * escala),
            "importancia": round(frac, 6),
        })
        base = f_k
        i += 1
    return momentos


def _dimensiones(path: Path) -> tuple[int, int]:
    """(ancho, alto) en píxeles del stream de video de `path`."""
    out = editar.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                      "stream=width,height", "-of", "csv=p=0", str(path)])
    w, h = out.strip().split(",")
    return int(w), int(h)


def _muestras(raw: Path, inicio: float, fin: float, fps: float, ancho: int) -> tuple[list[bytes], int, int, float]:
    """Cuadros en escala de grises de `raw` entre [`inicio`, `fin`), muestreados a `fps`
    y reducidos a `ancho` px de ancho (par de alto, preservando la relación de aspecto).

    Devuelve (cuadros, ancho_real, alto_real, escala) donde `escala` es el factor para
    volver a píxeles del crudo (ancho_original / `ancho`, igual en los dos ejes).
    """
    w0, h0 = _dimensiones(raw)
    escala = w0 / ancho
    alto = max(2, round(h0 / escala / 2) * 2)
    with tempfile.TemporaryDirectory() as tmp:
        salida = Path(tmp) / "muestras.raw"
        editar.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{inicio:.3f}", "-to", f"{fin:.3f}",
                    "-i", str(raw), "-vf", f"fps={fps},scale={ancho}:{alto}:flags=neighbor",
                    "-f", "rawvideo", "-pix_fmt", "gray", str(salida)])
        datos = salida.read_bytes()
    tam = ancho * alto
    cuadros = [datos[i:i + tam] for i in range(0, len(datos) - tam + 1, tam)]
    return cuadros, ancho, alto, escala


def detectar_momentos(raw: Path, inicio: float, fin: float, *, fps: float = FPS_MUESTREO,
                       ancho: int = ANCHO_MUESTRA, umbral: int = UMBRAL_GRIS,
                       area_min_frac: float = AREA_MIN_FRAC,
                       area_max_frac: float = AREA_MAX_FRAC) -> list[dict]:
    """[{t,x,y,w,h,importancia}] detectados en `raw` entre `inicio` y `fin` (segundos,
    en el eje del propio crudo)."""
    cuadros, anchop, altop, escala = _muestras(raw, inicio, fin, fps, ancho)
    paso = 1.0 / fps
    con_t = [(inicio + i * paso, c) for i, c in enumerate(cuadros)]
    return _momentos_en_cuadros(con_t, anchop, altop, escala, umbral=umbral,
                                area_min_frac=area_min_frac, area_max_frac=area_max_frac)
