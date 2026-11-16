"""Generador de imágenes falso para la aceptación de HU-03 (reemplaza a Codex).

Anota cada llamada en $GEN_LOG (una línea JSON) y dibuja un muñeco sobre fondo blanco.
Si el prompt dice «boca abierta», la boca sale más grande. Con GEN_FALLA=1 sale con error.
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw

p = argparse.ArgumentParser()
p.add_argument("--prompt", required=True)
p.add_argument("--salida", required=True)
p.add_argument("--referencia", action="append", default=[])
a = p.parse_args()
with open(os.environ["GEN_LOG"], "a") as f:
    f.write(json.dumps({"prompt": a.prompt, "salida": a.salida, "referencia": a.referencia}) + "\n")
if os.environ.get("GEN_FALLA") == "1":
    print("generador: sin cuota", file=sys.stderr)
    sys.exit(1)
im = Image.new("RGB", (1024, 1536), "white")
d = ImageDraw.Draw(im)
d.ellipse((362, 200, 662, 500), fill=(250, 210, 180), outline="black", width=8)      # cabeza
d.rectangle((312, 520, 712, 1300), fill=(150, 190, 230), outline="black", width=8)   # cuerpo
d.rectangle((362, 1300, 482, 1480), fill=(90, 90, 120), outline="black", width=8)    # piernas
d.rectangle((542, 1300, 662, 1480), fill=(90, 90, 120), outline="black", width=8)
if "boca abierta" in a.prompt.lower():
    d.ellipse((462, 400, 562, 470), fill=(120, 30, 40), outline="black", width=6)
else:
    d.line((472, 430, 552, 430), fill="black", width=8)
os.makedirs(os.path.dirname(os.path.abspath(a.salida)), exist_ok=True)
im.save(a.salida)
