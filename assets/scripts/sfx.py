"""Efectos de sonido sobre palabras (S3 del Hito 2, docs/explicador/HITO2.md).

Decisión Q1 (Juani, 03/10/2026): sin licencia. La skill trae un set chico de
sonidos generados con ffmpeg (lavfi), reproducibles: no hay archivo que versionar
ni derechos que pedir. El guion los referencia por nombre ("archivo": "pop") o,
si Juani quiere un sonido propio, por una ruta relativa a TUT_ROOT (igual que
"musica", ver musica.py).

Cada sonido generado es corto, con fundidos en los dos bordes (sin click de
entrada ni de salida) y a un nivel discreto (`volume=` ya adentro del filtro):
por debajo de la voz por defecto. El guion puede subir o bajar eso con
"ganancia_db" (dB que se suman a este nivel base, no lo reemplazan).
"""
from pathlib import Path

SR = 44100  # suficiente para los tonos y el ruido filtrado de abajo; se resamplea al mezclar

# nombre -> filtro lavfi que YA incluye el fundido de entrada/salida y el nivel
# discreto (volume=). Guía del Director en SKILL.md: usar uno en el dato clave o el
# remate, nunca en cada frase.
_GENERADORES = {
    "pop": "sine=f=900:d=0.12,afade=t=in:d=0.005,afade=t=out:st=0.07:d=0.05,volume=0.35",
    "click": "sine=f=2200:d=0.05,afade=t=in:d=0.003,afade=t=out:st=0.03:d=0.02,volume=0.3",
    "whoosh": ("anoisesrc=color=white:d=0.4:seed=3,highpass=f=600,lowpass=f=3500,"
               "afade=t=in:d=0.1,afade=t=out:st=0.28:d=0.12,volume=0.3"),
    "ding": "sine=f=1318.5:d=0.5,afade=t=in:d=0.01,afade=t=out:st=0.08:d=0.42,volume=0.3",
}

SONIDOS = tuple(_GENERADORES)


def _generar(nombre: str, out: Path) -> None:
    """Genera el sonido `nombre` (uno de SONIDOS) en `out`, mono, mediante ffmpeg -f lavfi.

    Import perezoso de `editar` (mismo motivo que musica.py): así cualquier ffmpeg de
    este módulo pasa por el vigía anti-cuelgue de `editar.run()`, sin crear un ciclo de
    import (editar importa sfx arriba del archivo; acá sólo cuando la función corre).
    """
    import editar
    editar.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", _GENERADORES[nombre],
                "-ar", str(SR), "-ac", "1", str(out)])


def resolver_archivo(root: Path, archivo: str, cache_dir: Path) -> Path:
    """Ruta absoluta del wav de un efecto.

    Si `archivo` es uno de SONIDOS, se genera (o se reusa, cacheado por nombre en
    `cache_dir`). Si no, es una ruta propia relativa a `root` (TUT_ROOT); si no existe,
    aborta (SystemExit) con su ruta absoluta, igual que `musica.resolver_archivo`.
    """
    if archivo in _GENERADORES:
        cache_dir.mkdir(parents=True, exist_ok=True)
        out = cache_dir / f"{archivo}.wav"
        if not out.exists():
            _generar(archivo, out)
        return out
    ruta = (root / archivo).resolve()
    if not ruta.exists():
        raise SystemExit(f"ABORTADO: no existe el archivo de sfx: {ruta}")
    return ruta


def construir_pista(duracion_total: float, efectos: list[tuple[float, Path, float]], out: Path) -> None:
    """Pista mono de `duracion_total` segundos con cada efecto sonando en su `t` absoluto.

    `efectos` es [(t, archivo, ganancia_db)]: `ganancia_db` se SUMA al nivel discreto que
    ya trae el propio archivo (0.0 lo deja igual). Sin efectos, queda silencio (R3: sin
    "sfx" en el guion esto no se llama, así que no hay regresión sobre G1-G4).

    `-t duracion_total` en el comando de salida (no sólo en el filtro): un `apad` o un
    `amix=duration=longest` sin ese límite en la línea de comando puede crecer sin fin
    (mismo bug ya visto en musica.py con la mezcla voz+música).
    """
    import editar
    if not efectos:
        editar.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"anullsrc=r={SR}:cl=mono", "-t", f"{duracion_total:.3f}", str(out)])
        return
    inputs = []
    ramas = []
    for i, (t, archivo, ganancia_db) in enumerate(efectos):
        inputs += ["-i", str(archivo)]
        ms = max(round(t * 1000), 0)
        ramas.append(f"[{i}:a]aformat=sample_rates={SR}:channel_layouts=mono,"
                     f"adelay={ms}:all=1,volume={ganancia_db}dB[e{i}]")
    mapa = "".join(f"[e{i}]" for i in range(len(efectos)))
    filtro = ";".join(ramas) + f";{mapa}amix=inputs={len(efectos)}:duration=longest:normalize=0[out]"
    editar.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", filtro,
               "-map", "[out]", "-t", f"{duracion_total:.3f}", str(out)])
