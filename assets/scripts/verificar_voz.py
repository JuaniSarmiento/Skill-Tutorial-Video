#!/usr/bin/env python3
"""Detecta tramos de voz con palabras repetidas o de más (alucinaciones típicas de TTS).

Transcribe cada wav con Whisper y lo compara con el texto del guion:
- repeticiones consecutivas ("modelo modelo") que no están en el texto original
- transcripciones mucho más largas que el texto

uso: uv run --with faster-whisper python verificar_voz.py <voz> [vNN ...]
imprime los tramos sospechosos; con --borrar elimina esos wav para que se regeneren.
"""
import json
import os
import re
import sys
from pathlib import Path

from faster_whisper import WhisperModel

ROOT = Path(os.environ.get("TUT_ROOT", os.getcwd()))


def palabras(text: str) -> list[str]:
    return re.findall(r"[a-záéíóúñü0-9]+", text.lower())


def repetidas(ws: list[str]) -> set[str]:
    return {a for a, b in zip(ws, ws[1:]) if a == b and len(a) > 2}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    borrar = "--borrar" in sys.argv
    voz, vids = args[0], args[1:] or sorted(p.stem for p in (ROOT / "guion").glob("v*.json"))
    model = WhisperModel("small", device="cpu", compute_type="int8")
    malos = 0
    for vid in vids:
        guion = json.loads((ROOT / "guion" / f"{vid}.json").read_text())
        for i, seg in enumerate(guion["segmentos"]):
            wav = ROOT / "videos" / vid / voz / f"{i:02d}.wav"
            if not wav.exists():
                continue
            original = palabras(seg["texto"])
            segs, _ = model.transcribe(str(wav), language="es")
            oido = palabras(" ".join(s.text for s in segs))
            extra = repetidas(oido) - repetidas(original)
            ratio = len(oido) / max(len(original), 1)
            if extra or ratio > 1.2:
                malos += 1
                print(f"{vid} seg {i:02d}: repetidas={sorted(extra)} ratio={ratio:.2f}")
                print(f"   oído: {' '.join(oido)[:300]}")
                if borrar:
                    wav.unlink()
                    wav.with_suffix(".txt").unlink(missing_ok=True)
    print(f"sospechosos: {malos}")


if __name__ == "__main__":
    main()
