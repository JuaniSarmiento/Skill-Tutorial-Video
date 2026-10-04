# presentaciones-tupad

Skill de Claude Code que arma presentaciones con el estilo de la cátedra UTN TUPaD: diapositivas `.pptx`
editables y su `.pdf`, a partir de una especificación YAML. El código se lee de los `.py` reales, las salidas
se obtienen ejecutándolos y los diagramas de recursión se dibujan desde una traza real. Antes de entregar,
cada diapositiva se revisa por imagen.

## Instalación

1. Copiar esta carpeta a `~/.claude/skills/presentaciones-tupad/`.
2. Instalar las dependencias de Python en un entorno virtual:
   `python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt`
3. Verificar el sistema (LibreOffice, pdftoppm, fuentes Inter y DejaVu Sans Mono):
   `.venv/bin/python scripts/preflight.py`. Si falta algo, dice qué instalar.

## Uso

Pedirle a Claude, por ejemplo: «armá las diapositivas del video de listas con el código de `codigo/`».

A mano: `python scripts/build.py examples/listas-python/presentacion.yaml -o salida --pdf --hoja`

- `SKILL.md`: el flujo y las reglas. `references/`: formato de la especificación, estilo y lecciones.
- `examples/`: el deck del video «Introducción a la recursividad» (U10) y un ejemplo mínimo de listas,
  con sus hojas de contactos (`*_hoja.png`).
