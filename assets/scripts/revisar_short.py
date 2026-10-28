"""Director de Shorts verticales: revisa un episodio YA grabado del canal "Fuera de
Rango" sin renderizar nada (sólo lee), igual de espíritu que `editar.py revisar` para
los videos 16:9 de la skill. Ver `references/shorts.md`.

Reusa de `editar.py` lo que ya mide lo mismo (D1: `_freezes`) en vez de copiarlo; lo
que no tiene equivalente ahí (D2 contando cues en vez de specs de escena, D8 por
`escena.forma` en vez de `escena.tipo`, y los chequeos de formato vertical) se escribe
acá. Uso: `revisar_short.py <guion.json> <tiempos.json> <video.mp4> [--estricto]`.
"""
import json
import subprocess
import sys
from pathlib import Path

ANCHO_VERTICAL = 1080
ALTO_VERTICAL = 1920
DURACION_MAXIMA_SHORT = 180.0
TP_MAXIMO_DBFS = -1.0
N_CAMBIO_VISUAL = 6.0  # mismo umbral D1/D2 que la skill 16:9 (editar.N_CAMBIO_VISUAL)


class ChequeoError(Exception):
    """Un chequeo vertical (dimensiones/duración) no pudo correr: ffprobe falló o
    devolvió algo inusable. `revisar_short()` lo convierte en 'no corrió' con la
    causa, nunca en un pase silencioso."""


def _info_video(video: Path) -> dict:
    """Ancho, alto y duración de `video`, leídos con ffprobe en una sola corrida."""
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:format=duration",
         "-of", "json", str(video)],
        capture_output=True, text=True)
    if res.returncode != 0:
        causa = res.stderr.strip().splitlines()[-1] if res.stderr.strip() else f"código {res.returncode}"
        raise ChequeoError(causa)
    try:
        datos = json.loads(res.stdout)
        return {
            "ancho": datos["streams"][0]["width"],
            "alto": datos["streams"][0]["height"],
            "duracion": float(datos["format"]["duration"]),
        }
    except (KeyError, IndexError, ValueError, json.JSONDecodeError) as e:
        raise ChequeoError(f"ffprobe no devolvió datos usables: {e}") from e


def _hallazgos_ritmo_forma(segmentos: list[dict]) -> tuple[list[str], list[str]]:
    """D8 vertical (hallazgos, no_corrio): ninguna racha de MÁS de 2 segmentos
    consecutivos con la misma `escena.forma` (no `escena.tipo`: en el canal el
    `tipo` es un nombre único por escena -p.ej. "z34_boca_433", "z34_boca_paredes"-
    aunque varias compartan la misma forma visual -"cancha"-, así que medir por
    `tipo` no vería la racha real).

    Si NINGÚN segmento del guion declara `forma`, D8 no tiene con qué medir: se
    informa en `no_corrio` (nunca un pase silencioso), no en `hallazgos`."""
    formas_declaradas = [s.get("escena", {}).get("forma") for s in segmentos
                          if isinstance(s.get("escena"), dict)]
    if not any(formas_declaradas):
        return [], ["D8 no corrió: el guion no declara escena.forma"]

    hallazgos: list[str] = []
    racha_forma = None
    racha_inicio = 0
    racha_largo = 0

    def _cerrar(hasta: int):
        if racha_largo > 2:
            hallazgos.append(
                f"ritmo: {racha_largo} escenas '{racha_forma}' seguidas (segmentos "
                f"{racha_inicio}-{hasta}), variá la forma de escena")

    for i, seg in enumerate(segmentos):
        escena = seg.get("escena")
        forma = escena.get("forma") if isinstance(escena, dict) else None
        if forma is not None and forma == racha_forma:
            racha_largo += 1
        else:
            _cerrar(i - 1)
            racha_forma = forma
            racha_inicio = i
            racha_largo = 1 if forma is not None else 0
    _cerrar(len(segmentos) - 1)
    return hallazgos, []


def _huecos_tiempos(tiempos: dict, n: float) -> list[tuple[float, float]]:
    """D2 vertical: tramos de más de n segundos sin una entrada nueva, contando como
    entrada el inicio de cada segmento y el tiempo de cada cue (`tiempos.json`, no el
    guion: acá no hay specs de escena resueltos para medir, como en D2 16:9)."""
    entradas = set()
    for seg in tiempos["segmentos"]:
        entradas.add(float(seg["inicio"]))
        for t in seg.get("cues", {}).values():
            entradas.add(float(t))
    total = tiempos["total"]
    puntos = [0.0, *sorted(entradas), total]
    return [(a, b) for a, b in zip(puntos, puntos[1:]) if b - a > n]


def revisar_short(guion_path: Path, tiempos_path: Path, video_path: Path,
                   n: float = N_CAMBIO_VISUAL) -> tuple[list[str], list[str]]:
    """(hallazgos, no_corrio) de revisar un episodio del canal YA grabado y publicado.

    Sólo lee: nunca renderiza ni modifica nada. Si un chequeo no puede correr
    (archivo faltante, ffprobe/ffmpeg falla) es un hallazgo 'no corrió', nunca un
    pase silencioso (mismo criterio que `editar.revisar`)."""
    import editar
    import musica

    hallazgos: list[str] = []
    no_corrio: list[str] = []

    if video_path.exists():
        # D1: tiempo muerto en el video (REUSADO de editar.py, no copiado).
        try:
            for inicio, fin in editar._freezes(video_path, n):
                hallazgos.append(
                    f"tiempo muerto: {inicio:.1f}s–{fin:.1f}s sin cambio visual "
                    f"(> {n:.0f}s) en {video_path.name}")
        except editar.ChequeoError as e:
            no_corrio.append(f"tiempo muerto: no corrió, {video_path.name} parece "
                              f"vacío o corrupto ({e})")

        # Vertical: dimensiones, duración (aviso si pasa de 180s) y loudness
        # (aviso si el true peak supera -1 dBFS).
        try:
            info = _info_video(video_path)
        except ChequeoError as e:
            no_corrio.append(f"vertical: no corrió, {video_path.name} ({e})")
        else:
            if (info["ancho"], info["alto"]) != (ANCHO_VERTICAL, ALTO_VERTICAL):
                hallazgos.append(
                    f"vertical: {video_path.name} mide {info['ancho']}x{info['alto']}, "
                    f"se esperaba {ANCHO_VERTICAL}x{ALTO_VERTICAL}")
            if info["duracion"] > DURACION_MAXIMA_SHORT:
                hallazgos.append(
                    f"aviso: {video_path.name} dura {info['duracion']:.1f}s "
                    f"(> {DURACION_MAXIMA_SHORT:.0f}s), ya no es Short en YouTube")
        try:
            _, tp = musica.medir_i_tp(video_path)
        except RuntimeError as e:
            no_corrio.append(f"loudness: no corrió, {video_path.name} ({e})")
        else:
            if tp > TP_MAXIMO_DBFS:
                hallazgos.append(
                    f"aviso: {video_path.name} true peak {tp:.1f} dBFS "
                    f"(> {TP_MAXIMO_DBFS:.0f} dBFS)")
    else:
        no_corrio.append(f"tiempo muerto: no corrió, falta {video_path}")
        no_corrio.append(f"vertical: no corrió, falta {video_path}")

    # D2: huecos de entradas, desde tiempos.json (no renderiza nada).
    if tiempos_path.exists():
        try:
            tiempos = json.loads(tiempos_path.read_text())
            for desde, hasta in _huecos_tiempos(tiempos, n):
                hallazgos.append(
                    f"{tiempos_path.name}: {desde:.1f}s–{hasta:.1f}s sin entrada "
                    f"nueva (> {n:.0f}s)")
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            no_corrio.append(f"entradas: no corrió, {tiempos_path.name} ({e})")
    else:
        no_corrio.append(f"entradas: no corrió, falta {tiempos_path}")

    # D8: ritmo por escena.forma, desde el guion.
    if guion_path.exists():
        try:
            guion = json.loads(guion_path.read_text())
            segmentos = guion["segmentos"]
        except (json.JSONDecodeError, KeyError) as e:
            no_corrio.append(f"ritmo: no corrió, {guion_path.name} ({e})")
        else:
            h, nc = _hallazgos_ritmo_forma(segmentos)
            hallazgos.extend(h)
            no_corrio.extend(nc)
    else:
        no_corrio.append(f"ritmo: no corrió, falta {guion_path}")

    return hallazgos, no_corrio


def informe(nombre: str, hallazgos: list[str], no_corrio: list[str]) -> str:
    lineas = [f"director de shorts: {nombre}"]
    lineas += [f"  - {h}" for h in hallazgos] if hallazgos else ["  sin hallazgos"]
    if no_corrio:
        lineas.append("chequeos que no corrieron:")
        lineas += [f"  - {c}" for c in no_corrio]
    return "\n".join(lineas)


USO = "uso: revisar_short.py <guion.json> <tiempos.json> <video.mp4> [--estricto]"


def _dispatch(args: list[str]) -> int:
    import editar

    flags = [a for a in args if a.startswith("-")]
    desconocidos = [f for f in flags if f != "--estricto"]
    if desconocidos:
        print(f"revisar_short.py: flag desconocido {desconocidos[0]!r} (válido: --estricto)",
              file=sys.stderr)
        print(USO, file=sys.stderr)
        return 2
    posicionales = [a for a in args if not a.startswith("-")]
    if len(posicionales) != 3:
        print(f"revisar_short.py: se esperan 3 argumentos, se recibieron {len(posicionales)}",
              file=sys.stderr)
        print(USO, file=sys.stderr)
        return 2
    guion_path, tiempos_path, video_path = (Path(p) for p in posicionales)
    estricto = "--estricto" in flags
    hallazgos, no_corrio = revisar_short(guion_path, tiempos_path, video_path)
    print(informe(guion_path.stem, hallazgos, no_corrio))
    return 1 if estricto and editar._estricto_falla(hallazgos, no_corrio) else 0


if __name__ == "__main__":
    sys.exit(_dispatch(sys.argv[1:]))
