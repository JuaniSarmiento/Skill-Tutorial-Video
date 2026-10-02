#!/usr/bin/env python3
"""Tiempos por palabra de una voz ya generada, y resolución de cues.

Una escena hace entrar cada elemento EN LA PALABRA QUE LO NOMBRA. Para eso hace
falta saber en qué segundo se dice cada palabra, y eso sale de transcribir la
voz con faster-whisper (`word_timestamps=True`). Se transcribe el audio real y
no se le piden los tiempos al proveedor de TTS: así funciona con cualquier voz
(decisión del PLAN, docs/explicador/PLAN.md).

Una "cue" se escribe de tres formas:
  "base de datos"                 la frase, tal cual se dice
  "cuando dice 'base de datos'"   la misma frase, en la forma larga del guion
  1.5                             un tiempo en segundos, para cuando no hay voz

uso: uv run --with faster-whisper --with "av<19" python palabras.py <audio> [salida.json] [--modelo base]
"""
import json
import re
import unicodedata
from pathlib import Path

# Whisper escribe en dígitos lo que la voz dice en palabras ("2 décadas"). Se
# normalizan los dos lados igual, así que "una" pasa a "1" también como artículo.
NUMEROS = dict(zip(
    "cero uno una un dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce "
    "quince veinte treinta cuarenta cincuenta sesenta setenta ochenta noventa cien".split(),
    "0 1 1 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 20 30 40 50 60 70 80 90 100".split()))
# Whisper oye mal alguna letra ("tembrano" por "temprano"): se tolera UN error por
# palabra, y sólo en palabras de LARGA letras o más. Una palabra corta con una letra
# distinta es otra palabra ("sí"/"sin", "tasa"/"casa", "banco"/"blanco"), y un número
# con un dígito distinto es otro número ("10"/"100"): esos tienen que estar tal cual.
LARGA = 6

MODELO = "base"  # "small" es mejor pero no entra en 1 GB de RAM libre junto a Chrome


def transcribir(audio, modelo=None) -> list[dict]:
    """Audio -> [{palabra, inicio, fin}] con los tiempos redondeados a ms."""
    if modelo is None or isinstance(modelo, str):
        from faster_whisper import WhisperModel
        modelo = WhisperModel(modelo or MODELO, device="cpu", compute_type="int8")
    segmentos, _ = modelo.transcribe(str(audio), language="es", word_timestamps=True)
    return [{"palabra": w.word.strip(), "inicio": round(w.start, 3), "fin": round(w.end, 3)}
            for s in segmentos for w in s.words]


def _sin_tilde(c: str) -> str:
    # la ñ es otra letra, no una n con tilde: "año" no es "ano"
    if c == "ñ":
        return c
    return "".join(x for x in unicodedata.normalize("NFD", c) if unicodedata.category(x) != "Mn")


def _norm(texto: str) -> str:
    sin_tildes = "".join(_sin_tilde(c) for c in unicodedata.normalize("NFC", texto.lower()))
    palabras = re.sub(r"[^a-z0-9ñ]+", " ", sin_tildes).split()
    return " ".join(NUMEROS.get(w, w) for w in palabras)


def _distancia(a: str, b: str) -> int:
    """Levenshtein: cuántas letras hay que agregar, sacar o cambiar."""
    fila = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        previa, fila[0] = fila[0], i
        for j, cb in enumerate(b, 1):
            previa, fila[j] = fila[j], min(fila[j] + 1, fila[j - 1] + 1, previa + (ca != cb))
    return fila[-1]


def _tolera(texto: str) -> int:
    return 0 if len(texto) < LARGA or any(c.isdigit() for c in texto) else 1


def _errores(frase: list[str], oidas: list[str]):
    """Errores entre la frase de la cue y un tramo oído, o None si no es la misma frase."""
    if len(frase) == len(oidas):
        d = [_distancia(f, o) for f, o in zip(frase, oidas)]
        return sum(d) if all(x <= _tolera(f) for x, f in zip(d, frase)) else None
    # Whisper pegó o partió palabras ("se suma" -> "esuma"): se compara la frase
    # junta, pero los números tienen que estar tal cual
    if any(any(c.isdigit() for c in f) and f not in oidas for f in frase):
        return None
    junta = "".join(frase)
    d = _distancia(junta, "".join(oidas))
    return d if d <= _tolera(junta) else None


def _frase(cue: str) -> list[str]:
    m = re.search(r"cuando dice\s+['\"‘“](.+?)['\"’”]", cue)
    return _norm(m.group(1) if m else cue).split()


def _buscar(palabras: list[dict], cue: str, desde_idx: int) -> int:
    """Índice de la primera palabra de `cue` a partir de desde_idx; ValueError si no está.

    Se queda con el tramo con menos errores (con 1 palabra de más o de menos,
    porque Whisper a veces pega dos: "se suma" -> "esuma"); a igual cantidad, el
    primero. La frase exacta tiene 0 errores, así que siempre le gana a una parecida.
    Ver LARGA para qué error se tolera y cuál no.
    """
    frase = _frase(cue)
    if not frase:
        raise ValueError(f"la cue {cue!r} está vacía: no nombra ninguna palabra")
    oidas = [_norm(p["palabra"]) for p in palabras]
    n = len(frase)
    mejor, idx = None, None
    for i in range(desde_idx, len(oidas)):
        for k in (n - 1, n, n + 1):
            if k >= 1 and i + k <= len(oidas):
                e = _errores(frase, " ".join(oidas[i:i + k]).split())
                if e is not None and (mejor is None or e < mejor):
                    mejor, idx = e, i
    if idx is not None:
        return idx
    dicho = " ".join(p["palabra"] for p in palabras)
    raise ValueError(f"la cue {cue!r} no se dice en la voz. Se oyó: {dicho[:300]!r}")


def resolver_cue(palabras: list[dict], cue, desde: float = 0.0) -> float:
    """Segundo en que empieza la cue (la primera aparición desde `desde`)."""
    if isinstance(cue, (int, float)):
        return float(cue)
    idx = next((i for i, p in enumerate(palabras) if p["inicio"] >= desde), len(palabras))
    return palabras[_buscar(palabras, cue, idx)]["inicio"]


def resolver_cues(palabras: list[dict], cues: list) -> list[float]:
    """Resuelve varias cues. El orden de la lista NO tiene que ser el orden en que se dicen.

    Un diagrama lista sus nodos y después sus flechas, pero la voz los intercala.
    Cada frase se busca sola; si la misma frase se repite ("la base", "la base"),
    cada repetición toma la aparición siguiente a la anterior de ESA frase.
    """
    tiempos, ultima = [], {}
    for cue in cues:
        if isinstance(cue, (int, float)):
            tiempos.append(float(cue))
            continue
        clave = tuple(_frase(cue))
        i = _buscar(palabras, cue, ultima.get(clave, -1) + 1)
        ultima[clave] = i
        tiempos.append(palabras[i]["inicio"])
    return tiempos


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="audio -> palabras.json [{palabra, inicio, fin}]")
    ap.add_argument("audio")
    ap.add_argument("salida", nargs="?", help="sin esto, imprime el JSON")
    ap.add_argument("--modelo", default=MODELO, help="tiny | base | small (default: base)")
    a = ap.parse_args()
    salida = json.dumps(transcribir(a.audio, a.modelo), ensure_ascii=False, indent=1)
    if a.salida:
        Path(a.salida).write_text(salida)
    else:
        print(salida)
