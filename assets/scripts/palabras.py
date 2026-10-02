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

uso: uv run --with faster-whisper python palabras.py <audio> [salida.json] [--modelo base]
"""
import json
import re
import unicodedata
from pathlib import Path

MODELO = "base"  # "small" es mejor pero no entra en 1 GB de RAM libre junto a Chrome


def transcribir(audio, modelo=None) -> list[dict]:
    """Audio -> [{palabra, inicio, fin}] con los tiempos redondeados a ms."""
    if modelo is None or isinstance(modelo, str):
        from faster_whisper import WhisperModel
        modelo = WhisperModel(modelo or MODELO, device="cpu", compute_type="int8")
    segmentos, _ = modelo.transcribe(str(audio), language="es", word_timestamps=True)
    return [{"palabra": w.word.strip(), "inicio": round(w.start, 3), "fin": round(w.end, 3)}
            for s in segmentos for w in s.words]


def _norm(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", texto.lower())
    sin_tildes = "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9ñ]+", " ", sin_tildes).strip()


def _frase(cue: str) -> list[str]:
    m = re.search(r"cuando dice\s+['\"‘“](.+?)['\"’”]", cue)
    return _norm(m.group(1) if m else cue).split()


def _buscar(palabras: list[dict], cue: str, desde_idx: int) -> int:
    """Índice de la primera palabra de `cue` a partir de desde_idx; ValueError si no está."""
    frase = _frase(cue)
    if not frase:
        raise ValueError(f"la cue {cue!r} está vacía: no nombra ninguna palabra")
    oidas = [_norm(p["palabra"]) for p in palabras]
    for i in range(desde_idx, len(oidas) - len(frase) + 1):
        if oidas[i:i + len(frase)] == frase:
            return i
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
